# Deployment & Infrastructure Lessons

Lessons about Docker, Railway, data sync, production pipelines, and deployment safety.
See also: `docs/DEPLOYMENT_GUIDE.md`, `docs/ops/OPS_DECISIONS.md`

---

### Lesson 31: Infrastructure decisions are as important as algorithmic ones
- **Mistake**: The "0 Photos" bug from `.dockerignore` cost more debugging time than any ML issue. Ops decisions weren't documented.
- **Rule**: Capture ops decisions (OD-XXX format in `docs/ops/OPS_DECISIONS.md`) with the same rigor as ML decisions (AD-XXX format).
- **Prevention**: Before modifying Dockerfile, railway.toml, or deployment scripts, read `docs/ops/OPS_DECISIONS.md`.

### Lesson 32: .gitignore and .dockerignore serve different purposes
- **Mistake**: Assumed all ignore files behave the same way.
- **Rule**: `data/` files belong in `.gitignore` (keep repo light) but NOT in `.dockerignore` (allow CLI deployment to include them).
- **Prevention**: Rule is now enforced by `.claude/rules/deployment.md` path-scoped rule.

### Lesson 42: Token-based API auth is simpler than session cookie sync for machine-to-machine
- **Mistake**: Previous sync approach required exporting browser session cookies as cookies.txt. This never worked because it required manual browser interaction and cookies expire.
- **Rule**: For machine-to-machine data sync, use a simple Bearer token (RHODESLI_SYNC_TOKEN). Set it once on both sides, never expires.
- **Prevention**: When building script-to-server communication, always prefer API tokens over session cookies.

### Lesson 43: Production and local JSON files are completely separate
- **Observation**: Railway has its own copy of identities.json on the persistent volume. Local dev has a separate copy. Admin tagging on the live site does NOT update local data.
- **Rule**: Every ML session MUST start with `python scripts/sync_from_production.py` to get fresh data.
- **Prevention**: `scripts/full_ml_refresh.sh` runs sync as step 1. Never skip it.

### Lesson 47: Documentation drift is invisible until it's severe
- **Mistake**: `docs/BACKLOG.md` fell 6 versions behind (v0.10.0 -> v0.14.1, 663 -> 900 tests) because CLAUDE.md only instructed updating ROADMAP.md. The reference "see `docs/BACKLOG.md`" read as "go look at it", not "keep it current."
- **Rule**: When maintaining parallel tracking documents, the update rule must explicitly name EVERY file. "Update ROADMAP.md" does NOT imply "also update BACKLOG.md."
- **Prevention**: CLAUDE.md now has explicit triple-update rule (ROADMAP + BACKLOG + CHANGELOG). `scripts/verify_docs_sync.py` and `tests/test_docs_sync.py` catch drift automatically.

### Lesson 49: A push-to-production API is essential for the ML pipeline
- **Mistake**: `process_uploads.sh` attempted `git add data/` but data/ is gitignored. There was no way to push locally-processed data back to Railway.
- **Rule**: Any two-stage pipeline (local processing -> remote deployment) needs a push mechanism. Don't rely on git for pushing gitignored data.
- **Prevention**: `POST /api/sync/push` + `scripts/push_to_production.py` now handle this. Token-authenticated, creates backups.

### Lesson 50: Downloaded files should match the existing directory convention
- **Mistake**: `download_staged.py` puts files in `raw_photos/pending/` but the photo_index path recorded `raw_photos/pending/filename.jpg`. All 124 existing photos are at `raw_photos/filename.jpg` (no subdirectory).
- **Rule**: After downloading, move files to match the canonical location before registering them.
- **Prevention**: The `process_uploads.sh` script should move files from pending/ to raw_photos/ root after download.

### Lesson 53: Verify production bugs by fetching rendered HTML, not checking local data
- **Mistake**: Multiple previous sessions claimed to fix production issues by checking local JSON files and API responses. But the live site still showed 5 bugs because the data never actually reached the production rendering pipeline.
- **Rule**: For EVERY production fix, verification means `curl -s https://rhodesli.nolanandrewfox.com/[page] | grep [expected content]`. Checking local data files is necessary but NOT sufficient.
- **Prevention**: Every deployment fix must end with HTML-based verification.

### Lesson 54: ALL essential data files must be in BOTH git tracking AND REQUIRED_DATA_FILES
- **Mistake**: `embeddings.npy` was gitignored (so not in Docker builds) AND not in `REQUIRED_DATA_FILES` (so not synced to volume). The init script had nothing to sync FROM.
- **Rule**: For a data file to reach production: (1) it must be tracked in git (or the Docker image won't have it), (2) it must be in `REQUIRED_DATA_FILES` (or `_sync_essential_files` won't update the volume copy), (3) the init script must handle binary files correctly.
- **Prevention**: Added `embeddings.npy` to `.gitignore` whitelist and `REQUIRED_DATA_FILES`. Any new data file for production needs BOTH.

### Lesson 56: Blind push-to-production overwrites admin actions
- **Mistake**: `push_to_production.py` did `git add data/ && git commit && git push` without checking production state. Admin merged "Zeb Capuano" on production, but local data still had the unmerged identities. Next push overwrote the merge.
- **Rule**: NEVER push data to production without first fetching and merging with the current production state. Production wins on conflicts (state changes, name changes, face set changes, merges, rejections).
- **Prevention**: `push_to_production.py` now has `perform_merge()` that fetches via sync API, detects user-modified identities via `_is_production_modified()`, and preserves them. Use `--no-merge` only for known-clean states.

### Lesson 59: Optional data files need explicit sync, not just bundling
- **Mistake**: `proposals.json` was tracked in git, bundled in Docker, but never synced to the Railway volume because `_sync_essential_files()` only processed `REQUIRED_DATA_FILES`. The "add missing files" fallback only copies files that DON'T exist — proposals.json already existed (empty) on the volume.
- **Rule**: Any data file that (a) changes over time and (b) needs to reach production must be in either `REQUIRED_DATA_FILES` or `OPTIONAL_SYNC_FILES` in `init_railway_volume.py`. Being in the Docker bundle alone is NOT sufficient if the file already exists on the volume.
- **Prevention**: When adding a new data file, ask: "Will this file change after initial deployment?" If yes, add it to the sync list. Added `OPTIONAL_SYNC_FILES` for non-critical files like proposals.json.

### Lesson 60: Empty proposals means clustering wasn't re-run, not a UI bug
- **Mistake**: Assumed the UI was broken because proposals weren't showing. The actual issue was proposals.json had 0 proposals because `cluster_new_faces.py` hadn't been re-run after data changes.
- **Rule**: When "feature X doesn't work on production", check the DATA first (is it populated?), then check the DEPLOYMENT PIPELINE (does it reach the server?), then check the UI code (does it read the data?).
- **Prevention**: After any data change (sync, merge, ingest), re-run clustering to regenerate proposals.

### Lesson 65: push_to_production.py must be run AFTER ingest completes, not before
- **Mistake**: `push_to_production.py` committed `data/embeddings.npy` before ingest_inbox finished writing the new face to it. The committed version had 657 entries (156 photos), but the working copy had 658 entries (157 photos). Production never got the new embedding.
- **Rule**: The full upload pipeline sequence must be: (1) download -> (2) ingest -> (3) upload to R2 -> (4) push to production. Step 4 must come LAST and include ALL modified data files. Verify with `git diff --stat` before pushing.
- **Prevention**: After `push_to_production.py`, always run `git status` to check for unstaged changes to data files. If any exist, the push was incomplete.

### Lesson 66: identities.json "history" key is REQUIRED — ingest_inbox doesn't write it
- **Mistake**: `core/ingest_inbox.py` writes identities.json with only `schema_version` and `identities` keys, omitting `history`. `IdentityRegistry.load()` requires `history` and throws `ValueError` when it's missing. `load_registry()` catches the error and returns an empty registry -> 0 identities on production.
- **Rule**: Any code that writes identities.json MUST include the `history` key (even if empty: `[]`). Use `IdentityRegistry.save()` for all writes, never `json.dump()` directly.
- **Prevention**: The ingest pipeline should load via `IdentityRegistry.load()`, modify, then save via `registry.save()` to preserve the full schema.

### Lesson 67: sync push must invalidate ALL in-memory caches, not just some
- **Mistake**: `/api/sync/push` invalidated `_photo_registry_cache` and `_face_data_cache` but missed `_photo_cache` and `_face_to_photo_cache`. After pushing new photo data, the photos page showed stale data.
- **Rule**: When adding a new in-memory cache, add it to the sync push invalidation list. Grep for `= None` patterns in the push handler.
- **Prevention**: Added `_photo_cache = None` and `_face_to_photo_cache = None` to the sync push cache invalidation block.

### Lesson 68: Multiple community uploads may come in separate batches
- **Mistake**: Assumed the contributor uploaded 2 photos in 1 batch. They actually uploaded in 2 separate batches (2 separate upload form submissions). `download_staged.py` was run once and cleared only the first batch. The second batch sat in staging for days.
- **Rule**: After processing community uploads, always run `download_staged.py --dry-run` one more time to check for additional batches. Contributors may upload photos incrementally.
- **Prevention**: Add a final verification step to the upload pipeline: "Verify staging is empty."

### Lesson 69: Production-origin data must NEVER be in deploy sync lists
- **Mistake**: `annotations.json` was in both `OPTIONAL_SYNC_FILES` (init_railway_volume.py) and `DATA_FILES` (push_to_production.py). Users submit annotations on the live site, but the deploy pipeline would overwrite the production copy with the local empty one. The user's annotation appeared to vanish.
- **Rule**: Data files written by users on production (annotations.json) must NOT be in OPTIONAL_SYNC_FILES or push DATA_FILES. They need their own pull mechanism (sync API endpoint) to flow production->local. The deploy must never touch them.
- **Prevention**: Before adding a data file to any sync list, ask: "Who writes this file?" If production users -> do NOT sync from bundle. If local ML pipeline -> sync from bundle. Added deploy safety tests that assert annotations.json is NOT in sync lists. Added `/api/sync/annotations` pull endpoint.
- **See also**: Lessons 78, 85; AD-134 (band-aid), AD-135 (structural fix); DATA-001 in docs/ISSUES_LOG.md

### Lesson 70: Dockerfile must COPY every package the web app imports at runtime
- **Mistake**: `rhodesli_ml/` was never added to the Dockerfile when its graph/importer modules were first imported by app/main.py (sessions 35-38). The Dockerfile only had `COPY app/`, `COPY core/`, `COPY scripts/`. Routes /connect, /tree, and /admin/gedcom all 500'd in production with `ModuleNotFoundError` — but worked locally because `rhodesli_ml/` existed on disk.
- **Rule**: When adding a NEW `from X import ...` to `app/main.py` where X is a package not already in the Dockerfile, you MUST update the Dockerfile in the SAME commit. "Works locally" is not "works in production."
- **Prevention**: Added 5 deploy safety tests (`TestDockerfileModuleCoverage`) that verify the Dockerfile has COPY directives for every rhodesli_ml subpackage the web app imports. Selectively copy only pure-Python runtime modules (graph/ + importers/ = 200KB), not the full ML package (3.2GB with .venv + checkpoints).

### Lesson 78: Production-local data divergence is the #1 recurring deployment failure
- **Mistake**: Session 49B reviewed 31 birth years via the admin UI on production. Those writes went to production's identities.json (on Railway volume). Subsequent deploys pushed local identities.json (which didn't have the birth years) to the Docker bundle, and init_railway_volume.py overwrote the production file by content hash. Birth years lost. This is at least the 4th occurrence of this pattern (Lessons 43, 56, 69 are all variants).
- **Rule**: The current architecture has a fundamental flaw: identities.json is BOTH written by admin actions on production AND deployed from the git bundle. There is no merge — whichever writes last wins. Every deploy risks overwriting admin work. BEFORE ANY PUSH TO PRODUCTION: always `sync_from_production.py` first to get the latest admin changes, merge locally, then push. This is a manual workaround for a broken architecture.
- **Prevention**: Short-term: add a pre-push hook or CI step that warns if local identities.json hasn't been synced recently. Medium-term: split identities.json into immutable seed data (deployed) and mutable admin data (production-only). Long-term: Postgres migration makes this a non-issue. Flag this as P0 infrastructure debt.
- **See also**: Lessons 69, 85; AD-134 (band-aid), AD-135 (structural fix); DATA-001 in docs/ISSUES_LOG.md

### Lesson 85: Deploy data safety gate — 5th occurrence of production data loss from volume overwrite
- **Mistake**: Session 49B entered 9 identity confirmations + names + birth years + 2 merges through the production web UI. Subsequent sessions (55-59) pushed code to main, triggering Railway redeploys. Each redeploy ran `init_railway_volume.py._sync_essential_files()` which compared bundle (46 confirmed) to volume (55 confirmed), found they differed, and OVERWROTE the volume with bundle data. All 49B user work was lost. Recovered from a `.bak.TIMESTAMP` file on the volume — lucky that the init script creates backups before overwriting. This is the 5th occurrence of this pattern (Sessions 12, 16, annotations incident, Lesson 78, now this).
- **Rule**: The init script MUST NEVER overwrite identities.json or photo_index.json if the volume copy has MORE confirmed identities / photos than the bundle. "Bundle is source of truth" is wrong for user-modified files. Triple protection required: (A) count-based safety gate refuses overwrite when volume > bundle, (B) auto-backup of all volume data before any sync, (C) per-file .bak timestamps. After ANY interactive session, IMMEDIATELY run `sync_from_production.py` to get user changes into git.
- **Prevention**: AD-134 implemented in `init_railway_volume.py`: `_is_volume_user_modified()` checks confirmed counts before allowing overwrite. `_auto_backup_volume()` saves all critical files to auto_backups/ before sync. 21 tests in `test_deploy_safety_gate.py` including exact Session 49B regression test. The safety gate would have caught ALL 5 previous occurrences.
- **See also**: Lessons 69, 78; AD-134 (band-aid), AD-135 (structural fix); DATA-001 in docs/ISSUES_LOG.md

### Lesson 94: Wait for deploy completion before browser verification — deploy transitions cause 502s and corrupted JS state
- **Mistake**: Session 81B pushed a tree fix to production and immediately navigated to the tree page in Chrome. Railway was mid-deploy (INITIALIZING → BUILDING → SUCCESS takes ~60s). The old container returned a 502 Bad Gateway. The page's JS `DOMContentLoaded` handler fired during the 502 failure, creating an empty SVG with stale closure variables. Subsequent attempts to reload or re-navigate from within the same tab retained the corrupted state. Debugging time was wasted investigating "why the tree is empty" when the real issue was deploy timing.
- **Rule**: After `git push`, ALWAYS check Railway deploy status (`mcp__railway-mcp-server__list-deployments` or Railway CLI) and wait for SUCCESS before any Chrome verification. A 502 during deploy transition corrupts in-page JS state in ways that persist across soft reloads.
- **Prevention**: (1) After push, poll deploy status until SUCCESS. (2) After deploy completes, open a NEW tab or do a hard navigation (not reload) to avoid stale JS closures. (3) If you hit a 502, assume ALL in-page JS state is corrupted — close the tab and start fresh. Session 81B.

### Lesson 117: Railway region deprecation silently breaks GitHub-triggered deploys — use CLI deploy as workaround
- **Mistake**: Railway deprecated `us-west1` region. A banner appeared: "The deployment configuration was automatically modified to ignore deprecated regions." After this, ALL GitHub-triggered deploys (via `git push`) started using `RAILPACK` builder instead of `DOCKERFILE`, ignoring `railway.toml` entirely. Deploys stuck in QUEUED/INITIALIZING indefinitely. The site stayed on the last successful deploy but no new code could ship. Three consecutive GitHub pushes all failed the same way.
- **Rule**: When Railway deprecates a region or modifies deployment config, GitHub-triggered deploys may silently lose their `railway.toml` settings. Symptoms: (1) deploy stuck in QUEUED, (2) deploy metadata shows `builder: "RAILPACK"` instead of `"DOCKERFILE"`, (3) no `configFile` field in deploy metadata, (4) no `healthcheckPath`. If GitHub deploys are stuck, use `railway deploy` CLI as immediate workaround — it reads `railway.toml` locally and works correctly.
- **Prevention**:
  1. **Deploy method**: Use `railway deploy` from project root instead of relying on GitHub auto-deploy. The CLI reads `railway.toml` locally and always works correctly.
  2. **Dashboard settings do NOT persist**: Setting Builder to Dockerfile in Settings → Build reverts to Railpack on every deploy. Config-as-code path also ineffective. This is a Railway platform bug (2026-03-10).
  3. **Region**: Keep region updated (us-west2 as of 2026-03-10) to avoid deprecation issues.
  4. **Diagnosis**: Check deploy metadata via `mcp__railway-mcp-server__list-deployments` with `json: true` — if `builder` is `"RAILPACK"` instead of `"DOCKERFILE"`, the deploy will fail. Cancel it and use CLI.
  5. **Stuck QUEUED deploys**: Remove via three-dot menu in Railway dashboard. They will never build.
- **See also**: OD-010 in docs/ops/OPS_DECISIONS.md

### Lesson 133: Supabase/Postgres DATA_SOURCE fallback masks real connection failures
- **Mistake**: DATA_SOURCE=postgres was set but health endpoint showed "Supabase connection skipped" — unclear if actually using Postgres.
- **Rule**: Supabase/Postgres DATA_SOURCE fallback masks real connection failures — health endpoint must clearly show which data source is active.
- **Prevention**: Health endpoint should report DATA_SOURCE value and whether Postgres load succeeded or fell back to JSON.

### Lesson 139: Supabase free-tier egress is dominated by TTL cache reloads, not user traffic
- **Mistake**: Set registry TTL to 30s without considering egress cost. A 380KB table reloaded every
  30s = 31 GB/month under constant traffic — 6x the free tier limit.
- **Rule**: Every TTL cache on a Supabase table is an egress multiplier. Calculate worst-case monthly
  cost before choosing TTL: `table_size_KB × (3600/TTL_seconds) × 24 × 30 / 1024 / 1024 = GB/month`.
- **Prevention**: OD-011 documents thresholds. `.claude/rules/egress-budget.md` triggers on new table reads.

### Lesson 71: has_insightface check must probe actual deferred imports, not just function references
- **Mistake**: `/api/compare/upload` checked `from core.ingest_inbox import extract_faces` and set `has_insightface = True`. But `core.ingest_inbox` has only stdlib top-level imports — cv2 and insightface are deferred inside `extract_faces()`. So the import always succeeds, even when cv2/insightface aren't installed. The graceful degradation path (save without face detection) was never reached on production.
- **Rule**: When checking whether optional ML dependencies are available, import the actual packages (cv2, insightface), not just the function that defers them. A function reference import tells you nothing about whether the function's internal imports will succeed.
- **Prevention**: Fixed the check to `import cv2; from insightface.app import FaceAnalysis` before trusting `has_insightface`. Added `opencv-python-headless<4.11` to requirements.txt. Created `tests/test_dependency_gate.py` — scans all app/core imports and verifies each resolves. Critical imports that have broken production get explicit tests.

### Lesson 159: ALWAYS verify deploy health before ending a session — failed deploy left site down overnight
- **Mistake**: Session 142 pushed commits and checked Railway deployment status for ML service (SUCCESS) but didn't verify the main app service. The main app deploy FAILED because Supabase identity load timed out (heavy GEDCOM queries from batch Gemini run overwhelmed free tier). Site was down from ~6:30 AM until user reported it.
- **Rule**: Before ending ANY session that pushes to main: (1) Check deploy status for ALL Railway services, not just one. (2) `curl -s https://rhodesli.nolanandrewfox.com/health` must return 200. (3) If deploy fails, redeploy or rollback before ending session. Never leave the site down.
- **Prevention**: Add health check to stop-gate.sh or session-end checklist. The production-verification rule already says this but it wasn't followed because the session was ending overnight with background tasks.

### Lesson 160: Batch scripts must verify logging on first call — 79 Gemini calls went unlogged
- **Mistake**: Session 142 batch Gemini script made 79 successful API calls but the Supabase audit logging failed for ALL of them because `build_prompt_lineage_fields()` returned columns (`contract_valid`, `full_response_hash`) that don't exist in the `gemini_api_calls` table. The error was logged as a warning but never checked. Data was saved to local JSON but the Supabase audit trail has a gap.
- **Rule**: Batch scripts that log to external systems MUST verify the first call's log succeeded before continuing. If logging fails, either fix it or abort — don't silently run 279 more calls without audit trail. Check logging output after call #1, not just the API result.
- **Prevention**: Add a `_verify_first_log()` check after the first successful Gemini call that queries `gemini_api_calls` to confirm the row was inserted. If it fails, log a P0 warning and offer to abort. Also: always test the full pipeline (API call + logging) in dry-run mode before batch execution.

### Lesson 161: Batch API calls — verify FULL output quality on first call, not just success
- **Mistake**: Session 142 batch Gemini ran 82 photos overnight. First 2 test photos returned good results (dates, ages, face analysis). But the GEDCOM context was NOT included for the remaining 82 because `_build_gedcom_context_for_photo()` timed out on Supabase for every photo. `gedcom_context_sent: False` on 83/84 labels. Should have checked `gedcom_context_sent` on the first real batch photo and stopped if False.
- **Rule**: After the first batch API call succeeds, verify EVERY enrichment flag in the output: `gedcom_context_sent`, `face_coordinates_sent`, all expected fields populated (not empty/None). If any enrichment is missing, STOP the batch and fix the enrichment before continuing. A successful API call with missing context is a waste of money.
- **Prevention**: Add a `_verify_first_result(label_entry)` function that checks all enrichment flags and field populations after photo #1. If any expected enrichment is False or empty, raise an error. The batch script should never silently degrade.

### Lesson 163: GEDCOM versioned importer does not scale to 175K+ row tables
- **Mistake**: Session 144 GEDCOM import took 30+ minutes, used 2.6GB RAM, wrote 700K+ change_log rows, and crashed when Supabase killed the connection during the change_log write. The import script reads ALL current rows into memory, does field-level diffing, then writes a per-field change log entry for every modified field across 22K individuals.
- **Rule**: (1) Change log writing must be non-fatal — wrap in try/except so entity data isn't lost. (2) The "unchanged rows" from the previous version must stay `is_current=true` after finalization — the importer only writes modified+added rows, so manually flipping `is_current` must account for unchanged rows. (3) Direct Postgres connection required — REST API times out reading 175K rows. (4) Consider architectural alternatives: prune old versions after import, limit change_log to added/removed (skip per-field diffs for modified), or use JSONB snapshots instead of row-per-entity versioning.
- **Prevention**: Before next import: add `--skip-change-log` flag, implement old version pruning, or redesign versioning. Test with the actual 175K-row table, not just unit tests with 5 rows.

### Lesson 164: datetime objects from direct DB reads must be serialized before Supabase REST API
- **Mistake**: Session 144 GEDCOM import used direct Postgres connection for reads (to avoid REST timeout) but then passed the resulting dicts to Supabase REST API for writes. Python `datetime` objects from psycopg2 can't be JSON-serialized by httpx. Error appeared in two places: the summary JSONB field and the error handler's `_set_version_status()`.
- **Rule**: Any data read from direct DB that will be sent via Supabase REST API must be round-tripped through `json.loads(json.dumps(data, default=str))` to convert datetime/date objects to strings. Apply this at the boundary (before any Supabase REST call), not just in one spot.
- **Prevention**: Add a `_sanitize_for_rest(data)` helper that does the round-trip conversion. Use it in `_set_version_status()`, `_build_summary()`, and any other function that bridges direct DB reads with REST API writes.

### Lesson 165: Supabase views with IS NULL clause include unversioned legacy rows
- **Mistake**: Session 144 GEDCOM context was empty for ALL batch photos despite Albert being linked. The `current_gedcom_individuals` view used `WHERE is_current = true OR is_current IS NULL` — the IS NULL clause included old version rows that hadn't been explicitly versioned. This caused 8,426 duplicate xrefs in REST API results, and Albert's row was excluded due to pagination inconsistency across duplicates.
- **Rule**: Views that filter by versioning columns (`is_current`) must use strict equality (`= true`), never `OR IS NULL`. Legacy rows from before versioning was added must be explicitly set to `false` during migration, not implicitly included via NULL.
- **Prevention**: After any schema change that adds versioning columns, backfill ALL existing rows with explicit values (not NULL). Audit all views for IS NULL clauses on versioning columns.

### Lesson 183: Supabase pooler is unreliable for long server-side cursor reads — use chunked-write, never accumulate large datasets in memory
- **Mistake (Session 158 Phase 158-2)**: Attempted a one-shot historical backfill of 196K-row `gedcom_individuals` into v2. Four approaches all failed today:
  1. **psycopg2 server-side cursor**: died mid-stream after ~10K rows — pooler closed the connection unexpectedly.
  2. **Chunked-by-version with per-chunk fresh connections + 5-retry**: 9 of 10 version-id chunks succeeded, but the NULL-version chunk (21,809 legacy pre-hash rows) failed all 3 retries.
  3. **Paginated NULL chunk + 5 retries**: failed even on the small `SELECT id, version_number FROM gedcom_versions` query — pooler in a degraded state.
  4. **Supabase REST API + accumulate-then-bulk-INSERT**: reads succeeded via `.range()` pagination (per Lesson 173), but loading 196K full-payload rows into one in-memory dict before writing plateaued at 951 MB resident memory and was stuck after 45 minutes — terminated.
  Net: zero rows written, full session lost on the cutover-day's central deliverable.
- **Rule**: For any backfill / migration touching ≥50K rows on Supabase, **NEVER accumulate the full dataset in memory**. Read AND write in batches: read one chunk, aggregate that chunk, upsert that chunk to the target, release memory, advance. The ON CONFLICT DO UPDATE pattern handles cross-chunk dedup naturally (each upsert sees the prior state via the existing target row's first/last_seen markers). For Supabase specifically, expect the pooler (`aws-0-<region>.pooler.supabase.com:6543`) to drop long-running cursor reads under load — a single bulk INSERT inside a short transaction is the only reliably-completing write pattern.
- **Prevention**:
  1. **Chunked-write template** for any ≥50K-row migration: outer loop over natural chunk keys (version_id, date range, gedcom_id prefix); each iteration reads a bounded slice (≤5–10K rows), aggregates in-memory ONLY for that slice, immediately upserts to target with `ON CONFLICT DO UPDATE SET first_seen=LEAST(...), last_seen=GREATEST(...)`, then `aggregated.clear()` before the next iteration. Per-chunk wall-clock should be <60s; total wall-clock typically 5–10 min.
  2. **Pre-flight pooler health probe**: before launching the heavy script, run a cheap probe (`SELECT count(*) FROM <table>` + `SELECT * FROM gedcom_versions`) 3 times. If 0–2/3 PASS, the pooler is degraded today — defer or switch to REST reads; do NOT attempt cursor reads.
  3. **Memory ceiling sanity check**: a chunk should fit in <100 MB. For ~22K rows of GEDCOM individuals (~5KB/row including JSONB), one chunk ≈ 110 MB — borderline but acceptable. Anything that would aggregate the full table (e.g., ~196K × 5KB ≈ 1 GB) is the failure mode this lesson exists to prevent.
  4. **Time-bound the run**: any single chunk that takes >5 min is a smell — abort, investigate (often: pooler degraded, or accidental full-table scan).
  5. **Related lessons**: 173 (REST `.range()` default page is 1000), 175 (use pooler not direct host), 178 (subagent token-budget hazard for multi-phase migrations).
