"""ONNX Runtime inference for calibrated similarity scoring.

Lightweight alternative to PyTorch inference (15MB vs 500MB).
Used in production on Railway where PyTorch is not installed.

Decision provenance: AD-128 (ONNX for production serving).
"""

from pathlib import Path

import numpy as np


class ONNXCalibrationInference:
    """ONNX Runtime-based calibration model inference."""

    def __init__(self, model_path: str | Path):
        import onnxruntime as ort

        self.session = ort.InferenceSession(
            str(model_path),
            providers=["CPUExecutionProvider"],
        )

    def predict(self, emb_a: np.ndarray, emb_b: np.ndarray) -> float:
        """Predict P(same_person) for a single embedding pair.

        Args:
            emb_a: (512,) or (1, 512) numpy array
            emb_b: (512,) or (1, 512) numpy array

        Returns:
            Float probability in [0, 1]
        """
        a = emb_a.reshape(1, -1).astype(np.float32)
        b = emb_b.reshape(1, -1).astype(np.float32)
        result = self.session.run(
            None,
            {"embedding_a": a, "embedding_b": b},
        )
        return float(result[0][0][0])

    def predict_batch(
        self, query_emb: np.ndarray, candidate_embs: np.ndarray
    ) -> np.ndarray:
        """Predict P(same_person) for one query vs many candidates.

        Args:
            query_emb: (512,) numpy array
            candidate_embs: (N, 512) numpy array

        Returns:
            (N,) numpy array of probabilities
        """
        n = len(candidate_embs)
        q = np.broadcast_to(
            query_emb.reshape(1, -1).astype(np.float32), (n, query_emb.shape[-1])
        ).copy()  # copy needed for contiguous memory
        c = candidate_embs.astype(np.float32)
        result = self.session.run(
            None,
            {"embedding_a": q, "embedding_b": c},
        )
        return result[0].flatten()
