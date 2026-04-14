**Auditor**: Codex CLI v0.120.0 (gpt-5.4)
**Agent type**: Independent (fresh context)
**Scope**: Session 148/148b changes (commits dc4f3415 through 3b8c5f96)
**Date**: 2026-04-13

## Findings: 4 total (1 P1, 2 P2, 1 P3)

### P1: Auto-rejection bypasses registry API — FIXED
- **File**: app/admin_routes.py:1530
- **Issue**: Direct mutation of `identity["state"]` skipped version_id increment, updated_at, and history event recording. Inconsistent with canonical state-change paths.
- **Fix**: Replaced with `registry.reject_identity(iid, user_source="upload_rejected")`. Added `rejection_source` tag afterward.
- **Commit**: [pending]

### P2: backup-memory.sh regex misses filenames with digits — FIXED
- **File**: scripts/backup-memory.sh:36
- **Issue**: Pattern `([a-z_]*\.md)` doesn't match files like `project_session130_findings.md`. Could miss deleted files in integrity check.
- **Fix**: Changed regex to `([a-z0-9_]*\.md)`.
- **Commit**: [pending]

### P2: Photo analysis extraction changed patch seam — DEFERRED
- **File**: app/components/photo_analysis.py
- **Issue**: Tests patching `app.main._get_date_badge` no longer intercept calls from within photo_analysis.py since the function now lives in the new module. Test isolation is weaker but runtime behavior is correct.
- **Assessment**: Low risk — the functions still work correctly, and `app.main._get_date_badge` re-export means patches on main still affect callers that go through main. Only calls within photo_analysis.py itself bypass the patch. Not a functional issue, just test isolation hygiene.
- **BACKLOG**: TEST-PATCH-001

### P3: Restore button lacks UI rendering test — NOTED
- **File**: app/components/identity_cards.py:811
- **Issue**: No test asserts the restore button renders for admin REJECTED/CONTESTED and not for other states.
- **Assessment**: Route coverage exists. UI rendering test is nice-to-have but low risk since the button's `hx_post` target has proper auth guards.
