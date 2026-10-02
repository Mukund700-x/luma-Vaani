"""
Text chunker — splits documents into overlapping chunks for embedding.

Strategy: recursive character splitting (similar to LangChain's RecursiveCharacterTextSplitter).
No external dependency required — pure Python.

Chunk sizes are in characters (not tokens), with a conservative estimate of
~4 chars per token for English text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    """A single chunk of text with its position metadata."""
    content: str
    chunk_index: int
    char_start: int
    char_end: int
    token_count: int  # approximate


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 characters per token for English."""
    return max(1, len(text) // 4)


def _split_by_separator(text: str, separator: str) -> list[str]:
    if separator == "":
        return list(text)
    return text.split(separator)


def chunk_text(
    text: str,
    chunk_size: int = 1500,
    chunk_overlap: int = 200,
) -> list[TextChunk]:
    """
    Split text into overlapping chunks using a hierarchy of separators.

    Priority: paragraph → sentence → newline → space → character

    Args:
        text: Source text to chunk
        chunk_size: Maximum characters per chunk
        chunk_overlap: Characters of overlap between consecutive chunks

    Returns:
        List of TextChunk objects in document order
    """
    text = text.strip()
    if not text:
        return []

    # Use a simple sliding window approach for reliability and zero dependencies
    chunks: list[TextChunk] = []
    separators = ["\n\n", "\n", ". ", "? ", "! ", " ", ""]

    # Try to find natural break points
    raw_chunks = _recursive_split(text, separators, chunk_size)

    # Merge small chunks and apply overlap
    merged = _merge_with_overlap(raw_chunks, chunk_size, chunk_overlap)

    char_pos = 0
    for idx, chunk_text in enumerate(merged):
        # Find actual position in original text
        start = text.find(chunk_text[:50], char_pos)
        if start == -1:
            start = char_pos
        end = start + len(chunk_text)
        char_pos = max(char_pos, end - chunk_overlap)

        chunks.append(TextChunk(
            content=chunk_text,
            chunk_index=idx,
            char_start=start,
            char_end=end,
            token_count=_estimate_tokens(chunk_text),
        ))

    return chunks


def _recursive_split(
    text: str,
    separators: list[str],
    chunk_size: int,
) -> list[str]:
    """Recursively split using separator hierarchy."""
    if not text:
        return []

    if len(text) <= chunk_size:
        return [text]

    for sep in separators:
        if sep == "":
            # Last resort: split at chunk_size boundary
            return [
                text[i:i + chunk_size]
                for i in range(0, len(text), chunk_size)
            ]

        if sep in text:
            parts = text.split(sep)
            result = []
            current = ""
            for part in parts:
                candidate = current + sep + part if current else part
                if len(candidate) <= chunk_size:
                    current = candidate
                else:
                    if current:
                        result.append(current)
                    # Part itself too large? Recurse with next separator
                    if len(part) > chunk_size:
                        result.extend(_recursive_split(part, separators[separators.index(sep) + 1:], chunk_size))
                    else:
                        current = part
            if current:
                result.append(current)
            return result

    return [text]


def _merge_with_overlap(
    chunks: list[str],
    chunk_size: int,
    overlap: int,
) -> list[str]:
    """Add overlap between consecutive chunks."""
    if len(chunks) <= 1:
        return chunks

    result = []
    for i, chunk in enumerate(chunks):
        if i == 0:
            result.append(chunk)
            continue
        # Prepend tail of previous chunk as context
        prev = chunks[i - 1]
        tail = prev[-overlap:] if len(prev) > overlap else prev
        merged = (tail + " " + chunk).strip()
        if len(merged) <= chunk_size:
            result.append(merged)
        else:
            result.append(chunk)

    return result
