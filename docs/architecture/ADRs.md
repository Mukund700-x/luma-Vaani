# ADR-001: Modular Monolith Architecture

**Status:** Accepted  
**Date:** 2026-10-02  
**Deciders:** Engineering team

---

## Context

Luma Vaani must serve multiple hospitals (multi-tenant) with features spanning:
authentication, appointment scheduling, AI conversation, RAG, notifications, and
voice interfaces. There is temptation to design this as microservices from day one.

## Decision

Start as a **modular monolith**.

- Single FastAPI application in `services/api/`
- Clear internal module boundaries (auth, hospitals, departments, doctors, patients, schedules, appointments, conversations, knowledge, notifications, safety)
- Each module owns its own models, repository, service, schemas, and router
- Modules communicate through service layer calls, never direct DB cross-queries
- Workers run as separate Node.js processes (BullMQ) communicating via Redis queues

## Consequences

**Positive:**
- Simpler deployment and local development
- Easier debugging and distributed tracing within a single process
- No network latency between modules
- Straightforward database transactions across module boundaries
- Can extract specific modules into microservices later if load demands it

**Negative:**
- Horizontal scaling requires scaling the entire API (acceptable at this stage)
- Module isolation is enforced by convention, not by network boundaries

## Future Migration Path

If a specific module (e.g., AI conversations) needs independent scaling:
1. Extract the module's service layer into its own FastAPI app
2. Replace in-process calls with HTTP/gRPC
3. The existing module boundary makes this mechanical

---

# ADR-002: Tenant Isolation Strategy

**Status:** Accepted  
**Date:** 2026-10-02

## Decision

Every hospital-owned entity carries a `hospital_id` UUID foreign key.

Rules enforced at the **repository layer**:
1. Every `SELECT` query on tenant-owned tables must include `WHERE hospital_id = :hospital_id`
2. Every `INSERT` must set `hospital_id` from the authenticated user's context, never from request body alone
3. `SUPER_ADMIN` users (hospital_id = NULL) may query across tenants for platform management only
4. Cross-tenant queries are never permitted for patient data, appointments, or clinical records

Tenant violations raise `TenantException` (HTTP 403).

## Enforcement

- Repository methods accept `hospital_id` as a required parameter (not optional)
- The `require_hospital_access` dependency validates path-level hospital_id against the JWT
- Integration tests verify that tenant A cannot access tenant B's data

---

# ADR-003: AI Tool Boundary

**Status:** Accepted  
**Date:** 2026-10-02

## Decision

The AI (LLM) must NEVER directly access PostgreSQL or any internal data store.

The boundary is enforced as follows:

```
LLM
  ↓  structured tool call (JSON)
AI Tool Layer  (ai/tools/)
  ↓  typed service call
Service Layer  (app/modules/*/service.py)
  ↓  repository call with tenant enforcement
Repository Layer  (app/modules/*/repository.py)
  ↓  parameterized SQL
PostgreSQL
```

Each tool in `ai/tools/` must:
1. Have a fully typed `ToolInput` and `ToolOutput` Pydantic model
2. Perform authorization checks (hospital_id, role, resource ownership)
3. Log every invocation to audit_logs
4. Return structured, sanitized output — never raw ORM objects or SQL results
5. Raise `ForbiddenException` for prohibited operations

**Prohibited tool operations (hardcoded, not configurable):**
- `diagnosis`
- `prescribe_medication`
- `modify_clinical_record`
- `emergency_override`
- Any direct database access

## RAG Caveat

RAG retrieval results are **untrusted data**. They must:
- Be clearly delimited in the prompt with `[RETRIEVED_DOCUMENT: {doc_id}]` markers
- Never be used for transactional decisions (appointment availability, billing)
- Be sanitized for prompt injection before inclusion

Real-time availability ALWAYS comes from the Scheduling Engine, not RAG.
