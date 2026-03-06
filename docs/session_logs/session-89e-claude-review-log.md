# Session 89e — Claude Review of Codex/GPT-5.4 Work

**Date**: 2026-03-05
**Type**: Review + Fix + Deploy session
**Predecessor**: Session 89e (Codex checkpoint at a3a6fd5)
**Commits**: 130231a (test fixes), 8c0d108 (assessment)

## Work Completed

### 1. Full Audit of Codex's 89e Checkpoint
- Read all Codex docs, diffs (34 files, ~13K insertions)
- Verified code changes against original prompt requirements
- Identified weakened test assertions, subprocess test debt, data safety risks

### 2. Benatar Photo Full Recovery
- Raw photo was already on R2 (repair endpoint worked in previous session)
- Face crop was MISSING — regenerated locally using InsightFace
- Uploaded crop `inbox_a4c3a5701b51.jpg` (7.4KB) to R2 via boto3
- Verified both photo and crop render on production identify page
- **Link**: https://rhodesli.nolanandrewfox.com/identify/1e0b3bc8-c823-4434-b12f-39c6dcf82cd2

### 3. Bug Fixes
- **core/confidence.py:95**: `distance = float(distance)` — numpy arrays caused `int()` crash. Pre-existing bug, not Codex-related.
- **tests/test_skipped_focus.py:578**: Changed `if "focus-btn-confirm" in html` to `if 'id="focus-btn-confirm"' in html` — was matching JS string reference, not actual button element. Codex bug.

### 4. Data Safety
- Restored data files to origin/main state before push
- Codex had synced production data (295 photos) into the commit; pushing would risk overwriting production admin actions
- init_railway_volume.py safety gate would likely have blocked it, but better safe than sorry

### 5. Production Deployment + Verification
- Pushed code changes (no data files)
- Called repair endpoint: `POST /api/sync/repair-upload` with job_id `0c57277a`
- Verified in Claude Chrome: Benatar photo, Leon's Restaurant, sort behavior, performance
- All pages <500ms response time

### 6. Pre-existing Issues Found
- **Phantom duplicate**: `/photo/a75e6b54b0eb6c50` is SHA256 of `unknown.jpg`, auto-generated when repair copied file to raw_photos/. Person 877 is the phantom identity. Both need cleanup on production.
- **Upload date backfill**: Script exists at `scripts/backfill_upload_dates.py` but needs safe production execution path (admin endpoint or sync-run-push workflow).

## Codex/GPT-5.4 Evaluation for Future Reference

### Task Types Where Codex May Add Value
1. **Script writing** with clear specs (backfill, cleanup, migration scripts)
2. **Root-cause analysis** of production bugs (good at reading logs and code)
3. **Caching/performance patterns** (well-structured TTL cache implementation)
4. **Documentation generation** (session logs, assessments — adequate quality)

### Task Types Where Codex Struggled
1. **Test stabilization** — spent 3+ hours and introduced technical debt
2. **Commit discipline** — failed commit-after-act even after repeated user emphasis
3. **Deploy + verify loop** — never deployed or browser-verified anything
4. **Data file handling** — mixed production sync with code changes in one commit
5. **Closure** — strong on analysis, weak on finishing and shipping

### Key Lesson for Future Codex/GPT Sessions
**Give Codex narrow, well-scoped tasks with clear acceptance criteria. Do NOT give it multi-act sessions that require deploy/verify discipline.** Best pattern: give Codex one specific bug fix or one script to write, then have Claude review and deploy.

### Approximate ROI
- Codex wall time: ~5 hours
- Useful output: ~2 hours of work (R2 path fix, perf caches, scripts)
- Claude review time: ~1.5 hours (audit, fix, deploy, verify, recover crop)
- Total cost: ~6.5 hours for ~2 hours of unique value
- **Verdict**: Net negative for this session. Claude alone would have finished in ~2 hours.

## Test Suite Concern
~3700 tests for a single-dev project is disproportionate. Many integration tests:
- Boot entire app and hit real data files
- Break when UI evolves (testing CSS classes, HTML attributes)
- Codex's subprocess fix adds 3-5s overhead per test

**Recommendation**: Audit test suite. Keep contract tests. Delete implementation-detail tests. Target: <1500 meaningful tests, <2 min runtime.

## Data Safety Research

### What's NOT in Postgres (HIGH risk if volume lost)
- identities.json, photo_index.json, embeddings.npy
- date_labels.json, photo_locations.json, photo_search_index.json

### What IS in Postgres (safe)
- Face alignments, GEDCOM data, user accounts, annotations (partial)

### Recommendation
1. Short term: Nightly Railway volume → R2 backup script
2. Medium term: Supabase shadow writes for identities + photo_index
3. Long term: Complete Postgres migration (Phase F)

## Files Changed This Session
- `core/confidence.py` — numpy scalar fix
- `tests/test_skipped_focus.py` — button element check fix
- `docs/assessments/session-89e-claude-review-assessment.md` — NEW
- `docs/session_logs/session-89e-claude-review-log.md` — NEW (this file)
- R2: `crops/inbox_a4c3a5701b51.jpg` uploaded (face crop for Benatar photo)
