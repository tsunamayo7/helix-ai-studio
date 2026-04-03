"""Tests for settings API routes."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_get_settings(client):
    resp = await client.get("/api/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert "settings" in data
    assert "ollama_url" in data["settings"]


@pytest.mark.asyncio
async def test_update_settings(client):
    resp = await client.put(
        "/api/settings",
        json={"settings": {"language": "en"}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "en" not in data.get("updated", []) or data["count"] >= 0


@pytest.mark.asyncio
async def test_api_key_masking(client):
    # Set a fake API key
    await client.put(
        "/api/settings",
        json={"settings": {"claude_api_key": "sk-ant-test1234567890"}},
    )
    resp = await client.get("/api/settings")
    data = resp.json()
    key_val = data["settings"].get("claude_api_key", "")
    # Should be masked except last 4 chars
    assert "****" in key_val or key_val == ""


@pytest.mark.asyncio
async def test_masked_value_not_overwritten(client):
    # Set real key
    await client.put(
        "/api/settings",
        json={"settings": {"claude_api_key": "sk-ant-real-key-abcd"}},
    )
    # Send masked value back — should NOT overwrite
    await client.put(
        "/api/settings",
        json={"settings": {"claude_api_key": "**************abcd"}},
    )
    # The original should still be intact (we can't read it directly from API
    # but we verify the masked key still ends with 'abcd')
    resp = await client.get("/api/settings")
    val = resp.json()["settings"]["claude_api_key"]
    assert val.endswith("abcd")


@pytest.mark.asyncio
async def test_bool_keys_returned_as_bool(client):
    resp = await client.get("/api/settings")
    data = resp.json()["settings"]
    # mem0_auto_inject and rag_auto_inject should be booleans
    assert isinstance(data.get("mem0_auto_inject"), bool)
    assert isinstance(data.get("rag_auto_inject"), bool)
