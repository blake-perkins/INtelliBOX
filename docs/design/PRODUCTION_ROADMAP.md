# INtelliBOX — Production Readiness Roadmap

> Created: 2026-02-17
> Last updated: 2026-02-19
> Status: Active — update this document as items are completed

---

## Executive Summary

The codebase is clean, well-structured, and functionally complete. Test suite: 13 pytest modules + 165 BDD scenarios + 46 Playwright E2E tests, all passing. The application is deployed to production on an EC2 instance with IronBank UBI 9 containers, nginx reverse proxy, TLS, and HTTP basic auth. CI/CD pipeline auto-deploys on push to `main` after all tests and security scans pass.

**Overall readiness: ~85/100 — deployed and running with security scanning, auth, and TLS in place.**

---

## How to Use This Document

Each item has a checkbox. Check it off when completed and add the completion date. Group items into sprints or milestones as work is planned. The phases are ordered by priority — do not skip Phase 0.

---

## Phase 0 — Immediate Blockers *(Do Before Anything Else)*

These are not optional. Nothing should be deployed publicly until these are resolved.

### 0.1 — Rotate Exposed Secrets
- [x] Regenerate the OpenAI API key at platform.openai.com *(done 2026-02-17)*
- [x] Verify `.env` is in `.gitignore` and never staged
- [ ] Rotate any SMTP credentials that may have been exposed
- [ ] Add a pre-commit hook to block secrets (`detect-secrets` or `gitleaks`)

### 0.2 — Decide Deployment Target *(Completed 2026-02-18)*
- **Who uses this?** Internal team — small number of known users
- **Where does it run?** AWS EC2 (t3.micro) with Podman containers
- **Single tenant or multi-tenant?** Single tenant
- **Network boundary?** Public internet with HTTP basic auth via nginx

---

## Phase 1 — Security Hardening

### 1.1 — Authentication *(Completed 2026-02-18)*
- [x] Decision made: **Option A — HTTP Basic Auth via nginx**
- [x] Auth implemented: nginx `auth_basic` with `.htpasswd`, `/health` endpoint excluded from auth
- [x] Smoke tests updated to support `PILOT_USER`/`PILOT_PASSWORD` env vars

### 1.2 — CSRF Protection
All HTML forms currently submit without CSRF tokens.
- [ ] Add `fastapi-csrf-protect` library
- [ ] Update `base.html` to include hidden token in all `<form>` tags
- [ ] Middleware validates token on all POST requests
- [ ] BDD test: POST without CSRF token returns 403

### 1.3 — Secrets Management
Move away from `.env` file on disk:
- **AWS:** AWS Secrets Manager or Parameter Store
- **Azure:** Azure Key Vault with managed identity
- **Self-hosted:** HashiCorp Vault or Docker secrets

Minimum bar before any deployment:
- [ ] `.env` owned by app user, mode `600`
- [ ] `.env` excluded from all backups going to insecure locations
- [ ] Preferred: secrets loaded from vault at startup, not from file

### 1.4 — Network Security *(Mostly Complete)*
- [x] Deploy behind a reverse proxy (nginx) — uvicorn bound to 127.0.0.1:8000 only
- [x] Configure TLS termination at the proxy layer (Let's Encrypt via Certbot, auto-renew)
- [ ] Restrict source IPs to VPN CIDR at firewall/security group level (optional — currently public with basic auth)
- [ ] Add rate limiting at proxy layer (Nginx `limit_req_zone`)

### 1.5 — Dependency Security Scanning *(Completed 2026-02-19)*
- [x] Add `pip-audit` and `bandit` to dev dependencies
- [x] Run `pip-audit` locally — no HIGH findings in dependencies
- [x] Add `bandit` scan to CI pipeline — gate on high severity/high confidence
- [x] Add Syft SBOM generation (SPDX + CycloneDX) and Grype container vulnerability scanning to CI
- [x] Fix bandit HIGH findings: MD5 `usedforsecurity=False`, Jinja2 `autoescape=True`
- [x] Security fixes logged in `docs/security/SECURITY_FIXES.md`
- [ ] Schedule weekly automated scans (separate from CI)

---

## Phase 2 — Refactoring

The code is clean but has accumulated structural debts worth addressing before further feature work.

### 2.1 — Split app.py into Route Modules *(Completed 2026-02-18)*
`app.py` refactored into route modules:
```
src/intellibox/web/
├── app.py              # App factory, startup/shutdown only
├── routers/
│   ├── dashboard.py    # GET /
│   ├── actions.py      # GET/POST /actions/*
│   ├── emails.py       # GET /emails/*
│   ├── settings.py     # GET/POST /settings, /categories/*
│   ├── roster.py       # GET/POST /roster/*
│   ├── insights.py     # GET /insights
│   ├── knowledge_base.py # GET/POST /knowledge-base/*
│   ├── analytics.py    # GET /analytics
│   ├── auth.py         # GET/POST /login, /logout, /auth/*
│   ├── api.py          # GET /api/*, GET /health
│   └── test_routes.py  # Test data setup routes
```
- [x] All routers extracted
- [x] All tests still pass after extraction

### 2.2 — Service Layer Extraction
Routes currently contain inline queries and business logic. Extract:
- [ ] `ActionService` — create, edit, assign, complete, delete
- [ ] `EmailService` — list, search, pagination
- [ ] `ReportService` — consolidate `generator.py` + caching logic

Routes should: validate input → call service → return response. No raw SQL in routes.

### 2.3 — Audit DetachedInstanceError Pattern
The `create_action()` bug (accessing `.id` after session close) is a pattern risk elsewhere.
- [ ] Search all routes for `return RedirectResponse(url=f"...{obj.attr}")` patterns
- [ ] Ensure all attribute accesses happen inside `with get_session()` blocks
- [ ] Add explicit test for each fixed location

### 2.4 — Replace Custom Test Runner
`run_tests.py` solves DB cross-contamination but in a fragile way. Proper fix:
- [ ] Refactor `conftest.py` to use function-scoped fixtures with unique DB names per module
- [ ] Verify `pytest tests/` works without cross-contamination
- [ ] Remove `run_tests.py` once standard pytest works
- [ ] Update CI to use standard `pytest` invocation

### 2.5 — Fix `in_progress` Status Bug *(Completed 2026-02-20)*
`Assignment.status` CHECK constraint only allows `'assigned'`/`'completed'` but the route accepts `in_progress`, causing a DB-level 500 error.
- [x] Decision: added `in_progress` to the model CHECK constraint
- [x] Write Alembic migration (008)
- [x] Update UI to reflect available statuses (dashboard + action detail)

### 2.6 — Validate Settings on Write
`SettingsService.set_setting()` stores arbitrary JSON with no validation. Bad values surface later as confusing runtime errors.
- [ ] Define Pydantic models for each settings key
- [ ] Validate on write in `SettingsService`
- [ ] Add tests for invalid settings values

### 2.7 — Cache Template Globals
`templates.env.globals['get_program_name']` calls `SettingsService` (a DB query) on every page render.
- [ ] Store program name in app state on startup
- [ ] Invalidate cache when settings are saved
- [ ] Verify no performance regression

---

## Phase 3 — Comprehensive Testing Strategy

Current: 13 pytest modules + 165 BDD scenarios + 46 E2E tests, all passing. These are the gaps.

### 3.1 — Coverage Analysis
- [ ] Run `pytest tests/ --cov=src/intellibox --cov-report=html` and open the report
- [ ] Document current line coverage percentage: **_____%**
- [ ] Set coverage gate in CI: **80% minimum**
- [ ] Target 100% on `models.py`, `settings_service.py`, `priority_rules.py`

### 3.2 — Missing Test Categories

**Ingestion pipeline:**
- [ ] Parse a real `.eml` file end-to-end → verify Email + Action records created
- [ ] Duplicate detection (same message_id rejected)
- [ ] Malformed email handling (truncated MIME, bad encoding)
- [ ] `.msg` format parsing

**AI client:**
- [ ] Mock OpenAI response → verify `create_action_objects` applies priority rules correctly
- [ ] Confidence threshold filtering (action below threshold is dropped)
- [ ] JSON parse failure handling (malformed AI response returns empty list)
- [ ] Real client falls back to mock when API key is placeholder

**Scheduler:**
- [ ] Verify `start_scheduler()` creates job with correct cron trigger
- [ ] Verify report email is sent when triggered (mock SMTP)
- [ ] Timezone handling (verify correct UTC offset)

**Email sender:**
- [ ] Mock SMTP server (use `aiosmtpd`)
- [ ] TLS upgrade works
- [ ] Auth failure handled gracefully (logs error, returns False)
- [ ] `dry_run=True` skips send

**Priority rule engine edge cases:**
- [ ] Sender domain match with subdomain (`sub.domain.com` vs `@domain.com`)
- [ ] Multiple keywords matching (still `high`)
- [ ] Due date exactly on threshold boundary
- [ ] Empty keyword list (no crash)

### 3.3 — Property-Based Testing
- [ ] Add `hypothesis` to dev dependencies
- [ ] Priority output is always one of `{high, medium, low}` for any input
- [ ] Settings round-trip (write → read) is idempotent
- [ ] Email parsing never raises (returns `None` gracefully on any input)

### 3.4 — Load / Performance Testing
Before production, run a basic load test with `locust` or `wrk`:
- [ ] Dashboard with 1,000 emails / 5,000 actions — still fast?
- [ ] `/actions?priority=high` with filters — pagination query performant?
- [ ] Report generation time as data grows
- [ ] Document baseline response times: **p50=___ p95=___ p99=___**

### 3.5 — Security Testing *(Partially Complete)*
- [x] Run `bandit -r src/` and address HIGH findings *(2 found and fixed — see docs/security/SECURITY_FIXES.md)*
- [x] Run `pip-audit` — no unresolved HIGH CVEs
- [x] Run Syft/Grype container scan — no high-severity fixable CVEs
- [ ] (After auth is added) Test authentication bypass attempts
- [ ] Verify 404 responses don't leak system info

### 3.6 — BDD Expansion
- [ ] Excel roster upload (`POST /roster/upload` with `.xlsx` file)
- [ ] Email search actually filters results (assert non-matching email not in page)
- [ ] Pagination boundary (last page + 1 returns 200 with empty list)
- [ ] Report page with AI data (verify insight sections render, not just 200)
- [ ] Settings persistence (save → reload → values still shown)

---

## Phase 4 — Database & Scalability

### 4.1 — Migrate SQLite → PostgreSQL
SQLite limitations for production:
- File-level write locking (concurrent POSTs can timeout)
- Not shareable across processes/containers
- No network access

Steps:
- [ ] Add `psycopg2-binary` (or `asyncpg`) to dependencies
- [ ] Update `DATABASE_URL` format in `.env.example`
- [ ] Provision PostgreSQL instance (RDS, Cloud SQL, or self-hosted)
- [ ] Run `alembic upgrade head` against Postgres instance
- [ ] Update `conftest.py` to support both SQLite (dev) and Postgres (CI/prod)
- [ ] Run full test suite against Postgres — all passing
- [ ] The Docker Compose `postgres` profile already exists — just activate it

### 4.2 — Connection Pooling
- [ ] Add pool configuration to `create_engine()`:
  ```python
  create_engine(url, pool_size=10, max_overflow=20, pool_pre_ping=True)
  ```
- [ ] `pool_pre_ping=True` handles stale connections automatically

### 4.3 — Database Backups
- [ ] Define RPO (Recovery Point Objective) — how much data loss is acceptable?
- [ ] Configure automated daily snapshots (RDS/Cloud SQL) or `pg_dump` cron
- [ ] Ship backups to S3 or blob storage
- [ ] **Test the restore** — schedule a quarterly restore drill

### 4.4 — Migrations in Production
- [ ] Decide: auto-run migrations on container startup OR manual operator step
- [ ] Recommended: `init` container runs `alembic upgrade head` before app starts
- [ ] App container waits for DB readiness (`wait-for-it.sh` pattern)
- [ ] Document rollback procedure for failed migrations

### 4.5 — Query Performance Review
- [ ] Run `EXPLAIN ANALYZE` on: dashboard stats, actions list with filters, report generation
- [ ] Add indexes where needed (candidates: `actions.category`, `assignments.assigned_to`)
- [ ] Document any query changes and their before/after times

---

## Phase 5 — CI/CD Pipeline *(Completed 2026-02-19)*

### 5.1 — GitHub Actions Structure
```
.github/workflows/
├── ci.yml          # Every push: lint, test, container, security, deploy
└── deploy-full.yml # Manual trigger: full rebuild deploy
```

### 5.2 — CI Pipeline (`ci.yml`) *(Completed)*
Triggered on: every push to any branch. All 3 test jobs run in parallel (no lint gating):

- [x] **lint:** `ruff check src/ tests/` — fast lint check
- [x] **test:** Full pytest suite (13 modules + BDD + E2E) + pip-audit dependency CVE scan + bandit static security analysis
- [x] **container:** Build IronBank UBI 9 image, run unit tests in container, start prod container, BDD integration tests against live container, Syft SBOM generation (SPDX + CycloneDX), Grype vulnerability scan
- [x] **deploy:** Auto-deploy to EC2 pilot on push to `main` (needs all 3 jobs above)

### 5.3 — CD Pipeline *(Completed)*
Deploy is integrated into `ci.yml` as the final job:
- [x] SSH into EC2 pilot instance
- [x] Pull latest code, build container with Podman, start with health check
- [x] Generate systemd service for auto-restart
- [x] Verify external HTTPS endpoint
- [x] IronBank registry credentials passed securely via GitHub Secrets

### 5.4 — Branch Strategy
Currently using direct push to `main` with CI gating. Future improvement:
- [ ] Enable branch protection on `main`: require PR, require CI, no force push
- [ ] Document branch strategy in `CONTRIBUTING.md`

### 5.5 — Versioning
- [x] `/health` endpoint returns current version from package metadata
- [ ] Adopt semantic versioning (`MAJOR.MINOR.PATCH`)
- [ ] Tag releases: `git tag v1.0.0`
- [ ] Docker image tagged with both git SHA and semantic version

### 5.6 — Weekly Security Scan
- [ ] Scheduled `pip-audit` + Grype scan (separate workflow)
- [ ] Auto-open GitHub Issue if new HIGH CVEs found

---

## Phase 6 — Observability & Monitoring

### 6.1 — Structured Logging
Replace plain-text formatter with JSON logging for production:
```json
{"timestamp": "...", "level": "INFO", "logger": "intellibox.web.app", "message": "Action created", "action_id": 42}
```
- [ ] Add `LOG_FORMAT=json` env var to toggle between human-readable (dev) and JSON (prod)
- [ ] Update `src/intellibox/utils/logging.py` to support both formats

### 6.2 — Log Aggregation
Choose based on deployment target:
- **AWS:** CloudWatch Logs (automatic with ECS + awslogs driver)
- **Self-hosted:** Loki + Grafana (free, Docker-composable)
- **SaaS:** Papertrail or Logtail (simple, cheap for small teams)

- [ ] Target chosen: **_____________**
- [ ] Logs flowing to aggregation service
- [ ] Retention policy set (recommend 90 days)
- [ ] Alert configured for `ERROR` level events

### 6.3 — Error Tracking (Sentry)
- [ ] Create Sentry project (free tier sufficient)
- [ ] Add `sentry-sdk[fastapi]` to dependencies
- [ ] Add `SENTRY_DSN` env var
- [ ] Initialize in `app.py` startup
- [ ] Verify errors appear in Sentry dashboard
- [ ] Configure Slack/email notification for new error types

### 6.4 — Health & Readiness Endpoints
Expand the existing `/health` endpoint:

**`GET /health`** (liveness — is the process running?)
```json
{"status": "healthy", "version": "1.2.3", "timestamp": "..."}
```

**`GET /ready`** (readiness — is the app ready for traffic?)
```json
{"status": "ready", "db": "connected", "scheduler": "running"}
```
- [ ] Implement `/ready` endpoint
- [ ] Fix Dockerfile healthcheck (current syntax is broken):
  ```dockerfile
  HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
      CMD curl -f http://localhost:8000/health || exit 1
  ```
- [ ] Configure ECS/Kubernetes liveness and readiness probes

### 6.5 — Metrics (Optional, Post-MVP)
- [ ] Add `prometheus-fastapi-instrumentator` (auto-instruments all routes)
- [ ] Deploy Prometheus + Grafana (or Grafana Cloud free tier)
- [ ] Dashboard: requests/sec, P95 latency, error rate, actions created/day, AI API latency

### 6.6 — Alerting
Minimum alerts:
- [ ] App down (health check failing >2 min) → PagerDuty/Slack
- [ ] Error rate spike (>5 errors/min) → Slack
- [ ] OpenAI API errors (quota/auth) → Slack
- [ ] Nightly report failed to send → email to admin
- [ ] Disk space on DB volume >80% → Slack

---

## Phase 7 — Feature Improvements

Not blockers, but meaningful product improvements.

### 7.1 — Audit Log
Record every write operation (create, assign, complete, change priority, delete, settings change):

| Column | Type | Notes |
|--------|------|-------|
| `who` | VARCHAR | IP until auth added; user identity after |
| `what` | VARCHAR | e.g. `action.assigned`, `settings.updated` |
| `when` | DateTime | UTC |
| `details` | JSON | `{old: ..., new: ...}` |
| `target_id` | INT | ID of affected record |

- [ ] Design `audit_log` table and write Alembic migration
- [ ] Add audit hook to all write operations (service layer)
- [ ] Add `/audit` admin page (if auth implemented)
- [ ] BDD tests for audit log entries

### 7.2 — Email Notifications on Assignment
When an action is assigned, notify the assignee by email.
- [ ] `send_assignment_email(action, assignee_email)` function in `email_sender.py`
- [ ] Call after successful assignment in `ActionService`
- [ ] Add `NOTIFY_ON_ASSIGN=true/false` env var toggle
- [ ] BDD test: assign action → verify email sent (mock SMTP)

### 7.3 — Action Comment Thread
Replace single `Assignment.notes` text field with a full comment thread per action.
- [ ] Design `comments` table: `action_id, author, body, created_at`
- [ ] Alembic migration
- [ ] Show comment thread on action detail page
- [ ] POST endpoint to add comment
- [ ] BDD tests for comment CRUD

### 7.4 — Bulk Operations on Actions List
Select multiple actions and:
- [ ] Bulk assign (all to one person)
- [ ] Bulk mark complete
- [ ] Bulk change priority
- [ ] Bulk export to CSV
- [ ] BDD tests for each bulk operation

### 7.5 — `in_progress` Status
See also Phase 2.5. This is the feature component:
- [ ] Add `in_progress` to `Assignment.status` (Alembic migration)
- [ ] Add "Mark In Progress" button to action detail page
- [ ] Show in-progress actions distinctly on dashboard
- [ ] BDD tests for the new status transitions

### 7.6 — Overdue Escalation
- [ ] Scheduled job: find actions where `due_date < today` and `status = assigned`
- [ ] Send reminder email to assignee
- [ ] Optionally alert program manager
- [ ] `ESCALATION_ENABLED=true/false` env var toggle
- [ ] BDD test: overdue action → escalation email sent

### 7.7 — Re-process Email via Web UI
Currently re-processing requires CLI commands.
- [ ] Add "Re-process with AI" button on email detail page
- [ ] `POST /emails/{id}/reprocess` route
- [ ] BDD test: button click → new actions extracted
- [ ] Guard against duplicate actions (idempotent re-processing)

### 7.8 — API Documentation
FastAPI auto-generates OpenAPI docs at `/docs`. Decide:
- [ ] Decision: expose docs or disable in production?
  - Expose: document, secure behind auth, announce to integrators
  - Disable: `FastAPI(docs_url=None, redoc_url=None)` in production config
- [ ] Write `API.md` documenting all endpoints regardless of UI decision

### 7.9 — Data Export *(Partially Complete 2026-02-20)*
- [x] `GET /actions/export.csv` → download filtered actions as CSV *(completed 2026-02-20)*
- [x] Export button on actions page respects active filters
- [x] Tests: content-type, attachment header, filter accuracy, empty DB
- [ ] "Download Report" button on report page → PDF or CSV

### 7.10 — Multi-Program Support *(Future / Optional)*
If the tool is used across multiple programs/contracts:
- [ ] Design `Program` model (separate namespaces for actions, rosters, settings)
- [ ] Alembic migration
- [ ] UI for switching between programs
- [ ] (This is a significant architectural change — scope carefully)

---

## Phase 8 — Documentation

### 8.1 — API Reference
- [ ] Write `docs/API.md` or link to auto-generated Swagger UI
- [ ] Document every endpoint: method, path, request body, response schema, error codes

### 8.2 — Architecture Decision Records (ADRs)
Create `docs/adr/` with one-page records for key decisions:
- [ ] `ADR-001-sqlite-to-postgres.md`
- [ ] `ADR-002-auth-approach.md`
- [ ] `ADR-003-mock-vs-real-ai.md`
- [ ] `ADR-004-bdd-test-strategy.md`

### 8.3 — Runbook
Create `docs/RUNBOOK.md` covering:
- [ ] How to restart the server
- [ ] How to check logs
- [ ] How to run a manual report
- [ ] How to re-process an email
- [ ] What to do if OpenAI API key is over quota
- [ ] How to add a roster member via CLI
- [ ] How to roll back a bad deployment
- [ ] How to restore from database backup

### 8.4 — ER Diagram
- [ ] Generate database schema diagram (`eralchemy2` or `mermaid` in Markdown)
- [ ] Commit to `docs/design/er_diagram.md`
- [ ] Update when new migrations are added

### 8.5 — Contributing Guide
- [ ] Create `CONTRIBUTING.md`:
  - Dev environment setup
  - How to run tests (and why `run_tests.py`)
  - Branch naming convention
  - PR process
  - How to write a BDD test for a new feature

---

## Priority Matrix

| Phase | Item | Effort | Status |
|-------|------|--------|--------|
| 0 | Rotate secrets | 1 hr | **Done** |
| 0 | Decide deployment target | 1 hr | **Done** (EC2 + Podman) |
| 1 | Auth (Option A: proxy) | 4 hrs | **Done** (nginx basic auth) |
| 1 | TLS + reverse proxy | 4 hrs | **Done** (Certbot + nginx) |
| 1 | Security scanning | 4 hrs | **Done** (pip-audit, bandit, Syft, Grype) |
| 5 | GitHub Actions CI/CD | 1 day | **Done** (4-job pipeline) |
| 1 | CSRF protection | 4 hrs | Not started |
| 4 | Migrate SQLite → PostgreSQL | 1 day | Not started |
| 6 | Sentry error tracking | 2 hrs | Not started |
| 6 | Structured JSON logging | 2 hrs | Not started |
| 2 | Split app.py into routers | 2 days | **Done** |
| 2 | Service layer extraction | 2 days | Not started |
| 2 | Fix `in_progress` status bug | 4 hrs | **Done** |
| 3 | Coverage analysis + gap filling | 1 day | Not started |
| 7 | Audit log | 1 day | Not started |
| 7 | Email notifications on assign | 4 hrs | Not started |
| 7 | Data export (CSV) | 1 day | **Done** (actions) |
| 8 | ADRs + Runbook | 1 day | Not started |

---

## Progress Tracking

| Phase | Status | Completed | Notes |
|-------|--------|-----------|-------|
| Phase 0 | Mostly complete | 2026-02-18 | Deployment target decided (EC2), secrets rotated |
| Phase 1 | Mostly complete | 2026-02-19 | Auth (nginx basic), TLS (Certbot), security scanning (pip-audit, bandit, Syft, Grype) |
| Phase 2 | Mostly complete | 2026-02-20 | Router split done, in_progress bug fixed, service layer TBD |
| Phase 3 | In progress | — | 13 modules + 165 BDD + 46 E2E, coverage % TBD |
| Phase 4 | Not started | — | Database & scalability |
| Phase 5 | **Complete** | 2026-02-19 | CI/CD pipeline: lint, test, container, security, auto-deploy |
| Phase 6 | Not started | — | Observability & monitoring |
| Phase 7 | In progress | — | CSV export done, other features TBD |
| Phase 8 | In progress | — | Documentation updates ongoing |

---

*Update this document as work is completed. Treat it as a living backlog, not a static report.*
