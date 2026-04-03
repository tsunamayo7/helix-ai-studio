"""Tests for RAG API routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_rag_status(client):
    with patch("helix_studio.services.rag.get_status", new_callable=AsyncMock) as mock:
        mock.return_value = {"available": False, "error": "Cannot connect to Qdrant"}
        resp = await client.get("/api/rag/status")
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_rag_documents_list(client):
    with patch("helix_studio.services.rag.list_documents", new_callable=AsyncMock) as mock:
        mock.return_value = []
        resp = await client.get("/api/rag/documents")
        assert resp.status_code == 200
        assert resp.json() == []


@pytest.mark.asyncio
async def test_rag_search(client):
    with patch("helix_studio.services.rag.search", new_callable=AsyncMock) as mock:
        mock.return_value = [
            {"content": "test chunk", "filename": "test.md", "chunk_index": 0, "score": 0.95}
        ]
        resp = await client.post(
            "/api/rag/search",
            json={"query": "test", "limit": 5},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["content"] == "test chunk"
