"""Tests for helix_studio.db."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from helix_studio.db import (
    DEFAULT_SETTINGS,
    ENV_OVERRIDE_MAP,
    SCHEMA,
    get_connection,
    init_db,
)


@pytest.mark.asyncio
async def test_init_db_creates_tables(app, test_db_path):
    assert test_db_path.exists()


@pytest.mark.asyncio
async def test_default_settings_inserted(app, test_db_path):
    with patch("helix_studio.db.DB_PATH", test_db_path):
        db = await get_connection()
        try:
            cursor = await db.execute("SELECT COUNT(*) as cnt FROM settings")
            row = await cursor.fetchone()
            assert row["cnt"] >= len(DEFAULT_SETTINGS)
        finally:
            await db.close()


@pytest.mark.asyncio
async def test_get_connection_returns_row_factory(app, test_db_path):
    with patch("helix_studio.db.DB_PATH", test_db_path):
        db = await get_connection()
        try:
            cursor = await db.execute("SELECT 1 as val")
            row = await cursor.fetchone()
            assert row["val"] == 1
        finally:
            await db.close()


@pytest.mark.asyncio
async def test_env_override(app, test_db_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-123")
    with patch("helix_studio.db.DB_PATH", test_db_path):
        db = await get_connection()
        try:
            # Delete existing to force re-insert
            await db.execute("DELETE FROM settings WHERE key='claude_api_key'")
            await db.commit()
        finally:
            await db.close()
        await init_db()
        db = await get_connection()
        try:
            cursor = await db.execute(
                "SELECT value FROM settings WHERE key='claude_api_key'"
            )
            row = await cursor.fetchone()
            assert row["value"] == "test-key-123"
        finally:
            await db.close()


def test_schema_has_expected_tables():
    assert "CREATE TABLE IF NOT EXISTS settings" in SCHEMA
    assert "CREATE TABLE IF NOT EXISTS conversations" in SCHEMA
    assert "CREATE TABLE IF NOT EXISTS messages" in SCHEMA
    assert "CREATE TABLE IF NOT EXISTS pipeline_runs" in SCHEMA


def test_default_settings_keys():
    assert "ollama_url" in DEFAULT_SETTINGS
    assert "default_local_model" in DEFAULT_SETTINGS
    assert "language" in DEFAULT_SETTINGS


def test_env_override_map_keys():
    assert "ANTHROPIC_API_KEY" in ENV_OVERRIDE_MAP
    assert "OLLAMA_URL" in ENV_OVERRIDE_MAP
