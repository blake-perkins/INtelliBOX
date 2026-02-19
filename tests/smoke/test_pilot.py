"""Smoke tests for the live pilot server.

Run against the deployed instance to verify all pages and API endpoints
are functional after a deploy.

Usage:
    PILOT_USER=bperkins PILOT_PASSWORD=... pytest tests/smoke/test_pilot.py -v

Or with a custom host:
    PILOT_HOST=your-host.duckdns.org PILOT_USER=x PILOT_PASSWORD=y pytest tests/smoke/test_pilot.py -v
"""

import os
import time

import pytest
import requests

PILOT_HOST = os.environ.get(
    "PILOT_HOST", "intellibox-pilot.duckdns.org"
)
BASE_URL = os.environ.get("BASE_URL", f"https://{PILOT_HOST}")
FIXTURES_DIR = os.path.join(
    os.path.dirname(__file__), "..", "fixtures"
)

_user = os.environ.get("PILOT_USER")
_password = os.environ.get("PILOT_PASSWORD")
AUTH = (_user, _password) if _user and _password else None

pytestmark = pytest.mark.smoke


def get(path, **kwargs):
    kwargs.setdefault("auth", AUTH)
    return requests.get(f"{BASE_URL}{path}", timeout=15, **kwargs)


def post(path, **kwargs):
    kwargs.setdefault("auth", AUTH)
    return requests.post(f"{BASE_URL}{path}", timeout=30, **kwargs)


# ── Pages ──────────────────────────────────────────────────────────────


class TestPages:
    """All pages should return 200 and no error text."""

    @pytest.mark.parametrize("path", [
        "/",
        "/actions",
        "/emails",
        "/insights",
        "/settings",
        "/roster",
        "/analytics",
    ])
    def test_page_loads(self, path):
        r = get(path)
        assert r.status_code == 200, f"{path} returned {r.status_code}"
        assert "Internal Server Error" not in r.text
        assert "Traceback" not in r.text

    def test_knowledge_base_redirects_to_settings(self):
        r = get("/knowledge-base", allow_redirects=False)
        assert r.status_code in (302, 303)

    def test_knowledge_base_follows_redirect(self):
        r = get("/knowledge-base")
        assert r.status_code == 200
        assert "Internal Server Error" not in r.text


# ── Health & Stats ─────────────────────────────────────────────────────


class TestHealthAndStats:

    def test_health_endpoint(self):
        r = get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert data["watcher"]["is_alive"] is True

    def test_stats_endpoint(self):
        r = get("/api/stats")
        assert r.status_code == 200
        data = r.json()
        assert "total_emails" in data
        assert "total_actions" in data
        assert data["total_emails"] >= 0
        assert data["total_actions"] >= 0


# ── Insights API ───────────────────────────────────────────────────────


class TestInsightsAPI:

    def test_generate_returns_job_id(self):
        r = post("/api/insights/generate")
        assert r.status_code == 200
        data = r.json()
        assert "job_id" in data

    def test_status_endpoint(self):
        r = post("/api/insights/generate")
        job_id = r.json()["job_id"]

        r = get(f"/api/insights/status/{job_id}")
        assert r.status_code == 200
        assert r.json()["status"] in ("running", "done")

    def test_active_job_endpoint(self):
        post("/api/insights/generate")
        r = get("/api/insights/active-job")
        assert r.status_code == 200

    def test_generate_completes(self):
        """Trigger generation and wait for it to finish (up to 60s)."""
        r = post("/api/insights/generate")
        job_id = r.json()["job_id"]

        for _ in range(60):
            r = get(f"/api/insights/status/{job_id}")
            if r.json()["status"] == "done":
                return
            time.sleep(1)

        pytest.fail(f"Insights job {job_id} did not complete within 60s")


# ── Email Upload ───────────────────────────────────────────────────────


class TestEmailUpload:

    def test_upload_eml_file(self):
        eml_path = os.path.join(FIXTURES_DIR, "pilot-test-weekly-status.eml")
        if not os.path.exists(eml_path):
            pytest.skip("Test fixture not found")

        with open(eml_path, "rb") as f:
            r = post(
                "/emails/upload",
                files={"file": ("test.eml", f, "message/rfc822")},
                allow_redirects=False,
            )

        assert r.status_code == 303
        assert "uploaded=1" in r.headers.get("location", "")
