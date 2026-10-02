"""
Knowledge Base API router.
/hospitals/{hid}/knowledge/documents  — document CRUD + reindex
/hospitals/{hid}/knowledge/search     — admin semantic search test
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser, HospitalPathDep
from app.core.pagination import Page, PaginationDep
from app.modules.knowledge.schemas import (
    KnowledgeDocumentCreate,
    KnowledgeDocumentDetail,
    KnowledgeDocumentResponse,
    KnowledgeDocumentUpdate,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    ReindexResponse,
)
from app.modules.knowledge.service import KnowledgeService

router = APIRouter(
    prefix="/hospitals/{hospital_id}/knowledge",
    tags=["Knowledge Base (RAG)"],
)


@router.post(
    "/documents",
    response_model=KnowledgeDocumentResponse,
    status_code=201,
    summary="Add knowledge document",
    description=(
        "**HOSPITAL_ADMIN or SUPER_ADMIN.** "
        "Add a document to the hospital's knowledge base. "
        "The document is automatically chunked and embedded using Google text-embedding-004. "
        "\n\n**Embedding status** will be `INDEXED` (success) or `FAILED` (check logs)."
        "\n\n**Access scopes:**\n"
        "- `PUBLIC` — AI can use to answer patient questions\n"
        "- `STAFF` — only returned in admin search, not AI-accessible\n"
        "- `INTERNAL` — admin only, not searchable\n\n"
        "**Available source types:** FAQ, POLICY, DOCTOR_PROFILE, PATIENT_INSTRUCTIONS, "
        "VISITING_HOURS, INSURANCE, CONTACT_INFO, GENERAL"
    ),
)
async def create_document(
    hospital_id: HospitalPathDep,
    payload: KnowledgeDocumentCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> KnowledgeDocumentResponse:
    return await KnowledgeService(db).create_document(hospital_id, payload, actor=current_user)


@router.get(
    "/documents",
    response_model=Page[KnowledgeDocumentResponse],
    summary="List knowledge documents",
    description="**STAFF or above.** Paginated list of knowledge documents for this hospital.",
)
async def list_documents(
    hospital_id: HospitalPathDep,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    params: PaginationDep,
    source_type: str | None = Query(default=None),
    access_scope: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
) -> Page[KnowledgeDocumentResponse]:
    return await KnowledgeService(db).list_documents(
        hospital_id, current_user, params=params,
        source_type=source_type, access_scope=access_scope, is_active=is_active,
    )


@router.get(
    "/documents/{document_id}",
    response_model=KnowledgeDocumentDetail,
    summary="Get document detail",
    description="**STAFF or above.** Full document including source content.",
)
async def get_document(
    hospital_id: HospitalPathDep,
    document_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> KnowledgeDocumentDetail:
    return await KnowledgeService(db).get_document(document_id, hospital_id, actor=current_user)


@router.patch(
    "/documents/{document_id}",
    response_model=KnowledgeDocumentResponse,
    summary="Update document",
    description=(
        "**HOSPITAL_ADMIN or SUPER_ADMIN.** Update document fields. "
        "If `content` is changed, the document is automatically re-indexed "
        "(old chunks deleted, new embeddings generated)."
    ),
)
async def update_document(
    hospital_id: HospitalPathDep,
    document_id: uuid.UUID,
    payload: KnowledgeDocumentUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> KnowledgeDocumentResponse:
    return await KnowledgeService(db).update_document(
        document_id, hospital_id, payload, actor=current_user
    )


@router.delete(
    "/documents/{document_id}",
    status_code=204,
    summary="Delete document",
    description=(
        "**HOSPITAL_ADMIN or SUPER_ADMIN.** "
        "Hard-delete a document and all its embedding chunks."
    ),
)
async def delete_document(
    hospital_id: HospitalPathDep,
    document_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await KnowledgeService(db).delete_document(document_id, hospital_id, actor=current_user)


@router.post(
    "/documents/{document_id}/reindex",
    response_model=ReindexResponse,
    summary="Reindex document",
    description=(
        "**HOSPITAL_ADMIN or SUPER_ADMIN.** "
        "Force-regenerate all embeddings for a document. "
        "Useful after embedding model upgrades or to fix FAILED status."
    ),
)
async def reindex_document(
    hospital_id: HospitalPathDep,
    document_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ReindexResponse:
    chunk_count = await KnowledgeService(db).reindex_document(
        document_id, hospital_id, actor=current_user
    )
    return ReindexResponse(
        document_id=document_id,
        chunks_created=chunk_count,
        embedding_status="INDEXED" if chunk_count > 0 else "FAILED",
        message=(
            f"Document reindexed with {chunk_count} chunks."
            if chunk_count > 0 else
            "Reindexing failed. Check GEMINI_API_KEY configuration."
        ),
    )


@router.post(
    "/search",
    response_model=KnowledgeSearchResponse,
    summary="Test semantic search",
    description=(
        "**STAFF or above.** "
        "Run a semantic similarity search against the knowledge base. "
        "This is the same search the AI runs when a patient asks a question. "
        "Use to verify retrieval quality before going live."
    ),
)
async def search_knowledge(
    hospital_id: HospitalPathDep,
    request: KnowledgeSearchRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> KnowledgeSearchResponse:
    return await KnowledgeService(db).search(hospital_id, request, actor=current_user)
