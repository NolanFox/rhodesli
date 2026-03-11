# PRD-038: Evaluation, Safety, And Rollout

**Parent**: [docs/prds/038_longitudinal_face_modeling.md](../038_longitudinal_face_modeling.md)
**Reviewed**: 2026-03-11

---

## Current Baseline Snapshot

- `data/golden_set.json` is stale at **125 mappings / 23 identities**.
- The repo currently contains **84 confirmed identities** and **28** with 2+ faces.
- Existing eval commands currently fail on mixed embedding schemas (`mu` plus legacy `embeddings`).
- A schema-aware local spot check on the current golden set gives:
  - Euclidean AUC about **0.978**
  - MLS AUC about **0.953**
  - Euclidean distance threshold at precision >= 0.90 about **1.196**

**Implication**: Phase 0 must repair evaluation before any matcher change is trusted.

---

## Eval Assets To Build

## 1. Golden Set V2

- Rebuild from all current confirmed identities.
- Version it so future baselines are comparable.
- Store both:
  - face-to-identity mappings
  - metadata slices needed for analysis

## 2. Longitudinal Slice Set

- Build from same-identity pairs with date coverage.
- Required buckets:
  - 0-9 years
  - 10-19 years
  - 20-29 years
  - 30+ years

## 3. Kinship Confusion Set

- Different-person pairs with GEDCOM or surname-family proximity.
- This is the slice most likely to regress if the system chases recall too aggressively.

## 4. Quality Slice Set

- Bucket by `det_score`, `quality`, and uncertainty.
- Required because the proposed scorer explicitly uses quality-aware logic.

## 5. Shadow Replay Set

- Snapshot unresolved faces and current proposal outputs.
- Use this to compare scorer versions before rollout.

## 6. Dominant-Identity Bias Set

- Build a slice that isolates overrepresented identities and families.
- Track whether the reranker gains are concentrated only on the biggest families.

---

## Mandatory Metrics

### Core Retrieval Metrics

- Rank-1
- Rank-3
- MRR
- ROC-AUC
- PR-AUC

### Slice Metrics

- Recall on year-gap >= 20
- Recall on year-gap >= 30
- Same-family false positive rate
- Dominant-identity lift vs non-dominant-identity lift
- Cross-community leakage count
- Quality-bucket Rank-1

### Product Metrics

- Precision of Tier 1 auto-adds on review sample
- Precision of discovery suggestions on review sample
- Label yield from active-learning queue
- Share of queue coming from underrepresented identities

---

## Gate Criteria By Phase

## Phase 0 Gate

- Eval CLI runs on current schema without manual patching.
- Golden Set V2 generated successfully.
- Baseline JSON report saved and reproducible.

## Phase 2 Gate: Frozen-Embedding Reranker

- Rank-1 and Rank-3 do not regress by more than 1 point.
- Recall on year-gap >= 20 improves by at least 5 points.
- Same-family false positive rate is flat or improved.
- Gains are not confined to the most overrepresented identities.
- No new community leakage in shadow replay.
- Top 50 changed proposals reviewed manually before enablement.

## Phase 3 Gate: Active Learning

- Queue excludes already labeled pairs.
- Queue diversity rule holds:
  - no more than 2 pairs from the same identity in a batch of 10
- At least 30% of surfaced pairs come from underrepresented identities or hard slices.
- Recent labels can be audited and reverted before recalibration consumes them.

## Phase 4 Gate: Adapter / LoRA

- Pass identity-held-out evaluation.
- Pass family-held-out evaluation.
- Pass community-held-out evaluation if cross-community data is in scope.
- Improve at least one hard slice without harming kinship safety or high-quality buckets.

---

## Rollout Plan

1. Build the new scorer behind a flag.
2. Run shadow mode on unresolved faces.
3. Diff current vs candidate proposals.
4. Review the highest-impact proposal changes manually.
5. Enable in batch upload path first.
6. Only after stability, switch proposal-generation paths that still use `cluster_new_faces.py`.
7. Keep local and future cloud workers on the same artifact contract so rollout semantics do not change when execution moves off the laptop.

---

## Safety Invariants

1. Confirmed identities remain human ground truth.
2. New scorer outputs are proposals, not automatic facts.
3. Cross-community proposals stay visibly labeled.
4. Rollback is artifact-based and immediate.
5. All eval artifacts are versioned so regressions are explainable.
6. Cloud migration may change where jobs run, not how they are evaluated or approved.

---

## Tests That Must Exist

```text
TEST: eval loader accepts mixed embedding schemas
  - Build a fixture with `mu` rows and `embeddings` rows
  - Assert: single eval CLI run succeeds

TEST: golden set v2 includes all current confirmed identities
  - Build from fixture registry with merged + confirmed + inbox identities
  - Assert: only confirmed, non-merged faces included

TEST: scorer shadow diff is community-safe
  - Run baseline scorer and candidate scorer on mixed-community fixture
  - Assert: all new cross-community proposals carry review metadata

TEST: longitudinal slice report is generated
  - Fixture with year gaps 5, 15, 25, 35
  - Assert: metrics emitted for all required buckets

TEST: kinship safety gate blocks regressions
  - Candidate scorer improves global Rank-1 but worsens same-family FP rate
  - Assert: rollout gate fails

TEST: dominant-identity bias gate blocks misleading wins
  - Candidate scorer improves only on the top 2 most-overrepresented identities
  - Assert: rollout gate fails

TEST: active-learning labels remain reversible
  - Queue label is written, then reverted before recalibration
  - Assert: recalibration export excludes the reverted label
```

---

## Retroactive Improvement Policy

- Retroactive re-scoring is allowed.
- Retroactive auto-merge is not.
- Existing confirmed anchors are never removed by the model.
- New discoveries are additive proposals with explicit review state.

That preserves the gatekeeper model while still letting the archive improve as labels accumulate.
