"""Insights and report generation routes."""

import threading
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from intellibox.reporter.generator import (
    generate_enhanced_report,
    get_cached_structured_program_news,
)
from intellibox.utils.datetime_utils import utcnow
from intellibox.web.deps import get_session, templates

router = APIRouter()

# --- Background insights generation jobs ---
_insights_jobs: dict = {}  # {job_id: {"status": "running"|"done"|"error", "started_at": datetime}}


def _cleanup_old_jobs():
    """Remove insight generation jobs older than 5 minutes."""
    cutoff = utcnow() - timedelta(minutes=5)
    stale = [jid for jid, j in _insights_jobs.items() if j["started_at"] < cutoff]
    for jid in stale:
        _insights_jobs.pop(jid, None)


@router.get("/insights", response_class=HTMLResponse)
async def view_insights(request: Request):
    """View AI-powered insights dashboard. Serves cached data; generation is triggered via the async API."""
    try:
        days = int(request.query_params.get("days", 14))
    except (ValueError, TypeError):
        days = 14
    days = max(7, min(days, 90))  # clamp to 7-90

    refreshed_status = request.query_params.get("refreshed", "")  # "ok", "error", or ""

    with get_session() as session:
        report_data = generate_enhanced_report(session, days=days, force_refresh=False)

        # Calculate cache age in minutes for display
        if report_data.get("is_cached") and report_data.get("generated_at"):
            cache_age_minutes = int((utcnow() - report_data["generated_at"]).total_seconds() / 60)
        else:
            cache_age_minutes = 0

        program_news_data = get_cached_structured_program_news(session)

        return templates.TemplateResponse("report.html", {
            "request": request,
            "report": report_data,
            "cache_age_minutes": cache_age_minutes,
            "program_news": program_news_data,
            "current_time": utcnow(),
            "datetime": datetime,
            "selected_days": days,
            "just_refreshed": refreshed_status in ("ok", "error"),
            "refresh_failed": refreshed_status == "error"
        })


@router.post("/api/insights/generate")
async def start_insights_generation(request: Request):
    """Start AI insights generation in a background thread. Returns a job ID for polling."""
    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    days = int(body.get("days", 14))
    days = max(7, min(days, 90))

    _cleanup_old_jobs()

    job_id = uuid.uuid4().hex[:8]
    _insights_jobs[job_id] = {"status": "running", "started_at": utcnow()}

    def run():
        try:
            with get_session() as session:
                result = generate_enhanced_report(session, days=days, force_refresh=True)
                get_cached_structured_program_news(session, days=days, force_refresh=True)
            _insights_jobs[job_id]["status"] = "error" if result.get("ai_failed") else "done"
        except Exception:
            _insights_jobs[job_id]["status"] = "error"

    threading.Thread(target=run, daemon=True, name=f"insights-{job_id}").start()
    return {"job_id": job_id}


@router.get("/api/insights/status/{job_id}")
async def insights_generation_status(job_id: str):
    """Poll generation status. Returns running, done, error, or unknown."""
    job = _insights_jobs.get(job_id)
    if not job:
        return {"status": "unknown"}
    return {"status": job["status"]}


@router.get("/api/insights/active-job")
async def insights_active_job():
    """Check if there's a currently running insights generation job."""
    for job_id, job in _insights_jobs.items():
        if job["status"] == "running":
            return {"job_id": job_id}
    return {"job_id": None}
