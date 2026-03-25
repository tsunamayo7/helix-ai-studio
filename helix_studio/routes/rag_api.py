"""RAG ナレッジベース API ルーター"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, File, UploadFile, HTTPException
from pydantic import BaseModel

from helix_studio.config import get_setting
from helix_studio.services import rag

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rag", tags=["rag"])


class RAGSearchRequest(BaseModel):
    query: str
    limit: int = 5


class RAGDeleteRequest(BaseModel):
    doc_id: str


@router.get("/status")
async def rag_status() -> dict[str, Any]:
    """RAG サービスのステータスを返す。"""
    return await rag.get_status()


@router.get("/documents")
async def list_documents() -> list[dict[str, Any]]:
    """登録済みドキュメント一覧。"""
    return await rag.list_documents()


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)) -> dict[str, Any]:
    """ドキュメントをアップロードして RAG に登録。"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="ファイル名が必要です")

    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = content.decode("shift_jis")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="テキストファイルのみ対応しています")

    ollama_url = await get_setting("ollama_url") or "http://localhost:11434"
    result = await rag.ingest_text(text, file.filename, ollama_url=ollama_url)

    if not result.get("ok"):
        raise HTTPException(status_code=500, detail=result.get("error", "登録失敗"))
    return result


@router.post("/search")
async def search_documents(req: RAGSearchRequest) -> list[dict[str, Any]]:
    """ナレッジベースをベクトル検索。"""
    ollama_url = await get_setting("ollama_url") or "http://localhost:11434"
    return await rag.search(req.query, limit=req.limit, ollama_url=ollama_url)


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str) -> dict[str, Any]:
    """ドキュメントを削除。"""
    ok = await rag.delete_document(doc_id)
    if not ok:
        raise HTTPException(status_code=500, detail="削除に失敗しました")
    return {"ok": True, "doc_id": doc_id}
