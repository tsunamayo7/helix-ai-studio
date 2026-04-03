"""Tests for CrewAI API routes."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_list_teams(client):
    resp = await client.get("/api/crew/teams")
    assert resp.status_code == 200
    data = resp.json()
    assert "teams" in data
    assert "dev_team" in data["teams"]
    assert "research_team" in data["teams"]
    assert "writing_team" in data["teams"]
