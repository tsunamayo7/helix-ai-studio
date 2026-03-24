"""CrewAI マルチエージェント API ルーター"""

from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from helix_studio.config import get_setting
from helix_studio.db import get_connection
from helix_studio.services import crew_ai

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/crew", tags=["crew"])


@router.get("/teams")
async def list_teams() -> dict:
    """プリセットチーム一覧"""
    return {"teams": crew_ai.list_preset_teams()}


@router.get("/vram")
async def vram_status() -> dict:
    """VRAM使用状況（GPU自動検出 + ユーザー設定反映）"""
    ollama_url = await get_setting("ollama_url") or "http://localhost:11434"
    status = await crew_ai.get_vram_status(ollama_url)
    # VRAM合計を設定から取得
    total = await crew_ai.get_effective_vram_total()
    status["total_vram_gb"] = total
    status["gpu_config"] = await get_setting("gpu_config") or "auto"
    return status


@router.post("/run")
async def run_crew_task(req: dict) -> dict:
    """CrewAIタスク実行（非ストリーミング）"""
    ollama_url = await get_setting("ollama_url") or "http://localhost:11434"

    task = req.get("task", "")
    team = req.get("team", "dev_team")
    custom_agents = req.get("custom_agents")

    if not task:
        return {"ok": False, "error": "タスクが空です"}

    result = await crew_ai.run_crew(
        ollama_url=ollama_url,
        task_description=task,
        team_name=team,
        custom_agents=custom_agents,
    )

    # DB保存
    run_id = str(uuid.uuid4())
    db = await get_connection()
    try:
        await db.execute(
            "INSERT INTO pipeline_runs (id, title, status, input_text, "
            "step1_result, step2_result, step3_result, "
            "step1_model, current_step, completed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))",
            (
                run_id,
                f"CrewAI: {team}",
                "completed" if result["ok"] else "failed",
                task,
                json.dumps(result["steps"], ensure_ascii=False),
                result["final_result"],
                json.dumps(result["vram_summary"], ensure_ascii=False),
                ",".join(result["models_used"]),
                result["agents_used"],
            ),
        )
        await db.commit()
    finally:
        await db.close()

    result["run_id"] = run_id
    return result


@router.websocket("/ws/crew")
async def ws_crew(ws: WebSocket):
    """CrewAIタスク実行（WebSocketストリーミング進捗）"""
    await ws.accept()
    try:
        raw = await ws.receive_text()
        data = json.loads(raw)

        ollama_url = await get_setting("ollama_url") or "http://localhost:11434"
        task = data.get("task", "")
        team = data.get("team", "dev_team")
        custom_agents = data.get("custom_agents")

        if not task:
            await ws.send_text(json.dumps({"type": "error", "message": "タスクが空です"}))
            return

        async def progress_cb(info: dict):
            await ws.send_text(json.dumps({"type": "progress", **info}, ensure_ascii=False))

        result = await crew_ai.run_crew(
            ollama_url=ollama_url,
            task_description=task,
            team_name=team,
            custom_agents=custom_agents,
            progress_callback=progress_cb,
        )

        await ws.send_text(json.dumps({
            "type": "done",
            "result": result,
        }, ensure_ascii=False))

    except WebSocketDisconnect:
        logger.info("CrewAI WebSocket切断")
    except Exception as e:
        logger.exception("CrewAI WebSocketエラー: %s", e)
        try:
            await ws.send_text(json.dumps({"type": "error", "message": str(e)}))
        except Exception:
            pass
