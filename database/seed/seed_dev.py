"""
Dev seed — creates a SUPER_ADMIN user and a sample hospital.

Usage (from services/api/):
    python -m database.seed.seed_dev

Requires DATABASE_URL in environment (or .env file).
"""

import asyncio
import sys
import os

# Allow running from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "services", "api"))

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.core.config import settings
from app.core.enums import UserRole
from app.core.security import hash_password
from app.modules.hospitals.models import Hospital
from app.modules.auth.models import User


DATABASE_URL = settings.DATABASE_URL


async def seed() -> None:
    engine = create_async_engine(DATABASE_URL, echo=False)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with SessionLocal() as session:
        # ── Sample hospital ────────────────────────────────────────────────────
        hospital = Hospital(
            name="Luma Demo Hospital",
            slug="luma-demo",
            contact_email="admin@lumademo.example",
            contact_phone="+91-9999999999",
            address="123 Healthcare Ave, Bengaluru, Karnataka 560001",
            config={
                "timezone": "Asia/Kolkata",
                "default_language": "en",
                "emergency_contact": "+91-112",
            },
            is_active=True,
        )
        session.add(hospital)
        await session.flush()

        # ── SUPER_ADMIN ────────────────────────────────────────────────────────
        super_admin = User(
            hospital_id=None,  # SUPER_ADMIN is not tenant-scoped
            email="superadmin@lumadev.example",
            full_name="Luma Super Admin",
            phone=None,
            password_hash=hash_password("SuperAdmin@123"),
            role=UserRole.SUPER_ADMIN,
            is_active=True,
        )
        session.add(super_admin)

        # ── Hospital Admin ─────────────────────────────────────────────────────
        hospital_admin = User(
            hospital_id=hospital.id,
            email="admin@lumademo.example",
            full_name="Demo Hospital Admin",
            phone="+91-9888888888",
            password_hash=hash_password("HospAdmin@123"),
            role=UserRole.HOSPITAL_ADMIN,
            is_active=True,
        )
        session.add(hospital_admin)

        await session.commit()

        print(f"[seed] Hospital created: id={hospital.id} slug={hospital.slug}")
        print(f"[seed] SUPER_ADMIN: email=superadmin@lumadev.example  password=SuperAdmin@123")
        print(f"[seed] HOSPITAL_ADMIN: email=admin@lumademo.example  password=HospAdmin@123")
        print("[seed] Done. Change these credentials before any real deployment!")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
