# ML Feedback Loop Analysis

> Design document analyzing how user actions feed back into ML predictions,
> identifying gaps, and proposing safe improvements.
>
> **Status:** Research / Design only. No code changes proposed.
>
> **Date:** 2026-02-05
>
> **Constraint:** `core/neighbors.py` algorithmic logic is FROZEN (Forensic Invariant #3).
> All proposals must work around this constraint.

---

## 1. Current State Analysis

### 1.1 Embedding Generation

Embeddings are generated **once per face, at ingestion time**, and are never modified afterward.

**Pipeline flow:**

1. `core/ingest.py` or `core/ingest_inbox.py` processes a photo using InsightFace (`buffalo_l` model, 640x640 detection size).
2. For each detected face, a Probabilistic Face Embedding (PFE) is created via `core/pfe.py:create_pfe()`:
   - `mu`: 512-dimensional L2-normalized embedding vector from InsightFace (`face.normed_embedding`).
   - `sigma_sq`: 512-dimensional uncertainty vector derived from detection confidence (`det_score`) and face bounding box area. Higher quality faces get lower sigma (more certain).
3. The PFE dict is appended atomically to `data/embeddings.npy` via `core/embeddings_io.py:atomic_append_embeddings()`.

**Key point:** Embeddings are immutable after creation. This is a Forensic Invariant ("Immutable Embeddings"). No user action -- merge, confirm, detach, reject -- ever modifies `data/embeddings.npy`. All user actions modify only `data/identities.json` (the identity registry metadata layer).

### 1.2 Embedding Storage

- **File:** `data/embeddings.npy` -- NumPy pickle array of face dicts.
- **Schema per entry:** `{mu, sigma_sq, det_score, bbox, filename, filepath, [face_id]}`.
- **Face ID generation:**
  - Legacy (bootstrap): `"{filename_stem}:face{index}"` -- deterministic from filename + face order.
  - Inbox (uploads): `"inbox_{sha256_hash[:12]}"` -- deterministic from job_id + filename + face_index.
- **Loading:** `app/main.py:load_face_embeddings()` builds a `face_id -> {mu, sigma_sq}` dict from `embeddings.npy`. Cached globally in `_face_data_cache`.

### 1.3 Identity Registry (`data/identities.json`)

Each identity contains:
- `anchor_ids`: List of face_ids confirmed as belonging to this person (strings or structured dicts with `face_id` + `weight`).
- `candidate_ids`: List of face_ids suggested but not yet confirmed.
- `negative_ids`: List of rejected face_ids AND rejected identity pairs (prefixed with `"identity:{id}"`).
- `state`: One of `INBOX`, `PROPOSED`, `CONFIRMED`, `CONTESTED`, `REJECTED`, `SKIPPED`.
- `merged_into`: If set, this identity was absorbed into another.
- Full append-only `_history` event log with provenance.

### 1.4 "Find Similar" Algorithm (`core/neighbors.py`)

The `find_nearest_neighbors()` function implements **Best-Linkage (Single Linkage)** matching:

1. Collects all face embeddings for the target identity (anchors + candidates).
2. For each other identity in the registry (excluding merged identities):
   - Skips identities in the target's `negative_ids` (entries prefixed with `"identity:"`).
   - Computes pairwise **Euclidean distance** between all face pairs: `cdist(target_embs, cand_embs, metric='euclidean')`.
   - Takes the **minimum distance** across all pairs (best-linkage).
   - Checks co-occurrence: if the two identities share any photo_id, merge is blocked.
3. Sorts candidates by distance (ascending).
4. Returns top-K results with distance, rank, and percentile.

**Distance metric:** Euclidean distance on 512-D L2-normalized embeddings. Not cosine similarity, not MLS.

**Thresholds (The Leon Standard, ADR 007):**
| Tier | Threshold | Description |
|------|-----------|-------------|
| High | `distance < 1.00` | Core cluster matches |
| Medium | `distance < 1.20` | Includes pose/quality variations |
| Low | `distance >= 1.20` | Weak similarity |

These thresholds are configured in `core/config.py` and were calibrated against the Big Leon Capeluto ground truth set.

### 1.5 Ingestion-Time Grouping (`core/grouping.py`)

When photos are uploaded via inbox, faces within a batch are grouped using:
- Pairwise Euclidean distance with Union-Find.
- `GROUPING_THRESHOLD = 0.95` (stricter than MATCH_THRESHOLD_HIGH to prefer under-grouping).
- Similar faces become one INBOX identity rather than N separate ones.

### 1.6 Clustering Pipeline (`core/clustering.py`, `core/build_clusters.py`)

A separate offline clustering pipeline exists but is **not used at runtime**:
- Uses Mutual Likelihood Score (MLS) with temporal priors (`core/temporal.py`).
- Agglomerative clustering with complete linkage.
- This was the original bootstrap pipeline. The web app uses the identity registry + Find Similar workflow instead.

### 1.7 Fusion (`core/fusion.py`)

Bayesian PFE fusion is implemented but **not invoked by any web app user action**:
- `fuse_anchors()`: Computes inverse-variance-weighted average of anchor embeddings.
- `safe_promote_candidate()`: Promotes with variance explosion check.
- `get_reevaluation_candidates()`: Surfaces rejected faces that might be reconsidered after anchor changes.

These are available in the codebase but the web app's confirm/merge/detach handlers do not call them. Fusion exists as infrastructure for future use.

---

## 2. User Action -> ML Impact Matrix

| User Action | Route | What Changes in Registry | Feeds Back to Find Similar? | Feeds Back to Clustering? | Signal Preserved? |
|---|---|---|---|---|---|
| **Merge** | `POST /api/identity/{t}/merge/{s}` | Source anchors+candidates move to target. Source marked `merged_into`. Negative_ids preserved. | **YES** -- merged identity excluded from future results (via `merged_into` filter in `list_identities`). Target's expanded face set changes distance calculations. | No (offline only) | **YES** -- merge event in history log |
| **Not Same Person** (Reject pair) | `POST /api/identity/{s}/reject/{t}` | Bidirectional `"identity:{id}"` added to both identities' `negative_ids` | **YES** -- `find_nearest_neighbors()` explicitly skips `negative_ids` entries prefixed with `"identity:"` (line 68) | No | **YES** -- stored in `negative_ids`, event log |
| **Undo "Not Same"** (Unreject) | `POST /api/identity/{s}/unreject/{t}` | Removes `"identity:{id}"` from both `negative_ids` | **YES** -- pair will reappear in results | No | **YES** |
| **Confirm Identity** | `POST /confirm/{id}` or `POST /inbox/{id}/confirm` | State -> `CONFIRMED` | **NO** -- confirmed identities are still searched against in Find Similar. No special treatment. | No | Partial -- state change recorded but not used by neighbor search |
| **Detach Face** | `POST /api/face/{id}/detach` | Face removed from source identity, new identity created with that face | **YES** -- source identity has fewer faces (changes distance profile). New identity appears as a separate candidate. | No | **YES** -- detach event in history |
| **Reject Identity** (INBOX/PROPOSED -> REJECTED) | `POST /reject/{id}` | State -> `REJECTED` | **NO** -- rejected identities still appear in Find Similar results for other identities (no filter on state in `find_nearest_neighbors`) | No | Partial -- state change recorded |
| **Skip Identity** | `POST /skip/{id}` | State -> `SKIPPED` | **NO** | No | State recorded |
| **Rename Identity** | `POST /api/identity/{id}/rename` | Name updated | **NO** | No | Name in event log |
| **Promote Candidate** (code exists but not wired in web UI) | N/A | Face moves from `candidate_ids` to `anchor_ids` | **Indirect** -- anchor list changes affect distance calculations since `get_identity_embeddings()` uses both anchors and candidates | No | Event recorded |
| **Upload Photo** | `POST /upload` | New embeddings appended to `embeddings.npy`. New INBOX identity created. | **YES** -- new identity appears in neighbor searches | No | Full provenance |

---

## 3. Feedback Gaps

### 3.1 Signals That ARE Used (Working Feedback)

1. **Rejection memory (identity pairs):** When admin clicks "Not Same", the rejected pair is stored bidirectionally in `negative_ids` with an `"identity:"` prefix. `find_nearest_neighbors()` explicitly checks this (line 68: `if f"identity:{cand_id}" in negative_ids: continue`). This is a **complete, working feedback loop**. Rejected pairs never reappear. Unreject is also supported.

2. **Merge signal:** Merged identities are excluded from results via the `merged_into` filter in `list_identities()`. The merged identity's faces expand the target, changing its distance profile to other identities.

3. **Detach signal:** Detaching a face splits an identity, directly changing the face composition used in distance calculations.

### 3.2 Signals That ARE LOST (Feedback Gaps)

1. **Confirmation signal is not leveraged.** When an admin confirms an identity, the state changes to `CONFIRMED` but `find_nearest_neighbors()` treats `CONFIRMED` identities identically to `PROPOSED` or `INBOX` ones. There is no mechanism to:
   - Prioritize confirmed identities as higher-trust matches.
   - Use confirmed identities as "anchor points" for matching new uploads.
   - Weight confirmed matches differently in distance calculations.

2. **REJECTED identity state is not leveraged.** An identity in `REJECTED` state (the whole identity was rejected, not a pair rejection) still appears as a candidate in Find Similar. If an admin rejects "Unidentified Person 047" as not a real face (e.g., a pattern in the background), it will continue appearing in neighbors for every other identity.

3. **Face-level reject signal is limited.** `reject_candidate()` in the registry moves a face from `candidate_ids` to `negative_ids`, but this is per-face within a single identity. It does not suppress that face from appearing as part of OTHER identities' neighbor results. (The web UI does not currently expose `promote_candidate` or `reject_candidate` -- these are legacy from the initial design.)

4. **Fusion is not used.** The Bayesian fusion infrastructure (`core/fusion.py`) exists but is never called by the web app. When identities are merged, the raw face embeddings are combined by appending to `anchor_ids`, but no fused centroid is computed. This means:
   - An identity with 10 faces uses all 10 in distance calculations (via best-linkage min-distance), which is the correct behavior for the current algorithm.
   - However, there's no "representative embedding" that improves with more confirmed faces.

5. **Temporal priors are not used at query time.** The clustering pipeline uses era classification (`core/temporal.py`) for MLS-based clustering, but `find_nearest_neighbors()` uses raw Euclidean distance with no temporal adjustment. This is by design (neighbors.py is FROZEN), but it means era information from the bootstrap is ignored during interactive review.

6. **Co-occurrence data enriches but does not suppress.** When two identities co-occur in a photo, merge is blocked (correctly), but the candidate still appears in the list marked "Blocked." After seeing the same blocked candidate repeatedly, there's no way to permanently suppress it short of clicking "Not Same" (which may be semantically incorrect -- they might be the same person who was detected twice in one photo due to a processing artifact).

### 3.3 Quantitative Impact Assessment

| Gap | Frequency | User Impact | ML Impact |
|-----|-----------|-------------|-----------|
| Confirmation not leveraged | Every confirmed identity | Low (no UX issue) | Medium (missed opportunity for better ranking) |
| REJECTED state not filtered | Rare (few whole-identity rejections) | Low-Medium (noise in results) | Low |
| Fusion not used | Every multi-face identity | None (best-linkage is correct) | Low (fusion would be additive, not essential) |
| Temporal priors at query time | Every Find Similar call | None visible | Unknown (would need evaluation) |
| No suppression for blocked candidates | Every co-occurring pair | Low-Medium (visual noise) | Low |

---

## 4. Proposed Improvements

### 4.1 [P0 - Already Implemented] Rejection Memory

**Status: COMPLETE.** This analysis confirms that rejection memory is fully implemented and working.

- `registry.reject_identity_pair()` stores bidirectional `"identity:{id}"` entries in `negative_ids`.
- `find_nearest_neighbors()` filters these at line 68.
- `registry.unreject_identity_pair()` provides reversibility.
- UI shows "Hidden Matches" count with an "Unblock" action for each rejected pair.

No action needed.

### 4.2 [P1 - Low Risk] Filter REJECTED-State Identities from Find Similar

**Problem:** Identities in `REJECTED` state (whole identity rejected, not pair rejection) still appear in Find Similar results. If an admin rejects a false-positive detection (e.g., a face detected in a decorative pattern), it continues polluting results.

**Proposal:** In the code that calls `find_nearest_neighbors()`, post-filter results to exclude identities whose state is `REJECTED`. This does NOT modify `core/neighbors.py` (frozen) -- it modifies the caller in `app/main.py`.

**Safety:** Additive. REJECTED identities are by definition unwanted. Confirmed identities are unaffected. Reversible because "reset" can move REJECTED back to INBOX.

**Effort:** Small. Post-filter on the results list.

### 4.3 [P2 - Medium Risk] Confirmed-Identity Priority for New Uploads

**Problem:** When new photos are uploaded, the ingestion-time grouping (`core/grouping.py`) only compares faces within the same upload batch. It does not compare against existing confirmed identities. This means a new upload of a known person creates a new "Unidentified Person" identity instead of being matched to the existing confirmed identity.

**Proposal:** After inbox identities are created, run a lightweight comparison: for each new inbox identity, compute its best-linkage distance to every CONFIRMED identity. If the distance is below `MATCH_THRESHOLD_HIGH` (the strictest threshold), annotate the inbox identity with a "suggested_match" field pointing to the confirmed identity. The UI can then show "Possible match: Leon Capeluto" during inbox review.

**Safety:** This is purely advisory (annotation only). It does NOT auto-merge. It does NOT modify the neighbors algorithm. Confirmed identities remain untouched.

**Constraint:** This would need to run in the ingestion pipeline (`core/ingest_inbox.py`), which requires ML dependencies. Since production does not have ML deps (`PROCESSING_ENABLED=false` on Railway), this would only work in local ingestion mode.

**Effort:** Medium. Requires new comparison logic in the ingestion pipeline.

### 4.4 [P3 - Low Risk] Merge Signal as Soft Evidence

**Problem:** When two identities are merged, we know their faces belong to the same person. This is a strong positive signal that is partially used (expanded face set changes best-linkage distances) but could be more explicitly leveraged.

**Current behavior:** After merge, the target identity's `anchor_ids` grows. Since `get_identity_embeddings()` returns all anchors + candidates, the best-linkage distance calculation automatically uses the expanded face set. This is already correct and useful.

**Proposal:** No change to the algorithm. Document that the current merge behavior IS the feedback loop -- expanding the face set IS the improvement. The merged identity's best-linkage distance to other identities will naturally improve as it has more exemplar faces.

**Action:** Documentation only. No code change.

### 4.5 [P4 - Zero Risk] Golden Set Expansion

**Problem:** The current golden set contains only one subject (Big Leon Capeluto) with 4 positive matches and 1 hard negative. This is sufficient for threshold calibration but too narrow for regression testing of ML changes.

**Proposal:** Identify 5-10 additional confirmed identities with 3+ face crops each. These become the expanded regression test set. Any change to matching logic must preserve correct clustering for all golden set subjects.

**Safety:** Zero risk -- this is a test infrastructure improvement, not a code change.

**See Section 5 for golden set candidates.**

### 4.6 [P5 - Medium Risk] Confirmation-Weighted Distance Display

**Problem:** Find Similar shows the same distance information regardless of whether the current identity is confirmed or proposed. A confirmed identity with 8 face crops has inherently more reliable best-linkage distances than a proposed identity with 1 face.

**Proposal:** In the UI (not in neighbors.py), display a "confidence" indicator alongside the distance that accounts for:
- Number of faces in the identity (more faces = more reliable best-linkage).
- State of the identity (confirmed = admin-vetted).
This is a **display-only** change. It does not alter ranking or filtering.

**Safety:** Zero algorithmic risk. UI-only change.

**Effort:** Small.

---

## 5. Golden Set Candidates

### 5.1 Current Golden Set

The existing golden set (`evaluation/golden_set.json`) contains:

- **Target:** `Brass_Rail_Restaurant_with_Leon_Capeluto_Picture:face0`
- **Positives (4):**
  - `Image 992_compress:face0` (distance: 0.9440)
  - `757557325.971675:face0` (distance: 0.9941)
  - `Image 964_compress:face1` (distance: 1.0490)
  - `Image 032_compress:face1` (distance: 1.1675) -- borderline, calibrated via ADR 007
- **Hard negatives (1):**
  - `Image 055_compress:face0` (distance: 1.4024)
- **Margin:** 0.2349 (between hardest positive at 1.1675 and closest negative at 1.4024)

### 5.2 Expansion Criteria

An ideal golden set identity should have:
1. **3+ face crops** in the embeddings (for within-identity consistency testing).
2. **CONFIRMED state** (admin-verified ground truth).
3. **Named** (not "Unidentified Person NNN").
4. **At least one hard negative** (a visually similar but different person).
5. **Diverse quality** (mix of frontal, angled, vintage, clear).

### 5.3 Candidate Identification Process

To identify candidates, a script should:
1. Load `data/identities.json`.
2. Filter to `state == "CONFIRMED"` identities.
3. Count face crops (anchors + candidates) per identity.
4. Sort by face count (descending).
5. Filter to identities with a non-default name (not "Unidentified Person").
6. For each candidate, verify face crops exist in `data/embeddings.npy`.

**Note:** This analysis cannot inspect `data/identities.json` directly (data safety rule). The script design in Section 6 outlines how to do this programmatically.

### 5.4 Recommended Golden Set Structure

```json
{
  "version": 2,
  "subjects": [
    {
      "name": "Big Leon Capeluto",
      "identity_id": "<from registry>",
      "target_face": "Brass_Rail_Restaurant_with_Leon_Capeluto_Picture:face0",
      "positives": ["Image 992_compress:face0", "..."],
      "hard_negatives": ["Image 055_compress:face0"],
      "threshold": 1.20,
      "notes": "Original Leon Standard. ADR 007."
    },
    {
      "name": "<Subject 2>",
      "identity_id": "<from registry>",
      "target_face": "<best quality face>",
      "positives": ["<face_id_1>", "<face_id_2>", "..."],
      "hard_negatives": ["<similar looking different person>"],
      "threshold": 1.20,
      "notes": "Curator-verified."
    }
  ]
}
```

---

## 6. Golden Set Evaluation Script Design

### 6.1 Script: `scripts/evaluate_golden_set.py`

```
Purpose: Evaluate face recognition accuracy against the expanded golden set.
Mode: Read-only. Does NOT modify any data.
Dependencies: numpy, scipy (same as core/neighbors.py)
```

### 6.2 Pseudocode

```python
#!/usr/bin/env python3
"""
Golden Set Evaluation Script.

Evaluates face recognition quality across multiple subjects.
Read-only: does NOT modify embeddings, identities, or any data files.

Usage:
    python scripts/evaluate_golden_set.py [--verbose] [--output results.json]
"""

def main():
    # 1. Load golden set definition
    golden_set = load_json("evaluation/golden_set_v2.json")

    # 2. Load face embeddings (read-only)
    face_data = load_face_data("data/")  # face_id -> {mu, sigma_sq}

    # 3. For each subject in golden set:
    results = []
    for subject in golden_set["subjects"]:
        result = evaluate_subject(subject, face_data)
        results.append(result)

    # 4. Aggregate metrics
    report = {
        "timestamp": now_utc(),
        "subjects_tested": len(results),
        "subjects_passed": sum(1 for r in results if r["passed"]),
        "per_subject": results,
    }

    # 5. Print summary
    print_summary(report)

    # 6. Optionally save to evaluation/run_log_v2.jsonl
    if args.output:
        append_jsonl(args.output, report)

    # 7. Exit with code 0 if all pass, 1 if any fail
    sys.exit(0 if all(r["passed"] for r in results) else 1)


def evaluate_subject(subject, face_data):
    """
    Evaluate a single subject from the golden set.

    For each positive face:
      - Compute Euclidean distance to target face
      - Check distance <= threshold

    For each hard negative face:
      - Compute Euclidean distance to target face
      - Check distance > threshold

    Additionally, check WITHIN-IDENTITY CONSISTENCY:
      - For all pairs of positive faces (including target):
        - Compute pairwise distances
        - Report min, max, mean within-identity distance
        - Flag if max within-identity distance > threshold (inconsistency)
    """
    target_mu = face_data[subject["target_face"]]["mu"]
    threshold = subject["threshold"]

    # Test positives
    positive_results = []
    for pos_face_id in subject["positives"]:
        pos_mu = face_data[pos_face_id]["mu"]
        distance = euclidean_distance(target_mu, pos_mu)
        passed = distance <= threshold
        positive_results.append({
            "face_id": pos_face_id,
            "distance": distance,
            "passed": passed,
        })

    # Test hard negatives
    negative_results = []
    for neg_face_id in subject["hard_negatives"]:
        neg_mu = face_data[neg_face_id]["mu"]
        distance = euclidean_distance(target_mu, neg_mu)
        passed = distance > threshold
        negative_results.append({
            "face_id": neg_face_id,
            "distance": distance,
            "passed": passed,
        })

    # Within-identity consistency
    all_positive_faces = [subject["target_face"]] + subject["positives"]
    all_mus = [face_data[fid]["mu"] for fid in all_positive_faces]
    pairwise = cdist(all_mus, all_mus, metric='euclidean')
    # Extract upper triangle (exclude diagonal)
    upper = pairwise[np.triu_indices_from(pairwise, k=1)]

    consistency = {
        "within_identity_min": float(upper.min()),
        "within_identity_max": float(upper.max()),
        "within_identity_mean": float(upper.mean()),
        "all_within_threshold": bool(upper.max() <= threshold),
    }

    # Overall pass
    all_positives_pass = all(r["passed"] for r in positive_results)
    all_negatives_pass = all(r["passed"] for r in negative_results)

    return {
        "name": subject["name"],
        "target_face": subject["target_face"],
        "threshold": threshold,
        "passed": all_positives_pass and all_negatives_pass,
        "positive_results": positive_results,
        "negative_results": negative_results,
        "consistency": consistency,
        "margin": compute_margin(positive_results, negative_results),
    }


def compute_margin(positive_results, negative_results):
    """
    Compute the margin between the hardest positive and closest negative.

    Larger margin = more robust separation.
    """
    if not positive_results or not negative_results:
        return None

    hardest_positive = max(r["distance"] for r in positive_results)
    closest_negative = min(r["distance"] for r in negative_results)

    return closest_negative - hardest_positive
```

### 6.3 Key Design Decisions

1. **Read-only:** The script loads embeddings and golden set definition but writes nothing to `data/`.
2. **Within-identity consistency:** Goes beyond the existing `evaluate_recognition.py` by checking that ALL positive faces are mutually close, not just each-to-target.
3. **Margin reporting:** Quantifies how much headroom exists between the hardest positive and closest negative. A shrinking margin is an early warning.
4. **Multi-subject:** Unlike the current single-subject script, this supports N subjects in one run.
5. **JSONL logging:** Appends to a run log for tracking evaluation over time.
6. **Exit code:** CI-friendly -- can be used in pre-commit or CI pipeline.

---

## 7. Risk Assessment

### 7.1 What Could Go Wrong

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Modifying `core/neighbors.py` | N/A (FROZEN) | High -- could break all existing matches | Forensic Invariant #3. No changes allowed without evaluation plan. |
| Filtering REJECTED identities causes info loss | Low | Low -- rejected identities are explicitly unwanted | Reversible via "reset" action. Filter is post-hoc, not in neighbors.py. |
| Suggested-match for uploads causes false confidence | Medium | Medium -- admin might trust suggestion blindly | Mark as "suggestion" with distance shown. Require explicit merge action. |
| Golden set expansion misidentifies ground truth | Low | High -- invalid golden set corrupts evaluation | Require curator verification for each golden set subject. |
| Fusing embeddings changes distance profile | N/A (not proposed) | High -- could invalidate Leon Standard thresholds | NOT proposing fusion changes. Document only. |

### 7.2 Invariants That Must Be Preserved

1. **Immutable Embeddings:** `data/embeddings.npy` is never modified by any proposed change.
2. **Reversible Actions:** All new filtering/annotation can be undone.
3. **No Silent Math:** `core/neighbors.py` is not touched. Any distance calculation changes require a new ADR and evaluation run.
4. **Conservation of Mass:** No faces are deleted. REJECTED identities are filtered from display, not deleted.
5. **Human Authority:** All proposed improvements are advisory. No auto-merge, no auto-confirm.

### 7.3 Regression Testing Strategy

Before implementing any change:
1. Run `scripts/evaluate_recognition.py` to establish baseline (must PASS).
2. Implement change.
3. Run evaluation again (must still PASS).
4. For P1/P2 changes, verify manually that:
   - All previously confirmed identities still show correct neighbors.
   - No confirmed identity loses a match that was previously visible.
   - REJECTED identities correctly disappear from results (P1).

---

## 8. Implementation Priority

| Priority | Proposal | Effort | Risk | Impact |
|----------|----------|--------|------|--------|
| **P0** | Rejection memory | DONE | N/A | Already working |
| **P1** | Filter REJECTED-state from Find Similar | Small (post-filter in app/main.py) | Low | Reduces noise in results |
| **P4** | Golden set expansion | Medium (data curation + script) | Zero | Enables safe future ML changes |
| **P5** | Confidence indicator in UI | Small (display only) | Zero | Better admin decision-making |
| **P2** | Confirmed-identity matching for uploads | Medium (ingestion pipeline change) | Medium | Better inbox review experience |
| **P3** | Document merge-as-feedback | Zero (docs only) | Zero | Clarity |

### Recommended Sequence

1. **First:** P4 (Golden set expansion) -- creates the safety net needed before any other changes.
2. **Second:** P1 (Filter REJECTED state) -- small, safe, reduces noise.
3. **Third:** P5 (Confidence indicator) -- improves admin experience with zero algorithm risk.
4. **Fourth:** P2 (Confirmed-identity matching for uploads) -- largest impact but requires more careful testing.
5. **Skip:** P3 (documentation only, can be done anytime).

---

## Appendix A: File Reference

| File | Role |
|------|------|
| `/Users/nolanfox/rhodesli/core/config.py` | Threshold configuration (MATCH_THRESHOLD_HIGH=1.00, MATCH_THRESHOLD_MEDIUM=1.20, GROUPING_THRESHOLD=0.95) |
| `/Users/nolanfox/rhodesli/core/neighbors.py` | Find Similar algorithm (FROZEN). Best-linkage Euclidean distance. |
| `/Users/nolanfox/rhodesli/core/registry.py` | Identity registry with merge, detach, confirm, reject operations |
| `/Users/nolanfox/rhodesli/core/embeddings_io.py` | Atomic read/append for embeddings.npy |
| `/Users/nolanfox/rhodesli/core/ingest.py` | Original ingestion pipeline (InsightFace -> PFE) |
| `/Users/nolanfox/rhodesli/core/ingest_inbox.py` | Upload ingestion pipeline (InsightFace -> PFE -> INBOX identity) |
| `/Users/nolanfox/rhodesli/core/grouping.py` | Ingestion-time face grouping (Union-Find, threshold 0.95) |
| `/Users/nolanfox/rhodesli/core/pfe.py` | Probabilistic Face Embedding creation (mu + sigma_sq) |
| `/Users/nolanfox/rhodesli/core/fusion.py` | Bayesian anchor fusion (exists but unused by web app) |
| `/Users/nolanfox/rhodesli/core/clustering.py` | MLS-based clustering (offline only, not used at runtime) |
| `/Users/nolanfox/rhodesli/core/photo_registry.py` | Photo-face mapping for co-occurrence validation |
| `/Users/nolanfox/rhodesli/core/event_recorder.py` | JSONL event logging |
| `/Users/nolanfox/rhodesli/app/main.py` | Web app: all user action handlers, UI rendering |
| `/Users/nolanfox/rhodesli/evaluation/golden_set.json` | Current golden set (Big Leon Capeluto, 1 subject) |
| `/Users/nolanfox/rhodesli/evaluation/baselines/run_2_leon_benchmark.json` | Baseline evaluation results |
| `/Users/nolanfox/rhodesli/scripts/evaluate_recognition.py` | Current single-subject evaluation script |

## Appendix B: Glossary

- **PFE:** Probabilistic Face Embedding. A face representation with mean (mu) and uncertainty (sigma_sq).
- **MLS:** Mutual Likelihood Score. A probabilistic distance metric used in offline clustering but NOT in Find Similar.
- **Best-Linkage / Single Linkage:** Taking the minimum distance across all face pairs between two identities.
- **Leon Standard:** The calibration baseline derived from Big Leon Capeluto's photos (ADR 007).
- **Co-occurrence:** Two faces appearing in the same photo, proving they are different people.
- **Anchor:** A face confirmed as belonging to an identity.
- **Candidate:** A face suggested for an identity but not yet confirmed.
- **Negative:** A face explicitly rejected from an identity, or an identity pair marked "Not Same."
