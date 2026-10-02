"""
User repository — data access layer for the auth module.
All queries are typed and tenant-safe.
"""

import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User


class UserRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, user_id: str | uuid.UUID) -> User | None:
        result = await self._db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self._db.execute(
            select(User).where(User.email == email.lower())
        )
        return result.scalar_one_or_none()

    async def create(self, **fields) -> User:  # type: ignore[no-untyped-def]
        user = User(**fields)
        self._db.add(user)
        await self._db.flush()
        await self._db.refresh(user)
        return user

    async def update_last_login(self, user_id: uuid.UUID) -> None:
        from datetime import UTC, datetime
        await self._db.execute(
            update(User)
            .where(User.id == user_id)
            .values(last_login_at=datetime.now(UTC))
        )
