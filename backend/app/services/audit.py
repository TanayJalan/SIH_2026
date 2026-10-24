"""Audit logging service.

All write operations must call :meth:`AuditService.log` in the same database
transaction as the change they describe.
"""

import uuid
from typing import Any

from sqlalchemy.orm import Session
from starlette.requests import Request

from app.models.audit import AuditLog
from app.models.user import User


class AuditService:
    """Create append-only audit entries within a request's transaction."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def log(
        self,
        actor: User | None,
        action: str,
        entity_type: str,
        entity_id: uuid.UUID,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        request: Request | None = None,
    ) -> AuditLog:
        """Add an audit entry to the current transaction and return it.

        The caller owns the transaction boundary and must commit or roll back.
        ``before`` and ``after`` should contain JSON-safe snapshots; the
        database engine additionally serialises UUIDs and datetimes.
        """
        entry = AuditLog(
            actor_id=actor.id if actor is not None else None,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before=before,
            after=after,
            ip=self._client_ip(request),
        )
        self._db.add(entry)
        self._db.flush()
        return entry

    @staticmethod
    def _client_ip(request: Request | None) -> str | None:
        if request is None or request.client is None:
            return None
        return request.client.host[:45]
