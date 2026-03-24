"""Mem0 HTTP API クライアント"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)


async def search(
    url: str,
    user_id: str,
    query: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """POST /search で記憶を検索。エラー時は空リスト。"""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{url.rstrip('/')}/search",
                json={"query": query, "user_id": user_id, "limit": limit},
            )
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else data.get("results", [])
    except Exception as e:
        logger.warning("Mem0検索に失敗: %s", e)
        return []


async def add(url: str, user_id: str, text: str) -> dict[str, Any] | None:
    """POST /add で記憶を追加。エラー時は None。"""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{url.rstrip('/')}/add",
                json={"text": text, "user_id": user_id},
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.warning("Mem0記憶の追加に失敗: %s", e)
        return None


async def get_all(url: str, user_id: str) -> list[dict[str, Any]]:
    """GET /memories?user_id= で全記憶を取得。エラー時は空リスト。"""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{url.rstrip('/')}/memories",
                params={"user_id": user_id},
            )
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else data.get("results", [])
    except Exception as e:
        logger.warning("Mem0全記憶の取得に失敗: %s", e)
        return []


async def health(url: str) -> bool:
    """GET /health でMem0の稼働状態を確認。"""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            resp = await client.get(f"{url.rstrip('/')}/health")
            return resp.status_code == 200
    except Exception:
        return False


async def get_status(url: str, user_id: str) -> dict[str, Any]:
    """Mem0のステータス情報を返す。"""
    available = await health(url)
    memory_count = 0
    error = None
    if available:
        try:
            memories = await get_all(url, user_id)
            memory_count = len(memories)
        except Exception as e:
            error = str(e)
    else:
        error = "Mem0サーバーに接続できません"
    return {
        "available": available,
        "memory_count": memory_count,
        "error": error,
    }
