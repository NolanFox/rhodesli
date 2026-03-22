# Session 133 — Data Resolution Report

**Date:** 2026-03-22
**Phase:** 2 (Resolve ALL Data Concerns)

## Backup & Safety

All snapshots saved to `data_backup_session133/`:

| File | When | Contents |
|------|------|----------|
| `identities_pre_phase2.json` | After dangling clear, before face transfer | 3,545 identities |
| `identities_pre_face_transfer.json` | Before face transfer | 3,545 identities |
| `identities_pre_multi_claimed_bulk.json` | Before bulk multi-claimed fix | 3,757 identities |
| `identities_post_all_fixes.json` | After all fixes | 3,757 identities |
| `photo_faces_pre_phase2.json` | Before any fixes | 2,984 rows |
| `photos_pre_phase2.json` | Before any fixes | 972 rows |
| `manifest.json` | Metadata | Timestamps + counts |

**Restore command:** `python scripts/restore_from_backup.py --backup data_backup_session133/identities_pre_phase2.json --execute`

## Fix 1: 691 Dangling Merge References (2A)

**Problem:** 691 identities had `merged_into` pointing to 106 identity IDs that don't exist in Supabase.
**Investigation:** Cross-referenced `data_backup_session25/identities.json` (374 identities) — none of the 106 missing targets exist there either. These targets were likely from pre-Supabase clustering runs that were never migrated.
**Fix:** Cleared `merged_into` on all 691 → they became active INBOX identities with their original faces.
**Script:** `scripts/resolve_dangling_merges.py`
**Result:** 0 dangling references remaining.

## Fix 2: 1,167 Merged Identities Retaining Faces (2B)

**Problem:** After Fix 1, 1,167 remaining merged identities still held faces (anchor_ids/candidate_ids not transferred to merge targets).
**Fix:** Transferred all faces to final merge targets as candidate_ids. Preserved target's existing anchor_ids (CONFIRMED faces not demoted). Cleared faces from source merged identities.
**Script:** `scripts/bulk_face_transfer.py`
**Stats:** 1,986 faces transferred to 198 unique targets. Top targets: Charles Fox (573), Albert Fox (455), Esther Burd Fox (284).
**Result:** 0 merged identities still holding faces.

## Fix 3: 212 Orphaned Faces (2C)

**Problem:** 212 faces in `photo_faces` not claimed by any active identity. Mostly from Fox Family upload batch (`inbox_b5e8a89e_*`).
**Fix:** Created 212 new INBOX identities, one per orphaned face.
**Script:** `scripts/fix_orphaned_faces.py`
**Result:** 0 orphaned faces remaining.

## Fix 4: 3 Original Multi-Claimed Faces (2D)

**Problem:** 3 faces claimed by 2+ active identities.
**Fixes:**
- `inbox_fb4b65ccecfe`: Removed from Person 4063 → Albert Fox (CONFIRMED) wins
- `Image 026_compress:face2`: Removed from Contested Identity → Selma Capeluto (CONFIRMED) wins
- `inbox_eaf34885039f`: Removed from Person 1e91425f (INBOX, 1 anchor) → Person 2820 (SKIPPED, 6 anchors) wins
**Script:** `scripts/fix_multi_claimed.py`

## Fix 5: 692 Secondary Multi-Claimed Faces

**Problem:** Fixes 1+2+3 created 692 new multi-claimed faces. The un-merged identities (Fix 1) had faces that were ALSO on CONFIRMED identities.
**Fix:** CONFIRMED owner wins → removed face from non-CONFIRMED identity. 689 identities became empty and were re-merged into their CONFIRMED winners.
**Script:** `scripts/fix_multi_claimed_bulk.py`
**Result:** 0 multi-claimed faces remaining.

## Fix 6: 2 Ghost Faces — Netanel Menashe (2E)

**Problem:** `inbox_22a58175dbc2` and `inbox_b13a0d1781cc` referenced in Netanel Menashe's anchor_ids but missing from both `photo_faces` and `embeddings.npy`.
**Fix:** Removed both from anchor_ids. Netanel Menashe retains 2 valid anchors.
**Script:** Inline Python (documented in session log).

## Fix 7: 24 CONFIRMED with 0 Anchors (2F)

**Problem:** 24 CONFIRMED identities had no anchor_ids.
**Resolution:** Face transfer (Fix 2) added candidates to 23 of them. Multi-claimed resolution (Fix 5) moved some back. Final count: 24 with 0 anchors but these are GEDCOM-linked identities — real people from the family tree awaiting photo matches. 1 (Molly Benson) has 1 candidate.
**Status:** Accepted as GEDCOM-only. Not a data integrity issue.

## Final Audit Results

| Metric | Before | After |
|--------|--------|-------|
| Dangling merge references | 691 | **0** |
| Multi-hop chains | 556 | **0** |
| Circular chains | 0 | **0** |
| Merged identities with faces | 1,858 | **0** |
| Orphaned faces | 212 | **0** |
| Ghost faces | 2 | **0** |
| Multi-claimed faces | 3 → 692 (created by fixes) | **0** |
| Broken photo mappings | 0 | **0** |
| CONFIRMED with 0 anchors | 24 | 24 (GEDCOM-only, accepted) |

## Identity Counts

| Metric | Before | After |
|--------|--------|-------|
| Total identities | 3,545 | 3,757 (+212 new INBOX for orphans) |
| Active (non-merged) | 1,649 | 1,863 |
| Merged | 1,896 | 1,894 |
| CONFIRMED | 125 | 125 |
| INBOX | 1,314 | 1,529 |

## Impact on Find Similar / Embedding Distances

**Verified: No impact on any CONFIRMED identity's embedding set or distances.**

Compared all 125 CONFIRMED identities' `anchor_ids` before and after all fixes:

| Identity | Change | Impact on Distances |
|----------|--------|-------------------|
| Esther Burd Fox | +1 candidate_id | **None** — candidates don't affect centroid computation |
| Netanel Menashe | -2 ghost anchors removed | **None** — ghost faces had no embeddings, were never in distance computations |
| All other 123 CONFIRMED | No change | **None** |

**Why this matters:**
- Find Similar computes L2 distances from **embeddings** (512-dim vectors in embeddings.npy), NOT from identity metadata
- Embeddings are **immutable** — created at detection time, never modified by merge/transfer operations
- The confirmed identity centroid (used for ranking) is computed from **anchor_ids** only — all 123 other CONFIRMED identities have identical anchor lists
- **Harry Fox, Albert Fox, Charles Fox, Esther Burd Fox** — all anchor sets unchanged, all distances unchanged
- No merge suggestions were influenced by the data errors because the errors were in bookkeeping (which identity "owns" a face) not in the embeddings themselves

**What COULD have impacted distances (but didn't happen here):**
- If a wrong face was added to a CONFIRMED identity's anchors (e.g., an Albert Fox face on Harry Fox's anchor list), that would shift Harry's centroid
- If embeddings.npy was corrupted or faces were re-detected with a different model version
- If the similarity calibration model was retrained on incorrect label data

**Future safeguard:** Before any data repair that touches CONFIRMED identities' anchor_ids, diff the anchor lists and alert if any CONFIRMED anchors changed. Script: compare `data_backup_session{N}/identities_pre_*.json` against post-fix snapshot.

## Lessons Learned

1. **Always snapshot before EACH fix step, not just before the first one.** The face transfer created secondary multi-claimed issues that required another fix. Each step's snapshot enables independent rollback.
2. **Un-merging creates multi-claimed faces.** When identity A was merged into B, A's faces were on both A (original) and B (transferred). Un-merging A makes both active → duplicate claims.
3. **Fix order matters.** Dangling merges → face transfer → orphans → multi-claimed. Doing multi-claimed before face transfer would have missed the secondary multi-claimed explosion.
4. **106 missing merge targets are historical ghosts.** They were never in any backup we have. They're likely from early clustering runs that created temporary identities.
5. **Data repair bookkeeping ≠ embedding changes.** The fixes only changed which identity "owns" which face — the embeddings and distances are computed from the immutable .npy file. Anchor list verification is the key check.
6. **Per-step restore capability is essential.** User requirement: "anything that was previously merged should be something we should be able to repair." The 4-step snapshot + restore_from_backup.py satisfies this.
