# EmailTools

An automated email action tracking system for fast-paced software teams.

## Overview

EmailTools helps teams manage incoming Requests for Information (RFIs), data calls, and stakeholder requests by:
- Parsing emails using AI (GPT-4) to extract actionable items
- Storing them in a database with metadata and priority rules
- Providing a web dashboard for action management and assignment
- Generating reports with AI-powered insights and program news
- Supporting a knowledge base for contextual AI prompt enrichment

## Features

- **Email Ingestion** - Process `.eml` and `.msg` files from `data/inbox/` with chain stripping and deduplication
- **AI Action Extraction** - GPT-4 identifies action items, priorities, due dates, and categories
- **Priority Rules** - Configurable rules for high-priority senders, keywords, and due date thresholds
- **Web Dashboard** - Full-featured UI at `http://localhost:8000` for managing actions, emails, and settings
- **Knowledge Base** - Upload documents (PDF, DOCX, TXT, XLSX) for AI context with TF-IDF and embedding search
- **Insights & Reports** - AI-generated executive summaries, risk radar, and recommendations
- **Team Roster** - Manage team members for action assignment
- **Analytics** - Activity trends and workload distribution charts
- **Database Maintenance** - Automated cache cleanup, log retention, VACUUM/ANALYZE
- **File Watcher** - Supervised inbox monitoring with health reporting and auto-restart
- **Container Support** - Production Dockerfile with health checks, plus test runner image

## Web Pages

| Route | Description |
|-------|-------------|
| `/` | Dashboard with global stats, unassigned actions, recent activity |
| `/actions` | Action list with filtering, sorting, bulk operations |
| `/emails` | Email archive with search and detail views |
| `/insights` | AI-generated program news and executive summary |
| `/settings` | Priority rules, categories, AI prompt configuration |
| `/knowledge-base` | Document upload and semantic search |
| `/roster` | Team member management |
| `/analytics` | Activity charts and workload analysis |
| `/health` | JSON health check (watcher status, uptime) |

## Installation

### Requirements
- Python 3.12 or higher
- OpenAI API key (for AI features; runs in demo mode without one)

### Local Setup

```bash
# Clone the repository
git clone <repository-url>
cd EmailTools

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Configure environment
cp .env.example .env
# Edit .env with your API keys and SMTP settings

# Initialize database
emailtools init

# Start the web server
emailtools web
```

### Container Setup (Podman/Docker)

```bash
# Build production image
podman build -t emailtools:latest .

# Run with docker-compose
podman-compose up -d

# Or run directly
podman run -d --name emailtools --env-file .env \
    -v ./data:/app/data:Z -p 8000:8000 emailtools:latest
```

See [Deployment Guides](docs/deployment/) for detailed container and cloud setup.

## CLI Commands

```bash
emailtools --help          # Show all commands
emailtools init            # Initialize the database
emailtools process         # Process emails from data/inbox/
emailtools web             # Start the web server (default: http://localhost:8000)
emailtools maintenance     # Run DB maintenance (cleanup caches/logs, vacuum)
emailtools actions list    # List actions (--unassigned for unassigned only)
emailtools ai process      # Run AI extraction on unprocessed emails
emailtools report generate # Preview report without sending
emailtools report send     # Send report via email
emailtools report schedule # Start nightly report scheduler
emailtools db show         # View database contents
```

## Testing

The project uses `run_tests.py` to run each test module in isolation (avoiding SQLite cross-contamination):

```bash
# Run all tests (13 modules + BDD scenarios)
python run_tests.py

# Run a specific test module
python -m pytest tests/test_web_interface.py -v

# Run BDD scenarios
behave features/
```

**Test suite**: 13 pytest modules + 165 BDD scenarios covering email processing, AI client retry logic, file watcher resilience, database maintenance, priority rules, web interface, knowledge base, and more.

### Container Testing

```bash
# Build test runner image (includes tests and dev dependencies)
# First swap .dockerignore for the test version:
cp .dockerignore .dockerignore.bak && cp .dockerignore.test .dockerignore
podman build -f Dockerfile.test -t emailtools:test-runner .
cp .dockerignore.bak .dockerignore

# Run tests inside container
podman run --rm --env-file .env.test emailtools:test-runner
```

## Project Structure

```
EmailTools/
├── src/emailtools/          # Main application code
│   ├── ingestion/          # Email parsing, file watching, chain stripping
│   ├── ai/                 # GPT-4 integration with retry logic
│   ├── reporter/           # Report generation and email sending
│   ├── knowledge/          # Knowledge base, embeddings, TF-IDF search
│   ├── web/                # FastAPI web interface and templates
│   └── utils/              # Logging, datetime utilities
├── tests/                  # 13 pytest test modules
├── features/               # 165 BDD scenarios (Behave)
├── alembic/                # Database migrations
├── docs/deployment/        # AWS, Azure, Podman deployment guides
├── Dockerfile              # Production container image
├── Dockerfile.test         # Test runner container image
├── docker-compose.yml      # Multi-service container orchestration
├── run_tests.py            # Test suite runner (isolation per module)
└── data/                   # Local data (gitignored)
    ├── inbox/             # Drop .eml/.msg files here
    ├── emails/            # Archived emails
    ├── logs/              # Rotating log files
    └── emailtools.db      # SQLite database
```

## Configuration

All configuration is managed via environment variables in `.env`:

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | Your OpenAI API key |
| `OPENAI_MODEL` | Model name (default: `gpt-4-turbo-preview`) |
| `SMTP_HOST`, `SMTP_PORT` | Email server for report sending |
| `SMTP_USER`, `SMTP_PASSWORD` | SMTP credentials |
| `REPORT_RECIPIENTS` | Comma-separated email addresses |
| `REPORT_TIME` | Nightly report time (default: `06:00`) |
| `TIMEZONE` | Timezone (default: `America/New_York`) |
| `PROGRAM_NEWS_DAYS` | Days included in program news (default: `7`) |
| `TEAM_MEMBERS` | Comma-separated team members for assignment |
| `LOG_LEVEL` | Logging level (default: `INFO`) |

## Cost Estimation

**Typical Usage** (50-100 emails/day):
- OpenAI API: ~$5-15/month
- Total: <$20/month

## License

[Your License Here]
