"""Tests for helix_studio.services.pipeline (unit tests)."""

from __future__ import annotations

import pytest

from helix_studio.services.pipeline import _detect_provider


class TestDetectProvider:
    def test_claude_model(self):
        assert _detect_provider("claude-sonnet-4-20250514") == "claude"

    def test_openai_gpt(self):
        # gpt-4 prefix matches CLI codex mapping first
        assert _detect_provider("gpt-4o") == "codex"

    def test_openai_o_series(self):
        assert _detect_provider("o4-mini") == "openai"

    def test_ollama_default(self):
        assert _detect_provider("gemma3:27b") == "ollama"

    def test_ollama_gemma4(self):
        assert _detect_provider("gemma4:31b") == "ollama"

    def test_cli_opus(self):
        assert _detect_provider("opus") == "claude_code"

    def test_cli_sonnet(self):
        assert _detect_provider("sonnet") == "claude_code"

    def test_cli_codex(self):
        assert _detect_provider("gpt-5.4") == "codex"

    def test_cli_gemini(self):
        assert _detect_provider("gemini") == "gemini_cli"
