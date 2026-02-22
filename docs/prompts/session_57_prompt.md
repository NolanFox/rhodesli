# Session 57 Prompt: CORAL Date Estimation → Production

## SESSION GOALS (in priority order)

1. **Export the trained CORAL date model to ONNX** — following the exact pattern from Session 55b (similarity calibration)
2. **Deploy the ONNX model to production** — lightweight inference via onnxruntime, no PyTorch in Docker
3. **Wire date estimation to the /estimate endpoint** — real ML inference replaces or augments the existing Gemini-only path
4. **Display date estimates in photo viewer UI** — decade + confidence bar on photo detail pages
5. **Apply the Gatekeeper pattern** — ML date estimates are proposals; admin reviews before they become canonical
6. **Session documentation + verification gate**

**The test for this session:** After deploying, uploading a photo to /estimate returns a date estimate from the local CORAL model (no Gemini API call needed). Photo detail pages show "circa 1930s" with a probability distribution. Admin can accept/correct date estimates.

## SCOPE

### IN SCOPE
- S1: ONNX export of trained CORAL date classifier
- S2: Production deployment of date ONNX model
- S3: /estimate endpoint wired to local model
- S4: Photo viewer date display + Gatekeeper UI
- S5: Regression gate verification
- S6: Verification gate + docs

### OUT OF SCOPE
- MLflow Dashboard → Session 58
- Face Compare Standalone Tier 1 (PRODUCT-001) → Session 59
- Gemini Progressive Refinement → Session 60
- Interactive Upload UX (SSE) → Session 61

## NON-NEGOTIABLE RULES
1. Commit after EVERY completed item or logical unit
2. Run `pytest tests/ -x -q` AND `pytest rhodesli_ml/tests/ -x -q` before each commit
3. Deploy via `git push` FREQUENTLY
4. **Serving Path Contract:** User-facing requests NEVER load PyTorch. Only ONNX Runtime for inference.
5. **Gatekeeper Pattern:** ML outputs are staged as proposals. Admin accepts/rejects/corrects before they go public.
6. **No training in production.** Only exported ONNX artifacts deploy.

## KEY FILES
- Best checkpoint: `rhodesli_ml/checkpoints/date-epoch=26-val/mae_decades=0.36.ckpt`
- Model: `rhodesli_ml/models/date_classifier.py` (DateEstimationModel, 253 lines)
- Calibration ONNX pattern: `rhodesli_ml/calibration/export_onnx.py` (175 lines)
- Calibration inference: `rhodesli_ml/calibration/inference.py` + `inference_onnx.py`
- /estimate handler: `app/main.py` lines 15024–15639
- Val transforms: Resize(257) → CenterCrop(224) → ToTensor → Normalize(ImageNet)
- Date dataset: `rhodesli_ml/data/date_dataset.py` — NUM_DECADES=11, 1900–2000
- Dockerfile: copies rhodesli_ml/calibration/ + rhodesli_ml/artifacts/
