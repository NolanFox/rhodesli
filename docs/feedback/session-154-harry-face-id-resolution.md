# Session 154 Track B Phase B1 — Harry Fox Face-ID Discrepancy Resolution

**Session:** 154 (Track B worktree agent)
**Date:** 2026-04-28
**Predecessor:** `docs/feedback/session-153b-harry-repair-decision.md` (Phase 7 blocker #2)
**Status:** RESOLVED. Codex audit was correct; breakthrough doc had a typo.

---

## TL;DR

The two contested face IDs from Session 153b's repair decision:

| Source | Face F (01659) | Face G (02068) |
|---|---|---|
| Session 153 breakthrough doc | `inbox_2bc31a40c34a` ❌ | `inbox_e507a54f204a` ✓ |
| Codex audit / Session 153 verification doc | `inbox_1fea75ce2caf` ✓ | `inbox_e507a54f204a` ✓ |

**Verdict:** Codex was correct. **`inbox_2bc31a40c34a` does not exist anywhere in the system** — neither in `data/embeddings.npy` nor in Supabase `photo_faces`. The breakthrough doc itself flagged the IDs as "to be verified against `docs/feedback/session-153-harry-verification.md`" — but that verification was never executed. The verification doc, written first, had the correct ID (`inbox_1fea75ce2caf`).

The two anchors that should be detached for the Harry repair are:

1. **`inbox_1fea75ce2caf`** — face F, photo 01659 Belle Isle Conservatory (3 young men, center)
2. **`inbox_e507a54f204a`** — face G, photo 02068 Detroit Belle Isle Conservatory group (center seated man)

---

## Evidence (script output: `scripts/session154_resolve_harry_face_ids.py`)

### Step 1 — Embeddings.npy presence

Loaded 3,285 embedding entries; 2,991 distinct inbox-style face IDs.

| Contested prefix | Hits | Result |
|---|---|---|
| `inbox_1fea75` | 1: `inbox_1fea75ce2caf` | Real face. |
| `inbox_2bc31a40c34a` | 0 | **Does not exist.** |

### Step 2 — Detroit photo 02068 face roster (6 faces)

`photo_id = inbox_fox-charlie-001_204_02068_p_13akf5twbc3600`. Bbox values were null in `photo_faces` (Supabase) but present in `embeddings.npy`:

| Face ID | bbox `[x1,y1,x2,y2]` | Quality | Det |
|---|---|---|---|
| `inbox_e507a54f204a` | `[783.2, 272.9, 906.6, 427.4]` | 27.73 | 0.883 |
| `inbox_c0710382a050` | `[475.8, 321.9, 601.8, 490.8]` | 27.27 | 0.883 |
| `inbox_b87b53e1ee20` | `[1067.8, 296.0, 1196.5, 470.4]` | 26.22 | 0.877 |
| `inbox_d4a2ab25ed8e` | `[742.0, 41.0, 844.2, 162.7]` | 23.00 | 0.839 |
| `inbox_ed3f214545b9` (3009 / Bessie hypothesis) | `[925.9, 58.2, 1040.4, 197.9]` | 23.39 | 0.791 |
| `inbox_f9b62bf22772` | `[1726.6, -37.8, 1802.3, 55.4]` | 17.34 | 0.518 |

By position (`y` ≈ 273-491 = front row seated; `y` ≈ 41-198 = back row standing), the **front-row seated** trio is `e507a54f204a` (center, x=783-906), `c0710382a050` (left, x=476-602), and `b87b53e1ee20` (right, x=1068-1196). The center seated face is therefore **`inbox_e507a54f204a`** — confirmed as Harry anchor G.

### Step 3 — Photo 01659 face roster (3 faces)

`photo_id = inbox_fox-charlie-001_3_01659_p_13akf5twbc1045`:

| Face ID | bbox |
|---|---|
| `inbox_1fea75ce2caf` | `[513.8, 282.7, 691.1, 506.6]` |
| `inbox_6a7ee543444c` | `[739.6, 884.8, 957.9, 1145.2]` |
| `inbox_ebe31fa5211e` | `[184.0, 890.5, 381.1, 1150.7]` |

Three faces, two clearly in the lower half (y ~885-1150 — likely seated below) and one in the upper half (`1fea75ce2caf`, y ~283-507 — likely standing/center, the "young man" labeled F). This matches Session 153 verification's description: "three young men posing, conservatory. Center man identical in face and clothing to G."

### Step 4 — Harry Fox identity anchor list

`identity_id = d74cb556-6d44-4288-ade3-1cc8fa2b45a6`, state `CONFIRMED`, 7 anchors:

| # | Face ID | Source photo | Notes |
|---|---|---|---|
| 1 | `inbox_c6abb86ff55b` | `IMG_2570.jpeg` (FB upload) | Likely real Harshel anchor |
| 2 | `inbox_5168f0722ca8` | `01811_p_13akf5twbc3558.jpg` | Likely real Harshel anchor |
| 3 | `inbox_16430d6022c1` | `01632_p_13akf5twbc0921.jpg` | Likely real Harshel anchor |
| 4 | `inbox_94bbb9408f42` | `01810_p_13akf5twbc3555.jpg` | Likely real Harshel anchor |
| 5 | `inbox_c66961c76a6a` | `02071_p_13akf5twbc3585.jpg` | Likely real Harshel anchor |
| 6 | **`inbox_1fea75ce2caf`** ⚠️ | **`01659` Belle Isle (face F)** | **WRONG — center young man, NOT Harshel.** Per audit_log `merge` entry 2026-03-18 from Person 2491. |
| 7 | **`inbox_e507a54f204a`** ⚠️ | **`02068` Detroit (face G)** | **WRONG — center seated young man, NOT Harshel.** Same cluster as F. |

`inbox_1fea75ce2caf` is in Harry's anchors. `inbox_2bc31a40c34a` is NOT in Harry's anchors and not anywhere else in the system.

---

## Why the typo happened (likely cause)

The Session 153 breakthrough doc (`session-153-harry-isaackovitz-breakthrough.md`, line 66) wrote:

> Anchors: F (`inbox_2bc31a40c34a` — 01659 face) + G (`inbox_e507a54f204a` — 02068-Detroit face). Full face IDs to be verified against `docs/feedback/session-153-harry-verification.md`.

Three things:

1. The breakthrough doc was **explicit that F's ID was unverified** ("to be verified against…"). The verification doc that already existed had the correct ID.
2. `inbox_2bc31a40c34a` is a 16-character (8-byte hex) string just like real face IDs — plausible-looking, easy to slip in.
3. No verification was performed in 153 OR 153b — Phase 7 of 153b explicitly flagged this as a hard blocker.

**Most likely:** the breakthrough doc author was working from memory or a paste from a different photo's face roster, didn't have the verification doc open, and didn't run a grep before publishing. The "to be verified" note was an honest hedge that became a 9-day open thread.

The breakthrough doc itself was already retracted in Session 153b (banner pointing to `session-153-corrective-analysis.md`). The typo is therefore an old artifact in a deprecated doc — not a live data corruption issue.

---

## Implications for Track D (repair plan)

If/when the Harry Fox repair proceeds (still gated on B2 Bessie strengthening + user authorization), the **2 face IDs to detach from Harry Fox identity `d74cb556-6d44-4288-ade3-1cc8fa2b45a6`** are:

1. **`inbox_1fea75ce2caf`** (was face F = 01659 center young man)
2. **`inbox_e507a54f204a`** (was face G = 02068 center seated young man)

**Replacement identity** (per Opus audit recommendation in 153b): label as *"Belle Isle Conservatory Young Man c.1917-1918"* — conservative, NOT "Harry Isaackovitz" (no reference photo exists; identity remains unconfirmed).

**Pre-repair gates from `session-153b-harry-repair-decision.md` STILL OUTSTANDING:**

| Gate | Was | Now |
|---|---|---|
| 1. Bessie hypothesis ≥ POSSIBLE on 3 sources | PARTIAL | See B2 output |
| 2. Face IDs F + G verified | ❌ NOT DONE | ✅ **DONE — this doc** |
| 3. Replacement label decided | DONE (conservative) | DONE |
| 4. Backup snapshot | NOT DONE | Still pending |
| 5. audit_log metadata drafted | NOT DONE | Still pending |
| 6. Structural tests pass | NOT RUN | Still pending |

Gate 2 is now closed. Gates 1, 4, 5, 6 remain.

---

## Data divergence flags (none found)

I specifically checked for the Lesson 142 / 144 / 147 split-brain patterns:

- ✅ All 7 of Harry's anchor face IDs DO have rows in Supabase `photo_faces` (no orphaned anchors).
- ✅ All anchor face IDs have entries in `data/embeddings.npy` with consistent bbox geometry.
- ⚠️ Bbox is NULL in `photo_faces` (Supabase) but populated in `embeddings.npy` (local). This is a **known harmless drift** (the bbox column was added to Supabase but never backfilled from npy). Not a Lesson 142 silent corruption — it's a write-time omission. Logging here in case Track A or Track D needs it.

No new red flags.

---

## Breadcrumbs

- Resolution script: `scripts/session154_resolve_harry_face_ids.py` (read-only, no mutations)
- Predecessor verification doc: `docs/feedback/session-153-harry-verification.md` (had correct IDs)
- Breakthrough doc with typo: `docs/feedback/session-153-harry-isaackovitz-breakthrough.md` (already retracted)
- Repair gate decision: `docs/feedback/session-153b-harry-repair-decision.md`
- 02068 audit_log evidence: face F came from merge of `b38fef24-858d-4b5f-95c0-c52c09a111f0` (Person 2491) on 2026-03-18 (route=`face_tag`)
