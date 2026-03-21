# Session 129 — Data Integrity Audit

**Date:** 2026-03-21
**Predecessor:** Session 128

## Task 1: Duplicate Name Code Path Analysis

### Root Cause
The `confirm_identity()` method in `core/registry.py` (line ~827) performs two checks before confirming:
1. State must be INBOX, PROPOSED, or SKIPPED
2. Name must not be a placeholder ("Unidentified Person...")

**Missing check:** No validation that another non-merged CONFIRMED identity already exists with the same name.

### All Code Paths That Create CONFIRMED Identities

| Route | File:Line | How it confirms |
|-------|-----------|----------------|
| `POST /confirm/{identity_id}` | identity_routes.py:71 | `registry.confirm_identity()` directly |
| `POST /api/photo/{photo_id}/quick-action` | identity_routes.py:1506 | `registry.confirm_identity()` for action="confirm" |
| `POST /api/face/create-identity` | identity_routes.py:1566 | `rename_identity()` + `confirm_identity()` (auto-confirm on tag) |
| `POST /inbox/confirm/{identity_id}` | identity_routes.py:3765 | `registry.confirm_identity()` for INBOX items |
| `POST /identity/{identity_id}/name-and-confirm` | identity_routes.py:~4200 | `rename_identity()` + `confirm_identity()` |

**ALL five paths** call `registry.confirm_identity()`, which is the single choke point. The fix in `confirm_identity()` covers all paths.

### Rename Path
`rename_identity()` in `core/registry.py` (line ~1137) also had no duplicate check. When renaming a CONFIRMED identity to a name that another CONFIRMED identity already has, this was silently allowed.

## Task 2: Supabase Data Integrity Scan Results

| Check | Result | Details |
|-------|--------|---------|
| Duplicate CONFIRMED names | PASS (0) | No current duplicates (user likely already merged them) |
| Orphaned merge targets | FAIL (691) | 691 identities have `merged_into` pointing to 106 non-existent IDs |
| Multi-claimed faces | PASS (0) | No faces claimed by multiple non-merged identities |
| Photo-face mapping gaps | PASS (0) | All identity faces exist in photo_faces table |
| Merge chain integrity | FAIL (691) | All 691 orphaned merge targets are also broken chains |

### Orphaned Merge Targets — Top Missing IDs
| Missing Target ID | Orphaned Source Count |
|-------------------|----------------------|
| 9b686cf1-b1ad-... | 219 |
| 5981a409-0572-... | 138 |
| a71d7a56-8044-... | 108 |
| 26fe72fa-3271-... | 34 |
| ef7470fd-9f3... | 19 |

**Root cause:** These 106 identity IDs were deleted from the identities table (likely during data migrations or reconciliation scripts) but their merge chains were not updated. The 691 orphaned identities are effectively "dead" — they have `merged_into` pointing to nowhere, and since they're all "Unidentified Person NNN" with no user data, they are harmless ghost records.

**Recommended action:** These can be safely cleaned up by setting `merged_into = NULL` and state back to INBOX, or by deleting them entirely since they contain no user-provided information. This is a cleanup task, not a data integrity emergency.

## Task 3: Root Cause Analysis

**The duplicate confirmed identity bug** was introduced when `confirm_identity()` was first written (Session ~59C, the Postgres migration). The method was designed to validate state transitions but never included a uniqueness check on the name field.

**How duplicates happen:**
1. Admin triages "Unidentified Person 1234", renames it to "Esther Burd Fox", confirms
2. Later, admin encounters another cluster, renames to "Esther Burd Fox", confirms
3. No warning is shown — two CONFIRMED identities now exist with the same name
4. The correct workflow should have been: rename + merge into the existing identity

**Why it wasn't caught sooner:**
- The identity model doesn't enforce unique names at the database level (names aren't primary keys)
- The admin triage workflow (speed-run, focus mode) is fast and doesn't show "existing matches" before confirm
- Tests never tested the multi-confirm-same-name scenario

## Task 4: Prevention Fix Applied

### Changes Made
1. **`core/registry.py` — `find_confirmed_by_name()`** (new method)
   - Case-insensitive search across all non-merged CONFIRMED identities
   - Returns matching identity or None
   - `exclude_id` parameter to allow self-rename

2. **`core/registry.py` — `confirm_identity()`** (modified)
   - Added duplicate name check before state transition
   - Raises `ValueError` with message suggesting merge instead

3. **`core/registry.py` — `rename_identity()`** (modified)
   - Added duplicate name check when renaming a CONFIRMED identity
   - Does NOT block renaming PROPOSED/INBOX identities (they may need the same name before merge)

4. **`tests/test_registry.py` — `TestDuplicateNamePrevention`** (9 new tests)
   - `test_confirm_rejects_duplicate_name`
   - `test_confirm_allows_different_name`
   - `test_confirm_duplicate_check_is_case_insensitive`
   - `test_confirm_ignores_merged_identities`
   - `test_rename_confirmed_rejects_duplicate_name`
   - `test_rename_non_confirmed_allows_duplicate_name`
   - `test_find_confirmed_by_name_returns_match`
   - `test_find_confirmed_by_name_returns_none_for_no_match`
   - `test_find_confirmed_by_name_excludes_self`

5. **Existing test fix:** `test_excludes_current_identity` updated to use unique names (was creating two CONFIRMED identities with "Test Person")

## Task 5: Orphaned Merge Chains

### Findings
- 691 identities have `merged_into` pointing to 106 non-existent IDs
- All are "Unidentified Person NNN" — no user-provided data at risk
- The top 3 missing targets account for 465/691 orphans (67%)
- These are harmless ghost records from past data migrations

### Recommended Cleanup (Future Session)
Option A: Delete orphaned merged identities (they have no faces, no user data)
Option B: Set `merged_into = NULL`, move to INBOX for re-triage
Option C: Leave as-is (they're filtered out of all queries by the `merged_into` check)

**Recommendation:** Option C for now (no user impact), Option A in a dedicated cleanup session.

## Summary

| Issue | Severity | Status |
|-------|----------|--------|
| Duplicate CONFIRMED names possible | P1 | FIXED — duplicate check added to confirm + rename |
| 691 orphaned merge targets | P3 | DOCUMENTED — harmless ghost records, cleanup deferred |
| Multi-claimed faces | n/a | PASS |
| Photo-face mapping gaps | n/a | PASS |
