# Where we are, and what's next — Research Desk (read this first)

*Written 2026-07-14 for Nolan, after Session 171. Plain-language orientation, then your choices.*

---

## What we've done (the last two sessions)

You paused the app because the roadmap had drifted into platform/security/growth work and away
from the two things you actually love: **documenting Rhodes Jewish history** and **identifying
family in photos**. Session 170 replanned the whole thing into **The Research Desk** — the plan
lives at `docs/strategy/2026-07-reengagement/RESEARCH_DESK_PLAN.md` and it's the constitution.

The core product is the **Morning Mystery**: overnight the Desk prepares ONE unresolved
identification case, assembles the evidence, and two AI models investigate it *blind* and their
conclusions are **sealed**. In the morning you review the evidence, make your OWN call first, then
reveal the sealed verdicts and adjudicate. Your call is the ground truth. You're the detective;
the Desk does the legwork.

**Session 171 (last night) shipped the first three pieces of that:**

1. **The first real Morning Mystery** — a hand-built case for the "Belle Isle Conservatory young
   man" (the man mislabeled "Harry Fox," in two photos with Albert & Irving Fox). Both Gemini and
   Sol abstained and agreed to drop the weak candidate. **This is the artifact you have the link
   to** — open it, it's the whole point.
2. **The "worth-opening" rubric** — the binary test every future nightly case must pass.
3. **The case/run contract** (`investigation_runs` table) + **the evidence-packet assembler**
   (`packet_assembler.py`) — the machinery that will let the Desk build these cases automatically.
   Both are live-validated against the Belle Isle case.
4. **A security fix (R1)** — the family tree was leaking the private Fox genealogy into other
   communities; that's closed and verified live.

Everything is committed, pushed, tested, CI-green, and the site is healthy.

---

## Your 3 decisions/actions (only YOU can do these)

**A. Open the Morning Mystery and react.** → https://claude.ai/code/artifact/fbe5aebf-f672-4311-b64a-3f177faa2c55
This is the single most valuable thing. Note three things: did you **play-first** (make your calls
before revealing) or **reveal-first**? Roughly how many **minutes**? And **was it worth opening?**
Those answers are the first real data point for the whole 30-day plan.

**B. Rotate the `ML_SERVICE_TOKEN` on Railway.** A secret was committed to the repo long ago; it
should be rotated. This is a 2-minute Railway task I can't safely do for you: generate a new token,
set `ML_SERVICE_TOKEN` on BOTH the ML service and the main app, redeploy both. Ask me and I'll walk
you through it with `!` commands.

**C. Confirm the tree UX.** The R1 fix means the Fox family tree now lives at
`/c/fox-family/tree`, and the root/Rhodes tree is Rhodes-scoped (currently empty). That's the
intended fix, but tell me if you'd rather the Fox tree also show at the root.

---

## Pick your next session (say one of these to me)

- **"Run W1-S4"** — the next dev step, no involvement needed from you. Claude builds the exhaustive,
  constraint-aware face retrieval (search ALL ~3,000 faces for a case, not just a top-5 shortlist,
  with age/kinship constraints). Full spec ready at `docs/prompts/session-172b-w1s4-prompt.md`.
  *Good choice if you want to keep the engine moving while you're busy.*

- **"Let's do FB capture"** — the interactive session (needs you ~45-60 min at the desktop). You
  browse the Jews of Rhodes group and open posts; Claude captures each post + all comments +
  commenter names into your Rhodes corpus in one pass. This is your PRIMARY evidence supply line
  and the most engagement-dense session in the plan. *Good choice for an evening when you're around.*

- **"Build another Mystery"** — the plan says hold off on generating *more* cases until the review
  loop survives your review twice (so the first ones are trustworthy). But once you've reviewed
  Belle Isle and it felt worth it, say this and I'll prep the next candidate (Bessie/3009, person
  3299 "Elizabeth Tischler?", or Nellie Kubrin).

- **Just react to the Morning Mystery** — tell me what worked and what didn't about the artifact
  itself, and I'll fix the format before we scale. Your feedback on the first one shapes all of them.

## If you're not sure
Do **A** (open the link, 15 min), tell me how it felt, then say **"Run W1-S4"** to keep the engine
moving. That's the natural path.

---
*Full detail: `RESEARCH_DESK_PLAN.md` (the plan) · `docs/session_logs/session-171-log.md` (what
happened) · `docs/assessments/session-171-assessment.md` (self-eval) ·
`docs/strategy/2026-07-reengagement/meta-log.md` (how the multi-model harness performed).*
