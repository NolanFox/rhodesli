# Rhodesli Deployment Guide

Deploy Rhodesli to Railway with a custom domain on Cloudflare.

## Pre-Deployment Checklist

**Complete this checklist BEFORE writing deployment code for any new platform.**

### Platform Research
- [x] Documented upload/build size limits (Railway: ~100MB)
- [x] Documented memory limits (Railway: 512MB-8GB)
- [x] Documented disk/volume limits (Railway: included on Hobby)
- [x] Documented timeout limits (Railway: 15 min build)
- [x] Checked pricing model (Railway: $5-20/mo)

### Asset Inventory (Rhodesli)

| Asset Type | Size | Location | Rationale |
|------------|------|----------|-----------|
| Application code | ~10MB | Docker image | Changes frequently |
| JSON data | ~500KB | Railway volume | Persists, too large for env vars |
| Embeddings | ~2.3MB | Railway volume | Persists, binary data |
| Photos | ~255MB | **Cloudflare R2** | Too large for Docker/volume seeding |
| Face crops | ~20MB | **Cloudflare R2** | Derived from photos |

### Deployment Spike
- [x] Tested basic deploy works
- [x] Validated photo storage approach (R2 required due to size limits)

### Assumptions Validated
- [x] Railway can handle JSON data seeding via volume (~5MB) ✓
- [x] Railway CANNOT handle 255MB photo uploads ✗ → Use R2
- [x] Cloudflare R2 can serve photos publicly ✓

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  Railway (rhodesli.nolanandrewfox.com)                      │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Docker Container (python:3.11-slim)                   │ │
│  │  - FastHTML web app (app/main.py)                      │ │
│  │  - Lightweight: ~50MB image                            │ │
│  │  - No ML dependencies, no photos bundled               │ │
│  └────────────────────────────────────────────────────────┘ │
│                           │                                  │
│                           ▼                                  │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Railway Persistent Volume (/app/storage)              │ │
│  │  └── data/        - identities.json, photo_index.json │ │
│  │                   - embeddings.npy (~2.3MB)            │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
         │                                    │
         │ HTTPS                              │ Photo URLs
         ▼                                    ▼
┌─────────────────┐               ┌─────────────────────────┐
│   Cloudflare    │               │   Cloudflare R2         │
│   DNS/Proxy     │               │   (Object Storage)      │
└─────────────────┘               │   ├── raw_photos/       │
                                  │   └── crops/            │
                                  └─────────────────────────┘
```

**Key insight:** Photos (~255MB) are served from Cloudflare R2, not bundled in the Docker image. This avoids Railway's upload size limits and allows simple `git push` deploys.

## Prerequisites

- Railway account ([railway.com](https://railway.com))
- Railway CLI installed: `npm install -g @railway/cli`
- Cloudflare account with `nolanandrewfox.com` configured
- Docker installed locally (for testing)

## Deployment Overview

With the R2 architecture, deployment is now simple:

| What | Where | How to Update |
|------|-------|---------------|
| Photos + Crops | Cloudflare R2 | `python scripts/upload_to_r2.py --execute` |
| JSON Data | Railway Volume | Bundled in Docker image, copied to volume on first run |
| Application Code | Docker Image | `git push origin main` |

### Typical Workflows

| Scenario | Steps |
|----------|-------|
| **First deploy** | 1. Set up R2 bucket, 2. Upload photos to R2, 3. Set env vars, 4. `git push` |
| **Code changes** | `git push origin main` |
| **Add new photos** | `python scripts/upload_to_r2.py --execute` (no redeploy needed) |
| **Fix a bug** | `git push origin main` |

### Understanding the Init Script

The init script (`scripts/init_railway_volume.py`) runs on every container start:

1. **If `.initialized` marker exists AND data is valid** → Skip seeding (normal operation)
2. **If `.initialized` exists BUT data is missing** → Remove marker, attempt re-seed
3. **If no marker AND bundles have data** → Copy JSON to volume, create marker
4. **If no marker AND bundles are empty** → Log error, do NOT create marker

The marker is ONLY created when data is successfully copied. Photos are NOT seeded from bundles - they come from R2.

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

## Step 2: Cloudflare R2 Setup

Photos and face crops are served from Cloudflare R2, not bundled in the Docker image.
This keeps the image small and allows `git push` deploys without size limits.

### 2.1 Create R2 Bucket

1. Go to [Cloudflare Dashboard](https://dash.cloudflare.com)
2. Navigate to **R2** in the sidebar
3. Click **Create bucket**
4. Name it: `rhodesli-photos`
5. Choose location: **Automatic** (or closest to your users)
6. Click **Create bucket**

### 2.2 Enable Public Access

By default, R2 buckets are private. We need public read access for photos.

1. Open your bucket (`rhodesli-photos`)
2. Go to **Settings** tab
3. Under **Public access**, click **Allow Access**
4. Confirm the warning about public access
5. Copy the **Public bucket URL** (e.g., `https://pub-abc123.r2.dev`)

> **Save this URL!** You'll need it for the `R2_PUBLIC_URL` environment variable.

### 2.3 Create API Token

Create credentials for uploading photos:

1. Go to **R2** → **Manage R2 API Tokens**
2. Click **Create API Token**
3. Name: `rhodesli-upload`
4. Permissions: **Object Read & Write**
5. Specify bucket: `rhodesli-photos` (or leave blank for all buckets)
6. Click **Create API Token**
7. **Copy immediately:**
   - Access Key ID
   - Secret Access Key

> **Warning:** The secret is only shown once. Save it securely.

### 2.4 Upload Photos to R2

From your local machine with the photos:

```bash
# Set environment variables
export R2_ACCOUNT_ID=your-account-id          # From Cloudflare dashboard URL
export R2_ACCESS_KEY_ID=your-access-key       # From step 2.3
export R2_SECRET_ACCESS_KEY=your-secret-key   # From step 2.3
export R2_BUCKET_NAME=rhodesli-photos

# Preview what would be uploaded
python scripts/upload_to_r2.py --dry-run

# Actually upload (~5 minutes for 255MB)
python scripts/upload_to_r2.py --execute
```

The script uploads:
- `raw_photos/` → `rhodesli-photos/raw_photos/`
- `app/static/crops/` → `rhodesli-photos/crops/`

### 2.5 Verify R2 Upload

After upload, verify photos are accessible:

```bash
# Replace with your actual public URL
curl -I "https://pub-abc123.r2.dev/raw_photos/some-photo.jpg"
# Should return: HTTP/2 200
```

Or visit the URL in your browser - you should see the photo.

## Step 3: Railway Setup

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

## Step 4: Create Persistent Volume

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

## Step 5: Set Environment Variables

In Railway dashboard → Service → Variables tab:

### Required Variables

| Variable | Value | Description |
|----------|-------|-------------|
| `HOST` | `0.0.0.0` | Network binding |
| `DEBUG` | `false` | Disable hot reload |
| `PROCESSING_ENABLED` | `false` | Disable ML processing |
| `STORAGE_DIR` | `/app/storage` | Single volume mount path |
| `STORAGE_MODE` | `r2` | **Required:** Tell app to use R2 for photos |
| `R2_PUBLIC_URL` | `https://pub-xxx.r2.dev` | **Required:** Your R2 public bucket URL from step 2.2 |

> **Note:** Railway automatically sets `PORT`. Your app reads it from the environment.

> **Important:** When `STORAGE_DIR` is set, `DATA_DIR` and `PHOTOS_DIR` are derived
> automatically (`/app/storage/data` and `/app/storage/raw_photos`). You do NOT need
> to set `DATA_DIR` or `PHOTOS_DIR` separately on Railway.

### R2 Upload Variables (Not needed on Railway)

These are only used locally for `scripts/upload_to_r2.py`. You don't need to set them on Railway:

| Variable | Used For |
|----------|----------|
| `R2_ACCOUNT_ID` | Uploading photos |
| `R2_ACCESS_KEY_ID` | Uploading photos |
| `R2_SECRET_ACCESS_KEY` | Uploading photos |
| `R2_BUCKET_NAME` | Uploading photos |

## Step 6: Deploy

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

## Step 7: Verify Deployment

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

## Step 8: Configure Custom Domain (Cloudflare)

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

## Step 9: Post-Deploy Checklist

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
