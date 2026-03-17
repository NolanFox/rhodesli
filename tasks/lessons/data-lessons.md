# Data Safety & Registry Lessons

Lessons about JSON data files, identity registries, photo IDs, and data integrity.
See also: `docs/architecture/DATA_MODEL.md`, `.claude/rules/test-isolation.md`

---

### Lesson 25: Photo ID schemes must be consistent within lookup systems
- **Mistake**: `_build_caches()` used SHA256(filename)[:16] as photo IDs but tried to look up sources from photo_index.json which used inbox_* IDs. 12 of 13 Betty Capeluto photos silently got empty source strings.
- **Rule**: When cross-referencing data between systems with different ID schemes, always include a fallback lookup by a shared key (e.g., filename).
- **Prevention**: Add a test that verifies every photo has a non-empty source after cache building.

### Lesson 29: Maintain ONE authoritative backlog
- **Mistake**: Session-scoped todos in `tasks/todo.md` contained only the current session's work, not the full project backlog. Previous sessions' items were lost.
- **Rule**: `tasks/todo.md` is the SINGLE project backlog. Session-scoped checklists are ephemeral — reconcile them into the backlog after every session.
- **Prevention**: At session end, move completed items to the "Completed" section and ensure all known open items are captured.

### Lesson 36: get_identity() returns a shallow copy — mutate _identities directly
- **Mistake**: `add_note()` and `resolve_proposed_match()` called `get_identity()` which returns `.copy()`. Mutations to the returned dict didn't persist.
- **Rule**: When adding methods to IdentityRegistry that mutate identity data, access `self._identities[id]` directly, not through `get_identity()`.
- **Prevention**: Before adding any mutation method to the registry, check whether `get_identity()` returns a copy.

### Lesson 44: "Skipped" is a deferral, not a resolution
- **Mistake**: Clustering script only included INBOX and PROPOSED faces as candidates. SKIPPED faces (192 — the largest pool of unresolved work) were silently excluded. The script reported "0 candidates" while 192 faces remained unidentified.
- **Rule**: SKIPPED means "I don't recognize this person right now." It is NOT a terminal state. ML pipelines, UI navigation, and stats must all treat skipped faces as active work items.
- **Prevention**: When adding state-based filters, always list what's EXCLUDED (confirmed, dismissed, rejected) rather than what's included. The default should be to include faces, not exclude them.

### Lesson 48: Route handlers must use canonical save functions, not direct .save()
- **Mistake**: `/api/photo/{id}/collection` called `photo_reg.save(photo_index_path)` directly instead of `save_photo_registry(photo_reg)`. Tests patched `save_photo_registry` but the route bypassed it, causing test fixture data to overwrite real `data/photo_index.json` on every test run.
- **Rule**: All data-modifying route handlers MUST use the canonical save functions (`save_registry()`, `save_photo_registry()`, etc.), never call `.save()` directly on registry objects.
- **Prevention**: Grep for `.save(` in route handlers. Any direct `.save(path)` call outside of canonical save functions is a bug.

### Lesson 104: Batch script outputs must write to the SAME data structure the app reads
- **Mistake**: Session 93's batch GEDCOM reanalysis script wrote 69 updated photo location entries to the *root level* of `data/photo_locations.json`. But the app's `_load_photo_locations()` reads only from `data.get("photos", {})`. The Supabase migration also only copied the `"photos"` section. Result: 69 photos showed old/wrong locations in production (e.g., Asheville photo showed Brooklyn). The correct data existed in the file but was invisible to all consumers.
- **Rule**: When a batch/script writes to a structured data file, it MUST write to the EXACT key path that consumers read from. Before writing, grep the codebase for how the file is loaded. If the app does `data.get("photos", {})`, the script must write under `data["photos"]`, not at root level.
- **Prevention**: (1) Batch scripts should load the existing file, modify in-place under the correct key, and save — not append at root level. (2) Add a structural validation test: `photo_locations.json` should have ONLY `version`, `description`, and `photos` at root level. Any other keys indicate orphaned data. (3) After any batch write, verify by loading the file with the SAME function the app uses and checking the affected entries.
- **See also**: Lesson 78 (production-local data divergence), AD-212

### Lesson 105: Supabase sync functions must match actual table schema — test with real upsert, not just mock
- **Mistake**: `sync_photo_locations_batch()` used column names `latitude`, `longitude`, `place` that didn't exist in the actual Supabase `photo_locations` table (real columns: `lat`, `lng`, `location_name`). Also missing `on_conflict="photo_id"` for proper upserts. The function was only tested with mocks that don't validate column names, so the bug was invisible until the first real sync attempt.
- **Rule**: When writing Supabase sync functions, verify column names against the actual table schema. Mock-only tests for database sync are insufficient — they can't catch column name mismatches.
- **Prevention**: (1) Add a comment in each sync function listing the expected table columns. (2) Consider an integration test that does a real upsert to a test table. (3) When creating a new Supabase table, immediately write the sync function AND test it with a real connection before moving on.

### Lesson 116: Sidebar counts and API endpoints must read from the SAME data sources
- **Mistake**: `_compute_sidebar_counts()` reads proposals from BOTH `registry.list_proposed_matches()` AND `proposals.json`. But `/api/proposed-matches` only reads from `registry.list_proposed_matches()`. Result: Fox Family sidebar shows "17 Proposals" but the proposals page content shows "No pending proposals."
- **Rule**: When a count badge and a content API show the same data, they MUST read from identical data sources. Otherwise users see a number they can never access.
- **Prevention**: Extract a shared `_get_all_proposals(community_identity_ids)` function that both sidebar counts and API endpoints call. Never duplicate data source logic in two places.

### Lesson 118: Ingest pipeline must ALWAYS set upload_date
- **Mistake**: CLI ingest (`--directory`/`--file`) had no `--upload-date` argument. Web upload's `_background_ingest()` didn't pass `upload_date` either. Result: 637 photos (636 Fox Family + 1 other) had no `upload_date`, breaking sort-by-upload-date.
- **Rule**: Every photo MUST have `upload_date` set at ingest time. The field is required for sorting, analytics, and data provenance.
- **Prevention**: (1) CLI now has `--upload-date`/`--uploaded-by` args, defaults to current UTC time. (2) `process_single_image()` auto-generates `upload_date` if not provided. (3) Data integrity audit catches missing `upload_date`.

### Lesson 119: Merge must deduplicate faces across anchor AND candidate lists
- **Mistake**: `merge_identities()` checked `if anchor not in target["anchor_ids"]` but not `target["candidate_ids"]`. A face could exist in target's candidates and source's anchors, creating a duplicate face assignment.
- **Rule**: Before adding any face to an identity during merge, check ALL face lists (anchors + candidates + negatives). Face IDs must be globally unique within an identity.
- **Prevention**: Added `target_all_faces` set combining all face lists. Promotes candidate→anchor when source has it as anchor.

### Lesson 120: Data integrity audit must run after every ingest and before every deploy
- **Mistake**: 103 orphan faces, 11 merge chains, 1 duplicate face, 3 CONFIRMED placeholders, 637 missing upload_dates accumulated silently over multiple sessions.
- **Rule**: Run `scripts/data_integrity_audit.py` after every ingest and before every deploy. 0 critical issues required.
- **Prevention**: Audit script exists with `--fix` for safe auto-repairs. Add to CI/CD pipeline and pre-deploy hook.

### Lesson 121: Batch orphan detection must be batch-wide, not per-file
- **Mistake**: `process_single_image()` validates orphans per-file (line 694-716), but `create_inbox_identities()` groups faces across files. Cross-file grouping failures leave faces without identities, not caught by per-file check.
- **Rule**: After processing an entire batch/directory, run a batch-wide orphan face check covering ALL processed faces against ALL created identities.
- **Prevention**: `process_directory()` should do a final batch-wide orphan sweep after all files are processed.

### Lesson 122: Canonical registry records must define face existence, not derivative artifacts
- **Mistake**: Face records still existed in `identities.json` and `photo_index.json`, but the UI trusted embeddings/crops too much when building photo views. When a derivative artifact was missing or drifted, the face appeared to vanish even though the canonical archive record still existed.
- **Rule**: `identities.json` and `photo_index.json` are the canonical record of whether a face exists in the archive. Embeddings, crops, and overlay coordinates are derivative artifacts. Missing artifacts may degrade presentation, but they must never erase the underlying face from the UI or audit trail.
- **Prevention**: (1) Photo caches must preserve registry-backed face records even when embeddings or bbox data are missing. (2) Tests must cover artifact-drift scenarios explicitly. (3) Any UI that cannot render a full overlay must show an explicit archival-record notice rather than silently dropping the face.

### Lesson 123: Additive-only shadow sync is not reconciliation
- **Mistake**: Corrected snapshots were upserted into Supabase, but stale rows were never removed. Production could therefore remain polluted even after the audited local snapshot was clean, because the shadow store accumulated obsolete identities over time.
- **Rule**: A shadow-store reconcile job must compare the full audited snapshot to the target store and identify rows that should no longer exist. Upsert-only sync is suitable for propagation, not for integrity recovery.
- **Prevention**: (1) Add a dry-run reconcile mode that emits a machine-readable stale-row report before applying changes. (2) Require an explicit backup artifact before pruning stale shadow rows. (3) Add a verification step that compares snapshot counts to live store counts after reconcile.

### Lesson 124: Multi-store data repairs need a machine-readable unwind trail before cleanup
- **Mistake**: The system had enough layers that a human-readable summary alone was not sufficient to safely unwind production cleanup later. Without a checked-in backup artifact, stale-row pruning and cross-store repair would be hard to reconstruct or reverse.
- **Rule**: Any production data repair that goes beyond pure append/update semantics must create a machine-readable before/after trail and capture recovery artifacts before cleanup happens.
- **Prevention**: (1) For every production reconciliation, write before/after audit JSON plus any prune backup JSON into `docs/assessments/`. (2) Capture live backup filenames or snapshot identifiers in the assessment. (3) Do not prune anything from production unless the recovery artifact already exists and is linked from the session assessment.

### Lesson 125: Exact archive timestamp ties need a deterministic archival tie-break
- **Mistake**: Several imported photos shared the exact same `upload_date`, so upload-newest sorting fell through to cache IDs and filenames. The UI looked wrong even though the stored timestamps were identical.
- **Rule**: When archive timestamps tie exactly, sort by a stable archival sequence, not by incidental cache identifiers.
- **Prevention**: Carry `photo_index.json` insertion order into the photo cache and use it as the secondary tie-break for upload-date sorts. Also surface full timestamps in the provenance line so tied-order behavior is explainable.

### Lesson 126: Admin empty states must preserve first-run ML entry points
- **Mistake**: The AI Analysis panel disappeared entirely when a photo had no existing `date_labels` entry. That removed the only obvious first-run Gemini action from newly uploaded photos.
- **Rule**: An empty admin state must still preserve the primary action needed to populate that state.
- **Prevention**: Render an explicit empty-state AI Analysis panel for unlabeled admin photo views, including the first-run action and copy explaining what will be generated.

### Lesson 127: File-only audit trails are not enough for archival mutation history
- **Mistake**: `log_user_action()` wrote only to local `logs/user_actions.log`, so a meaningful slice of mutation history lived outside the structured Supabase audit trail. That is survivable for debugging but not acceptable for archival provenance after a multi-session data integrity incident.
- **Rule**: Any audit-relevant mutation trail that the team may need for recovery, attribution, or incident review must be durably recorded in the structured store, not just appended to a local file.
- **Prevention**: Dual-write user action logs to Supabase `audit_log`, and treat the local file as a convenience mirror rather than the only durable copy.

### Lesson 128: `user_source` is provenance class, not actor identity
- **Mistake**: Identity registry events recorded `user_source` values like `approved_name_suggestion` or `web_review`, but not the actual actor email/user ID. Reconstructing "who changed this person?" then required correlating multiple logs after the fact.
- **Rule**: Capture actor identity at mutation time on the canonical event, not as an inference assembled later from neighboring systems.
- **Prevention**: Add explicit actor fields to canonical registry/photo mutation records and expose them through entity history timelines. Use `user_source` only for workflow/provenance class.

### Lesson 129: Mirrored list builders must share the same metadata contract
- **Mistake**: The workstation and public photo lists assembled their card payloads independently. The upload-order tie-break fix had landed in one path, but the public `/photos` path still omitted `photo_index_order` and `uploaded_by`, so sorting and provenance drifted back apart.
- **Rule**: When two surfaces render the same archival objects, they must carry the same canonical metadata fields unless the omission is deliberate and tested.
- **Prevention**: Centralize or explicitly mirror the photo-card metadata contract (`upload_date`, `uploaded_by`, `photo_index_order`, provenance text inputs) across all list builders, and add regression tests that compare workstation and public rendering behavior.

### Lesson 130: Request-path GEDCOM search must never full-scan a versioned rich mirror
- **Mistake**: Session 98 upgraded `_load_gedcom_individuals()` to page through the full rich GEDCOM mirror (`21,944` current people) and the admin GEDCOM link panel auto-fired search on person-page load. The first admin lookup therefore tried to pull the entire rich mirror across ~22 Supabase pages and made the linker feel broken.
- **Rule**: Request-path search/link flows must prefilter candidates in the database and use exact-record lookups for selected rows. Full mirrored datasets are for offline analysis, background hydration, or explicitly cached browse surfaces, not on-demand admin search requests.
- **Prevention**: (1) For GEDCOM search, fetch thin candidate rows from Supabase, then fuzzy-score in Python. (2) For link rendering and POST routes, fetch exactly one GEDCOM row by `gedcom_id`. (3) Add regression tests that fail if a link route falls back to the bulk mirror loader.

### Lesson 131: Never claim fixed without production browser verification
- **Mistake**: Claimed data fixes were applied without verifying production was actually serving the corrected data.
- **Rule**: Never claim fixed without production browser verification — always curl/screenshot the live page.
- **Prevention**: After any data fix, verify the production page shows the corrected data before declaring done.

### Lesson 132: Confirmed identity workflow needs visual verification gate
- **Mistake**: Confirmed identity workflow allowed confirming a face that didn't exist in embeddings.
- **Rule**: Confirmed identity workflow needs visual verification gate — admin must see the face before confirming.
- **Prevention**: Add a data integrity CI check: every CONFIRMED identity's anchor_ids must exist in embeddings AND photo_index.

### Lesson 141: Never git-add production-origin data files — 6th occurrence of the deploy-overwrite pattern
- **Mistake (Session 104):** Attempted to `git add data/comparison_results.json` to create a shareable comparison result. This file is created by users on production when they run comparisons. Adding it to git would have overwritten all existing comparison results on the next deploy — the exact same pattern as Lessons 56, 69, 78, and 85.
- **The chain:** Lesson 56 (admin merge overwritten) → Lesson 69 (annotations wiped) → Lesson 78 (birth years lost, 4th time) → Lesson 85 (confirmations lost, 5th time, triple protection added) → NOW (comparison_results, caught by .gitignore)
- **Rule:** Before `git add`-ing ANY file in `data/`, ask: "Who writes this file on production?" If users or the app create/modify it at runtime → it's production-origin → NEVER add to git. If .gitignore blocks the add, that's the safety system WORKING — don't use `-f`.
- **Prevention:** (1) Trust .gitignore. (2) Production-origin files need API/UI creation, not git push. (3) The `data/*` allowlist in .gitignore is the canonical list of git-safe data files.
- **See also:** Lessons 56, 69, 78, 85, 133; AD-134 (safety gate), AD-135 (structural fix)

### Lesson 144: DATA_SOURCE split-brain — ingest writes JSON, production reads Supabase, photos vanish
- **Mistake (Session 104b):** Robert Mattatia photos ingested locally → written to photo_index.json → pushed to production via sync API → photo_index.json updated on disk. But production has `DATA_SOURCE=postgres`, so `load_photo_registry()` reads from Supabase `photos` table. Photos weren't in Supabase → invisible in workstation grid, no metadata, no source, no community assignment. Required 4 separate debugging rounds across the session.
- **The chain:** (1) Ingest pipeline only writes JSON. (2) Shadow-write to Supabase is fire-and-forget, failures invisible. (3) `/api/sync/push` writes JSON only, not Supabase. (4) `_invalidate_all_caches()` missed `_photo_registry_cache`. (5) Community assignment is manual. Each gap individually wouldn't have been fatal; together they created a complete data blackout.
- **Rule:** When `DATA_SOURCE=postgres`, EVERY write path must reach Supabase or the data doesn't exist on production. "Written to JSON" is NOT "shipped" when the app reads from Postgres.
- **Prevention:** Session 105 — sync push writes to Supabase, shadow-writes become synchronous when strict=True, auto-community-assignment on ingest, startup parity check.
- **See also:** Lesson 136 (fire-and-forget data loss), Lesson 142 (JSONB type coercion), AD-135 (data in Supabase)

### Lesson 142: Supabase JSONB columns can silently store string-encoded arrays — always guard reads AND writes
- **Mistake (Session 104b):** 20 Robert Mattatia identity rows had `anchor_ids` stored as the string `'["inbox_e8b9205ffaa7"]'` instead of the JSONB array `["inbox_e8b9205ffaa7"]`. When `load_from_postgres()` read these, Python got a `str`, and iterating it yielded individual characters (`[`, `"`, `i`, `n`, ...) instead of face IDs. `get_identity_for_face()` returned None → all faces showed "Unidentified" on production.
- **Root cause:** The Supabase Python client can accept both lists and strings for JSONB columns. If the caller passes a string (e.g., from JSON that was double-serialized), Supabase stores it as-is. The `shadow_write_identities_batch` path didn't validate types before write.
- **Compounding factor:** Production uses `DATA_SOURCE=postgres` but local dev uses `DATA_SOURCE=json`. The bug was invisible locally because JSON files always have proper lists.
- **Rule:** (1) Always coerce JSONB fields on READ with `_ensure_list()` — never trust the column type. (2) Always coerce on WRITE with `_ensure_list_for_supabase()` — prevent corruption at source. (3) When a feature works locally but fails on production, check if `DATA_SOURCE` differs.
- **Prevention:** `_ensure_list()` in `core/registry.py:load_from_postgres()` and `_ensure_list_for_supabase()` in `app/supabase_data.py`. 3 regression tests.
- **See also:** Lesson 105 (mock tests don't catch column mismatches), Lesson 133 (DATA_SOURCE fallback masks failures)

### Lesson 145: photo_faces table must be written alongside photos table — READ path queries it, WRITE path must populate it
- **Mistake (Session 105b):** `load_from_postgres()` reads `photo_faces` table to build the face-to-photo mapping. But NO write path ever populated `photo_faces` after the one-time migration script. `save_photo_registry()`, `_background_ingest()`, and `/api/sync/push` all wrote to the `photos` table but not `photo_faces`. New uploads had faces in JSON but not in the Supabase face mapping — causing incomplete face data on production when `DATA_SOURCE=postgres`.
- **Rule:** When adding a Supabase read path, immediately verify the corresponding write path exists. If a table is queried by `load_from_*()`, every function that calls `save_*()` must also write to that table.
- **Prevention:** `shadow_write_photo_faces_batch()` now called in all write paths. Structural test verifies photo_faces is written whenever photos are written.

### Lesson 146: Upload pipeline creates orphaned faces — post-sync identity verification missing
- **Mistake**: `_background_ingest()` in `app/upload_routes.py` calls `process_directory()` which writes faces to JSON and photo_faces to Supabase. But if the Supabase sync at lines 1034-1065 fails (or writes incorrect identity data), the app (reading from Supabase via DATA_SOURCE=postgres) doesn't see the new identities. 9 James Fields faces existed in photo_faces but had zero corresponding identities in Supabase.
- **Rule**: Upload pipeline must verify identity creation in Supabase after sync. If identity count mismatches face count, log error and retry sync. The `/api/sync/resync-supabase` endpoint has orphan repair logic — but it's a manual endpoint, not wired into the pipeline.
- **Prevention**: Add post-sync validation in `_background_ingest()`: after Supabase sync, query photo_faces and identities tables to verify counts match. If mismatch, call the orphan repair logic directly. Add a data health endpoint for ad-hoc diagnostics.

### Lesson 147: Local-production data divergence — 7th occurrence
- **Mistake**: James Fields photos uploaded to production but local data has zero entries. Clustering impossible locally. No automated sync-back mechanism for embeddings. This is the 7th occurrence of local-production data divergence (Lessons 56→69→78→85→141→142→147).
- **Rule**: After any production upload, local must be synced before running ML pipelines locally. Alternatively, ML pipelines should run on production data directly.
- **Prevention**: Add `/api/sync/embeddings` endpoint that streams embeddings.npy. Update `sync_from_production.py` to optionally download embeddings with `--include-embeddings`.

### Lesson 55: Crop filename formats differ between legacy and inbox — don't assume quality is encoded
- **Mistake**: `face_card()` parsed quality from crop filenames using pattern `_{quality}_{index}.jpg`. Inbox crops use format `inbox_{hash}.jpg` with no quality encoded. Result: "Quality: 0.00" for all inbox faces.
- **Rule**: When a computed value (quality, score, etc.) is stored in different places for different face formats, the lookup must have a fallback chain: filename parse -> embeddings cache -> default.
- **Prevention**: `get_face_quality()` helper provides the fallback. `face_card()` now falls back to embeddings when filename parse returns 0.

### Lesson 149: NEVER click action buttons on production — browser automation is READ-ONLY
- **Mistake**: While debugging a focus mode redirect issue via Chrome browser plugin, Claude clicked the Merge button on production to observe the HTMX response. This merged two real identities (Person 5efac7a7 into Hanula Franco Cohen, Person 3410 into Esther Burd Fox). User caught the corruption and data had to be manually repaired via Supabase queries.
- **Rule**: Browser automation on production is strictly READ-ONLY. Screenshots, DOM reads, network monitoring — all fine. NEVER click buttons that modify data (Merge, Confirm, Reject, Skip, Save, Upload, Override, Tag, Delete). Unless the user EXPLICITLY instructs you to click a specific button, always ask first.
- **Prevention**: Rule file at `.claude/rules/browser-read-only.md`. Memory entry saved. If you need to test an interaction: read the button's hx-post URL from the DOM (sufficient for debugging), ask the user to click while you watch, or write a unit test.
