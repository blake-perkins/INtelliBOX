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

echo "=== INtelliBOX Deployment Setup ==="
echo "Domain: $DOMAIN"
echo ""

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

# Update DNS now
curl -s "https://www.duckdns.org/update?domains=${SUBDOMAIN}&token=${DUCKDNS_TOKEN}&ip=" | tee /tmp/duckdns.log
echo ""

# Set up cron to update every 5 minutes
CRON_LINE="*/5 * * * * curl -s 'https://www.duckdns.org/update?domains=${SUBDOMAIN}&token=${DUCKDNS_TOKEN}&ip=' > /dev/null 2>&1"
(crontab -l 2>/dev/null | grep -v duckdns; echo "$CRON_LINE") | crontab -
echo "DuckDNS cron installed"

# ── Configure nginx ─────────────────────────────────────────────────────────

echo "=== Configuring nginx ==="

REPO_ROOT=$(cd .. && pwd)

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

podman build -t intellibox:prod -f Dockerfile .

# Create data directory on host for persistence
mkdir -p /opt/intellibox/data/inbox /opt/intellibox/data/emails

# Stop existing container if running
podman stop intellibox 2>/dev/null || true
podman rm intellibox 2>/dev/null || true

echo "=== Starting INtelliBOX container ==="

podman run -d \
    --name intellibox \
    --restart=always \
    --env-file deploy/.env.production \
    -v /opt/intellibox/data:/app/data:Z \
    -p 127.0.0.1:8000:8000 \
    intellibox:prod

# Wait for health
echo "Waiting for container to start..."
for i in $(seq 1 30); do
    if curl -sf http://127.0.0.1:8000/health > /dev/null 2>&1; then
        echo "Container healthy after ${i}s"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "WARNING: Container did not become healthy in 30s"
        echo "Check logs: podman logs intellibox"
    fi
    sleep 1
done

# ── Set up container auto-start on boot ─────────────────────────────────────

echo "=== Configuring auto-start ==="

# Generate systemd service for the container
mkdir -p /etc/systemd/system
podman generate systemd --name intellibox --new > /etc/systemd/system/intellibox.service
systemctl daemon-reload
systemctl enable intellibox.service

# ── Done ────────────────────────────────────────────────────────────────────

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
echo ""
echo "  Data is stored at: /opt/intellibox/data/"
echo "  nginx config: /etc/nginx/sites-available/intellibox"
echo ""
echo "  Next steps:"
echo "    1. Visit https://$DOMAIN to verify the dashboard loads"
echo "    2. Forward a test email to your IMAP address"
echo "    3. Check the dashboard for the new email and AI-extracted actions"
echo ""
