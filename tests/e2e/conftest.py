"""Playwright E2E test configuration: server lifecycle, fixtures, API helpers."""

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest
import requests

BASE_URL = "http://127.0.0.1:8787"
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


# ── Server lifecycle ──


@pytest.fixture(scope="session")
def test_server():
    """Start a real uvicorn server with TESTING=true for the test session."""
    # Use a temporary database so we don't touch the real one
    tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False, prefix="e2e_")
    tmp_db.close()

    env = os.environ.copy()
    env["TESTING"] = "true"
    env["AUTH_MODE"] = "disabled"
    env["DATABASE_PATH"] = tmp_db.name

    proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn",
            "intellibox.web.app:app",
            "--host", "127.0.0.1",
            "--port", "8787",
            "--no-access-log",
        ],
        env=env,
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for server readiness
    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            resp = requests.get(f"{BASE_URL}/health", timeout=1)
            if resp.status_code == 200:
                break
        except requests.ConnectionError:
            pass
        time.sleep(0.3)
    else:
        stdout = proc.stdout.read().decode() if proc.stdout else ""
        stderr = proc.stderr.read().decode() if proc.stderr else ""
        proc.terminate()
        raise RuntimeError(
            f"Test server did not start within 15s.\nstdout: {stdout}\nstderr: {stderr}"
        )

    yield proc

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    # Clean up temp database
    try:
        os.unlink(tmp_db.name)
    except OSError:
        pass


@pytest.fixture(scope="session")
def base_url(test_server):
    """Provide the base URL for pytest-playwright — page.goto('/path') uses this."""
    return BASE_URL


# ── API Helpers ──


class TestAPI:
    """Thin wrapper around the test-only API endpoints."""

    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url

    def reset_db(self):
        resp = requests.post(f"{self.base_url}/api/test/reset")
        assert resp.status_code == 200, f"DB reset failed: {resp.text}"

    def seed(self, entity_type: str, data: dict) -> int:
        resp = requests.post(
            f"{self.base_url}/api/test/seed",
            json={"type": entity_type, "data": data},
        )
        assert resp.status_code == 200, f"Seed {entity_type} failed: {resp.text}"
        return resp.json()["id"]

    def query_action(self, action_id: int) -> dict:
        return requests.get(f"{self.base_url}/api/test/query/action/{action_id}").json()

    def query_assignment(self, action_id: int) -> dict:
        return requests.get(
            f"{self.base_url}/api/test/query/assignment",
            params={"action_id": action_id},
        ).json()

    def query_roster_count(self) -> int:
        return requests.get(f"{self.base_url}/api/test/query/roster/count").json()["count"]

    def query_knowledge_count(self) -> int:
        return requests.get(f"{self.base_url}/api/test/query/knowledge/count").json()["count"]


@pytest.fixture(scope="session")
def api():
    return TestAPI()


# ── Seed Data Factories ──


_counter = 0


def _next_id():
    global _counter
    _counter += 1
    return _counter


def make_email(api: TestAPI, **overrides) -> int:
    n = _next_id()
    defaults = {
        "message_id": f"e2e-{n}-{time.time_ns()}@test",
        "subject": f"Test Email {n}",
        "from_address": "sender@example.com",
        "from_name": "Test Sender",
        "to_addresses": '["team@example.com"]',
        "received_date": "2026-02-15T10:00:00",
        "body_text": "Test email body content.",
        "body_html": "<p>Test email body content.</p>",
        "processed": True,
        "processed_at": "2026-02-15T10:05:00",
    }
    defaults.update(overrides)
    return api.seed("email", defaults)


def make_action(api: TestAPI, email_id: int, **overrides) -> int:
    n = _next_id()
    defaults = {
        "email_id": email_id,
        "title": f"Test Action {n}",
        "description": f"Description for test action {n}",
        "priority": "medium",
        "confidence_score": 0.9,
    }
    defaults.update(overrides)
    return api.seed("action", defaults)


def make_assignment(api: TestAPI, action_id: int, **overrides) -> int:
    defaults = {
        "action_id": action_id,
        "assigned_to": "Alice Johnson",
        "status": "assigned",
    }
    defaults.update(overrides)
    return api.seed("assignment", defaults)


def make_roster_member(api: TestAPI, **overrides) -> int:
    n = _next_id()
    defaults = {
        "first_name": f"User{n}",
        "last_name": f"Test{n}",
        "email": f"user{n}.{time.time_ns()}@example.com",
        "active": True,
    }
    defaults.update(overrides)
    return api.seed("roster_member", defaults)


def make_knowledge_doc(api: TestAPI, **overrides) -> int:
    n = _next_id()
    defaults = {
        "filename": f"doc-{n}.txt",
        "file_type": "txt",
        "file_size": 100,
        "extracted_text": f"Knowledge document content {n}",
        "extraction_status": "success",
    }
    defaults.update(overrides)
    return api.seed("knowledge_document", defaults)


# ── Per-test DB reset ──


@pytest.fixture(autouse=True)
def reset_db(api, test_server):
    """Reset the database before every test."""
    api.reset_db()
