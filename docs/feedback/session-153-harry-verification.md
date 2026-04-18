# Session 153 — Harry Fox Identity Anchor Verification

**Date:** 2026-04-18
**Trigger:** Codex P0 flag — Detroit 1918 photo face (`inbox_e507a54f204a`) apparent age (25-30) inconsistent with Harry Fox b.1882 (=age 35-36 in 1917-18).
**Scope:** Verify all 7 CONFIRMED anchors on identity `d74cb556-6d44-4288-ade3-1cc8fa2b45a6` (Harry Fox).
**Mode:** READ-ONLY. No data mutations.

## Verdict

**The identity `d74cb556-6d44-4288-ade3-1cc8fa2b45a6` ("Harry Fox") is NOT a single-person identity.** It contains **two distinct identity clusters** plus one outlier. The "hero" anchor labeled `Harshel Iosha Fox` (on a naturalization-style ID photo) and the Detroit-photo young man are **different people**. However the Detroit face-assignment hypothesis (it's *not* Harry, i.e. the man pictured in the primary anchor) is **CONFIRMED** — Codex was right.

## Anchor Roster

| # | Face ID | Photo | Est. Year | Apparent Age | Cluster | Visual Verdict |
|---|---------|-------|-----------|--------------|---------|----------------|
| A | inbox_c6abb86ff55b | `IMG_2570.jpeg` | 1940s ID card | ~50-55 | **Harshel** (primary) | Definitively labeled "Harshel Iosha Fox" on the photo itself (handwritten). Round-faced, glasses, thinning hair. **This is Harry b.1882.** |
| B | inbox_5168f0722ca8 | `01811_p_13akf5twbc3558.jpg` | 1940s-50s | ~60-65 | **Harshel-adjacent** | Older man with glasses, garden setting. Consistent with A aged ~10 years. Plausibly same person. |
| C | inbox_16430d6022c1 | `01632_p_13akf5twbc0921.jpg` | 1940s-50s | ~60-65 | **Harshel-adjacent** | Similar to B — older man, glasses, similar face shape. Plausibly same event/decade. |
| D | inbox_94bbb9408f42 | `01810_p_13akf5twbc3555.jpg` | 1940-55 | ~50 | **Harshel-adjacent** | Man with wife, suburban setting. Tall, slender build — NOT obviously the same man as A, but not clearly different. Ambiguous. |
| E | inbox_c66961c76a6a | `02071_p_13akf5twbc3585.jpg` | 1968-74 | ~65 (per Gemini) | **Outlier** | Elderly man at banquet. Photo dated LATER than Harry's death (bef. 12 Apr 1980 — possible but at the upper edge). Blurry color shot. Low visual confidence. |
| F | inbox_1fea75ce2caf | `01659_p_13akf5twbc1045.jpg` | 1915-25 | ~22-25 | **Young-man** | Three young men posing, conservatory. Center man identical in face and clothing to G. |
| G | inbox_e507a54f204a | `02068_p_13akf5twbc3600.jpg` | 1915-22 | ~22-25 | **Young-man (DETROIT)** | Center of five-person group shot, same conservatory, same outfit, same face as F. |

**Key observation:** Photos F (01659) and G (02068) show the **same three men** in **the same outfits** at the **same conservatory** — they are different frames of the same event. F and G are clearly the same young man (~25 yrs old).

## Internal Embedding Distance Matrix (L2, normalized)

```
            A       B       C       D       E       F       G
A:        0.000   0.960   0.996   1.118   1.103   1.418   1.431
B:        0.960   0.000   0.693   0.715   1.047   1.406   1.411
C:        0.996   0.693   0.000   0.901   1.108   1.399   1.404
D:        1.118   0.715   0.901   0.000   1.097   1.368   1.356
E:        1.103   1.047   1.108   1.097   0.000   1.432   1.405
F:        1.418   1.406   1.399   1.368   1.432   0.000   0.629
G:        1.431   1.411   1.404   1.368   1.405   0.629   0.000
```

### Cluster analysis

- **Cluster 1 (Harshel/older man):** A, B, C, D — mutual distances 0.69-1.12, mean ~0.92. Tight enough to be same-person over years.
- **Cluster 2 (Young man at conservatory):** F, G — d=0.629. Same person, same event.
- **Outlier:** E — >1.0 from everything. Likely a different person OR very degraded color photo.
- **Cross-cluster distance A-G = 1.431, A-F = 1.418** — these are near the threshold for completely different people (typical same-person L2 in PFE normalized space is <1.0; >1.3 is very high).

**F and G are NOT the same person as A/B/C/D.** They belong to a separate cluster that was incorrectly attached to Harry.

## Detroit Face (G) vs other Harry anchors

| Anchor | L2 Distance | Interpretation |
|--------|-------------|----------------|
| A (Harshel primary) | **1.431** | Different person (very high) |
| B (older 01811) | 1.411 | Different person |
| C (older 01632) | 1.404 | Different person |
| D (1940s couple) | 1.356 | Different person |
| E (banquet) | 1.405 | Different person |
| F (young man 01659) | **0.629** | SAME PERSON (matches G) |

## Merge History

- **9 identities merged INTO Harry** (all `Unidentified Person NNNN` in INBOX state). Merge-sources no longer have own anchors in registry.
- **1 audit_log `merge` entry** (2026-03-18, route=`face_tag`): face `inbox_1fea75ce2caf` (F, young man) merged in from source `b38fef24-858d-4b5f-95c0-c52c09a111f0` (Unidentified Person 2491). This is the merge that introduced the **young-man cluster** into Harry's identity.
- No audit record for G (inbox_e507a54f204a) specifically — it likely arrived as part of the same source-cluster merge or was added prior to the current audit schema.

## GEDCOM

- Harry Fox `@I132332580124@`: death `Bef. 12 Apr 1980`, no birth date in GEDCOM, parents family `@F3918@`.
- Birth year **1882** from user memory (1894 Minsk revision list) — not recorded in GEDCOM. Harry's age in 1917-18 = 35-36; in 1918 Detroit photo the man is 22-25 → age mismatch of ~10-13 years.
- No known late-life or labeled photo match confirmed beyond the `IMG_2570.jpeg` Harshel ID card.

## Root Cause Hypothesis

A merge during face_tag (2026-03-18) consolidated a young-man cluster (F + G + possibly others) into Harry's identity because:
1. The conservatory photo subjects happened to be in the Fox-family Charles collection (Dayton).
2. ML similarity flagged them as Fox-family based on surrounding photo co-occurrence, not direct facial match to anchor A.
3. Harry's anchor at the time (A) was a high-quality ID photo; the merge was done via `route=face_tag` which trusts operator tagging over embedding distance.

The young man in F/G is more likely **Harry's brother Albert Fox** (b. ~1896, age ~22 in 1918) or another young Fox sibling. This matches the pattern of Albert/Harry ML confusion already logged in `project_fox_sibling_resemblance.md`.

## Recommended Action (REVERSIBLE)

Do **NOT** act without user approval. Proposed repair plan:

1. **Snapshot** identity `d74cb556-6d44-4288-ade3-1cc8fa2b45a6` (full `anchor_ids`, `candidate_ids`, `version_id`) to `data/backups/session-153-harry-pre-repair.json`.
2. **Detach** faces F (`inbox_1fea75ce2caf`) and G (`inbox_e507a54f204a`) from Harry's anchors.
3. **Create** a new INBOX identity "Unidentified Young Man — Conservatory c.1918" with these 2 faces as anchors.
4. **Hold** anchor E (`inbox_c66961c76a6a` banquet) for user visual review — embedding outlier but could be aged Harry (1968-74 at age 86-92 is possible given death bef. 1980, but Gemini estimated age 65 not 86).
5. **Audit log** the repair with `metadata.reason = "session-153 embedding-cluster mismatch + visual verification"` and link to this report.
6. **Downstream impact** on Rose Scheckzner (Person 3009): since Harry is NOT in the Detroit photo, Rose (his wife) being present is also unsupported — her candidate score for Person 3009 must be re-weighted.

## AI Tool Usage
- **Tool:** Manual analysis (Python + PIL) + Claude Opus 4.7 vision
- **Agent type:** Independent fresh-context subagent
- **Task:** Verify Harry Fox anchor correctness
- **Findings:** 1 P0 (misassignment), 1 P1 (outlier E needs review)
- **Value assessment:** STRONG — quantitative embedding evidence + visual verification align. Would not have been caught without the cross-check.
