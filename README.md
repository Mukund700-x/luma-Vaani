# Luma Vaani

**AI-powered hospital front-desk & patient-access platform.**

> AI handles conversation. Backend handles truth. Hospital controls clinical policy.

---

## Overview

Luma Vaani is a multi-tenant healthcare platform that provides:

- AI chat (and future voice) receptionist for patients
- Real-time appointment booking, cancellation, and rescheduling
- Multi-lingual conversation (Hindi, English, regional languages)
- Hospital knowledge retrieval via RAG
- Emergency escalation via hospital-approved protocols
- Admin dashboard for hospital staff

---

## Repository Structure

```
luma-vaani/
├── apps/
│   └── web/              # Next.js patient portal + admin dashboard
├── services/
│   └── api/              # FastAPI backend (Python)
├── packages/
│   ├── types/            # Shared TypeScript API types
│   └── config/           # Shared ESLint / TS / Prettier config
├── ai/
│   ├── prompts/          # Versioned prompt templates
│   ├── tools/            # AI tool definitions
│   ├── rag/              # Retrieval logic
│   ├── evaluation/       # AI eval datasets
│   └── safety/           # Guardrails and triage rules
├── workers/
│   ├── notifications/    # BullMQ notification worker
│   ├── reminders/        # BullMQ reminder worker
│   ├── rag-ingestion/    # Document processing worker
│   └── integrations/     # External system sync worker
├── database/
│   ├── migrations/       # Alembic migration files
│   └── seed/             # Development seed data
├── docs/                 # Architecture docs, ADRs
├── tests/                # E2E tests
└── infrastructure/       # Docker, future IaC
```

---

## Quick Start (Development)

### Prerequisites

- Docker & Docker Compose
- Python 3.12+
- Node.js 20+
- pnpm 9+

### 1. Clone and configure

```bash
cp .env.example .env
# Edit .env and fill in JWT_SECRET_KEY (openssl rand -hex 32) and AI keys
```

### 2. Start infrastructure

```bash
docker-compose up postgres redis -d
```

### 3. Run backend

```bash
cd services/api
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

### 4. Run frontend

```bash
cd apps/web
pnpm install
pnpm dev
```

### 5. Run full stack via Docker

```bash
docker-compose up
```

API docs: http://localhost:8000/docs  
Frontend: http://localhost:3000

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14, TypeScript, Tailwind CSS |
| Backend | FastAPI, Python 3.12, Pydantic v2, SQLAlchemy 2.0 (async) |
| Database | PostgreSQL 16 + pgvector |
| Cache / Queue | Redis 7, BullMQ (Node.js workers) |
| Auth | JWT (access + refresh tokens) |
| AI | Provider-agnostic AI Gateway (Gemini / OpenAI / Anthropic) |
| Migrations | Alembic |

---

## Core Principles

1. **AI handles conversation. Backend handles truth. Hospital controls clinical policy.**
2. The AI must never directly access the database.
3. Every hospital-owned entity is tenant-scoped by `hospital_id`.
4. Appointment availability comes only from the scheduling engine, never from LLM memory.
5. All AI tool actions pass through backend authorization and validation.

---

## Development Phases

| Phase | Goal |
|---|---|
| 1 (current) | Foundation: auth, multi-tenancy, API skeleton, frontend skeleton |
| 2 | Hospital core: hospitals, departments, doctors, patients, schedules |
| 3 | Scheduling engine: availability, booking, cancellation, rescheduling |
| 4 | AI chat receptionist: gateway, tool calling, patient chat UI |
| 5 | RAG: document ingestion, pgvector, hospital knowledge |
| 6 | Background jobs: BullMQ, notifications, reminders |
| 7+ | Voice, safety engine, integrations, pilot |
