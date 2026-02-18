# Podman Deployment Guide for EmailTools

Podman is a daemonless container engine that's a drop-in replacement for Docker. This guide covers using Podman for local development and AWS deployment.

## Why Podman?

- **Daemonless**: No background daemon required
- **Rootless**: Run containers without root privileges
- **Docker-compatible**: Uses same commands and Dockerfiles
- **Security**: Better isolation and security model
- **Kubernetes-ready**: Generate Kubernetes YAML from pods

## Installation

### Windows
```powershell
# Install via WSL2
wsl --install
wsl --set-default-version 2

# Inside WSL2:
sudo apt-get update
sudo apt-get install -y podman

# Or use Podman Desktop
winget install RedHat.Podman-Desktop
```

### macOS
```bash
brew install podman
podman machine init
podman machine start
```

### Linux
```bash
# Debian/Ubuntu
sudo apt-get install -y podman

# RHEL/Fedora
sudo dnf install -y podman
```

---

## Container Images

EmailTools provides two container images:

| Image | Dockerfile | Purpose |
|-------|-----------|---------|
| `emailtools:latest` | `Dockerfile` | Production — runs web server with health check |
| `emailtools:test-runner` | `Dockerfile.test` | CI/testing — runs full test suite and exits |

The production `.dockerignore` excludes tests for a smaller image. The test build uses `.dockerignore.test` which includes tests and BDD features.

---

## Local Development with Podman

### Build Production Image
```bash
podman build -t emailtools:latest .
```

### Run Web Server
```bash
podman run -d \
    --name emailtools \
    --env-file .env \
    -v ./data:/app/data:Z \
    -p 8000:8000 \
    emailtools:latest

# Dashboard available at http://localhost:8000
# Health check at http://localhost:8000/health
```

### Run Test Suite
```bash
# Build test image (swap .dockerignore first)
cp .dockerignore .dockerignore.bak && cp .dockerignore.test .dockerignore
podman build -f Dockerfile.test -t emailtools:test-runner .
cp .dockerignore.bak .dockerignore

# Run all 13 test modules + 165 BDD scenarios
podman run --rm --env-file .env.test emailtools:test-runner
```

### Run One-Off Commands
```bash
podman run --rm --env-file .env -v ./data:/app/data:Z \
    emailtools:latest emailtools process

podman run --rm --env-file .env -v ./data:/app/data:Z \
    emailtools:latest emailtools maintenance
```

**Note**: The `:Z` flag is important for SELinux systems — it relabels the volume content.

### Using Podman Compose

```bash
pip install podman-compose

# Run production web server
podman-compose up -d

# View logs
podman-compose logs -f

# Stop services
podman-compose down
```

---

## Docker Compose Services

The `docker-compose.yml` defines these services:

| Service | Profile | Description |
|---------|---------|-------------|
| `emailtools` | (default) | Production web server on port 8000 |
| `emailtools-test` | `testing` | Web server with test config on port 8001 |
| `test-runner` | `ci` | Runs test suite and exits |
| `postgres` | `production` | PostgreSQL 16 for production use |

```bash
# Run production
podman-compose up -d

# Run with PostgreSQL
podman-compose --profile production up -d

# Run test suite
podman-compose --profile ci run --rm test-runner
```

---

## Rootless Containers (Recommended)

Podman's rootless mode provides better security:

```bash
podman run -d \
    --name emailtools \
    --userns=keep-id \
    --env-file .env \
    -v ./data:/app/data:Z \
    -p 8000:8000 \
    emailtools:latest
```

---

## Podman Pods (Multi-Container Setup)

Podman pods group containers together (like docker-compose):

```bash
# Create a pod
podman pod create --name emailtools-pod -p 8000:8000

# Run PostgreSQL in pod
podman run -d \
    --pod emailtools-pod \
    --name postgres \
    -e POSTGRES_DB=emailtools \
    -e POSTGRES_USER=emailtools \
    -e POSTGRES_PASSWORD=changeme \
    -v postgres-data:/var/lib/postgresql/data \
    postgres:16-alpine

# Run EmailTools in same pod
podman run -d \
    --pod emailtools-pod \
    --name emailtools \
    --env-file .env \
    -v ./data:/app/data:Z \
    emailtools:latest
```

---

## Health Monitoring

The production container includes a health check endpoint:

```bash
# Check health
curl http://localhost:8000/health
```

Returns JSON with application status and file watcher health:
```json
{
  "status": "healthy",
  "timestamp": "2026-02-18T15:50:35.102003",
  "watcher": {
    "is_alive": true,
    "last_poll_at": "2026-02-18T15:50:32.982584",
    "error_count": 0,
    "files_processed": 0
  }
}
```

The Dockerfile includes a `HEALTHCHECK` directive using this endpoint. Note: Podman with OCI format shows a warning about HEALTHCHECK — this is cosmetic and the health check works correctly with Docker or when using `--format docker` with Podman.

---

## AWS Deployment with Podman

### 1. Build for AWS (ARM64 for Graviton)
```bash
podman build \
    --platform linux/amd64,linux/arm64 \
    --manifest emailtools:latest \
    -f Dockerfile \
    .
```

### 2. Push to AWS ECR
```bash
aws ecr get-login-password --region us-east-1 | \
    podman login --username AWS --password-stdin \
    YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com

podman tag emailtools:latest \
    YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/emailtools:latest

podman push \
    YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/emailtools:latest
```

---

## Systemd Integration (Linux Only)

```bash
podman generate systemd --new --name emailtools --files
sudo cp container-emailtools.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now container-emailtools.service
```

---

## Podman vs Docker Commands

| Task | Docker | Podman |
|------|--------|--------|
| Build | `docker build` | `podman build` |
| Run | `docker run` | `podman run` |
| Push | `docker push` | `podman push` |
| Compose | `docker compose up` | `podman-compose up` |
| Login | `docker login` | `podman login` |

**They're identical!** Just replace `docker` with `podman`.

---

## Troubleshooting

### Permission Denied on Volumes
```bash
podman run -v ./data:/app/data:Z emailtools:latest
```

### Podman Machine Issues (macOS/Windows)
```bash
podman machine stop
podman machine start
podman machine list
```

### HEALTHCHECK Warning
```
HEALTHCHECK is not supported for OCI image format and will be ignored
```
This is cosmetic. Use `podman build --format docker` to suppress it, or ignore — the health endpoint still works at `/health`.
