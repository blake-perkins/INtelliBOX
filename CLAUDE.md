# CLAUDE.md — EmailTools

## Project Overview

EmailTools is an automated email action tracking system for fast-paced software teams. It parses emails using AI (GPT-4) to extract actionable items, stores them in a database, and generates nightly reports showing unassigned actions.

## Repository Structure

```
EmailTools/
├── src/emailtools/          # Main application code
│   ├── ingestion/          # Email parsing and file watching
│   ├── ai/                 # GPT-4 integration (Phase 2)
│   ├── reporter/           # Report generation (Phase 3)
│   ├── utils/              # Shared utilities
│   ├── config.py           # Pydantic settings
│   ├── models.py           # SQLAlchemy ORM models
│   ├── database.py         # Database initialization
│   └── cli.py              # Click CLI commands
├── tests/                  # Test suite
│   └── fixtures/
│       └── sample_emails/  # .eml files for testing
├── data/                   # Local data (gitignored)
│   ├── inbox/             # Drop .eml files here
│   ├── emails/            # Archived emails
│   └── emailtools.db      # SQLite database
├── alembic/               # Database migrations
├── pyproject.toml         # Dependencies and config
└── .env                   # Environment variables (create from .env.example)
```

## Current State

- **Status**: MVP Complete — All 3 phases implemented and tested
  - ✅ Phase 1: Email ingestion and parsing
  - ✅ Phase 2: AI action extraction (demo mode)
  - ✅ Phase 3: Nightly reporting with email summaries
- **Primary branch**: `main`
- **Next Steps**: Production deployment (OpenAI API key, SMTP config, AWS migration)

## Development Workflow

_To be updated as the project takes shape._ When setting up the project, establish:

1. A `README.md` with project description, setup instructions, and usage examples.
2. A build/dependency configuration file appropriate to the chosen language (e.g., `package.json`, `pyproject.toml`).
3. A test framework and test directory.
4. Linting and formatting configuration.
5. CI/CD pipeline (e.g., GitHub Actions).

## Conventions for AI Assistants

- Read existing files before proposing edits.
- Do not add features, abstractions, or refactors beyond what is requested.
- Keep changes minimal and focused on the task at hand.
- When source code is added, follow the patterns and style already established in the codebase.
- Update this file when significant project structure or workflow changes are introduced.
