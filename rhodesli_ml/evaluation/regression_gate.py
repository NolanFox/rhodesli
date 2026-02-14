"""Regression gate: evaluates date estimation model before deployment.

Computes metrics on a held-out set and checks if the model passes
quality gates. Nothing touches production without passing ALL gates.

Metrics:
    - Mean Absolute Error (in decades)
    - Exact accuracy (predicted decade = true decade)
    - Adjacent accuracy (within +-1 decade)
    - Per-decade precision/recall
    - Calibration: high confidence -> higher accuracy
    - Brier score on probability distributions

Usage:
    python -m rhodesli_ml.scripts.run_evaluation --model checkpoints/best.ckpt --data labels.json
"""

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch

from rhodesli_ml.models.date_classifier import (
    DateEstimationModel,
    ordinal_logits_to_probs,
    probs_to_predicted_class,
)
from rhodesli_ml.data.date_dataset import (
    NUM_DECADES,
    index_to_decade,
    decade_to_index,
    decade_probs_to_tensor,
)


class GateResult:
    """Result of running the regression gate."""

    def __init__(self, metrics: dict, per_decade: dict, gate_config: dict):
        self.metrics = metrics
        self.per_decade = per_decade
        self.gate_config = gate_config
        self.failure_reasons = []
        self._check_gates()

    def _check_gates(self):
        """Check all gate criteria and populate failure_reasons."""
        cfg = self.gate_config

        # Adjacent accuracy gate
        min_adjacent = cfg.get("min_adjacent_accuracy", 0.70)
        if self.metrics["adjacent_accuracy"] < min_adjacent:
            self.failure_reasons.append(
                f"Adjacent accuracy {self.metrics['adjacent_accuracy']:.3f} < {min_adjacent}"
            )

        # MAE gate
        max_mae = cfg.get("max_mae_decades", 1.5)
        if self.metrics["mae_decades"] > max_mae:
            self.failure_reasons.append(
                f"MAE {self.metrics['mae_decades']:.3f} > {max_mae}"
            )

        # Per-decade recall gate
        min_recall = cfg.get("min_decade_recall", 0.20)
        for decade_str, stats in self.per_decade.items():
            if stats["n"] >= 5 and stats["recall"] < min_recall:
                self.failure_reasons.append(
                    f"Decade {decade_str} recall {stats['recall']:.3f} < {min_recall} (n={stats['n']})"
                )

        # Calibration gate (high > medium > low accuracy)
        if (
            self.metrics.get("accuracy_high") is not None
            and self.metrics.get("accuracy_medium") is not None
            and self.metrics["accuracy_high"] < self.metrics["accuracy_medium"]
        ):
            self.failure_reasons.append(
                f"Calibration failure: high conf accuracy {self.metrics['accuracy_high']:.3f} "
                f"< medium {self.metrics['accuracy_medium']:.3f}"
            )

    @property
    def passed(self) -> bool:
        return len(self.failure_reasons) == 0

    def to_dict(self) -> dict:
        return {
            "model_version": "date_v1",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metrics": self.metrics,
            "per_decade": self.per_decade,
            "pass": self.passed,
            "failure_reasons": self.failure_reasons,
        }

    def print_report(self):
        """Print formatted evaluation report."""
        print("\n" + "=" * 60)
        print("DATE ESTIMATION MODEL EVALUATION")
        print("=" * 60)

        print(f"\n{'Metric':<30} {'Value':>10}")
        print("-" * 42)
        for key, value in sorted(self.metrics.items()):
            if isinstance(value, float):
                print(f"  {key:<28} {value:>10.4f}")
            else:
                print(f"  {key:<28} {value!s:>10}")

        print(f"\n{'Decade':<10} {'Prec':>8} {'Recall':>8} {'N':>5}")
        print("-" * 33)
        for decade in sorted(self.per_decade.keys()):
            stats = self.per_decade[decade]
            print(f"  {decade}s  {stats['precision']:>8.3f} {stats['recall']:>8.3f} {stats['n']:>5d}")

        print(f"\n{'GATE RESULT:'} {'PASS' if self.passed else 'FAIL'}")
        if not self.passed:
            print("Failure reasons:")
            for reason in self.failure_reasons:
                print(f"  - {reason}")
        print("=" * 60)


def compute_brier_score(pred_probs: np.ndarray, true_indices: np.ndarray, num_classes: int) -> float:
    """Compute Brier score for probability calibration.

    Lower is better. 0 = perfect, 1 = worst.
    """
    one_hot = np.zeros((len(true_indices), num_classes))
    for i, idx in enumerate(true_indices):
        one_hot[i, idx] = 1.0
    return float(np.mean((pred_probs - one_hot) ** 2))


def evaluate_model(
    model: DateEstimationModel,
    labels: list[dict],
    photos_dir: str = "raw_photos",
    gate_config: dict | None = None,
    num_classes: int = NUM_DECADES,
    photo_index: dict | None = None,
) -> GateResult:
    """Run full evaluation on a date estimation model.

    Args:
        model: Trained DateEstimationModel.
        labels: List of label dicts with photo_id, estimated_decade, etc.
        photos_dir: Directory containing photos.
        gate_config: Gate criteria config dict.
        num_classes: Number of decade classes.

    Returns:
        GateResult with metrics and pass/fail status.
    """
    from rhodesli_ml.data.date_dataset import DateEstimationDataset
    from rhodesli_ml.data.augmentations import get_val_transforms

    default_gate = {
        "min_adjacent_accuracy": 0.70,
        "max_mae_decades": 1.5,
        "min_decade_recall": 0.20,
    }
    gate_config = gate_config or default_gate

    # Create dataset
    transform = get_val_transforms()
    dataset = DateEstimationDataset(
        labels=labels,
        photos_dir=photos_dir,
        photo_index=photo_index,
        transform=transform,
        num_classes=num_classes,
    )

    if len(dataset) == 0:
        return GateResult(
            metrics={"error": "no_data", "mae_decades": float("inf"), "adjacent_accuracy": 0.0},
            per_decade={},
            gate_config=gate_config,
        )

    # Collect predictions
    model.eval()
    all_pred_indices = []
    all_true_indices = []
    all_pred_probs = []
    all_confidences = []

    with torch.no_grad():
        for i in range(len(dataset)):
            item = dataset[i]
            image = item["image"].unsqueeze(0)
            true_class = item["class_index"]

            logits = model(image)
            probs = ordinal_logits_to_probs(logits)
            pred_class = probs_to_predicted_class(probs).item()

            all_pred_indices.append(pred_class)
            all_true_indices.append(true_class)
            all_pred_probs.append(probs.numpy()[0])

            # Map confidence from label
            label = labels[i] if i < len(labels) else {}
            all_confidences.append(label.get("confidence", "medium"))

    pred_indices = np.array(all_pred_indices)
    true_indices = np.array(all_true_indices)
    pred_probs = np.array(all_pred_probs)

    # Core metrics
    exact_accuracy = float(np.mean(pred_indices == true_indices))
    mae = float(np.mean(np.abs(pred_indices - true_indices)))
    adjacent = float(np.mean(np.abs(pred_indices - true_indices) <= 1))
    brier = compute_brier_score(pred_probs, true_indices, num_classes)

    # Confidence-stratified accuracy
    conf_accuracy = {}
    for conf_level in ["high", "medium", "low"]:
        mask = [c == conf_level for c in all_confidences]
        if any(mask):
            mask_arr = np.array(mask)
            conf_accuracy[f"accuracy_{conf_level}"] = float(
                np.mean(pred_indices[mask_arr] == true_indices[mask_arr])
            )
            conf_accuracy[f"n_{conf_level}"] = int(mask_arr.sum())

    # Per-decade metrics
    per_decade = {}
    for decade_idx in range(num_classes):
        decade = index_to_decade(decade_idx)
        true_mask = true_indices == decade_idx
        pred_mask = pred_indices == decade_idx

        n_true = int(true_mask.sum())
        n_pred = int(pred_mask.sum())

        tp = int((true_mask & pred_mask).sum())
        precision = tp / n_pred if n_pred > 0 else 0.0
        recall = tp / n_true if n_true > 0 else 0.0

        per_decade[str(decade)] = {
            "precision": precision,
            "recall": recall,
            "n": n_true,
        }

    metrics = {
        "exact_accuracy": exact_accuracy,
        "adjacent_accuracy": adjacent,
        "mae_decades": mae,
        "brier_score": brier,
        "n_samples": len(true_indices),
        **conf_accuracy,
    }

    return GateResult(
        metrics=metrics,
        per_decade=per_decade,
        gate_config=gate_config,
    )
