# Session 97 Gemini Follow-Up — Eval Specifications

**Date:** 2026-03-11
**Author:** Gemini (Antigravity)
**Context:** This document answers the follow-up questions posed in the `session-97-post-gemini-assessment.md` to turn qualitative review feedback into concrete evaluation and safety designs for Codex's implementation pass.

---

## 1. Exact Source Citations

The "Research Additions" in the initial Gemini review relied on the following sources, which are now explicitly cited here to meet the harness's breadcrumb standards:

*   **CACon and CALFW Benchmarks:**
    *   *CACon:* "Cross-Age Contrastive Learning for Age-Invariant Face Recognition" (arXiv 2024: [https://arxiv.org/abs/2408.00797](https://arxiv.org/abs/2408.00797))
    *   *CALFW:* Cross-Age Labeled Faces in the Wild benchmark ([https://www.whdeng.cn/CALFW/index.html](https://www.whdeng.cn/CALFW/index.html))
*   **Dual-Encoder vs. Cross-Encoder Paradigms:**
    *   Sentence Transformers, Retrieve & Re-Rank architecture guide: ([https://www.sbert.net/examples/sentence_transformer/applications/retrieve_rerank/README.html](https://www.sbert.net/examples/sentence_transformer/applications/retrieve_rerank/README.html))
*   **Google Photos Face Grouping Failure Modes:**
    *   Reddit community discussion on face grouping complaints, specifically highlighting kin false merges and repair difficulty: ([https://www.reddit.com/r/googlephotos/comments/10nmhee/face_detectiongrouping_quality_on_google_photos/](https://www.reddit.com/r/googlephotos/comments/10nmhee/face_detectiongrouping_quality_on_google_photos/))
*   **Human-in-the-Loop Active Learning (Medical Imaging):**
    *   Wang et al., 2024: "Deep active learning in medical image analysis" ([https://pubmed.ncbi.nlm.nih.gov/38776841/](https://pubmed.ncbi.nlm.nih.gov/38776841/))
    *   Follmer et al., 2024: "Uncertainty-aware submodular selection" demonstrating that diversity must be balanced with uncertainty ([https://proceedings.mlr.press/v250/follmer24a.html](https://proceedings.mlr.press/v250/follmer24a.html))

---

## 2. Dominant-Identity Bias: Eval Design

To ensure the longitudinal reranker does not simply overfit to the highly represented Fox and Capeluto families (Gini 0.788), the evaluation harness must test for distributed lift.

*   **Exact Metrics:**
    *   `dominant_lift_ratio`: (ROC-AUC improvement for the Top 3 most frequent identities) / (ROC-AUC improvement for all remaining identities).
    *   `tail_recall_delta`: The absolute change in Rank-1 recall specifically for the bottom 50% of identities (by confirmed face count).
*   **Exact Slice Construction:**
    *   `slice_dominant_identities`: A subset of the Golden Set containing *only* query-target pairs where both faces belong to the top 3 identities by volume (e.g., Roland Fox, etc.).
    *   `slice_tail_identities`: A subset containing pairs where the target identity has `< 5` confirmed faces in the entire archive.
*   **Exact Rollout Gate:**
    *   `dominant_lift_ratio` must be **< 3.0**. (The model can improve more on the big families, but not infinitely more; if the ratio exceeds 3.0, it's memorizing family traits rather than learning generalized aging).
    *   `tail_recall_delta` must be **>= 0.0**. (The reranker is not permitted to regress performance on rare people to achieve higher global accuracy).
*   **2 Test-Fixture Ideas:**
    *   `test_eval_blocks_extreme_family_overfit`: Create a mocked candidate scorer block that returns a `1.0` similarity for all Fox family pairs, but returns a random `[0.0, 0.5]` score for all other families. Assert that the `dominant_lift_ratio` gate trips and blocks rollout.
    *   `test_eval_passes_balanced_lift`: Create a mocked scorer that adds `+0.05` to the baseline similarity score uniformly across all pairs. Assert that both gates pass.

---

## 3. Active-Learning Label Toxicity: Safety Design

Mislabeled pairs submitted through the active learning UI can poison the recalibration pool. This design enforces reversible, auditable label management.

*   **What should be reversible:**
    *   Any `Same` or `Different` decision submitted via the Active Learning UI must be fully revertible by an admin **until** the next offline recalibration batch job successfully completes and consumes those labels.
*   **What should be logged:**
    *   The `face_id_1` and `face_id_2` involved.
    *   The `admin_user_id` who made the decision.
    *   The exact timestamp.
    *   The applied label (`explicit_positive` or `explicit_negative`).
    *   The source surface (`active_learning_queue`).
*   **What should block recalibration:**
    *   Recalibration must run a pre-flight **Logical Consistency Check**. If newly submitted labels violate transitive identity (e.g., the admin labeled A=B, B=C, but A!=C), the entire recalibration job must abort and flag the specific conflicting labels for admin review.
*   **2 Test-Fixture Ideas:**
    *   `test_recalibration_excludes_reverted_label`: Submit an `explicit_positive` label via the mock UI, immediately call the revert/undo endpoint, trigger a mock recalibration dump, and assert that the reverted pair is absent from the training payload.
    *   `test_recalibration_aborts_on_logical_conflict`: Inject a deliberate transitive conflict into the unconsumed label pool (A=B, B=C, A!=C). Trigger recalibration. Assert an exception is raised and the job terminates before altering the model state.

---

## 4. `has_kinship_risk`: Feature Family Scope

The post-assessment rightfully noted that a single boolean `has_kinship_risk` is too blunt. Kinship is not a binary visual confounder; it has dimensions. 

It should become a **small feature family** rather than a boolean.

**Why:** A father-son pair across a 30-year temporal gap (e.g., father at age 40, son at age 10) presents a vastly different visual similarity profile than two brothers photographed in the exact same year. A single boolean forces the HGBC reranker to penalize both scenarios equally. By breaking it into a small set of tabular features, the gradient boosting tree can learn nuanced, multi-dimensional boundary penalties.

**Proposed Feature Family:**
1.  `kinship_category` (Categorical): The closest GEDCOM relationship between the two identities (`sibling`, `parent_child`, `skip_generation`, `none`).
2.  `kinship_temporal_overlap` (Boolean): Were they both alive and of photographable age at the time the query photo was taken? (Helps discount impossible false-positives).
3.  `kinship_age_delta` (Float/Integer): The absolute difference in their estimated ages *at the time the respective photos were taken*. (If a brother is 15 in photo A, and the other brother is 15 in photo B, the risk of a false merge is exceedingly high, and the reranker should require a massive similarity score to confirm).
