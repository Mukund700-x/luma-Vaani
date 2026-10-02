"""007 knowledge — knowledge_documents and knowledge_chunks tables with pgvector

Revision ID: 007
Revises: 006
Create Date: 2026-10-02

IMPORTANT: Requires pgvector extension (already enabled in migration 001).
           IVFFlat index requires at least 1000 rows for optimal performance;
           for smaller datasets, ivfflat lists=1 is fine.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None

EMBEDDING_DIM = 768


def upgrade() -> None:
    # pgvector must be enabled (migration 001 handles this via CREATE EXTENSION IF NOT EXISTS vector)
    
    # ── knowledge_documents ────────────────────────────────────────────────────
    op.create_table(
        "knowledge_documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("hospital_id", UUID(as_uuid=True), sa.ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        # DocumentSourceType: FAQ, POLICY, DOCTOR_PROFILE, PATIENT_INSTRUCTIONS,
        #   VISITING_HOURS, INSURANCE, CONTACT_INFO, GENERAL
        sa.Column("source_type", sa.String(50), nullable=False, server_default="GENERAL"),
        # DocumentAccessScope: PUBLIC, STAFF, INTERNAL
        sa.Column("access_scope", sa.String(20), nullable=False, server_default="PUBLIC"),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        # PENDING, INDEXED, FAILED
        sa.Column("embedding_status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("metadata", JSONB, nullable=False, server_default="{}"),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_knowledge_docs_hospital_id", "knowledge_documents", ["hospital_id"])
    op.create_index("ix_knowledge_docs_source_type", "knowledge_documents", ["source_type"])
    op.create_index("ix_knowledge_docs_hospital_scope", "knowledge_documents", ["hospital_id", "access_scope"])
    op.execute("""
        CREATE TRIGGER trg_knowledge_documents_updated_at
        BEFORE UPDATE ON knowledge_documents
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)

    # ── knowledge_chunks ───────────────────────────────────────────────────────
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("hospital_id", UUID(as_uuid=True), sa.ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False),
        # Denormalised from parent document for filtered vector queries
        sa.Column("access_scope", sa.String(20), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("token_count", sa.Integer, nullable=False, server_default="0"),
        # pgvector embedding column — 768 dims for text-embedding-004
        sa.Column("embedding", sa.Text, nullable=True),  # overridden below with ALTER
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    # Add proper vector column type (ALTER TABLE — Alembic doesn't natively support vector)
    op.execute(f"""
        ALTER TABLE knowledge_chunks
        ALTER COLUMN embedding TYPE vector({EMBEDDING_DIM})
        USING NULL::vector({EMBEDDING_DIM});
    """)

    op.create_index("ix_knowledge_chunks_document_id", "knowledge_chunks", ["document_id"])
    op.create_index("ix_knowledge_chunks_hospital_scope", "knowledge_chunks", ["hospital_id", "access_scope"])

    # IVFFlat approximate nearest-neighbour index for cosine similarity
    # lists=100 is suitable for up to ~100k chunks; increase for larger datasets
    op.execute(f"""
        CREATE INDEX ix_knowledge_chunks_embedding_ivfflat
        ON knowledge_chunks
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100);
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_knowledge_documents_updated_at ON knowledge_documents")
    op.execute("DROP INDEX IF EXISTS ix_knowledge_chunks_embedding_ivfflat")
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_documents")
