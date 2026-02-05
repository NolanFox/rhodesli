# Rhodesli Deployment Guide

Deploy Rhodesli to Railway with a custom domain on Cloudflare.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  Railway (rhodesli.nolanandrewfox.com)                      │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Docker Container (python:3.11-slim)                   │ │
│  │  - FastHTML web app (app/main.py)                      │ │
│  │  - Lightweight: ~200MB image                           │ │
│  │  - No ML dependencies (insightface, torch, etc.)       │ │
│  └────────────────────────────────────────────────────────┘ │
│                           │                                  │
│                           ▼                                  │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Railway Persistent Volume (/app/storage)              │ │
│  │  ├── data/        - identities.json, photo_index.json │ │
│  │  │                - embeddings.npy                     │ │
│  │  ├── raw_photos/  - source photographs                │ │
│  │  └── staging/     - upload staging area               │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ HTTPS (Cloudflare SSL)
                            ▼
                    ┌───────────────┐
                    │   Cloudflare  │
                    │   DNS/Proxy   │
                    └───────────────┘
```

## Prerequisites

- Railway account ([railway.com](https://railway.com))
- Railway CLI installed: `npm install -g @railway/cli`
- Cloudflare account with `nolanandrewfox.com` configured
- Docker installed locally (for testing)

## Step 1: Test Docker Build Locally

Before deploying, verify the Docker image works:

```bash
# Build the image
docker build -t rhodesli .
```

### Test 1: Local Development Mode (dual mount)

This mirrors local development where data/ and raw_photos/ are separate:

```bash
docker run -p 5001:5001 \
    -v $(pwd)/data:/app/data \
    -v $(pwd)/raw_photos:/app/raw_photos \
    -e PORT=5001 \
    -e DEBUG=false \
    -e PROCESSING_ENABLED=false \
    rhodesli

# Test health endpoint
curl http://localhost:5001/health
# Should return: {"status": "ok", "identities": ..., "photos": ..., "processing_enabled": false}
```

### Test 2: Railway Mode (single volume)

This mimics the Railway deployment with STORAGE_DIR:

```bash
# Create temp storage directory
mkdir -p /tmp/rhodesli-storage

# Run with single volume mount
docker run -p 5001:5001 \
    -v /tmp/rhodesli-storage:/app/storage \
    -e STORAGE_DIR=/app/storage \
    -e PORT=5001 \
    -e DEBUG=false \
    -e PROCESSING_ENABLED=false \
    rhodesli

# Init script should create:
#   /tmp/rhodesli-storage/data/
#   /tmp/rhodesli-storage/raw_photos/
#   /tmp/rhodesli-storage/staging/
#   /tmp/rhodesli-storage/.initialized

# Test health endpoint
curl http://localhost:5001/health
```

### Verification Checklist

Visit http://localhost:5001 and verify:
- [ ] App loads with dark theme
- [ ] Sidebar shows correct counts
- [ ] Focus mode displays identity with photos
- [ ] Photo viewer works
- [ ] All navigation works

## Step 2: Railway Setup

### 2.1 Login and Initialize

```bash
# Login to Railway
railway login

# Initialize new project (run from repo root)
railway init
# Name it: rhodesli
```

### 2.2 Connect GitHub Repository (Recommended)

1. Go to [railway.com](https://railway.com) dashboard
2. Click your `rhodesli` project → Settings
3. Click "Connect GitHub repo"
4. Select your `rhodesli` repository
5. Railway will auto-deploy on every push to `main`

**OR** deploy directly without GitHub:

```bash
railway up
```

## Step 3: Create Persistent Volume

Railway needs persistent storage for photos and data.

> **Important:** Railway allows only ONE persistent volume per service. We use a single
> volume mounted at `/app/storage` which contains subdirectories for data and photos.

1. In Railway dashboard, click your service
2. Open Command Palette (`⌘K` on Mac, `Ctrl+K` on Windows)
3. Select "Add Volume"

### Storage Volume
- **Name:** `rhodesli-storage`
- **Mount Path:** `/app/storage`
- **Size:** 1 GB (can grow later)

The init script automatically creates this structure inside the volume:
```
/app/storage/
├── data/          ← identities.json, photo_index.json, embeddings
├── raw_photos/    ← source photographs
└── staging/       ← upload staging area
```

> **Note:** On first deploy, the init script copies bundled data from the Docker
> image into the volume. The `.initialized` marker prevents re-copying on restarts.

## Step 4: Set Environment Variables

In Railway dashboard → Service → Variables tab:

| Variable | Value | Description |
|----------|-------|-------------|
| `HOST` | `0.0.0.0` | Network binding |
| `DEBUG` | `false` | Disable hot reload |
| `PROCESSING_ENABLED` | `false` | Disable ML processing |
| `STORAGE_DIR` | `/app/storage` | **Required:** Single volume mount path |

> **Note:** Railway automatically sets `PORT`. Your app reads it from the environment.

> **Important:** When `STORAGE_DIR` is set, `DATA_DIR` and `PHOTOS_DIR` are derived
> automatically (`/app/storage/data` and `/app/storage/raw_photos`). You do NOT need
> to set `DATA_DIR` or `PHOTOS_DIR` separately on Railway.

## Step 5: Deploy

### If connected to GitHub:

```bash
git add .
git commit -m "feat: add Docker deployment configuration"
git push origin main
```

Railway will automatically build and deploy.

### If deploying directly:

```bash
railway up
```

### Monitor Deployment

- Watch build logs in Railway dashboard
- Look for startup messages:
  ```
  ============================================================
  RHODESLI STARTUP
  ============================================================
  [config] Host: 0.0.0.0
  [config] Port: 5001
  [config] Debug: False
  [config] Processing enabled: False
  ...
  Server starting at http://0.0.0.0:5001
  ```

## Step 6: Verify Deployment

Railway provides a temporary URL like:
`rhodesli-production.up.railway.app`

### Health Check

```bash
curl https://rhodesli-production.up.railway.app/health
```

### Manual Verification

- [ ] App loads with dark theme
- [ ] Sidebar shows correct identity counts
- [ ] Focus mode works
- [ ] Browse mode works
- [ ] Photo viewer opens photos
- [ ] Photo context modal shows face boxes
- [ ] Clicking faces navigates correctly
- [ ] Upload page shows (files staged, not processed)

## Step 7: Configure Custom Domain (Cloudflare)

### 7.1 Add Domain in Railway

1. Go to Service → Settings → Domains
2. Click "Add Custom Domain"
3. Enter: `rhodesli.nolanandrewfox.com`
4. Railway shows a CNAME target (e.g., `rhodesli-production.up.railway.app`)

### 7.2 Configure DNS in Cloudflare

1. Go to [dash.cloudflare.com](https://dash.cloudflare.com)
2. Select `nolanandrewfox.com`
3. Click DNS in sidebar
4. Click "Add Record"
5. Configure:
   - **Type:** CNAME
   - **Name:** rhodesli
   - **Target:** `[Railway URL from above]`
   - **Proxy status:** Proxied (orange cloud)
   - **TTL:** Auto
6. Save

### 7.3 Verify Custom Domain

Wait 2-5 minutes for DNS propagation, then:

```bash
curl https://rhodesli.nolanandrewfox.com/health
```

Visit `https://rhodesli.nolanandrewfox.com` in browser.

## Step 8: Post-Deploy Checklist

- [ ] App accessible at `rhodesli.nolanandrewfox.com`
- [ ] HTTPS working (green lock icon)
- [ ] All photos loading correctly
- [ ] All identities visible (check `/health` count)
- [ ] Focus mode works
- [ ] Browse mode works
- [ ] Photo viewer works
- [ ] Photo context modal works
- [ ] Face thumbnails clickable
- [ ] No console errors
- [ ] Upload shows "pending admin review" message

## Production Upload Workflow

Since `PROCESSING_ENABLED=false` in production:

1. Contributors upload photos via web UI
2. Files land in `/app/storage/staging/{job_id}/`
3. Admin downloads staged files to local machine
4. Admin runs `python -m core.ingest_inbox` locally (ML deps installed)
5. Admin syncs updated data back to Railway volume

### Syncing Data to Railway

```bash
# SSH into Railway container (if needed)
railway shell

# Or use Railway CLI to copy files
railway run -- cp /local/path /app/data/
```

## Troubleshooting

### App won't start

- Check Railway logs for Python errors
- Verify `PORT` env var is being read (Railway sets it automatically)
- Check health endpoint: `/health`

### Photos not loading

- Verify `STORAGE_DIR=/app/storage` is set in Railway environment variables
- Verify the volume is mounted at `/app/storage`
- Check init script ran (look for `.initialized` marker in `/app/storage/`)
- Check Railway logs for file-not-found errors

### 502 Bad Gateway

- App might still be starting (loading embeddings)
- Health check timeout is 300s; wait for startup
- Check Railway logs for crash loops

### Custom domain not working

- Wait 5-10 minutes for DNS propagation
- Verify CNAME record in Cloudflare points to Railway URL
- Check Railway custom domain settings
- Clear browser cache and try incognito

### Out of memory

- Railway Hobby plan has 512MB RAM limit
- Embeddings.npy must fit in memory (~2.4MB currently, should be fine)
- If needed, upgrade to Pro plan

## Maintenance

### Updating the App

```bash
# Make changes locally
git add .
git commit -m "fix: description of change"
git push origin main
# Railway auto-deploys from GitHub
```

### Viewing Logs

```bash
railway logs
# Or view in Railway dashboard
```

### Redeploying

```bash
railway up
# Or trigger redeploy from dashboard
```

### Backup Data

Periodically download data from Railway volume:

```bash
railway run -- cat /app/storage/data/identities.json > backup_identities.json
railway run -- cat /app/storage/data/photo_index.json > backup_photo_index.json
```

## Cost Estimate

Railway Hobby plan ($5/month):
- 512MB RAM
- 1GB disk per volume (single volume for all storage)
- Unlimited bandwidth
- Custom domains included

For this app's current size (~350MB data + photos), Hobby plan is sufficient.

---

## Change Log

| Date | Change | Triggered By | Session |
|------|--------|--------------|---------|
| 2026-02-05 | Switch to single volume mount (STORAGE_DIR=/app/storage) | Railway only allows 1 volume per service | Deployment fix session |
