# INtelliBOX - Quick Start Guide

Get INtelliBOX running in containers in 5 minutes using Podman or Docker.

## Prerequisites

Choose one:
- **Podman** (recommended): `brew install podman` or `winget install RedHat.Podman-Desktop`
- **Docker**: `brew install docker` or install Docker Desktop

## Local Development (No Container)

```bash
cd INtelliBOX
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env      # Edit with your settings
intellibox init
intellibox web             # Dashboard at http://localhost:8000
```

## Container Setup

### 1. Configure Environment

```bash
cp .env.example .env
```

Required settings in `.env`:
```bash
OPENAI_API_KEY=sk-proj-your-key-here
SMTP_HOST=smtp.gmail.com
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
REPORT_RECIPIENTS=team@example.com
```

### 2. Build and Run (Podman)

```bash
# Build production image
podman build -t intellibox:latest .

# Run with compose
pip install podman-compose
podman-compose up -d

# Or run directly
podman run -d --name intellibox --env-file .env \
    -v ./data:/app/data:Z -p 8000:8000 intellibox:latest
```

### 3. Build and Run (Docker)

```bash
docker build -t intellibox:latest .
docker compose up -d
docker compose logs -f
```

### 4. Verify

```bash
# Check health
curl http://localhost:8000/health

# Open dashboard
open http://localhost:8000
```

The entrypoint automatically runs database migrations on startup.

## Running Tests in Container

```bash
# Build test runner (includes test suite and dev dependencies)
cp .dockerignore .dockerignore.bak && cp .dockerignore.test .dockerignore
podman build -f Dockerfile.test -t intellibox:test-runner .
cp .dockerignore.bak .dockerignore

# Run all 13 test modules + 165 BDD scenarios
podman run --rm --env-file .env.test intellibox:test-runner
```

Or using docker-compose:
```bash
docker compose --profile ci run --rm test-runner
```

## Application Commands (Inside Container)

```bash
podman exec intellibox intellibox --help
podman exec intellibox intellibox process          # Process emails
podman exec intellibox intellibox maintenance      # DB cleanup/vacuum
podman exec intellibox intellibox actions list     # List actions
podman exec intellibox intellibox report generate  # Preview report
podman exec intellibox intellibox db show          # View database
```

## Web Dashboard Pages

| Route | Description |
|-------|-------------|
| `/` | Dashboard with stats and unassigned actions |
| `/actions` | Action list with filtering and sorting |
| `/emails` | Email archive and detail views |
| `/insights` | AI-generated program news and summary |
| `/settings` | Priority rules, categories, AI config |
| `/knowledge-base` | Document upload and search |
| `/roster` | Team member management |
| `/analytics` | Activity charts |
| `/health` | JSON health check |

## Production with PostgreSQL

```bash
# Start with PostgreSQL profile
docker compose --profile production up -d

# Migrations run automatically via entrypoint
```

## Updating

```bash
git pull
podman build -t intellibox:latest .
podman-compose down && podman-compose up -d
```

## Troubleshooting

### Container won't start
```bash
podman logs intellibox     # Check logs
curl http://localhost:8000/health  # Check health endpoint
```

### Database errors
```bash
podman exec intellibox intellibox init  # Reinitialize tables
podman exec intellibox intellibox maintenance  # Run cleanup
```

### Permission errors (Podman/SELinux)
```bash
# Use :Z flag for volumes
podman run -v ./data:/app/data:Z intellibox:latest
```

## Documentation

- [Podman Guide](PODMAN.md)
- [AWS Deployment](AWS_DEPLOYMENT.md)
- [Azure Deployment](AZURE_DEPLOYMENT.md)
