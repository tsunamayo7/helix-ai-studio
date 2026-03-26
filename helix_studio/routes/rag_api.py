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
        raise HTTPException(status_code=400, detail="Filename is required")

    from pathlib import Path
    ext = Path(file.filename).suffix.lower()
    content = await file.read()

    # Docling 対応フォーマット (PDF, Office, 画像)
    if ext in rag.DOCLING_EXTENSIONS:
        text = await rag._parse_with_docling(content, file.filename)
        if not text:
            raise HTTPException(
                status_code=500,
                detail=f"Docling parse failed for {file.filename}. Is docling-serve running on {rag.DOCLING_URL}?",
            )
    # テキスト系フォーマット
    else:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = content.decode("shift_jis")
            except UnicodeDecodeError:
                raise HTTPException(status_code=400, detail="Unsupported file encoding")

    ollama_url = await get_setting("ollama_url") or "http://localhost:11434"
    result = await rag.ingest_text(text, file.filename, ollama_url=ollama_url)

    if not result.get("ok"):
        raise HTTPException(status_code=500, detail=result.get("error", "Registration failed"))
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
        raise HTTPException(status_code=500, detail="Failed to delete document")
    return {"ok": True, "doc_id": doc_id}
