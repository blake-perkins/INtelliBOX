# CLAUDE.md — INtelliBOX

## Project Overview

INtelliBOX is an automated email action tracking system for fast-paced software teams. It parses emails using AI (GPT-4) to extract actionable items, stores them in a database, and provides a web dashboard for action management, assignment tracking, and AI-generated reports.

## Repository Structure

```
INtelliBOX/
├── src/intellibox/          # Main application code
│   ├── ingestion/          # Email parsing (.eml/.msg), file watching, chain stripping
│   ├── ai/                 # GPT-4 integration with retry logic, mock client for demo
│   ├── reporter/           # Report generation, program news, email sending
│   ├── knowledge/          # Knowledge base: document storage, embeddings, TF-IDF search
│   ├── web/                # FastAPI web interface
│   │   └── templates/      # Jinja2 HTML templates
│   ├── utils/              # Logging (rotating), datetime utilities
│   ├── config.py           # Pydantic settings
│   ├── models.py           # SQLAlchemy ORM models
│   ├── database.py         # Database init, maintenance, cleanup
│   ├── settings_service.py # Settings CRUD (JSON serialization)
│   ├── priority_rules.py   # Priority rule engine
│   └── cli.py              # Click CLI commands
├── tests/                  # 13 pytest modules + 45 Playwright E2E tests
│   ├── test_ai/            # AI-specific tests (priority integration)
│   ├── e2e/                # Playwright browser E2E tests (10 files)
│   └── fixtures/           # Sample .eml files
├── features/               # 165 BDD scenarios (Behave)
│   └── steps/              # Step definitions
├── data/                   # Local data (gitignored)
│   ├── inbox/             # Drop .eml/.msg files here
│   ├── emails/            # Archived emails
│   ├── logs/              # Rotating log files
│   └── intellibox.db      # SQLite database
├── alembic/               # Database migrations
├── deploy/                # Production deployment (pilot.sh, setup.sh, nginx, env templates)
├── docs/deployment/       # AWS, Azure, Podman guides
├── Dockerfile             # Production container image
├── Dockerfile.test        # Test runner container image
├── docker-compose.yml     # Multi-service orchestration
├── run_tests.py           # Test runner (isolated per module)
├── .dockerignore          # Production build excludes tests
├── .dockerignore.test     # Test build includes tests
└── pyproject.toml         # Dependencies, ruff, pytest config
```

## Current State

- **Status**: Feature-complete with web dashboard, AI integration, and container support
  - Email ingestion with chain stripping and deduplication
  - AI action extraction with configurable priority rules
  - Web dashboard: /, /actions, /emails, /insights, /settings, /knowledge-base, /roster, /analytics
  - Knowledge base with TF-IDF and embedding search
  - Database maintenance (cache cleanup, log retention, VACUUM/ANALYZE)
  - Email upload via web dashboard (.eml/.msg files)
  - File watcher with health monitoring and supervised restarts
  - AI client retry logic with exponential backoff
  - Rotating log files
  - Container support (Dockerfile, Dockerfile.test, docker-compose.yml)
  - Production deployment (deploy/ — Podman, nginx, Certbot, DuckDNS)
  - Zero-touch pilot deployment (`bash deploy/pilot.sh`)
  - CI/CD pipeline: lint, tests (unit + BDD + E2E), container build/test, auto-deploy
- **Primary branch**: `main`
- **Python**: 3.12+
- **Database**: SQLite (data/intellibox.db)

## Testing

Tests are run in isolation to avoid SQLite cross-contamination between modules:

```bash
# ALWAYS use this command to run all tests:
python run_tests.py

# NOT: pytest tests/  (causes cross-contamination errors)
```

**Test suite**: 13 pytest modules + 165 BDD scenarios (Behave) + 45 Playwright E2E tests.

E2E tests (Playwright):
```bash
# Run E2E tests only (starts its own server on port 8787):
python -m pytest tests/e2e/ -v

# Run a specific E2E test:
python -m pytest tests/e2e/test_e2e_dashboard.py::test_dashboard_overdue_expand_collapse -v

# Run E2E tests in headed mode (visible browser):
python -m pytest tests/e2e/ -v --headed

# First-time setup:
pip install -e ".[dev]" && playwright install chromium
```

Container testing:
```bash
# Swap .dockerignore, build test image, run tests
cp .dockerignore .dockerignore.bak && cp .dockerignore.test .dockerignore
podman build -f Dockerfile.test -t intellibox:test-runner .
cp .dockerignore.bak .dockerignore
podman run --rm --env-file .env.test intellibox:test-runner
```

## CLI Commands

```
intellibox init            # Initialize database
intellibox process         # Process emails from inbox
intellibox web             # Start web server (http://localhost:8000)
intellibox maintenance     # DB maintenance (cleanup, vacuum, analyze)
intellibox actions list    # List actions
intellibox ai process      # Run AI extraction
intellibox report generate # Preview report
intellibox report send     # Send report
intellibox db show         # View database
```

## Development Workflow

1. Local development uses `venv/` virtual environment
2. `pip install -e ".[dev]"` for all dependencies including test tools
3. Web server: `intellibox web` (or `./venv/Scripts/intellibox.exe web` on Windows)
4. Template changes (HTML) take effect immediately; Python changes require server restart
5. Run `python run_tests.py` before committing

## Conventions for AI Assistants

- Read existing files before proposing edits.
- Do not add features, abstractions, or refactors beyond what is requested.
- Keep changes minimal and focused on the task at hand.
- When source code is added, follow the patterns and style already established in the codebase.
- Update this file when significant project structure or workflow changes are introduced.
