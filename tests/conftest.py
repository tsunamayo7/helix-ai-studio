"""Shared test fixtures."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from helix_studio.app import create_app
from helix_studio.db import DB_PATH


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture()
def test_db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture()
async def app(test_db_path: Path):
    """Create a FastAPI app with an isolated test DB."""
    with patch("helix_studio.db.DB_PATH", test_db_path):
        _app = create_app()
        async with _app.router.lifespan_context(_app):
            yield _app


@pytest.fixture()
async def client(app) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
