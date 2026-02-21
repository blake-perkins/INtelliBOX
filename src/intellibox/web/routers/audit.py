"""Audit log routes."""

import json
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import desc

from intellibox.models import AuditLog
from intellibox.utils.datetime_utils import utcnow
from intellibox.web.auth import require_admin
from intellibox.web.deps import get_session, templates
from intellibox.web.queries import paginate

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/audit", response_class=HTMLResponse)
async def audit_log_page(
    request: Request,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    user: Optional[str] = None,
    days: Optional[str] = None,
    page: int = Query(1, ge=1),
):
    """View the audit log with filters."""
    with get_session() as session:
        query = session.query(AuditLog).order_by(desc(AuditLog.created_at))

        if action:
            query = query.filter(AuditLog.action == action)
        if resource_type:
            query = query.filter(AuditLog.resource_type == resource_type)
        if user:
            query = query.filter(AuditLog.user == user)
        if days:
            try:
                cutoff = utcnow() - timedelta(days=int(days))
                query = query.filter(AuditLog.created_at >= cutoff)
            except ValueError:
                pass

        entries, total_count, total_pages = paginate(query, page)

        # Parse JSON details for display
        for entry in entries:
            if entry.details:
                try:
                    entry._parsed_details = json.loads(entry.details)
                except (json.JSONDecodeError, TypeError):
                    entry._parsed_details = entry.details
            else:
                entry._parsed_details = None

        # Get distinct values for filter dropdowns
        actions_list = [
            r[0] for r in
            session.query(AuditLog.action).distinct().order_by(AuditLog.action).all()
        ]
        resource_types_list = [
            r[0] for r in
            session.query(AuditLog.resource_type).distinct().order_by(AuditLog.resource_type).all()
        ]
        users_list = [
            r[0] for r in
            session.query(AuditLog.user).distinct().order_by(AuditLog.user).all()
        ]

        return templates.TemplateResponse("audit.html", {
            "request": request,
            "entries": entries,
            "action_filter": action,
            "resource_type_filter": resource_type,
            "user_filter": user,
            "days": days,
            "page": page,
            "total_pages": total_pages,
            "total_count": total_count,
            "actions_list": actions_list,
            "resource_types_list": resource_types_list,
            "users_list": users_list,
            "current_time": utcnow(),
        })
