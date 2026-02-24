# Session 49B Triage — Root Cause Analysis & Fixes

**Date:** 2026-02-20
**Tests:** 2496 passed (+10 new), 0 failures

## Bug 1: Upload Stuck at 0%

**Root cause:** `PROCESSING_ENABLED=true` on Railway. Subprocess spawned with `stderr=subprocess.DEVNULL` to run `core.ingest_inbox`. Subprocess crashes (likely ML import or OOM), stderr is silently discarded. Status file (`data/inbox/{job_id}.status.json`) is never created. Polling endpoint returns "Starting..." forever.

**Evidence:** Railway logs showed 80+ consecutive `GET /upload/status/7c743eb1` requests at 2-second intervals — infinite polling loop.

**Fix:**
1. Write initial `"starting"` status file BEFORE spawning subprocess (so we can detect if it dies)
2. Log subprocess stdout/stderr to `data/inbox/{job_id}.log` instead of DEVNULL
3. Status polling detects `"starting"` status stuck for >2 minutes and shows error with log excerpt

**Lines changed:** `app/main.py` upload handler (~20028-20050), status endpoint (~20083-20140)

## Bug 2: Compare Silent Failure

**Root cause:** Compare WORKS on production. Confirmed via:
- `curl -X POST -F photo=@... /api/compare/upload` returned full results (20 matches, face detection working)
- Playwright browser test: uploaded file, received "2 faces detected" + 20 matches with face selector

**54F smoke test gap:** Production smoke tests (`scripts/production_smoke_test.py`) are GET-only — they test page loads, never POST files. The "11/11 passing" result was meaningless for upload functionality.

**Likely explanation for Nolan's experience:**
- Processing takes 5-10 seconds with no clear in-progress indicator visible
- Results appear below the fold; auto-scroll to `#compare-results` happens before the request completes
- May have been a transient Railway issue (memory pressure, container restart)

**No code change needed** — compare endpoint is functional.

## Bug 3: Sort Routing Broken

**Root cause:** `_sort_control()` (line 3357) generated sort links like `/?section=to_review&sort_by=faces` without `&view=browse`. Clicking a sort link dropped the `view=browse` parameter, defaulting to `view=focus`. Focus mode ignores the `sort_by` parameter entirely, rendering the same as unsorted.

**Fix:** Added `view_mode` parameter to `_sort_control()`. Callers:
- `render_to_review_section()` passes current `view_mode`
- `render_confirmed_section()` passes `view_mode="browse"` (always browse-like)

**Lines changed:** `app/main.py:3357` (function signature + URL generation), `3349` and `3409` (callers)

## Harness Learning: HD-013

Production smoke tests must test actual user flows (POST/upload), not just page loads (GET). The "11/11 smoke tests passing" claim in Session 54F was technically accurate but semantically misleading — none of the tests exercised file upload functionality.

## Tests Added (10)
- `TestSortLinksPreserveViewMode` — 4 tests (view=browse preserved in sort links)
- `TestUploadStatusTimeout` — 4 tests (starting status, timeout detection, log excerpt, no-file)
- `TestCompareUploadEndpoint` — 2 tests (form presence, spinner indicator)
