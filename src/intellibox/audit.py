"""Audit logging helper for recording user write operations."""

import json
from typing import Any, Optional

from fastapi import Request
from sqlalchemy.orm import Session

from intellibox.models import AuditLog
from intellibox.utils.datetime_utils import utcnow


def log_audit(
    session: Session,
    request: Request,
    action: str,
    resource_type: str,
    resource_id: Optional[int] = None,
    details: Optional[dict[str, Any]] = None,
) -> None:
    """Record a write operation in the audit log.

    Args:
        session: Active SQLAlchemy session (caller commits).
        request: FastAPI Request (provides user and IP).
        action: Verb -- "create", "update", "delete", "assign",
                "unassign", "complete", "change_priority".
        resource_type: Noun -- "action", "assignment", "roster_member",
                       "setting", "knowledge_document".
        resource_id: Primary key of the affected resource (nullable).
        details: Optional dict of context (serialized to JSON TEXT).
    """
    user = getattr(request.state, "user", None)
    username = user.username if user else "unknown"

    ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if not ip:
        ip = request.client.host if request.client else None

    entry = AuditLog(
        user=username,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=json.dumps(details) if details else None,
        ip_address=ip,
        created_at=utcnow(),
    )
    session.add(entry)
