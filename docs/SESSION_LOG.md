# Session Log

Running log of Claude Code sessions and what was accomplished.
Update this at the END of every implementation session.

---

## Session 10: Init Script Hardening + Deployment Config Fix (2026-02-05)

**Goal:** Fix Railway deployment failures caused by init script creating `.initialized` marker even when no data was copied, leaving volume locked in empty state.

**Problem:**
1. Init script always created `.initialized` marker, even when bundles were empty (GitHub deploy)
2. Once marker exists, volume appears "initialized" but is actually empty
3. No recovery mechanism — stuck in bad state forever
4. `.railwayignore` wasn't committed, so `railway up` might still exclude needed files

**Root Cause:** The init script had no validation — it created the marker unconditionally at the end of the function, regardless of whether any data was actually copied.

**Completed:**
- Hardened `scripts/init_railway_volume.py`:
  - Added `volume_is_valid()` function to check for required files
  - Marker is only created when critical files exist
  - Detects "initialized but empty" state and auto-recovers
  - Returns exit code 1 on failure (helps Railway detect failed deploys)
  - Clear error messages explaining what to do
- Added `.railwayignore` to git tracking (was previously uncommitted)
- Updated `CLAUDE.md`:
  - Added "Gitignore vs Dockerignore vs Railwayignore" comparison table
  - Added "Init Script Marker Files" section with best practices
- Updated `docs/DEPLOYMENT_GUIDE.md`:
  - Expanded "Deployment Modes" section with CLI vs Git explanation
  - Added "Reset Protocol" for recovering stuck/empty volumes
  - Updated Change Log

**Files modified:**
- `scripts/init_railway_volume.py` (major hardening)
- `.railwayignore` (now tracked in git)
- `CLAUDE.md` (new sections)
- `docs/DEPLOYMENT_GUIDE.md` (reset protocol, expanded modes)
- `docs/SESSION_LOG.md` (this entry)

**Verification:**
- ✅ Init script detects "initialized but empty" state
- ✅ Init script removes invalid marker and attempts re-init
- ✅ Init script exits with code 1 on failure
- ✅ Init script does NOT create marker when bundles are empty

**Key Insight:**
The marker file pattern is dangerous if not implemented carefully. Always:
1. Validate before creating marker
2. Validate after finding marker
3. Provide automatic recovery
4. Exit with error codes on failure

---

## Session 9: Dockerfile GitHub Deploy Fix (2026-02-05)

**Goal:** Fix Dockerfile so it builds successfully from both CLI (`railway up`) and GitHub push deployments.

**Problem:** Railway deployment via GitHub push failed because `raw_photos/` and `data/` are gitignored but the Dockerfile has rigid `COPY` commands for them. GitHub builds don't have the gitignored content, causing COPY to fail.

**Root Cause:** `raw_photos/` had no tracked files. The `.gitkeep` was whitelisted in `.gitignore` but never created.

**Completed:**
- Created `raw_photos/.gitkeep` so directory exists in GitHub builds
- Updated `scripts/init_railway_volume.py` to detect empty bundles (GitHub deploy) and log clear warnings
- Added "Deployment Modes" section to `docs/DEPLOYMENT_GUIDE.md` explaining CLI vs GitHub deploys
- Added "Gitignore-Dockerfile Consistency Rule" to `CLAUDE.md`

**Files modified:**
- `raw_photos/.gitkeep` (created)
- `scripts/init_railway_volume.py` (empty bundle detection)
- `docs/DEPLOYMENT_GUIDE.md` (deployment modes section)
- `CLAUDE.md` (gitignore-dockerfile consistency rule)
- `docs/SESSION_LOG.md` (this entry)

**Verification:**
- ✅ `docker build .` succeeds with full data (CLI deploy simulation)
- ✅ `docker build .` succeeds with only `.gitkeep` files (GitHub deploy simulation)
- ✅ Init script logs appropriate warnings when bundles are empty

**Key Insight:**
- Initial deploy: `railway up` (CLI) — seeds volume with local photos/data
- Code updates: `git push` — photos already on volume, Dockerfile handles empty bundles

---

## Session 8: Single Railway Volume Fix (2026-02-05)

**Goal:** Fix deployment configuration for Railway's single-volume limitation.

**Problem:** Railway only allows ONE persistent volume per service. Our deployment guide assumed two volumes (`/app/data` and `/app/raw_photos`).

**Completed:**
- Added `STORAGE_DIR` environment variable for single-volume mode
- Updated `core/config.py` to derive `DATA_DIR` and `PHOTOS_DIR` from `STORAGE_DIR` when set
- Updated `scripts/init_railway_volume.py` to create subdirectories in single volume
- Updated `app/main.py` to use config paths instead of hardcoded paths
- Updated `Dockerfile` with storage directory creation and comments
- Updated `docs/DEPLOYMENT_GUIDE.md` for single volume setup
- Updated `.env.example` with `STORAGE_DIR` documentation
- Added "Deployment Impact Rule" to CLAUDE.md

**Files modified:**
- `core/config.py` (added STORAGE_DIR logic)
- `scripts/init_railway_volume.py` (single-volume support)
- `app/main.py` (use config paths)
- `Dockerfile` (storage directory, comments)
- `docs/DEPLOYMENT_GUIDE.md` (single volume instructions)
- `.env.example` (STORAGE_DIR documentation)
- `CLAUDE.md` (added Deployment Impact Rule)
- `docs/SESSION_LOG.md` (this entry)

**Verification:**
- ✅ Local dev: `python app/main.py` uses `./data/` and `./raw_photos/`
- ✅ Docker dual-mount: mounts data/ and raw_photos/ separately
- ✅ Docker single-volume: `STORAGE_DIR=/app/storage` creates subdirectories

**Notes:**
- Railway environment requires: `STORAGE_DIR=/app/storage`
- Volume mount path: `/app/storage`
- Init script creates: `storage/data/`, `storage/raw_photos/`, `storage/staging/`

---

## Session 7: Harness Improvement (2026-02-05)

**Goal:** Update documentation to prevent future absolute-path-style bugs from reaching production.

**Completed:**
- Added Pre-Deployment Checklist to CLAUDE.md with path/hostname audit commands
- Added Post-Bug Protocol to CLAUDE.md for systematic harness improvements
- Added Docker Startup Log Audit section to MANUAL_TEST_CHECKLIST.md
- Added absolute paths bug to Known Bug Locations table (marked fixed)

**Files modified:**
- `CLAUDE.md` (added Pre-Deployment Checklist + Post-Bug Protocol sections)
- `docs/MANUAL_TEST_CHECKLIST.md` (added Docker audit section, updated bug table)
- `docs/SESSION_LOG.md` (this entry)

**Lessons learned:**
- Data files generated locally can contain environment-specific values
- The path from local dev → Docker → Railway is a critical validation point
- Startup logs are the first line of defense for catching environment issues

---

## Session 6: Fix Hardcoded Paths (2026-02-05)

**Goal:** Convert absolute paths in photo_index.json to relative paths for Docker/Railway compatibility.

**Problem:** 12 inbox photos had absolute paths like `/Users/nolanfox/rhodesli/data/uploads/...` which caused Docker runtime warnings and would fail on Railway.

**Completed:**
- Diagnosed issue: 12 photos in `data/uploads/b5e8a89e/` had absolute paths
- Created `scripts/fix_absolute_paths.py` migration script with `--dry-run`/`--execute` flags
- Updated `app/main.py:_load_photo_path_cache()` to handle relative paths
- Migrated photo_index.json to use relative paths (`data/uploads/...`)
- Verified in Docker: no missing file warnings, health endpoint OK, photos served correctly

**Files created:**
- `scripts/fix_absolute_paths.py`

**Files modified:**
- `app/main.py` (updated path resolution logic)
- `data/photo_index.json` (converted 12 absolute paths to relative)
- `data/photo_index.json.bak` (backup created by migration)

**Verification:**
- Docker startup: `[startup] Photo path cache: 12 inbox photos indexed` (no warnings)
- Health endpoint: `status: ok`, 268 identities, 124 photos
- Photo serving: HTTP 200 for both inbox and legacy photos

---

## Session 5: Operational Documentation (2026-02-05)

**Goal:** Create operational documentation for day-to-day management.

**Completed:**
- Created `docs/OPERATIONS.md` — comprehensive runbook covering:
  - Data architecture diagrams
  - Photo processing workflow
  - Local ↔ Production sync procedures
  - Backup & recovery
  - Troubleshooting guide
  - Quick reference table
- Created `docs/SESSION_LOG.md` — this file
- Updated `CLAUDE.md` with Project Status section

**Files created:**
- `docs/OPERATIONS.md`
- `docs/SESSION_LOG.md`

**Files modified:**
- `CLAUDE.md` (added Project Status section)

---

## Session 4: Phase A Deployment (2026-02-05)

**Goal:** Dockerize application and prepare for Railway deployment.

**Completed:**
- Added environment variable configuration to `core/config.py`
- Modified `app/main.py`:
  - Uses config for host/port/debug
  - Added `/health` endpoint
  - Modified upload handler for staged uploads when `PROCESSING_ENABLED=false`
  - Added comprehensive startup logging
- Created Docker deployment infrastructure:
  - `Dockerfile` (python:3.11-slim, lightweight)
  - `.dockerignore`
  - `railway.toml`
  - `.env.example`
  - `scripts/init_railway_volume.py`
- Created `docs/DEPLOYMENT_GUIDE.md` with Railway + Cloudflare setup
- Updated documentation (CHANGELOG, RELEASE_NOTES, MANUAL_TEST_CHECKLIST)

**Files created:**
- `Dockerfile`
- `.dockerignore`
- `railway.toml`
- `.env.example`
- `scripts/init_railway_volume.py`
- `docs/DEPLOYMENT_GUIDE.md`

**Files modified:**
- `core/config.py`
- `app/main.py`
- `requirements.txt` (added Pillow)
- `.gitignore`
- `CHANGELOG.md`
- `docs/RELEASE_NOTES.md`
- `docs/MANUAL_TEST_CHECKLIST.md`

**Commits:**
- `c2139e1` feat: add environment variable configuration for Railway deployment
- `09d9d12` feat: add Docker and Railway deployment configuration
- `7e85d17` docs: add deployment guide and update release documentation

---

## Session 3: System Design (2026-02-05)

**Goal:** Create comprehensive architecture document for web deployment.

**Completed:**
- Created `docs/SYSTEM_DESIGN_WEB.md` (1300+ lines)
- Documented "Layered Truth" architecture (Canonical + Community + Users)
- Finalized decisions: Railway, Supabase, Cloudflare, invite-only auth
- Created implementation phases A-F with detailed prompts
- Added schema extension guide

**Files created:**
- `docs/SYSTEM_DESIGN_WEB.md`

---

## Session 2: Bug Fixes + Features (2026-02-04)

**Goal:** Fix interaction bugs, add source attribution and photo viewer.

**Completed:**
- Fixed 6 interaction bugs (documented in POST_MORTEM_UI_BUGS.md)
- Added Source Attribution feature:
  - `source` field in PhotoRegistry
  - Source input on upload form
  - Source display in Photo Context modal
- Added Photo Viewer section:
  - Grid view of all photos
  - Filter by collection
  - Sort options

**Files modified:**
- `app/main.py`
- `core/photo_registry.py` (if exists)

**Commits:** Multiple (see git log for details)

---

## Session 1: UI Overhaul (2026-02-04)

**Goal:** Complete redesign of UI with Command Center layout.

**Completed:**
- Built Command Center with fixed sidebar navigation
- Implemented Focus Mode (review one identity at a time)
- Implemented Browse Mode (grid view)
- Added Darkroom theme (dark mode)
- Added Skip/Reset workflow states
- Fixed vanishing reject bug

**Files modified:**
- `app/main.py` (extensive changes)
- `app/static/` (CSS updates)

**Documentation created:**
- `docs/POST_MORTEM_UI_BUGS.md`
- `docs/INTERACTION_TESTING_PROTOCOL.md`

---

## How to Update This Log

At the end of each session, add a new entry at the TOP with:

```markdown
## Session N: [Short Title] (YYYY-MM-DD)

**Goal:** [What you set out to do]

**Completed:**
- [Bullet points of what was done]

**Files created:**
- [List new files]

**Files modified:**
- [List changed files]

**Commits:**
- [List commit hashes and messages, or "see git log"]

**Notes:** [Any important context for future sessions]
```
