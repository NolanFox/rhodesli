"""ONNX Runtime inference for date estimation.

Lightweight alternative to PyTorch inference (15MB vs 500MB+).
Used in production on Railway where PyTorch is not installed.

The CORAL model outputs ordinal logits which are converted to
decade probabilities via sigmoid-based cumulative probability extraction.

Decision provenance: AD-129 (ONNX for date estimation serving).
"""

from pathlib import Path

import numpy as np


class ONNXDateEstimationInference:
    """ONNX Runtime-based date estimation inference.

    Takes a preprocessed image tensor and returns decade predictions
    with probability distributions.
    """

    # 11 decades: 1900s through 2000s
    DECADES = [1900, 1910, 1920, 1930, 1940, 1950, 1960, 1970, 1980, 1990, 2000]

    def __init__(self, model_path: str | Path):
        import onnxruntime as ort

        self.session = ort.InferenceSession(
            str(model_path),
            providers=["CPUExecutionProvider"],
        )

    def predict_from_tensor(self, image_tensor: np.ndarray) -> dict:
        """Predict date from a preprocessed image tensor.

        Args:
            image_tensor: (1, 3, 224, 224) or (3, 224, 224) float32,
                          already ImageNet-normalized.

        Returns:
            Dict with predicted_decade, confidence, decade_probabilities, etc.
        """
        if image_tensor.ndim == 3:
            image_tensor = image_tensor[np.newaxis, ...]
        image_tensor = image_tensor.astype(np.float32)

        # Run ONNX inference
        logits = self.session.run(None, {"image": image_tensor})[0]

        # Convert CORAL ordinal logits to decade probabilities
        probs = self._ordinal_logits_to_probs(logits[0])

        # Derive predictions
        predicted_idx = int(np.argmax(probs))
        predicted_decade = self.DECADES[predicted_idx]
        confidence = float(probs[predicted_idx])

        # Expected year: weighted average of decade midpoints
        midpoints = [d + 5 for d in self.DECADES]
        expected_year = sum(m * p for m, p in zip(midpoints, probs))

        return {
            "predicted_decade": predicted_decade,
            "confidence": round(confidence, 3),
            "decade_probabilities": {
                str(d): round(float(p), 4) for d, p in zip(self.DECADES, probs)
            },
            "expected_year": round(expected_year),
            "source": "coral_v1",
        }

    def predict_from_image(self, image: np.ndarray) -> dict:
        """Predict date from a raw RGB image (any size).

        Args:
            image: HWC uint8 RGB image (any size).

        Returns:
            Dict with predicted_decade, confidence, decade_probabilities, etc.
        """
        tensor = self._preprocess(image)
        return self.predict_from_tensor(tensor)

    def _ordinal_logits_to_probs(self, logits: np.ndarray) -> np.ndarray:
        """Convert CORAL ordinal logits to class probabilities.

        P(class > k) = sigmoid(logit_k) for k = 0..K-2
        P(class = k) = P(class > k-1) - P(class > k)
        with P(class > -1) = 1.0 and P(class > K-1) = 0.0

        Args:
            logits: (K-1,) array of ordinal logits.

        Returns:
            (K,) array of class probabilities summing to 1.0.
        """
        # Clip to avoid overflow in exp
        logits_clipped = np.clip(logits, -20, 20)
        cumprobs = 1.0 / (1.0 + np.exp(-logits_clipped))

        num_classes = len(self.DECADES)
        probs = np.zeros(num_classes)

        # P(class = 0) = 1 - P(class > 0)
        probs[0] = 1.0 - cumprobs[0]
        # P(class = k) = P(class > k-1) - P(class > k) for 1..K-2
        for k in range(1, len(cumprobs)):
            probs[k] = cumprobs[k - 1] - cumprobs[k]
        # P(class = K-1) = P(class > K-2)
        probs[-1] = cumprobs[-1]

        # Clamp and normalize for numerical stability
        probs = np.clip(probs, 0, 1)
        total = probs.sum()
        if total > 0:
            probs /= total

        return probs

    def _preprocess(self, image: np.ndarray) -> np.ndarray:
        """Preprocess raw image to match training val transforms.

        Training used: Resize(257) → CenterCrop(224) → ToTensor → Normalize(ImageNet)
        We replicate this exactly using PIL + numpy.

        Args:
            image: HWC uint8 RGB image (any size).

        Returns:
            (1, 3, 224, 224) float32 tensor, ImageNet-normalized.
        """
        from PIL import Image

        img = Image.fromarray(image)

        # Resize shortest side to 257 (Resize(int(224 * 1.15)) ≈ 257)
        w, h = img.size
        target_size = 257
        if w < h:
            new_w = target_size
            new_h = int(h * target_size / w)
        else:
            new_h = target_size
            new_w = int(w * target_size / h)
        img = img.resize((new_w, new_h), Image.BILINEAR)

        # Center crop to 224x224
        w, h = img.size
        left = (w - 224) // 2
        top = (h - 224) // 2
        img = img.crop((left, top, left + 224, top + 224))

        # To float32 [0, 1]
        arr = np.array(img, dtype=np.float32) / 255.0

        # ImageNet normalization
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        arr = (arr - mean) / std

        # HWC → CHW, add batch dimension
        arr = arr.transpose(2, 0, 1)[np.newaxis, ...]

        return arr
