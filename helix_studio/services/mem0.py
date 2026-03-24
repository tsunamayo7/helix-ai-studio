"""Mem0 クライアント — HTTP API + Qdrant直接検索フォールバック"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)

# Qdrant直接検索の設定
QDRANT_URL = "http://localhost:6333"
QDRANT_COLLECTION = "mem0_shared"
OLLAMA_URL = "http://localhost:11434"
EMBEDDING_MODEL = "qwen3-embedding:8b"


async def _embed(text: str) -> list[float] | None:
    """Ollama埋め込みモデルでテキストをベクトル化"""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{OLLAMA_URL}/api/embed",
                json={"model": EMBEDDING_MODEL, "input": text},
            )
            resp.raise_for_status()
            data = resp.json()
            embeddings = data.get("embeddings", [[]])
            return embeddings[0] if embeddings and embeddings[0] else None
    except Exception as e:
        logger.debug("埋め込み生成失敗: %s", e)
        return None


async def _qdrant_search(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Qdrantに直接ベクトル検索（Mem0 HTTPが空を返す場合のフォールバック）"""
    vector = await _embed(query)
    if not vector:
        return []

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{QDRANT_URL}/collections/{QDRANT_COLLECTION}/points/search",
                json={"vector": vector, "limit": limit, "with_payload": True},
            )
            resp.raise_for_status()
            data = resp.json()
            results = []
            for point in data.get("result", []):
                payload = point.get("payload", {})
                memory_text = payload.get("data", payload.get("memory", ""))
                if memory_text and point.get("score", 0) > 0.3:
                    results.append({
                        "memory": memory_text,
                        "score": point.get("score", 0),
                    })
            return results
    except Exception as e:
        logger.debug("Qdrant直接検索失敗: %s", e)
        return []


async def search(
    url: str,
    user_id: str,
    query: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """記憶検索。Mem0 HTTP API → Qdrant直接検索のフォールバック。"""
    # 1. Mem0 HTTP API
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{url.rstrip('/')}/search",
                json={"query": query, "user_id": user_id, "limit": limit},
            )
            resp.raise_for_status()
            data = resp.json()
            results = data if isinstance(data, list) else data.get("results", [])
            if results:
                return results
    except Exception as e:
        logger.debug("Mem0 HTTP検索失敗: %s", e)

    # 2. フォールバック: Qdrant直接検索
    logger.info("Mem0 HTTP検索が空 → Qdrant直接検索にフォールバック")
    return await _qdrant_search(query, limit=limit)


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
