-- PostgreSQL initialization script for Luma Vaani
-- Runs once on first container start via docker-entrypoint-initdb.d
-- The pgvector extension is also enabled in migration 001, but we enable it
-- here too so the database is ready before Alembic runs.

-- Enable pgvector for semantic search / RAG (Phase 5)
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable uuid-ossp for uuid generation (gen_random_uuid is built-in in PG14+)
-- PostgreSQL 16 has gen_random_uuid() built-in, so this is optional.
-- CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Ensure the database is using UTF-8 (should already be, but explicit)
-- (Can't alter lc_collate after creation; rely on Docker env for locale)
