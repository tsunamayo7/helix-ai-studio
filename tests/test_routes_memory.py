"""Tests for memory API routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_search_memory(client):
    with patch("helix_studio.services.mem0.search", new_callable=AsyncMock) as mock:
        mock.return_value = [{"memory": "test memory", "score": 0.9}]
        resp = await client.post(
            "/api/memory/search",
            json={"query": "test"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["results"][0]["memory"] == "test memory"


@pytest.mark.asyncio
async def test_add_memory(client):
    with patch("helix_studio.services.mem0.add", new_callable=AsyncMock) as mock:
        mock.return_value = {"id": "mem-1"}
        resp = await client.post(
            "/api/memory/add",
            json={"text": "remember this"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True


@pytest.mark.asyncio
async def test_add_memory_failure(client):
    with patch("helix_studio.services.mem0.add", new_callable=AsyncMock) as mock:
        mock.return_value = None
        resp = await client.post(
            "/api/memory/add",
            json={"text": "remember this"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False


@pytest.mark.asyncio
async def test_memory_status(client):
    with patch("helix_studio.services.mem0.get_status", new_callable=AsyncMock) as mock:
        mock.return_value = {"available": True, "memory_count": 42, "error": None}
        resp = await client.get("/api/memory/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is True
        assert data["memory_count"] == 42
