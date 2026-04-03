"""Tests for helix_studio.services.cli_ai (unit tests)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from helix_studio.services.cli_ai import (
    CLAUDE_CODE_MODELS,
    CODEX_MODELS,
    GEMINI_CLI_MODELS,
    detect_installed_clis,
    list_cli_models,
)


class TestDetectInstalledClis:
    def test_returns_dict(self):
        result = detect_installed_clis()
        assert isinstance(result, dict)
        assert "claude_code" in result
        assert "codex" in result
        assert "gemini_cli" in result

    def test_all_values_are_bool(self):
        result = detect_installed_clis()
        for v in result.values():
            assert isinstance(v, bool)


class TestListCliModels:
    def test_with_no_cli_installed(self):
        with patch("helix_studio.services.cli_ai.detect_installed_clis") as mock:
            mock.return_value = {"claude_code": False, "codex": False, "gemini_cli": False}
            result = list_cli_models()
            assert result == {}

    def test_with_claude_installed(self):
        with patch("helix_studio.services.cli_ai.detect_installed_clis") as mock:
            mock.return_value = {"claude_code": True, "codex": False, "gemini_cli": False}
            result = list_cli_models()
            assert "claude_code" in result
            assert len(result["claude_code"]) == len(CLAUDE_CODE_MODELS)


class TestModelDefinitions:
    def test_claude_models_have_id(self):
        for m in CLAUDE_CODE_MODELS:
            assert "id" in m
            assert "name" in m

    def test_codex_models_have_id(self):
        for m in CODEX_MODELS:
            assert "id" in m

    def test_gemini_models_have_id(self):
        for m in GEMINI_CLI_MODELS:
            assert "id" in m
