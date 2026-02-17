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

## Local Development with Podman

### Build Image
```bash
# Same as Docker
podman build -t emailtools:latest .

# Or use Dockerfile explicitly
podman build -f Dockerfile -t emailtools:latest .
```

### Run Container
```bash
# Run scheduler
podman run -d \
    --name emailtools \
    --env-file .env \
    -v ./data:/app/data:Z \
    emailtools:latest \
    emailtools report schedule

# Run one-time processing
podman run --rm \
    --env-file .env \
    -v ./data:/app/data:Z \
    emailtools:latest \
    emailtools process
```

**Note**: The `:Z` flag is important for SELinux systems - it relabels the volume content.

### Using Podman Compose

```bash
# Install podman-compose
pip install podman-compose

# Run services (same as docker-compose)
podman-compose up -d

# View logs
podman-compose logs -f

# Stop services
podman-compose down
```

---

## Rootless Containers (Recommended)

Podman's rootless mode provides better security:

```bash
# Run as non-root user (default with Podman)
podman run -d \
    --name emailtools \
    --userns=keep-id \
    --env-file .env \
    -v ./data:/app/data:Z \
    emailtools:latest

# Check running containers
podman ps

# View logs
podman logs -f emailtools
```

---

## Podman Pods (Multi-Container Setup)

Podman pods group containers together (like docker-compose):

```bash
# Create a pod
podman pod create --name emailtools-pod -p 8080:8080

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

# Pod containers share network namespace (can talk via localhost)
```

---

## AWS Deployment with Podman

### 1. Build for AWS (ARM64 for Graviton)
```bash
# Build multi-arch image
podman build \
    --platform linux/amd64,linux/arm64 \
    --manifest emailtools:latest \
    -f Dockerfile \
    .

# Or build specifically for ARM64 (AWS Graviton)
podman build \
    --platform linux/arm64 \
    -t emailtools:latest-arm64 \
    .
```

### 2. Push to AWS ECR
```bash
# Login to ECR (same as Docker)
aws ecr get-login-password --region us-east-1 | \
    podman login --username AWS --password-stdin \
    YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com

# Tag image
podman tag emailtools:latest \
    YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/emailtools:latest

# Push to ECR
podman push \
    YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/emailtools:latest
```

### 3. Use Deployment Script with Podman
```bash
# Set Podman as container engine
export CONTAINER_ENGINE=podman

# Run deployment
./aws/deploy-podman.sh
```

---

## Systemd Integration (Linux Only)

Generate systemd service files for automatic startup:

```bash
# Generate systemd unit file
podman generate systemd \
    --new \
    --name emailtools \
    --files

# Move to systemd directory
sudo cp container-emailtools.service /etc/systemd/system/

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable container-emailtools.service
sudo systemctl start container-emailtools.service

# Check status
sudo systemctl status container-emailtools.service
```

---

## Generate Kubernetes YAML

Convert Podman pods to Kubernetes deployments:

```bash
# Generate Kubernetes YAML from pod
podman generate kube emailtools-pod > emailtools-k8s.yaml

# Deploy to Kubernetes
kubectl apply -f emailtools-k8s.yaml

# Or deploy to AWS EKS
eksctl create cluster --name emailtools --region us-east-1
kubectl apply -f emailtools-k8s.yaml
```

---

## Podman vs Docker Commands

| Task | Docker | Podman |
|------|--------|--------|
| Build | `docker build` | `podman build` |
| Run | `docker run` | `podman run` |
| Push | `docker push` | `podman push` |
| Compose | `docker-compose up` | `podman-compose up` |
| Login | `docker login` | `podman login` |
| Images | `docker images` | `podman images` |
| Containers | `docker ps` | `podman ps` |
| Logs | `docker logs` | `podman logs` |
| Exec | `docker exec` | `podman exec` |

**They're identical!** Just replace `docker` with `podman`.

---

## Aliases for Docker Compatibility

Add to your `.bashrc` or `.zshrc`:

```bash
alias docker=podman
alias docker-compose=podman-compose
```

Now all Docker commands work seamlessly!

---

## Troubleshooting

### Permission Denied on Volumes
```bash
# Use :Z flag for SELinux relabeling
podman run -v ./data:/app/data:Z emailtools:latest

# Or disable SELinux (not recommended)
sudo setenforce 0
```

### Podman Machine Issues (macOS/Windows)
```bash
# Restart machine
podman machine stop
podman machine start

# Check machine status
podman machine list

# SSH into machine
podman machine ssh
```

### Registry Authentication
```bash
# Store credentials
podman login registry.example.com

# Check stored credentials
cat ~/.config/containers/auth.json

# Logout
podman logout registry.example.com
```

---

## Performance Tips

1. **Use rootless mode** for better security
2. **Enable cgroup v2** for better resource limits
3. **Use `:Z` volume flag** on SELinux systems
4. **Build with `--layers=false`** for smaller images
5. **Use multi-stage builds** to reduce image size

---

## Security Best Practices

1. **Run rootless** whenever possible
2. **Use `--read-only`** for immutable containers
3. **Limit capabilities** with `--cap-drop=ALL`
4. **Use seccomp profiles** for syscall filtering
5. **Scan images** with `podman scan` (requires Trivy)

---

## Next Steps

1. Test locally with `podman run`
2. Use `podman-compose` for multi-container setup
3. Generate Kubernetes YAML for orchestration
4. Deploy to AWS ECS/EKS
5. Set up CI/CD with Podman

For Docker-specific guides, see `AWS_DEPLOYMENT.md` (commands are identical).
