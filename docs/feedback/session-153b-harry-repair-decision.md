# Session 153b Phase 7 — Harry Fox Anchor Repair Decision

**Session:** 153b
**Date:** 2026-04-19
**Decision:** **DO NOT EXECUTE.** Blockers remain.

---

## Pre-conditions status

Per the Session 153b prompt Phase 7, ALL must be true before mutation. Current state:

| # | Pre-condition | Status | Blocker detail |
|---|---|---|---|
| 1 | 3009 = Bessie Fox validated at POSSIBLE+ across 3 sources | **PARTIAL** | Synthesis says POSSIBLE trending WEAK (~40%). 2 sources POSSIBLE (Claude multimodal, Opus), 2 WEAK (ML, Claude direct). Codex (1C) still running at wrap. |
| 2 | Face IDs F + G verified (`1fea75` vs `2bc31` discrepancy resolved) | **NOT DONE** | Codex audit said `inbox_1fea75...`; Session 153 breakthrough doc said `inbox_2bc31a40c34a`. No reconciliation attempted in 153b. Hard blocker. |
| 3 | Replacement identity label decided | **DONE** (specified) | Per Opus audit: "Belle Isle Conservatory Young Man c.1917–1918" (conservative). User retains veto. |
| 4 | Backup snapshot saved | NOT DONE | Would be required. |
| 5 | Audit_log metadata drafted | NOT DONE | Would be required. |
| 6 | Structural tests pass | NOT RUN | Would be required. |

**Gate: 1 DONE, 1 PARTIAL, 4 NOT DONE → DO NOT EXECUTE.**

## Why the repair should not proceed in 153b

1. **Bessie hypothesis is not at POSSIBLE+ on ≥3 sources.** The prompt's gate threshold isn't met. Repairing Harry without first establishing the companion Bessie hypothesis means we'd be making data changes based on a half-completed investigation — the exact failure mode session 153 already suffered once.

2. **Face-ID discrepancy is a potential data-corruption vector.** If we transfer the "wrong" face IDs to a new identity we could either (a) leave the real offending anchors untouched and move innocent anchors, OR (b) move the right faces but from the wrong list position. Either is a silent destructive mutation. Lessons 153–156 all warn against this class of bug.

3. **The center-man identification is not positive.** The Phase 2 honest hypothesis table shows 3 distinct POSSIBLE candidates and 1 rejected. The "Harry Isaackovitz" label that Session 153 proposed was **not triangulated** — only "NOT Harshel" was triangulated. Using the non-triangulated label for a production mutation re-commits the exact error Session 153b was created to correct.

4. **Reversibility is imperfect.** Even with snapshots, un-merging is destructive of downstream state (embeddings cache, ML proposals, cross-batch matches). Session 142 documented 692 secondary multi-claimed faces created by one un-merge. We don't want to undertake that class of cleanup speculatively.

## What to do instead (follow-up work)

### Priority 1 — Resolve the face-ID discrepancy
Next session (154 or continuation) should grep `inbox_1fea75` and `inbox_2bc31` against:
- `data/embeddings.npy` entries (which face ID actually exists?)
- Supabase `photo_faces` rows for photo 02068
- The current Harry Fox identity's `anchor_ids` JSONB array
- Codex audit output vs breakthrough doc — one of them is wrong; identify which

### Priority 2 — Strengthen or falsify the Bessie hypothesis
- Search Ancestry tree 162873127 for a 1910s Bessie Fox / Bessie Isaackovitz photo (user task)
- Check whether 3009 appears in the other 2 Belle Isle Conservatory frames (91b6f6b296e93a60, 01659). If yes, that's multi-frame triangulation.
- Test kinship hypothesis: does 3009 have systematic proximity to OTHER Bessie-adjacent identities (her daughter Leona appeared at rank 15 d=1.24)?

### Priority 3 — Improve the repair plumbing (PRD-062 — already written)
The PRD-062 anchor inspector UX would let admin perform this repair without a Claude Code session. Implementation is priority P1 for data integrity reasons (Lesson 153–156 recurring category). If the PRD gets built out before the next Fox-family identification session, the Harry repair can be done in-product in <3 clicks with full audit trail.

### Priority 4 — Defer repair indefinitely, document as known-issue
The Harry Fox identity currently contains 2 face anchors that are NOT Harry Fox. This is a real data-integrity defect. But:
- It's a ~2-person misassignment in a 2000-identity archive (0.1% error rate in the affected identity)
- Admin action to fix it is low-priority vs COMMUNITY-001 or PRD-059 Phase 4
- Impact: 3 Belle Isle Conservatory faces (the 1917 group photo + 2 other frames) show a "Harry Fox" label that's wrong. Public-facing mislabel.
- Partial mitigation: add a "See context for caveats" note on the Harry Fox person page referencing this doc. No data mutation, information-only.

## Breadcrumbs
- Phase 1 synthesis: `docs/feedback/session-153b-bessie-validation.md`
- Phase 2 hypothesis table: `docs/feedback/session-153b-center-man-honest.md`
- Opus audit: `docs/feedback/session-153b-opus-audit.md`
- Multimodal audit: `docs/feedback/session-153b-claude-multimodal-bessie.md`
- Original breakthrough doc (over-claimed): `docs/feedback/session-153-harry-isaackovitz-breakthrough.md`
- PRD-062 (anchor repair UX): `docs/prds/062_anchor_inspector_and_repair_ux.md`
