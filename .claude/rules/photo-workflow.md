---
paths:
  - "scripts/download_staged.py"
  - "scripts/process_uploads.sh"
  - "scripts/process_pending.py"
  - "scripts/sync_from_production.py"
  - "scripts/upload_to_r2.py"
  - "core/ingest.py"
  - "core/ingest_inbox.py"
---

# Photo Workflow Rules

Before modifying upload, sync, or ingestion scripts, read docs/PHOTO_WORKFLOW.md.

Key rules:
1. All scripts support `--dry-run` (default) and require `--execute` to make changes
2. ML processing happens locally, never on the web server
3. Staged uploads live in `data/staging/{job_id}/` — never modify `raw_photos/` directly from the web app
4. Sync uses Bearer token auth (`RHODESLI_SYNC_TOKEN`), not session cookies (Lesson #42)
5. Photos go to R2 via `upload_to_r2.py`, never served through Python proxy routes (OD-004)
