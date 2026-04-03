"""Tests for helix_studio.services.tools (unit tests)."""

from __future__ import annotations

import pytest

from helix_studio.services.tools import (
    _is_safe_path,
    format_search_results,
    format_file_listing,
)


class TestSafePath:
    def test_allowed_path(self):
        assert _is_safe_path("C:/Development/apps/test.py") is True

    def test_users_path(self):
        assert _is_safe_path("C:/Users/tomot/file.txt") is True

    def test_disallowed_path(self):
        assert _is_safe_path("C:/Windows/System32/cmd.exe") is False

    def test_traversal_attack(self):
        assert _is_safe_path("C:/Development/../../Windows/System32") is False


class TestFormatSearchResults:
    def test_empty(self):
        result = format_search_results([])
        assert "No search results" in result

    def test_with_results(self):
        results = [
            {"title": "Title 1", "snippet": "Snippet 1", "url": "https://example.com"},
        ]
        text = format_search_results(results)
        assert "Title 1" in text
        assert "Snippet 1" in text


class TestFormatFileListing:
    def test_error(self):
        result = format_file_listing({"error": "Not found"})
        assert "Error" in result

    def test_entries(self):
        result = format_file_listing({
            "path": "/test",
            "entries": [
                {"name": "dir1", "type": "dir"},
                {"name": "file1.py", "type": "file", "size_display": "1.0 KB"},
            ],
            "count": 2,
        })
        assert "dir1" in result
        assert "file1.py" in result
        assert "Total: 2" in result
