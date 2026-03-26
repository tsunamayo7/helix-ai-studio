"""Mem0 メモリ API ルーター"""

from __future__ import annotations

from fastapi import APIRouter

from helix_studio.config import get_setting
from helix_studio.models import MemoryAddRequest, MemorySearchRequest, MemoryStatusResponse
from helix_studio.services import mem0

router = APIRouter(prefix="/api/memory", tags=["memory"])


@router.post("/search")
async def search_memory(req: MemorySearchRequest) -> dict:
    """Mem0で記憶を検索。"""
    url = await get_setting("mem0_url") or "http://localhost:8080"
    user_id = req.user_id or await get_setting("mem0_user_id") or "tsunamayo7"
    results = await mem0.search(url, user_id, req.query, limit=req.limit)
    return {"results": results, "count": len(results)}


@router.post("/add")
async def add_memory(req: MemoryAddRequest) -> dict:
    """Mem0に記憶を追加。"""
    url = await get_setting("mem0_url") or "http://localhost:8080"
    user_id = req.user_id or await get_setting("mem0_user_id") or "tsunamayo7"
    result = await mem0.add(url, user_id, req.text)
    if result is None:
        return {"success": False, "message": "Failed to add memory to Mem0. Please check if the server is running."}
    return {"success": True, "result": result}


@router.get("/status")
async def memory_status() -> MemoryStatusResponse:
    """Mem0のステータスを返す。"""
    url = await get_setting("mem0_url") or "http://localhost:8080"
    user_id = await get_setting("mem0_user_id") or "tsunamayo7"
    status = await mem0.get_status(url, user_id)
    return MemoryStatusResponse(**status)
