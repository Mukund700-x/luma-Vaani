"""
EmbeddingService — generates text embeddings via Google text-embedding-004.

Google's text-embedding-004 model:
  - Dimensions: 768
  - Max input tokens: 2048 per request
  - Task types: RETRIEVAL_DOCUMENT (ingestion) vs RETRIEVAL_QUERY (search)
  - Using task_type correctly improves retrieval accuracy significantly.

PHI SAFETY:
  Patient messages passed for retrieval must be pre-sanitised by the caller.
  This service is stateless and unaware of patient identity.
"""

from __future__ import annotations

import asyncio
from typing import Literal

import structlog

logger = structlog.get_logger(__name__)

EMBEDDING_DIM = 768
_MODEL_NAME = "models/text-embedding-004"

try:
    import google.generativeai as genai
    _GENAI_AVAILABLE = True
except ImportError:
    _GENAI_AVAILABLE = False

TaskType = Literal["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY", "SEMANTIC_SIMILARITY"]


class EmbeddingService:
    """
    Thin async wrapper around the Gemini Embeddings API.

    Usage:
        svc = EmbeddingService(api_key=settings.GEMINI_API_KEY)
        vec = await svc.embed_query("What are visiting hours?")
        vecs = await svc.embed_documents(["FAQ text...", "Policy text..."])
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._configured = False

    def _ensure_configured(self) -> None:
        if not _GENAI_AVAILABLE:
            raise RuntimeError(
                "google-generativeai is not installed. "
                "Run: pip install google-generativeai>=0.8.0"
            )
        if not self._configured:
            genai.configure(api_key=self._api_key)
            self._configured = True

    async def embed_query(self, text: str) -> list[float]:
        """
        Generate a query embedding for semantic search.
        Uses RETRIEVAL_QUERY task type — optimised for finding similar documents.
        """
        return await self._embed(text, task_type="RETRIEVAL_QUERY")

    async def embed_document(self, text: str) -> list[float]:
        """
        Generate a document embedding for storage.
        Uses RETRIEVAL_DOCUMENT task type — optimised to be retrieved by queries.
        """
        return await self._embed(text, task_type="RETRIEVAL_DOCUMENT")

    async def embed_documents_batch(
        self,
        texts: list[str],
        batch_size: int = 20,
    ) -> list[list[float]]:
        """
        Generate embeddings for multiple document chunks.
        Processes in batches to respect API rate limits.
        """
        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            embeddings = await asyncio.gather(
                *[self.embed_document(text) for text in batch]
            )
            all_embeddings.extend(embeddings)
        return all_embeddings

    async def _embed(self, text: str, task_type: TaskType) -> list[float]:
        """Call the Gemini Embedding API via asyncio.to_thread."""
        if not self._api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")

        self._ensure_configured()

        text = text.strip()
        if not text:
            raise ValueError("Cannot embed empty text")

        # Truncate to safe limit (≈8000 chars ≈ 2000 tokens)
        if len(text) > 8000:
            text = text[:8000]
            logger.debug("embed_text_truncated", original_len=len(text))

        result = await asyncio.to_thread(
            genai.embed_content,
            model=_MODEL_NAME,
            content=text,
            task_type=task_type,
        )

        embedding = result["embedding"]
        if len(embedding) != EMBEDDING_DIM:
            raise ValueError(
                f"Unexpected embedding dimension: {len(embedding)} (expected {EMBEDDING_DIM})"
            )

        return embedding

    @property
    def is_available(self) -> bool:
        return _GENAI_AVAILABLE and bool(self._api_key)
