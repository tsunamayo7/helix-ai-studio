"""Tests for helix_studio.config."""

from __future__ import annotations

import pytest

from helix_studio.config import get_all_settings, get_setting, set_setting


@pytest.mark.asyncio
async def test_get_setting_returns_default(app):
    val = await get_setting("ollama_url")
    assert val == "http://localhost:11434"


@pytest.mark.asyncio
async def test_get_setting_nonexistent(app):
    val = await get_setting("nonexistent_key_xyz")
    assert val is None


@pytest.mark.asyncio
async def test_set_and_get_setting(app):
    await set_setting("test_key", "test_value")
    val = await get_setting("test_key")
    assert val == "test_value"


@pytest.mark.asyncio
async def test_set_setting_overwrite(app):
    await set_setting("overwrite_key", "first")
    await set_setting("overwrite_key", "second")
    val = await get_setting("overwrite_key")
    assert val == "second"


@pytest.mark.asyncio
async def test_get_all_settings_returns_dict(app):
    settings = await get_all_settings()
    assert isinstance(settings, dict)
    assert "ollama_url" in settings
    assert "language" in settings
