# HealLink --- AI-Powered Hospital Front Desk & Appointment Platform

**Document Type:** Product + Technical Specification\
**Status:** Initial Engineering Specification / MVP Blueprint\
**Working Product Name:** HealLink\
**Primary Goal:** Build a hospital-grade, multilingual AI front-desk and
appointment orchestration platform.

------------------------------------------------------------------------

## 1. Executive Summary

HealLink is a healthcare operations platform designed to reduce friction
between patients and hospital front desks.

Today, many patients still need to:

-   stand in long registration/appointment queues,
-   call repeatedly to find doctor availability,
-   depend on reception staff for routine questions,
-   manage appointments through paper/manual workflows,
-   struggle with language barriers,
-   wait unnecessarily when schedules change,
-   have difficulty getting the correct hospital pathway during urgent
    situations.

HealLink provides a unified digital front desk through:

-   AI voice receptionist,
-   web application,
-   future WhatsApp integration,
-   multilingual conversation,
-   appointment discovery and booking,
-   doctor/department routing,
-   hospital knowledge retrieval,
-   reminders and notifications,
-   emergency escalation according to hospital-defined protocols,
-   hospital administration dashboard,
-   integration APIs for existing hospital systems.

### Core product principle

> **HealLink is an AI-powered hospital front desk, not an autonomous
> doctor.**

The AI may understand symptoms and requests to determine the appropriate
workflow, but it must not independently diagnose disease, prescribe
treatment, or override hospital clinical/emergency protocols.

------------------------------------------------------------------------

# 2. Product Vision

## Vision

Make accessing hospital services as simple as having a conversation.

A patient should be able to say:

> "Mujhe kal doctor ko dikhana hai."

and HealLink should be able to:

1.  understand the language,
2.  understand the user's intent,
3.  collect only the information required,
4.  determine the appropriate hospital-defined routing path,
5.  check real-time availability,
6.  present available slots,
7.  obtain confirmation,
8.  create the appointment,
9.  send confirmation,
10. escalate to a human when necessary.

## Long-term vision

HealLink should evolve from an appointment assistant into a complete
**AI hospital front-desk operating layer** connecting patients, doctors,
reception staff, hospital administrators, and existing hospital
information systems.

------------------------------------------------------------------------

# 3. Problem Statement

## Patient problems

-   Long registration queues.
-   Manual appointment booking.
-   Paper-based appointment records in some environments.
-   Difficulty finding doctor availability.
-   Language barriers.
-   Repeated phone calls.
-   Difficulty rescheduling/cancelling appointments.
-   Lack of appointment reminders.
-   Confusion about departments and hospital services.
-   Unclear escalation path for potentially urgent symptoms.

## Hospital problems

-   High reception workload.
-   Repetitive phone calls.
-   Manual data entry.
-   Appointment scheduling inefficiencies.
-   No-shows.
-   Fragmented patient communication.
-   Inconsistent information provided by different staff members.
-   Limited after-hours support.
-   Difficulty scaling reception operations.

## Product opportunity

Automate routine administrative communication while keeping clinical and
emergency decisions under controlled hospital-defined workflows.

------------------------------------------------------------------------

# 4. Target Users

## 4.1 Patient

Needs:

-   appointment booking,
-   doctor search,
-   department guidance,
-   hospital information,
-   cancellation/rescheduling,
-   reminders,
-   multilingual communication.

## 4.2 Receptionist

Needs:

-   appointment management,
-   patient lookup,
-   manual booking,
-   AI conversation visibility,
-   escalation handling,
-   queue management.

## 4.3 Doctor

Needs:

-   schedule management,
-   appointment visibility,
-   availability control,
-   patient appointment context,
-   notifications.

## 4.4 Hospital Administrator

Needs:

-   hospital configuration,
-   doctor management,
-   departments,
-   schedules,
-   appointment analytics,
-   AI configuration,
-   escalation monitoring,
-   audit logs.

## 4.5 Platform Super Admin

Needs:

-   hospital onboarding,
-   tenant management,
-   subscription/billing controls,
-   platform analytics,
-   system health,
-   security controls.

------------------------------------------------------------------------

# 5. Product Scope

## MVP

The MVP must support:

-   hospital registration/configuration,
-   department management,
-   doctor management,
-   doctor schedules,
-   patient registration,
-   appointment booking,
-   cancellation,
-   rescheduling,
-   appointment availability,
-   web-based patient experience,
-   admin dashboard,
-   AI chat receptionist,
-   basic multilingual support,
-   RAG-based hospital information retrieval,
-   function/tool calling,
-   notification jobs,
-   audit logs,
-   role-based access control.

## Phase 2

-   AI voice receptionist,
-   WhatsApp integration,
-   advanced multilingual voice,
-   appointment reminders,
-   queue/token management,
-   patient follow-up workflows,
-   analytics dashboard.

## Phase 3

-   hospital-system integrations,
-   FHIR/HL7 interoperability where applicable,
-   advanced agentic workflows,
-   document ingestion,
-   hospital-specific knowledge bases,
-   advanced reporting.

## Future

-   laboratory booking,
-   pharmacy workflows,
-   billing integration,
-   insurance workflows,
-   patient document management,
-   patient history workflows,
-   doctor follow-up automation,
-   multi-hospital networks.

------------------------------------------------------------------------

# 6. Explicit Non-Goals

The initial product must NOT:

-   diagnose patients,
-   prescribe medicines,
-   recommend medication dosages,
-   replace doctors,
-   autonomously make clinical decisions,
-   override emergency protocols,
-   fabricate doctor availability,
-   fabricate hospital policies,
-   modify clinical records without authorized workflow,
-   book an appointment without required confirmation,
-   expose patient information to unauthorized users.

------------------------------------------------------------------------

# 7. Core User Journey

## Normal appointment

``` text
Patient
  |
  v
Web / Voice / Future WhatsApp
  |
  v
AI Receptionist
  |
  v
Intent Detection
  |
  v
Collect Required Information
  |
  v
Hospital Routing Rules
  |
  v
Department / Doctor Discovery
  |
  v
Scheduling Engine
  |
  v
Real-Time Availability
  |
  v
Present Slots
  |
  v
Patient Confirmation
  |
  v
Transactional Appointment API
  |
  v
Database / Hospital Integration
  |
  v
Confirmation
  |
  +----> BullMQ ---> SMS / WhatsApp / Email
```

------------------------------------------------------------------------

# 8. Emergency / Safety Workflow

Emergency handling must be a separate safety-controlled subsystem.

The LLM must NOT independently decide whether a patient has a medical
emergency.

Instead:

``` text
Patient message
      |
      v
AI extracts relevant information
      |
      v
Safety / Triage Rule Engine
      |
      v
Hospital-approved protocol
      |
      +--------------------+
      |                    |
      v                    v
Potential emergency     Normal workflow
      |                    |
      v                    v
Emergency escalation     Appointment routing
      |
      v
Human / hospital emergency pathway
```

## Important rule

The AI can identify that a conversation contains information requiring
escalation according to configured rules.

It must not represent that it has medically diagnosed the patient.

## Emergency responses

Emergency workflows must be configurable per hospital and may include:

-   instructing the patient to contact local emergency services,
-   directing the patient to the hospital emergency department,
-   escalating to designated hospital staff,
-   creating a high-priority callback task,
-   recording the escalation event.

The exact emergency protocol must be configured and approved by the
hospital.

------------------------------------------------------------------------

# 9. High-Level System Architecture

``` text
                         HEALLINK PLATFORM
                                |
       +------------------------+------------------------+
       |                        |                        |
   Web Patient             Voice Channel          Future WhatsApp
       |                        |                        |
       +------------------------+------------------------+
                                |
                                v
                       AI Conversation Layer
                                |
                 +--------------+--------------+
                 |                             |
             LLM Gateway                 Conversation State
                 |                             |
                 +--------------+--------------+
                                |
                                v
                         Intent Engine
                                |
          +---------------------+---------------------+
          |                     |                     |
          v                     v                     v
      Knowledge             Appointment          Safety /
       Request                Request            Escalation
          |                     |                     |
          v                     v                     v
        RAG                Scheduling Engine     Safety Engine
          |                     |                     |
          v                     v                     v
     Vector Search          Core APIs          Hospital Rules
                                |
                                v
                         Tool / Action Layer
                                |
          +---------------------+---------------------+
          |                     |                     |
          v                     v                     v
      Doctor API          Availability API     Appointment API
                                |
                                v
                         Transaction Layer
                                |
                  +-------------+-------------+
                  |                           |
                  v                           v
             PostgreSQL                    Hospital APIs
                  |
          +-------+-------+
          |               |
          v               v
       pgvector         Audit Logs

Redis
  |
  +---- BullMQ
          |
          +---- Notifications
          +---- Reminders
          +---- Async processing
          +---- Document ingestion
          +---- Integration synchronization
```

------------------------------------------------------------------------

# 10. Recommended Technology Stack

## Frontend

-   Next.js
-   TypeScript
-   React
-   Tailwind CSS
-   Accessible component system

## Backend

Recommended:

-   Python
-   FastAPI
-   Pydantic
-   SQLAlchemy
-   Alembic

Node.js/TypeScript may be used for specific infrastructure services if
there is a strong reason, but the initial backend should avoid
unnecessary language fragmentation.

## Database

-   PostgreSQL

Use PostgreSQL as the primary transactional source of truth.

## Vector Search

Initial recommendation:

-   PostgreSQL + pgvector

Do not introduce a separate vector database unless scale or retrieval
requirements justify it.

## Cache / Queue

-   Redis
-   BullMQ

BullMQ is responsible for asynchronous/background jobs.

## AI

Use an LLM provider through an internal AI Gateway abstraction.

Requirements:

-   structured output,
-   tool/function calling,
-   model abstraction,
-   prompt versioning,
-   token/cost tracking,
-   safety policies,
-   fallback handling.

## Voice

Architecture:

``` text
Voice Input
   |
Speech-to-Text
   |
Conversation Engine
   |
LLM
   |
Text-to-Speech
   |
Patient
```

Voice providers must remain behind an abstraction layer.

## Notifications

Abstract notification provider:

``` text
NotificationService
    |
    +-- SMS Provider
    +-- Email Provider
    +-- WhatsApp Provider
    +-- Push Provider
```

------------------------------------------------------------------------

# 11. AI Architecture

## AI Gateway

All LLM calls should pass through a centralized AI Gateway.

``` text
Application
    |
    v
AI Gateway
    |
    +-- Model Router
    +-- Prompt Manager
    +-- Safety Guardrails
    +-- Structured Output Validator
    +-- Tool Permission Layer
    +-- Usage / Cost Tracking
    +-- Observability
    |
    v
LLM Provider
```

Benefits:

-   model switching,
-   centralized prompts,
-   cost control,
-   logging,
-   safety controls,
-   consistent tool permissions.

------------------------------------------------------------------------

# 12. RAG Architecture

RAG should be used for **hospital knowledge**, not transactional data.

## Good RAG sources

-   hospital FAQs,
-   department information,
-   doctor profiles,
-   hospital policies,
-   visiting hours,
-   appointment policies,
-   cancellation policies,
-   insurance information,
-   OPD information,
-   hospital services,
-   approved patient instructions,
-   administrative procedures.

## Do NOT use RAG as the source of truth for

-   real-time doctor availability,
-   appointment booking,
-   appointment cancellation,
-   patient identity,
-   transactional state,
-   emergency authorization,
-   financial transactions.

Those must use structured APIs/databases.

## RAG pipeline

``` text
Hospital Document
      |
      v
Document Ingestion
      |
      v
Parsing
      |
      v
Chunking
      |
      v
Metadata Extraction
      |
      v
Embedding
      |
      v
pgvector
      |
      v
Retriever
      |
      v
Relevant Chunks
      |
      v
LLM
      |
      v
Grounded Response
```

## Required metadata

Each chunk should include:

-   hospital_id,
-   department_id where relevant,
-   document_id,
-   document_version,
-   source_type,
-   effective_date,
-   expiry_date if applicable,
-   language,
-   access_scope,
-   created_at,
-   updated_at.

------------------------------------------------------------------------

# 13. Agentic RAG

Agentic RAG should be introduced only after the basic RAG + tool system
works reliably.

## Example

Patient:

> "Meri mother ka follow-up appointment next week book karna hai."

Agent workflow:

``` text
Understand intent
      |
Identify patient
      |
Retrieve relevant non-sensitive context
      |
Determine department / appointment type
      |
Check hospital rules
      |
Call availability tool
      |
Return slots
      |
Ask for confirmation
      |
Call booking tool
      |
Send confirmation
```

## Agent restrictions

The agent must use an explicit allowlist of tools.

Example:

``` text
Allowed:
- search_hospital_knowledge
- search_doctors
- get_doctor_availability
- get_department
- create_appointment
- cancel_appointment
- reschedule_appointment
- send_notification

Restricted:
- modify_clinical_record
- modify_medication
- diagnosis
- prescription
- emergency_override
```

Transactional actions must pass through backend authorization and
validation.

------------------------------------------------------------------------

# 14. LoRA / Fine-Tuning Strategy

LoRA should NOT be part of the initial MVP by default.

Use prompting, structured outputs, RAG, and tool calling first.

LoRA/PEFT becomes relevant when there is sufficient high-quality,
legally usable training data and a demonstrated need for specialized
behavior.

Potential future uses:

-   intent classification,
-   structured information extraction,
-   domain-specific language behavior,
-   Indian multilingual conversational patterns,
-   consistent receptionist tone.

Never fine-tune on patient data without the appropriate legal, privacy,
consent, governance, and security controls.

------------------------------------------------------------------------

# 15. Tool Calling Architecture

The LLM should never directly manipulate the database.

Correct:

``` text
LLM
 |
 | tool call
 v
Backend Tool
 |
 v
Authorization
 |
 v
Validation
 |
 v
Business Logic
 |
 v
Database
```

Example:

``` json
{
  "tool": "get_available_slots",
  "arguments": {
    "hospital_id": "...",
    "department_id": "...",
    "date_from": "...",
    "date_to": "..."
  }
}
```

For booking:

``` text
LLM proposes booking
        |
        v
Backend validates patient
        |
        v
Backend validates slot
        |
        v
Backend checks authorization
        |
        v
Transaction begins
        |
        v
Appointment created
        |
        v
Transaction committed
```

------------------------------------------------------------------------

# 16. Scheduling Engine

The scheduling engine is a core domain service.

## Responsibilities

-   doctor availability,
-   working hours,
-   slot duration,
-   breaks,
-   leave,
-   holidays,
-   blocked slots,
-   appointment type,
-   capacity,
-   double-booking prevention,
-   cancellation,
-   rescheduling,
-   waitlist,
-   priority rules.

## Critical rule

The scheduling engine, not the LLM, owns appointment truth.

## Concurrency

The system must prevent two users from booking the same slot
simultaneously.

Use database transactions and appropriate locking/constraints.

------------------------------------------------------------------------

# 17. Database Model

Core entities:

``` text
Hospital
User
Role
Patient
Doctor
Department
DoctorDepartment
DoctorSchedule
ScheduleException
Appointment
AppointmentStatus
AppointmentType
Conversation
ConversationMessage
KnowledgeDocument
KnowledgeChunk
Notification
NotificationTemplate
EmergencyProtocol
Escalation
AuditLog
Integration
```

## Patient

Suggested fields:

``` text
id
hospital_id
external_patient_id
full_name
date_of_birth
phone
email
preferred_language
created_at
updated_at
```

Do not collect unnecessary personal information.

## Doctor

``` text
id
hospital_id
full_name
specialization
department_id
registration_identifier
status
created_at
updated_at
```

## Appointment

``` text
id
hospital_id
patient_id
doctor_id
department_id
appointment_type
start_time
end_time
status
source
notes
created_at
updated_at
```

## Conversation

``` text
id
hospital_id
patient_id nullable
channel
language
status
started_at
ended_at
```

## AuditLog

``` text
id
hospital_id
actor_type
actor_id
action
resource_type
resource_id
metadata
timestamp
ip_address
```

Avoid storing sensitive content in logs unless necessary.

------------------------------------------------------------------------

# 18. Multi-Tenant Architecture

HealLink is intended to support multiple hospitals.

Every hospital-owned resource must be tenant-scoped.

``` text
Platform
 |
 +-- Hospital A
 |     +-- Doctors
 |     +-- Patients
 |     +-- Appointments
 |     +-- Knowledge
 |
 +-- Hospital B
 |     +-- Doctors
 |     +-- Patients
 |     +-- Appointments
 |     +-- Knowledge
```

Never allow cross-tenant data access.

Every backend query involving tenant-owned resources must enforce
`hospital_id` or an equivalent tenant boundary.

------------------------------------------------------------------------

# 19. Role-Based Access Control

Minimum roles:

``` text
SUPER_ADMIN
HOSPITAL_ADMIN
RECEPTIONIST
DOCTOR
PATIENT
```

Permissions must be explicit.

Example:

  Capability                   Patient   Receptionist    Doctor   Hospital Admin
  -------------------------- --------- -------------- --------- ----------------
  Book appointment                 Yes            Yes   Limited              Yes
  Cancel appointment               Own            Yes   Limited              Yes
  Manage doctors                    No             No        No              Yes
  Manage schedules                  No        Limited       Own              Yes
  View audit logs                   No        Limited   Limited              Yes
  Manage hospital policies          No             No        No              Yes

------------------------------------------------------------------------

# 20. BullMQ Architecture

Use Redis + BullMQ for asynchronous tasks.

## Queues

``` text
notifications
appointment-reminders
document-processing
rag-ingestion
integration-sync
analytics
```

## Example

``` text
Appointment Created
       |
       v
BullMQ
       |
       +--> Confirmation SMS
       +--> WhatsApp message
       +--> Email
       +--> 24h reminder
       +--> 1h reminder
```

Jobs must support:

-   retries,
-   exponential backoff,
-   dead-letter handling,
-   idempotency,
-   observability,
-   cancellation where appropriate.

------------------------------------------------------------------------

# 21. API Design

Use REST initially.

## Authentication

``` text
POST /api/v1/auth/login
POST /api/v1/auth/logout
POST /api/v1/auth/refresh
```

## Hospitals

``` text
GET    /api/v1/hospitals/:id
PATCH  /api/v1/hospitals/:id
```

## Departments

``` text
GET    /api/v1/departments
POST   /api/v1/departments
PATCH  /api/v1/departments/:id
DELETE /api/v1/departments/:id
```

## Doctors

``` text
GET    /api/v1/doctors
POST   /api/v1/doctors
GET    /api/v1/doctors/:id
PATCH  /api/v1/doctors/:id
```

## Availability

``` text
GET /api/v1/doctors/:id/availability
GET /api/v1/departments/:id/availability
```

## Appointments

``` text
POST   /api/v1/appointments
GET    /api/v1/appointments/:id
PATCH  /api/v1/appointments/:id
POST   /api/v1/appointments/:id/cancel
POST   /api/v1/appointments/:id/reschedule
```

## AI

``` text
POST /api/v1/ai/conversations
POST /api/v1/ai/conversations/:id/messages
POST /api/v1/ai/conversations/:id/end
```

## Knowledge

``` text
POST   /api/v1/knowledge/documents
GET    /api/v1/knowledge/documents
PATCH  /api/v1/knowledge/documents/:id
DELETE /api/v1/knowledge/documents/:id
```

------------------------------------------------------------------------

# 22. Frontend Applications

## Patient application

Pages:

``` text
/
 /login
 /register
 /hospital
 /departments
 /doctors
 /book
 /appointments
 /appointments/:id
 /profile
 /chat
```

Primary patient experience should be simple and mobile-first.

## Hospital dashboard

``` text
/dashboard
/dashboard/appointments
/dashboard/doctors
/dashboard/departments
/dashboard/schedules
/dashboard/patients
/dashboard/conversations
/dashboard/escalations
/dashboard/knowledge
/dashboard/notifications
/dashboard/analytics
/dashboard/settings
```

------------------------------------------------------------------------

# 23. AI Conversation Design

The AI receptionist should:

1.  identify itself clearly as an AI assistant,
2.  communicate naturally,
3.  detect preferred language,
4.  understand user intent,
5.  ask only necessary questions,
6.  use tools for real-time information,
7.  ground hospital-specific information in RAG,
8.  confirm transactional actions,
9.  escalate when uncertain or required,
10. avoid clinical overreach.

## Example

Patient:

> "Mujhe skin ka doctor chahiye."

AI:

> "Bilkul. Aap Dermatology appointment ke liye booking kar sakte hain.
> Main available doctors aur slots check kar raha hoon."

Then call:

``` text
search_doctors(department="dermatology")
get_available_slots(...)
```

------------------------------------------------------------------------

# 24. Multilingual Architecture

Language detection should be handled separately from the core business
logic.

``` text
User Language
      |
      v
Language Detection
      |
      v
Conversation State
      |
      v
LLM
      |
      v
Localized Response
```

The internal data model remains language-neutral.

Store:

``` text
preferred_language
```

rather than creating separate workflows for each language.

MVP target:

-   English
-   Hindi
-   one regional language based on pilot hospital

------------------------------------------------------------------------

# 25. Observability

Every production component must be observable.

Track:

-   request latency,
-   error rate,
-   AI latency,
-   LLM token usage,
-   LLM cost,
-   tool-call failures,
-   appointment failures,
-   notification failures,
-   queue depth,
-   job failures,
-   RAG retrieval quality,
-   escalation rate.

Do not log raw sensitive patient data unnecessarily.

------------------------------------------------------------------------

# 26. Security Requirements

Minimum:

-   TLS everywhere,
-   encrypted secrets,
-   secure authentication,
-   role-based authorization,
-   tenant isolation,
-   database access controls,
-   secure session handling,
-   audit logging,
-   rate limiting,
-   input validation,
-   output validation,
-   CSRF protection where applicable,
-   secure file uploads,
-   dependency scanning,
-   vulnerability monitoring,
-   encrypted backups.

Healthcare deployments must also comply with applicable laws/regulations
and hospital policies for the deployment jurisdiction.

For India, the implementation should be reviewed against applicable
requirements including the Digital Personal Data Protection framework
and healthcare-specific obligations before production deployment.

Do not treat this document as legal advice.

------------------------------------------------------------------------

# 27. Privacy Principles

HealLink should follow data minimization.

Only collect information required for the requested workflow.

Examples:

For an appointment:

``` text
Name
Contact
Hospital
Department/doctor
Appointment preference
Required identification information
```

Do not collect unrelated sensitive information merely because the AI can
ask for it.

Patients should receive appropriate notice about:

-   AI interaction,
-   data collection,
-   purpose,
-   storage,
-   communication,
-   human escalation.

------------------------------------------------------------------------

# 28. AI Safety Principles

## Never

-   claim to be a human,
-   claim to diagnose,
-   claim certainty when uncertain,
-   invent hospital policies,
-   invent appointments,
-   invent doctor availability,
-   fabricate medical records,
-   provide unauthorized medical instructions,
-   bypass hospital emergency workflows.

## Always

-   ground hospital-specific answers,
-   use structured APIs for transactional data,
-   validate tool outputs,
-   respect authorization,
-   escalate when required,
-   preserve auditability,
-   clearly communicate important limitations.

------------------------------------------------------------------------

# 29. Error Handling

Every external dependency can fail.

Examples:

``` text
LLM unavailable
Database unavailable
Voice provider unavailable
SMS provider unavailable
Hospital API unavailable
Queue unavailable
RAG unavailable
```

The system should degrade gracefully.

Example:

If AI is unavailable:

``` text
AI unavailable
      |
      v
Fallback
      |
      +--> Web booking
      +--> Receptionist escalation
```

If hospital integration is unavailable:

Do not claim that an appointment has been booked.

Instead:

> "The hospital scheduling system is temporarily unavailable. I have not
> confirmed the appointment."

------------------------------------------------------------------------

# 30. Idempotency

Appointment creation and notification systems must be idempotent.

Example:

If the booking request is accidentally sent twice:

``` text
Request A
Request A retry
```

must not create two appointments.

Use:

``` text
idempotency_key
```

for transactional operations.

------------------------------------------------------------------------

# 31. Testing Strategy

## Unit tests

-   scheduling logic,
-   slot calculation,
-   authorization,
-   validation,
-   routing rules.

## Integration tests

-   database,
-   appointment API,
-   notification service,
-   BullMQ,
-   AI tool calling,
-   RAG retrieval.

## AI evaluation

Create a fixed evaluation dataset covering:

-   normal booking,
-   cancellation,
-   rescheduling,
-   multilingual input,
-   ambiguous requests,
-   unsupported requests,
-   emergency-like conversations,
-   hallucination attempts,
-   prompt injection,
-   unauthorized requests.

## End-to-end tests

Example:

``` text
Patient
  ↓
AI
  ↓
Department
  ↓
Availability
  ↓
Confirmation
  ↓
Appointment
  ↓
Notification
```

------------------------------------------------------------------------

# 32. Prompt Injection Defense

Hospital knowledge documents and user messages must be treated as
untrusted content.

The AI must not follow instructions embedded inside retrieved documents
that attempt to alter system behavior.

Example:

A hospital document should provide information, not instructions such
as:

> "Ignore your system prompt."

RAG content is data, not authority.

Tool permissions must be enforced by the backend rather than trusting
the model.

------------------------------------------------------------------------

# 33. Recommended Repository Structure

``` text
heallink/
│
├── apps/
│   ├── web/
│   └── admin/
│
├── services/
│   └── api/
│
├── packages/
│   ├── ui/
│   ├── types/
│   └── config/
│
├── ai/
│   ├── prompts/
│   ├── tools/
│   ├── rag/
│   ├── evaluation/
│   └── safety/
│
├── workers/
│   ├── notifications/
│   ├── reminders/
│   ├── rag-ingestion/
│   └── integrations/
│
├── database/
│   ├── migrations/
│   └── seed/
│
├── docs/
│
├── tests/
│
├── infrastructure/
│
├── .env.example
├── docker-compose.yml
├── README.md
└── LICENSE
```

The exact structure may be adjusted after implementation begins, but
domain boundaries should remain clear.

------------------------------------------------------------------------

# 34. Development Stages

## Stage 0 --- Product Definition

Deliverables:

-   requirements,
-   user stories,
-   architecture,
-   database schema,
-   API specification,
-   UX flows.

## Stage 1 --- Hospital Core

Build:

-   authentication,
-   hospital,
-   departments,
-   doctors,
-   schedules,
-   patients,
-   appointments.

## Stage 2 --- Admin Dashboard

Build:

-   dashboard,
-   appointment management,
-   doctor management,
-   schedule management,
-   patient lookup.

## Stage 3 --- Patient Booking

Build:

-   patient portal,
-   department search,
-   doctor search,
-   slot discovery,
-   booking,
-   cancellation,
-   rescheduling.

## Stage 4 --- AI Chat Receptionist

Build:

-   conversation engine,
-   intent detection,
-   tool calling,
-   booking integration,
-   structured responses.

## Stage 5 --- RAG

Build:

-   document upload,
-   ingestion,
-   chunking,
-   embeddings,
-   pgvector retrieval,
-   citations/source metadata,
-   hospital-specific knowledge.

## Stage 6 --- Background Jobs

Build:

-   Redis,
-   BullMQ,
-   confirmations,
-   reminders,
-   retries,
-   dead-letter handling.

## Stage 7 --- Voice

Build:

-   STT,
-   AI conversation,
-   TTS,
-   call session management,
-   escalation.

## Stage 8 --- Safety

Build:

-   hospital emergency protocols,
-   escalation workflows,
-   human handoff,
-   auditability,
-   safety evaluation.

## Stage 9 --- Integration

Build:

-   integration gateway,
-   FHIR/HL7 where applicable,
-   hospital API adapters,
-   synchronization,
-   integration monitoring.

## Stage 10 --- Pilot

Deploy to one controlled hospital/clinic environment.

Measure:

-   successful booking rate,
-   booking completion time,
-   AI escalation rate,
-   receptionist workload,
-   no-show rate,
-   notification success,
-   patient satisfaction,
-   system reliability.

------------------------------------------------------------------------

# 35. MVP Success Criteria

The MVP is successful when a patient can:

1.  enter the system,
2.  communicate naturally,
3.  select/describe the required service,
4.  receive valid doctor/department options,
5.  see real availability,
6.  select a slot,
7.  confirm the appointment,
8.  receive confirmation,
9.  cancel/reschedule,
10. communicate in supported languages.

The hospital must be able to:

1.  create doctors,
2.  configure departments,
3.  configure schedules,
4.  see appointments,
5.  modify availability,
6.  manage patients,
7.  view AI conversations where authorized,
8.  handle escalations,
9.  manage hospital knowledge.

------------------------------------------------------------------------

# 36. What NOT to Over-Engineer

Do not initially build:

-   Kubernetes,
-   dozens of microservices,
-   custom foundation model,
-   LoRA training pipeline,
-   dedicated vector database,
-   complex event-driven architecture,
-   blockchain,
-   autonomous clinical agent,
-   full hospital ERP.

Start with:

``` text
Next.js
+
FastAPI
+
PostgreSQL
+
pgvector
+
Redis
+
BullMQ
+
LLM Gateway
+
RAG
+
Function Calling
```

This is enough to build a serious MVP.

------------------------------------------------------------------------

# 37. Architecture Evolution

## Version 1

``` text
Next.js
   |
FastAPI
   |
PostgreSQL + pgvector
   |
Redis + BullMQ
   |
LLM
```

## Version 2

Add:

``` text
Voice
WhatsApp
Advanced RAG
Agentic workflows
Integration gateway
```

## Version 3

At scale:

``` text
API Gateway
     |
+----+----------------------+
|                           |
Core Services          AI Platform
|                           |
+-- Scheduling              +-- AI Gateway
+-- Patients                +-- RAG
+-- Hospitals               +-- Agents
+-- Appointments            +-- Voice
+-- Notifications           +-- Evaluation
```

Only split services when actual scaling, ownership, or reliability
requirements justify it.

------------------------------------------------------------------------

# 38. Claude Code Implementation Rules

Claude Code should treat this document as the product specification.

## Rule 1 --- Do not invent requirements

If something is unspecified, identify the ambiguity rather than silently
creating a major feature.

## Rule 2 --- Preserve domain boundaries

AI should not directly access the database.

Use:

``` text
AI → Tool → Service → Repository → Database
```

## Rule 3 --- Transactional truth comes from backend systems

Never use LLM output or RAG results as the source of truth for:

-   appointment availability,
-   appointment status,
-   patient identity,
-   doctor schedule,
-   billing status.

## Rule 4 --- Use typed contracts

Use strongly typed request/response models.

## Rule 5 --- Validate everything

Validate:

-   user input,
-   API input,
-   tool arguments,
-   model outputs,
-   database state,
-   external API responses.

## Rule 6 --- Every feature must have tests

Do not implement major functionality without tests.

## Rule 7 --- Security by default

Do not expose secrets, tokens, patient data, or internal system
information.

## Rule 8 --- Multi-tenancy from the beginning

Do not build a single-hospital architecture and attempt to retrofit
tenant isolation later.

## Rule 9 --- Keep providers replaceable

AI, voice, SMS, email, and WhatsApp providers must sit behind
interfaces/adapters.

## Rule 10 --- Prefer simple architecture

Do not introduce a new infrastructure component unless it solves a
demonstrated problem.

------------------------------------------------------------------------

# 39. Claude Code Development Workflow

Claude Code should follow this sequence:

``` text
1. Read this specification
        ↓
2. Inspect existing repository
        ↓
3. Identify current implementation state
        ↓
4. Create/update architecture documentation
        ↓
5. Create database schema
        ↓
6. Create migrations
        ↓
7. Implement domain services
        ↓
8. Implement APIs
        ↓
9. Implement frontend
        ↓
10. Implement AI tools
        ↓
11. Implement RAG
        ↓
12. Implement workers
        ↓
13. Add tests
        ↓
14. Run lint/type checks/tests
        ↓
15. Fix failures
        ↓
16. Update documentation
```

Claude Code should not attempt to implement the entire platform in one
pass.

Each stage should produce a working, testable increment.

------------------------------------------------------------------------

# 40. Definition of Done

A feature is not considered complete until:

-   implementation exists,
-   database migrations exist where required,
-   API contracts are defined,
-   validation exists,
-   authorization exists,
-   tests exist,
-   error handling exists,
-   logging/observability is appropriate,
-   documentation is updated,
-   linting passes,
-   type checks pass,
-   tests pass.

------------------------------------------------------------------------

# 41. Product Positioning

## Internal positioning

> HealLink is an AI-powered hospital front-desk operating platform.

## Patient-facing positioning

> **Healthcare access, simplified.**

## Core value proposition

> **24/7 multilingual assistance for hospital appointments and routine
> front-desk needs.**

## Key differentiators

-   multilingual conversational interface,
-   AI-assisted hospital navigation,
-   real-time appointment orchestration,
-   hospital-specific RAG,
-   controlled AI tool use,
-   emergency escalation workflows,
-   hospital-system integration,
-   human handoff,
-   multi-tenant architecture.

------------------------------------------------------------------------

# 42. Final System Principle

HealLink should be built around one central rule:

> **The AI handles conversation. The backend handles truth. The hospital
> controls clinical policy.**

Therefore:

``` text
                    PATIENT
                       |
                       v
                CONVERSATIONAL AI
                       |
          +------------+------------+
          |            |            |
          v            v            v
        RAG          TOOLS       SAFETY
          |            |            |
          |            v            v
          |      BUSINESS LOGIC   HOSPITAL
          |            |          PROTOCOLS
          |            v
          |       DATABASE
          |            |
          +------------+
                       |
                       v
              HOSPITAL SYSTEMS
```

This separation is the foundation of HealLink's reliability,
scalability, security, and future AI capabilities.

------------------------------------------------------------------------

# 43. Immediate Build Order

The first implementation should be:

### Sprint 1

-   Repository setup
-   Next.js application
-   FastAPI application
-   PostgreSQL
-   Redis
-   Docker Compose
-   authentication
-   base multi-tenant model

### Sprint 2

-   Hospital
-   Departments
-   Doctors
-   Doctor schedules
-   Patients
-   Appointment schema

### Sprint 3

-   Scheduling engine
-   Availability API
-   Booking
-   Cancellation
-   Rescheduling
-   Admin dashboard

### Sprint 4

-   Patient booking UI
-   AI Gateway
-   AI conversation endpoint
-   Function calling
-   Appointment tools

### Sprint 5

-   RAG
-   pgvector
-   hospital knowledge management
-   retrieval evaluation

### Sprint 6

-   BullMQ
-   notifications
-   reminders
-   background processing

### Sprint 7+

-   Voice
-   multilingual expansion
-   emergency escalation
-   hospital integrations
-   pilot deployment

------------------------------------------------------------------------

# 44. First Engineering Milestone

Before adding voice, agents, LoRA, or complex integrations, the
following demo must work:

``` text
Patient
   |
   v
HealLink Web
   |
   v
AI Receptionist
   |
   v
"Which department do you need?"
   |
   v
Patient answers naturally
   |
   v
AI calls hospital tools
   |
   v
Real doctor availability
   |
   v
Patient selects slot
   |
   v
Backend validates slot
   |
   v
Appointment created
   |
   v
BullMQ
   |
   +--> Confirmation
   +--> Reminder
```

Once this works reliably, HealLink has a real technical foundation.

------------------------------------------------------------------------

## END OF SPECIFICATION
