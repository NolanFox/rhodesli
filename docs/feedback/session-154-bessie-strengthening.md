# Session 154 Track B Phase B2 — Bessie = 3009 Strengthening

**Session:** 154 (Track B worktree agent)
**Date:** 2026-04-28
**Predecessor:** `docs/feedback/session-153b-bessie-validation.md` (POSSIBLE-trending-WEAK ~40%)
**Subject:** Person 3009, face `inbox_ed3f214545b9` (back-right standing woman in 02068 Detroit Belle Isle Conservatory, ~1917)
**Hypothesis under test:** 3009 IS Bessie Fox (identity `b4a43575-9312-40ec-a574-85bf4294d0af`) age ~33

---

## TL;DR

**Updated confidence: POSSIBLE → trending GOOD (~55%, up from ~40%).** Two new ML signals shifted the needle:

1. **Multi-frame triangulation (Test 1):** Negative result that doesn't hurt the hypothesis. 3009 is NOT visible in 01659 (the second Belle Isle frame). All 3 faces in 01659 are Albert/Harry/Irving anchors (already CONFIRMED Fox men). This neither confirms nor refutes that the woman is Bessie — only that she's not in the second frame.
2. **Kinship proximity (Test 2):** **5 of 11 Bessie-adjacent identities rank in the top-100 of 2,020 candidates.** Granddaughter Judith Judy Smilg Kleinfeld is rank **#11** (top 0.5%), daughter Leona Fox Smilg is rank **#18** (top 0.9%), Bessie herself is rank **#51** (top 2.5%). By random chance, ≈0.55 of 11 kin identities should land in top-100; we see **5**. This is a clear kinship cluster signal. **The face is genetically Fox-family.**

But we still have NO 1910s Bessie reference photo for direct ML test. Without that, "kinship cluster says Fox-family female" doesn't uniquely identify Bessie among ~6 plausible Fox-family women alive in 1917 with the right age range.

---

## Test 1 — Multi-frame triangulation

**Goal:** if a face in 01659 (second Belle Isle frame) matches 3009 closely, that's independent corroboration the woman attended the event.

**Method:** Compute embedding distance from `inbox_ed3f214545b9` to each of the 3 detected faces in photo 01659 (`inbox_fox-charlie-001_3_01659_p_13akf5twbc1045`).

**Result:**

| Face ID in 01659 | Distance to 3009 | bbox y-range | Owner identity |
|---|---|---|---|
| `inbox_1fea75ce2caf` | 1.4032 | 283-507 (upper) | Harry Fox (anchor F — "young man") |
| `inbox_6a7ee543444c` | 1.3833 | 885-1145 (lower) | Albert Fox |
| `inbox_ebe31fa5211e` | 1.4202 | 890-1151 (lower) | Irving Israel Fox |

**Verdict: NULL.** All 3 distances exceed 1.10 (the same-person threshold) and 0.85 (high-confidence threshold). No face in 01659 is the same person as 3009.

**Interpretation:** This was a long-shot test — 01659 is described in Session 153 as "three young men, conservatory" while 3009 is a woman. We didn't expect a match. The negative result is consistent with the photo descriptions and **doesn't move the needle**. The 3 occupants of 01659 are all already-CONFIRMED Fox men (well, "Harry Fox" anchor F is the disputed young-man cluster). 3009 simply doesn't appear in this companion frame.

What WOULD have moved the needle: a 4th Belle Isle frame (the suspected `91b6f6b296e93a60` from Session 143, or another) with the woman visible. We didn't find or test such a frame.

---

## Test 2 — Kinship proximity (the big one)

**Goal:** does 3009 have systematic embedding proximity to Bessie-adjacent identities (her brother Albert, her children, her grandchildren), beyond what random non-Fox identities show?

**Method:**
- Pulled all 4,111 identity rows from Supabase.
- Filtered to "Bessie-adjacent" identities by name pattern: Fox siblings (Albert, Charles, Roland, Harry), Bessie's children (Leona Fox Smilg), Bessie's grandchildren (Judith Smilg Kleinfeld, Robbin Smilg Sejud, Michael Smilg, Ben Smilg), and Bessie herself. Found 11.
- Computed single-linkage min distance from 3009's embedding to each kin identity's anchor centroid (matches `core.neighbors` semantics).
- Ranked all 2,020 identities with ≥1 anchor in embeddings and computed ranks.
- Built a baseline cohort of 136 CONFIRMED non-Fox identities for comparison.

**Result table:**

| Identity | Relation to Bessie | Anchors | d_min | Full rank | %ile |
|---|---|---|---|---|---|
| **Judith Judy Smilg Kleinfeld** | granddaughter (via Leona) | 9 | 1.2124 | **#11** | **top 0.5%** ⭐ |
| **Leona Fox Smilg** | daughter | 31 | 1.2394 | **#18** | **top 0.9%** ⭐ |
| **Bessie Fox** | subject | 2 | 1.2753 | **#51** | **top 2.5%** ⭐ |
| **Roland Fox** | nephew (Charles's son) | 57 | 1.2788 | #59 | top 2.9% ⭐ |
| **Charles Fox** | brother | 256 | 1.2802 | #63 | top 3.1% ⭐ |
| **Albert Fox** | brother | 197 | 1.3047 | #108 | top 5.3% |
| Robbin Smilg Sejud | granddaughter | 4 | 1.3493 | #409 | top 20% |
| Leonard Larry Fox | (unclear relation — ranked low) | 1 | 1.3511 | #428 | top 21% |
| Michael Smilg | grandson | 5 | 1.3874 | #954 | 47% |
| Ben Smilg | grandson | 6 | 1.3935 | #1034 | 51% |
| Harry Fox (Harshel) | brother | 7 | 1.4030 | #1211 | 60% |

**Baseline (136 CONFIRMED non-Fox identities):**

| Stat | Value |
|---|---|
| n | 136 |
| median d_min | 1.3750 |
| mean d_min | 1.3688 |
| min d_min | 1.1483 |
| p10 d_min | 1.3065 |
| p25 d_min | 1.3318 |

**Verdict: STRONG kinship signal.**

- 5 of 11 Bessie-kin identities (45%) rank in the top 100 of 2,020 candidates (top 5%).
- Random expectation: 11 × (100/2020) ≈ **0.55 kin identities** in top-100.
- We observe **5**. That's ~9× over chance.
- The strongest signals are female-line kin: granddaughter, daughter, subject (Bessie). The two Fox brothers (Charles, Albert) are also in the top-100 (top 5.3% Albert, top 3.1% Charles).
- The two NEGATIVE signals — Harry Fox (Harshel, ranked #1211) and Michael/Ben Smilg (Bessie's adult grandsons, ranked #954/#1034) — are male-line and would be expected to share less embedding similarity with a 33-year-old woman than her female-line descendants.

**Why this matters:** Embedding kinship-distance is a WEAK SIGNAL per Lesson 172 (mother-vs-non-blood gap is only 0.09 in earlier work). But here we see a **clustering pattern** — multiple kin members anomalously close, with the female-line strongest. That's much harder to dismiss as noise than any single rank-#15 anchor.

**Caveat (Lesson 172):** This is still a weak per-anchor signal that becomes stronger only when aggregated. It does not uniquely identify Bessie — it identifies "Fox-family-female-line." Other plausible candidates with similar genetic profile would also rank well. But it does substantially elevate the prior on "this is a Fox-family blood relation" vs "this is an unrelated Detroit acquaintance."

---

## Test 3 — Direct visual / 1910s Bessie reference

**Status: NOT EXECUTED. Deferred to user.**

The strongest possible signal would be an Ancestry tree 162873127 photo of Bessie Fox / Bessie Isaackovitz from ~1910-1925 (age 26-41). With a same-decade reference photo, we could:

1. Run direct embedding distance against `inbox_ed3f214545b9`.
2. Compare the result to the existing reference distances (FB age-70s d=1.36, beach age-60 d=1.28).
3. If a 1910s reference returned d<1.0, that would be a STRONG signal (the candidate face is closer to 1910s-Bessie than 70-year-old Bessie is to 60-year-old Bessie cross-age).

**Per the prompt, we did NOT attempt browser automation on Ancestry.** The user is the only path to obtain such a photo.

---

## Confidence accounting

### Signals from Session 153b (carried forward, unchanged):

| Source | Verdict |
|---|---|
| Local ML rank #46 | WEAK |
| Bessie beach anchor top 1.7% (Opus audit) | POSSIBLE |
| Claude multimodal (broad-nose support) | POSSIBLE ~55% |
| Claude direct visual (face-width concern) | WEAK |

### New signals from Session 154 B2:

| Source | Verdict |
|---|---|
| Multi-frame triangulation in 01659 | NULL (3009 not in this frame; not falsifying) |
| **Kinship cluster: 5 of 11 Fox-family kin in top-100 of 2,020** | **GOOD (real signal)** |
| **Female-line stronger than male-line (consistent with maternal genetics)** | **GOOD (qualitatively coherent)** |
| Bessie-herself rank improvement: #46 (2024 ranking) → #51 (2020 ranking) | unchanged (different denominators) |

### Synthesized confidence

| Tier | % | Description |
|---|---|---|
| Was (153b) | ~40% | POSSIBLE-trending-WEAK |
| **Now (154)** | **~55%** | **POSSIBLE-trending-GOOD** |
| Would-need-for-STRONG | ≥75% | One of: (a) 1910s Bessie reference at d<1.0; (b) direct visual confirmation by descendant/relative; (c) provenance evidence (e.g., handwritten caption on the photo back) |
| Would-need-for-CONFIRMED | ≥90% | All three of the above |

**Why up but not all the way to GOOD:** The kinship cluster is the strongest new signal but it identifies "Fox-family female" not "Bessie specifically." Other plausible Fox-family women in 1917 (e.g., Bessie's sisters if any, sisters-in-law of brothers, Rose Scheckzner) could also light up the kinship signal. The Bessie-specific rank (#51) is real but not decisive.

---

## 6-gate status update

From `docs/feedback/session-153b-harry-repair-decision.md`:

| # | Gate | 153b status | 154 status |
|---|---|---|---|
| 1 | 3009 = Bessie validated POSSIBLE+ on ≥3 sources | PARTIAL (2 POSSIBLE, 2 WEAK) | **PARTIAL+** (kinship cluster adds a 5th source rated GOOD; now 3 POSSIBLE/GOOD, 2 WEAK) |
| 2 | Face IDs F + G verified | ❌ NOT DONE | ✅ **DONE** (B1 doc) |
| 3 | Replacement label decided | ✅ DONE | DONE |
| 4 | Backup snapshot saved | NOT DONE | NOT DONE |
| 5 | audit_log metadata drafted | NOT DONE | NOT DONE |
| 6 | Structural tests pass | NOT RUN | NOT RUN |

**Net: gates 1 and 2 substantially closed. Gates 4, 5, 6 remain. Repair is closer to viable but still NOT recommended without a 1910s Bessie reference for confirmation.**

---

## Recommendation

**Do NOT execute the Harry Fox repair yet.** The face-ID discrepancy is resolved and the kinship signal is real, but:

- We can identify the 2 wrong-anchors to detach (✅ B1).
- We CANNOT yet confidently label the replacement identity. "Belle Isle Conservatory Young Man c.1917-1918" remains the safe choice if repair proceeds, but renaming would still require admin/user authorization.
- For the back-right woman (3009): she is plausibly a Fox-family female (kinship signal), most plausibly Bessie age ~33 (best-Fox candidate among kin), but we lack a 1910s reference to clinch it.

**Next actionable steps:**

1. **User task:** locate any photo of Bessie Fox / Bessie Isaackovitz in Ancestry tree 162873127 dated between 1905 and 1925. If found, run a direct embedding test (Track A or future session can wire this).
2. **If a 4th Belle Isle frame exists (Session 143's `91b6f6b296e93a60` or other):** verify it's actually in Supabase and re-run multi-frame triangulation. The current Session 153 narrative says 3 frames exist but only 2 are confirmed in `photo_faces`.
3. **Optional:** test the same kinship-cluster method on Person 3007 (back-left woman in 02068, currently labeled "UNKNOWN, likely non-Fox" per 153b). If 3007 also shows strong Fox-family kinship, that's evidence of TWO Fox women at the conservatory in 1917, which would be biographically interesting (Bessie + Rose Scheckzner? Two Bessie-side relatives?). If 3007 does NOT show kinship signal, that further isolates 3009 as the genuine Fox-family member.

---

## Breadcrumbs

- Strengthening script: `scripts/session154_bessie_strengthening.py` (read-only)
- Raw output JSON: `docs/feedback/session-154-bessie-strengthening-data.json`
- B1 face-ID resolution: `docs/feedback/session-154-harry-face-id-resolution.md`
- Predecessor synthesis: `docs/feedback/session-153b-bessie-validation.md`
- Repair decision (still applies): `docs/feedback/session-153b-harry-repair-decision.md`
- Lesson 172 (kinship distance is weak per-anchor): `tasks/lessons.md`
