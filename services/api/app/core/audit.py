"""
AuditService — writes immutable audit log entries from the service layer.

Rules:
- NEVER store raw PII or PHI in before_state / after_state.
- NEVER store passwords, tokens, or medical content.
- Store only IDs, action names, and non-sensitive metadata.
"""

import uuid
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import AuditActorType
from app.modules.audit.models import AuditLog

logger = structlog.get_logger(__name__)


class AuditService:
    """
    Writes append-only audit records. Called from service layer.
    Flush-only — the caller's session commit persists the record atomically.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def log(
        self,
        *,
        action: str,
        actor_type: AuditActorType,
        actor_id: str | None = None,
        hospital_id: uuid.UUID | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        before_state: dict[str, Any] | None = None,
        after_state: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        """
        Append an audit record. Flushes but does not commit.
        The calling session's commit (in get_db) persists it transactionally.
        """
        entry = AuditLog(
            hospital_id=hospital_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            before_state=before_state,
            after_state=after_state,
            metadata=metadata or {},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self._db.add(entry)
        await self._db.flush()

        logger.info(
            "audit_event",
            action=action,
            actor_type=actor_type.value,
            actor_id=actor_id,
            resource_type=resource_type,
            resource_id=resource_id,
            hospital_id=str(hospital_id) if hospital_id else None,
        )
        return entry
