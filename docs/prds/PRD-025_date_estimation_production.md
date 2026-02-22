# PRD-025: CORAL Date Estimation in Production

## Problem
The CORAL date classifier is trained and evaluated locally (MAE 0.36 decades,
~96% adjacent accuracy) but exists only as a PyTorch checkpoint. Users uploading
photos to /estimate get Gemini API results only — slow, costs money per call,
and requires an API key.

## Solution
Export the trained model to ONNX and deploy it alongside the existing similarity
calibration model. The /estimate endpoint uses the local ONNX model for instant
inference (no API call, no cost).

## Target User
- Public users uploading photos to /estimate
- Admin reviewing date estimates for accuracy
- Nolan demonstrating the ML pipeline in interviews

## Requirements
1. ONNX export produces equivalent predictions to PyTorch checkpoint
2. /estimate returns date estimate in < 2 seconds (no API call)
3. Photo detail pages show decade estimate + confidence distribution
4. Admin can accept, correct, or reject ML date estimates (Gatekeeper)
5. Accepted estimates become ground truth for future retraining
6. Existing Gemini labels remain visible (higher quality)

## Acceptance Criteria
- [ ] ONNX model loads in production (verify via railway logs)
- [ ] /estimate with photo upload returns decade prediction
- [ ] Photo viewer shows "circa 1930s" with probability bars
- [ ] Admin date review interface works
- [ ] Corrected dates persist and feed back to training data
- [ ] Both test suites pass
- [ ] Verified in production browser

## Architecture
- Model: EfficientNet-B0 + CORAL ordinal head (16.5 MB ONNX)
- Input: 224x224 RGB, ImageNet normalized
- Output: 10 ordinal logits → 11 decade probabilities (1900s–2000s)
- Serving: ONNX Runtime on CPU, < 100ms per image
- Fallback: Gemini API for detailed evidence when ONNX unavailable
