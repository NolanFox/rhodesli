# Upload Pipeline Test Report

## Date: 2026-02-10
## Photos Uploaded: 1 batch, 2 photos (Zeb Capuano / Newspapers.com)

### Step Results
| Step | Status | Notes |
|------|--------|-------|
| Download staged | PASS | 2 photos + 1 metadata file from Railway staging |
| ML processing | PASS | 2 faces detected (1 per photo), 2 INBOX identities created |
| Clustering (dry-run) | PASS | No matches at threshold 1.05 (expected - new person not in confirmed set) |
| R2 upload | PASS | 4 files uploaded (2 photos + 2 crops), verified in bucket |
| Push to production | PASS | New push API endpoint built and deployed, data synced |
| Clear staging | PASS | 0 files remaining on production |

### Data Integrity
- Photos before/after: 124 -> 126 (+2)
- Identities before/after: 292 -> 294 (+2 INBOX)
- Face-to-photo mappings: 373 -> 375 (+2)
- Confirmed unchanged: YES (23)
- All R2 URLs valid: YES (verified via boto3 head_object)
- All face references valid: YES
- All crops exist: YES (76KB + 82KB)

### Clustering Proposals (at default threshold 1.05)
- Total: 0 (expected - these are newspaper photos of "Zeb Capuano", not in confirmed set)
- At wider threshold (1.5): 250 proposals, but new faces scored LOW (1.30, 1.33)
- Closest match for new faces: Victoria Capuano Capeluto (1.30) and Isaac Louza (1.33)

### Bugs Found & Fixed

1. **Data corruption during test suite (CRITICAL)**
   - The `/api/photo/{id}/collection` route called `photo_reg.save(photo_index_path)` directly
     instead of `save_photo_registry(photo_reg)`. This bypassed the mockable save function,
     causing test fixture data (3 placeholder photos) to overwrite real `data/photo_index.json`
     on every test run.
   - Fix: Changed to use `save_photo_registry()` which is properly intercepted by test patches.
   - Commit: `186e22b`

2. **No push-to-production mechanism**
   - The upload pipeline had no way to push locally-processed data back to Railway.
     `process_uploads.sh` attempted `git add data/` but data/ is gitignored.
   - Fix: Added `POST /api/sync/push` endpoint + `scripts/push_to_production.py` CLI tool.
     Token-authenticated, creates backups before overwriting, validates structure.
   - Commit: `2487abf`

3. **Photos stuck in raw_photos/pending/ after download**
   - Downloaded photos landed in `raw_photos/pending/` but photo_index recorded the path
     with the pending/ subdirectory. All existing photos are at `raw_photos/` root level.
   - Fix: Moved photos to `raw_photos/` and updated photo_index paths to match convention.

### Bugs Found & NOT Fixed (needs human attention)
- None

### Pipeline Timing
- Download staged: ~5 seconds
- ML processing (2 photos): ~30 seconds (InsightFace CPU mode)
- Clustering dry-run: ~5 seconds
- R2 upload (4 files): ~3 seconds
- Push to production: ~2 seconds
- Total pipeline: ~45 seconds for 2 photos

### Recommendations
- The 2 new photos show "Zeb Capuano" from Lido newspaper clippings. The admin should:
  1. Review the faces at `/inbox` on the live site
  2. If they recognize the person, tag them (the ML had no match)
  3. Consider renaming from "Unidentified Person 289/290" to actual names
