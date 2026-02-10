# Upload Processing Pipeline

**Last updated:** 2026-02-10

The canonical way to process uploaded photos is:

```bash
python scripts/process_uploads.py
```

---

## Quick Start

```bash
# 1. Activate venv
source venv/bin/activate

# 2. Run the pipeline (interactive mode)
python scripts/process_uploads.py

# 3. Or dry-run (download + ML + clustering preview, no upload/push)
python scripts/process_uploads.py --dry-run

# 4. Or auto mode (no prompts except clustering review)
python scripts/process_uploads.py --auto
```

---

## Pipeline Steps

| Step | What It Does | Script |
|------|-------------|--------|
| 1. Backup | Creates timestamped backups of identities.json and photo_index.json | (built-in) |
| 2. Download | Fetches staged photos from production to `raw_photos/pending/` | `download_staged.py` |
| 3. ML Processing | Runs face detection and embedding generation on new photos | `core.ingest_inbox` |
| 4. Clustering | Finds matches against confirmed identities (always pauses for review) | `cluster_new_faces.py` |
| 5. R2 Upload | Uploads new photos and face crops to Cloudflare R2 | `upload_to_r2.py` |
| 6. Push Data | Pushes updated identities.json and photo_index.json to production | `push_to_production.py` |
| 7. Clear Staging | Removes processed files from production staging area | `download_staged.py --clear-after` |

---

## Modes

- **Interactive** (default): Prompts for confirmation before upload, push, and clear steps
- **`--auto`**: Skips prompts except at the clustering review step (step 4)
- **`--dry-run`**: Runs steps 1-4 only; no upload, push, or staging clear

The clustering step (step 4) **always** pauses for human review, even in `--auto` mode.

---

## Manual Step-by-Step

For debugging individual steps:

```bash
# Step 1: Backup
cp data/identities.json data/backups/identities.json.manual.bak
cp data/photo_index.json data/backups/photo_index.json.manual.bak

# Step 2: Download staged photos
python scripts/download_staged.py --dest raw_photos/pending/

# Step 3: Face detection
python -m core.ingest_inbox --directory raw_photos/pending/ \
    --job-id staged-$(date +%Y%m%d) --source "Collection Name"

# Step 4: Clustering preview
python scripts/cluster_new_faces.py --dry-run

# Step 5: Upload to R2
python scripts/upload_to_r2.py --execute

# Step 6: Push to production
python scripts/push_to_production.py

# Step 7: Clear staging
python scripts/download_staged.py --clear-after
```

---

## Required Environment Variables

Set in `.env` or export before running:

| Variable | Required For | Description |
|----------|-------------|-------------|
| `RHODESLI_SYNC_TOKEN` | All steps | API auth token for production |
| `R2_ACCOUNT_ID` | Step 5 (upload) | Cloudflare account ID |
| `R2_ACCESS_KEY_ID` | Step 5 (upload) | R2 API access key |
| `R2_SECRET_ACCESS_KEY` | Step 5 (upload) | R2 API secret |
| `R2_BUCKET_NAME` | Step 5 (upload) | R2 bucket name |

R2 variables are not needed for `--dry-run` mode.

---

## Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| "No staged files" | Nothing uploaded on production | Upload photos via the web UI first |
| "Unauthorized" at download | Wrong or missing sync token | Check `RHODESLI_SYNC_TOKEN` in `.env` |
| R2 upload fails | Missing R2 credentials | Set all 4 `R2_*` variables in `.env` |
| Push returns 404 | Push API not deployed | Deploy latest code to Railway first |
| "0 candidates" in clustering | No INBOX/PROPOSED/SKIPPED faces | Check if faces were already processed |
| SSL errors on macOS | Missing certificates | `pip install certifi` |

---

## Restoring from Backup

Backups are in `data/backups/` with timestamps:

```bash
# List backups
ls -la data/backups/

# Restore identities
cp data/backups/identities.json.YYYYMMDD-HHMMSS.bak data/identities.json

# Restore photo index
cp data/backups/photo_index.json.YYYYMMDD-HHMMSS.bak data/photo_index.json

# Push restored data to production
python scripts/push_to_production.py
```

The preflight backup (`identities.json.preflight`) from the last stress test is also available as a secondary reference.
