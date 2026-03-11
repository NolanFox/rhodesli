# Session 97 Gemini Review Prompt — PRD-038 Planning Package

You are reviewing Codex's PRD-038 planning package in the Rhodesli repo.
This is a critical review pass, not an implementation pass.

Current review target:
- repo worktree: `/tmp/rhodesli-prd038-plan`
- branch: `codex-prd-038-plan`
- commit under review: `d2d31ba` — `[codex] docs(ml): package PRD-038 session 97 handoff`

Your job is to evaluate whether this plan is technically sound, well-scoped,
well-researched, and likely to produce a better matcher without causing
regressions or wasting implementation effort.

Do not be generous. Be exact.

## Core Instructions

1. Fully audit the PRD-038 planning package.
2. Do your own research where needed:
   - academic sources
   - product/industry patterns
   - open-source systems
   - community pain points
   - best practices for evaluation, retrieval/reranking, active learning,
     and scaling ML systems
3. Validate or challenge Codex's conclusions with evidence.
4. Identify:
   - hidden risks
   - weak assumptions
   - missing evals
   - over-engineering
   - under-specified parts
   - better alternatives if they exist
5. Write a markdown review artifact into this worktree.
6. Commit that review in this worktree only.

## Non-Negotiable Constraints

1. Do **not** disrupt the user's active main checkout, where another agent is
   finishing Session 96 work.
2. Stay in `/tmp/rhodesli-prd038-plan` or a child branch/worktree created from it.
3. Do **not** change application code, data files, or production behavior.
4. Follow the harness:
   - preserve research in repo artifacts
   - preserve conclusions in repo artifacts
   - preserve review output in repo artifacts
5. If you need more research, do it. Do not skip it because the plan already
   has sources.

## Read First

Read these in order:

1. `AGENTS.md`
2. `docs/session_context/session-97-gemini-review-context.md`
3. `docs/prds/038_longitudinal_face_modeling.md`
4. `docs/prds/SDD-038_longitudinal_face_modeling.md`
5. `docs/prds/038_longitudinal/EVALUATION_AND_SAFETY.md`
6. `docs/prds/038_longitudinal/RESEARCH_REFERENCES.md`
7. `docs/session_context/session-97-context.md`
8. `docs/prompts/session-97-prompt.md`
9. `docs/assessments/session-97-prep-assessment.md`
10. `docs/session_logs/session-97-prep-log.md`
11. `docs/ml/ALGORITHMIC_DECISIONS.md` entries AD-215 through AD-217
12. `docs/HARNESS_DECISIONS.md` entries HD-024 and HD-025
13. `ROADMAP.md`
14. `docs/BACKLOG.md`
15. `docs/roadmap/ML_ROADMAP.md`
16. `docs/architecture/ML_SERVICE.md`

## What You Are Evaluating

Codex's main claims are:

1. The first implementation step should be **evaluation repair and scorer-path
   unification**, not immediate model work.
2. The main offline matcher should evolve toward:
   - frozen-embedding retrieval
   - a small quality-aware prototype bank per identity
   - a multifeature longitudinal reranker
3. The original draft's "best face per decade" concept should be superseded.
4. Metadata expansion should go into a reranker, not be bolted only onto the
   legacy isotonic path.
5. LoRA / PEFT should be a gated experiment after the frozen-embedding path
   proves out on hard slices.
6. The architecture should remain local-first now, but cloud extraction should
   be planned via artifact-based offline jobs and queued workers later.
7. The Session 97 implementation prompt and context are strong enough to guide
   a safe, effective Codex build pass.

You should evaluate whether these claims are actually correct.

## Areas To Scrutinize Hard

### 1. Evaluation Design

- Is the evaluation plan sufficient to prove a real improvement?
- Are the right slices present?
- Is anything missing around temporal bias, kinship confusion, community leakage,
  calibration drift, or proposal quality?
- Is the baseline strong enough that some proposed work is unlikely to pay off?

### 2. Architecture Choice

- Is prototype-bank + reranker the right next step?
- Would another approach be better:
  - per-identity thresholds
  - metric learning without LoRA
  - graph-based identity reasoning
  - hybrid prototype + temporal prior model
  - other state-of-the-art approaches

### 3. LoRA / Adaptation

- Is Codex too conservative on LoRA?
- Or not conservative enough given the pair skew?
- What concrete gating criteria would you use?

### 4. Active Learning And UX

- Is integrating active learning into review UX the correct product move?
- Are the proposed queue/diversity rules adequate?
- Are there better patterns from the literature or leading products?

### 5. Scaling Path

- Are the local-to-cloud migration thresholds sensible?
- Is the proposed migration order right?
- Are there missing operational constraints around artifacts, queues, cost,
  observability, reproducibility, or rollback?

### 6. Prompt / Harness Quality

- Is the Session 97 Codex prompt actually good enough to drive execution?
- Where is it ambiguous, too broad, or missing required outputs?
- Does it properly control context, commits, tests, and artifact preservation?

## Required Research Standard

Do not rely only on the sources already in the package.
Bring in any additional external sources needed to evaluate the plan well.

At minimum, look for evidence on:
- cross-age face recognition
- retrieval + reranking patterns for identity matching
- active learning for low-volume / human-in-the-loop ML systems
- practical deployment patterns for offline ML pipelines moving to cloud workers
- product failure modes in consumer or archival face grouping systems

## Required Output

Write:

`docs/assessments/session-97-gemini-review.md`

The review must contain these sections:

1. **Verdict**
   - overall recommendation: approve / approve with changes / substantial rework

2. **Strongest Parts**
   - what Codex got right

3. **Critical Findings**
   - ordered by severity
   - include file references where relevant

4. **Tradeoff Analysis**
   - why the chosen design may be right
   - why it may be wrong
   - alternatives and their costs

5. **Research Additions**
   - new sources you consulted
   - how they changed or reinforced your view

6. **Recommended Changes**
   - concrete doc or plan changes before implementation

7. **Prompt Assessment**
   - whether `docs/prompts/session-97-prompt.md` is strong enough for Codex

8. **Scaling Assessment**
   - whether the local-to-cloud plan is well-designed

9. **Confidence**
   - confidence per major conclusion

The review should be specific enough that Codex can take a second pass on the
package without ambiguity.

## Commit Requirement

After writing the review:

1. commit it in this worktree
2. use a conventional commit message
3. do not touch the user's main branch

Suggested commit:

`[gemini] docs(ml): review PRD-038 session 97 package`
