# Session 97 Prompt — Charlie Fox Collection Ingest + Post-Upload Intelligence Pipeline

## Context
- 636 photos from Uncle Charlie (Roland Fox's brother), digitized by cousin David
- Files located at: `~/Downloads/fox_photos_for_rhodesli/Charlie/`
- All small JPGs (~5MB each)
- Collection: "Charles Fox Dayton Ohio Collection"
- Source: "Personal Photos"
- Community: Fox Family (`fox-family` slug, existing in Supabase)
- Cross-community overlap: Betty Capeluto and Roland Fox are confirmed identities in Rhodes archive and appear prominently in this collection
- PRD-037: Post-Upload Intelligence Pipeline (auto-cluster + GEDCOM triage + batch Gemini)

## Pre-Requisites
- Read `tasks/lessons.md` + `tasks/todo.md`
- Read `docs/prds/037_post_upload_intelligence.md`
- Set `.claude/current_session.txt` to `97`

---

## Act 1: Orient + Validate Photos (5 min)

1. Count files in `~/Downloads/fox_photos_for_rhodesli/Charlie/`
2. Verify file types (should be JPGs), check total size
3. Spot-check a few filenames to understand naming convention
4. Confirm Fox Family community exists in Supabase: `communities` table, slug=`fox-family`
5. Confirm `photo_communities` table is ready for tagging
6. Check current embeddings count (`data/embeddings.npy`) — note starting size
7. Check current identity count — note starting size
8. Log all numbers in session log for before/after comparison

**Commit:** `docs: session 97 orient — {N} photos validated, starting state logged`
**/clear**

---

## Act 2: Ingest Photos via Local Pipeline (30-60 min)

### Important: This is a large batch. Monitor for issues.

1. **Activate venv:** `source venv/bin/activate`

2. **Run ingest in batches** (to avoid memory issues with 636 photos):
   ```bash
   # Check if ingest_inbox supports --dir or needs individual files
   python -m core.ingest_inbox --help
   ```

   If `--dir` is supported:
   ```bash
   python -m core.ingest_inbox \
     --dir ~/Downloads/fox_photos_for_rhodesli/Charlie/ \
     --job-id fox-charlie-001 \
     --source "Personal Photos" \
     --collection "Charles Fox Dayton Ohio Collection" \
     --data-dir data/ \
     --crops-dir app/static/crops/
   ```

   If `--dir` is NOT supported, process in sub-batches:
   ```bash
   # Split files into groups of ~100 and process sequentially
   # Watch memory usage between batches
   ```

3. **Monitor during ingest:**
   - Memory usage: `ps aux | grep python | head -5`
   - Status file: `cat data/inbox/fox-charlie-001.status.json`
   - Face detection rate: expect 1-3 faces per photo average
   - Log any errors or warnings to session log
   - If OOM or crash: note which file it stopped on, restart from there

4. **Post-ingest validation:**
   - Count new embeddings: `python -c "import numpy as np; d=np.load('data/embeddings.npy', allow_pickle=True); print(len(d))"`
   - Count new identities in `data/identities.json`
   - Count new photos in `data/photo_index.json`
   - Verify face crops generated: `ls app/static/crops/ | wc -l`
   - Log: photos processed, faces detected, identities created, errors

5. **Lessons to capture:**
   - How long did 636 photos take?
   - Any memory issues? Peak RAM?
   - Any file format issues (despite being "all JPGs")?
   - Any face detection failures? Which photos?
   - Did any photos have 0 faces detected?

**Commit:** `feat: ingest Charlie Fox collection — {N} photos, {M} faces detected`
**/clear**

---

## Act 3: Tag Photos to Fox Family Community (5 min)

1. Get the Fox Family `community_id` from Supabase `communities` table
2. For every photo_id created in Act 2, insert into `photo_communities`:
   ```python
   from app.supabase_data import add_photo_to_community
   for photo_id in new_photo_ids:
       add_photo_to_community(photo_id, fox_family_community_id)
   ```
3. Verify count: `SELECT COUNT(*) FROM photo_communities WHERE community_id = '{fox_family_id}'`
4. Quick sanity: the Fox Family browse page should now show these photos (after cache expiry)

**Commit:** `feat: tag {N} Charlie Fox photos to fox-family community`
**/clear**

---

## Act 4: Auto-Cluster Against Known Identities (15 min)

This is PRD-037 Phase 1 — but run manually first for this collection.

1. Run clustering:
   ```bash
   python scripts/cluster_new_faces.py --dry-run 2>&1 | tee cluster_dryrun.log
   ```
2. Analyze results:
   - How many Tier 1 matches (<0.85 distance)? Which identities?
   - How many Tier 2 matches (0.85-1.30)? Which identities?
   - **Specifically look for Betty Capeluto and Roland Fox matches**
   - How many faces had no match (>1.30)?
3. If dry-run looks good:
   ```bash
   python scripts/cluster_new_faces.py --execute 2>&1 | tee cluster_execute.log
   ```
4. Document: top 20 identities by face count (descending). This is the "GEDCOM triage list."
5. Save clustering results to session log

**Commit:** `feat: auto-cluster Charlie Fox faces — {T1} Tier 1, {T2} Tier 2 matches`
**/clear**

---

## Act 5: Upload to R2 + Push to Production (10 min)

1. Upload new photos to R2:
   ```python
   # Use boto3 directly for new files only (not upload_to_r2.py which re-uploads all)
   import boto3
   # Upload raw_photos/ new files + crops/ new files
   ```
2. Push data files to git:
   ```bash
   git add data/identities.json data/photo_index.json data/embeddings.npy
   git commit -m "data: Charlie Fox collection — {N} photos, {M} faces, {K} clustered"
   git push origin main
   ```
3. Verify production loads correctly (wait for deploy, then check)

**Commit:** data commit above
**/clear**

---

## Act 6: Build Post-Upload Auto-Cluster (PRD-037 Phase 1) (20 min)

Wire auto-clustering into the upload background thread so it runs automatically after every upload.

1. In `app/upload_routes.py`, after `process_directory()` succeeds in `_background_ingest()`:
   ```python
   # Auto-cluster new faces against confirmed identities
   from core.auto_cluster import run_backfill
   # Only cluster faces from THIS upload batch
   cluster_result = run_backfill(...)
   ```
2. Add cluster summary to upload status response
3. Tests:
   - Test that auto-cluster runs after successful ingest
   - Test that auto-cluster failure doesn't block the upload (try/except)
   - Test that cluster results are logged
4. Update `upload_batches` table with cluster status

**Commit:** `feat(upload): auto-cluster after ingest — PRD-037 Phase 1`
**/clear**

---

## Act 7: Build GEDCOM Triage Page (PRD-037 Phase 2) (30 min)

New page: `/admin/upload-review` — shows top identities by face count for GEDCOM linking.

1. Route: `GET /admin/upload-review?batch={job_id}` or `GET /admin/upload-review` (latest batch)
2. Query: all INBOX/PROPOSED identities from latest upload, grouped by face count
3. Display per identity:
   - Face thumbnail grid (top 6 faces)
   - Total face count
   - GEDCOM link status: "Linked to [GEDCOM person]" or "Not linked"
   - **Inline GEDCOM search + link button** (reuse existing search component)
   - Match confidence (Tier 1 / Tier 2 indicator)
4. Sort: by face count descending (most faces = most impactful to link)
5. Action buttons:
   - "Link to GEDCOM" → inline search panel
   - "Confirm Identity" → quick confirm
   - "Skip" → move on
6. Footer: "Run Gemini Estimation" button (disabled until ≥1 identity linked, shows cost estimate)
7. Tests: route returns 200, shows identities, inline GEDCOM search works

**Commit:** `feat: GEDCOM triage page — PRD-037 Phase 2`
**/clear**

---

## Act 8: Verification + Assessment (10 min)

1. Re-read this prompt
2. Verify each act completed
3. Browser-verify Fox Family at `/c/fox-family/?section=photos` shows Charlie Fox photos
4. Browser-verify clustering results visible in triage/discoveries
5. Write assessment: `docs/assessments/session-97-assessment.md`
6. Update: CHANGELOG, ROADMAP, BACKLOG, session log
7. Run `make test-fast`

**Commit:** `docs: session 97 assessment — Charlie Fox collection + PRD-037`

---

## Key Risks
- **Memory:** 636 photos × InsightFace face detection could OOM on laptop. Monitor RAM. If needed, batch in groups of 100.
- **Clustering time:** ~1000 new faces × ~900 confirmed identities = ~900K distance computations. Should be <30s but monitor.
- **R2 upload:** 636 photos × ~5MB = ~3.2GB upload. Use parallel uploads if possible.
- **Gemini cost:** NOT running Gemini this session. GEDCOM linking first, then batch Gemini in Session 98.

## What We Are NOT Doing This Session
- Gemini batch estimation (Session 98, after GEDCOM linking)
- Google Drive API integration (TOOLS-006, future)
- Cross-community identity merging
- Non-admin upload flows
