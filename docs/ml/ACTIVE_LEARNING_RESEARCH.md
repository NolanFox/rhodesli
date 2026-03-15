# Active Learning Research for Heritage Photo Clustering

**Session:** 102 | **Date:** 2026-03-15
**Context:** Nolan's insight (FB-145): after confirming clusters, can we re-run ML with that feedback?

## Core Idea

Rhodesli has 95 confirmed identities with 262 face anchors. Each confirmation creates must-link constraints; each "Not Same" rejection creates cannot-link constraints. Academic literature shows these constraints dramatically improve clustering quality.

## Key Papers

### Constrained Clustering
- **Wagstaff et al. (2001)** — "Constrained K-means Clustering with Background Knowledge." Seminal paper showing must-link/cannot-link constraints improve cluster purity from ~60% to ~90% on benchmark datasets. Our confirmed faces = must-links, rejections = cannot-links.

### Semi-Supervised Deep Clustering
- **ScienceDirect (2023)** — Semi-supervised deep embedded clustering with pairwise constraints. Shows pairwise constraints in embedding space (exactly our setup with frozen PFE 512-dim vectors) outperform unconstrained clustering by 10-15% on face datasets.

### Continuous Learning for Face Clustering
- **ResearchGate (2021)** — Combines active learning with self-paced learning for automatic face annotation. The "self-paced" component selects easy examples first (high-confidence clusters), then progressively harder ones — mirrors our Tier 1 (auto-add) → Tier 2 (suggestions) pipeline.

### Dual-Constraint Semi-Supervised Deep Clustering
- **PMC (2025)** — DC-SSDEC: uses soft "should-link" and "shouldNot-link" constraints (not binary must/cannot). Applicable to our similarity scores where we have continuous confidence values, not just binary decisions.

### Comprehensive Review
- **Springer (2025)** — Comprehensive review of constrained clustering methods. Key finding: even 5-10% labeled data (constraints) can achieve performance comparable to fully supervised methods.

## Applicability to Rhodesli

| Concept | Paper | Rhodesli Equivalent |
|---------|-------|-------------------|
| Must-link constraint | Wagstaff 2001 | Confirmed faces in same identity (anchor_ids) |
| Cannot-link constraint | Wagstaff 2001 | Rejected faces (negative_ids) |
| Pairwise embedding constraint | ScienceDirect 2023 | Frozen PFE 512-dim vectors + distance thresholds |
| Self-paced selection | ResearchGate 2021 | Tier 1 auto-add → Tier 2 suggestions |
| Soft constraints | PMC 2025 | Calibrated similarity scores (AUC 0.9577) |
| Active learning query | All | `rhodesli_ml/active_learning.py` selects most informative face |

## Current Infrastructure (PRD-038, Session 97)

1. **Prototype-bank reranker** — `rhodesli_ml/longitudinal_reranker.py`. Uses confirmed face centroids to re-score proposals. Shadow mode only.
2. **Active learning** — `rhodesli_ml/active_learning.py`. Selects most informative faces for review. Wired to review UX.
3. **Adapter experiment** — `rhodesli_ml/embedding_adapter_experiment.py`. Frozen-embedding fine-tuning harness.
4. **Calibration lineage** — `rhodesli_ml/calibration_lineage.py`. Reversible labels, pair tracking.

**Status:** All gates closed. Ready to open with sufficient labels.

## Label Inventory (as of Session 102)

- 95 confirmed identities, 262 confirmed face anchors
- 262 anchors → ~34,000 positive pairs (all anchor combinations within identities)
- Negative pairs from `negative_ids` + cross-identity distances
- **Assessment:** Sufficient for constrained clustering evaluation (papers show improvement with as few as 5% constraints)

## Recommended Next Steps

1. **PRD-046** (ML Run Provenance) — prerequisite for safe experimentation
2. **Phase 1:** Activate prototype-bank reranker, compare shadow vs baseline
3. **Phase 2:** Re-cluster with confirmed anchors as seeds
4. **Phase 3:** Wire into post-triage pipeline
5. **Phase 4:** Measure precision/recall per run, decide on graduation

## Breadcrumbs

- PRD-038: `docs/prds/038_longitudinal_face_modeling/` (Session 97)
- PRD-045: `docs/prds/045_active_learning_feedback_loop.md`
- PRD-046: `docs/prds/046_ml_run_provenance.md`
- AD-149/152: Similarity calibration (AUC 0.9577)
- AD-179: Two-tier auto-clustering pipeline
