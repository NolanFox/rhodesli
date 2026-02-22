# Session 58 Planning Context — MLflow Model Registry + Training Dashboard

## Breadcrumb: Why We're Here

### The original plan and why it was deprioritized

Session 58 was originally "MLflow Dashboard" — building a visible view
of experiment tracking data. This was called "table stakes" because
just showing training curves doesn't demonstrate ML thinking.

### What makes it higher leverage

Research revealed that the real value isn't a dashboard — it's wiring
the **MLflow Model Registry** into the existing ONNX export pipeline.
This transforms MLflow from "logging tool" into the **model lifecycle
management system** that governs how models get from training to
production. That's a fundamentally different portfolio story.

**Before:** "I use MLflow to track experiments" (table stakes)
**After:** "My models go through a registry with versioning, aliases,
and a regression gate before they reach production" (MLOps maturity)

### What already exists (Session 23 baseline)

- `rhodesli_ml/mlruns/` — local MLflow tracking directory
- PyTorch Lightning MLFlowLogger — logs metrics per epoch during
  training (loss, MAE, accuracy, learning rate, early stopping)
- At least one experiment: `rhodesli_date_estimation`
- Training runs logged from Session 23 (157 photos) and Session 25
  (250 photos, retrained)
- Similarity calibration runs may also be logged

### What's missing

1. **Model Registry:** No registered models, no versioning, no aliases
2. **ONNX artifacts not logged:** Models are exported to ONNX manually
   via `export_onnx.py` but not registered in MLflow
3. **No regression gate integration:** The gate runs separately from
   MLflow — results aren't logged as model version tags
4. **No promotion workflow:** No formal path from "trained" → "tested"
   → "deployed to production"
5. **README/docs:** No documentation of how to use MLflow in the project

### Known training runs to backfill

These runs should exist in `rhodesli_ml/mlruns/`:

| Run | Session | Dataset | Key Metrics |
|-----|---------|---------|-------------|
| CORAL v1 (initial) | 23 | 157 photos, Gemini labels | First training baseline |
| CORAL v2 (retrained) | 25 | 250 photos, 3 labeling passes | MAE 0.320, exact 73.2%, adj 96% |
| Similarity calibration | 55b | Pairwise similarity scores | Deployed as calibration_v1.onnx |

Claude Code should look for these in `mlruns/` and link them to the
registered models as earlier versions. The Session 25 run (250 photos)
should become the `@champion` for date-estimation.

---

## Session 57 Assessment (Pre-Session 58 Audit)

Session 57 completed in 40 min (estimated 1.5 hrs), all 6 phases
PASS, 3048 tests (+45 new), ONNX model 16.5MB. But speed raises
questions about completeness of the more complex phases.

### Items to verify in Phase 0.5

**1. CORAL probability conversion correctness**
The 9 ordinal logits → decade probabilities conversion (sigmoid →
cumulative → class probs) is the trickiest piece. If any step is
wrong, predictions look plausible but are silently incorrect. Need
to verify the app's implementation matches the documented formula
and that probabilities sum to ~1.0.

**2. Gatekeeper completeness**
Session 57 reported "existing date correction UI serves as Gatekeeper."
This likely means Phase 4 was simplified — reusing existing correction
UI rather than building the full proposal → "(unreviewed)" → admin
accept/correct/dismiss flow. Specific concerns:
- Are ML estimates labeled "(unreviewed)" on public pages?
- Do admin accept/correct/dismiss buttons exist for date estimates?
- Is there a `date_corrections.json` (or equivalent) that saves
  corrections as ground truth for future retraining?
- Do probability bars render on photo detail pages?

This matters for Session 58 because the Gatekeeper corrections
are what feed back into the retraining loop that MLflow tracks.

**3. Gemini supplementary UX**
The prompt specified /estimate shows CORAL results instantly with a
"Get Detailed Analysis" button for optional Gemini. Need to verify
this is a user-triggered action, not auto-running.

**4. Test coverage proportionality**
App tests went from 2631 → 2649 (+18). For a session that added
DateEstimationService, endpoint handler, probability conversion,
photo viewer integration, AND Gatekeeper UI, 18 app tests is light.
ML tests +27 is more proportional.

### Audit protocol

Phase 0.5 in the prompt runs grep/code checks to verify each item.
Findings are logged in the checkpoint. Issues become backlog items
but are NOT fixed in this session (ML-pipeline only scope).

---

## Architecture: Where MLflow Sits

```
Training (MacBook)              Production (Railway)
┌─────────────────────┐        ┌──────────────────────┐
│ train_date.py       │        │ Docker container     │
│   ↓                 │        │   ↓                  │
│ MLflow Logger       │        │ onnxruntime loads    │
│   ↓                 │        │ .onnx from artifacts/│
│ mlruns/ (metrics)   │        │   ↓                  │
│   ↓                 │        │ DateEstimationService│
│ Model Registry      │        │ CalibrationService   │
│   ↓                 │        └──────────────────────┘
│ export_onnx.py      │                ↑
│   ↓                 │                │
│ artifacts/*.onnx ───┼── git push ────┘
└─────────────────────┘

MLflow lives ENTIRELY on the MacBook.
Production only sees the exported ONNX files.
```

---

## Key Design Decision: Model Registry with Aliases

MLflow deprecated fixed stages (Staging/Production/Archived) in v2.9
in favor of **aliases** — mutable named pointers to model versions.

For Rhodesli, the workflow becomes:

1. Train model → log run to MLflow
2. Export ONNX → log ONNX artifact to MLflow via `mlflow.onnx.log_model()`
3. Register model version in registry (auto-incremented)
4. Run regression gate → tag version with `gate_status: passed/failed`
5. If passed, assign `@champion` alias to this version
6. `export_onnx.py` updated to pull from `@champion` alias
7. ONNX file copied to `rhodesli_ml/artifacts/` → git push → production

This means you can tell an interviewer: "When I retrain, the new model
gets a version number, runs through the regression gate, and only gets
the champion alias if it passes. The production deploy script always
pulls from @champion."

### Models to register

| Registered Model | Current Artifact | Versions |
|-----------------|------------------|----------|
| `rhodesli-date-estimation` | `date_estimation_v1.onnx` | 1+ |
| `rhodesli-similarity-calibration` | `calibration_v1.onnx` | 1+ |

---

## Higher-Leverage Additions (from research)

### 1. Log ONNX artifacts with signatures

MLflow's `mlflow.onnx.log_model()` records:
- The ONNX model itself as an artifact
- Input/output schema (via `ModelSignature`)
- Python dependencies
- Model lineage (which experiment/run produced it)

**Important:** Use `save_as_external_data=False` for both models.
Default is True (creates separate data files), but our models are
~20MB each and should be single files for simpler deployment.

This makes the model self-documenting and reproducible.

### 2. Tag model versions with regression gate results

After running `run_evaluation.py`, tag the model version with:
```python
client.set_model_version_tag(name, version, "gate_status", "passed")
client.set_model_version_tag(name, version, "val_mae", "0.320")
client.set_model_version_tag(name, version, "adjacent_accuracy", "0.96")
client.set_model_version_tag(name, version, "dataset_size", "250")
```

These tags are visible in `mlflow ui` and tell the full story.

### 3. Training comparison view

With multiple runs logged, `mlflow ui` gives you:
- Side-by-side metric comparison (v1 on 157 photos vs v2 on 250)
- Hyperparameter diff
- Training curve overlays
- Artifact browser (click to download any version's ONNX)

This is the "demo during interview" capability.

### 4. Automated promotion script

Create `rhodesli_ml/scripts/promote_model.py` that:
1. Takes a model name and run ID
2. Runs the regression gate
3. If passed → registers version, assigns @champion, copies ONNX
4. If failed → registers version, tags as failed, does NOT promote

This is the "CI/CD for ML" story.

---

## The Lifecycle Story (Portfolio Narrative)

The MLflow Model Registry completes a lifecycle that spans multiple
sessions:

1. **Session 47:** Gatekeeper pattern — ML outputs as proposals,
   admin accepts/corrects, corrections become ground truth anchors
2. **Session 57:** CORAL model in production — date estimates shown
   as proposals, admin can correct → corrections saved to
   `date_corrections.json`
3. **Session 58 (this):** MLflow Registry — versions, gate tags,
   promotion pipeline
4. **Future retraining:** When corrections accumulate (target: 500+
   photos), retrain CORAL → new version logged → regression gate →
   if improved, @champion alias moves → git push → production

The registry makes the retraining loop auditable: "version 1 trained
on 250 Gemini labels, version 2 trained on 250 Gemini + 47 admin
corrections, and the regression gate shows MAE improved from 0.320
to 0.28." That's the story you tell in interviews.

Without the registry, this is just "I retrained the model." With it,
it's "I have a versioned, gated, auditable model lifecycle."

---

## Deferred Items

| Item | Target Session |
|------|---------------|
| Face Compare Standalone Tier 1 | 59 (PRODUCT-001) |
| Gemini Progressive Refinement | 60 |
| Interactive Upload UX (SSE) | 61 |
| Admin/Public UX Unification | 62 |
| Docker Image Slimming | 63+ |

---

## Risk Register

| Risk | Mitigation |
|------|------------|
| MLflow version compatibility | Pin version in pyproject.toml |
| Registry requires DB backend for UI | Use local SQLite (default) |
| Existing mlruns/ data loss | Back up before any migration |
| Session scope creep | This is ~30 min. Don't build UI pages. |
