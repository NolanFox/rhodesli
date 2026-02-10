# Photo Workflow

How photos flow through Rhodesli from ingestion to display.

## 1. Adding New Photos (Admin, Local Workflow)

This is the primary workflow today. It runs entirely on the admin's local machine.

1. **Place photos** in `raw_photos/` (organized in subdirectories by collection/source).
2. **Run the ML pipeline**: `python -m core.ingest` to detect faces, generate embeddings, and build identity clusters.
3. **Upload photos to R2**: `python -m scripts.upload_to_r2` pushes images to Cloudflare R2 for web serving.
4. **Sync data to Railway**: Deploy with `railway up --no-gitignore` or use the admin export endpoints to pull updated data back from production.

The heavy AI work (face detection, embedding generation, clustering) happens locally via InsightFace/AdaFace. The web server never runs ML inference.

## 2. Web App Uploads

The web upload endpoint (`/upload`) supports two roles:

### Admin Uploads
- All uploads go to `data/staging/{job_id}/` for processing or moderation
- When `PROCESSING_ENABLED=true` (local dev), a subprocess runs the ML pipeline immediately
- When `PROCESSING_ENABLED=false` (production), files sit staged for local processing

### Contributor Uploads (Pending Queue)
- Logged-in non-admin users can upload photos via `/upload`
- Files are saved to `data/staging/{job_id}/` with a pending status
- A record is created in `data/pending_uploads.json` tracking the submission
- Admin is optionally notified via email (if Resend API key is configured)
- Admin reviews pending uploads at `/admin/pending`
- Admin can approve or reject each submission
- Approved uploads are processed via `scripts/process_pending.py` (locally)

### Pending Upload Lifecycle
```
Contributor uploads → data/staging/{job_id}/ + pending_uploads.json
                           ↓
                    Admin reviews at /admin/pending
                           ↓
                    Approve → status="approved"
                    Reject  → status="rejected", files cleaned up
                           ↓
                    Admin runs: python scripts/process_pending.py --execute
                           ↓
                    Approved files processed through ML pipeline
```

## 3. Processing Staged Uploads (End-to-End)

When someone uploads photos on the live site, files land in `data/staging/` on the Railway volume. The ML pipeline runs locally — here's the full flow:

```
Contributor uploads on rhodesli.nolanandrewfox.com
         ↓
Files land in data/staging/{job_id}/ on Railway
         ↓
Admin runs: ./scripts/process_uploads.sh (or step-by-step below)
         ↓
1. Download staged photos to raw_photos/pending/
2. Run face detection + embedding generation
3. Run clustering to match faces to known identities
4. Upload photos + crops to R2
5. Push updated data to production (git push → Railway redeploy)
6. Clear staging on production
         ↓
Photos appear on the site with detected faces
```

### One-Command Pipeline

```bash
# Full pipeline (interactive, confirms before destructive steps)
./scripts/process_uploads.sh

# Preview mode — download + ML only, no R2 upload or deploy
./scripts/process_uploads.sh --dry-run
```

### Step-by-Step (Manual)

```bash
# 1. Download staged photos from production
python scripts/download_staged.py              # download to raw_photos/pending/
python scripts/download_staged.py --dry-run    # list what's staged without downloading

# 2. Face detection + embeddings
python -m core.ingest_inbox --directory raw_photos/pending/ --job-id staged-$(date +%Y%m%d)

# 3. Clustering (find matches)
python scripts/cluster_new_faces.py --dry-run   # review proposals
python scripts/cluster_new_faces.py --execute   # apply matches

# 4. Upload to R2
python scripts/upload_to_r2.py --dry-run       # preview
python scripts/upload_to_r2.py --execute       # upload

# 5. Commit + deploy
git add data/ && git commit -m "data: process staged uploads"
git push  # triggers Railway auto-deploy

# 6. Clear staging on production
python scripts/download_staged.py --clear-after
```

### Sync API Endpoints

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `GET /api/sync/status` | None | Server stats (public) |
| `GET /api/sync/identities` | Bearer token | Download identities.json |
| `GET /api/sync/photo-index` | Bearer token | Download photo_index.json |
| `GET /api/sync/staged` | Bearer token | List staged upload files |
| `GET /api/sync/staged/download/{path}` | Bearer token | Download a staged file |
| `POST /api/sync/staged/clear` | Bearer token | Remove processed staged files |

All token-authenticated endpoints use `RHODESLI_SYNC_TOKEN` via Bearer header.

### Syncing Data Only (No Uploads)

```bash
# Pull latest identities.json + photo_index.json from production
python scripts/sync_from_production.py

# Dry run (compare without writing)
python scripts/sync_from_production.py --dry-run
```

## 4. ML Clustering Scripts

For evaluating and improving ML accuracy:

| Script | Purpose |
|--------|---------|
| `scripts/build_golden_set.py` | Extract ground truth from confirmed identities |
| `scripts/evaluate_golden_set.py` | Measure precision/recall/F1 at various thresholds |
| `scripts/cluster_new_faces.py` | Match new faces against confirmed identities (multi-anchor, AD-001) |
| `scripts/validate_clustering.py` | Compare clustering proposals against admin tagging decisions |
| `scripts/calibrate_thresholds.py` | Combine golden set + validation evidence for threshold calibration |
| `scripts/apply_cluster_matches.py` | Apply approved matches with tiered confidence (--tier very_high\|high\|moderate) |

All scripts support `--dry-run` (default) and `--execute` flags.

### Clustering Workflow

```bash
# 1. Rebuild golden set from current confirmed identities
python scripts/build_golden_set.py --execute

# 2. Evaluate precision/recall across thresholds
python scripts/evaluate_golden_set.py --sweep

# 3. Find new matches (dry-run to review)
python scripts/cluster_new_faces.py --dry-run

# 4. Validate proposals against admin's manual tagging
python scripts/validate_clustering.py

# 5. Apply only slam-dunk matches (VERY_HIGH tier, <0.80 distance)
python scripts/apply_cluster_matches.py --dry-run --tier very_high
python scripts/apply_cluster_matches.py --execute --tier very_high

# 6. Apply confident matches (HIGH tier, <1.05, zero FP in golden set)
python scripts/apply_cluster_matches.py --execute --tier high
```

### Confidence Tiers (AD-013, calibrated 2026-02-09)

| Tier | Distance | Precision | Action |
|------|----------|-----------|--------|
| VERY HIGH | < 0.80 | ~100% | Safe to auto-apply as candidates |
| HIGH | < 1.05 | 100% | Zero FP in golden set (3713 negative pairs) |
| MODERATE | < 1.15 | ~94% | Show with caution — FPs are family resemblance |
| LOW | < 1.25 | ~69% | Deep search only |

## 5. Future Vision

The long-term plan:

1. **Background ML processing**: A worker service (or scheduled job) picks up approved uploads, runs face detection and embedding generation, and updates the data files.
2. **Automatic sync**: Data changes on the processing worker propagate to the web server without manual intervention.
3. **Community annotations**: Contributors can suggest names, dates, locations for identities and photos.
