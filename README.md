# 💙 Luma Vaani — AI-Powered Hospital Front Desk Platform

<div align="center">

**Production-grade, multi-tenant hospital AI that speaks to patients through Chat, Voice, and WhatsApp.**

[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue?logo=python)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green?logo=fastapi)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+pgvector-336791?logo=postgresql)](https://www.postgresql.org)
[![Gemini](https://img.shields.io/badge/AI-Gemini%201.5%20Flash-4285F4?logo=google)](https://ai.google.dev)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

</div>

---

## 🏥 What is Luma Vaani?

Luma Vaani is an **AI-powered hospital front-desk and patient-access platform**. It replaces the traditional phone/reception workflow with an intelligent conversational interface available 24/7 across multiple channels.

```
Patient
  → talks via Chat / Voice / WhatsApp
  → AI identifies department using hospital-approved rules
  → checks REAL doctor availability from the backend
  → presents appointment slots
  → patient books, cancels, or reschedules
  → automated confirmations sent via SMS + WhatsApp + Email
```

**Core principle:** *AI handles conversation. Backend handles truth. Hospital controls clinical policy.*

---

## ✨ Features

| Category | Capability |
|---|---|
| 🤖 **AI Engine** | Gemini 1.5 Flash with 8 structured tools (book, cancel, reschedule, search, retrieve knowledge) |
| 🔍 **RAG Knowledge** | Semantic search over hospital FAQs, policies, visiting hours via pgvector |
| 📅 **Scheduling** | Real-time availability engine, timezone-aware, conflict detection |
| 🔔 **Notifications** | SMS + WhatsApp + Email via Twilio & SMTP, 12 default templates, background worker |
| 🏨 **Multi-Tenant** | Complete data isolation per hospital — no cross-tenant data access possible |
| 🛡️ **Safety Layer** | Zero-latency emergency detection bypasses LLM entirely |
| 🔐 **Auth** | JWT + refresh tokens, RBAC (SUPER_ADMIN, HOSPITAL_ADMIN, DOCTOR, RECEPTIONIST, PATIENT) |
| 📋 **Audit Trail** | Immutable audit log for all state changes — PHI never logged |
| 🐳 **Production-Ready** | Docker, non-root container, healthchecks, structured logging, rate limiting |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Luma Vaani API                           │
│                                                                 │
│  FastAPI ─── Auth (JWT/RBAC)                                    │
│    │                                                            │
│    ├── Hospital Core (hospitals, departments, doctors, patients) │
│    ├── Scheduling (AvailabilityEngine, appointments)            │
│    ├── AI Conversations ──── Gemini Gateway                     │
│    │       │                      │                            │
│    │       ├── SafetyLayer         └── ToolRegistry (8 tools)   │
│    │       └── RAG Context ──── KnowledgeRetriever              │
│    │                                      │                    │
│    ├── Knowledge Base ──── pgvector ──── text-embedding-004     │
│    └── Notifications ─── SMS/WhatsApp (Twilio) + Email (SMTP)  │
│                               │                                │
│                        Background Worker (asyncio)              │
│                      (reminder scheduling, retry)               │
└─────────────────────────────────────────────────────────────────┘
         │                    │                    │
    PostgreSQL 16          Redis 7             Gemini API
    + pgvector         (rate limiting)     (Flash + Embeddings)
```

### AI Conversation Pipeline (14 steps per turn)

```
User message
  ├─1─ Rate limit check
  ├─2─ Conversation turn limit guard
  ├─3─ Load hospital (tenant isolation)
  ├─4─ Safety check → [EMERGENCY → bypass LLM, zero-latency response]
  ├─5─ Persist patient message
  ├─6─ Build system prompt
  ├─6b─ RAG retrieval → inject hospital knowledge context
  ├─7─ Load conversation history
  ├─8─ Build ToolContext (patient_id server-side, never in LLM prompt)
  ├─9─ Gemini agentic loop (tool call → execute → iterate)
  ├─10─ Output safety check
  ├─11─ Persist AI response
  ├─12─ Persist all tool calls (audit)
  └─13─ Return AITurnResponse
```

---

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Google Gemini API key ([Get one here](https://ai.google.dev))

### 1. Clone & configure

```bash
git clone https://github.com/your-org/luma-vaani.git
cd luma-vaani
cp .env.example .env
# Edit .env — at minimum set GEMINI_API_KEY, JWT_SECRET_KEY
```

### 2. Start the stack

```bash
docker compose up --build
```

### 3. Run migrations

```bash
docker compose run --rm migrate
```

### 4. Open API docs

```
http://localhost:8000/docs        ← Swagger UI
http://localhost:8000/redoc       ← ReDoc
http://localhost:8080             ← Database Admin (Adminer)
```

---

## 📁 Project Structure

```
luma-vaani/
├── services/api/                  # FastAPI backend
│   ├── app/
│   │   ├── api/v1/router.py      # Route aggregator
│   │   ├── core/                 # Config, auth, database, exceptions
│   │   ├── ai/                   # AI engine
│   │   │   ├── gateway/          # Gemini gateway (agentic loop)
│   │   │   ├── tools/            # 8 AI tools (book, cancel, search…)
│   │   │   ├── safety/           # Emergency detection safety layer
│   │   │   ├── prompts/          # System prompt builder
│   │   │   └── knowledge/        # RAG: chunker, embeddings, retriever
│   │   └── modules/              # Feature modules
│   │       ├── auth/             # JWT auth, users
│   │       ├── hospitals/        # Hospital CRUD
│   │       ├── departments/      # Departments + routing rules
│   │       ├── doctors/          # Doctor profiles
│   │       ├── patients/         # Patient records (PHI-isolated)
│   │       ├── schedules/        # Doctor schedules + AvailabilityEngine
│   │       ├── appointments/     # Booking, cancel, reschedule
│   │       ├── conversations/    # AI conversation sessions
│   │       ├── knowledge/        # Knowledge base documents (RAG)
│   │       └── notifications/    # SMS/WhatsApp/Email + worker
│   ├── alembic/                  # Database migrations (001–007)
│   ├── Dockerfile                # Multi-stage (dev + production)
│   └── pyproject.toml
├── docker-compose.yml            # Full local stack
├── .env.example                  # All environment variables documented
└── docs/                         # Architecture docs
```

---

## 🔌 API Reference

### Core Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/auth/login` | Obtain JWT tokens |
| `POST` | `/api/v1/auth/refresh` | Refresh access token |
| `GET` | `/api/v1/hospitals/{hid}/doctors` | List doctors with filters |
| `GET` | `/api/v1/hospitals/{hid}/doctors/{did}/availability` | Real-time availability |
| `POST` | `/api/v1/hospitals/{hid}/appointments` | Book appointment |
| `POST` | `/api/v1/hospitals/{hid}/conversations` | Start AI conversation |
| `POST` | `/api/v1/hospitals/{hid}/conversations/{cid}/messages` | Send message to AI |
| `GET` | `/api/v1/hospitals/{hid}/notifications` | Notification history |
| `POST` | `/api/v1/hospitals/{hid}/knowledge/documents` | Add knowledge document |
| `POST` | `/api/v1/hospitals/{hid}/knowledge/search` | Test semantic search |

### AI Tools (8 tools available to Gemini)

| Tool | Purpose |
|---|---|
| `find_patient` | Lookup patient by phone/ID |
| `search_doctors` | Filter doctors by specialization/dept |
| `get_availability` | Real-time slot availability |
| `book_appointment` | Create a booking |
| `get_patient_appointments` | View upcoming appointments |
| `cancel_appointment` | Cancel with reason |
| `get_hospital_info` | Hospital details, departments, hours |
| `search_hospital_knowledge` | Semantic RAG search over hospital documents |

---

## ⚙️ Configuration

All config is via environment variables. See [`.env.example`](.env.example) for full documentation.

### Critical variables

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/lumadb

# Security (generate strong secrets for production)
JWT_SECRET_KEY=your-256-bit-secret
JWT_REFRESH_SECRET_KEY=your-other-256-bit-secret

# AI (required for all AI features)
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-1.5-flash

# Notifications (optional — uses stub provider if not set)
TWILIO_ACCOUNT_SID=ACxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxx
TWILIO_SMS_FROM=+919876543210
TWILIO_WHATSAPP_FROM=+919876543210

# SMTP Email
SMTP_HOST=smtp.gmail.com
SMTP_USER=noreply@yourhospital.com
SMTP_PASSWORD=app-password
```

---

## 🛡️ Security Architecture

- **PHI isolation**: Patient PII (phone, email) is never written to audit logs
- **Tenant isolation**: Every query is scoped by `hospital_id` — cross-tenant access is impossible at the SQL level
- **Patient ID server-side**: `patient_id` is never passed to the LLM — resolved from the session server-side
- **Emergency bypass**: SafetyLayer detects emergencies before the LLM is invoked (zero-latency)
- **Non-root container**: Production Docker image runs as `lumauser`, not root
- **RAG scope**: Only `PUBLIC`-scoped documents are AI-accessible; `STAFF`/`INTERNAL` never reach the LLM

---

## 🗄️ Database Migrations

```bash
# Apply all pending migrations
alembic upgrade head

# Create a new migration
alembic revision --autogenerate -m "your_description"

# Rollback one migration
alembic downgrade -1

# Check current revision
alembic current
```

**Migration chain:** `001_initial` → `002_hospital_core` → `003_scheduling` → `004_appointments` → `005_conversations` → `006_notifications` → `007_knowledge`

---

## 📬 Notification System

Luma Vaani sends automated notifications on key events:

| Event | SMS | WhatsApp | Email |
|---|---|---|---|
| Appointment confirmed | ✅ | ✅ | ✅ |
| Reminder (24h before) | ✅ | ✅ | — |
| Reminder (2h before) | ✅ | ✅ | — |
| Appointment cancelled | ✅ | ✅ | ✅ |
| Appointment rescheduled | ✅ | ✅ | — |

Templates are fully customisable per hospital via the admin API. See `POST /hospitals/{hid}/notification-templates`.

---

## 🧠 Knowledge Base (RAG)

Add hospital-specific content to ground the AI in facts:

```bash
# Seed a FAQ document
POST /api/v1/hospitals/{hid}/knowledge/documents
{
  "title": "Visiting Hours",
  "source_type": "VISITING_HOURS",
  "access_scope": "PUBLIC",
  "content": "General Ward: 10am–12pm, 5pm–7pm daily..."
}
```

The document is automatically chunked and embedded. The AI will use it to answer patient questions without hallucinating.

Test retrieval quality:
```bash
POST /api/v1/hospitals/{hid}/knowledge/search
{ "query": "can I visit my father tonight?", "top_k": 3 }
```

---

## 🧪 Running Tests

```bash
cd services/api
pip install -e ".[dev]"
pytest tests/ -v --cov=app --cov-report=term-missing
```

---

## 📄 License

MIT © Luma Vaani Team
