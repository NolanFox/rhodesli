# Session 161 Post-Execution Audit

**Auditor**: Claude general-purpose subagent (Opus 4.7, fresh context)
**Agent type**: Independent (no prior context)
**Scope**: rhodesli + rhodes-wiki Session 161 changes
**Date**: 2026-05-13
**Verdict**: PASS-WITH-FIXES

**Note**: Codex CLI v0.130.0 attempted first per harness `ai-tool-audit.md` (gpt-5.5, xhigh) but the run hung on a `find` scan of `$HOME` (>10 min, no progress, sandbox couldn't `pkill`). Per Session 161 prompt's documented fallback path, the audit was retried via Claude general-purpose subagent with the same prompt.

## Summary

The executed code faithfully implements the pre-audit-corrected plan: gate order (rhodes-wiki availability → CSRF → admin → slug-validate) is correct on every POST route; atomic CAS, path-traversal defense, production gating, and schema match the spec. Most pre-audit P0/P1 fixes are present and exercised by the 34 tests. One P1 gap (no unit test for `detect_drift()`/`reconcile()`), two P2 issues (race-loser leaves filesystem drift; mislabeled audit entity_type), one P2 marginal note, and five P3 cleanups remain.

## P0 findings

None.

## P1 findings

- **[P1-1] No tests for `scripts/rhodes_inbox_reconcile.detect_drift()` or `reconcile()`** (`tests/` — missing file)
  Evidence: `grep -rln "detect_drift\|rhodes_inbox_reconcile" tests/` returns nothing. The prompt's verify item #5 listed "drift detection test all present" — this requirement is not met. The reconcile script handles the post-crash recovery path (Supabase-approved + filesystem-still-pending) but has zero coverage. A small bug in `_scan_filesystem`'s multi-state warning or `reconcile()`'s `os.replace` call would not be caught.
  Fix: add `tests/test_rhodes_inbox_reconcile.py` with at least: (a) mismatch fs/sb → reconcile moves fs to match sb; (b) fs_only → upserts Supabase row; (c) sb_only → reported, no fs side-effects; (d) consistent state → empty actions dict.
  **Status**: FIXED in commit (Phase 8) — 5 new tests added.

## P2 findings

- **[P2-1] Race-loser `AlreadyApprovedError` path leaves filesystem in `pending/` while Supabase is at `approved`** (`app/rhodes_inbox.py:344-347`)
  Evidence: When the CAS loses because someone else already approved, the function raises BEFORE the filesystem move. Source remains in `pending/`, target slug is in `approved/` per Supabase truth. This is exactly the drift case the reconcile script handles, but each lost race silently generates work for it. The admin route redirects with `msg=already_approved` so user-facing UX is fine, but the filesystem state is wrong every time. Test `test_mark_approved_already_approved_raises` even asserts this drift (`assert (fake_inbox / "inbox" / "pending" / ...).exists()`).
  Fix proposed: in the race-loser branch, if `check.data[0]["status"] == "approved"` and `pending/<slug>` exists locally, attempt `os.replace(pending, approved)` before raising.
  **Status**: Deferred to RHODESLI-INBOX-008 (BACKLOG). Single-admin local-dev MVP — drift is documented design (AD-RID-6) and the reconcile script handles it. Fix is worthwhile when a 2nd admin scenario lands.

- **[P2-2] `_log_audit(entity_type="identity")` mislabels rhodes_inbox entries** (`app/audit.py:35`, called from `app/rhodes_inbox.py:391-397, 474-481`)
  Evidence: `app/audit.py:35` hard-codes `"entity_type": "identity"`. Approve/reject of an inbox entry is NOT an identity mutation — it's a `rhodes_inbox_entries` row transition. Future audit queries filtering by `entity_type='rhodes_inbox'` will miss these rows.
  Fix: extend `_log_audit` to accept `entity_type` parameter (default "identity" for back-compat), and pass `entity_type="rhodes_inbox"` from both call sites in `app/rhodes_inbox.py`.
  **Status**: FIXED in commit (Phase 8).

- **[P2-3] `mark_approved` retry-after-upsert can succeed at Supabase but skip filesystem move silently** (`app/rhodes_inbox.py:351-364`)
  Evidence: The retry path reads `_read_post_json(slug, "pending")` to populate the upsert. If `post is None`, it raises `FileNotFoundError`. But if `post` IS readable AND the second CAS succeeds, the function falls through to the filesystem block at line 366. There it does `if src.exists()` — but the test `test_mark_approved_creates_row_when_missing` covers only mocked Supabase, not the filesystem after. So if any future code path lands here when `src` doesn't exist (e.g., a manual rm during a race), the function silently completes without filesystem state. Marginal — but flag because it crosses the Supabase/filesystem trust boundary.
  Fix proposed: add an assertion in `test_mark_approved_creates_row_when_missing` that the filesystem was moved, OR raise if both src and dst missing in mark_approved (currently only warns).
  **Status**: Deferred to RHODESLI-INBOX-009 (BACKLOG). Edge case requires manual filesystem mutation between Supabase write and filesystem move — drift detector covers the operational failure mode.

## P3 findings

- **[P3-1] Dead `csrf_token` hidden field on approve form** (`app/admin_rhodes_inbox_routes.py:295`)
  Evidence: `Input(type="hidden", name="csrf_token", value="")` — empty value, never validated. The real CSRF protection is `_check_origin`. The empty hidden field is misleading.
  **Status**: FIXED in commit (Phase 8) — line removed.

- **[P3-2] Reject form lacks the (dead) csrf_token field even though approve has one** (`app/admin_rhodes_inbox_routes.py:303-310`)
  Evidence: Approve form at line 294 has the dead csrf_token Input; reject form at 303 does not. Inconsistent.
  **Status**: FIXED via P3-1 deletion — inconsistency removed at source.

- **[P3-3] `mark_rejected` reuses `approved_by` column for the rejector's email** (`app/rhodes_inbox.py:417`)
  Evidence: Comment says `"reuse approved_by as actor; approved_at left null"` — but the next line writes `"approved_at": _now_iso()`. Column name overloads two meanings.
  **Status**: Deferred to RHODESLI-INBOX-010. Schema-change required.

- **[P3-4] `prefill_description` is computed but never passed to `upload_area`** (`app/upload_routes.py:386, 407`)
  Evidence: Line 386 declares `prefill_description = ""`; line 407 sets it to the FB caption; the `upload_area(...)` call at line 562-571 does NOT pass `prefill_description`. The variable is dead code.
  **Status**: Deferred to RHODESLI-INBOX-011. Would require upload_area signature change.

- **[P3-5] `is_rhodes_wiki_available` checks "pending OR approved" but not "rejected"** (`app/rhodes_inbox.py:70-71`)
  Evidence: A vault that has only `rejected/` will return False here. Edge case — vault must have at least one of pending/approved to be valid by definition.
  **Status**: Deferred — Won't-Fix. The vault initialization always creates pending/ first; rejected-only is unreachable.

## Categories Confirmed Clean

1. **Security gate order** — Clean. All 4 admin routes verify rhodes-wiki availability FIRST (404 silently), then CSRF (`_check_origin`, POSTs only), then `_check_admin`, then `_validate_slug`. `_validate_slug` is called BEFORE any filesystem op in `mark_approved`/`mark_rejected`/`load_entry`/`link_rhodesli_photo`/`kinship_triples_for`. Path-traversal test asserts `client.table.assert_not_called()` after the raise — Supabase never touched.

2. **Cross-repo boundary** — Clean. `rhodesli/.claude/settings.json` denies `Edit/Write` on `/Users/nolanfox/rhodes-wiki/**` and denies `python /Users/nolanfox/rhodes-wiki/*`. rhodesli code uses `os.replace` (POSIX atomic, NOT `shutil.move`). Cross-repo writes are limited to `mark_approved` / `mark_rejected` filesystem renames inside rhodes-wiki/inbox/.

3. **Atomicity** — Clean. Supabase-first ordering verified at `app/rhodes_inbox.py:309-364, 407-455`. Atomic CAS via `.update(...).eq("slug", x).eq("status", "pending").execute()` then `if not result.data: raise AlreadyApprovedError`. `AlreadyApprovedError` and `AlreadyRejectedError` defined as `RuntimeError` subclasses. Race-loser path generates drift (see P2-1, deferred) — recovery via reconcile script.

4. **Production safety** — Clean. `is_rhodes_wiki_available()` checks `RAILWAY_ENVIRONMENT` FIRST. Every admin handler short-circuits to 404. `count_pending_rhodes_inbox()` returns 0 in same conditions. `_count_pending_rhodes_inbox_safe()` wraps in try/except.

5. **Test coverage** — Was P1-1 gap; FIXED. Path-traversal: 4 tests. CAS race: 2 tests. Production-gate: 5 tests. Drift detection: 5 tests added (Phase 8 fix). Atomic CAS + reconciliation now both have coverage.

6. **Schema correctness** — Clean. `rhodesli_photo_id TEXT REFERENCES photos(photo_id) ON DELETE SET NULL` matches `photos.photo_id TEXT PRIMARY KEY`. `kinship_triples_json JSONB` ✓. `rejection_reason` 4096-char CHECK ✓ — caller truncates AND constraint enforces. `status` 3-value CHECK ✓. rhodes-wiki ARCHITECTURE.md §3.3 is synced.

7. **FB-NESTED-001 `_infer_depth`** — Clean. Handles all three documented signals: `declared >= 1` preserved verbatim, `aria_label.startswith("reply by")` → 1, `parent_comment_id` non-empty string → 1. Synthetic tests cover both inference paths plus the "trust JS when >=1" branch.
