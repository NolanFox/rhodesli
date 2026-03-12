# Session 100 Design Method Research

**Date:** 2026-03-12  
**Author:** Codex

## Question
Should Session 100 use a “five designers + design board” method to improve
design quality when Antigravity is unavailable or quota-limited?

## Short Answer
Yes, but not as pure roleplay.

The strongest version is:
- parallel concept generation
- structured critique with a fixed rubric
- explicit red-team review for confusion/regression risk
- one synthesis pass with documented reasons for selection

Pure serial “pretend to be five designers” is weaker because one model can
produce fake diversity. The method works better when each pass is forced to
optimize for a different constraint and scored against the same rubric.

## What The Research Says

### 1. Parallel concepts beat single-thread ideation
The Stanford d.school / related parallel prototyping work argues that teams make
better decisions when they compare multiple concrete alternatives instead of
iterating too early on one favorite direction.

Source:
- Stanford / d.school parallel prototyping article:
  https://web.stanford.edu/~klemmer/cgi-bin/Papers.php?id=parallel-prototyping-to-leverage-divergent-exploration

### 2. Structured critique is better than taste-by-volume
NN/g and Figma both push critique as a disciplined activity: clarify the goal,
review work against criteria, separate observation from preference, and leave
with clear decisions.

Sources:
- NN/g design-critique guidance:
  https://www.nngroup.com/articles/design-critique/
- Figma critique best practices:
  https://www.figma.com/blog/how-to-run-a-design-critique/

### 3. Independent sketches + a decider reduce groupthink
Google Ventures design sprint practice uses individual sketches, a structured
critique/decision step, and a decider. That maps well to Rhodesli because the
danger is converging too fast on one pretty but impractical flow.

Sources:
- GV / Design Sprint sketch-and-decide materials:
  https://www.gv.com/sprint/
- Google Design Sprint Kit:
  https://designsprintkit.withgoogle.com/

### 4. Modern AI critique research supports multi-critic review, but with a caveat
Recent multi-critic systems show that diverse critique roles improve output
quality. But the useful lesson is not “make up five personas.” It is “force
multiple evaluators to inspect the work through distinct lenses.”

Source:
- CritiqueCrew paper:
  https://arxiv.org/abs/2409.08503

## Recommended Rhodesli Method

### Name
Parallel Concept Sprint + Structured Jury

### Step 1: Freeze the task
Define:
- route/surface
- user goal
- trust risk
- regression risk
- non-negotiables

### Step 2: Generate 3-5 sharply different concepts
Not five variations of the same thing. Each concept must optimize for a
different lens, for example:
- archival/editorial trust
- high-speed admin throughput
- public contribution clarity
- mobile-first use
- dense multi-face comprehension

### Step 3: Critique each concept with one shared rubric
Score each on:
- task speed
- discoverability
- archive/context clarity
- admin/public separation
- regression risk
- visual taste / anti-slop

### Step 4: Run one explicit red-team pass
Ask:
- what would confuse a Fox Family contributor?
- what would leak them into Rhodes?
- what would slow tagging?
- what would create one-off UI drift?

### Step 5: Select one direction and record why
Do not blend all five. Pick one primary direction, then carry forward only the
best supporting ideas from the others.

### Step 6: Browser-verify the selected direction
Use real flows and screenshots, not only static mockups.

## How Codex Should Use This When Antigravity Is Unavailable
1. Produce multiple concept passes intentionally, not casually.
2. Label each pass by its design lens.
3. Score each against the same rubric.
4. Document the “board discussion” as a synthesis note, not as fake consensus.
5. Keep attribution explicit:
   - Codex-generated concept passes
   - Antigravity-generated critique/mockups when available
   - user decisions

## Decision
Adopt the method in adapted form.

For Rhodesli, the best protocol is **not** “five designers and vote.”
It is **parallel concepts + rubric + red-team + synthesis + browser proof**.
