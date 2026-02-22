# Session 57 Planning Context — CORAL Date Estimation → Production

## Breadcrumb: Why We're Here

### Journey to this session

1. **Session 16 (Track C):** Created `rhodesli_ml/` package structure, signal_harvester.py, config YAMLs, skeleton training files
2. **Session 23:** Built the full date estimation pipeline — CORAL ordinal regression model (EfficientNet-B0), heritage augmentations, Gemini silver label generation, regression gate, MLflow tracking, 53 ML tests
3. **Sessions 24-25:** Ran Gemini labeling — 250 photos labeled across 3 passes. Model retrained: val MAE 0.320, exact accuracy 73.2%, adjacent accuracy 96%
4. **Session 47:** Established the Gatekeeper pattern — ML outputs are proposals, admin accepts/rejects before public display. Applied to birth year estimates first.
5. **Session 55b:** Proved the ONNX serving pattern — similarity calibration model exported from PyTorch, deployed as ONNX artifact, served via onnxruntime in production Docker container
6. **Session 56:** Landing page refresh, P1 UX polish, lazy loading. App is now shareable.
7. **Session 57 (this session):** Apply the same 55b pattern to the CORAL date model.

### Why CORAL before other ML work

From the strategic evaluation (pre-Session 57 planning):

- **Novelty:** CORAL ordinal regression for date estimation from historical photos is unusual. Interviewers won't have heard of it. The portfolio story writes itself.
- **Infrastructure reuse:** The ONNX export + serve pattern from 55b is proven and identical. No new infrastructure needed.
- **MLflow Dashboard (Session 58):** Deprioritized — table stakes tooling, doesn't demonstrate ML thinking. Can be folded into a future session as a 15-minute add-on.
- **Face Compare Standalone (Session 59):** Strong for product thinking but less urgent now that the landing page exists as a shareable demo.

---

## What Already Exists (as of Session 56 completion)

### ML artifacts built in Sessions 23-25

| Artifact | Location | Status |
|----------|----------|--------|
| CORAL date classifier | `rhodesli_ml/models/date_classifier.py` | ✓ Trained |
| EfficientNet-B0 backbone | Pretrained weights, fine-tuned | ✓ Complete |
| Heritage augmentations | `rhodesli_ml/data/augmentations.py` | ✓ 7 transforms |
| Training script | `rhodesli_ml/training/train_date.py` | ✓ Working |
| Gemini silver labels | `rhodesli_ml/data/date_labels.json` | ✓ 250 labels |
| Regression gate | `rhodesli_ml/evaluation/regression_gate.py` | ✓ Working |
| ONNX export script | `rhodesli_ml/scripts/export_onnx.py` | ✓ For calibration |
| Best checkpoint | `rhodesli_ml/checkpoints/best.ckpt` | ✓ Trained |
| ML tests | `rhodesli_ml/tests/` | ✓ 53+ tests |

### Production infrastructure from Session 55b

| Component | Status |
|-----------|--------|
| onnxruntime in requirements.txt | ✓ Already deployed |
| calibration_v1.onnx in Docker | ✓ Working pattern |
| ONNX inference in production | ✓ Proven at scale |
| Health check for ML models | ✓ Reports model status |

### Model performance (from Session 25 retraining)

| Metric | Value | Gate Threshold |
|--------|-------|----------------|
| Val MAE | 0.320 decades | ≤ 1.5 |
| Exact accuracy | 73.2% | — |
| Adjacent accuracy (±1 decade) | 96% | ≥ 70% |
| Early stopping epoch | 22 | — |
| Training photos | 250 | — |
| Known gap: 1980s recall | 0% (7 samples) | Exempted (too few) |

---

## Technical Decisions Pre-Made

### AD: CORAL logit → probability conversion

CORAL outputs 9 logits representing P(decade > k) for k = 0..8.
To get class probabilities:
```
cumprobs[k] = sigmoid(logit[k])
P(decade=0) = 1 - cumprobs[0]
P(decade=k) = cumprobs[k-1] - cumprobs[k]  for k=1..8
P(decade=9) = cumprobs[8]
```
Then clip and normalize for numerical stability.

### AD: Expected year from probability distribution

```
expected_year = sum(decade_midpoint * probability for each decade) 
where decade_midpoint = decade_start + 5 (e.g., 1935 for 1930s)
```
This gives sub-decade resolution even with decade-level classes.

### AD: Preprocessing must match training

The ONNX model expects:
- Input: (batch, 3, 224, 224) float32 tensor
- Normalization: ImageNet mean [0.485, 0.456, 0.406], std [0.229, 0.224, 0.225]
- Resize: 224x224 (bilinear)
- Channel order: RGB

**If preprocessing differs between training and serving, predictions will be wrong.** Validate this explicitly.

---

## Deferred Items (tracked with target sessions)

| Item | Target Session | BACKLOG ID |
|------|---------------|------------|
| MLflow Dashboard | 58 (or fold in) | — |
| Face Compare Standalone Tier 1 | 59 | PRODUCT-001 |
| Gemini Progressive Refinement | 60 | — |
| Interactive Upload UX (SSE) | 61 | — |
| Admin/Public UX Unification | 62 | — |
| Docker Image Slimming | 63+ | — |
| Year-level training (at 500+ photos) | Future | — |
| 1980s recall improvement (need more data) | Future | — |
| Active learning from Gatekeeper corrections | Future | — |
| LoRA backbone fine-tuning | Future (if calibration plateaus) | — |

---

## Risk Register

| Risk | Mitigation |
|------|------------|
| ONNX export fails for CORAL architecture | Use existing calibration export as template; CORAL is standard PyTorch ops |
| Preprocessing mismatch train vs serve | Explicit validation: run same 5 images through both paths, compare |
| Docker image size increase | date_estimation_v1.onnx should be ~20MB (EfficientNet-B0). Acceptable. |
| /estimate breaks existing Gemini flow | Graceful fallback: if ONNX model missing, fall back to Gemini-only |
| Gatekeeper adds too much complexity | Start with minimal: just show date on photo pages. Full admin review can be Phase 4 stretch goal |

---

## Session 56 → 57 Handoff Notes

Session 56 was the "adoption session" — making the app shareable. Landing page refresh, P1 UX fixes, lazy loading. The app should now be presentable to interviewers.

Session 57 adds the second ML model to production. This makes the portfolio story concrete: "I have TWO custom models running in production — face similarity calibration and photo date estimation — both trained in PyTorch and served via ONNX."

After this session, the most impactful next steps are:
1. Interactive demo for interviews (Session 59: Face Compare Standalone)
2. LoRA fine-tuning (when similarity calibration plateaus)
3. MLflow dashboard (lowest priority — can show interviewer MLflow locally)
