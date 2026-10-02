"""
KnowledgeDocument and KnowledgeChunk ORM models.

KnowledgeDocument: a hospital-owned source document (FAQ, policy, doctor profile, etc.)
KnowledgeChunk: a chunked + embedded piece of a document, used for semantic retrieval.

ARCHITECTURE (ADR-004):
  - Embeddings are stored as pgvector `vector(768)` columns.
  - All vector search is scoped to `hospital_id` — cross-hospital leakage is impossible.
  - PUBLIC-scoped chunks are queryable by the AI for patient-facing answers.
  - STAFF-scoped chunks are only queryable by logged-in staff via admin search.
  - Document content is the source of truth; chunks are derived and re-generatable.

Embedding model: Google text-embedding-004 (768 dimensions)
Vector distance metric: cosine similarity (<=> operator in pgvector)
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.core.enums import DocumentAccessScope, DocumentSourceType

try:
    from pgvector.sqlalchemy import Vector
    _PGVECTOR_AVAILABLE = True
except ImportError:
    Vector = None
    _PGVECTOR_AVAILABLE = False


# Embedding dimensions for Google text-embedding-004
EMBEDDING_DIM = 768


class KnowledgeDocument(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    A source document owned by a hospital.

    Examples:
      - FAQ: "What are your visiting hours?"
      - POLICY: "Cancellation policy"
      - DOCTOR_PROFILE: "Dr. Sharma — Cardiologist bio"
      - VISITING_HOURS: "Ward visiting hours schedule"
      - CONTACT_INFO: "Phone numbers and departments"
      - INSURANCE: "Accepted insurance plans"
    """

    __tablename__ = "knowledge_documents"
    __table_args__ = (
        Index("ix_knowledge_docs_hospital_id", "hospital_id"),
        Index("ix_knowledge_docs_source_type", "source_type"),
        Index("ix_knowledge_docs_hospital_scope", "hospital_id", "access_scope"),
    )

    hospital_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hospitals.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    # FAQ, POLICY, DOCTOR_PROFILE, PATIENT_INSTRUCTIONS, VISITING_HOURS,
    # INSURANCE, CONTACT_INFO, GENERAL
    source_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default=DocumentSourceType.GENERAL.value
    )
    # PUBLIC: AI can use for patient answers
    # STAFF: only staff admin search
    # INTERNAL: admin-only, not AI-accessible
    access_scope: Mapped[str] = mapped_column(
        String(20), nullable=False, default=DocumentAccessScope.PUBLIC.value
    )
    content: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="Full source text — chunks are derived from this"
    )
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Embedding status: PENDING, INDEXED, FAILED
    embedding_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PENDING"
    )
    # Document-level metadata (tags, version, source URL, etc.)
    metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )

    # Relationships
    chunks: Mapped[list["KnowledgeChunk"]] = relationship(
        "KnowledgeChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<KnowledgeDocument id={self.id} title={self.title[:40]!r} "
            f"type={self.source_type} scope={self.access_scope}>"
        )


class KnowledgeChunk(Base, UUIDPrimaryKeyMixin):
    """
    A chunked excerpt of a KnowledgeDocument with a vector embedding.

    Chunks are the atomic unit of retrieval.
    - chunk_index: position within the parent document (0-indexed)
    - embedding: 768-dimensional float32 vector from text-embedding-004
    - token_count: approximate token count for context window management
    """

    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        Index("ix_knowledge_chunks_document_id", "document_id"),
        Index("ix_knowledge_chunks_hospital_scope", "hospital_id", "access_scope"),
        # IVFFlat index for fast approximate nearest-neighbour search
        # Created in migration (requires pgvector extension)
    )

    hospital_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hospitals.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Denormalised from parent document for fast filtered vector queries
    access_scope: Mapped[str] = mapped_column(String(20), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)

    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Vector embedding — None until generated
    if _PGVECTOR_AVAILABLE and Vector is not None:
        embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    else:
        embedding = mapped_column(Text, nullable=True)  # fallback (not functional)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationship
    document: Mapped[KnowledgeDocument] = relationship(
        "KnowledgeDocument", back_populates="chunks"
    )

    def __repr__(self) -> str:
        return (
            f"<KnowledgeChunk id={self.id} doc={self.document_id} "
            f"idx={self.chunk_index} tokens={self.token_count}>"
        )
