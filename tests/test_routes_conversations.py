"""Tests for conversation CRUD API routes."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_create_conversation(client):
    resp = await client.post(
        "/api/conversations",
        json={"title": "Test Conv", "provider": "ollama", "model": "gemma3:27b"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert data["title"] == "Test Conv"


@pytest.mark.asyncio
async def test_list_conversations(client):
    # Create one
    await client.post(
        "/api/conversations",
        json={"title": "List Test"},
    )
    resp = await client.get("/api/conversations")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_get_conversation(client):
    create_resp = await client.post(
        "/api/conversations",
        json={"title": "Get Test"},
    )
    conv_id = create_resp.json()["id"]
    resp = await client.get(f"/api/conversations/{conv_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == conv_id
    assert data["title"] == "Get Test"
    assert "messages" in data


@pytest.mark.asyncio
async def test_get_conversation_not_found(client):
    resp = await client.get("/api/conversations/nonexistent-id")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_conversation(client):
    create_resp = await client.post(
        "/api/conversations",
        json={"title": "Delete Test"},
    )
    conv_id = create_resp.json()["id"]
    del_resp = await client.delete(f"/api/conversations/{conv_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["deleted"] == conv_id

    # Verify deleted
    get_resp = await client.get(f"/api/conversations/{conv_id}")
    assert get_resp.status_code == 404
