"""
Knowledge module Pydantic schemas.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.core.enums import DocumentAccessScope, DocumentSourceType


# ── Document schemas ───────────────────────────────────────────────────────────

class KnowledgeDocumentCreate(BaseModel):
    title: str = Field(max_length=500, description="Document title")
    source_type: DocumentSourceType = Field(
        default=DocumentSourceType.GENERAL,
        description="FAQ | POLICY | DOCTOR_PROFILE | PATIENT_INSTRUCTIONS | VISITING_HOURS | INSURANCE | CONTACT_INFO | GENERAL",
    )
    access_scope: DocumentAccessScope = Field(
        default=DocumentAccessScope.PUBLIC,
        description="PUBLIC (AI-accessible) | STAFF (staff search only) | INTERNAL (admin only)",
    )
    content: str = Field(
        min_length=10,
        description="Full source text. Will be automatically chunked and embedded.",
    )
    language: str = Field(default="en", max_length=10)
    metadata: dict = Field(default_factory=dict)


class KnowledgeDocumentUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    source_type: DocumentSourceType | None = None
    access_scope: DocumentAccessScope | None = None
    content: str | None = Field(default=None, min_length=10)
    language: str | None = None
    is_active: bool | None = None
    metadata: dict | None = None


class KnowledgeDocumentResponse(BaseModel):
    id: uuid.UUID
    hospital_id: uuid.UUID
    title: str
    source_type: str
    access_scope: str
    language: str
    is_active: bool
    embedding_status: str
    chunk_count: int = 0
    content_length: int = 0
    metadata: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_with_stats(cls, doc, chunk_count: int = 0) -> "KnowledgeDocumentResponse":
        return cls(
            id=doc.id,
            hospital_id=doc.hospital_id,
            title=doc.title,
            source_type=doc.source_type,
            access_scope=doc.access_scope,
            language=doc.language,
            is_active=doc.is_active,
            embedding_status=doc.embedding_status,
            chunk_count=chunk_count,
            content_length=len(doc.content),
            metadata=doc.metadata,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        )


class KnowledgeDocumentDetail(KnowledgeDocumentResponse):
    """Full response including the source content (for admin edit views)."""
    content: str


# ── Search schemas ─────────────────────────────────────────────────────────────

class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)
    min_similarity: float = Field(default=0.70, ge=0.0, le=1.0)
    access_scope: str = Field(
        default="PUBLIC",
        description="PUBLIC or STAFF_AND_PUBLIC"
    )


class KnowledgeSearchResult(BaseModel):
    document_id: uuid.UUID
    document_title: str
    source_type: str
    content: str
    similarity: float
    chunk_index: int


class KnowledgeSearchResponse(BaseModel):
    query: str
    total: int
    results: list[KnowledgeSearchResult]


# ── Reindex response ───────────────────────────────────────────────────────────

class ReindexResponse(BaseModel):
    document_id: uuid.UUID
    chunks_created: int
    embedding_status: str
    message: str
