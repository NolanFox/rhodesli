# Session 97 Gemini Review Context — PRD-038 Planning Package

**Prepared:** 2026-03-11
**Target reviewer:** Gemini in Antigravity
**Review target commit:** `d2d31ba`
**Worktree:** `/tmp/rhodesli-prd038-plan`
**Branch:** `codex-prd-038-plan`

---

## Purpose

This review is not an implementation pass. It is a critical external review of
the PRD-038 planning package before any code changes for Session 97 begin.

Gemini should:
- stress-test the plan
- validate or challenge the research
- identify weak assumptions, missing evals, and risky tradeoffs
- propose improvements where the plan is underspecified or overconfident
- write the result to a markdown artifact in this worktree and commit it

---

## Constraints

1. Do not interfere with ongoing Session 96 debugging on the user's active checkout.
2. Stay inside this isolated worktree or a child branch/worktree created from it.
3. Do not modify production data, local `data/` files, or app behavior.
4. Follow the harness: preserve research, findings, and decisions in repo artifacts.
5. Be critical. The goal is to improve the plan, not to rubber-stamp it.

---

## Files To Review First

### Core plan

1. `AGENTS.md`
2. `docs/prds/038_longitudinal_face_modeling.md`
3. `docs/prds/SDD-038_longitudinal_face_modeling.md`
4. `docs/prds/038_longitudinal/EVALUATION_AND_SAFETY.md`
5. `docs/prds/038_longitudinal/RESEARCH_REFERENCES.md`

### Handoff and rationale

6. `docs/session_context/session-97-context.md`
7. `docs/prompts/session-97-prompt.md`
8. `docs/assessments/session-97-prep-assessment.md`
9. `docs/session_logs/session-97-prep-log.md`

### Decision and roadmap breadcrumbs

10. `docs/ml/ALGORITHMIC_DECISIONS.md` entries AD-215 through AD-217
11. `docs/HARNESS_DECISIONS.md` entries HD-024 and HD-025
12. `ROADMAP.md`
13. `docs/BACKLOG.md`
14. `docs/roadmap/ML_ROADMAP.md`
15. `docs/architecture/ML_SERVICE.md`

---

## Known Ground Truth From Codex's Audit

- confirmed identities: 84
- confirmed identities with 2+ faces: 28
- same-identity pairs from confirmed faces: about 1,453
- same-identity pairs with year coverage: 331
- same-identity pairs with year gap >= 20: 54
- current golden set is stale at 125 mappings / 23 identities
- current eval scripts are broken on the live embedding schema
- schema-aware local spot check:
  - Euclidean AUC about 0.978
  - MLS AUC about 0.953
- key architectural finding:
  - scorer path is split across `core/auto_cluster.py` and `scripts/cluster_new_faces.py`

Gemini should validate these claims where possible and note where they materially
affect confidence in the plan.

---

## Main Questions Gemini Should Answer

1. Is the revised execution order correct?
   - eval repair first
   - scorer-path unification second
   - frozen-embedding longitudinal reranker before LoRA

2. Is the prototype-bank + reranker approach stronger than:
   - best-face-per-decade
   - metadata-only calibrator expansion
   - immediate LoRA / PEFT

3. Are the eval gates strong enough?
   - what is missing
   - what is too weak
   - what should block rollout

4. Are the safety constraints sufficient for:
   - kinship confusion
   - community leakage
   - retroactive discoveries
   - false confidence from stale or skewed data

5. Is the cloud-scaling plan sensible?
   - are the cutover triggers reasonable
   - should the thresholds be different
   - is the proposed migration order correct

6. Is the Session 97 implementation prompt strong enough for Codex?
   - where is it too vague
   - where is it over-scoped
   - where are there missing deliverables or weak review gates

---

## Required Output Artifact

Write a markdown review to:

`docs/assessments/session-97-gemini-review.md`

The review should include:
- executive verdict
- strongest parts of the plan
- critical findings and risks
- research-backed disagreements
- tradeoff analysis
- recommended changes to the plan or prompt
- explicit confidence level on each major recommendation
- note of any additional sources consulted

The review should be blunt and technically specific.

---

## Commit Requirement

After writing the review:
- commit it in this PRD-038 worktree
- use a conventional commit message
- do not touch the user's main working branch

Suggested commit:

`[gemini] docs(ml): review PRD-038 session 97 package`
