"""RAG サービス — Qdrant + Ollama Embedding によるドキュメント検索

既に稼働中の Qdrant (localhost:6333) と Ollama 埋め込みモデルを再利用し、
最小限のコードでフル RAG パイプラインを実現する。

コレクション: helix_rag (Mem0 の mem0_shared とは分離)
"""

from __future__ import annotations

import hashlib
import logging
import re
import uuid
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

QDRANT_URL = "http://localhost:6333"
OLLAMA_URL = "http://localhost:11434"
COLLECTION = "helix_rag"
EMBEDDING_MODEL = "qwen3-embedding:8b"
EMBEDDING_DIM = 4096
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

_TIMEOUT = httpx.Timeout(connect=5.0, read=60.0, write=10.0, pool=5.0)

SUPPORTED_EXTENSIONS = {
    ".txt", ".md", ".py", ".js", ".ts", ".json", ".yaml", ".yml",
    ".toml", ".csv", ".html", ".css", ".sh", ".bat", ".sql",
    ".java", ".go", ".rs", ".c", ".cpp", ".h", ".rb", ".php",
    ".xml", ".ini", ".cfg", ".log", ".env",
}

# Docling Serve でパース可能な拡張子
DOCLING_EXTENSIONS = {
    ".pdf", ".docx", ".pptx", ".xlsx", ".png", ".jpg", ".jpeg",
    ".tiff", ".bmp", ".gif", ".webp",
}

DOCLING_URL = "http://localhost:5001"


# ── Docling パーサー ──────────────────────────────────────


async def _parse_with_docling(file_content: bytes, filename: str) -> str | None:
    """Docling Serve API でドキュメントをMarkdownに変換。"""
    import base64
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=5.0, read=120.0, write=30.0, pool=5.0)) as c:
            payload = {
                "options": {"to_format": "markdown"},
                "http_sources": [],
                "file_sources": [
                    {
                        "base64": base64.b64encode(file_content).decode("ascii"),
                        "filename": filename,
                    }
                ],
            }
            r = await c.post(f"{DOCLING_URL}/v1/convert/source", json=payload)
            r.raise_for_status()
            data = r.json()
            # Docling Serve v1 returns {"document": {"md_content": "..."}}
            doc = data.get("document", {})
            md = doc.get("md_content", "")
            if not md:
                # 代替パス: results 配列
                for result in data.get("results", []):
                    md += result.get("md_content", result.get("text", "")) + "\n"
            return md if md.strip() else None
    except Exception as e:
        logger.warning("Docling パース失敗 (%s): %s", filename, e)
        return None


# ── コレクション管理 ──────────────────────────────────────


async def ensure_collection() -> bool:
    """Qdrant コレクションが存在しなければ作成する。"""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            r = await c.get(f"{QDRANT_URL}/collections/{COLLECTION}")
            if r.status_code == 200:
                return True
            # 作成
            r = await c.put(
                f"{QDRANT_URL}/collections/{COLLECTION}",
                json={
                    "vectors": {"size": EMBEDDING_DIM, "distance": "Cosine"},
                },
            )
            r.raise_for_status()
            logger.info("Qdrant コレクション '%s' を作成", COLLECTION)
            return True
    except Exception as e:
        logger.warning("Qdrant コレクション確認失敗: %s", e)
        return False


# ── 埋め込み ──────────────────────────────────────────────


async def _embed(text: str, ollama_url: str | None = None) -> list[float] | None:
    """Ollama でテキストを埋め込みベクトルに変換。"""
    url = ollama_url or OLLAMA_URL
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            r = await c.post(
                f"{url}/api/embed",
                json={"model": EMBEDDING_MODEL, "input": text},
            )
            r.raise_for_status()
            embeddings = r.json().get("embeddings", [[]])
            return embeddings[0] if embeddings and embeddings[0] else None
    except Exception as e:
        logger.debug("埋め込み生成失敗: %s", e)
        return None


# ── チャンク分割 ──────────────────────────────────────────


def _chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[str]:
    """テキストを固定サイズチャンクに分割 (段落境界を優先)。"""
    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    # 段落で分割して再構成
    paragraphs = re.split(r"\n{2,}", text)
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(current) + len(para) + 2 <= chunk_size:
            current = f"{current}\n\n{para}" if current else para
        else:
            if current:
                chunks.append(current)
            # 長い段落はさらに分割
            if len(para) > chunk_size:
                words = para.split()
                current = ""
                for w in words:
                    if len(current) + len(w) + 1 <= chunk_size:
                        current = f"{current} {w}" if current else w
                    else:
                        if current:
                            chunks.append(current)
                        current = w
            else:
                current = para

    if current:
        chunks.append(current)

    # オーバーラップ適用
    if overlap > 0 and len(chunks) > 1:
        overlapped = [chunks[0]]
        for i in range(1, len(chunks)):
            prev_tail = chunks[i - 1][-overlap:]
            overlapped.append(prev_tail + "\n" + chunks[i])
        chunks = overlapped

    return chunks


# ── ドキュメント登録 ──────────────────────────────────────


async def ingest_text(
    text: str,
    filename: str,
    metadata: dict[str, Any] | None = None,
    ollama_url: str | None = None,
) -> dict[str, Any]:
    """テキストをチャンク分割 → 埋め込み → Qdrant に保存。"""
    if not await ensure_collection():
        return {"ok": False, "error": "Qdrant に接続できません"}

    chunks = _chunk_text(text)
    if not chunks:
        return {"ok": False, "error": "テキストが空です"}

    doc_id = hashlib.sha256(f"{filename}:{text[:200]}".encode()).hexdigest()[:16]
    points = []

    for i, chunk in enumerate(chunks):
        vector = await _embed(chunk, ollama_url)
        if not vector:
            continue
        point_id = str(uuid.uuid4())
        points.append({
            "id": point_id,
            "vector": vector,
            "payload": {
                "doc_id": doc_id,
                "filename": filename,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "content": chunk,
                **(metadata or {}),
            },
        })

    if not points:
        return {"ok": False, "error": "埋め込み生成に失敗しました"}

    # Qdrant にバッチ upsert
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            r = await c.put(
                f"{QDRANT_URL}/collections/{COLLECTION}/points",
                json={"points": points},
            )
            r.raise_for_status()
    except Exception as e:
        return {"ok": False, "error": f"Qdrant 保存失敗: {e}"}

    logger.info("RAG 登録: %s (%d チャンク)", filename, len(points))
    return {
        "ok": True,
        "doc_id": doc_id,
        "filename": filename,
        "chunks": len(points),
    }


async def ingest_file(
    file_path: str,
    ollama_url: str | None = None,
) -> dict[str, Any]:
    """ファイルを読み込んで ingest_text に渡す。"""
    p = Path(file_path)
    if not p.exists():
        return {"ok": False, "error": f"ファイルが見つかりません: {file_path}"}
    if p.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return {"ok": False, "error": f"未対応の拡張子: {p.suffix}"}

    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return {"ok": False, "error": f"読み込み失敗: {e}"}

    return await ingest_text(text, p.name, {"path": str(p)}, ollama_url)


# ── 検索 ──────────────────────────────────────────────────


async def search(
    query: str,
    limit: int = 5,
    score_threshold: float = 0.3,
    ollama_url: str | None = None,
) -> list[dict[str, Any]]:
    """クエリに関連するチャンクをベクトル検索で取得。"""
    vector = await _embed(query, ollama_url)
    if not vector:
        return []

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            r = await c.post(
                f"{QDRANT_URL}/collections/{COLLECTION}/points/search",
                json={
                    "vector": vector,
                    "limit": limit,
                    "with_payload": True,
                    "score_threshold": score_threshold,
                },
            )
            r.raise_for_status()
            results = []
            for point in r.json().get("result", []):
                payload = point.get("payload", {})
                results.append({
                    "content": payload.get("content", ""),
                    "filename": payload.get("filename", ""),
                    "chunk_index": payload.get("chunk_index", 0),
                    "score": round(point.get("score", 0), 4),
                })
            return results
    except Exception as e:
        logger.debug("RAG 検索失敗: %s", e)
        return []


def format_rag_context(results: list[dict[str, Any]]) -> str:
    """検索結果をプロンプト注入用のコンテキスト文字列にフォーマット。"""
    if not results:
        return ""
    lines = ["## 参考: ナレッジベース (RAG)"]
    for r in results:
        src = r.get("filename", "unknown")
        score = r.get("score", 0)
        lines.append(f"### [{src}] (relevance: {score})")
        lines.append(r.get("content", ""))
        lines.append("")
    return "\n".join(lines)


# ── ドキュメント管理 ──────────────────────────────────────


async def list_documents() -> list[dict[str, Any]]:
    """登録済みドキュメントの一覧を取得。"""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            r = await c.post(
                f"{QDRANT_URL}/collections/{COLLECTION}/points/scroll",
                json={"limit": 1000, "with_payload": True, "with_vector": False},
            )
            r.raise_for_status()
            points = r.json().get("result", {}).get("points", [])

            # doc_id でグループ化
            docs: dict[str, dict] = {}
            for p in points:
                payload = p.get("payload", {})
                doc_id = payload.get("doc_id", "unknown")
                if doc_id not in docs:
                    docs[doc_id] = {
                        "doc_id": doc_id,
                        "filename": payload.get("filename", ""),
                        "chunks": 0,
                        "total_chunks": payload.get("total_chunks", 0),
                    }
                docs[doc_id]["chunks"] += 1

            return list(docs.values())
    except Exception as e:
        logger.debug("ドキュメント一覧取得失敗: %s", e)
        return []


async def delete_document(doc_id: str) -> bool:
    """doc_id に一致する全チャンクを削除。"""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            r = await c.post(
                f"{QDRANT_URL}/collections/{COLLECTION}/points/delete",
                json={
                    "filter": {
                        "must": [
                            {"key": "doc_id", "match": {"value": doc_id}},
                        ],
                    },
                },
            )
            r.raise_for_status()
            logger.info("RAG ドキュメント削除: %s", doc_id)
            return True
    except Exception as e:
        logger.warning("RAG ドキュメント削除失敗: %s", e)
        return False


async def get_status() -> dict[str, Any]:
    """RAG サービスのステータスを返す。"""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as c:
            r = await c.get(f"{QDRANT_URL}/collections/{COLLECTION}")
            if r.status_code == 200:
                info = r.json().get("result", {})
                count = info.get("points_count", 0)
                return {"available": True, "points_count": count}
            return {"available": False, "error": "コレクション未作成"}
    except Exception:
        return {"available": False, "error": "Qdrant に接続できません"}
