"""Tests for chat API routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_post_chat_missing_api_key(client):
    # ValueError is raised when API key is missing, propagates as exception
    with pytest.raises(Exception):
        await client.post(
            "/api/chat",
            json={
                "provider": "claude",
                "model": "claude-sonnet-4-20250514",
                "messages": [{"role": "user", "content": "hi"}],
            },
        )


@pytest.mark.asyncio
async def test_post_chat_ollama_mock(client):
    async def fake_stream(*args, **kwargs):
        yield "Hello "
        yield "world!"

    with patch("helix_studio.routes.chat.local_ai.stream_chat", side_effect=fake_stream):
        resp = await client.post(
            "/api/chat",
            json={
                "provider": "ollama",
                "model": "gemma3:27b",
                "messages": [{"role": "user", "content": "hi"}],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["content"] == "Hello world!"
        assert data["provider"] == "ollama"
        assert "conversation_id" in data
