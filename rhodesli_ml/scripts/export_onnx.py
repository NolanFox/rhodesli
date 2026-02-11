"""Export trained PyTorch models to ONNX for production inference.

Usage:
    python -m rhodesli_ml.scripts.export_onnx --model calibrator --checkpoint path/to/ckpt
"""

# Placeholder — will be implemented after first model training.
#
# Models to export:
# - Similarity calibrator (MLP, ~10KB ONNX)
# - Date classifier (EfficientNet-B0, ~20MB ONNX)
#
# Production inference uses onnxruntime (no PyTorch dependency on server).
