"""API Usage telemetry dashboard route."""

from datetime import timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import desc, func

from intellibox.models import APIUsageLog
from intellibox.utils.datetime_utils import utcnow
from intellibox.web.auth import require_admin
from intellibox.web.deps import get_session, templates

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/api-usage", response_class=HTMLResponse)
async def api_usage_dashboard(request: Request):
    """API usage telemetry dashboard."""
    try:
        days_int = int(request.query_params.get("days", 30))
    except (ValueError, TypeError):
        days_int = 30
    days_int = max(7, min(days_int, 180))

    cutoff = utcnow() - timedelta(days=days_int)

    with get_session() as session:
        # --- Summary cards ---
        base_q = session.query(APIUsageLog).filter(APIUsageLog.created_at >= cutoff)

        total_calls = base_q.count()
        total_tokens = session.query(
            func.coalesce(func.sum(APIUsageLog.total_tokens), 0)
        ).filter(APIUsageLog.created_at >= cutoff).scalar()
        total_prompt_tokens = session.query(
            func.coalesce(func.sum(APIUsageLog.prompt_tokens), 0)
        ).filter(APIUsageLog.created_at >= cutoff).scalar()
        total_completion_tokens = session.query(
            func.coalesce(func.sum(APIUsageLog.completion_tokens), 0)
        ).filter(APIUsageLog.created_at >= cutoff).scalar()

        # Calls today
        today_start = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        calls_today = session.query(APIUsageLog).filter(
            APIUsageLog.created_at >= today_start
        ).count()

        # Error count
        error_count = session.query(APIUsageLog).filter(
            APIUsageLog.status == "error",
            APIUsageLog.created_at >= cutoff,
        ).count()

        # Avg latency (successful calls only)
        avg_latency = session.query(
            func.coalesce(func.avg(APIUsageLog.latency_ms), 0)
        ).filter(
            APIUsageLog.status == "success",
            APIUsageLog.created_at >= cutoff,
        ).scalar()

        # Cost estimate (GPT-4o-mini: $0.15/1M input, $0.60/1M output)
        cost_estimate = (
            (total_prompt_tokens * 0.15 / 1_000_000)
            + (total_completion_tokens * 0.60 / 1_000_000)
        )

        # --- Daily calls for bar chart ---
        daily_rows = session.query(
            func.date(APIUsageLog.created_at).label("day"),
            func.count(APIUsageLog.id).label("calls"),
            func.coalesce(func.sum(APIUsageLog.total_tokens), 0).label("tokens"),
        ).filter(
            APIUsageLog.created_at >= cutoff
        ).group_by(
            func.date(APIUsageLog.created_at)
        ).order_by(func.date(APIUsageLog.created_at)).all()

        daily_data = [{"day": str(r.day), "calls": r.calls, "tokens": int(r.tokens)} for r in daily_rows]
        max_daily_calls = max((d["calls"] for d in daily_data), default=0)

        # --- Breakdown by call_type ---
        type_rows = session.query(
            APIUsageLog.call_type,
            func.count(APIUsageLog.id).label("count"),
            func.coalesce(func.sum(APIUsageLog.total_tokens), 0).label("tokens"),
            func.coalesce(func.avg(APIUsageLog.latency_ms), 0).label("avg_latency"),
        ).filter(
            APIUsageLog.created_at >= cutoff
        ).group_by(APIUsageLog.call_type).order_by(desc("count")).all()

        type_breakdown = [{
            "type": r.call_type,
            "count": r.count,
            "tokens": int(r.tokens),
            "avg_latency": int(r.avg_latency),
        } for r in type_rows]
        max_type_count = max((t["count"] for t in type_breakdown), default=0)

        # --- Recent calls table (last 25) ---
        recent_calls = session.query(APIUsageLog).order_by(
            desc(APIUsageLog.created_at)
        ).limit(25).all()

        return templates.TemplateResponse("api_usage.html", {
            "request": request,
            "days": str(days_int),
            "total_calls": total_calls,
            "total_tokens": total_tokens,
            "total_prompt_tokens": total_prompt_tokens,
            "total_completion_tokens": total_completion_tokens,
            "calls_today": calls_today,
            "error_count": error_count,
            "avg_latency": int(avg_latency),
            "cost_estimate": cost_estimate,
            "daily_data": daily_data,
            "max_daily_calls": max_daily_calls,
            "type_breakdown": type_breakdown,
            "max_type_count": max_type_count,
            "recent_calls": recent_calls,
        })
