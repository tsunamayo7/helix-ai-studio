"""Helix AI Studio — CrewAI Phase 2 エンジン v12.2.0

phase2_engine 設定で選択された場合に使用される Phase 2 実行エンジン。
既存の model_assignments（UIのカテゴリ別モデル選択）をそのまま活かす。

実行モード:
  crewai_sequential   — CrewAI Process.sequential
                        各エージェントが順番に実行し、前段の出力を次に引き継ぐ
  crewai_hierarchical — CrewAI Process.hierarchical
                        P1/P3 エンジン（Claude/GPT/Gemini/Ollama）が監督者として
                        各エージェントにタスクを委任・レビューし対話的に進める

エージェント構成（実行順）:
  1. Thinker   (thinking / reasoning): 前提・論点・リスク・作戦を整理
  2. Researcher (research):             情報収集・根拠・不確実性を整理
  3. Vision    (vision):               画像/スクショ読解（タスクがある場合のみ）
  4. Coder     (coding):               実装方針・差分・手順・注意点
  5. Translator (translation):          最終出力の日本語整形

各エージェントの LLM は UI の model_assignments を引き継ぐ:
  - Ollama ローカルモデル → ollama/<model>
  - Anthropic Claude API  → anthropic/<model>
  - OpenAI GPT API        → <model>
  - Google Gemini API     → gemini/<model>
"""

import io
import json
import logging
import sys
import time
from typing import Callable, List, Optional

from .sequential_executor import SequentialResult, SequentialTask

logger = logging.getLogger(__name__)

# CrewAI はオプション依存（なくても graceful degradation）
# pythonw.exe では sys.stdout/stderr が None のため CrewAI インポート時にクラッシュする
# インポート前後で一時的に StringIO に差し替えて回避する
_import_orig_stdout = sys.stdout
_import_orig_stderr = sys.stderr
if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()
try:
    from crewai import Agent, Crew, LLM, Process, Task

    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False
    logger.info(
        "[CrewAIEngine] crewai パッケージ未インストール — "
        "pip install 'crewai[tools]' でインストールしてください"
    )
finally:
    sys.stdout = _import_orig_stdout
    sys.stderr = _import_orig_stderr


# ─── エージェント定義（固定） ───────────────────────────────────────

_AGENT_SPECS: dict[str, dict] = {
    "thinking": {
        "role": "Thinker",
        "goal": "要求の前提・論点・リスク・作戦を簡潔に整理し、後続エージェントが動ける形で出力する",
        "backstory": (
            "批判的思考と論理構造化の専門家。"
            "要求の本質を抽出し、リスクと対策を明示する。"
            "出力は箇条書きで簡潔にまとめ、次の調査・実装工程のインプットとなる。"
        ),
    },
    "research": {
        "role": "Researcher",
        "goal": "必要情報の調査結果と根拠、不確実性を整理して提供する",
        "backstory": (
            "情報収集と根拠評価の専門家。"
            "信頼性の高い情報と不確実性を明確に区別して整理する。"
            "Thinker の分析を踏まえて調査範囲を決定する。"
        ),
    },
    "vision": {
        "role": "Vision Analyst",
        "goal": "画像・スクリーンショットの視覚情報を正確に読解・解析する",
        "backstory": (
            "視覚情報解析の専門家。"
            "画像から必要な情報を抽出し、テキストで明確に説明する。"
            "UI/UX や図表の解釈も得意とする。"
        ),
    },
    "coding": {
        "role": "Coder",
        "goal": "実装方針・差分・手順・注意点を具体的に作成する",
        "backstory": (
            "ソフトウェア実装の専門家。"
            "コード品質、保守性、パフォーマンスを考慮した実装方針を提供する。"
            "Researcher と Vision の調査結果を活用して実装計画を策定する。"
        ),
    },
    "translation": {
        "role": "Translator",
        "goal": "最終出力を日本語に整形し、必要に応じて英日翻訳を行う",
        "backstory": (
            "技術文書翻訳の専門家。"
            "技術的正確性を保ちながら、自然な日本語に整形する。"
            "前工程の全成果物を統合して最終レポートを作成する。"
        ),
    },
}

# reasoning は thinking のエイリアス（後方互換）
_AGENT_SPECS["reasoning"] = _AGENT_SPECS["thinking"]

# 実行順序（カテゴリ名）
_EXECUTION_ORDER = ["thinking", "reasoning", "research", "vision", "coding", "translation"]


# ─── LLM ファクトリ ─────────────────────────────────────────────────

def _make_crewai_llm(model: str) -> "LLM":
    """モデル名から CrewAI LLM インスタンスを生成する。

    cloud_models.json の provider フィールドを参照して適切なプロバイダーを選択する。
    未登録モデルは Ollama ローカルモデルとして扱う。
    """
    if not CREWAI_AVAILABLE:
        raise RuntimeError("crewai not installed")

    try:
        from .sequential_executor import _get_cloud_provider_for_model
        provider = _get_cloud_provider_for_model(model)
    except Exception:
        provider = None

    if provider == "anthropic_api":
        return LLM(model=f"anthropic/{model}")
    elif provider == "openai_api":
        return LLM(model=model)  # OpenAI はプレフィックス不要
    elif provider == "google_api":
        return LLM(model=f"gemini/{model}")
    else:
        # Ollama ローカルモデル（デフォルト）
        return LLM(model=f"ollama/{model}", base_url="http://localhost:11434")


# ─── CrewAI Phase 2 エンジン ────────────────────────────────────────

class CrewAIPhaseTwoEngine:
    """CrewAI を使った Phase 2 実行エンジン v12.2.0

    5 体のエージェント（Thinker/Researcher/Vision/Coder/Translator）を
    sequential または hierarchical で実行する。
    各エージェントの LLM は既存の model_assignments を引き継ぐ。
    hierarchical モードでは P1/P3 エンジンが監督者として参加する。
    """

    def execute(
        self,
        tasks: List[SequentialTask],
        on_start: Optional[Callable[[str, str], None]] = None,
        on_finish: Optional[Callable[[str, bool, float], None]] = None,
        on_progress: Optional[Callable[[int, int], None]] = None,
        manager_llm_model: Optional[str] = None,
    ) -> List[SequentialResult]:
        """CrewAI で Phase 2 タスクを実行する。

        Args:
            tasks:             SequentialTask リスト（Phase 1 から構築済み）
            on_start:          タスク開始コールバック (category, model)
            on_finish:         タスク完了コールバック (category, success, elapsed)
            on_progress:       進捗コールバック (completed, total)
            manager_llm_model: P1/P3 エンジンのモデルID。指定時は
                               Process.hierarchical で監督者として参加する。
                               None の場合は Process.sequential を使用。

        Returns:
            SequentialResult リスト（カテゴリ別実行結果、P3 と互換）
        """
        if not CREWAI_AVAILABLE:
            logger.error("[CrewAIEngine] crewai 未インストール — sequential フォールバックを使用してください")
            return self._error_results(tasks, "crewai not installed")

        # カテゴリ→SequentialTask マップ（reasoning を thinking にエイリアス）
        task_map: dict[str, SequentialTask] = {}
        for t in tasks:
            cat = "thinking" if t.category == "reasoning" else t.category
            task_map[cat] = t

        # 実行順に並べたカテゴリリスト（タスクが存在するもののみ）
        ordered = [cat for cat in _EXECUTION_ORDER if cat in task_map]
        if not ordered:
            return []

        total = len(ordered)
        logger.info(f"[CrewAIEngine] Phase 2 開始: {ordered} ({total} エージェント)")

        # ── CrewAI Agent / Task を構築 ──
        agents: list = []
        crew_tasks: list = []

        for cat in ordered:
            seq_task = task_map[cat]
            spec = _AGENT_SPECS.get(cat, {
                "role": cat.capitalize(),
                "goal": seq_task.prompt[:200],
                "backstory": f"{cat} 専門エージェント",
            })

            try:
                llm = _make_crewai_llm(seq_task.model)
            except Exception as e:
                logger.warning(
                    f"[CrewAIEngine] LLM 初期化失敗 ({cat}/{seq_task.model}): {e} "
                    f"— Ollama フォールバック使用"
                )
                llm = LLM(model=f"ollama/{seq_task.model}", base_url="http://localhost:11434")

            agent = Agent(
                role=spec["role"],
                goal=spec["goal"],
                backstory=spec["backstory"],
                llm=llm,
                verbose=False,
                allow_delegation=False,
            )
            agents.append(agent)

            crew_task = Task(
                description=seq_task.prompt,
                expected_output=(
                    seq_task.expected_output
                    or f"{spec['role']}として、担当領域の詳細な分析と提言を出力する"
                ),
                agent=agent,
            )
            crew_tasks.append(crew_task)

        # ── タイミング・コールバック管理 ──
        task_timings: dict[int, float] = {}
        completed_idx = [0]  # リスト経由でクロージャから変更可能にする

        def _task_callback(task_output) -> None:
            """各タスク完了時に呼ばれる（CrewAI task_callback）"""
            idx = completed_idx[0]
            completed_idx[0] += 1
            if idx < len(ordered):
                cat = ordered[idx]
                seq_task = task_map[cat]
                elapsed = time.time() - task_timings.get(idx, time.time())
                logger.info(
                    f"[CrewAIEngine] {spec['role']} 完了 "
                    f"({seq_task.category}, {elapsed:.1f}s)"
                )
                if on_finish:
                    on_finish(seq_task.category, True, elapsed)
                if on_progress:
                    on_progress(completed_idx[0], total)

        def _step_callback(step_output) -> None:
            """各エージェントのステップ開始時に呼ばれる（CrewAI step_callback）"""
            idx = completed_idx[0]
            if idx not in task_timings:
                task_timings[idx] = time.time()
                if idx < len(ordered):
                    cat = ordered[idx]
                    seq_task = task_map[cat]
                    logger.info(
                        f"[CrewAIEngine] {cat} 開始 ({seq_task.model})"
                    )
                    if on_start:
                        on_start(seq_task.category, seq_task.model)

        # ── Crew 組成・実行 ──
        use_hierarchical = bool(manager_llm_model)

        if use_hierarchical:
            # hierarchical モード: P1/P3 エンジンが監督者として参加
            try:
                manager_llm = _make_crewai_llm(manager_llm_model)
                logger.info(
                    f"[CrewAIEngine] hierarchical モード: 監督者 = {manager_llm_model}"
                )
            except Exception as e:
                logger.warning(
                    f"[CrewAIEngine] 監督者 LLM 初期化失敗 ({manager_llm_model}): {e} "
                    f"— sequential にフォールバック"
                )
                use_hierarchical = False
                manager_llm = None

        if use_hierarchical:
            crew = Crew(
                agents=agents,
                tasks=crew_tasks,
                process=Process.hierarchical,
                manager_llm=manager_llm,
                verbose=False,
                task_callback=_task_callback,
                step_callback=_step_callback,
            )
        else:
            crew = Crew(
                agents=agents,
                tasks=crew_tasks,
                process=Process.sequential,
                verbose=False,
                task_callback=_task_callback,
                step_callback=_step_callback,
            )

        start_all = time.time()
        # pythonw.exe では sys.stdout/stderr が None のため CrewAI がクラッシュする
        # kickoff() 前後で一時的に StringIO に差し替えて回避する
        _orig_stdout = sys.stdout
        _orig_stderr = sys.stderr
        if sys.stdout is None:
            sys.stdout = io.StringIO()
        if sys.stderr is None:
            sys.stderr = io.StringIO()
        try:
            crew.kickoff()
        except Exception as e:
            logger.error(f"[CrewAIEngine] Crew.kickoff() 失敗: {e}")
            return self._error_results(tasks, str(e))
        finally:
            sys.stdout = _orig_stdout
            sys.stderr = _orig_stderr

        total_elapsed = time.time() - start_all
        logger.info(f"[CrewAIEngine] Phase 2 完了 ({total_elapsed:.1f}s)")

        # ── SequentialResult 変換 ──
        results: list[SequentialResult] = []
        for idx, (cat, crew_task) in enumerate(zip(ordered, crew_tasks)):
            seq_task = task_map[cat]

            # タスクの出力テキストを取得（CrewAI バージョン差異に対応）
            output_text = ""
            try:
                if hasattr(crew_task, "output") and crew_task.output is not None:
                    if hasattr(crew_task.output, "raw"):
                        output_text = crew_task.output.raw or ""
                    else:
                        output_text = str(crew_task.output)
            except Exception as e:
                logger.debug(f"[CrewAIEngine] output 取得エラー ({cat}): {e}")

            success = bool(output_text.strip())
            elapsed_approx = total_elapsed / max(len(ordered), 1)

            normalized = json.dumps(
                {
                    "category": seq_task.category,
                    "model_used": f"crewai/{seq_task.model}",
                    "output": output_text,
                    "confidence": 0.85 if success else 0.0,
                    "notes": "CrewAI sequential execution",
                },
                ensure_ascii=False,
            )

            results.append(
                SequentialResult(
                    category=seq_task.category,  # 元のカテゴリ名を保持（P3 互換）
                    model=seq_task.model,
                    success=success,
                    response=normalized,
                    elapsed=elapsed_approx,
                    order=seq_task.order,
                    original_prompt=seq_task.prompt,
                    expected_output=seq_task.expected_output,
                )
            )

        return results

    # ─── ヘルパー ──────────────────────────────────────────────────

    def _error_results(
        self, tasks: List[SequentialTask], error: str
    ) -> List[SequentialResult]:
        """エラー時のフォールバック結果生成（P3 への影響を最小化）"""
        return [
            SequentialResult(
                category=t.category,
                model=t.model,
                success=False,
                response=json.dumps(
                    {
                        "category": t.category,
                        "model_used": t.model,
                        "output": f"CrewAI エンジンエラー: {error}",
                        "confidence": 0.0,
                        "notes": "engine_error",
                    },
                    ensure_ascii=False,
                ),
                elapsed=0.0,
                order=t.order,
                original_prompt=t.prompt,
                expected_output=t.expected_output,
            )
            for t in tasks
        ]
