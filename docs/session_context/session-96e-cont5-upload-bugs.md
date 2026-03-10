# Session 96e-cont5: Upload Pipeline Bug Investigation

## Context
User uploaded 2 photos (fb_rhodes_holocaust_isaac_menashe) to "Rhodes Holocaust Remembrance Group" collection via production upload page. Face detection succeeded ("2 faces extracted from 2 images"). But multiple post-upload features are broken.

## Production Logs (job 98ead818)
```
[upload] R2 upload complete: 4 files for job 98ead818
[upload] Tagged 2 photos to community 72d8e4f0-...  (FIXED - was 0 before)
[upload] Auto-cluster complete for job 98ead818: 13 matches found (FIXED - was crashing before)
[upload] Grouping: 85 merges in 60 clusters for job 98ead818
[upload] Tagged 0 identities to community 72d8e4f0-...
[upload] Supabase sync error for job 98ead818: 'list' object has no attribute 'get'
[upload] Caches invalidated for job 98ead818
```

## All Issues Found (from screenshots + logs)

### BUG-1: Supabase sync crash — `'list' object has no attribute 'get'`
- **Severity**: CRITICAL — prevents all new data from reaching Postgres
- **Location**: `app/upload_routes.py:984-989` — the code does:
  ```python
  id_items = [dict(v, identity_id=k) for k, v in json_registry._identities.items()]
  ```
  After apply_suggestions() rewrote identities.json, some identity values may be lists (e.g., anchor_ids values) rather than dicts. OR the `_identities` dict has a non-dict value.
- **Root cause investigation needed**: Load the production identities.json and check for malformed entries. The apply_suggestions() call writes JSON directly (`_json_cluster.dump(updated_data, _idf)`) and the returned data from apply_suggestions() wraps identities in `{"identities": {...}, "schema_version": 1}`, so `IdentityRegistry.load()` should parse it correctly. BUT maybe `updated_data` has a different structure than expected.
- **Fix**: Check what `apply_suggestions()` returns. It does `data = copy.deepcopy(identities_data)` where `identities_data` is from `load_identities(data_path)`. Need to check what `load_identities` returns vs what IdentityRegistry expects.

### BUG-2: Photo dimensions missing — "Dimensions unavailable"
- **Severity**: HIGH — prevents face overlay boxes on new photos
- **Screenshot evidence**: Photo Context modal shows "Dimensions unavailable" and "(Face overlays require cached dimensions)"
- **Location**: `app/page_routes.py:3030` — `get_photo_dimensions(photo["filename"])` returns (0, 0)
- **Root cause**: `process_directory()` DOES set dimensions via `photo_registry.set_dimensions(photo_id, image_width, image_height)` in `_process_single_file` (line 641). But on production with DATA_SOURCE=postgres, the photo is loaded from Supabase which may not have width/height.
- **The Supabase sync crash (BUG-1) means dimensions never reached Postgres** — photos table has width/height columns, but the sync errored out before writing.
- **Fix**: Fix BUG-1 first. Also verify shadow_write_photos_batch includes width/height.

### BUG-3: uploaded_by not passed to process_directory()
- **Severity**: MEDIUM — user asked "is it logging who uploaded this?"
- **Location**: `app/upload_routes.py` — the `_background_ingest()` function calls `process_directory()` at line 814. Checking the call signature:
  ```python
  result = process_directory(
      directory=job_dir,
      job_id=job_id,
      data_dir=data_path,
      source=source,
      collection=collection,
      prefer_hybrid=True,
  )
  ```
  **Missing: `uploaded_by=uploader_email` and `upload_date=...`**
- `process_directory()` accepts these params (line 1039-1040) but they're not passed.
- **Fix**: Add `uploaded_by=uploader_email, upload_date=datetime.now(timezone.utc).isoformat()` to the process_directory() call.

### BUG-4: Upload date sort — newly uploaded photos NOT at top
- **Severity**: HIGH — defeats the purpose of upload sorting
- **Screenshot evidence**: Sort "Estimated Date (Newest)" shows 1980s photos at top. Bottom of page shows recent uploads (congo, halfon, holocaust).
- **Root cause**: The user's screenshot shows sort="Estimated Date (Newest)" not "Upload Date (Newest)". But even with "Upload Date (Newest)", the upload_date may be NULL because BUG-3 means upload_date isn't passed to process_directory().
- **Also**: The `_sort_photos` function (page_routes.py:5411-5417) puts photos WITHOUT upload_date at the end when sorting newest-first (NO_DATE = ""). So photos with missing upload_date sink to bottom.
- **Fix**: Fix BUG-3 to pass upload_date. Also consider: should the default sort be "Upload Date (Newest)" after an upload?

### BUG-5: Duplicate "Source: Facebook" in Photo Context
- **Severity**: LOW — cosmetic
- **Screenshot evidence**: Photo Context modal shows "Source: Facebook" on two separate lines
- **Location**: `app/page_routes.py` in the photo context modal rendering
- **Fix**: Find the duplicate source display and remove one.

### BUG-6: Face descriptions not available — "No face descriptions available yet"
- **Severity**: LOW — face alignment/description is a separate feature (requires Gemini API call)
- **Screenshot evidence**: Photo Context shows "No face descriptions available yet" with "Detect Faces" button
- **Root cause**: Face descriptions require explicit admin action (Detect Faces button) or the enrichment pipeline. The upload pipeline only does face DETECTION (bounding boxes), not face DESCRIPTION (Gemini analysis). This is by design.
- **Not a bug** — working as designed. But could be confusing UX.

### BUG-7: Discoveries shows 0 despite auto-cluster finding matches
- **Severity**: MEDIUM — Discoveries page appears non-functional
- **Screenshot evidence**: "0 high-confidence matches to confirmed identities" / "All discoveries reviewed!"
- **Root cause**: Discoveries shows matches where an INBOX/PROPOSED face matches a CONFIRMED identity. Auto-cluster found 13 matches, but those are face-to-face matches, not necessarily to confirmed identities. If none of the 13 matches involved confirmed identities, discoveries would correctly show 0.
- **BUT**: The Discoveries page has been showing 0 for multiple sessions. Need to check if the proposals.json or the discoveries query is filtering too aggressively.
- **Investigation needed**: Check proposals.json on production, check discoveries route filtering logic, check if proposals are being regenerated correctly.

### BUG-8: Identity community tagging still shows 0
- **Severity**: MEDIUM — new identities not tagged to community
- **Log evidence**: "Tagged 0 identities to community"
- **Location**: `app/upload_routes.py:955-964` — uses `get_identity_for_face(registry, fid)`
- **Root cause**: The registry loaded at line 955 is `_main_mod.load_registry()` which loads from Postgres (DATA_SOURCE=postgres). But the new identities only exist in JSON at this point. The Supabase sync hasn't run yet (it runs AFTER this block, and it crashes anyway).
- **Fix**: Load from JSON file instead: `IdentityRegistry.load(data_path / "identities.json")`

### BUG-9: Sidebar photo count fluctuates (276 vs 278)
- **Severity**: LOW — likely cache timing
- **Screenshot evidence**: Upload page shows "Photos 276", other pages show "Photos 278"
- **Root cause**: Cache invalidation timing. The upload page was loaded during ingest processing, before caches were invalidated. After cache invalidation, it shows 278.
- **Not a critical fix needed** — the cache invalidation at end of _background_ingest handles this.

## Fix Plan (Priority Order)

### Phase 1: Critical data flow fixes
1. **BUG-1 fix**: Debug the `'list' object has no attribute 'get'` error. Check what `load_identities()` from `cluster_new_faces.py` returns vs what IdentityRegistry._identities contains. The issue is likely that `json_registry._identities` contains the raw dict from the JSON file including metadata keys like "schema_version" which aren't identity dicts.
2. **BUG-3 fix**: Pass `uploaded_by=uploader_email` and `upload_date=datetime.now(timezone.utc).isoformat()` to `process_directory()` call in `_background_ingest()`.
3. **BUG-8 fix**: Load identities from JSON file (not Postgres) when doing identity community tagging after ingest.

### Phase 2: Consequential fixes (fixed by Phase 1)
4. **BUG-2**: Fixed by BUG-1 — once Supabase sync works, dimensions reach Postgres.
5. **BUG-4**: Fixed by BUG-3 — once upload_date is passed, sorting works.

### Phase 3: Independent fixes
6. **BUG-5 fix**: Remove duplicate source line in photo context modal.
7. **BUG-7**: Investigate discoveries pipeline — check proposals.json on production, check filtering.

## Key Files to Modify
- `app/upload_routes.py` — BUG-1, BUG-3, BUG-8
- `core/ingest_inbox.py` — already fixed (photo_ids return)
- `app/page_routes.py` — BUG-5 (duplicate source)
- `scripts/cluster_new_faces.py` — check load_identities() return format

## Breadcrumbs
- Production deploy: `01fffdf3` (SUCCESS, has photo_ids fix + apply_suggestions fix)
- Job 98ead818: Latest upload test showing all issues
- Previous jobs: f9a6a6fb (Raymond Halfon), 0170024f (Claude Benatar 3 photos)
- Lesson 116: "Sidebar counts and API endpoints must read from the SAME data sources"
