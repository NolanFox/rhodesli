---
name: Active learning opportunity with Fox Family labels
description: Nolan wants to investigate if confirmed Fox clusters can improve ML matching — PRD-038 infrastructure exists but gates are closed
type: project
---

Nolan asked (2026-03-14): after confirming several Fox Family clusters, can we re-run ML with that feedback to get better matches?

**Why:** PRD-038 (Session 97) built prototype-bank reranker, active learning, and adapter experiment harness — all in shadow mode with rollout gates closed. Now we have ~8 confirmed Fox people which may be enough to test.

**How to apply:** When planning ML sessions, evaluate opening PRD-038 gates. Key question: does re-clustering with confirmed faces as centroids reduce manual triage work? This is high-value if it works — could turn 1000+ manual reviews into a few dozen.
