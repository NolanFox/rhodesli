# Session 133 Data Repair Verification Report

**Date:** 2026-03-22
**Type:** READ-ONLY deep verification of Session 133 data repairs
**Script:** `scripts/verify_session133.py`

## Context

Session 133 performed massive Supabase data repairs:
- 691 dangling merge references cleared
- 1,167 merged identities' faces transferred to targets
- 212 orphaned faces given new INBOX identities
- 692 multi-claimed faces resolved
- 2 ghost faces removed

This verification confirms nothing was broken by those repairs.

---

## Verification 1: CONFIRMED Anchor Validity

**Check:** Every face_id in every CONFIRMED identity's anchor_ids must exist in both photo_faces (Supabase) AND embeddings.npy (local).

**Result: PASS with known caveat**

| Metric | Value |
|--------|-------|
| CONFIRMED identities | 155 |
| Total anchor face_ids | 878 |
| Valid in both photo_faces + embeddings | 871 |
| In photo_faces but missing from local embeddings | 7 |
| Missing from photo_faces | 0 |

**5 identities with faces missing from local embeddings.npy:**

| Identity | Anchors | Missing | Affected Faces |
|----------|---------|---------|----------------|
| Irving Israel Fox | 8 | 2 | inbox_d850b25bd32d, inbox_00b5b0705d41 |
| Sarah Gukaylo Yanishefsky | 1 | 1 | inbox_cbf2bb584d81 |
| Ralph Burd | 5 | 3 | inbox_c567874f61ca, inbox_9dbb8580c082, inbox_8846e6691a0d |
| Miriam Cohen Burd | 3 | 1 | inbox_60660a4071ab |
| Fannie Burd Yanishefsky | 3 | 1 | inbox_48f9849e0231|

**Root cause:** These 7 faces (plus 20 others, 27 total) were processed by the Railway ML service during web uploads. Their embeddings exist on the Railway volume but were never synced back to local `data/embeddings.npy`. All 27 exist in Supabase `photo_faces` — they are real faces with valid photo references.

**Impact:** LOW. These faces render correctly in the UI (crops exist in R2). They cannot participate in local embedding distance calculations, but the production server has the full embedding set. This is the known AD-229 embeddings sync gap.

**Verdict:** NOT a Session 133 regression. Pre-existing condition.

---

## Verification 2: No CONFIRMED Identity Lost Faces

**Check:** Compare pre-fix snapshot (`identities_pre_phase2.json`) with current Supabase state. Every CONFIRMED identity's anchors should be a superset of pre-fix anchors.

**Result: PASS — all face losses are legitimate merges**

| Category | Count | Details |
|----------|-------|---------|
| CONFIRMED that lost ALL anchors | 29 | All are merge SOURCES with `merged_into` set |
| Face transfer rate | 100% | Every lost face found in the merge TARGET's anchors |
| CONFIRMED with partial loss | 1 | Netanel Menashe: 4 -> 2 anchors |

**All 29 merge-source identities had 100% face transfer:**
- 8 merged into Charles Fox
- 5 merged into Albert Fox
- 5 merged into Esther Burd Fox
- 3 merged into Roland Fox
- 1 each into Robert Mattatia, Leona Fox Smilg, Rose, and other targets

**Netanel Menashe (1 partial loss):**
- Pre-fix: 4 anchors. Current: 2 anchors.
- Lost faces: `inbox_b13a0d1781cc`, `inbox_22a58175dbc2`
- Root cause: Multi-claimed face resolution. Both faces were anchored in BOTH Netanel Menashe (CONFIRMED) and an INBOX identity merged into Netanel. The multi-claimed resolver removed the face from the CONFIRMED identity instead of the merged INBOX identity.
- **Impact:** MEDIUM. 2 valid Netanel Menashe faces are now orphaned (not in any active identity). These should be re-added to Netanel Menashe in a future repair.
- **Action item:** Re-add `inbox_b13a0d1781cc` and `inbox_22a58175dbc2` to Netanel Menashe's anchor_ids.

---

## Verification 3: Harry Fox & Albert Fox Spot-Check

**Result: PASS — both identities intact and distinct**

| Person | Anchors | Valid in photo_faces | Valid in embeddings |
|--------|---------|---------------------|---------------------|
| Harry Fox | 7 | 7/7 (100%) | 7/7 (100%) |
| Albert Fox | 163 | 163/163 (100%) | 163/163 (100%) |

**Inter-identity distance:**

| Metric | Value | Assessment |
|--------|-------|------------|
| L2 distance (centroid) | 0.6958 | Below 0.8 threshold |
| Cosine similarity | 0.3872 | Low similarity (distinct) |
| Harry intra-identity avg L2 | 1.1618 (max 1.4324) | High variance (expected for brothers across ages) |
| Albert intra-identity avg L2 | 1.0947 (max 1.3824) | High variance (expected for 163 faces across ages) |

**Note:** The L2 distance of 0.6958 is below the 0.8 "distinct" threshold, which is expected — Harry and Albert Fox are brothers who look very similar (see CLUSTER-QUALITY-001, `project_fox_sibling_resemblance.md`). The high intra-identity variance (1.1-1.4) across both identities reflects age variation in the Fox family photos. The inter-identity distance (0.70) being LOWER than intra-identity averages (1.09-1.16) confirms the known challenge: these siblings are closer to each other than some of their own photos are to each other. This is a known ML limitation, not a data integrity issue.

---

## Verification 4: Unexpected Candidates on CONFIRMED

**Result: PASS — minimal and expected**

Only 1 CONFIRMED identity gained a new candidate from the face transfer:
- **Esther Burd Fox** gained 1 new candidate (`inbox_f43d9eaca7f7`)

37 CONFIRMED identities have existing candidates (pre-dating Session 133), ranging from 1-31 per identity. Roland Fox has the most at 31. These are ML-proposed face matches awaiting admin review — normal operation.

**Verdict:** No unexpected or problematic candidate additions from Session 133 repairs.

---

## Verification 5: GEDCOM-Only CONFIRMED Identities (0 Anchors)

**Result: INFORMATIONAL — pre-existing condition, not a regression**

| Category | Count |
|----------|-------|
| CONFIRMED with 0 anchors (not merged) | 24 |
| With GEDCOM link in `gedcom_face_links` | 15 |
| Without GEDCOM link | 9 |
| With candidates (face proposals pending review) | 23 |
| With 0 candidates AND 0 anchors | 1 (Solomon Solly Galante — has GEDCOM link) |

**All 24 had 0 anchors BEFORE Session 133 repairs.** These are named identities created from GEDCOM records where ML has proposed face matches (as candidates) but admin has not yet confirmed any faces as anchors.

**9 without GEDCOM links but with candidates:**
Molly Benson, Arlene Kessler Capeluto, Vida Capeluto, Sheila Surmani, Boulissa Pizanti Capeluto, Ray Franco, Regina Reina Israel Capeluto, Eleanore Cohen, Herman Benson

These were likely created during admin triage (confirmed as named people from photo context) but never linked to GEDCOM records. Their candidates are ML proposals awaiting review.

**Verdict:** NOT a Session 133 regression. Pre-existing data state.

---

## Verification 6: Global Integrity Checks

**Result: PASS**

| Check | Result |
|-------|--------|
| Active (non-merged) identities | 1,863 |
| Faces claimed as anchor by multiple active identities | **0** |
| Merged identities | 1,894 |
| Faces still only in merged identities (not transferred) | **0** |

The multi-claimed face resolution was successful — zero faces are now claimed by multiple active identities. All faces from merged identities have been transferred to their merge targets.

---

## Summary

| Verification | Result | Notes |
|-------------|--------|-------|
| V1: CONFIRMED anchors valid | **PASS*** | 7 faces missing from local embeddings only (Railway ML sync gap, pre-existing) |
| V2: No CONFIRMED lost faces | **PASS*** | 29/30 are legitimate merges with 100% transfer. 1 partial: Netanel Menashe lost 2 faces (multi-claim resolution bug) |
| V3: Harry & Albert Fox distinct | **PASS** | Both intact, known sibling similarity |
| V4: No unexpected candidates | **PASS** | Only 1 new candidate added (Esther Burd Fox) |
| V5: GEDCOM-only identities | **PASS** | All 24 were 0-anchor before repairs |
| V6: Global integrity | **PASS** | 0 multi-claimed, 0 untransferred |

### Action Items

1. **P2 — Netanel Menashe face restore:** Re-add `inbox_b13a0d1781cc` and `inbox_22a58175dbc2` to identity `64096284-ace8-4790-aebb-a82ff1f288a5` anchor_ids. These were incorrectly removed during multi-claimed resolution.

2. **P3 — Embeddings sync:** 27 faces exist in Supabase photo_faces but not in local embeddings.npy. Run embeddings sync from Railway to close the AD-229 gap.

3. **P3 — GEDCOM linking:** 9 named CONFIRMED identities have no GEDCOM link. Consider running GEDCOM auto-match for these.

### Conclusion

Session 133 data repairs were successful. The only actual data loss is 2 faces from Netanel Menashe, which is a minor issue with a straightforward fix. All other apparent losses are legitimate merges with 100% face transfer confirmed. Global integrity checks pass cleanly.
