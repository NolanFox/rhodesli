# The "Worth Opening" Rubric

**Purpose.** The binary acceptance test every nightly Morning Mystery artifact must pass before it is
allowed to notify Nolan. Written in Session 171 (W1-S1) against the first hand-built case
(`morning-mystery-belle-isle/`). One page, on purpose. If a nightly artifact fails ANY gate below,
it is NOT worth opening — hold it, degrade it, or throw it back to the evidence loop; do not notify.

**The one-line test:** *Would a busy person who loves this work feel their 15 minutes were repaid?*

---

## Part A — Hard gates (ALL must be YES, else DO NOT SHIP the case)

1. **Real, single case.** Exactly one case; one subject or one tightly-scoped question. Not a digest.
2. **Immutable evidence packet.** The artifact carries a packet of numbered evidence IDs, hashed in a
   manifest. The reviewer can see every input the models saw.
3. **Every claim is cited.** Each atomic claim in every verdict cites ≥1 evidence ID. A verdict with
   an uncited factual claim fails.
4. **≤3 requested decisions.** The case asks Nolan for at most three concrete calls, each answerable
   from the evidence on the page.
5. **Sealed verdicts, ≥2 independent investigators.** At least two models investigated independently;
   their conclusions are sealed (hidden until Nolan makes his own call, in play-first mode).
6. **A genuine open question exists.** The case is actually unresolved — the matcher/evidence does not
   already settle it. (If ML already confidently answers it, it is a confirmation task, not a mystery.)
7. **No fabricated identification.** No verdict asserts a positive face ID to a person with no
   reference face. "Consistent with / cannot be excluded" is allowed; "is" is not.
8. **Zero writes to confirmed data.** Preparing the case mutated nothing in the confirmed identity set.
9. **Cost under cap.** The case was prepared within the $2/night model budget.

## Part B — Value gates (≥3 of 5 must be YES for "worth opening" = TRUE)

10. **A decisive lever is named — specifically and obtainably.** The artifact names the single
    cheapest piece of missing evidence that would resolve the case AND it is concrete: a specific
    artifact (a named record/photo/caption) or a specific person/holder to ask. A generic lever
    ("find an album caption," "ask the family") with no named target FAILS this gate — otherwise
    "abstain + boilerplate lever" is a degenerate strategy that passes forever while the ledger never
    moves. (Anti-degeneracy guard for the abstention path — Fable review, Session 171.)
11. **A real contradiction is surfaced, not buried.** Where sources disagree (e.g. a stale DB location
    vs. the research), the artifact shows the conflict beside the claim rather than silently picking one.
12. **The models disagree OR converge for visibly different reasons.** The bake-off has signal — the
    reveal will teach Nolan something about the models or the evidence, not just repeat one answer.
13. **A next action is one tap away.** Accept / correct / request-witness / drop-candidate — the
    decision Nolan makes writes straight back to the identity or the corpus.
14. **It advances the ledger.** The case plausibly moves at least one of the six counters (cases
    advanced · accepted claims · identities confirmed/corrected · photos linked · witness answers ·
    $/accepted claim) — even an abstention that names the witness to ask counts.

## Part C — Abstention is a first-class PASS (explicit, so the loop never punishes caution)

An **ABSTAIN** verdict is "worth opening" when it passes all of Part A AND Part B gate 10 (names the
decisive missing evidence). "No defensible identification; here is the one photo that would settle it"
is a *good morning*. Score abstaining runs on cost-per-reviewed-case, never as a failure. Track
unsupported-claim rate and overturned-conclusion rate — a confident wrong answer is worse than a
well-argued abstention.

## How to apply
- Nightly runner computes gates 1-9 (Part A) and 10-14 (Part B) mechanically where it can, and marks
  the rest for the artifact author. **Ship only if:** Part A all YES **and** Part B ≥3/5.
- The 30-day pilot bar counts a dossier as "worth opening" iff this rubric returns TRUE. Target:
  ≥3 of the first 6 reviewed dossiers pass.

---
*First application: `morning-mystery-belle-isle/` — **Part A: 9/9 YES · Part B: 4/5 YES** →
**WORTH OPENING = TRUE.** Honest scoring (Fable review, Session 171): gate 13 (one-tap write-back) is
scored **NO** for the hand-built artifact — it is a static file whose adjudication is captured by hand;
the write-back is a nightly-runner capability, not something this artifact does. The four Part-B YES:
gate 10 (lever names a specific holder — "whoever holds the Charles Fox album"); gate 11 (contradiction
E9 vs E10/E11 surfaced beside the claim); gate 12 (models converge on ABSTAIN+DROP but **diverge on
family-inference strength** — Gemini "likely friend/relative" vs Sol "cannot distinguish from
non-family" — **and on the cheapest lever** — a labeled photo vs an album caption); gate 14 (drops a
candidate + corrects a location = two ledger deltas even under a double-abstain). Gate 9 cost is
recorded in the artifact footer (≈$0.14).*
