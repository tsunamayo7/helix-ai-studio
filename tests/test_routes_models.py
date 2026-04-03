"""Tests for models API routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_list_models(client):
    with (
        patch("helix_studio.services.local_ai.list_ollama_models", new_callable=AsyncMock) as mock_ollama,
        patch("helix_studio.services.local_ai.list_openai_compat_models", new_callable=AsyncMock) as mock_compat,
        patch("helix_studio.services.cloud_ai.list_claude_models", new_callable=AsyncMock) as mock_claude,
        patch("helix_studio.services.cloud_ai.list_openai_models", new_callable=AsyncMock) as mock_openai,
        patch("helix_studio.services.cli_ai.list_cli_models") as mock_cli,
    ):
        mock_ollama.return_value = [
            {"provider": "ollama", "name": "gemma4:31b", "size": "18.0 GB"},
        ]
        mock_compat.return_value = []
        mock_claude.return_value = []
        mock_openai.return_value = []
        mock_cli.return_value = {}

        resp = await client.get("/api/models")
        assert resp.status_code == 200
        data = resp.json()
        assert "ollama" in data
        assert len(data["ollama"]) == 1
        assert data["ollama"][0]["name"] == "gemma4:31b"


@pytest.mark.asyncio
async def test_test_connection_ollama(client):
    with patch("helix_studio.services.local_ai.list_ollama_models", new_callable=AsyncMock) as mock:
        mock.return_value = [{"name": "gemma3:27b"}]
        resp = await client.post(
            "/api/models/test",
            json={"provider": "ollama"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True


@pytest.mark.asyncio
async def test_test_connection_unsupported(client):
    resp = await client.post(
        "/api/models/test",
        json={"provider": "unsupported_provider"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
