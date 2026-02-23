#!/bin/bash
# INtelliBOX EC2 Deployment Setup
# Run on a fresh Ubuntu 24.04 EC2 instance
#
# Usage:
#   1. Clone the repo:  git clone https://github.com/blake-perkins/INtelliBOX.git
#   2. cd INtelliBOX/deploy
#   3. cp .env.production.example .env.production  (then fill in real values)
#   4. chmod +x setup.sh && sudo ./setup.sh
#
set -euo pipefail

# Print each command before executing (helps diagnose failures)
trap 'echo ""; echo "ERROR: Setup failed at line $LINENO. See output above for details."; exit 1' ERR

# ── Load config ─────────────────────────────────────────────────────────────

if [ ! -f .env.production ]; then
    echo "ERROR: .env.production not found."
    echo "Copy .env.production.example to .env.production and fill in your values first."
    exit 1
fi

# Source just the DOMAIN and DUCKDNS_TOKEN for setup
DOMAIN=$(grep '^DOMAIN=' .env.production | cut -d'=' -f2)
DUCKDNS_TOKEN=$(grep '^DUCKDNS_TOKEN=' .env.production | cut -d'=' -f2)

if [ -z "$DOMAIN" ] || [ "$DOMAIN" = "your-name.duckdns.org" ]; then
    echo "ERROR: Set a real DOMAIN in .env.production"
    exit 1
fi

if [ -z "$DUCKDNS_TOKEN" ] || [ "$DUCKDNS_TOKEN" = "your-duckdns-token" ]; then
    echo "ERROR: Set a real DUCKDNS_TOKEN in .env.production"
    exit 1
fi

SUBDOMAIN=$(echo "$DOMAIN" | sed 's/\.duckdns\.org$//')

# REPO_ROOT can be set by cloud-init; defaults to parent of this script's directory
REPO_ROOT="${REPO_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"

echo "=== INtelliBOX Deployment Setup ==="
echo "Domain: $DOMAIN"
echo ""

# ── Create swap file (needed for t3.micro / 1GB instances) ────────────────

if [ ! -f /swapfile ]; then
    echo "=== Creating 2GB swap file ==="
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    echo "Swap enabled: $(swapon --show)"
else
    echo "=== Swap already exists ==="
    swapon /swapfile 2>/dev/null || true
fi

# ── Install Podman ──────────────────────────────────────────────────────────

echo "=== Installing Podman ==="
apt-get update
apt-get install -y podman

echo "Podman version: $(podman --version)"

# ── Install nginx ───────────────────────────────────────────────────────────

echo "=== Installing nginx ==="
apt-get install -y nginx

# ── Install Certbot ─────────────────────────────────────────────────────────

echo "=== Installing Certbot ==="
apt-get install -y certbot python3-certbot-nginx

# ── Set up DuckDNS ──────────────────────────────────────────────────────────

echo "=== Setting up DuckDNS ==="

# Update DNS now (non-fatal — pilot.sh already updated DNS before launching)
DUCKDNS_RESULT=$(curl -sf "https://www.duckdns.org/update?domains=${SUBDOMAIN}&token=${DUCKDNS_TOKEN}&ip=" 2>/dev/null || echo "FAILED")
echo "  DuckDNS response: $DUCKDNS_RESULT"
if [ "$DUCKDNS_RESULT" != "OK" ]; then
    echo "  WARNING: DuckDNS update failed. DNS may have been updated by pilot.sh already."
fi

# Set up cron to update every 5 minutes
CRON_LINE="*/5 * * * * curl -s 'https://www.duckdns.org/update?domains=${SUBDOMAIN}&token=${DUCKDNS_TOKEN}&ip=' > /dev/null 2>&1"
(crontab -l 2>/dev/null | grep -v duckdns; echo "$CRON_LINE") | crontab -
echo "DuckDNS cron installed"

# ── Configure nginx ─────────────────────────────────────────────────────────

echo "=== Configuring nginx ==="

# Install nginx config with domain substituted
sed "s/\${DOMAIN}/$DOMAIN/g" nginx/intellibox.conf > /etc/nginx/sites-available/intellibox

# Disable default site, enable ours
rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/intellibox /etc/nginx/sites-enabled/intellibox

# ── Obtain SSL certificate ──────────────────────────────────────────────────

echo "=== Obtaining SSL certificate ==="
echo ""
echo "Certbot will now request a certificate for $DOMAIN."
echo "Make sure your EC2 security group allows inbound ports 80 and 443."
echo ""

# Temporarily set up a simple HTTP config for certbot
cat > /etc/nginx/sites-available/intellibox-temp <<EOF
server {
    listen 80;
    server_name $DOMAIN;
    location / { return 200 'ok'; }
}
EOF
ln -sf /etc/nginx/sites-available/intellibox-temp /etc/nginx/sites-enabled/intellibox
nginx -t && systemctl restart nginx

certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email

# Restore real config
sed "s/\${DOMAIN}/$DOMAIN/g" nginx/intellibox.conf > /etc/nginx/sites-available/intellibox
ln -sf /etc/nginx/sites-available/intellibox /etc/nginx/sites-enabled/intellibox
rm -f /etc/nginx/sites-available/intellibox-temp
nginx -t && systemctl reload nginx

echo "SSL certificate obtained and nginx configured"

# ── Build and start container ───────────────────────────────────────────────

echo "=== Building INtelliBOX container ==="

cd "$REPO_ROOT"

echo "Building container image (this may take a few minutes)..."
podman build -t intellibox:prod -f Dockerfile .
echo "Container image built successfully"

# Create data directory on host for persistence
mkdir -p /opt/intellibox/data/inbox /opt/intellibox/data/emails

# Fix ownership from inside the container (host UID mapping may differ from container)
podman run --rm --user root --entrypoint bash \
    -v /opt/intellibox/data:/app/data:Z \
    intellibox:prod \
    -c "chown -R 1000:1000 /app/data"

# Stop existing containers/pods
podman stop intellibox 2>/dev/null || true
podman rm intellibox 2>/dev/null || true
podman stop intellibox-db 2>/dev/null || true
podman rm intellibox-db 2>/dev/null || true
podman pod stop intellibox-pod 2>/dev/null || true
podman pod rm intellibox-pod 2>/dev/null || true

# Detect database backend from .env.production
DATABASE_URL=$(grep '^DATABASE_URL=' deploy/.env.production | cut -d'=' -f2-)

if echo "$DATABASE_URL" | grep -q "^postgresql"; then
    echo "=== Starting PostgreSQL + INtelliBOX (Podman pod) ==="

    POSTGRES_PASSWORD=$(grep '^POSTGRES_PASSWORD=' deploy/.env.production | cut -d'=' -f2)
    if [ -z "$POSTGRES_PASSWORD" ] || [ "$POSTGRES_PASSWORD" = "CHANGE_ME" ]; then
        echo "ERROR: Set a real POSTGRES_PASSWORD in deploy/.env.production"
        exit 1
    fi

    # Create persistent volume for PostgreSQL data
    mkdir -p /opt/intellibox/pgdata

    # Create a pod — containers in a pod share localhost networking
    podman pod create \
        --name intellibox-pod \
        -p 127.0.0.1:8000:8000

    # Start PostgreSQL container inside the pod
    podman run -d \
        --name intellibox-db \
        --pod intellibox-pod \
        --restart=always \
        -e POSTGRES_DB=intellibox \
        -e POSTGRES_USER=intellibox \
        -e POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
        -v /opt/intellibox/pgdata:/var/lib/postgresql/data:Z \
        docker.io/library/postgres:16-alpine

    # Wait for PostgreSQL to accept connections
    echo "Waiting for PostgreSQL..."
    for i in $(seq 1 30); do
        if podman exec intellibox-db pg_isready -U intellibox -q 2>/dev/null; then
            echo "PostgreSQL ready after ${i}s"
            break
        fi
        if [ "$i" -eq 30 ]; then
            echo "ERROR: PostgreSQL did not start within 30s"
            podman logs intellibox-db
            exit 1
        fi
        sleep 1
    done

    # Start INtelliBOX container inside the same pod
    podman run -d \
        --name intellibox \
        --pod intellibox-pod \
        --restart=always \
        --env-file deploy/.env.production \
        -v /opt/intellibox/data:/app/data:Z \
        intellibox:prod

else
    echo "=== Starting INtelliBOX (SQLite) ==="

    podman run -d \
        --name intellibox \
        --restart=always \
        --env-file deploy/.env.production \
        -v /opt/intellibox/data:/app/data:Z \
        -p 127.0.0.1:8000:8000 \
        intellibox:prod
fi

# Wait for health
echo "Waiting for application to start..."
for i in $(seq 1 60); do
    if curl -sf http://127.0.0.1:8000/health > /dev/null 2>&1; then
        echo "Application healthy after ${i}s"
        break
    fi
    if [ "$i" -eq 60 ]; then
        echo "WARNING: Application did not become healthy in 60s"
        echo "Check logs: podman logs intellibox"
    fi
    sleep 1
done

# ── Set up container auto-start on boot ─────────────────────────────────────

echo "=== Configuring auto-start ==="

# Generate systemd services
mkdir -p /etc/systemd/system
if echo "$DATABASE_URL" | grep -q "^postgresql"; then
    # Generate a systemd service for the whole pod
    podman generate systemd --name intellibox-pod --new --files
    mv pod-intellibox-pod.service /etc/systemd/system/
    mv container-intellibox.service /etc/systemd/system/
    mv container-intellibox-db.service /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable pod-intellibox-pod.service
else
    podman generate systemd --name intellibox --new > /etc/systemd/system/intellibox.service
    systemctl daemon-reload
    systemctl enable intellibox.service
fi

# ── Done ────────────────────────────────────────────────────────────────────

AUTH_MODE=$(grep '^AUTH_MODE=' deploy/.env.production | cut -d'=' -f2)

echo ""
echo "============================================="
echo "  INtelliBOX deployment complete!"
echo "============================================="
echo ""
echo "  URL: https://$DOMAIN"
echo ""
echo "  Useful commands:"
echo "    podman logs -f intellibox          # View app logs"
echo "    podman restart intellibox           # Restart the app"
echo "    podman exec -it intellibox bash     # Shell into container"
echo "    curl http://127.0.0.1:8000/health  # Health check"
echo "    certbot renew --dry-run             # Test cert renewal"

if echo "$DATABASE_URL" | grep -q "^postgresql"; then
    echo "    podman logs -f intellibox-db       # View PostgreSQL logs"
    echo "    podman exec -it intellibox-db psql -U intellibox  # PostgreSQL shell"
    echo ""
    echo "  Data: /opt/intellibox/data/ (app), /opt/intellibox/pgdata/ (PostgreSQL)"
else
    echo ""
    echo "  Data: /opt/intellibox/data/"
fi

echo "  nginx config: /etc/nginx/sites-available/intellibox"
echo ""
echo "  Next steps:"
echo "    1. Visit https://$DOMAIN to verify the dashboard loads"

if [ "$AUTH_MODE" = "local" ]; then
    echo "    2. Create an admin user:"
    echo "       sudo podman exec -it intellibox intellibox user create \\"
    echo "         --username admin --email admin@example.com --role admin"
    echo "    3. Log in and upload a test .eml file"
else
    echo "    2. Go to Emails page and upload a test .eml file"
    echo "    3. Check the dashboard for the email and AI-extracted actions"
fi
echo ""
