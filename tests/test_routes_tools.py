"""Tests for tools API routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_search_empty_query(client):
    resp = await client.post("/api/tools/search", json={"query": ""})
    assert resp.status_code == 200
    data = resp.json()
    assert "error" in data


@pytest.mark.asyncio
async def test_search_with_mock(client):
    with patch("helix_studio.services.tools.web_search", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = [
            {"title": "Result 1", "snippet": "Snippet 1", "url": "https://example.com", "source": "Test"}
        ]
        resp = await client.post("/api/tools/search", json={"query": "test query"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1


@pytest.mark.asyncio
async def test_files_list_empty_path(client):
    resp = await client.post("/api/tools/files/list", json={"path": ""})
    assert resp.status_code == 200
    data = resp.json()
    assert "error" in data


@pytest.mark.asyncio
async def test_files_read_empty_path(client):
    resp = await client.post("/api/tools/files/read", json={"path": ""})
    assert resp.status_code == 200
    data = resp.json()
    assert "error" in data
