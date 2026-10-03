"""
Pytest configuration and shared fixtures for Luma Vaani test suite.

Test database strategy:
  - Uses a separate test database (DATABASE_URL with _test suffix or TEST_DATABASE_URL)
  - Each test function gets a rolled-back transaction (no state leakage)
  - SQLAlchemy async sessions are properly managed with asyncio

Test layers:
  unit/       — pure unit tests (no DB, no external services)
  integration/ — tests against a real test PostgreSQL instance
"""

import asyncio
import os
import uuid
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# ── Test database URL ──────────────────────────────────────────────────────────
# Use TEST_DATABASE_URL if set, otherwise append _test to the main DB name
_DEFAULT_DB = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://lumauser:lumasecret@localhost:5432/lumadb",
)
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", _DEFAULT_DB.replace("lumadb", "lumadb_test"))

# Override settings for tests
os.environ.setdefault("DATABASE_URL", TEST_DATABASE_URL)
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-do-not-use-in-production-32chars!!")
os.environ.setdefault("JWT_REFRESH_SECRET_KEY", "test-refresh-key-do-not-use-32chars!!")
os.environ.setdefault("NOTIFICATIONS_ENABLED", "false")  # Never send real notifications in tests
os.environ.setdefault("GEMINI_API_KEY", "")               # No real API calls in unit tests


@pytest.fixture(scope="session")
def event_loop_policy():
    return asyncio.DefaultEventLoopPolicy()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create a shared async engine for the test session."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, pool_pre_ping=True)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def create_tables(test_engine):
    """Create all tables once per test session."""
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "api"))

    from app.core.base import Base
    # Import all models so they register with Base.metadata
    import app.modules.auth.models           # noqa: F401
    import app.modules.hospitals.models      # noqa: F401
    import app.modules.departments.models    # noqa: F401
    import app.modules.doctors.models        # noqa: F401
    import app.modules.patients.models       # noqa: F401
    import app.modules.schedules.models      # noqa: F401
    import app.modules.appointments.models   # noqa: F401
    import app.modules.conversations.models  # noqa: F401
    import app.modules.notifications.models  # noqa: F401
    import app.modules.knowledge.models      # noqa: F401

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db(test_engine, create_tables) -> AsyncGenerator[AsyncSession, None]:
    """
    Per-test transactional DB session.
    All changes are rolled back after each test — zero state leakage.
    """
    async with test_engine.begin() as conn:
        session_factory = async_sessionmaker(
            bind=conn,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
        async with session_factory() as session:
            yield session
            await session.rollback()


@pytest_asyncio.fixture
async def client(db) -> AsyncGenerator[AsyncClient, None]:
    """
    Async HTTP test client wired to the FastAPI app.
    Overrides the DB dependency to use the transactional test session.
    """
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "api"))

    from app.main import app
    from app.core.database import get_db

    async def _override_db():
        yield db

    app.dependency_overrides[get_db] = _override_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Content-Type": "application/json"},
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ── Test data factories ────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def test_hospital(db: AsyncSession):
    """Create and return a test hospital."""
    from app.modules.hospitals.models import Hospital
    hospital = Hospital(
        name="Test Hospital",
        slug=f"test-hospital-{uuid.uuid4().hex[:8]}",
        contact_email="test@hospital.example",
        contact_phone="+91-9000000000",
        address="1 Test Street",
        config={
            "timezone": "Asia/Kolkata",
            "default_language": "en",
            "emergency_phone": "112",
            "notification_channels": [],  # No notifications in tests
        },
        is_active=True,
    )
    db.add(hospital)
    await db.flush()
    return hospital


@pytest_asyncio.fixture
async def test_admin_user(db: AsyncSession, test_hospital):
    """Create and return a HOSPITAL_ADMIN user."""
    from app.modules.auth.models import User
    from app.core.enums import UserRole
    from app.core.security import hash_password
    user = User(
        hospital_id=test_hospital.id,
        email=f"admin-{uuid.uuid4().hex[:8]}@test.example",
        full_name="Test Admin",
        phone="+91-9000000001",
        password_hash=hash_password("Test@12345"),
        role=UserRole.HOSPITAL_ADMIN,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


@pytest_asyncio.fixture
async def test_patient(db: AsyncSession, test_hospital):
    """Create and return a test patient."""
    from app.modules.patients.models import Patient
    from datetime import date
    patient = Patient(
        hospital_id=test_hospital.id,
        full_name="Test Patient",
        phone="+91-9000099999",
        email="patient@test.example",
        date_of_birth=date(1990, 1, 1),
        gender="MALE",
        medical_record_number=f"TEST-{uuid.uuid4().hex[:8].upper()}",
        is_active=True,
    )
    db.add(patient)
    await db.flush()
    return patient


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient, test_admin_user, test_hospital) -> dict:
    """Return Authorization headers for the test admin user."""
    response = await client.post("/api/v1/auth/login", json={
        "email": test_admin_user.email,
        "password": "Test@12345",
        "hospital_slug": "test-hospital",
    })
    token = response.json().get("access_token", "")
    return {"Authorization": f"Bearer {token}"}
