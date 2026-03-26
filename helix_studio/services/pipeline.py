"""3ステップパイプライン — Cloud計画 → Local実行(CrewAI対応) → Cloud検証

旧版Helix AI Studio MixAIの改良版。
- Step 1: Cloud AIが要件を分析し、構造化された実行計画を生成
- Step 2: ローカルLLMが計画を実行（単体 or CrewAIマルチエージェント）
- Step 3: Cloud AIが結果を検証し、品質評価と改善提案を出力
- 全ステップでMem0の関連記憶を自動注入
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable, Awaitable
from datetime import datetime, timezone
from typing import Any

from helix_studio.config import get_setting
from helix_studio.db import get_connection
from helix_studio.services import cloud_ai, local_ai, mem0

logger = logging.getLogger(__name__)

# ── プロンプトテンプレート（改良版）──

STEP1_PROMPT = """あなたは経験豊富なソフトウェアアーキテクト兼プロジェクトマネージャーです。
以下のタスクを分析し、構造化された実行計画を作成してください。

## タスク
{input_text}

{memory_context}

## 出力形式（必ずこの構造で出力）

### 1. タスク分析
- 目的: （何を達成するか）
- スコープ: （含まれる範囲と含まれない範囲）
- 前提条件: （必要な環境・知識）

### 2. 実行計画
各ステップを以下の形式で記述:
- **ステップN**: （タイトル）
  - 作業内容: （具体的にやること）
  - 期待出力: （何が出来上がるか）
  - 使用技術: （言語・ツール等）

### 3. リスクと対策
- リスク1 → 対策
- リスク2 → 対策

### 4. 成功基準
- （完了の判定条件を箇条書き）
"""

STEP2_PROMPT = """あなたは優秀なソフトウェアエンジニアです。
以下の計画に基づいて、各ステップを着実に実行してください。

## 元のタスク
{input_text}

## 実行計画（Step 1で作成済み）
{step1_result}

{memory_context}

## 指示
1. 計画の各ステップを順番に実行してください
2. 各ステップの実行結果を具体的に記述してください
3. コード、設定ファイル、文書などの成果物はそのまま含めてください
4. 問題が発生した場合は、問題点と代替案を記述してください
5. 最後に全体の実行サマリーをまとめてください
"""

STEP3_PROMPT = """あなたは品質管理の専門家です。
以下のタスク、計画、実行結果を総合的に検証してください。

## 元のタスク
{input_text}

## Step 1: 計画
{step1_result}

## Step 2: 実行結果
{step2_result}

{memory_context}

## 検証基準と出力形式

### 1. 品質評価
- **総合評価**: A（優秀）/ B（良好）/ C（要改善）/ D（不十分）
- **完成度**: 計画の何%が実行されたか

### 2. 計画との整合性
- 各ステップの計画 vs 実行結果の対比
- 未実行・不足項目のリスト

### 3. 品質チェック
- 正確性: 内容に誤りがないか
- 完全性: 要件を満たしているか
- 実用性: 実際に使える品質か

### 4. 改善提案
- 優先度高の改善点（3つ以内）
- 追加で検討すべき事項

### 5. 最終まとめ
- （3行以内で結論）
"""

ProgressCallback = Callable[[int, str, str], Awaitable[None]]


async def run_pipeline(
    run_id: str,
    input_text: str,
    step1_model: str = "",
    step2_model: str = "",
    step3_model: str = "",
    use_crew: bool = False,
    crew_team: str = "dev_team",
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    """3ステップパイプラインを実行し、結果をDBに保存。

    Args:
        use_crew: TrueならStep2をCrewAIマルチエージェントで実行
        crew_team: CrewAIのプリセットチーム名
    """

    # 設定からモデル読み込み
    if not step1_model:
        step1_model = await get_setting("pipeline_step1_model") or "claude-sonnet-4-20250514"
    if not step2_model:
        step2_model = await get_setting("pipeline_step2_model") or "gemma3:27b"
    if not step3_model:
        step3_model = await get_setting("pipeline_step3_model") or "claude-sonnet-4-20250514"

    # Mem0から関連記憶を取得
    memory_context = await _get_memory_context(input_text)

    db = await get_connection()
    try:
        await db.execute(
            """UPDATE pipeline_runs SET status='running', current_step=1,
               step1_model=?, step2_model=?, step3_model=?
               WHERE id=?""",
            (step1_model, step2_model if not use_crew else f"crew:{crew_team}", step3_model, run_id),
        )
        await db.commit()

        # ── Step 1: Cloud AI で計画 ──
        if progress_callback:
            await progress_callback(1, "running", "Step1: 計画を作成中...")

        step1_result = await _run_cloud_step(
            step1_model,
            STEP1_PROMPT.format(input_text=input_text, memory_context=memory_context),
        )
        await db.execute(
            "UPDATE pipeline_runs SET step1_result=?, current_step=2 WHERE id=?",
            (step1_result, run_id),
        )
        await db.commit()

        # ── Step 2: Local LLM で実行 ──
        if use_crew:
            # CrewAIマルチエージェントモード
            if progress_callback:
                await progress_callback(2, "running", f"Step2: CrewAI ({crew_team}) で実行中...")

            from helix_studio.services import crew_ai
            ollama_url = await get_setting("ollama_url") or "http://localhost:11434"
            crew_result = await crew_ai.run_crew(
                ollama_url=ollama_url,
                task_description=f"{input_text}\n\n## 実行計画\n{step1_result}",
                team_name=crew_team,
            )
            step2_result = crew_result.get("final_result", "")
            # エージェント別の結果も保存
            if crew_result.get("steps"):
                import json
                step2_result += "\n\n---\n## エージェント別結果\n"
                for s in crew_result["steps"]:
                    step2_result += f"\n### {s['role']} ({s['agent']})\n{s['result']}\n"
        else:
            # 単体ローカルLLMモード
            if progress_callback:
                await progress_callback(2, "running", "Step2: ローカルLLMで実行中...")

            step2_result = await _run_local_step(
                step2_model,
                STEP2_PROMPT.format(
                    input_text=input_text,
                    step1_result=step1_result,
                    memory_context=memory_context,
                ),
            )

        await db.execute(
            "UPDATE pipeline_runs SET step2_result=?, current_step=3 WHERE id=?",
            (step2_result, run_id),
        )
        await db.commit()

        # ── Step 3: Cloud AI で検証 ──
        if progress_callback:
            await progress_callback(3, "running", "Step3: 品質検証中...")

        step3_result = await _run_cloud_step(
            step3_model,
            STEP3_PROMPT.format(
                input_text=input_text,
                step1_result=step1_result,
                step2_result=step2_result,
                memory_context=memory_context,
            ),
        )
        now = datetime.now(timezone.utc).isoformat()
        await db.execute(
            """UPDATE pipeline_runs SET step3_result=?, current_step=3,
               status='completed', completed_at=? WHERE id=?""",
            (step3_result, now, run_id),
        )
        await db.commit()

        if progress_callback:
            await progress_callback(3, "completed", "パイプライン完了")

        return {
            "id": run_id,
            "status": "completed",
            "step1_result": step1_result,
            "step2_result": step2_result,
            "step3_result": step3_result,
        }

    except Exception as e:
        logger.exception("パイプライン実行エラー: %s", e)
        await db.execute(
            "UPDATE pipeline_runs SET status='failed', error_msg=? WHERE id=?",
            (str(e), run_id),
        )
        await db.commit()
        if progress_callback:
            await progress_callback(0, "failed", f"エラー: {e}")
        return {"id": run_id, "status": "failed", "error_msg": str(e)}
    finally:
        await db.close()


async def _get_memory_context(query: str) -> str:
    """Mem0から関連記憶を取得してコンテキスト文字列を生成"""
    try:
        mem0_url = await get_setting("mem0_url") or "http://localhost:8080"
        user_id = await get_setting("mem0_user_id") or "tsunamayo7"
        auto_inject = await get_setting("mem0_auto_inject")
        if auto_inject != "true":
            return ""

        memories = await mem0.search(mem0_url, user_id, query, limit=5)
        if not memories:
            return ""

        lines = ["## 参考: 過去の記憶（Mem0）"]
        for m in memories:
            text = m.get("memory", m.get("text", str(m)))
            lines.append(f"- {text}")
        return "\n".join(lines)
    except Exception:
        return ""


async def _run_cloud_step(model: str, prompt: str) -> str:
    """AIにプロンプトを送信して応答を取得。Cloud/Ollamaを自動判定。"""
    # モデル名からプロバイダを判定
    if model.startswith("claude"):
        provider = "claude"
        api_key = await get_setting("claude_api_key") or ""
    elif model.startswith(("gpt-", "o1", "o3", "o4")):
        provider = "openai"
        api_key = await get_setting("openai_api_key") or ""
    else:
        # Cloud APIキーがなければOllamaにフォールバック
        provider = "claude"
        api_key = await get_setting("claude_api_key") or ""

    # Cloud APIキーがない場合、Ollamaで実行
    if not api_key:
        logger.info("Cloud APIキー未設定、Ollamaで実行: %s", model)
        return await _run_local_step(model, prompt)

    messages = [{"role": "user", "content": prompt}]
    return await cloud_ai.chat_once(provider, api_key, model, messages)


async def _run_local_step(model: str, prompt: str) -> str:
    """ローカルLLMにプロンプトを送信して応答を取得。"""
    ollama_url = await get_setting("ollama_url") or "http://localhost:11434"
    messages = [{"role": "user", "content": prompt}]
    chunks: list[str] = []
    async for chunk in local_ai.stream_ollama_chat(ollama_url, model, messages):
        chunks.append(chunk)
    return "".join(chunks)


async def create_pipeline_run(title: str, input_text: str) -> str:
    """パイプライン実行レコードをDBに作成し、IDを返す。"""
    run_id = str(uuid.uuid4())
    db = await get_connection()
    try:
        await db.execute(
            "INSERT INTO pipeline_runs (id, title, input_text) VALUES (?, ?, ?)",
            (run_id, title, input_text),
        )
        await db.commit()
        return run_id
    finally:
        await db.close()
