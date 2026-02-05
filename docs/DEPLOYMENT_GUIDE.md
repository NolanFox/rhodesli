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

## Deployment Modes (Critical)

Railway deployments can come from two sources with **DIFFERENT behaviors**:

### CLI Deploy (`railway up`)

- Uploads files from your **LOCAL machine**
- **CRITICAL:** Railway CLI uses `.gitignore` by default, NOT just `.railwayignore`
- `data/` and `raw_photos/` are gitignored, so they're excluded unless you use `--no-gitignore`
- **Use for:** Initial deploy, adding new photos, reseeding data
- **Required when:** You need to upload data/raw_photos to the image bundles

```bash
# Standard deploy (uses .gitignore - excludes data/)
railway up

# Full deploy including gitignored files (use for seeding data)
railway up --no-gitignore
```

> **Size Limit Warning:** Railway/Cloudflare has upload size limits (~100MB). If upload fails with
> "413 Payload Too Large", update `.railwayignore` to exclude large files like `raw_photos/` and
> `data/embeddings.npy`. The app can work with just JSON data (face crops are separate).

### Git Deploy (`git push` or Dashboard redeploy)

- Builds from your **GitHub REPOSITORY**
- Respects `.gitignore`
- `data/` and `raw_photos/` are NOT included (they're gitignored)
- **Use for:** Code changes, config updates, bug fixes
- **Works because:** Volume already has data from previous CLI deploy

```bash
git push origin main
```

### The Golden Rule

| Scenario | Method | Why |
|----------|--------|-----|
| First deploy ever | `railway up` | Seeds volume with photos/data |
| Code changes only | `git push` | Photos already on volume |
| Adding new photos | `railway up` | Re-bundles with new photos |
| Fixing a bug | `git push` | No data change needed |
| Volume is empty/corrupted | `railway up` + reset | See Reset Protocol below |
| Config/env changes | Railway dashboard | No build needed |

### Understanding the Init Script

The init script (`scripts/init_railway_volume.py`) runs on every container start:

1. **If `.initialized` marker exists AND data is valid** → Skip seeding (normal operation)
2. **If `.initialized` exists BUT data is missing** → Remove marker, attempt re-seed
3. **If no marker AND bundles have data** → Copy to volume, create marker
4. **If no marker AND bundles are empty** → Log error, do NOT create marker

The marker is ONLY created when data is successfully copied. This prevents "initialized but empty" corruption.

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

### Upload too large (413 Payload Too Large)

- Railway/Cloudflare has upload size limits (~100MB)
- Full `data/` + `raw_photos/` can exceed this (~340MB)
- Solution: Update `.railwayignore` to exclude large files:
  ```
  raw_photos/*
  !raw_photos/.gitkeep
  data/backups/
  data/embeddings.npy
  ```
- The app works with just JSON files (identities.json, photo_index.json)
- Face crops are served from a separate location

### Data bundle is empty after `railway up`

- Railway CLI uses `.gitignore` by default
- `data/` is gitignored, so it's excluded from upload
- Solution: Use `railway up --no-gitignore` to include gitignored files

## Reset Protocol

If the site shows 0 photos or the volume is stuck in a bad state:

### Step 1: Set temporary start command

In Railway Dashboard → Settings → Deploy → Custom Start Command:

```bash
rm -f /app/storage/.initialized && python scripts/init_railway_volume.py && python app/main.py
```

### Step 2: Deploy from CLI (NOT dashboard)

```bash
# Use --no-gitignore to include the gitignored data/ directory
railway up --no-gitignore
```

This ensures data files are in the build AND the marker is cleared.

> **Note:** If upload fails due to size limits, update `.railwayignore` to exclude `raw_photos/*`
> and `data/embeddings.npy`, then retry. The app works with just JSON data.

### Step 3: Verify data loaded

Check deploy logs for:
```
[init] Copying data from /app/data_bundle to /app/storage/data...
[init] Copied X data items.
[init] Copying photos from /app/photos_bundle to /app/storage/raw_photos...
[init] Copied Y photos.
```

And startup logs for:
```
[data] Photos found: 112
[data] Identities loaded: 268
```

### Step 4: Clear the start command

Go back to Railway Dashboard → Settings → Deploy → Custom Start Command.
Delete the command (make it empty).

### Step 5: Confirm clean startup

Run `railway up` once more (or let GitHub auto-deploy).
The logs should show:
```
[init] Volume already initialized and valid, skipping seed.
```

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
| 2026-02-05 | Document --no-gitignore flag and upload size limits | Railway CLI uses .gitignore, excluding data/ | Autonomous debug session |
| 2026-02-05 | Add Reset Protocol for corrupted/empty volumes | Init script created marker even when empty | Init script hardening |
| 2026-02-05 | Expand Deployment Modes with CLI vs Git explanation | Confusion about which method to use when | Init script hardening |
| 2026-02-05 | Add Deployment Modes section (CLI vs GitHub) | GitHub deploys fail on missing gitignored dirs | Dockerfile GitHub fix |
| 2026-02-05 | Switch to single volume mount (STORAGE_DIR=/app/storage) | Railway only allows 1 volume per service | Deployment fix session |
