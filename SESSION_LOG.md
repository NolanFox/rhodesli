# Session 65d Log
## Mission: Fix disk space → verify upload in browser → GEDCOM versioning → self-improving harness
## Started: 2026-02-24
## Context: Upload shows "Errno 28: No space left on device". Chrome plugin enabled.
## Rule: /clear between phases, NEVER /compact.
## Predecessor: Session 65c (v0.70.0 — upload OOM fix, verification sweep, harness)

### Phase 0: Orient
- [x] Read CLAUDE.md, ROADMAP.md, session-65d-context.md, SESSION_LOG.md, tasks/lessons.md
- [x] Set .claude/current_session.txt to "65d"
- App version: v0.70.0 | ~3475 tests | 271 photos | 775 identities | 55 confirmed
- Key context: Upload RAM fix worked (65c), but now hits Errno 28 (disk full) on Railway
- Upload surfaces to test: /upload, /compare/pair, /estimate
- Chrome plugin enabled for browser verification

### Phase 1: Disk Space Fix + Upload Browser Verification
#### 1A: Diagnosis
- Docker image bundled 393MB of unnecessary backup files from data/backups/ via COPY data/
- Push endpoint creates .bak.{ts} files that accumulate unbounded on Railway volume
- No cleanup of staging/inbox temp files after upload processing
- No disk space monitoring at startup

#### 1B: Fixes Applied (committed b1dea0c, pushed)
- [x] .dockerignore updated: excludes data/backups/, data/auto_backups/, data/staging/, raw_photos/ (~400MB savings)
- [x] Startup cleanup (`_startup_disk_cleanup`): removes stale staging dirs (>1hr), old inbox files (>24hr), .tmp files
- [x] Backup pruning (`_prune_bak_files`): keeps only 3 most recent .bak files per type, runs at startup + after push
- [x] Upload temp cleanup: `finally` block in `_background_ingest` removes staging dir after processing
- [x] Health endpoint reports disk space: total_mb, free_mb, used_pct
- [x] 10 new tests in tests/test_session_65d_disk_cleanup.py
- [x] AD-162 logged

#### 1C: Browser Verification (Chrome plugin — admin logged in)
- [x] /upload: PASS — "0 faces extracted, 0 added to Inbox" (synthetic canvas image, no real face)
- [x] /compare/pair: PASS — Panel A shows "No faces detected. Try a clearer photo." (upload processed, no disk error)
- [x] /estimate: PASS — Returned "Expected year: ~1945" with decade probability distribution
- [x] Health endpoint: disk 45.2% used, 1.6TB free
- All three upload surfaces work. No Errno 28. Disk space fix confirmed.

#### Phase 1 VERDICT: PASS
Upload fixed across 3 sessions: 65a (PID tracking), 65c (RAM/OOM fix), 65d (disk space cleanup).
