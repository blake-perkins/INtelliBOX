"""FastAPI web application for INtelliBOX."""

import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from intellibox import __version__
from intellibox.database import get_session
from intellibox.web.deps import static_dir, templates  # noqa: F401 — templates re-exported for backward compat


def _start_background_watcher():
    """Start the file watcher in a background daemon thread with supervised restarts."""
    from intellibox.ai.processor import process_email_with_ai
    from intellibox.ingestion.file_watcher import supervised_watch
    from intellibox.ingestion.parser import parse_and_store_email

    inbox_dir = Path("data/inbox")

    def callback(eml_path: Path):
        with get_session() as session:
            email_record = parse_and_store_email(eml_path, session)
            if email_record:
                process_email_with_ai(email_record, session)

    thread = threading.Thread(
        target=supervised_watch,
        args=(inbox_dir, callback),
        kwargs={"interval": 5, "max_restarts": 5},
        daemon=True,
        name="inbox-watcher",
    )
    thread.start()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _start_background_watcher()
    yield


# Create FastAPI app
app = FastAPI(
    title="INtelliBOX",
    description="AI-Powered Email Action Tracking System",
    version=__version__,
    lifespan=lifespan,
)

# Mount static files
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.middleware("http")
async def no_cache_html(request: Request, call_next):
    """Prevent browser caching of HTML pages so data is always fresh."""
    response = await call_next(request)
    ct = response.headers.get("content-type", "")
    if "text/html" in ct:
        response.headers["Cache-Control"] = "no-store"
    return response


# --- Include routers ---
from intellibox.web.routers import (  # noqa: E402
    actions,
    analytics,
    api,
    dashboard,
    emails,
    insights,
    knowledge_base,
    roster,
    settings,
)

app.include_router(dashboard.router)
app.include_router(actions.router)
app.include_router(emails.router)
app.include_router(insights.router)
app.include_router(settings.router)
app.include_router(knowledge_base.router)
app.include_router(roster.router)
app.include_router(analytics.router)
app.include_router(api.router)

# Test-only routes (gated by TESTING env var)
if os.environ.get("TESTING", "").lower() in ("true", "1", "yes"):
    from intellibox.web.routers import test_routes  # noqa: E402

    app.include_router(test_routes.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
