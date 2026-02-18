# INtelliBOX Production Deployment

Deploy INtelliBOX to an AWS EC2 instance with Podman, nginx, and HTTPS.

## Architecture

```
Team forwards emails → Outlook/IMAP inbox
                              ↓
              IMAP Fetcher (polls every 60s)
                              ↓
              File Watcher → AI Processing → Database
                              ↓
Internet → HTTPS (443) → nginx → HTTP (8000) → INtelliBOX container (Podman)
```

## Prerequisites

- AWS account
- An email address with IMAP access (Outlook, Gmail, etc.)
- OpenAI API key

## Step 1: Get a Free Domain (DuckDNS)

1. Go to [duckdns.org](https://www.duckdns.org/) and sign in
2. Pick a subdomain (e.g. `intellibox-pilot`) → you get `intellibox-pilot.duckdns.org`
3. Copy your **token** from the DuckDNS dashboard

## Step 2: Set Up Email Account

For **Outlook/Office 365**:
- Use your existing Outlook email, or create a new one
- IMAP is enabled by default for most Outlook accounts
- Host: `outlook.office365.com`, Port: `993`
- If using MFA, create an App Password: Account Settings → Security → App Passwords

For **Gmail**:
- Enable IMAP: Settings → See all settings → Forwarding and POP/IMAP → Enable IMAP
- Create an App Password: Google Account → Security → 2-Step Verification → App passwords
- Host: `imap.gmail.com`, Port: `993`

## Step 3: Launch EC2 Instance

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

## Step 4: Deploy

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

## Step 5: Verify

1. Visit `https://your-name.duckdns.org` — the dashboard should load
2. Forward a test email to your IMAP email address
3. Wait ~60 seconds for the IMAP fetcher to pick it up
4. Check the dashboard — the email and AI-extracted actions should appear
5. Check health: `curl https://your-name.duckdns.org/health`

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

**IMAP not fetching emails:**
- Check `IMAP_ENABLED=true` in `.env.production`
- Verify IMAP credentials: `podman logs intellibox | grep IMAP`
- Some email providers require App Passwords when MFA is enabled

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
