"""Tests for pipeline API routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_pipeline_history_empty(client):
    resp = await client.get("/api/pipeline/history/list")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_pipeline_not_found(client):
    resp = await client.get("/api/pipeline/nonexistent-id")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_start_pipeline(client):
    with patch("helix_studio.routes.pipeline_api.run_pipeline", new_callable=AsyncMock):
        resp = await client.post(
            "/api/pipeline/start",
            json={"title": "Test Pipeline", "input_text": "Write hello world"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "pending"
        assert "id" in data
