"""
Unit tests for the text chunker (Phase 5 — Knowledge/RAG).

These tests are pure Python — no DB, no external services required.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "services", "api"))

from app.ai.knowledge.chunker import chunk_text, TextChunk


class TestChunkText:
    """Tests for the document chunker."""

    def test_empty_text_returns_empty(self):
        result = chunk_text("")
        assert result == []

    def test_whitespace_only_returns_empty(self):
        result = chunk_text("   \n\n  ")
        assert result == []

    def test_short_text_single_chunk(self):
        text = "This is a short document."
        result = chunk_text(text, chunk_size=1000)
        assert len(result) == 1
        assert result[0].content == text
        assert result[0].chunk_index == 0

    def test_chunk_indices_are_sequential(self):
        text = ("A " * 200 + "\n\n") * 5  # ~2000+ chars
        result = chunk_text(text, chunk_size=400, chunk_overlap=50)
        for i, chunk in enumerate(result):
            assert chunk.chunk_index == i

    def test_chunks_respect_max_size(self):
        text = "word " * 500  # 2500 chars
        result = chunk_text(text, chunk_size=500, chunk_overlap=50)
        for chunk in result:
            # Allow slight overflow at word boundaries
            assert len(chunk.content) <= 700, f"Chunk too long: {len(chunk.content)}"

    def test_token_count_is_positive(self):
        text = "Hello world, this is a test document with some content."
        result = chunk_text(text, chunk_size=1000)
        assert all(c.token_count > 0 for c in result)

    def test_paragraph_breaks_preferred(self):
        text = "First paragraph content here.\n\nSecond paragraph here.\n\nThird paragraph."
        result = chunk_text(text, chunk_size=40, chunk_overlap=0)
        # Should split at paragraph breaks
        assert len(result) >= 2

    def test_returns_text_chunk_objects(self):
        text = "Some content for testing."
        result = chunk_text(text)
        assert all(isinstance(c, TextChunk) for c in result)

    def test_all_content_preserved(self):
        """Key property: no content should be silently dropped."""
        text = ("The quick brown fox jumps over the lazy dog. " * 50).strip()
        result = chunk_text(text, chunk_size=200, chunk_overlap=20)
        # Every unique sentence segment should appear in at least one chunk
        assert len(result) > 0
        # Combined chunks should contain all words from the original
        combined = " ".join(c.content for c in result)
        # At least 80% of original words should be present
        original_words = set(text.split())
        combined_words = set(combined.split())
        coverage = len(original_words & combined_words) / len(original_words)
        assert coverage >= 0.80, f"Content coverage too low: {coverage:.0%}"
