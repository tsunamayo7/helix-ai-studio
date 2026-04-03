"""Tests for MCP API routes."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_list_mcp_servers(client):
    resp = await client.get("/api/mcp/servers")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_list_mcp_tools(client):
    resp = await client.get("/api/mcp/tools")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
