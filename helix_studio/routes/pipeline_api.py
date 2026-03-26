"""パイプライン API ルーター"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException

from helix_studio.db import get_connection
from helix_studio.models import PipelineRequest, PipelineStatus
from helix_studio.services.pipeline import create_pipeline_run, run_pipeline

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


@router.post("/start")
async def start_pipeline(req: PipelineRequest) -> dict:
    """パイプラインを開始（バックグラウンド実行）。"""
    run_id = await create_pipeline_run(req.title, req.input_text)

    # バックグラウンドで実行
    asyncio.create_task(
        run_pipeline(
            run_id=run_id,
            input_text=req.input_text,
            step1_model=req.step1_model,
            step2_model=req.step2_model,
            step3_model=req.step3_model,
        )
    )

    return {"id": run_id, "status": "pending", "message": "Pipeline started"}


@router.get("/{run_id}")
async def get_pipeline_status(run_id: str) -> PipelineStatus:
    """パイプラインの実行状況を取得。"""
    db = await get_connection()
    try:
        cursor = await db.execute(
            "SELECT * FROM pipeline_runs WHERE id = ?", (run_id,)
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Pipeline not found")
        return PipelineStatus(**dict(row))
    finally:
        await db.close()


@router.get("/history/list")
async def pipeline_history() -> list[dict]:
    """パイプライン実行履歴を取得。"""
    db = await get_connection()
    try:
        cursor = await db.execute(
            "SELECT id, title, status, current_step, created_at, completed_at "
            "FROM pipeline_runs ORDER BY created_at DESC LIMIT 50"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()
