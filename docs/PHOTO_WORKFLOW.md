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

The web upload endpoint (`/upload`) is currently **admin-only** (until a moderation queue is built in Phase D).

- Uploaded files go to `data/staging/` on the server.
- `PROCESSING_ENABLED=false` by default in production, so uploaded files sit unprocessed.
- When processing is enabled, the server spawns a subprocess for ingestion. This requires ML dependencies which are not present on Railway.

In practice, web uploads are used for receiving photos from family members. The admin then downloads them, processes locally, and re-deploys.

## 3. Syncing Data

Admin export endpoints allow downloading the canonical data files from production:

| Endpoint | Returns |
|----------|---------|
| `GET /admin/export/identities` | `identities.json` as a download |
| `GET /admin/export/photo-index` | `photo_index.json` as a download |
| `GET /admin/export/all` | ZIP containing both files |

All endpoints require admin authentication.

### Using the sync script

```bash
# Set up cookies (one-time, after logging in via browser)
# Export your session cookie to cookies.txt

# Sync production data to local repo
./scripts/sync_from_production.sh

# Review changes
git diff data/
```

You can override the production URL:

```bash
SITE_URL=https://staging.example.com ./scripts/sync_from_production.sh
```

## 4. Future Vision

The long-term plan (Phase D and beyond):

1. **Web upload** by any authenticated user (not just admin).
2. **Moderation queue**: Uploaded photos land in an admin review queue before entering the pipeline.
3. **Background ML processing**: A worker service (or scheduled job) picks up approved uploads, runs face detection and embedding generation, and updates the data files.
4. **Automatic sync**: Data changes on the processing worker propagate to the web server without manual intervention.

Until then, the local-first workflow described in section 1 is the primary path.
