"""
KnowledgeRetriever — semantic similarity search over hospital knowledge chunks.

Uses pgvector's cosine distance operator (<=>), filtered strictly by:
  1. hospital_id — no cross-hospital leakage possible
  2. access_scope — PUBLIC for AI queries, PUBLIC|STAFF for staff search
  3. is_active (via document join) — only indexed active documents

SEARCH PIPELINE:
  1. Embed the query string (RETRIEVAL_QUERY task type)
  2. Run cosine similarity search with IVFFlat ANN index
  3. Filter by similarity threshold
  4. Return top-K results with document metadata

ARCHITECTURE NOTE:
  The AI tool calls this retriever — not the database directly.
  All SQL is parameterised; no user-controlled values are interpolated.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Literal

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.knowledge.embeddings import EmbeddingService

logger = structlog.get_logger(__name__)

AccessScope = Literal["PUBLIC", "STAFF_AND_PUBLIC"]


@dataclass(frozen=True)
class RetrievalResult:
    """A single retrieved knowledge chunk with its similarity score."""
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    source_type: str
    content: str
    similarity: float          # 0.0 – 1.0 (higher = more similar)
    chunk_index: int


class KnowledgeRetriever:
    """
    Executes semantic similarity search over a hospital's knowledge base.

    Instantiate per request with the current DB session.
    """

    def __init__(
        self,
        db: AsyncSession,
        embedding_service: EmbeddingService,
        top_k: int = 5,
        min_similarity: float = 0.70,
    ) -> None:
        self._db = db
        self._emb = embedding_service
        self._top_k = top_k
        self._min_similarity = min_similarity

    async def search(
        self,
        hospital_id: uuid.UUID,
        query: str,
        access_scope: AccessScope = "PUBLIC",
    ) -> list[RetrievalResult]:
        """
        Semantic search over a hospital's knowledge base.

        Args:
            hospital_id: Tenant scope — NEVER omit this.
            query: Patient/staff question text.
            access_scope: "PUBLIC" (AI-facing) or "STAFF_AND_PUBLIC" (admin search).

        Returns:
            Up to top_k results ordered by similarity descending.
        """
        if not self._emb.is_available:
            logger.warning("retriever_embeddings_unavailable")
            return []

        if not query.strip():
            return []

        try:
            query_vec = await self._emb.embed_query(query)
        except Exception as exc:
            logger.error("retriever_embed_query_failed", error=str(exc))
            return []

        # Build scope filter
        if access_scope == "PUBLIC":
            scope_filter = "kc.access_scope = 'PUBLIC'"
        else:
            scope_filter = "kc.access_scope IN ('PUBLIC', 'STAFF')"

        # pgvector cosine distance: 1 - (embedding <=> query_vec) = cosine similarity
        # Lower <=> distance = higher similarity
        sql = text(f"""
            SELECT
                kc.id            AS chunk_id,
                kc.document_id,
                kd.title         AS document_title,
                kc.source_type,
                kc.content,
                kc.chunk_index,
                1 - (kc.embedding <=> CAST(:query_vec AS vector)) AS similarity
            FROM knowledge_chunks kc
            JOIN knowledge_documents kd
              ON kd.id = kc.document_id
             AND kd.is_active = TRUE
             AND kd.hospital_id = :hospital_id
            WHERE kc.hospital_id = :hospital_id
              AND kc.embedding IS NOT NULL
              AND {scope_filter}
              AND 1 - (kc.embedding <=> CAST(:query_vec AS vector)) >= :min_similarity
            ORDER BY kc.embedding <=> CAST(:query_vec AS vector) ASC
            LIMIT :top_k
        """)

        try:
            result = await self._db.execute(
                sql,
                {
                    "hospital_id": str(hospital_id),
                    "query_vec": f"[{','.join(str(v) for v in query_vec)}]",
                    "min_similarity": self._min_similarity,
                    "top_k": self._top_k,
                },
            )
            rows = result.mappings().all()
        except Exception as exc:
            logger.error("retriever_search_failed", error=str(exc))
            return []

        results = []
        for row in rows:
            results.append(RetrievalResult(
                chunk_id=uuid.UUID(str(row["chunk_id"])),
                document_id=uuid.UUID(str(row["document_id"])),
                document_title=row["document_title"],
                source_type=row["source_type"],
                content=row["content"],
                similarity=float(row["similarity"]),
                chunk_index=int(row["chunk_index"]),
            ))

        logger.info(
            "knowledge_retrieval_complete",
            hospital_id=str(hospital_id),
            query_length=len(query),
            results_found=len(results),
        )
        return results

    @staticmethod
    def format_for_llm(results: list[RetrievalResult], max_chars: int = 3000) -> str:
        """
        Format retrieval results as a context block for the LLM system prompt.
        Respects a max_chars budget to avoid context overflow.
        """
        if not results:
            return ""

        lines = ["## Retrieved Hospital Knowledge\n"]
        total = len(lines[0])

        for i, r in enumerate(results, 1):
            block = (
                f"**Source {i}: {r.document_title}** (relevance: {r.similarity:.0%})\n"
                f"{r.content.strip()}\n\n"
            )
            if total + len(block) > max_chars:
                break
            lines.append(block)
            total += len(block)

        lines.append(
            "*(Use the above context to answer the patient's question. "
            "If the answer is not in the context, say so and offer to connect to staff.)*"
        )
        return "".join(lines)
