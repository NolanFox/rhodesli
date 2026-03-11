# PRD-038: Longitudinal Face Modeling

**Author**: Nolan Fox + Claude Code
**Date**: 2026-03-10
**Status**: PLANNED → Ready for Review
**Priority**: P1 (upgrades matching quality as data grows)
**Estimated effort**: 5-8 sessions across 5 workstreams + recalibration architecture
**Source**: User feedback Session 96e-cont6 — Roland Fox has many photos across life stages
**Predecessor research**: AD-001 (multi-anchor), AD-034 (centroid rejected), AD-115/145 (LoRA), AD-092 (active learning), AD-126/149 (calibration), ADR-002 (temporal priors), Session 68 LoRA audit

## Detailed Specs (sub-files)
- **[System Design / Implementation Plan](SDD-038_longitudinal_face_modeling.md)** — Current-state audit, implementation phases, eval-first rollout, and explicit divergences from the initial PRD draft
- **[Recalibration Architecture](038_longitudinal/RECALIBRATION_ARCHITECTURE.md)** — When/where/how calibration re-runs, event triggers, architecture options
- **[Implementation Specs](038_longitudinal/IMPLEMENTATION_SPECS.md)** — Per-workstream code changes, function signatures, test specs, LoRA data growth strategy
- **[Evaluation & Safety](038_longitudinal/EVALUATION_AND_SAFETY.md)** — Hold-out evaluation, retroactive improvement safety, community resilience, notification flow
- **[Research References](038_longitudinal/RESEARCH_REFERENCES.md)** — Academic papers, Google Photos analysis, LoRA best practices, heritage-specific challenges
- **[ML Lineage & Replay](038_longitudinal/LINEAGE_AND_REPLAY.md)** — Current logging gaps, run/version lineage requirements, and what must exist before iterative scorer refreshes are trustworthy
- **[Session 97 Context](../session_context/session-97-context.md)** — Phase-scoped execution context, captured user constraints, and scale triggers
- **[Session 97 Prompt](../prompts/session-97-prompt.md)** — Codex-optimized implementation and test prompt for the future build pass
- **[Session 97 Prep Assessment](../assessments/session-97-prep-assessment.md)** — Planning-package audit and handoff status

**Implementation note (2026-03-11 review)**: This PRD remains the product brief. The companion SDD supersedes workstream ordering and file-level implementation details where the original draft conflicts with the live codebase, especially around scorer unification, evaluation repair, and the primary `core/auto_cluster.py` path.
**Scaling note (2026-03-11 review)**: PRD-038 still launches as a local offline pipeline, but the revised SDD now defines the cloud-extraction path and the thresholds that should trigger it so the architecture does not hard-code "Nolan's laptop" as a permanent dependency.

---

## Problem Statement

Rhodesli has growing photo collections spanning 100+ years (1890s-1990s). Fox Family alone has ~636 photos with many repeat people (e.g., Roland Fox across childhood to adulthood). As an admin confirms more identities and adds more communities, matching should get **continuously better** — not just linearly (more anchors to compare) but compounding (model improves, thresholds sharpen, uncertainty decreases).

**Current state**: Multi-anchor best-linkage (AD-001) with frozen InsightFace embeddings. AUC 0.9577 via isotonic calibration on 348 pairs. No age-awareness, no active learning loop, no embedding fine-tuning. Recalibration hooks exist but **silently fail on production** (sklearn not on Railway, embeddings path wrong).

**Gap**: Three compounding problems:
1. Adding photos improves matching linearly, not exponentially (no model improvement)
2. Admin confirmations generate training data that's never used (recalibration broken)
3. No temporal reasoning means 100-year age gaps don't reduce match confidence

## Who This Is For

| Role | Relationship |
|------|-------------|
| **Admin (Nolan)** | Confirms identities, reviews suggestions, runs ML pipeline locally |
| **Community members** | See better "Is this the same person?" suggestions over time |
| **Future community admins** | Same admin tools for their archives |

---

## User Flows

### Flow 1: Continuous Improvement Loop (Admin)
1. Admin confirms identities via Discoveries / New Matches pages
2. Each confirm/merge/reject fires recalibration hooks → pairs saved to `calibration_pairs` table in Supabase
3. After accumulating 20+ new labels, admin runs `python scripts/recalibrate.py` locally
4. Recalibration script pulls pairs from Supabase, retrains isotonic model, reports AUC change
5. Admin runs `python scripts/cluster_new_faces.py` → clustering uses updated calibration
6. Deploys updated model artifact via `git push`
7. Next time community members browse, suggestions reflect improved model

### Flow 2: Active Learning Review (Admin)
1. Admin opens Discoveries page
2. Below main discoveries, sees "Help Improve Matching" section with 10 uncertain pairs
3. Each pair shows two face crops side by side with similarity percentage
4. Admin clicks "Same Person" or "Different Person"
5. Label stored in `calibration_pairs` → feeds into next recalibration
6. After labeling session, admin runs recalibration locally

### Flow 3: Data Growth → LoRA Milestone (Admin)
1. Admin adds new community archive (more family photos)
2. Confirms identities → positive pair count grows
3. Runs `python scripts/lora_data_audit.py` → reports "READY: 520 pairs, Gini 0.28"
4. Runs LoRA training script locally (30-60 min)
5. Script auto-evaluates on golden test set, reports AUC change
6. If improved: deploy new embeddings, re-cluster everything
7. If regressed: automatic rollback, log finding, wait for more data

### Flow 4: Age-Aware Matching (Automatic)
1. New photo uploaded with Gemini date estimate "circa 1925"
2. Clustering compares against existing identities
3. Identity "Leon Capeluto" has anchors from 1920s, 1940s, 1960s
4. System matches against 1920s anchors first (closest era), applies no age penalty
5. Match against 1960s anchor applies soft penalty (40-year gap)
6. Result: Better ranking of suggestions, fewer cross-era false positives

---

## 5 Workstreams + Recalibration Architecture

### WS-0: Fix Recalibration Pipeline (PREREQUISITE)
**Critical finding**: Recalibration hooks exist (`rhodesli_ml/recalibration_hooks.py`) and are wired into `app/engagement_routes.py:727-740`, but they silently fail on production because sklearn isn't installed on Railway (AD-007) and embeddings path is wrong (Lesson 114).

**Fix** (1 session):
1. Remove `_check_recalibration()` from production hooks (keep pair insertion only)
2. Fix embeddings path to use `core.config.STORAGE_DIR`
3. Upgrade `logging.debug` → `logging.warning` for visibility
4. Add `scripts/recalibrate.py` CLI for local recalibration
5. Add `/api/admin/calibration-status` endpoint
6. Add Sentry alert when >20 new pairs accumulated

**Architecture decision**: Local-only recalibration (Option A). See [RECALIBRATION_ARCHITECTURE.md](038_longitudinal/RECALIBRATION_ARCHITECTURE.md) for full analysis of 4 options and why this is right for now.

### WS-1: Confidence-Weighted Matching (ML-110, ML-115)
Weight anchors by face quality. High-quality detections reduce effective distance by up to 30%. Also recalibrate thresholds with current confirmed dataset.
- **File**: `scripts/cluster_new_faces.py` → `compute_min_distance()`
- **Effort**: LOW (1 session) | **Expected**: +2-5% recall

### WS-2: Age-Aware Clustering (ML-113, ML-116)
Soft penalties for age-impossible matches + stratify anchors by decade.
- **File**: `scripts/cluster_new_faces.py` + `collect_identity_embeddings()`
- **Data**: 271 photo dates + 67 GEDCOM birth years
- **Effort**: MEDIUM (1-2 sessions) | **Expected**: Eliminate cross-era false positives

### WS-3: Active Learning Loop (ML-112)
Surface uncertain pairs for admin review. Each label improves calibration.
- **File**: `rhodesli_ml/active_learning.py` → wire to Discoveries page
- **Effort**: LOW (1 session) | **Expected**: Continuous improvement compound

### WS-4: LoRA Fine-Tuning (ML-114)
Fine-tune InsightFace backbone on heritage photo pairs using LoRA.
- **Data strategy**: Grow via admin confirmations + new community archives
- **Milestones**: 350 pairs (first training) → 500 → 1000 → 2000 (re-evaluate)
- **Continuous**: Each data milestone triggers re-evaluation, retrain, validate
- **Effort**: HIGH (2-3 sessions) | **Expected**: +3-8% AUC
- See [IMPLEMENTATION_SPECS.md WS-4](038_longitudinal/IMPLEMENTATION_SPECS.md) for data growth strategy and training recipe

### WS-5: Metadata Feature Expansion (ML-111)
Add date proximity, name similarity, GEDCOM distance, co-occurrence to calibrator.
- **File**: `rhodesli_ml/similarity_calibration.py` → `_featurize_pair()`
- **Effort**: LOW-MEDIUM (1 session) | **Expected**: AUC 0.957 → 0.965+

---

## Implementation Sequence

| Session | Work | Depends On | Parallel? |
|---------|------|------------|-----------|
| N | **WS-0**: Fix recalibration pipeline | Nothing | Yes (with WS-1) |
| N | **WS-1**: Confidence weighting + recalibration CLI | Nothing | Yes (with WS-0) |
| N | **WS-3**: Wire active learning to UI | Nothing | Yes (with WS-0/1) |
| N+1 | **WS-5**: Metadata feature expansion | WS-0 (calibrator fix) | Yes (with WS-2) |
| N+1 | **WS-2**: Age-aware distance + anchor stratification | Date data exists | Yes (with WS-5) |
| N+2 | Admin confirmation sprint (data collection) | WS-3 (active learning) | — |
| N+3-4 | **WS-4**: LoRA fine-tuning | 350+ positive pairs | — |

WS-0/1/3 can all run in parallel as first session. WS-2/5 parallel as second session.

---

## Data Model Changes

### New/Modified Tables
- `calibration_pairs` — Already exists. Add `labeled_at` timestamp, `session_id` for tracking.
- `ml_model_versions` — NEW. Track model version, AUC, threshold, pair count, created_at. Allows rollback.

### New Artifacts
- `rhodesli_ml/artifacts/calibration_v{N}.pt` — Versioned calibration models (not just v1)
- `rhodesli_ml/artifacts/lora_v{N}.pt` — LoRA weights per training run (WS-4)

### New CLI Scripts
- `scripts/recalibrate.py` — Pull pairs, retrain, export, report
- `scripts/lora_data_audit.py` — Assess readiness for LoRA training
- `scripts/lora_train.py` — LoRA training with golden test evaluation (WS-4)

---

## Evaluation Framework (Critical)

Every improvement MUST be quantified. See [EVALUATION_AND_SAFETY.md](038_longitudinal/EVALUATION_AND_SAFETY.md) for full spec.

**Golden test set**: 5-fold cross-validation on confirmed identities. Hold out 1 anchor per identity to simulate "would this photo find the right person?"
**Evaluation script**: `python scripts/evaluate_ml.py --mode [quick|full|compare|holdout-sim]`
**Before every deploy**: quick eval (30s). After WS completion: full eval (5min). After LoRA: full + holdout-sim (10min).
**Key metrics**: AUC, Rank-1 accuracy, cross-era recall, family false positive rate, calibration ECE.

## Retroactive Improvement Safety

When ML improves, re-clustering may find new matches. Safety rules:
1. **NEVER break confirmed clusters** — confirmed = human ground truth, ML can only propose
2. **Additions are proposals** — "Algorithm discovered [face] may be [Name]" notification, admin confirms
3. **Additive only** — new proposals generated, existing proposals not revoked, confirmed untouched
4. **Community-scoped** — cross-community proposals show badges, each community admin approves their own

The flywheel: More communities → more photos → admin confirms → calibration improves → better clustering → retroactive discoveries → notifications → more confirmations → cycle repeats.

## Technical Constraints

1. **AD-007**: ML inference local-only. sklearn/torch NOT on Railway. Recalibration must be local.
2. **AD-110**: Web requests never run heavy ML. All improvements are to the offline pipeline.
3. **AD-001**: Multi-anchor architecture is validated by literature (multi-prototype learning).
4. **Embeddings are frozen (AD-002)**: Until LoRA (WS-4), we improve matching via calibration, weighting, and temporal priors — not by changing embeddings.
5. **Lesson 114**: STORAGE_DIR derivation only in `core/config.py` — all path references must use it.
6. **300-line doc limit**: This hub PRD links to sub-files for detail.

---

## Acceptance Criteria

- [ ] `calibration_pairs` table accumulating data from admin actions (verified)
- [ ] `scripts/recalibrate.py` produces updated model with AUC report
- [ ] Active learning pairs visible in Discoveries UI
- [ ] Quality-weighted matching measurably improves recall on golden test set
- [ ] Age penalty reduces cross-era false positives
- [ ] LoRA training with data milestone checks and automatic rollback
- [ ] No regression on existing confirmed identities
- [ ] Upload of new photos → better suggestions over time (the Google Photos effect)

## Out of Scope

- Real-time face recognition on web requests (AD-110)
- pgvector migration (deferred until 5K+ embeddings)
- Full transformer backbone replacement (InsightFace ResNet adequate at scale)
- GAN-based age progression/synthesis
- External face dataset training (our value is our photos; exception: historical portrait datasets if found)

## Priority Order (if session runs out of context)

1. **WS-0**: Fix recalibration — data collection must work before anything else
2. **WS-1**: Confidence weighting — lowest effort, immediate impact
3. **WS-3**: Active learning — enables data growth for WS-4
4. **WS-5**: Metadata features — quick AUC gains
5. **WS-2**: Age-aware clustering — medium effort, specific to heritage archives
6. **WS-4**: LoRA — highest effort, highest potential, needs data milestones

## Metrics

| Metric | Current | Target (post-PRD) |
|--------|---------|-------------------|
| AUC on golden test set | 0.9577 | 0.975+ |
| Precision@recall=0.8 | ~87% | 92%+ |
| Admin review efficiency | Manual | Active learning guided |
| Cross-era false positive rate | Unknown | Tracked, decreasing |
| Calibration model freshness | Frozen | Auto-alerted when stale |
| Positive pair count | 221 | 500+ (before LoRA) |

## Breadcrumbs

- BACKLOG: ML-110 through ML-116 (all linked back to this PRD)
- ROADMAP: "Near-Term — Longitudinal Face Modeling (PRD-038)"
- ADs: AD-001, AD-034, AD-092, AD-115, AD-126, AD-145, AD-149, AD-152, ADR-002
- Sub-files: `docs/prds/038_longitudinal/` (3 detailed specs)
- Recalibration hooks: `rhodesli_ml/recalibration_hooks.py`
- Calibrator: `rhodesli_ml/similarity_calibration.py`
- Active learning: `rhodesli_ml/active_learning.py`
- Clustering: `scripts/cluster_new_faces.py`
