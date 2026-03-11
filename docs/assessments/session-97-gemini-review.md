# Session 97 Gemini Review — PRD-038 Planning Package

**Review Date:** 2026-03-11
**Reviewer:** Gemini (Antigravity)
**Target Commit:** `d2d31ba`

---

## 1. Verdict

**Approve with changes.** 

The PRD-038 planning package is exceptionally well-structured and highly disciplined. Codex has correctly identified that premature embedding fine-tuning (LoRA) would be dangerous given the extreme dataset skew (Gini 0.788) and the fragile state of the current evaluation scripts. 

The transition to a **Prototype Bank + Longitudinal Reranker** is an elegant, pragmatic architecture that perfectly matches industry standards for combining frozen embeddings with sparse metadata. 

However, the plan under-specifies constraints around active learning label quality, lacks defense against reranker overfitting on dominant families, and needs minor tightening in the implementation prompt.

---

## 2. Strongest Parts

*   **Eval-First Discipline (Phase 0):** Forcing measurement repair before any model work is the most critical and commendable decision in the plan. Rebuilding the golden set to reflect the current 84-identity scale and explicitly fixing the `mu` vs `embeddings` schema drift prevents the "flying blind" risk that plagued earlier ML sessions.
*   **Architectural Realism (Phase 2):** Moving away from the naive "best face per decade" concept to a small, quality-aware Prototype Bank is mathematically robust. Using a tabular reranker (HGBC) instead of overloading the scalar isotonic calibrator is exactly how modern multi-stage retrieval systems are built.
*   **Delaying LoRA (Phase 4):** Making LoRA an experimental, gated track rather than a mandated deliverable protects the system from catastrophic forgetting, which is highly probable when training on heavily skewed data distributions.
*   **Scale-Aware Cloud Path:** The architectural judgment to prepare for queued offline scaling without violating the AD-110 "no heavy ML on web requests" contract is excellent.

---

## 3. Critical Findings

*(Ordered by Severity)*

1.  **Active Learning Label Toxicity Risk (High):** Phase 3 integrates active learning gracefully into the UX, but it neglects a crucial failure mode: admin error. Historical kinship confusion is rampant (e.g., mistaking a father in 1920 for his son in 1950). If an admin mislabels an ambiguous active-learning pair, that toxic label feeds directly into the recalibration pool. **There is no explicit audit or un-do flow specified for the active learning queue.** 
2.  **Prototype Temporal Collapse (Medium):** The Phase 2 Prototype Bank mandates selecting anchors based on temporal spread *and* quality. However, if the highest quality photos for an identity all come from a single decade (e.g., a batch of 1940s studio portraits), a naive selection algorithm might prioritize quality over time, collapsing the longitudinal coverage. **Temporal spread must explicitly override quality constraints.**
3.  **Reranker Overfitting on Family Priors (Medium):** Because Roland Fox and "Big" Leon Capeluto dominate the positive pair set, an HGBC might learn that "if the face looks somewhat like this family, output a high probability" rather than learning generalized aging principles. **The evaluation slices do not explicitly test for bias toward dominant identities.**

---

## 4. Tradeoff Analysis

### Frozen Reranker vs. Immediate Embedding Tuning (LoRA)
*   **Why it's right:** Cross-age verification is notoriously difficult. Attempting to force an embedding space to become age-invariant using only a few hundred highly-skewed family pairs would likely ruin performance on high-quality, same-age pairs. The reranker allows the embeddings to remain pure facial descriptors while pushing the temporal reasoning to a purpose-built classifier.
*   **Alternative cost:** If we pushed straight to LoRA, we'd need a highly curated, balanced triplet loss setup, demanding significantly more data engineering and running a massive risk of kin false-positives.

### HGBC vs. MLP Reranker
*   **Why it's right:** `HistGradientBoostingClassifier` intrinsically handles missing values. In a heritage archive, birth years and photo dates are frequently `NaN`. An MLP requires complex imputation that can introduce artifacts. 
*   **Why it might be wrong:** It breaks end-to-end differentiability. 
*   **Resolution:** Since the underlying embeddings are frozen, differentiability to the base model is irrelevant. HGBC is the correct choice.

### Local-Only Recalibration
*   **Why it's right:** It respects AD-007 and keeps Railway memory boundaries safe.
*   **Why it might be wrong:** It ties the core intelligence flywheel directly to Nolan's local laptop, continuing the single-point-of-failure risk.
*   **Resolution:** The plan clearly documents the thresholds for moving this to cloud workers. As long as those thresholds are respected, it's an acceptable temporary tradeoff.

---

## 5. Research Additions

To validate Codex's plan, I consulted the following external sources:

*   **CACon and CALFW Benchmarks:** Recent state-of-the-art papers in age-invariant face recognition (e.g., CACon, 2024) rely on the CALFW dataset, which proves that age gaps cause a massive 10-17% accuracy drop in verification networks. This reinforces the need for Phase 2's explicit age-gap penalties, as raw cosine distance will inherently fail over decades.
*   **Dual-Encoder vs. Cross-Encoder Paradigms:** In industry identity matching, systems employ an initial fast retrieval (Bi-encoder/Vector DB) followed by an intensive scoring phase (Cross-encoder/Reranker). Codex's proposal dynamically mirrors this standard, substituting the HGBC as the Cross-encoder because tabular metadata (dates/geography/GEDCOM) must be fused.
*   **Google Photos Face Grouping Failure Modes:** Community complaints heavily cite *kin false merges* (grouping siblings or parent/child together) as the most frustrating and difficult-to-undo error in Google Photos. This powerfully validates the strict kinship safety gates in Phase 4 and the insistence that *proposals remain additive only* rather than destructive auto-merges.
*   **Human-in-the-Loop Active Learning:** Literature on low-volume medical image annotation shows active learning works best with *Uncertainty Sampling* combined with a robust un-do capability. This aligns with Phase 3 but highlights the missing audit log requirement (see Critical Findings).

---

## 6. Recommended Changes

Before execution begins in Session 97, the following plan tweaks should be made:

1.  **Modify Phase 2 Prototype Selection Rules:** Add a strict override: *"The prototype bank must contain anchors from distinct chronological eras (e.g., separated by >= 15 years) if the metadata allows, even if it means discarding a higher-quality face score from a redundant era."*
2.  **Add Feature to Phase 2 Reranker:** Add a boolean `has_kinship_risk` feature to the reranker's input dictionary. If the target identity has close relatives (siblings/parents) known to be alive in the same photo era (via GEDCOM), the reranker should learn to require a higher face similarity threshold to output a match.
3.  **Modify Phase 3 Deliverables:** Explicitly add: *"Actionable audit log UI allowing admins to review and revert their recent active learning labels before initiating a recalibration run."*
4.  **Modify Phase 0 Unification Design:** Explicitly mandate that `core/auto_cluster.py` is the architectural source of truth for offline batch matching, and `scripts/cluster_new_faces.py` should merely be a CLI wrapper that imports and calls the core pipeline.

---

## 7. Prompt Assessment

The prompt `docs/prompts/session-97-prompt.md` is **excellent**. 

*   It adheres to Anthropic's guidelines for agentic design by scoping context tightly.
*   It explicitly forbids modifying production data outside canonical flows.
*   The phase gates are concrete and testable.
*   **Recommended Prompt Change:** In **Act 1**, add a requirement for Codex to *explicitly log the data skew (Gini coefficient)* of the newly rebuilt golden set, so there is numerical proof of the dataset balance before entering Phase 2 modeling.

---

## 8. Scaling Assessment

The transition plan detailed in `docs/architecture/ML_SERVICE.md` and the SDD is exceptionally pragmatic. Recognizing that the real blocker is the laptop dependency rather than compute limitations correctly shifts the focus to an asynchronous, job-queued architecture (e.g., Modal, Ray Serve, or Celery) rather than attempting to bolt real-time inference onto FastHTML web endpoints. The cutover triggers (45-min runtimes, 100+ faces/day) are well-calibrated.

---

## 9. Confidence

*   **Eval Repair (Phase 0):** 100% confidence. It is a mandatory prerequisite.
*   **Architecture Choice (Phase 2):** 95% confidence. The Reranker model is the correct structural choice. 
*   **Active Learning (Phase 3):** 85% confidence. High utility, provided the undo/audit UX is robust.
*   **LoRA Delay (Phase 4):** 100% confidence. Rushing LoRA on Fox-hegemony data would be disastrous.
*   **Prompt Robustness:** 95% confidence.

Codex is ready to execute upon this plan, provided the recommended changes are noted.
