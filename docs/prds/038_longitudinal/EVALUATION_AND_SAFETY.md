# PRD-038: Evaluation Framework & Retroactive Improvement Safety

**Parent**: [docs/prds/038_longitudinal_face_modeling.md](../038_longitudinal_face_modeling.md)

---

## Evaluation Framework

### The Problem
We need to quantify whether each improvement (WS-1 through WS-5) actually delivers value. Without rigorous evaluation, we can't distinguish real improvement from noise, and we risk deploying changes that look good on average but hurt specific cases.

### Golden Test Set Design

**Hold-out methodology**:
1. Select 20% of confirmed identities as held-out test set (stratified by community, decade, face count)
2. These identities are NEVER used for calibration training or LoRA fine-tuning
3. For each held-out identity, measure: "Given face X, does the system rank the correct identity in top-1, top-3, top-5?"
4. Report: Rank-1 accuracy, AUC, precision@recall curves

**Cross-validation for small datasets**:
- With only 69 confirmed identities, 20% hold-out = 14 identities (small)
- Alternative: 5-fold cross-validation, report mean ± std for all metrics
- Each fold trains on 4/5 identities, evaluates on 1/5
- Ensures every identity participates in evaluation

**Photo hold-out for retroactive testing**:
- For identities with 3+ anchors, hold out 1 anchor as "unseen test photo"
- Simulate: "If this photo arrived new, would the system find the right identity?"
- This tests the complete pipeline (quality weighting → age penalty → calibration → ranking)
- Run this test BEFORE and AFTER each improvement to measure delta

### Evaluation Script Design
```bash
# Full evaluation suite
python scripts/evaluate_ml.py --mode full

# Quick check (just AUC + rank-1 on golden set)
python scripts/evaluate_ml.py --mode quick

# A/B comparison (before vs after a change)
python scripts/evaluate_ml.py --mode compare \
  --baseline rhodesli_ml/artifacts/calibration_v1.pt \
  --candidate rhodesli_ml/artifacts/calibration_v2.pt

# Held-out photo simulation
python scripts/evaluate_ml.py --mode holdout-sim \
  --holdout-fraction 0.2 --seed 42
```

### Metrics to Track Per Improvement

| Metric | What it measures | Good direction |
|--------|-----------------|----------------|
| **AUC** | Overall ranking quality | Higher |
| **Rank-1 accuracy** | "Is the right person first?" | Higher |
| **Precision@90recall** | How many suggestions are correct at high recall | Higher |
| **Cross-era recall** | Do we find same person across 30+ year gaps? | Higher |
| **Family false positive rate** | Do we confuse father for son? | Lower |
| **New-photo hit rate** | "Would this new photo find its person?" | Higher |
| **Calibration ECE** | How well-calibrated are probability scores? | Lower |

### Evaluation Cadence
- **Before every deploy**: `evaluate_ml.py --mode quick` (30 seconds)
- **After WS completion**: `evaluate_ml.py --mode full` (5 minutes)
- **After LoRA training**: `evaluate_ml.py --mode full --mode holdout-sim` (10 minutes)
- **Monthly**: Full evaluation + report to `docs/ml/EVALUATION_REPORTS/`

---

## Retroactive Cluster Improvement

### The Challenge
As ML improves, it may discover that:
1. Two separate identities should be merged (found connection)
2. An existing cluster has a misassigned face (found error)
3. A face in INBOX matches a confirmed identity (new discovery)

Each of these requires different handling to avoid breaking the user experience.

### Safety Rules

**Rule 1: NEVER break confirmed clusters**
- If the model suggests splitting a CONFIRMED identity, it's a PROPOSAL, not an action
- Confirmed clusters are human-verified ground truth (AD-006: provenance="human" > provenance="model")
- Even if the model is 99.9% confident, the admin reviews first

**Rule 2: Additions are proposals, not actions**
- When the model discovers a new face that matches a confirmed identity:
  - DO NOT auto-add to the identity
  - DO create a Discovery notification: "Our algorithm found a new photo that may be [Name]. Can you confirm?"
  - This appears in Discoveries page AND as a notification
  - Admin confirms → face added to identity (human provenance)
  - Admin rejects → face goes to `negative_ids` (improves future matching)

**Rule 3: Retroactive re-clustering is additive only**
- After an ML improvement (new calibration, LoRA, etc.), re-run clustering
- NEW proposals may be generated (faces that now match above threshold)
- EXISTING proposals are NOT revoked (they were above the old threshold)
- CONFIRMED matches are NEVER touched
- Result: monotonically increasing discovery count, never decreasing

**Rule 4: Community-scoped retroactive improvement**
- Re-clustering must respect community boundaries
- A Fox Family face can be proposed to match a Rhodes identity (cross-community)
- But the proposal must indicate "From Fox Family" badge
- Admin of EACH community must approve cross-community matches
- Retroactive improvement within a single community is straightforward
- Cross-community proposals use the existing cross-community badge system (Session 96c-d)

### Notification Flow for Retroactive Discoveries

```
ML improvement deployed
  → Re-cluster all unresolved faces
  → For each new match above threshold:
    IF target identity is CONFIRMED:
      → Create Discovery notification
      → "Our algorithm discovered that [face] may be [Name] (87% confidence)"
      → Admin sees in Discoveries page + bell icon
      → Confirm: face added as anchor (human provenance)
      → Reject: face added to negative_ids
    IF target identity is PROPOSED:
      → Add as candidate_id (same as current behavior)
    IF target identity is INBOX:
      → Propose merge (same as current behavior)
```

### What This Looks Like in the UI
1. Admin opens app after ML improvement deploy
2. Bell icon shows "3 new discoveries"
3. Notifications page: "Algorithm update found 3 potential new matches"
4. Each discovery card shows:
   - The newly matched face (large)
   - The existing identity it matches (with existing anchors)
   - Confidence score and which improvement found it
   - "Confirm" / "Not Same Person" buttons
5. Admin reviews, confirms 2, rejects 1
6. Confirmed faces now appear on the identity page
7. Rejected face improves future matching (hard negative)

---

## Community Resilience

### Invariants That Must Hold
1. **No data loss**: Retroactive improvement never removes a face from a cluster
2. **No cross-contamination**: Community A's data doesn't pollute Community B's view
3. **Transparent provenance**: Every change shows WHERE it came from and WHO approved it
4. **Reversible**: Any retroactive addition can be undone (detach face)
5. **Notification-driven**: Admin is ALWAYS informed before data changes

### Cross-Community Safety
- Community-scoped clustering: When re-clustering Fox Family, only Fox Family photos participate in primary matching
- Cross-community proposals: If a Fox Family face matches a Rhodes identity, it appears as a cross-community Discovery with explicit badge
- Community admin authority: Each community's admin approves their own matches
- No cascade effects: Confirming a cross-community match doesn't trigger further cross-community proposals

### Testing for Community Resilience
```
TEST: Retroactive improvement does not break existing communities
  - Confirm 5 Fox Family identities
  - Run retroactive re-clustering
  - Assert: All 5 confirmed identities still have same anchor_ids
  - Assert: No Fox Family faces appear in Rhodes clusters without proposal
  - Assert: Cross-community proposals have "From Fox Family" badge

TEST: Community-scoped re-clustering isolation
  - Add improvement to clustering (e.g., quality weighting)
  - Re-cluster Fox Family only
  - Assert: Rhodes clustering unchanged
  - Assert: Fox Family may have new proposals
  - Assert: No data from other communities leaked in

TEST: Notification flow for retroactive discoveries
  - Deploy ML improvement
  - Re-cluster → 3 new matches found for confirmed identities
  - Assert: 3 Discovery notifications created
  - Assert: Admin sees bell icon with count
  - Assert: No faces auto-added to identities
  - Confirm 2, reject 1
  - Assert: 2 faces added as anchors, 1 in negative_ids
```

---

## Continuous Improvement Flywheel

The complete system creates a virtuous cycle:

```
More communities added (data growth)
  → More photos of same people across decades
  → Admin confirms identities (via active learning UI)
  → Calibration pairs accumulate in Supabase
  → Recalibration improves threshold accuracy
  → Better clustering → better proposals → easier admin review
  → More confirmations → more LoRA training data
  → LoRA improves embeddings → better matching across age gaps
  → Retroactive re-clustering finds NEW matches in old data
  → Discoveries notifications surface them to admin
  → Admin confirms → more data → cycle continues
```

Each step in the cycle feeds the next. The system gets smarter with every admin interaction, every new photo, and every new community added.

---

## Breadcrumbs
- Gatekeeper pattern: AD-006 (provenance hierarchy)
- Notification system: PRD-028 (bell icon, /notifications)
- Community scoping: AD-213, AD-216 (photo-derived identity sets)
- Cross-community badges: Session 96c-d implementation
- Retroactive clustering: AD-179 (two-tier auto-clustering)
- Discovery notifications: DD-003 (notification design)
