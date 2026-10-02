"""
Knowledge repository — tenant-scoped data access.
"""

import uuid
from typing import Any

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.knowledge.models import KnowledgeChunk, KnowledgeDocument


class KnowledgeRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Documents ──────────────────────────────────────────────────────────────

    async def get_by_id(
        self, document_id: uuid.UUID, hospital_id: uuid.UUID
    ) -> KnowledgeDocument | None:
        result = await self._db.execute(
            select(KnowledgeDocument).where(
                and_(
                    KnowledgeDocument.id == document_id,
                    KnowledgeDocument.hospital_id == hospital_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        hospital_id: uuid.UUID,
        *,
        source_type: str | None = None,
        access_scope: str | None = None,
        is_active: bool | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[KnowledgeDocument], int]:
        base_q = select(KnowledgeDocument).where(
            KnowledgeDocument.hospital_id == hospital_id
        )
        if source_type:
            base_q = base_q.where(KnowledgeDocument.source_type == source_type.upper())
        if access_scope:
            base_q = base_q.where(KnowledgeDocument.access_scope == access_scope.upper())
        if is_active is not None:
            base_q = base_q.where(KnowledgeDocument.is_active == is_active)

        count_q = select(func.count()).select_from(base_q.subquery())
        total: int = (await self._db.execute(count_q)).scalar_one()
        items_q = (
            base_q.order_by(KnowledgeDocument.created_at.desc())
            .limit(limit).offset(offset)
        )
        items = list((await self._db.execute(items_q)).scalars().all())
        return items, total

    async def create(self, hospital_id: uuid.UUID, **fields: Any) -> KnowledgeDocument:
        doc = KnowledgeDocument(hospital_id=hospital_id, **fields)
        self._db.add(doc)
        await self._db.flush()
        await self._db.refresh(doc)
        return doc

    async def update(
        self,
        document_id: uuid.UUID,
        hospital_id: uuid.UUID,
        fields: dict[str, Any],
    ) -> KnowledgeDocument | None:
        await self._db.execute(
            update(KnowledgeDocument)
            .where(
                and_(
                    KnowledgeDocument.id == document_id,
                    KnowledgeDocument.hospital_id == hospital_id,
                )
            )
            .values(**fields)
        )
        return await self.get_by_id(document_id, hospital_id)

    async def delete(self, document_id: uuid.UUID, hospital_id: uuid.UUID) -> bool:
        doc = await self.get_by_id(document_id, hospital_id)
        if not doc:
            return False
        await self._db.delete(doc)
        return True

    # ── Chunks ─────────────────────────────────────────────────────────────────

    async def delete_chunks_for_document(self, document_id: uuid.UUID) -> int:
        """Delete all chunks for a document (before reindexing)."""
        result = await self._db.execute(
            select(KnowledgeChunk).where(KnowledgeChunk.document_id == document_id)
        )
        chunks = result.scalars().all()
        count = len(chunks)
        for chunk in chunks:
            await self._db.delete(chunk)
        return count

    async def create_chunks(
        self,
        hospital_id: uuid.UUID,
        document_id: uuid.UUID,
        access_scope: str,
        source_type: str,
        chunk_data: list[dict[str, Any]],
    ) -> list[KnowledgeChunk]:
        """Bulk-create embedding chunks for a document."""
        chunks = []
        for data in chunk_data:
            chunk = KnowledgeChunk(
                hospital_id=hospital_id,
                document_id=document_id,
                access_scope=access_scope,
                source_type=source_type,
                **data,
            )
            self._db.add(chunk)
            chunks.append(chunk)
        await self._db.flush()
        return chunks

    async def get_chunk_count(self, document_id: uuid.UUID) -> int:
        result = await self._db.execute(
            select(func.count()).where(KnowledgeChunk.document_id == document_id)
        )
        return result.scalar_one() or 0
