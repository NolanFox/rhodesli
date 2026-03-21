# Session 130 — Data Integrity Deep Audit + Structural Prevention

@docs/session_context/session-129-data-audit.md
@docs/feedback/session-129-feedback.md
@tasks/lessons.md

## Background — Why This Session Exists

Session 129 uncovered a critical data corruption bug: the `identity_overrides` Supabase table was silently overwriting correct identity data with stale snapshots on every page load. This caused 36 faces to disappear across 4 identities (Esther Burd Fox lost 29 faces). The bug existed for 4 days (Mar 17-21) and was invisible because both tables were updated in the same `save_registry()` path — it only surfaced when a repair script wrote directly to `identities` without updating overrides.

This is the **9th occurrence** of the split-brain data pattern (Lessons 56→69→78→85→141→144→147→150→153). The user is rightfully frustrated: "I want real solutions, not just assurances that mean nothing."

### What Session 129 Fixed
- Removed `identity_overrides` read from `load_from_postgres()` (core/registry.py)
- Removed `sync_identity_overrides()` calls from `save_registry()` (app/main.py)
- Added 5 structural invariant tests (`tests/test_data_layer_invariants.py`)
- Merged duplicate Esther Burd Fox (83+29→112 faces) and Robert Mattatia
- Added duplicate name prevention to `confirm_identity()` and `rename_identity()`
- Verified: Esther shows 112 faces on production

### What Session 129 Did NOT Fix
- FB-016: photo_faces table uses inbox IDs while URLs use SHA256 IDs (10/18 faces unresolvable on Dayton Ohio group photo)
- 691 orphaned merge chains (targets deleted during past migrations)
- `identity_overrides` table still exists in Supabase (should be dropped)
- JSON backup still written asynchronously (is this needed?)
- No production health check that compares rendered face counts against Supabase

## Goal

Conduct the deepest possible data integrity audit, eliminate every remaining data layer that could diverge, and build infrastructure that makes this class of bug structurally impossible.

---

## Phase 1: Full Production Data Audit (CRITICAL)

### 1A: Verify EVERY confirmed identity
For each of the ~125 CONFIRMED non-merged identities:
1. Count anchor_ids in Supabase `identities` table
2. Count how many of those anchors exist in `embeddings.npy`
3. Count how many have crops (check R2 or photo_faces)
4. Compare to what the person page renders
5. Flag ANY discrepancy

Script output should be a table: `identity_id | name | supabase_anchors | embeddings_count | crop_count | rendered_count | status`

### 1B: Verify photo_faces ID consistency
For EVERY photo in the `photos` table:
1. What ID does the `photos` table use?
2. What IDs does `photo_faces` use for that photo's faces?
3. Do the IDs match?
4. If not, how many faces are "invisible" due to the mismatch?

This is FB-016 — the root cause of Esther's face being untagged on the Dayton Ohio photo. How many OTHER photos have this problem?

### 1C: Orphaned merge chain audit
For each of the 691 orphaned merge chains:
1. Is the face in ANY valid (non-merged, non-orphaned) identity?
2. If yes: the orphaned chain is harmless noise — document and ignore
3. If no: the face is genuinely lost — flag for repair

### 1D: identity_overrides cleanup
1. Verify `identity_overrides` table is no longer read by any code
2. Truncate or drop the table in Supabase
3. Verify no other "shadow" or "sync" tables exist that could cause the same pattern

---

## Phase 2: Structural Fixes

### 2A: Fix photo_faces ID mismatch (FB-016)
The upload pipeline creates inbox-style photo IDs in `photo_faces` but the photo page route generates SHA256 IDs. Fix options:
- A: Add SHA256 photo_id column to photo_faces (dual lookup)
- B: Normalize all photo_faces to use SHA256 IDs
- C: Make the photo page lookup try both ID formats

Pick the simplest option that doesn't break existing data.

### 2B: Remove JSON backup write (if safe)
`save_registry()` currently writes JSON in a background thread. Since Postgres is the sole source of truth:
- Is the JSON backup needed for anything?
- Can it be removed entirely?
- If kept, ensure it can NEVER be read as authoritative data

### 2C: Add production health check
Build an endpoint or script that:
1. Reads all CONFIRMED identities from Supabase
2. For each, checks that `len(anchor_ids)` matches the number of renderable faces
3. Reports any discrepancies
4. Can be run as a CI check or cron job

---

## Phase 3: Structural Prevention Tests

### 3A: Expand invariant test suite
Add tests for:
- No code path reads from JSON when DATA_SOURCE=postgres
- No code path writes to a "shadow" table alongside the primary table
- Every Supabase write in `save_registry()` is to the `identities` table only
- `photo_faces` IDs match `photos` table IDs for all entries

### 3B: Data reconciliation script
Build a reusable script (`scripts/data_reconciliation.py`) that:
- Compares all data sources (identities table, embeddings, photo_faces, R2 crops)
- Reports mismatches in a structured format
- Can be run after every deploy or data migration
- Documents WHAT was checked and WHEN

---

## Phase 4: Document Everything

### 4A: Update ALGORITHMIC_DECISIONS.md
- AD-NNN: Single Source of Truth — Final Resolution
  - Context: 9 occurrences of split-brain data pattern over 70+ sessions
  - Decision: Remove ALL secondary data layers; `identities` table is sole read/write source
  - What was removed: identity_overrides, JSON read path, override sync
  - What remains: JSON backup (write-only, async, non-authoritative)

### 4B: Update Lesson 153 with prevention results

### 4C: Write session-130 assessment with evidence

---

## Verification Gate

| Check | Method | Expected |
|-------|--------|----------|
| All CONFIRMED identities render correct face count? | Phase 1A script | 0 discrepancies |
| All photo_faces IDs match photos table? | Phase 1B script | 0 mismatches (or all fixed) |
| identity_overrides table empty/dropped? | Supabase check | Empty or dropped |
| No code reads from JSON in production? | Grep + invariant test | No read paths |
| Reconciliation script exists and passes? | Run it | PASS |
| Tests pass? | `make test-fast` | PASS |
| Production verified? | curl + browser | All faces visible |

---

## Context Files
- Data audit: `docs/session_context/session-129-data-audit.md`
- Feedback: `docs/feedback/session-129-feedback.md` (20 items, FB-001 through FB-020)
- Lesson 153: `tasks/lessons/data-lessons.md`
- Invariant tests: `tests/test_data_layer_invariants.py`
- Repair script: `scripts/repair_duplicate_identities.py`
