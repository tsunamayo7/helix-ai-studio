"""ツール API ルーター — Web検索 + ファイル操作"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from helix_studio.services import tools

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/tools", tags=["tools"])


@router.post("/search")
async def search(req: dict) -> dict:
    """Web検索（DuckDuckGo、無料・APIキー不要）"""
    query = req.get("query", "")
    if not query:
        return {"error": "Search query is empty"}

    max_results = req.get("max_results", 5)
    results = await tools.web_search(query, max_results)
    return {
        "query": query,
        "results": results,
        "count": len(results),
        "formatted": tools.format_search_results(results),
    }


@router.post("/files/list")
async def list_files(req: dict) -> dict:
    """ディレクトリ一覧"""
    path = req.get("path", "")
    if not path:
        return {"error": "Path is empty"}
    result = await tools.list_files(path)
    result["formatted"] = tools.format_file_listing(result)
    return result


@router.post("/files/read")
async def read_file(req: dict) -> dict:
    """ファイル読み取り"""
    path = req.get("path", "")
    if not path:
        return {"error": "Path is empty"}
    return await tools.read_file(path)


@router.post("/files/write")
async def write_file(req: dict) -> dict:
    """ファイル書き込み"""
    path = req.get("path", "")
    content = req.get("content", "")
    if not path:
        return {"error": "Path is empty"}
    return await tools.write_file(path, content)
