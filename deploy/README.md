# INtelliBOX Production Deployment

Deploy INtelliBOX to an AWS EC2 instance with Podman, nginx, and HTTPS.

## Architecture

```
Upload via dashboard  ─┐
SCP / folder sync     ─┤
                       ↓
                  data/inbox/
                       ↓
         File Watcher → AI Processing → Database
                       ↓
Internet → HTTPS (443) → nginx → HTTP (8000) → INtelliBOX container (Podman)
```

## Prerequisites

- AWS account
- OpenAI API key

## Step 1: Get a Free Domain (DuckDNS)

1. Go to [duckdns.org](https://www.duckdns.org/) and sign in
2. Pick a subdomain (e.g. `intellibox-pilot`) → you get `intellibox-pilot.duckdns.org`
3. Copy your **token** from the DuckDNS dashboard

## Step 2: Launch EC2 Instance

1. Go to AWS EC2 → Launch Instance
2. Settings:
   - **AMI**: Ubuntu 24.04 LTS
   - **Instance type**: t3.micro (free tier eligible)
   - **Key pair**: Create or select an SSH key
   - **Security group**: Allow inbound:
     - SSH (22) from your IP
     - HTTP (80) from anywhere
     - HTTPS (443) from anywhere
   - **Storage**: 20 GB gp3 (default is fine)
3. Launch and note the public IP

## Step 3: Deploy

SSH into your instance:
```bash
ssh -i your-key.pem ubuntu@<your-ec2-ip>
```

Clone the repo and configure:
```bash
git clone https://github.com/blake-perkins/INtelliBOX.git
cd INtelliBOX/deploy
cp .env.production.example .env.production
nano .env.production  # Fill in your real values
```

Run the setup script:
```bash
chmod +x setup.sh
sudo ./setup.sh
```

This will:
1. Install Podman, nginx, and Certbot
2. Register your DuckDNS subdomain
3. Obtain an SSL certificate
4. Build and start the INtelliBOX container
5. Configure auto-start on boot

## Step 4: Verify

1. Visit `https://your-name.duckdns.org` — the dashboard should load
2. Go to the **Emails** page and upload a test `.eml` file
3. The file watcher picks it up within a few seconds
4. Check the dashboard — the email and AI-extracted actions should appear
5. Check health: `curl https://your-name.duckdns.org/health`

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
