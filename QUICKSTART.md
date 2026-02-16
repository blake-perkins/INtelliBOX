# EmailTools - Quick Start Guide

Get EmailTools running in containers in 5 minutes using Podman or Docker.

## Prerequisites

Choose one:
- **Podman** (recommended): `brew install podman` or `winget install RedHat.Podman-Desktop`
- **Docker**: `brew install docker` or install Docker Desktop

## Local Development

### 1. Clone and Configure

```bash
# Navigate to project
cd EmailTools

# Copy environment template
cp .env.example .env

# Edit .env with your settings
nano .env
```

Required settings:
```bash
OPENAI_API_KEY=sk-proj-your-key-here
SMTP_HOST=smtp.gmail.com
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
REPORT_RECIPIENTS=team@example.com
```

### 2. Build and Run (Podman)

```bash
# Build image
podman build -t emailtools:latest .

# Run scheduler (sends nightly reports)
podman run -d \
    --name emailtools \
    --env-file .env \
    -v ./data:/app/data:Z \
    emailtools:latest \
    emailtools report schedule

# Or use podman-compose
pip install podman-compose
podman-compose up -d
```

### 3. Build and Run (Docker)

```bash
# Build image
docker build -t emailtools:latest .

# Run with docker-compose
docker-compose up -d

# View logs
docker-compose logs -f
```

### 4. Test the System

```bash
# Initialize database
podman exec emailtools emailtools init

# Process test emails
podman exec emailtools emailtools process

# Generate test report
podman exec emailtools emailtools report generate

# View actions
podman exec emailtools emailtools actions list
```

## Production Deployment

### AWS ECS Fargate

```bash
# Install AWS CLI
pip install awscli

# Configure AWS credentials
aws configure

# Deploy to AWS
chmod +x aws/deploy-podman.sh
./aws/deploy-podman.sh
```

### Using Docker Compose for Production

```bash
# Start with PostgreSQL
docker-compose --profile production up -d

# Run database migration
docker-compose exec emailtools alembic upgrade head

# Check logs
docker-compose logs -f emailtools
```

## Common Commands

### Container Management

```bash
# Podman
podman ps                    # List running containers
podman logs -f emailtools    # View logs
podman stop emailtools       # Stop container
podman rm emailtools         # Remove container
podman images                # List images

# Docker (same commands, replace 'podman' with 'docker')
docker ps
docker logs -f emailtools
docker stop emailtools
```

### Application Commands

```bash
# Inside container
podman exec emailtools emailtools --help

# Process emails
podman exec emailtools emailtools process

# Generate report
podman exec emailtools emailtools report send --dry-run

# View database
podman exec emailtools emailtools db show

# List actions
podman exec emailtools emailtools actions list
```

## Updating

```bash
# Pull latest code
git pull

# Rebuild image
podman build -t emailtools:latest .

# Recreate container
podman stop emailtools
podman rm emailtools
podman run -d --name emailtools --env-file .env -v ./data:/app/data:Z emailtools:latest
```

## Troubleshooting

### Container won't start
```bash
# Check logs
podman logs emailtools

# Check if port is in use
lsof -i :8080

# Verify .env file
cat .env | grep -v PASSWORD
```

### Database connection errors
```bash
# Check database URL
podman exec emailtools env | grep DATABASE_URL

# Test connection
podman exec emailtools python -c "from emailtools.database import get_session; print('OK')"
```

### Permission errors (Podman)
```bash
# Use :Z flag for volumes
podman run -v ./data:/app/data:Z emailtools:latest

# Or change ownership
sudo chown -R $USER:$USER data/
```

## Next Steps

1. **Configure IMAP** for automatic email ingestion
2. **Set up monitoring** with CloudWatch or Prometheus
3. **Enable backups** for database and email storage
4. **Configure domain** for SES email sending
5. **Set up CI/CD** with GitHub Actions

## Documentation

- [AWS Deployment Guide](AWS_DEPLOYMENT.md)
- [Podman Guide](PODMAN.md)
- [Main README](README.md)
- [Architecture Plan](.claude/plans/reactive-wondering-cascade.md)

## Support

- GitHub Issues: https://github.com/your-org/emailtools/issues
- Email: support@example.com
