# Investigation: Esther Burd Face Assignment — Declared Fixed But Wasn't

**Date:** 2026-03-22
**Investigator:** Claude (Session 131 read-only investigation)
**Subject:** FB-002 (Esther Burd face untagged in photo despite prior tagging)

---

## What Was Claimed

### Session 129 Claims
1. **FB-001 (FIXED):** Duplicate Esther Burd Fox identities merged — d4f29ffb (29 anchors) into 65207728 (83 anchors) = 112 total anchors.
2. **identity_overrides root cause (FIXED):** Override layer removed from `load_from_postgres()` and `save_registry()`. 5 structural tests added.
3. **"Verified: Esther shows 112 faces on production post-deploy"** — session log line 46.
4. **FB-002 (ROOT CAUSE IDENTIFIED, NOT FIXED):** Correctly identified as dependent on FB-016 (photo_faces ID mismatch). Deferred to Session 130.

### Session 130 Claims
1. **FB-016 (FIXED):** 212 missing photo_faces rows backfilled. 82/125 CONFIRMED identities repaired. "0 CONFIRMED identities with missing faces (was 82)."
2. **identity_overrides startup read (FIXED):** Session 129 only removed the WRITE path; startup sync still READ from the table. Session 130 removed the read + truncated the table.
3. **Verification gate: ALL PASS** — 5 checks all marked PASS.

### Session 130 Assessment
- Listed FB-016 as shipped with evidence: reconciliation script passes, 0 missing faces.
- "Deferred: None. All 6 phases completed."
- Did NOT verify in browser that Esther's face appears tagged in the Dayton Ohio photo.

---

## What Was Actually Done

### Session 129 — Code Changes
1. **Commit 0930666:** Created `scripts/repair_duplicate_identities.py` (164 lines). Merged duplicate Esther identities in Supabase `identities` table. Fixed a stale test assertion. Did NOT modify photo_faces, did NOT modify app code.
2. **Commit 8fc34d6:** Removed override loading from `core/registry.py` `load_from_postgres()`. Removed `sync_identity_overrides()` calls from `app/main.py` `save_registry()`. Updated 3 tests.
3. **Commit c703555:** Added 5 structural invariant tests in `tests/test_data_layer_invariants.py`.

### Session 130 — Code Changes
1. **Commit 2caedbd:** Created `scripts/backfill_photo_faces.py` (242 lines). Added `PhotoRegistry.resolve_photo_id()` to `core/photo_registry.py` (+45 lines). Added 9 tests. Fixed a stale test assertion.
2. **Commit 547826e:** Removed identity_overrides read from `app/supabase_data.py` `sync_from_supabase_on_startup()`. Stubbed functions. Truncated table. Added 2 structural tests.
3. **Commits 0a1d2f7, d4b502e:** Health endpoint enhancement, reconciliation script, 6 more structural tests.

---

## Why the "Fix" Didn't Work (Analysis)

### Problem 1: The Merge Fixed Supabase, Not the Rendering

Session 129 merged the two Esther identities at the Supabase level (112 anchor_ids in the `identities` table). The session log says "Verified: Esther shows 112 faces on production." However, FB-002 was about a SPECIFIC FACE on a SPECIFIC PHOTO (10a7d40eb3bf94f7, Dayton Ohio group) being untagged. The 112-face verification checked the person page face count, not whether that specific face resolved to Esther on the photo page.

The root cause of FB-002 was **not** the duplicate identity merge. It was the photo_faces ID mismatch (FB-016): the photo page uses SHA256 IDs to look up faces, but photo_faces stores inbox-format IDs. This was correctly identified as a separate issue but conflated in the "verified" claim.

### Problem 2: Session 130 Backfilled Data, But Deployment Was Unclear

Session 130 created `scripts/backfill_photo_faces.py` and ran it to insert 212 missing rows. The log says "0 CONFIRMED identities with missing faces (was 82)" and the reconciliation script passes. However:

- The session log has **no mention of deployment**. No `git push`, no `railway deploy`, no smoke test URL.
- The assessment's "Next Session Should Verify" section explicitly says "Deploy to production and verify `/health` returns 200" and "Verify face overlays render on previously-broken photos" — acknowledging these verifications were NOT done.
- The backfill script writes to Supabase (so production data is updated), but the CODE changes (PhotoRegistry.resolve_photo_id()) require a deployment to take effect.

### Problem 3: Session 131 Deployed But Didn't Verify FB-002

Session 131 deployed (11/11 smoke tests pass) and did browser verification of "Landing, People, Photos, Compare, Estimate" — but **never checked the specific Dayton Ohio photo (10a7d40eb3bf94f7)** or any photo_faces rendering. The Esther Burd / FB-002 / FB-016 string does not appear anywhere in the Session 131 log. The smoke test verified page-level health, not face-level data integrity.

### Problem 4: Two Layers of Fix Required, Only One Verified

FB-002 required TWO things to be fixed:
1. **Data layer:** photo_faces rows must exist for all faces (Session 130 backfill)
2. **Code layer:** photo page must resolve both inbox and SHA256 IDs (Session 130 `resolve_photo_id()`)

The verification script (`data_reconciliation.py`) checks the data layer. Nobody verified the code layer in production — whether `resolve_photo_id()` is actually called in the photo page rendering path, and whether it correctly resolves the Dayton Ohio photo's faces to Esther's identity.

---

## Evidence Cited vs Reality

| Claim | Evidence Cited | Actual Verification |
|-------|---------------|---------------------|
| "Esther shows 112 faces on production" (S129) | Session log line | Likely checked person page face count, not photo overlay |
| "0 CONFIRMED with missing faces" (S130) | Reconciliation script output | Script checks Supabase data, not rendered UI |
| "All 5 reconciliation checks PASS" (S130) | Script output | Correct for data layer; does not test rendering |
| "11/11 smoke tests pass" (S131) | Deploy verification log | Smoke tests check page-level 200s, not face assignments |
| "Browser verified — Landing, People, Photos, Compare, Estimate" (S131) | Session log | Generic page checks, did not test specific photo |

---

## What Was Missing

1. **No browser verification of the specific photo.** Nobody navigated to `rhodesli.nolanandrewfox.com/c/fox-family/photo/10a7d40eb3bf94f7` and confirmed Esther's face shows a green border, name label, and person link.
2. **No end-to-end test.** No test verifies that a photo page renders face-identity assignments for photos with inbox-format IDs in photo_faces.
3. **Session 130 deferred deployment verification to Session 131.** Session 131 deployed but forgot to check FB-002/FB-016 specifically.
4. **The verification gate in Session 130 checked data, not rendering.** All 5 checks were data-level (Supabase queries), not UI-level.

---

## Root Cause Pattern

This is a repeat of **Lesson 131 (never claim fixed without production browser verification)** and **Lesson 97 (self-assessment must include visual verification evidence)**.

The pattern:
1. Root cause correctly identified
2. Data-level fix correctly applied
3. Code-level fix correctly written
4. Verification done at the wrong layer (Supabase queries instead of rendered UI)
5. "PASS" declared based on data check, not user-visible behavior
6. Specific photo/face never re-checked after the fix

---

## Proposed Lesson (154)

**Lesson 154: Data-layer fixes that affect UI rendering require browser verification of the SPECIFIC broken page, not just a reconciliation script.**

- **Mistake:** FB-002 (Esther Burd face untagged on Dayton Ohio photo) was declared fixed across Sessions 129-131 based on Supabase data reconciliation. Nobody navigated to the specific photo page to confirm the face overlay renders correctly.
- **Rule:** When a bug report names a specific page/photo/identity, the fix verification MUST include navigating to that exact page in production browser and confirming the specific visual behavior.
- **Prevention:** Add the specific URL to the verification gate checklist. Data reconciliation scripts are necessary but not sufficient — they verify data, not rendering.
