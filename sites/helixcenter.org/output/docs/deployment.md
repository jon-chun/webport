# Deployment Guide

Production deployment of the Helix Center Next.js application on an Ubuntu 22.04 VPS with Nginx, PM2, and Let's Encrypt SSL.

---

## Prerequisites

- A VPS or dedicated server running **Ubuntu 22.04 LTS** (minimum 1 vCPU, 1 GB RAM, 20 GB disk)
- A domain name (`helixcenter.org`) with DNS A record pointing to the server's IP
- SSH access with a sudo-capable user
- **Python 3.9+** with `httpx` and `beautifulsoup4` packages (required for the supplemental scraper)
- Media files remain hosted on `media.helixcenter.org` (no migration required)

---

## 1. Server Provisioning

### Create a deploy user

```bash
# As root
adduser deploy
usermod -aG sudo deploy
```

### Configure firewall

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
sudo ufw status
```

Expected output:

```
Status: active

To                         Action      From
--                         ------      ----
OpenSSH                    ALLOW       Anywhere
Nginx Full                 ALLOW       Anywhere
OpenSSH (v6)               ALLOW       Anywhere (v6)
Nginx Full (v6)            ALLOW       Anywhere (v6)
```

### Harden SSH (recommended)

```bash
sudo nano /etc/ssh/sshd_config
```

Set the following:

```
PermitRootLogin no
PasswordAuthentication no
```

```bash
sudo systemctl restart sshd
```

---

## 2. Install Node.js 20 LTS

```bash
# Install NodeSource repository
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -

# Install Node.js
sudo apt-get install -y nodejs

# Verify
node --version   # v20.x.x
npm --version    # 10.x.x

# Install PM2 globally
sudo npm install -g pm2
```

---

## 3. Install Nginx

```bash
sudo apt-get install -y nginx
sudo systemctl enable nginx
sudo systemctl start nginx
```

---

## 4. Clone and Build the Application

### Clone the repository

```bash
sudo mkdir -p /var/www/helixcenter
sudo chown deploy:deploy /var/www/helixcenter

# As the deploy user
git clone git@github.com:your-org/helixcenter-next.git /var/www/helixcenter
cd /var/www/helixcenter
```

### Install dependencies

```bash
npm ci --production=false
```

### Set up environment variables

```bash
cp .env.example .env.production
nano .env.production
```

Populate with production values (see [Environment Variables](#environment-variables) below).

### Run the data pipeline

Before building the application, you must run two data-collection scripts to produce the JSON files that the seed script reads. Both scripts should be run from the project root.

```bash
# 1. Main WordPress API crawl
#    Produces: wp_posts.json, wp_participants.json, wp_pages.json,
#              wp_tags.json, wp_media.json, roundtable_participants.json,
#              participant_roundtables.json
python crawl_helix.py

# 2. Supplemental HTML scraper (fills gaps the REST API does not expose)
#    Produces: participant_titles.json, roundtable_details.json, wp_series.json
#    Updates:  wp_media.json (adds image size variants)
#    Requires: pip install httpx beautifulsoup4
python scrape_missing_data.py
```

After both scripts complete successfully you should have the following files in your data directory:

| File | Source | Description |
|---|---|---|
| `wp_posts.json` | `crawl_helix.py` | WordPress posts (roundtable content) |
| `wp_participants.json` | `crawl_helix.py` | Participant records from the API |
| `wp_pages.json` | `crawl_helix.py` | Static pages |
| `wp_tags.json` | `crawl_helix.py` | Tag taxonomy |
| `wp_media.json` | Both scripts | Media records; the scraper adds `thumbnail`, `medium`, and `full` size variants |
| `roundtable_participants.json` | `crawl_helix.py` | Roundtable-to-participant join data |
| `participant_roundtables.json` | `crawl_helix.py` | Participant-to-roundtable join data |
| `participant_titles.json` | `scrape_missing_data.py` | Professional titles scraped from HTML |
| `roundtable_details.json` | `scrape_missing_data.py` | Event dates and YouTube video URLs scraped from HTML |
| `wp_series.json` | `scrape_missing_data.py` | Series taxonomy from the API |

### Build the application

Run the following steps in order:

```bash
# 1. Generate Prisma client
npx prisma generate

# 2. Push schema to SQLite database (creates the file if it does not exist)
npx prisma db push

# 3. Seed the database with crawled WordPress data
#    Reads all JSON files produced by the data pipeline above
npx prisma db seed

# 4. Build the Next.js application
npm run build
```

The build output is written to `.next/`. The SQLite database is created at the path specified by `DATABASE_URL`.

---

## 5. Environment Variables

Create `/var/www/helixcenter/.env.production` with the following:

```bash
# Database
DATABASE_URL="file:/var/www/helixcenter/prisma/production.db"

# Public URLs
NEXT_PUBLIC_SITE_URL="https://helixcenter.org"
NEXT_PUBLIC_MEDIA_URL="https://media.helixcenter.org"

# Runtime
NODE_ENV="production"
PORT=3000
```

| Variable | Description | Required |
|---|---|---|
| `DATABASE_URL` | SQLite connection string. Must be an absolute path prefixed with `file:`. | Yes |
| `NEXT_PUBLIC_SITE_URL` | Canonical site URL. Used for SEO metadata and sitemap generation. | Yes |
| `NEXT_PUBLIC_MEDIA_URL` | Base URL for media assets (images, audio). Points to the existing WordPress media host. | Yes |
| `NODE_ENV` | Must be `"production"` for optimized builds. | Yes |
| `PORT` | Port the Next.js server listens on. Default: `3000`. | No |

---

## 6. PM2 Process Manager

### Create ecosystem config

Create `/var/www/helixcenter/ecosystem.config.js`:

```javascript
module.exports = {
  apps: [
    {
      name: "helixcenter",
      cwd: "/var/www/helixcenter",
      script: "node_modules/.bin/next",
      args: "start",
      instances: "max",
      exec_mode: "cluster",
      env: {
        NODE_ENV: "production",
        PORT: 3000,
      },
      // Logging
      log_date_format: "YYYY-MM-DD HH:mm:ss Z",
      error_file: "/var/log/pm2/helixcenter-error.log",
      out_file: "/var/log/pm2/helixcenter-out.log",
      merge_logs: true,
      // Restart policy
      max_restarts: 10,
      min_uptime: "10s",
      restart_delay: 5000,
      // Memory limit (restart if exceeded)
      max_memory_restart: "512M",
    },
  ],
};
```

### Start the application

```bash
# Create log directory
sudo mkdir -p /var/log/pm2
sudo chown deploy:deploy /var/log/pm2

# Start with ecosystem config
pm2 start ecosystem.config.js

# Save the process list so PM2 restarts on reboot
pm2 save

# Set up PM2 to start on system boot
pm2 startup systemd -u deploy --hp /home/deploy
# Run the command that PM2 outputs
```

### Useful PM2 commands

```bash
pm2 status                  # View running processes
pm2 logs helixcenter        # Tail logs
pm2 monit                   # Real-time monitoring dashboard
pm2 restart helixcenter     # Restart application
pm2 reload helixcenter      # Zero-downtime reload (cluster mode)
pm2 stop helixcenter        # Stop application
pm2 delete helixcenter      # Remove from PM2
```

---

## 7. Nginx Configuration

### Create site config

Create `/etc/nginx/sites-available/helixcenter`:

```nginx
# Redirect HTTP to HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name helixcenter.org www.helixcenter.org;
    return 301 https://helixcenter.org$request_uri;
}

# Redirect www to non-www
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name www.helixcenter.org;

    ssl_certificate /etc/letsencrypt/live/helixcenter.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/helixcenter.org/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    return 301 https://helixcenter.org$request_uri;
}

# Main server block
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name helixcenter.org;

    # SSL (managed by Certbot)
    ssl_certificate /etc/letsencrypt/live/helixcenter.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/helixcenter.org/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Content-Security-Policy: allow YouTube iframe embeds for roundtable videos
    # (127 of 135 roundtable pages include YouTube video embeds)
    add_header Content-Security-Policy "default-src 'self'; frame-src https://www.youtube.com https://www.youtube-nocookie.com; img-src 'self' https://media.helixcenter.org data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline' 'unsafe-eval';" always;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_min_length 1000;
    gzip_types
        text/plain
        text/css
        text/javascript
        application/javascript
        application/json
        application/xml
        image/svg+xml;

    # Next.js static assets (immutable, long cache)
    location /_next/static/ {
        proxy_pass http://localhost:3000;
        expires 365d;
        add_header Cache-Control "public, immutable";
        access_log off;
    }

    # Public static files (favicon, robots.txt, etc.)
    location /favicon.ico {
        proxy_pass http://localhost:3000;
        expires 30d;
        add_header Cache-Control "public";
        access_log off;
    }

    location /robots.txt {
        proxy_pass http://localhost:3000;
        expires 1d;
        access_log off;
    }

    location /sitemap.xml {
        proxy_pass http://localhost:3000;
        expires 1h;
        access_log off;
    }

    # Reverse proxy to Next.js
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Deny access to hidden files
    location ~ /\. {
        deny all;
        access_log off;
        log_not_found off;
    }
}
```

### Enable the site

```bash
sudo ln -s /etc/nginx/sites-available/helixcenter /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default    # Remove default site
sudo nginx -t                               # Test configuration
sudo systemctl reload nginx
```

---

## 8. SSL Certificate with Certbot

### Install Certbot

```bash
sudo apt-get install -y certbot python3-certbot-nginx
```

### Obtain certificate

If Nginx is not yet configured with SSL blocks, use Certbot's Nginx plugin to obtain and auto-configure:

```bash
sudo certbot --nginx -d helixcenter.org -d www.helixcenter.org
```

If you have already placed the SSL directives in the Nginx config (as shown above), use standalone mode first:

```bash
# Temporarily stop Nginx
sudo systemctl stop nginx

# Obtain certificate
sudo certbot certonly --standalone -d helixcenter.org -d www.helixcenter.org

# Restart Nginx
sudo systemctl start nginx
```

### Auto-renewal

Certbot installs a systemd timer for automatic renewal. Verify it is active:

```bash
sudo systemctl status certbot.timer
```

Test renewal:

```bash
sudo certbot renew --dry-run
```

---

## 9. SQLite Backup Strategy

### Daily backup script

Create `/var/www/helixcenter/scripts/backup-db.sh`:

```bash
#!/bin/bash
set -euo pipefail

DB_PATH="/var/www/helixcenter/prisma/production.db"
BACKUP_DIR="/backups/helixcenter/sqlite"
RETENTION_DAYS=30
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Create backup directory if it does not exist
mkdir -p "$BACKUP_DIR"

# Use SQLite .backup command for a consistent snapshot
sqlite3 "$DB_PATH" ".backup '$BACKUP_DIR/production_$TIMESTAMP.db'"

# Compress the backup
gzip "$BACKUP_DIR/production_$TIMESTAMP.db"

# Remove backups older than retention period
find "$BACKUP_DIR" -name "production_*.db.gz" -mtime +$RETENTION_DAYS -delete

echo "[$(date)] Backup completed: production_$TIMESTAMP.db.gz"
```

```bash
chmod +x /var/www/helixcenter/scripts/backup-db.sh
sudo mkdir -p /backups/helixcenter/sqlite
sudo chown deploy:deploy /backups/helixcenter/sqlite
```

### Schedule with cron

```bash
crontab -e
```

Add the following line (runs daily at 2:00 AM):

```
0 2 * * * /var/www/helixcenter/scripts/backup-db.sh >> /var/log/helixcenter-backup.log 2>&1
```

### Optional: Offsite backup

Sync backups to a remote server or S3-compatible storage:

```bash
# Rsync to remote server
rsync -avz /backups/helixcenter/ user@backup-server:/backups/helixcenter/

# Or use AWS CLI for S3
aws s3 sync /backups/helixcenter/sqlite/ s3://your-bucket/helixcenter/sqlite/
```

---

## 10. Media Files

Media files (images, audio recordings) are hosted on `media.helixcenter.org` and are **not migrated** as part of this deployment. The Next.js application references these URLs directly.

### Image size variants

The supplemental scraper (`scrape_missing_data.py`) enriches `wp_media.json` with image size variant metadata. Each media record now includes `thumbnail`, `medium`, and `full` size URLs and dimensions stored as JSON. Use these variants for responsive image optimization -- for example, serve `thumbnail` in listing cards and `full` on detail pages.

### Remote image configuration

Ensure that `media.helixcenter.org` allows cross-origin requests from `helixcenter.org` if you plan to use `next/image` with the remote domain. Add the following to `next.config.js`:

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "media.helixcenter.org",
        pathname: "/**",
      },
    ],
    // Use size variants from wp_media.json for deviceSizes/imageSizes
    // to match the thumbnail (150px), medium (300px), and full widths
    deviceSizes: [640, 750, 828, 1080, 1200],
    imageSizes: [150, 300, 768],
  },
};

module.exports = nextConfig;
```

---

## 11. Monitoring

### PM2 monitoring

```bash
pm2 monit                        # Real-time CPU/memory dashboard
pm2 logs helixcenter --lines 50  # Recent logs
pm2 describe helixcenter         # Detailed process info
```

### Nginx logs

```bash
# Access logs
sudo tail -f /var/log/nginx/access.log

# Error logs
sudo tail -f /var/log/nginx/error.log
```

### Optional: External uptime monitoring

Set up a free uptime monitor with one of the following services to receive alerts when the site goes down:

- [UptimeRobot](https://uptimerobot.com/) (free tier: 50 monitors, 5-minute intervals)
- [Better Uptime](https://betteruptime.com/)
- [Healthchecks.io](https://healthchecks.io/) for cron job monitoring

Monitor the following endpoints:

| URL | Expected Status | Check Interval |
|---|---|---|
| `https://helixcenter.org` | 200 | 5 minutes |
| `https://helixcenter.org/roundtables` | 200 | 15 minutes |
| `https://helixcenter.org/api/health` | 200 | 5 minutes |

---

## 12. Deployment Workflow

### Manual deployment

```bash
ssh deploy@your-server-ip
cd /var/www/helixcenter

# Pull latest changes
git pull origin main

# Install dependencies (if package-lock.json changed)
npm ci --production=false

# Rebuild
npx prisma generate
npm run build

# Zero-downtime reload
pm2 reload helixcenter
```

### Re-seeding after data changes

If upstream content has changed on the WordPress site, re-run the full data pipeline before re-seeding:

```bash
cd /var/www/helixcenter

# Re-crawl and re-scrape
python crawl_helix.py
python scrape_missing_data.py

# Re-seed the database
npx prisma db push --force-reset
npx prisma db seed

# Rebuild and reload
npm run build
pm2 reload helixcenter
```

### Recommended: Deployment script

Create `/var/www/helixcenter/scripts/deploy.sh`:

```bash
#!/bin/bash
set -euo pipefail

APP_DIR="/var/www/helixcenter"
cd "$APP_DIR"

echo "[$(date)] Starting deployment..."

# Pull latest code
git pull origin main

# Install dependencies
npm ci --production=false

# Re-run data pipeline if --reseed flag is passed
if [[ "${1:-}" == "--reseed" ]]; then
    echo "[$(date)] Running data pipeline..."
    python crawl_helix.py
    python scrape_missing_data.py
    npx prisma db push --force-reset
    npx prisma db seed
fi

# Generate Prisma client (in case schema changed)
npx prisma generate

# Run migrations if needed
npx prisma db push

# Build Next.js
npm run build

# Reload with zero downtime
pm2 reload helixcenter

echo "[$(date)] Deployment complete."
```

```bash
chmod +x /var/www/helixcenter/scripts/deploy.sh
```

---

## 13. Rollback Procedure

If a deployment causes issues:

```bash
cd /var/www/helixcenter

# Check recent commits
git log --oneline -10

# Revert to the previous commit
git checkout <previous-commit-hash>

# Rebuild and reload
npm ci --production=false
npx prisma generate
npm run build
pm2 reload helixcenter
```

For database rollback, restore from the most recent backup:

```bash
# Stop the application
pm2 stop helixcenter

# Restore database
gunzip -k /backups/helixcenter/sqlite/production_YYYYMMDD_HHMMSS.db.gz
cp /backups/helixcenter/sqlite/production_YYYYMMDD_HHMMSS.db /var/www/helixcenter/prisma/production.db

# Restart
pm2 start helixcenter
```

---

## Quick Reference

| Task | Command |
|---|---|
| Start app | `pm2 start ecosystem.config.js` |
| Stop app | `pm2 stop helixcenter` |
| Restart app | `pm2 reload helixcenter` |
| View logs | `pm2 logs helixcenter` |
| Monitor | `pm2 monit` |
| Test Nginx config | `sudo nginx -t` |
| Reload Nginx | `sudo systemctl reload nginx` |
| Renew SSL | `sudo certbot renew` |
| Run backup | `/var/www/helixcenter/scripts/backup-db.sh` |
| Deploy | `/var/www/helixcenter/scripts/deploy.sh` |
| Deploy with re-seed | `/var/www/helixcenter/scripts/deploy.sh --reseed` |
| Run API crawl | `python crawl_helix.py` |
| Run supplemental scraper | `python scrape_missing_data.py` |
