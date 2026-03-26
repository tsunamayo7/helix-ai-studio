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
from helix_studio.services import cloud_ai, local_ai, cli_ai, mem0

logger = logging.getLogger(__name__)

# ── プロンプトテンプレート（改良版）──

STEP1_PROMPT = """You are an experienced software architect and project manager.
You MUST respond in the same language as the task description below.
Analyze the following task and create a structured execution plan.

## Task
{input_text}

{memory_context}

## Output Format (must follow this structure)

### 1. Task Analysis
- Objective: (what to achieve)
- Scope: (what is included and excluded)
- Prerequisites: (required environment and knowledge)

### 2. Execution Plan
Describe each step in the following format:
- **Step N**: (title)
  - Work: (specific actions to take)
  - Expected Output: (deliverables)
  - Technology: (languages, tools, etc.)

### 3. Risks and Mitigations
- Risk 1 → Mitigation
- Risk 2 → Mitigation

### 4. Success Criteria
- (bullet list of completion conditions)
"""

STEP2_PROMPT = """You are a skilled software engineer.
You MUST respond in the same language as the task description below.
Execute each step of the plan below thoroughly.

## Original Task
{input_text}

## Execution Plan (created in Step 1)
{step1_result}

{memory_context}

## Instructions
1. Execute each step of the plan in order
2. Describe the results of each step concretely
3. Include all deliverables such as code, configuration files, and documents as-is
4. If issues arise, describe the problem and alternative solutions
5. Provide an overall execution summary at the end
"""

STEP3_PROMPT = """You are a technical writer who creates polished, actionable final deliverables.
You MUST respond in the same language as the task description below.

Based on the plan and execution results below, create a final answer that the user can directly use.

## Original Task
{input_text}

## Step 1: Plan
{step1_result}

## Step 2: Execution Results
{step2_result}

{memory_context}

## Instructions
1. Synthesize the plan and execution results into a single, coherent final deliverable
2. If code was requested, include the final polished code with comments
3. If a document was requested, include the final document
4. Remove all meta-commentary (planning notes, intermediate steps)
5. The output should be something the user can copy-paste and use immediately
6. Add a brief quality assessment at the end (1-2 lines)
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
            await progress_callback(1, "running", "Step1: Creating plan...")

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
                await progress_callback(2, "running", f"Step2: Executing with CrewAI ({crew_team})...")

            from helix_studio.services import crew_ai
            ollama_url = await get_setting("ollama_url") or "http://localhost:11434"
            crew_result = await crew_ai.run_crew(
                ollama_url=ollama_url,
                task_description=f"{input_text}\n\n## Execution Plan\n{step1_result}",
                team_name=crew_team,
            )
            step2_result = crew_result.get("final_result", "")
            # エージェント別の結果も保存
            if crew_result.get("steps"):
                import json
                step2_result += "\n\n---\n## Results by Agent\n"
                for s in crew_result["steps"]:
                    step2_result += f"\n### {s['role']} ({s['agent']})\n{s['result']}\n"
        else:
            # 単体ローカルLLMモード
            if progress_callback:
                await progress_callback(2, "running", "Step2: Executing with local LLM...")

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

        # ── Step 3: Final Answer (Cloud/CLI/Ollama) ──
        if progress_callback:
            await progress_callback(3, "running", "Step3: Generating final answer...")

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
            await progress_callback(3, "completed", "Pipeline completed")

        return {
            "id": run_id,
            "status": "completed",
            "step1_result": step1_result,
            "step2_result": step2_result,
            "step3_result": step3_result,
        }

    except Exception as e:
        logger.exception("Pipeline execution error: %s", e)
        await db.execute(
            "UPDATE pipeline_runs SET status='failed', error_msg=? WHERE id=?",
            (str(e), run_id),
        )
        await db.commit()
        if progress_callback:
            await progress_callback(0, "failed", f"Error: {e}")
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

        lines = ["## Reference: Past Memories (Mem0)"]
        for m in memories:
            text = m.get("memory", m.get("text", str(m)))
            lines.append(f"- {text}")
        return "\n".join(lines)
    except Exception:
        return ""


_CLI_PROVIDERS = {"claude_code", "codex", "gemini_cli"}
_CLI_MODEL_MAP = {
    "opus": "claude_code", "sonnet": "claude_code", "haiku": "claude_code",
    "gpt-5": "codex", "gpt-4": "codex",
    "gemini": "gemini_cli",
}


def _detect_provider(model: str) -> str:
    """モデル名からプロバイダを自動判定。"""
    m = model.lower()
    for prefix, provider in _CLI_MODEL_MAP.items():
        if m.startswith(prefix):
            return provider
    if m.startswith("claude"):
        return "claude"
    if m.startswith(("gpt-", "o1", "o3", "o4")):
        return "openai"
    return "ollama"


async def _run_cloud_step(model: str, prompt: str) -> str:
    """AIにプロンプトを送信して応答を取得。CLI/Cloud/Ollamaを自動判定。"""
    provider = _detect_provider(model)

    # CLI (Claude Code / Codex / Gemini CLI)
    if provider in _CLI_PROVIDERS:
        logger.info("CLI execution: provider=%s model=%s", provider, model)
        chunks: list[str] = []
        async for chunk in cli_ai.stream_chat_cli(provider, model, prompt):
            chunks.append(chunk)
        return "".join(chunks)

    # Cloud API
    if provider in ("claude", "openai"):
        api_key_map = {"claude": "claude_api_key", "openai": "openai_api_key"}
        api_key = await get_setting(api_key_map[provider]) or ""
        if api_key:
            messages = [{"role": "user", "content": prompt}]
            return await cloud_ai.chat_once(provider, api_key, model, messages)

    # Ollamaフォールバック
    logger.info("Executing with Ollama: %s", model)
    return await _run_local_step(model, prompt)


async def _run_local_step(model: str, prompt: str) -> str:
    """ローカルLLMにプロンプトを送信して応答を取得。"""
    ollama_url = await get_setting("ollama_url") or "http://localhost:11434"
    # Strip provider prefix (e.g. "ollama/gemma3:4b" -> "gemma3:4b")
    if "/" in model:
        model = model.split("/", 1)[1]
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
