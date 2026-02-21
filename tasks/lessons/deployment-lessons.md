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

### Lesson 70: Dockerfile must COPY every package the web app imports at runtime
- **Mistake**: `rhodesli_ml/` was never added to the Dockerfile when its graph/importer modules were first imported by app/main.py (sessions 35-38). The Dockerfile only had `COPY app/`, `COPY core/`, `COPY scripts/`. Routes /connect, /tree, and /admin/gedcom all 500'd in production with `ModuleNotFoundError` — but worked locally because `rhodesli_ml/` existed on disk.
- **Rule**: When adding a NEW `from X import ...` to `app/main.py` where X is a package not already in the Dockerfile, you MUST update the Dockerfile in the SAME commit. "Works locally" is not "works in production."
- **Prevention**: Added 5 deploy safety tests (`TestDockerfileModuleCoverage`) that verify the Dockerfile has COPY directives for every rhodesli_ml subpackage the web app imports. Selectively copy only pure-Python runtime modules (graph/ + importers/ = 200KB), not the full ML package (3.2GB with .venv + checkpoints).

### Lesson 78: Production-local data divergence is the #1 recurring deployment failure
- **Mistake**: Session 49B reviewed 31 birth years via the admin UI on production. Those writes went to production's identities.json (on Railway volume). Subsequent deploys pushed local identities.json (which didn't have the birth years) to the Docker bundle, and init_railway_volume.py overwrote the production file by content hash. Birth years lost. This is at least the 4th occurrence of this pattern (Lessons 43, 56, 69 are all variants).
- **Rule**: The current architecture has a fundamental flaw: identities.json is BOTH written by admin actions on production AND deployed from the git bundle. There is no merge — whichever writes last wins. Every deploy risks overwriting admin work. BEFORE ANY PUSH TO PRODUCTION: always `sync_from_production.py` first to get the latest admin changes, merge locally, then push. This is a manual workaround for a broken architecture.
- **Prevention**: Short-term: add a pre-push hook or CI step that warns if local identities.json hasn't been synced recently. Medium-term: split identities.json into immutable seed data (deployed) and mutable admin data (production-only). Long-term: Postgres migration makes this a non-issue. Flag this as P0 infrastructure debt.

### Lesson 71: has_insightface check must probe actual deferred imports, not just function references
- **Mistake**: `/api/compare/upload` checked `from core.ingest_inbox import extract_faces` and set `has_insightface = True`. But `core.ingest_inbox` has only stdlib top-level imports — cv2 and insightface are deferred inside `extract_faces()`. So the import always succeeds, even when cv2/insightface aren't installed. The graceful degradation path (save without face detection) was never reached on production.
- **Rule**: When checking whether optional ML dependencies are available, import the actual packages (cv2, insightface), not just the function that defers them. A function reference import tells you nothing about whether the function's internal imports will succeed.
- **Prevention**: Fixed the check to `import cv2; from insightface.app import FaceAnalysis` before trusting `has_insightface`. Added `opencv-python-headless<4.11` to requirements.txt. Created `tests/test_dependency_gate.py` — scans all app/core imports and verifies each resolves. Critical imports that have broken production get explicit tests.
