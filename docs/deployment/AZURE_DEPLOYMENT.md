# Azure VM Deployment Guide for EmailTools Web Interface

This guide covers deploying EmailTools to an Azure VM with a web interface accessible via IP address.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Azure Cloud                       │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌──────────────────────────────────────────────┐  │
│  │  Azure VM (Ubuntu 22.04)                     │  │
│  │  - Podman Container Runtime                  │  │
│  │  - EmailTools Container (Web + Scheduler)     │  │
│  │  - Port 8000 (Web Interface)                  │  │
│  │  - SQLite Database (Persistent Volume)       │  │
│  └──────────────────────────────────────────────┘  │
│                        │                             │
│              Public IP: XX.XX.XX.XX:8000            │
│                                                      │
└─────────────────────────────────────────────────────┘
```

## Prerequisites

- Azure subscription with VM creation permissions
- Basic knowledge of Azure Portal or Azure CLI
- SSH client for connecting to VM

---

## Part 1: Create Azure VM

### Option A: Using Azure Portal (Easiest)

1. **Go to Azure Portal**: https://portal.azure.com

2. **Create Virtual Machine**:
   - Click "Create a resource" > "Virtual Machine"
   - Fill in details:
     - **Resource Group**: Create new or select existing
     - **VM Name**: `emailtools-vm`
     - **Region**: Choose closest to your location
     - **Image**: Ubuntu Server 22.04 LTS
     - **Size**: Standard_B2s (2 vCPUs, 4 GB RAM) - ~$30/month
     - **Authentication**: SSH public key (recommended) or Password

3. **Configure Networking**:
   - **Public IP**: Enable (auto-assigned)
   - **Inbound Ports**: Select SSH (22) and HTTP (80)
   - Click "Advanced" > Add inbound rule for port 8000

4. **Review + Create** and wait for deployment

### Option B: Using Azure CLI (Faster)

```bash
# Login to Azure
az login

# Create resource group
az group create --name emailtools-rg --location eastus

# Create VM
az vm create \
  --resource-group emailtools-rg \
  --name emailtools-vm \
  --image Ubuntu2204 \
  --size Standard_B2s \
  --admin-username azureuser \
  --generate-ssh-keys \
  --public-ip-sku Standard

# Open port 8000 for web interface
az vm open-port \
  --resource-group emailtools-rg \
  --name emailtools-vm \
  --port 8000 \
  --priority 1001

# Get public IP
az vm list-ip-addresses \
  --resource-group emailtools-rg \
  --name emailtools-vm \
  --output table
```

---

## Part 2: Setup VM

### 1. Connect to VM

```bash
# Get your VM's public IP from Azure Portal
# SSH into the VM
ssh azureuser@YOUR_VM_PUBLIC_IP
```

### 2. Install Podman

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Podman
sudo apt install -y podman

# Verify installation
podman --version
```

### 3. Clone Repository

```bash
# Install git if needed
sudo apt install -y git

# Clone your repo
git clone https://github.com/blake-perkins/EmailTools.git
cd EmailTools
```

### 4. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit with your settings
nano .env
```

**Required settings** in `.env`:
```bash
# Database
DATABASE_URL=sqlite:///./data/emailtools.db

# OpenAI API Key
OPENAI_API_KEY=sk-your-real-api-key

# SMTP (for email reports)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
REPORT_FROM=programtracker@example.com
REPORT_RECIPIENTS=team@example.com

# Reporting
REPORT_TIME=06:00
TIMEZONE=America/New_York
```

---

## Part 3: Deploy with Podman

### Build Container

```bash
cd ~/EmailTools
podman build -t emailtools:latest .
```

### Run Web Interface + Scheduler

```bash
# Create persistent data directory
mkdir -p ~/emailtools-data

# Run web server (with scheduler in background)
podman run -d \
  --name emailtools-web \
  --restart always \
  -p 8000:8000 \
  --env-file .env \
  -v ~/emailtools-data:/app/data:Z \
  emailtools:latest \
  emailtools web --host 0.0.0.0 --port 8000

# Run scheduler (processes emails nightly)
podman run -d \
  --name emailtools-scheduler \
  --restart always \
  --env-file .env \
  -v ~/emailtools-data:/app/data:Z \
  emailtools:latest \
  emailtools report schedule

# Verify containers are running
podman ps
```

### Initialize Database

```bash
# One-time database setup
podman exec emailtools-web emailtools init
```

---

## Part 4: Access Web Interface

### Get Your Public IP

```bash
# On Azure VM
curl ifconfig.me

# Or from Azure Portal:
# Go to VM > Overview > Public IP address
```

### Access Dashboard

Open browser and go to:
```
http://YOUR_VM_PUBLIC_IP:8000
```

You should see the EmailTools dashboard!

### Pages Available:
- `http://YOUR_IP:8000/` - Dashboard
- `http://YOUR_IP:8000/actions` - Actions list
- `http://YOUR_IP:8000/emails` - Emails list
- `http://YOUR_IP:8000/report` - Daily report

---

## Part 5: Setup Auto-Start on Reboot

### Create Systemd Services

```bash
# Generate systemd files for containers
podman generate systemd --new --name emailtools-web --files
podman generate systemd --new --name emailtools-scheduler --files

# Move to systemd directory
sudo mv container-emailtools-*.service /etc/systemd/system/

# Enable services
sudo systemctl daemon-reload
sudo systemctl enable container-emailtools-web.service
sudo systemctl enable container-emailtools-scheduler.service

# Check status
sudo systemctl status container-emailtools-web.service
```

---

## Part 6: Security & Hardening

### Enable Firewall

```bash
# Install firewall
sudo apt install -y ufw

# Allow SSH and web port
sudo ufw allow 22/tcp
sudo ufw allow 8000/tcp

# Enable firewall
sudo ufw --force enable

# Check status
sudo ufw status
```

### Optional: Add HTTPS with Nginx

```bash
# Install Nginx
sudo apt install -y nginx certbot python3-certbot-nginx

# Configure Nginx proxy
sudo nano /etc/nginx/sites-available/emailtools
```

**Nginx config**:
```nginx
server {
    listen 80;
    server_name YOUR_DOMAIN_OR_IP;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/emailtools /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# Now access via http://YOUR_IP (port 80)
```

---

## Part 7: Maintenance & Monitoring

### View Logs

```bash
# Web server logs
podman logs -f emailtools-web

# Scheduler logs
podman logs -f emailtools-scheduler

# System journal
sudo journalctl -u container-emailtools-web.service -f
```

### Update Application

```bash
# Pull latest code
cd ~/EmailTools
git pull origin main

# Rebuild container
podman build -t emailtools:latest .

# Restart containers (systemd will recreate)
sudo systemctl restart container-emailtools-web.service
sudo systemctl restart container-emailtools-scheduler.service
```

### Backup Data

```bash
# Backup database and emails
tar -czf emailtools-backup-$(date +%Y%m%d).tar.gz ~/emailtools-data/

# Copy to local machine
scp azureuser@YOUR_IP:~/emailtools-backup-*.tar.gz ./
```

### Monitor Resources

```bash
# Check container resource usage
podman stats emailtools-web emailtools-scheduler

# Check VM resources
htop  # or top
df -h
```

---

## Part 8: Azure Network Security Group (NSG) Rules

Ensure Azure NSG allows traffic on port 8000:

```bash
# Via Azure CLI
az network nsg rule create \
  --resource-group emailtools-rg \
  --nsg-name emailtools-vmNSG \
  --name AllowWeb \
  --protocol tcp \
  --priority 1001 \
  --destination-port-range 8000 \
  --access Allow
```

Or via Azure Portal:
1. Go to VM > Networking
2. Add inbound port rule
3. Destination port: 8000
4. Protocol: TCP
5. Action: Allow

---

## Troubleshooting

### Can't Access Web Interface

```bash
# Check if containers are running
podman ps

# Check if port is listening
sudo netstat -tlnp | grep 8000

# Check firewall
sudo ufw status

# Check container logs
podman logs emailtools-web
```

### Container Won't Start

```bash
# Check environment variables
podman exec emailtools-web env | grep -E "DATABASE|OPENAI"

# Test database connection
podman exec emailtools-web python -c "from emailtools.database import get_session; print('OK')"
```

### Performance Issues

```bash
# Check VM size (may need to upgrade)
az vm show -g emailtools-rg -n emailtools-vm --query hardwareProfile

# Monitor resources
htop
podman stats
```

---

## Cost Estimation

**Azure VM (Standard_B2s)**:
- Compute: ~$30/month
- Storage (30 GB): ~$2/month
- Bandwidth: ~$5/month (typical)
- **Total: ~$37/month**

**Alternative - Smaller VM (Standard_B1s)**:
- Compute: ~$10/month (1 vCPU, 1 GB RAM)
- Good for testing, may be slow for production

---

## Quick Reference Commands

```bash
# Start web interface manually
emailtools web --host 0.0.0.0 --port 8000

# Process emails
emailtools process

# View actions
emailtools actions list

# Generate report
emailtools report send --dry-run

# Container management
podman ps                    # List containers
podman logs -f emailtools-web # View logs
podman restart emailtools-web # Restart
podman exec emailtools-web emailtools db show  # Run command

# System management
sudo systemctl status container-emailtools-web.service
sudo systemctl restart container-emailtools-web.service
sudo journalctl -u container-emailtools-web.service -f
```

---

## Next Steps

1. ✅ Access web interface at `http://YOUR_IP:8000`
2. Configure email ingestion (drop .eml files in `data/inbox/`)
3. Set up automated email forwarding to process emails
4. Share IP address with your boss
5. Monitor and maintain

**Your boss can now access EmailTools at**: `http://YOUR_VM_IP:8000`

---

For questions or issues, refer to the main [README.md](README.md) or [AWS_DEPLOYMENT.md](AWS_DEPLOYMENT.md) for additional deployment options.
