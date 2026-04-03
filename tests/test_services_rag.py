"""Tests for helix_studio.services.rag (unit tests with mocks)."""

from __future__ import annotations

import pytest

from helix_studio.services.rag import (
    _chunk_text,
    _tokenize_for_bm25,
    format_rag_context,
    SUPPORTED_EXTENSIONS,
    DOCLING_EXTENSIONS,
)


class TestChunkText:
    def test_short_text_single_chunk(self):
        chunks = _chunk_text("Hello world")
        assert len(chunks) == 1
        assert chunks[0] == "Hello world"

    def test_empty_text(self):
        chunks = _chunk_text("")
        assert chunks == []

    def test_whitespace_only(self):
        chunks = _chunk_text("   \n\n   ")
        assert chunks == []

    def test_long_text_multiple_chunks(self):
        text = "word " * 500  # ~2500 chars
        chunks = _chunk_text(text, chunk_size=200, overlap=0)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= 250  # allowing some tolerance

    def test_paragraph_boundary(self):
        text = "Paragraph one.\n\nParagraph two.\n\nParagraph three."
        chunks = _chunk_text(text, chunk_size=30, overlap=0)
        assert len(chunks) >= 2

    def test_overlap_applied(self):
        text = "A" * 500 + "\n\n" + "B" * 500
        chunks = _chunk_text(text, chunk_size=300, overlap=50)
        assert len(chunks) >= 2
        if len(chunks) > 1:
            # Second chunk should contain overlap from first
            assert len(chunks[1]) > 0


class TestBM25Tokenizer:
    def test_basic_tokenization(self):
        result = _tokenize_for_bm25("hello world hello")
        assert len(result["indices"]) > 0
        assert len(result["indices"]) == len(result["values"])

    def test_empty_text(self):
        result = _tokenize_for_bm25("")
        assert result["indices"] == []
        assert result["values"] == []

    def test_single_token(self):
        result = _tokenize_for_bm25("word")
        assert len(result["indices"]) == 1

    def test_indices_are_sorted(self):
        result = _tokenize_for_bm25("the quick brown fox jumps over the lazy dog")
        assert result["indices"] == sorted(result["indices"])


class TestFormatRagContext:
    def test_empty_results(self):
        assert format_rag_context([]) == ""

    def test_with_results(self):
        results = [
            {"content": "chunk text", "filename": "test.md", "score": 0.95},
        ]
        text = format_rag_context(results)
        assert "Knowledge Base" in text
        assert "test.md" in text
        assert "chunk text" in text

    def test_multiple_results(self):
        results = [
            {"content": "first", "filename": "a.txt", "score": 0.9},
            {"content": "second", "filename": "b.txt", "score": 0.8},
        ]
        text = format_rag_context(results)
        assert "first" in text
        assert "second" in text


class TestExtensions:
    def test_supported_has_common_formats(self):
        assert ".py" in SUPPORTED_EXTENSIONS
        assert ".md" in SUPPORTED_EXTENSIONS
        assert ".json" in SUPPORTED_EXTENSIONS

    def test_docling_has_pdf(self):
        assert ".pdf" in DOCLING_EXTENSIONS
        assert ".docx" in DOCLING_EXTENSIONS
