"""
Main API v1 router — aggregates all module routers.

Phase status:
  ✅ Phase 1 — auth
  ✅ Phase 2 — hospitals, departments, doctors, patients
  ✅ Phase 3 — schedules, availability engine, appointments
  ✅ Phase 4 — AI conversations (Gemini gateway, tools, safety)
  🔴 Phase 5 — knowledge / RAG
  🔴 Phase 6 — notifications
"""

from fastapi import APIRouter

from app.modules.auth.router import router as auth_router
from app.modules.hospitals.router import router as hospitals_router
from app.modules.departments.router import router as departments_router
from app.modules.doctors.router import router as doctors_router
from app.modules.patients.router import router as patients_router
# Phase 3
from app.modules.schedules.router import router as schedules_router
from app.modules.appointments.router import router as appointments_router
# Phase 4
from app.modules.conversations.router import router as conversations_router

api_router = APIRouter()

# ── Phase 1: Authentication ────────────────────────────────────────────────────
api_router.include_router(auth_router)

# ── Phase 2: Hospital Core ─────────────────────────────────────────────────────
api_router.include_router(hospitals_router)
api_router.include_router(departments_router)
api_router.include_router(doctors_router)
api_router.include_router(patients_router)

# ── Phase 3: Scheduling & Appointments ────────────────────────────────────────
api_router.include_router(schedules_router)
api_router.include_router(appointments_router)

# ── Phase 4: AI Conversations ─────────────────────────────────────────────────
api_router.include_router(conversations_router)

# ── Phase 5: Knowledge / RAG (upcoming) ───────────────────────────────────────
# from app.modules.knowledge.router import router as knowledge_router
# api_router.include_router(knowledge_router)

# ── Phase 6: Notifications (upcoming) ─────────────────────────────────────────
# from app.modules.notifications.router import router as notifications_router
# api_router.include_router(notifications_router)
