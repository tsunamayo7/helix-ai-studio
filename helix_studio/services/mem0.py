"""共有記憶クライアント — Qdrant直接検索 + HTTP APIフォールバック"""

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
        logger.debug("Embedding generation failed: %s", e)
        return None


async def _qdrant_search(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Qdrantに直接ベクトル検索"""
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
        logger.debug("Qdrant direct search failed: %s", e)
        return []


async def search(
    url: str,
    user_id: str,
    query: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """記憶検索。Qdrant直接検索 → HTTP APIフォールバック。"""
    # 1. Qdrant直接検索（メイン）
    results = await _qdrant_search(query, limit=limit)
    if results:
        return results

    # 2. フォールバック: HTTP API
    logger.info("Qdrant direct search returned empty -> falling back to HTTP API")
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{url.rstrip('/')}/search",
                json={"query": query, "limit": limit},
            )
            resp.raise_for_status()
            data = resp.json()
            memories = data.get("memories", [])
            return [{"memory": m.get("text", ""), "score": m.get("score", 0)} for m in memories]
    except Exception as e:
        logger.debug("HTTP API search failed: %s", e)
        return []


async def add(url: str, user_id: str, text: str) -> dict[str, Any] | None:
    """POST /add で記憶を追加。"""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{url.rstrip('/')}/add",
                json={"text": text},
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.warning("Failed to add memory: %s", e)
        return None


async def get_all(url: str, user_id: str) -> list[dict[str, Any]]:
    """GET /list で全記憶を取得。"""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(f"{url.rstrip('/')}/list")
            resp.raise_for_status()
            data = resp.json()
            memories = data.get("memories", [])
            return [{"memory": m.get("text", ""), "id": m.get("id", "")} for m in memories]
    except Exception as e:
        logger.warning("Failed to retrieve all memories: %s", e)
        return []


async def health(url: str) -> bool:
    """GET /health で稼働状態を確認。"""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
            resp = await client.get(f"{url.rstrip('/')}/health")
            return resp.status_code == 200
    except Exception:
        return False


async def get_status(url: str, user_id: str) -> dict[str, Any]:
    """ステータス情報を返す。"""
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
        error = "Cannot connect to memory server"
    return {
        "available": available,
        "memory_count": memory_count,
        "error": error,
    }
