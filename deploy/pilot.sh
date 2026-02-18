#!/bin/bash
# INtelliBOX Pilot — Zero-Touch Deployment
#
# Provisions a fresh EC2 instance and deploys the full stack automatically.
# Run from your local machine (Git Bash on Windows, or any bash shell).
#
# Prerequisites:
#   1. AWS CLI installed and configured (aws configure)
#   2. deploy/.env.pilot filled in (copy from .env.pilot.example)
#   3. deploy/.env.production filled in (copy from .env.production.example)
#
# Usage:
#   bash deploy/pilot.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── Load configs ──────────────────────────────────────────────────────────────

if [ ! -f "$SCRIPT_DIR/.env.pilot" ]; then
    echo "ERROR: deploy/.env.pilot not found."
    echo "Copy .env.pilot.example to .env.pilot and fill in your values."
    exit 1
fi

if [ ! -f "$SCRIPT_DIR/.env.production" ]; then
    echo "ERROR: deploy/.env.production not found."
    echo "Copy .env.production.example to .env.production and fill in your values."
    exit 1
fi

# shellcheck source=/dev/null
source "$SCRIPT_DIR/.env.pilot"

DOMAIN=$(grep '^DOMAIN=' "$SCRIPT_DIR/.env.production" | cut -d'=' -f2)
DUCKDNS_TOKEN=$(grep '^DUCKDNS_TOKEN=' "$SCRIPT_DIR/.env.production" | cut -d'=' -f2)
SUBDOMAIN=$(echo "$DOMAIN" | sed 's/\.duckdns\.org$//')

# Validate required values
for var in AWS_REGION AWS_KEY_NAME INSTANCE_TYPE DOMAIN DUCKDNS_TOKEN; do
    if [ -z "${!var:-}" ]; then
        echo "ERROR: $var is not set. Check your .env.pilot and .env.production files."
        exit 1
    fi
done

if [ "$DOMAIN" = "your-name.duckdns.org" ] || [ "$DUCKDNS_TOKEN" = "your-duckdns-token" ]; then
    echo "ERROR: Replace placeholder values in deploy/.env.production"
    exit 1
fi

echo "=== INtelliBOX Pilot Deployment ==="
echo "  Region:   $AWS_REGION"
echo "  Domain:   $DOMAIN"
echo "  Instance: $INSTANCE_TYPE"
echo "  Key:      $AWS_KEY_NAME"
echo ""

# ── Terminate old pilot instance ─────────────────────────────────────────────

echo "=== Checking for existing pilot instance ==="

OLD_INSTANCE_IDS=$(aws ec2 describe-instances \
    --region "$AWS_REGION" \
    --filters "Name=tag:Name,Values=INtelliBOX-pilot" \
              "Name=instance-state-name,Values=running,stopped,pending" \
    --query 'Reservations[].Instances[].InstanceId' \
    --output text 2>/dev/null || echo "")

if [ -n "$OLD_INSTANCE_IDS" ] && [ "$OLD_INSTANCE_IDS" != "None" ]; then
    echo "  Terminating old instance(s): $OLD_INSTANCE_IDS"
    aws ec2 terminate-instances \
        --region "$AWS_REGION" \
        --instance-ids $OLD_INSTANCE_IDS > /dev/null
    echo "  Waiting for termination..."
    aws ec2 wait instance-terminated \
        --region "$AWS_REGION" \
        --instance-ids $OLD_INSTANCE_IDS 2>/dev/null || true
    echo "  Old instance terminated."
else
    echo "  No existing pilot instance found."
fi

# ── Create security group (idempotent) ───────────────────────────────────────

echo ""
echo "=== Ensuring security group ==="

SG_NAME="intellibox-pilot-sg"

SG_ID=$(aws ec2 describe-security-groups \
    --region "$AWS_REGION" \
    --group-names "$SG_NAME" \
    --query 'SecurityGroups[0].GroupId' \
    --output text 2>/dev/null || echo "")

if [ -z "$SG_ID" ] || [ "$SG_ID" = "None" ]; then
    echo "  Creating security group: $SG_NAME"
    SG_ID=$(aws ec2 create-security-group \
        --region "$AWS_REGION" \
        --group-name "$SG_NAME" \
        --description "INtelliBOX pilot - SSH, HTTP, HTTPS" \
        --query 'GroupId' \
        --output text)

    # Open SSH (22), HTTP (80), HTTPS (443)
    for PORT in 22 80 443; do
        aws ec2 authorize-security-group-ingress \
            --region "$AWS_REGION" \
            --group-id "$SG_ID" \
            --protocol tcp \
            --port "$PORT" \
            --cidr 0.0.0.0/0 > /dev/null
    done
    echo "  Created: $SG_ID (ports 22, 80, 443 open)"
else
    echo "  Using existing: $SG_ID"
fi

# ── Look up latest Ubuntu 24.04 AMI ─────────────────────────────────────────

echo ""
echo "=== Finding latest Ubuntu 24.04 AMI ==="

AMI_ID=$(aws ec2 describe-images \
    --region "$AWS_REGION" \
    --owners 099720109477 \
    --filters "Name=name,Values=ubuntu/images/hvm-ssd-amd64/ubuntu-noble-24.04-amd64-server-*" \
              "Name=state,Values=available" \
    --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
    --output text)

if [ -z "$AMI_ID" ] || [ "$AMI_ID" = "None" ]; then
    echo "ERROR: Could not find Ubuntu 24.04 AMI in $AWS_REGION"
    exit 1
fi

echo "  AMI: $AMI_ID"

# ── Generate cloud-init user-data ────────────────────────────────────────────

echo ""
echo "=== Generating cloud-init script ==="

# Read .env.production contents for embedding into user-data
ENV_PRODUCTION_CONTENTS=$(cat "$SCRIPT_DIR/.env.production")

# Build the cloud-init user-data script
USER_DATA=$(cat <<'CLOUD_INIT_HEADER'
#!/bin/bash
set -euo pipefail
exec > /var/log/intellibox-setup.log 2>&1
echo "=== INtelliBOX cloud-init started at $(date) ==="

# ── Install prerequisites ────────────────────────────────────────────────────

apt-get update
apt-get install -y git

# ── Clone repository ─────────────────────────────────────────────────────────

cd /home/ubuntu
git clone https://github.com/blake-perkins/INtelliBOX.git
chown -R ubuntu:ubuntu INtelliBOX

# ── Write .env.production ────────────────────────────────────────────────────

cat > /home/ubuntu/INtelliBOX/deploy/.env.production <<'ENVFILE'
CLOUD_INIT_HEADER
)

# Append the actual env contents and close the heredoc
USER_DATA="${USER_DATA}
${ENV_PRODUCTION_CONTENTS}
ENVFILE"

# Append the rest of the cloud-init script
USER_DATA="${USER_DATA}
$(cat <<'CLOUD_INIT_FOOTER'

# ── Run setup ─────────────────────────────────────────────────────────────────

export REPO_ROOT=/home/ubuntu/INtelliBOX
cd /home/ubuntu/INtelliBOX/deploy
chmod +x setup.sh
./setup.sh

echo "=== INtelliBOX cloud-init completed at $(date) ==="
CLOUD_INIT_FOOTER
)"

echo "  Cloud-init script generated ($(echo "$USER_DATA" | wc -l) lines)"

# ── Launch EC2 instance ──────────────────────────────────────────────────────

echo ""
echo "=== Launching EC2 instance ==="

INSTANCE_ID=$(aws ec2 run-instances \
    --region "$AWS_REGION" \
    --image-id "$AMI_ID" \
    --instance-type "$INSTANCE_TYPE" \
    --key-name "$AWS_KEY_NAME" \
    --security-group-ids "$SG_ID" \
    --user-data "$USER_DATA" \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=INtelliBOX-pilot}]" \
    --query 'Instances[0].InstanceId' \
    --output text)

echo "  Instance: $INSTANCE_ID"
echo "  Waiting for instance to start..."

aws ec2 wait instance-running \
    --region "$AWS_REGION" \
    --instance-ids "$INSTANCE_ID"

# Get public IP
PUBLIC_IP=$(aws ec2 describe-instances \
    --region "$AWS_REGION" \
    --instance-ids "$INSTANCE_ID" \
    --query 'Reservations[0].Instances[0].PublicIpAddress' \
    --output text)

echo "  Public IP: $PUBLIC_IP"

# ── Update DuckDNS ───────────────────────────────────────────────────────────

echo ""
echo "=== Updating DuckDNS ==="

DUCKDNS_RESULT=$(curl -s "https://www.duckdns.org/update?domains=${SUBDOMAIN}&token=${DUCKDNS_TOKEN}&ip=${PUBLIC_IP}")
echo "  DuckDNS response: $DUCKDNS_RESULT"

if [ "$DUCKDNS_RESULT" != "OK" ]; then
    echo "WARNING: DuckDNS update did not return OK. DNS may not resolve correctly."
fi

# ── Wait for deployment to complete ──────────────────────────────────────────

echo ""
echo "=== Waiting for deployment to complete ==="
echo "  Cloud-init is running on the instance (podman build, nginx, certbot...)"
echo "  This typically takes 3-5 minutes."
echo ""

SSH_KEY_PATH="${SSH_KEY_PATH:-}"
MAX_WAIT=360  # 6 minutes
INTERVAL=10

for i in $(seq 1 $((MAX_WAIT / INTERVAL))); do
    ELAPSED=$((i * INTERVAL))

    # Try the health endpoint
    if curl -sf --max-time 5 "https://${DOMAIN}/health" > /dev/null 2>&1; then
        echo ""
        echo "============================================="
        echo "  INtelliBOX pilot is LIVE!"
        echo "============================================="
        echo ""
        echo "  URL:         https://$DOMAIN"
        echo "  Instance:    $INSTANCE_ID"
        echo "  Public IP:   $PUBLIC_IP"
        echo ""
        if [ -n "$SSH_KEY_PATH" ]; then
            echo "  SSH:         ssh -i $SSH_KEY_PATH ubuntu@$PUBLIC_IP"
        else
            echo "  SSH:         ssh -i <your-key.pem> ubuntu@$PUBLIC_IP"
        fi
        echo "  Setup log:   ssh ... 'cat /var/log/intellibox-setup.log'"
        echo ""
        exit 0
    fi

    # Show progress
    printf "  [%3ds] Waiting... " "$ELAPSED"

    # If SSH key available, try to peek at cloud-init status
    if [ -n "$SSH_KEY_PATH" ] && [ -f "$SSH_KEY_PATH" ]; then
        STATUS=$(ssh -o StrictHostKeyChecking=no -o ConnectTimeout=3 -o LogLevel=ERROR \
            -i "$SSH_KEY_PATH" "ubuntu@$PUBLIC_IP" \
            "cloud-init status --format json 2>/dev/null | python3 -c 'import sys,json; print(json.load(sys.stdin).get(\"status\",\"unknown\"))' 2>/dev/null" \
            2>/dev/null || echo "connecting")
        echo "(cloud-init: $STATUS)"
    else
        echo ""
    fi

    sleep "$INTERVAL"
done

# ── Timeout — show debug info ────────────────────────────────────────────────

echo ""
echo "WARNING: Deployment did not complete within ${MAX_WAIT}s."
echo ""
echo "  The instance is running but cloud-init may still be in progress."
echo "  Check the setup log:"
if [ -n "$SSH_KEY_PATH" ] && [ -f "$SSH_KEY_PATH" ]; then
    echo "    ssh -i $SSH_KEY_PATH ubuntu@$PUBLIC_IP 'tail -50 /var/log/intellibox-setup.log'"
    echo ""
    echo "  Cloud-init status:"
    echo "    ssh -i $SSH_KEY_PATH ubuntu@$PUBLIC_IP 'cloud-init status'"
else
    echo "    ssh -i <your-key.pem> ubuntu@$PUBLIC_IP 'tail -50 /var/log/intellibox-setup.log'"
fi
echo ""
echo "  Instance: $INSTANCE_ID"
echo "  IP: $PUBLIC_IP"
echo "  Domain: https://$DOMAIN"
exit 1
