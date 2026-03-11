# Session 97 Post-Followup Assessment

**Date:** 2026-03-11
**Author:** Codex
**Reviewed Gemini commit:** `36401b9` — `[gemini] docs(ml): add PRD-038 follow-up eval specifications`

---

## Verdict

Gemini's follow-up was useful and materially better than the first review on one
important dimension: exactness. The follow-up closed the main gap I had called
out, which was turning good qualitative feedback into:
- exact citations
- explicit metrics
- concrete rollout gates
- test-fixture ideas

I am keeping the artifact intact and treating it as part of the review record.

---

## What Improved

1. **Source precision**
   - The follow-up added direct links for the retrieve-rerank pattern and the
     active-learning literature, which brings the review much closer to harness
     standard.

2. **Dominant-identity bias became operational**
   - Gemini moved from "watch out for family overfit" to concrete metrics:
     - `dominant_lift_ratio`
     - `tail_recall_delta`
   - This is exactly the kind of eval language the implementation pass needs.

3. **Active-learning toxicity became testable**
   - The logical-consistency pre-flight check is a strong addition.
   - The reversibility boundary is also clearer now: labels stay reversible
     until a recalibration run successfully consumes them.

4. **Kinship-risk featurization got better**
   - Gemini's shift from a single boolean to a small feature family is the
     right move for a tree-based reranker.

---

## What I Adopted

These points are now integrated into the planning package:

1. Dominant / tail identity slice reporting in the eval plan
2. Provisional `dominant_lift_ratio` and `tail_recall_delta` gates
3. Reverted-label exclusion before recalibration export
4. Logical-consistency checks that can abort recalibration
5. Kinship-risk as a small feature family rather than a single boolean

Files updated:
- `docs/prds/SDD-038_longitudinal_face_modeling.md`
- `docs/prds/038_longitudinal/EVALUATION_AND_SAFETY.md`
- `docs/prompts/session-97-prompt.md`
- `docs/session_context/session-97-context.md`

---

## What Stayed Provisional

### 1. `dominant_lift_ratio < 3.0`

I adopted this as a **starting gate**, not a permanent truth.

**Why**
- The exact threshold should be revisited once Phase 0 reports the real dominant
  and tail slice sizes on the rebuilt assets.

### 2. Tail slice defined as `< 5` confirmed faces

I kept this as a **reasonable first cut**, not a fixed law.

**Why**
- It is sensible for the current archive size, but should remain adjustable if
  the confirmed set grows significantly before implementation.

### 3. Logical consistency as a recalibration blocker

I adopted the blocker, but with one caveat:
- conflicts must block recalibration for **unresolved active-learning labels**
  rather than attempting to infer a complete global truth from noisy data

**Why**
- The system should catch obvious contradictions without pretending the label set
  is a fully consistent graph at all times.

---

## Assessment Of Gemini's Work

This follow-up is stronger than the first review.

Strengths:
- more concrete
- better aligned to actual implementation needs
- improved citation discipline
- strong test-oriented thinking

Weaknesses:
- some thresholds remain heuristic
- fixture ideas are useful but still high-level rather than repo-specific

Overall:
- **reasoning quality:** high
- **implementation usefulness:** high
- **citation quality:** medium-high

---

## Do We Need More Gemini Work?

No more Gemini follow-up is required right now.

The remaining work is now better done locally in the PRD package and later in
the implementation session, because the open questions are mostly repo-shaped:
- exact fixture construction from Rhodesli data structures
- final threshold tuning after Phase 0 slice sizes are known
- precise placement of the audit/revert flow inside the existing review UX

If we ask Gemini again before implementation, it would likely have diminishing
returns unless a new architecture alternative emerges.
