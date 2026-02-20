# INtelliBOX Production Deployment

Deploy INtelliBOX to an AWS EC2 instance with Podman, nginx, and HTTPS. The container image uses IronBank UBI 9 (`registry1.dso.mil/ironbank/redhat/ubi/ubi9`) as the base image.

## Architecture

```
Upload via dashboard  ─┐
SCP / folder sync     ─┤
                       ↓
                  data/inbox/
                       ↓
         File Watcher → AI Processing → Database
                       ↓
Internet → HTTPS (443) → nginx (basic auth + TLS) → HTTP (8000) → INtelliBOX container (Podman, IronBank UBI 9)
```

## Quick Start — Zero-Touch Deployment

Deploy a fresh pilot instance with a single command. No SSH, no manual steps.

### One-Time Prerequisites

1. [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) installed and configured (`aws configure`)
2. An EC2 key pair created in your AWS region
3. A DuckDNS subdomain — go to [duckdns.org](https://www.duckdns.org/), sign in, create a subdomain, copy your token
4. IronBank registry credentials — sign up at [registry1.dso.mil](https://registry1.dso.mil) and get your CLI secret

### Configure

```bash
cd deploy

# AWS settings
cp .env.pilot.example .env.pilot
# Edit .env.pilot: set AWS_REGION, AWS_KEY_NAME, INSTANCE_TYPE, SSH_KEY_PATH

# App secrets
cp .env.production.example .env.production
# Edit .env.production: set DOMAIN, DUCKDNS_TOKEN, OPENAI_API_KEY, SMTP creds
```

### Deploy

```bash
bash deploy/pilot.sh
```

This will automatically:
1. Terminate any existing pilot instance
2. Create a security group (ports 22, 80, 443)
3. Find the latest Ubuntu 24.04 AMI
4. Launch an EC2 instance with cloud-init
5. Install Podman, nginx, Certbot on the instance
6. Clone the repo, build the container, start the app
7. Configure DuckDNS and obtain an SSL certificate
8. Wait for the health check to pass
9. Print the live URL

### CI/CD Auto-Deploy

Pushes to `main` that pass all tests and security scans automatically deploy to the pilot instance. To enable this, add these GitHub secrets:

```bash
# Store the SSH private key
gh secret set PILOT_SSH_KEY < path/to/intellibox-key.pem

# Store the pilot hostname
gh secret set PILOT_HOST -b "intellibox-pilot.duckdns.org"

# IronBank registry credentials (required for container builds in CI)
gh secret set IRONBANK_USER -b "your-ironbank-username"
gh secret set IRONBANK_PASSWORD -b "your-ironbank-cli-secret"
```

The deploy job will skip gracefully if these secrets are not configured.

---

## Manual Deployment (Alternative)

If you prefer to set up manually instead of using `pilot.sh`:

### Step 1: Get a Free Domain (DuckDNS)

1. Go to [duckdns.org](https://www.duckdns.org/) and sign in
2. Pick a subdomain (e.g. `intellibox-pilot`) → you get `intellibox-pilot.duckdns.org`
3. Copy your **token** from the DuckDNS dashboard

### Step 2: Launch EC2 Instance

1. Go to AWS EC2 → Launch Instance
2. Settings:
   - **AMI**: Ubuntu 24.04 LTS
   - **Instance type**: t3.micro (free tier eligible)
   - **Key pair**: Create or select an SSH key
   - **Security group**: Allow inbound SSH (22), HTTP (80), HTTPS (443)
   - **Storage**: 20 GB gp3 (default is fine)
3. Launch and note the public IP

### Step 3: Deploy

```bash
ssh -i your-key.pem ubuntu@<your-ec2-ip>
git clone https://github.com/blake-perkins/INtelliBOX.git
cd INtelliBOX/deploy
cp .env.production.example .env.production
nano .env.production  # Fill in your real values
chmod +x setup.sh
sudo ./setup.sh
```

### Step 4: Verify

1. Visit `https://your-name.duckdns.org` — the dashboard should load
2. Go to the **Emails** page and upload a test `.eml` file
3. Check the dashboard — the email and AI-extracted actions should appear
4. Check health: `curl https://your-name.duckdns.org/health`

## Getting Emails In

There are two ways to get emails into INtelliBOX:

**Via the dashboard** — Go to the Emails page and use the upload form to upload `.eml` or `.msg` files directly from your browser.

**Via the file system** — Drop `.eml` or `.msg` files into the `data/inbox/` directory (inside the container at `/app/data/inbox/`, or on the host at `/opt/intellibox/data/inbox/`). The file watcher picks them up automatically. This works with SCP, OneDrive/SharePoint sync, or any folder-based integration.

## Management Commands

```bash
# View logs
podman logs -f intellibox

# Restart
podman restart intellibox

# Shell into container
podman exec -it intellibox bash

# Health check
curl http://127.0.0.1:8000/health

# Rebuild after code changes
cd ~/INtelliBOX
git pull
podman build -t intellibox:prod -f Dockerfile .
podman stop intellibox && podman rm intellibox
podman run -d --name intellibox --restart=always \
    --env-file deploy/.env.production \
    -v /opt/intellibox/data:/app/data:Z \
    -p 127.0.0.1:8000:8000 \
    intellibox:prod

# SSL certificate renewal (auto-renews, but to test)
sudo certbot renew --dry-run
```

## Data

All persistent data is at `/opt/intellibox/data/`:
- `intellibox.db` — SQLite database
- `inbox/` — incoming email files (processed and moved to `emails/`)
- `emails/` — archived emails
- `logs/` — rotating application logs

## Troubleshooting

**Container won't start:**
```bash
podman logs intellibox
```

**Uploaded emails not processing:**
- Check the file watcher health: `curl http://127.0.0.1:8000/health`
- Look for errors in logs: `podman logs intellibox | grep -i error`

**SSL certificate issues:**
```bash
sudo certbot renew --force-renewal
sudo systemctl reload nginx
```

**nginx errors:**
```bash
sudo nginx -t
sudo journalctl -u nginx --no-pager -n 50
```
