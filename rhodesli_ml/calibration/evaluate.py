"""Evaluation of calibration model against raw Euclidean baseline.

Computes precision/recall/AUC for both the trained model and raw
Euclidean distance, enabling direct comparison.

Usage:
    python -m rhodesli_ml.calibration.evaluate --data-dir data/ --model artifacts/calibration_v1.pt
"""

import argparse
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader

from rhodesli_ml.calibration.data import (
    PairDataset,
    generate_pairs,
    load_confirmed_identities,
    load_face_embeddings,
    split_identities,
)
from rhodesli_ml.calibration.model import CalibrationModel
from rhodesli_ml.calibration.train import compute_metrics


def euclidean_baseline_metrics(
    pairs: list[tuple[np.ndarray, np.ndarray, float]],
    thresholds: list[float] | None = None,
) -> dict:
    """Compute precision/recall using raw Euclidean distance.

    Converts Euclidean distance to a probability-like score using
    the sigmoid approximation from the current production code.
    Then computes same metrics as the trained model for comparison.
    """
    if thresholds is None:
        thresholds = [0.3, 0.4, 0.5, 0.6, 0.7]

    # Compute distances and convert to scores
    scores = []
    labels = []
    for emb_a, emb_b, label in pairs:
        dist = np.linalg.norm(emb_a - emb_b)
        # Sigmoid transformation: closer distance = higher score
        # Use same-person mean=0.18 as center (from kinship calibration)
        score = 1.0 / (1.0 + np.exp((dist - 0.8) / 0.3))
        scores.append(score)
        labels.append(label)

    scores = np.array(scores)
    labels = np.array(labels)

    metrics = {}
    best_f1 = 0.0
    best_threshold = 0.5

    for t in thresholds:
        predicted_pos = scores >= t
        tp = np.sum(predicted_pos & (labels == 1.0))
        fp = np.sum(predicted_pos & (labels == 0.0))
        fn = np.sum(~predicted_pos & (labels == 1.0))

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        metrics[f"precision_{t}"] = round(float(precision), 4)
        metrics[f"recall_{t}"] = round(float(recall), 4)
        metrics[f"f1_{t}"] = round(float(f1), 4)

        if f1 > best_f1:
            best_f1 = f1
            best_threshold = t

    metrics["best_threshold"] = best_threshold
    metrics["best_f1"] = round(float(best_f1), 4)

    # ROC-AUC
    sorted_idx = np.argsort(-scores)
    sorted_labels = labels[sorted_idx]
    n_pos = np.sum(labels == 1.0)
    n_neg = np.sum(labels == 0.0)

    if n_pos > 0 and n_neg > 0:
        tpr_list, fpr_list = [], []
        tp_count, fp_count = 0, 0
        for lab in sorted_labels:
            if lab == 1.0:
                tp_count += 1
            else:
                fp_count += 1
            tpr_list.append(tp_count / n_pos)
            fpr_list.append(fp_count / n_neg)
        auc = np.trapz(tpr_list, fpr_list)
        metrics["roc_auc"] = round(float(auc), 4)
    else:
        metrics["roc_auc"] = 0.0

    return metrics


def load_model(model_path: Path) -> CalibrationModel:
    """Load a trained CalibrationModel from checkpoint."""
    checkpoint = torch.load(model_path, weights_only=False)
    config = checkpoint.get("config", {})
    model = CalibrationModel(
        embed_dim=config.get("embed_dim", 512),
        hidden_dim=config.get("hidden_dim", 256),
        dropout=config.get("dropout", 0.3),
    )
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    return model


def compare_baseline_vs_calibrated(
    data_dir: Path,
    model_path: Path,
    seed: int = 42,
) -> dict:
    """Run full comparison of baseline vs calibrated model.

    Returns dict with baseline metrics, calibrated metrics, and deltas.
    """
    identities = load_confirmed_identities(data_dir)
    face_embeddings = load_face_embeddings(data_dir)
    _, eval_ids = split_identities(identities, face_embeddings, seed=seed)

    eval_pairs = generate_pairs(
        eval_ids, face_embeddings, neg_ratio=3, seed=seed + 1,
    )

    if not eval_pairs:
        return {"error": "No eval pairs generated"}

    # Baseline
    baseline = euclidean_baseline_metrics(eval_pairs)

    # Calibrated
    model = load_model(model_path)
    dataset = PairDataset(eval_pairs)
    loader = DataLoader(dataset, batch_size=64, shuffle=False)
    calibrated = compute_metrics(model, loader)

    # Compute deltas
    comparison = {"baseline": baseline, "calibrated": calibrated, "deltas": {}}
    for key in baseline:
        if key in calibrated and isinstance(baseline[key], (int, float)):
            delta = calibrated[key] - baseline[key]
            comparison["deltas"][key] = round(delta, 4)

    return comparison


def main():
    parser = argparse.ArgumentParser(description="Evaluate calibration model vs baseline")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--model", type=Path,
                        default=Path("rhodesli_ml/artifacts/calibration_v1.pt"))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if not args.model.exists():
        print(f"Model not found: {args.model}")
        print("Run training first: python -m rhodesli_ml.calibration.train")
        return

    results = compare_baseline_vs_calibrated(args.data_dir, args.model, args.seed)

    print("=" * 70)
    print("CALIBRATION EVALUATION — Baseline vs Calibrated")
    print("=" * 70)
    print(f"\n{'Metric':<25} {'Baseline':>12} {'Calibrated':>12} {'Delta':>12}")
    print("-" * 65)

    for key in sorted(results["baseline"].keys()):
        b = results["baseline"][key]
        c = results["calibrated"].get(key, "—")
        d = results["deltas"].get(key, "—")
        if isinstance(b, float):
            b_str = f"{b:.4f}"
            c_str = f"{c:.4f}" if isinstance(c, float) else str(c)
            d_str = f"{d:+.4f}" if isinstance(d, float) else str(d)
        else:
            b_str, c_str, d_str = str(b), str(c), str(d)
        print(f"  {key:<23} {b_str:>12} {c_str:>12} {d_str:>12}")


if __name__ == "__main__":
    main()
