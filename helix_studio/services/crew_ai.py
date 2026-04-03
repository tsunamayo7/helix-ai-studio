"""CrewAI統合 — Ollamaローカルモデル専用マルチエージェント

CrewAIをOllamaローカルLLM専用で使用し、複数エージェントが協調して
複雑なタスクを遂行する。VRAM圧迫を避けるため、同時に使用するモデルは
1つに制限し、エージェント間でモデルを切り替える Sequential 方式を採用。

VRAM使用量の目安（RTX PRO 6000 96GB）:
  - 120Bモデル: ~80GB → 単独使用のみ
  - 27Bモデル: ~16GB → 最大5モデル同時
  - 8Bモデル: ~6GB → 最大15モデル同時
  - 推奨構成: 27B x1（メイン） + 8B x1（補助） = ~22GB
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import httpx

logger = logging.getLogger(__name__)


# ── VRAM管理 ──────────────────────────────────────────


async def detect_gpu_vram() -> float:
    """GPUのVRAM合計を自動検出（nvidia-smi経由）。失敗時は0を返す。"""
    import subprocess
    try:
        result = await asyncio.to_thread(
            subprocess.run,
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            total = sum(int(line.strip()) for line in result.stdout.strip().split("\n") if line.strip())
            return round(total / 1024, 1)  # MB -> GB
    except Exception as e:
        logger.debug("GPU VRAM自動検出失敗: %s", e)
    return 0


async def get_effective_vram_total() -> float:
    """ユーザー設定またはGPU自動検出からVRAM合計を取得"""
    try:
        from helix_studio.config import get_setting
        user_setting = await get_setting("gpu_vram_total")
        if user_setting and float(user_setting) > 0:
            return float(user_setting)
    except Exception:
        pass
    # 自動検出
    detected = await detect_gpu_vram()
    if detected > 0:
        return detected
    return 24.0  # 検出不可時のフォールバック（一般的なGPU想定）


@dataclass
class VRAMBudget:
    """VRAM使用量管理。同時ロードモデルを制限する。"""
    total_gb: float = 24.0  # detect_gpu_vram()で上書きされる
    reserved_gb: float = 2.0  # OS/CUDA overhead
    loaded_models: dict[str, float] = field(default_factory=dict)

    @property
    def available_gb(self) -> float:
        used = sum(self.loaded_models.values())
        return self.total_gb - self.reserved_gb - used

    def can_load(self, model_name: str, size_gb: float) -> bool:
        if model_name in self.loaded_models:
            return True
        return size_gb <= self.available_gb

    def register(self, model_name: str, size_gb: float):
        self.loaded_models[model_name] = size_gb

    def unregister(self, model_name: str):
        self.loaded_models.pop(model_name, None)

    def summary(self) -> dict:
        used = sum(self.loaded_models.values())
        return {
            "total_gb": self.total_gb,
            "used_gb": round(used, 1),
            "available_gb": round(self.available_gb, 1),
            "loaded_models": dict(self.loaded_models),
        }


# モデルサイズ推定（Ollamaのメタデータから取得できなければこのテーブルを参照）
MODEL_SIZE_ESTIMATES_GB: dict[str, float] = {
    "nemotron-3-super:120b": 81.0,
    "qwen3.5:122b": 76.0,
    "devstral-2:123b": 70.0,
    "command-a:latest": 63.0,
    "gpt-oss:120b": 61.0,
    "qwen3-next:80b": 47.0,
    "nemotron-cascade-2:latest": 23.0,
    "nemotron-3-nano:30b": 23.0,
    "gemma4:31b": 18.0,
    "gemma3:27b": 16.0,
    "translategemma:27b": 16.0,
    "mistral-small3.2:latest": 14.0,
    "ministral-3:14b": 9.0,
    "ministral-3:8b": 6.0,
    "gemma3:4b": 3.0,
}


def estimate_model_size(model_name: str) -> float:
    """モデルのVRAM使用量を推定（GB）"""
    if model_name in MODEL_SIZE_ESTIMATES_GB:
        return MODEL_SIZE_ESTIMATES_GB[model_name]
    # パラメータ数から推定（名前に含まれるパターン）
    for suffix in ["120b", "122b", "123b"]:
        if suffix in model_name:
            return 75.0
    for suffix in ["80b"]:
        if suffix in model_name:
            return 47.0
    for suffix in ["27b", "30b"]:
        if suffix in model_name:
            return 20.0
    for suffix in ["14b"]:
        if suffix in model_name:
            return 9.0
    for suffix in ["8b", "7b"]:
        if suffix in model_name:
            return 6.0
    for suffix in ["4b", "3b"]:
        if suffix in model_name:
            return 3.0
    return 10.0  # デフォルト


async def get_vram_status(ollama_url: str) -> dict:
    """現在のOllama VRAM使用状況を取得"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{ollama_url}/api/ps")
            resp.raise_for_status()
            data = resp.json()
            loaded = {}
            for m in data.get("models", []):
                name = m.get("name", "unknown")
                size_gb = m.get("size_vram", m.get("size", 0)) / (1024**3)
                loaded[name] = round(size_gb, 1)
            return {
                "loaded_models": loaded,
                "total_vram_used_gb": round(sum(loaded.values()), 1),
            }
    except Exception as e:
        logger.debug("VRAM状況取得失敗: %s", e)
        return {"loaded_models": {}, "total_vram_used_gb": 0}


# ── CrewAIエージェント定義 ────────────────────────────


@dataclass
class AgentRole:
    """エージェントの役割定義"""
    name: str
    role: str
    goal: str
    model: str  # Ollamaモデル名
    backstory: str = ""


# プリセット役割チーム
PRESET_TEAMS: dict[str, list[AgentRole]] = {
    "dev_team": [
        AgentRole(
            name="architect",
            role="ソフトウェアアーキテクト",
            goal="要件を分析し、最適なアーキテクチャと実装計画を設計する",
            model="gemma3:27b",
            backstory="大規模システムの設計経験が豊富なアーキテクト",
        ),
        AgentRole(
            name="engineer",
            role="バックエンドエンジニア",
            goal="アーキテクトの設計に基づき、高品質なコードを実装する",
            model="gemma3:27b",
            backstory="Python/FastAPIに精通したエンジニア",
        ),
        AgentRole(
            name="reviewer",
            role="コードレビュアー",
            goal="実装されたコードの品質、セキュリティ、パフォーマンスを検証する",
            model="ministral-3:8b",
            backstory="コードレビューのベストプラクティスに詳しいQAエンジニア",
        ),
    ],
    "research_team": [
        AgentRole(
            name="researcher",
            role="リサーチャー",
            goal="指定されたテーマについて深く調査し、重要な知見をまとめる",
            model="gemma3:27b",
            backstory="技術調査と情報整理に優れたリサーチャー",
        ),
        AgentRole(
            name="analyst",
            role="アナリスト",
            goal="調査結果を分析し、実行可能な提案をまとめる",
            model="ministral-3:8b",
            backstory="データ分析と意思決定支援の専門家",
        ),
    ],
    "writing_team": [
        AgentRole(
            name="writer",
            role="テクニカルライター",
            goal="技術的な内容を分かりやすく正確に文書化する",
            model="gemma3:27b",
            backstory="技術文書とブログ記事の執筆経験が豊富",
        ),
        AgentRole(
            name="editor",
            role="エディター",
            goal="文書の品質を向上させ、読みやすく整える",
            model="ministral-3:8b",
            backstory="日本語の表現力と校正に優れた編集者",
        ),
    ],
}


# ── Sequential Crew実行 ──────────────────────────────


async def _ollama_chat(
    ollama_url: str,
    model: str,
    messages: list[dict[str, str]],
) -> str:
    """Ollama API で同期的にチャット（ストリーミングなし）"""
    async with httpx.AsyncClient(timeout=300.0) as client:
        resp = await client.post(
            f"{ollama_url}/api/chat",
            json={"model": model, "messages": messages, "stream": False},
        )
        resp.raise_for_status()
        return resp.json().get("message", {}).get("content", "")


async def run_crew(
    ollama_url: str,
    task_description: str,
    team_name: str = "dev_team",
    custom_agents: list[dict] | None = None,
    progress_callback: Optional[Callable] = None,
) -> dict:
    """CrewAI的なマルチエージェント実行（Ollamaローカル専用）

    VRAM圧迫を避けるため、同一モデルのエージェントを優先し、
    モデル切替を最小限にする Sequential 方式で実行する。

    Args:
        ollama_url: Ollama API URL
        task_description: タスクの説明
        team_name: プリセットチーム名（dev_team/research_team/writing_team）
        custom_agents: カスタムエージェント定義（省略時はプリセット使用）
        progress_callback: 進捗通知コールバック(step_info: dict)

    Returns:
        {ok, team, agents_used, steps, final_result, vram_summary, duration_ms}
    """
    start_time = time.monotonic()

    # エージェント定義
    if custom_agents:
        agents = [
            AgentRole(
                name=a.get("name", f"agent_{i}"),
                role=a.get("role", "アシスタント"),
                goal=a.get("goal", "タスクを遂行する"),
                model=a.get("model", "gemma3:27b"),
                backstory=a.get("backstory", ""),
            )
            for i, a in enumerate(custom_agents)
        ]
    else:
        agents = PRESET_TEAMS.get(team_name, PRESET_TEAMS["dev_team"])

    # VRAM見積もり
    unique_models = set(a.model for a in agents)
    total_vram_needed = sum(estimate_model_size(m) for m in unique_models)
    vram_status = await get_vram_status(ollama_url)

    if progress_callback:
        await _safe_callback(progress_callback, {
            "step": "init",
            "message": f"チーム「{team_name}」を起動中... "
                       f"(エージェント数: {len(agents)}, "
                       f"使用モデル: {len(unique_models)}, "
                       f"推定VRAM: {total_vram_needed:.0f}GB)",
            "vram": vram_status,
        })

    # Sequential実行（同一モデルのエージェントをグループ化してVRAM切替を最小化）
    model_groups: dict[str, list[AgentRole]] = {}
    for agent in agents:
        model_groups.setdefault(agent.model, []).append(agent)

    steps: list[dict] = []
    accumulated_context = f"## タスク\n{task_description}\n\n"

    for model_name, group_agents in model_groups.items():
        model_size = estimate_model_size(model_name)

        if progress_callback:
            await _safe_callback(progress_callback, {
                "step": "model_load",
                "message": f"モデル「{model_name}」をロード中... ({model_size:.0f}GB)",
                "model": model_name,
            })

        for agent in group_agents:
            agent_start = time.monotonic()

            system_prompt = (
                f"あなたは「{agent.role}」です。\n"
                f"目標: {agent.goal}\n"
            )
            if agent.backstory:
                system_prompt += f"背景: {agent.backstory}\n"
            system_prompt += (
                "\n前のエージェントの作業結果を踏まえて、あなたの役割を果たしてください。"
                "\n出力は日本語で、具体的かつ実用的な内容にしてください。"
            )

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": accumulated_context},
            ]

            if progress_callback:
                await _safe_callback(progress_callback, {
                    "step": "agent_start",
                    "agent": agent.name,
                    "role": agent.role,
                    "model": agent.model,
                    "message": f"「{agent.role}」({agent.name}) が作業中...",
                })

            try:
                result = await _ollama_chat(ollama_url, agent.model, messages)
                duration = time.monotonic() - agent_start

                step_info = {
                    "agent": agent.name,
                    "role": agent.role,
                    "model": agent.model,
                    "result": result,
                    "duration_sec": round(duration, 1),
                    "ok": True,
                }
                steps.append(step_info)

                # 次のエージェントへのコンテキスト累積
                accumulated_context += f"\n## {agent.role}（{agent.name}）の作業結果\n{result}\n\n"

                if progress_callback:
                    await _safe_callback(progress_callback, {
                        "step": "agent_done",
                        "agent": agent.name,
                        "role": agent.role,
                        "duration_sec": round(duration, 1),
                        "message": f"「{agent.role}」完了 ({duration:.1f}秒)",
                    })

            except Exception as e:
                logger.error("エージェント %s 実行エラー: %s", agent.name, e)
                steps.append({
                    "agent": agent.name,
                    "role": agent.role,
                    "model": agent.model,
                    "result": f"エラー: {e}",
                    "ok": False,
                })
                if progress_callback:
                    await _safe_callback(progress_callback, {
                        "step": "agent_error",
                        "agent": agent.name,
                        "message": f"「{agent.role}」エラー: {e}",
                    })

    total_duration = time.monotonic() - start_time
    final_vram = await get_vram_status(ollama_url)

    # 最終結果は最後のエージェントの出力
    final_result = steps[-1]["result"] if steps else ""

    return {
        "ok": all(s.get("ok", False) for s in steps),
        "team": team_name,
        "agents_used": len(agents),
        "models_used": list(unique_models),
        "estimated_vram_gb": round(total_vram_needed, 1),
        "steps": steps,
        "final_result": final_result,
        "vram_summary": final_vram,
        "duration_sec": round(total_duration, 1),
    }


def list_preset_teams() -> dict[str, list[dict]]:
    """プリセットチーム一覧を返す"""
    result = {}
    for team_name, agents in PRESET_TEAMS.items():
        result[team_name] = [
            {
                "name": a.name,
                "role": a.role,
                "goal": a.goal,
                "model": a.model,
                "estimated_vram_gb": estimate_model_size(a.model),
            }
            for a in agents
        ]
    return result


async def _safe_callback(callback: Callable, data: dict):
    """コールバックを安全に呼び出す"""
    try:
        result = callback(data)
        if asyncio.iscoroutine(result):
            await result
    except Exception as e:
        logger.debug("Progress callback error: %s", e)
