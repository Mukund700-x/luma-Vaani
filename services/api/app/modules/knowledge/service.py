"""
Knowledge service — document ingestion, indexing, and semantic search.

INGESTION PIPELINE per document:
  1. Validate and create KnowledgeDocument (embedding_status=PENDING)
  2. Chunk the content using the text chunker
  3. Generate embeddings for all chunks in batch (Gemini text-embedding-004)
  4. Store KnowledgeChunk records with embeddings
  5. Update KnowledgeDocument embedding_status=INDEXED

REINDEX pipeline (on document update):
  1. Delete existing chunks
  2. Re-run ingestion pipeline with new content

All operations are transactional — on embedding failure, status=FAILED is set
and existing chunks are preserved (or empty if first index attempt).
"""

import uuid
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.knowledge.chunker import chunk_text
from app.ai.knowledge.embeddings import EmbeddingService
from app.ai.knowledge.retriever import KnowledgeRetriever
from app.core.audit import AuditService
from app.core.config import settings
from app.core.enums import AuditActorType, UserRole
from app.core.exceptions import ForbiddenException, NotFoundException
from app.core.pagination import Page, PageParams
from app.modules.auth.models import User
from app.modules.knowledge.models import KnowledgeDocument
from app.modules.knowledge.repository import KnowledgeRepository
from app.modules.knowledge.schemas import (
    KnowledgeDocumentCreate,
    KnowledgeDocumentDetail,
    KnowledgeDocumentResponse,
    KnowledgeDocumentUpdate,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    KnowledgeSearchResult,
    ReindexResponse,
)

logger = structlog.get_logger(__name__)

_ADMIN_ROLES = {UserRole.SUPER_ADMIN, UserRole.HOSPITAL_ADMIN}
_STAFF_ROLES = {UserRole.SUPER_ADMIN, UserRole.HOSPITAL_ADMIN, UserRole.RECEPTIONIST, UserRole.DOCTOR}


class KnowledgeService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = KnowledgeRepository(db)
        self._audit = AuditService(db)

    def _embedding_svc(self) -> EmbeddingService:
        return EmbeddingService(api_key=settings.GEMINI_API_KEY or "")

    # ── Document CRUD ──────────────────────────────────────────────────────────

    async def create_document(
        self,
        hospital_id: uuid.UUID,
        payload: KnowledgeDocumentCreate,
        actor: User,
    ) -> KnowledgeDocumentResponse:
        if actor.role not in _ADMIN_ROLES:
            raise ForbiddenException("Admin access required to manage knowledge base")

        doc = await self._repo.create(
            hospital_id,
            title=payload.title,
            source_type=payload.source_type.value,
            access_scope=payload.access_scope.value,
            content=payload.content,
            language=payload.language,
            is_active=True,
            embedding_status="PENDING",
            metadata=payload.metadata,
            created_by=actor.id,
        )

        logger.info("knowledge_document_created", document_id=str(doc.id))

        # Run embedding pipeline (non-blocking attempt)
        chunk_count = await self._run_indexing(doc)

        await self._audit.log(
            action="knowledge.document.create",
            actor_type=AuditActorType.USER,
            actor_id=str(actor.id),
            hospital_id=hospital_id,
            resource_type="knowledge_document",
            resource_id=str(doc.id),
            after_state={"title": doc.title, "source_type": doc.source_type, "chunks": chunk_count},
        )

        return KnowledgeDocumentResponse.from_orm_with_stats(doc, chunk_count=chunk_count)

    async def update_document(
        self,
        document_id: uuid.UUID,
        hospital_id: uuid.UUID,
        payload: KnowledgeDocumentUpdate,
        actor: User,
    ) -> KnowledgeDocumentResponse:
        if actor.role not in _ADMIN_ROLES:
            raise ForbiddenException("Admin access required")

        doc = await self._repo.get_by_id(document_id, hospital_id)
        if not doc:
            raise NotFoundException("KnowledgeDocument", str(document_id))

        update_fields: dict[str, Any] = {}
        if payload.title is not None:
            update_fields["title"] = payload.title
        if payload.source_type is not None:
            update_fields["source_type"] = payload.source_type.value
        if payload.access_scope is not None:
            update_fields["access_scope"] = payload.access_scope.value
        if payload.language is not None:
            update_fields["language"] = payload.language
        if payload.is_active is not None:
            update_fields["is_active"] = payload.is_active
        if payload.metadata is not None:
            update_fields["metadata"] = payload.metadata

        content_changed = payload.content is not None and payload.content != doc.content
        if content_changed:
            update_fields["content"] = payload.content
            update_fields["embedding_status"] = "PENDING"

        updated = await self._repo.update(document_id, hospital_id, update_fields)

        chunk_count = await self._repo.get_chunk_count(document_id)
        if content_changed:
            chunk_count = await self.reindex_document(document_id, hospital_id, actor)
        
        return KnowledgeDocumentResponse.from_orm_with_stats(updated, chunk_count=chunk_count)

    async def delete_document(
        self,
        document_id: uuid.UUID,
        hospital_id: uuid.UUID,
        actor: User,
    ) -> None:
        if actor.role not in _ADMIN_ROLES:
            raise ForbiddenException("Admin access required")
        deleted = await self._repo.delete(document_id, hospital_id)
        if not deleted:
            raise NotFoundException("KnowledgeDocument", str(document_id))

    async def get_document(
        self,
        document_id: uuid.UUID,
        hospital_id: uuid.UUID,
        actor: User,
    ) -> KnowledgeDocumentDetail:
        if actor.role not in _STAFF_ROLES:
            raise ForbiddenException("Staff access required")
        doc = await self._repo.get_by_id(document_id, hospital_id)
        if not doc:
            raise NotFoundException("KnowledgeDocument", str(document_id))
        chunk_count = await self._repo.get_chunk_count(document_id)
        base = KnowledgeDocumentResponse.from_orm_with_stats(doc, chunk_count=chunk_count)
        return KnowledgeDocumentDetail(**base.model_dump(), content=doc.content)

    async def list_documents(
        self,
        hospital_id: uuid.UUID,
        actor: User,
        *,
        params: PageParams,
        source_type: str | None = None,
        access_scope: str | None = None,
        is_active: bool | None = None,
    ) -> Page[KnowledgeDocumentResponse]:
        if actor.role not in _STAFF_ROLES:
            raise ForbiddenException("Staff access required")
        items, total = await self._repo.list(
            hospital_id,
            source_type=source_type,
            access_scope=access_scope,
            is_active=is_active,
            limit=params.size,
            offset=params.offset,
        )
        return Page.create(
            [KnowledgeDocumentResponse.from_orm_with_stats(d) for d in items],
            total, params,
        )

    # ── Indexing ───────────────────────────────────────────────────────────────

    async def reindex_document(
        self,
        document_id: uuid.UUID,
        hospital_id: uuid.UUID,
        actor: User,
    ) -> int:
        """Delete existing chunks and regenerate embeddings. Returns chunk count."""
        if actor.role not in _ADMIN_ROLES:
            raise ForbiddenException("Admin access required")

        doc = await self._repo.get_by_id(document_id, hospital_id)
        if not doc:
            raise NotFoundException("KnowledgeDocument", str(document_id))

        await self._repo.delete_chunks_for_document(document_id)
        await self._repo.update(document_id, hospital_id, {"embedding_status": "PENDING"})
        await self._db.flush()

        return await self._run_indexing(doc)

    async def _run_indexing(self, doc: KnowledgeDocument) -> int:
        """
        Core indexing pipeline:
          1. Chunk content
          2. Generate embeddings in batch
          3. Store chunks with embeddings
          4. Update document status
        Returns number of chunks created.
        """
        emb_svc = self._embedding_svc()
        if not emb_svc.is_available:
            logger.warning("embeddings_not_available_skipping_index", document_id=str(doc.id))
            await self._repo.update(doc.id, doc.hospital_id, {"embedding_status": "FAILED"})
            return 0

        try:
            # Step 1: Chunk
            raw_chunks = chunk_text(
                doc.content,
                chunk_size=settings.KNOWLEDGE_CHUNK_SIZE,
                chunk_overlap=settings.KNOWLEDGE_CHUNK_OVERLAP,
            )
            if not raw_chunks:
                logger.warning("no_chunks_generated", document_id=str(doc.id))
                await self._repo.update(doc.id, doc.hospital_id, {"embedding_status": "FAILED"})
                return 0

            # Step 2: Embed in batch
            texts = [c.content for c in raw_chunks]
            embeddings = await emb_svc.embed_documents_batch(texts)

            # Step 3: Store chunks
            chunk_data = []
            for raw, emb in zip(raw_chunks, embeddings):
                chunk_data.append({
                    "chunk_index": raw.chunk_index,
                    "content": raw.content,
                    "token_count": raw.token_count,
                    "embedding": emb,
                })

            await self._repo.create_chunks(
                hospital_id=doc.hospital_id,
                document_id=doc.id,
                access_scope=doc.access_scope,
                source_type=doc.source_type,
                chunk_data=chunk_data,
            )

            # Step 4: Mark INDEXED
            await self._repo.update(doc.id, doc.hospital_id, {"embedding_status": "INDEXED"})

            logger.info(
                "document_indexed",
                document_id=str(doc.id),
                chunks=len(chunk_data),
                source_type=doc.source_type,
            )
            return len(chunk_data)

        except Exception as exc:
            logger.exception("document_indexing_failed", document_id=str(doc.id), error=str(exc))
            await self._repo.update(doc.id, doc.hospital_id, {"embedding_status": "FAILED"})
            return 0

    # ── Semantic search (admin test) ───────────────────────────────────────────

    async def search(
        self,
        hospital_id: uuid.UUID,
        request: KnowledgeSearchRequest,
        actor: User,
    ) -> KnowledgeSearchResponse:
        """Admin semantic search endpoint for testing retrieval quality."""
        if actor.role not in _STAFF_ROLES:
            raise ForbiddenException("Staff access required")

        emb_svc = self._embedding_svc()
        retriever = KnowledgeRetriever(
            db=self._db,
            embedding_service=emb_svc,
            top_k=request.top_k,
            min_similarity=request.min_similarity,
        )
        results = await retriever.search(
            hospital_id=hospital_id,
            query=request.query,
            access_scope=request.access_scope,  # type: ignore[arg-type]
        )

        return KnowledgeSearchResponse(
            query=request.query,
            total=len(results),
            results=[
                KnowledgeSearchResult(
                    document_id=r.document_id,
                    document_title=r.document_title,
                    source_type=r.source_type,
                    content=r.content,
                    similarity=r.similarity,
                    chunk_index=r.chunk_index,
                )
                for r in results
            ],
        )
