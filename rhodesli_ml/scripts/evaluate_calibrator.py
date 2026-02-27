"""Regression gate — calibrator vs baseline comparison.

Compares the trained calibrator against the Euclidean distance baseline
on AUC-ROC, precision@90recall, and calibration error. The calibrator
must beat the baseline on ALL three metrics to ship.

Usage:
    python -m rhodesli_ml.scripts.evaluate_calibrator
    python -m rhodesli_ml.scripts.evaluate_calibrator --data-dir data/ --model rhodesli_ml/artifacts/calibration_v1.pt
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
from rhodesli_ml.calibration.evaluate import (
    euclidean_baseline_metrics,
    load_model,
)
from rhodesli_ml.calibration.train import compute_metrics


def precision_at_recall(preds, labels, target_recall=0.9):
    """Compute precision at a given recall threshold."""
    n_pos = np.sum(labels == 1.0)
    if n_pos == 0:
        return 0.0

    sorted_idx = np.argsort(-preds)
    sorted_labels = labels[sorted_idx]
    sorted_preds = preds[sorted_idx]

    tp = 0
    best_precision = 0.0
    for i, lab in enumerate(sorted_labels):
        if lab == 1.0:
            tp += 1
        recall = tp / n_pos
        if recall >= target_recall:
            precision = tp / (i + 1)
            best_precision = max(best_precision, precision)
            break

    return best_precision


def calibration_error(preds, labels, n_bins=10):
    """Expected calibration error (ECE)."""
    bin_edges = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        mask = (preds >= bin_edges[i]) & (preds < bin_edges[i + 1])
        if mask.sum() == 0:
            continue
        bin_preds = preds[mask]
        bin_labels = labels[mask]
        avg_confidence = np.mean(bin_preds)
        avg_accuracy = np.mean(bin_labels)
        ece += np.abs(avg_confidence - avg_accuracy) * mask.sum() / len(preds)
    return ece


def evaluate_gate(data_dir: Path, model_path: Path, seed: int = 42):
    """Run regression gate: calibrator must beat baseline on all metrics."""
    identities = load_confirmed_identities(data_dir)
    face_embeddings = load_face_embeddings(data_dir)
    _, eval_ids = split_identities(identities, face_embeddings, seed=seed)

    eval_pairs = generate_pairs(eval_ids, face_embeddings, neg_ratio=3, seed=seed + 1)
    if not eval_pairs:
        print("ERROR: No eval pairs generated")
        return False

    # --- Baseline metrics ---
    baseline_scores = []
    labels_list = []
    for emb_a, emb_b, label in eval_pairs:
        dist = np.linalg.norm(emb_a - emb_b)
        # Baseline: distance-to-score mapping (production thresholds)
        if dist < 0.95:
            score = 0.9
        elif dist < 1.10:
            score = 0.6
        elif dist < 1.20:
            score = 0.3
        else:
            score = 0.1
        baseline_scores.append(score)
        labels_list.append(label)

    baseline_scores = np.array(baseline_scores)
    labels = np.array(labels_list)

    baseline_metrics = euclidean_baseline_metrics(eval_pairs)
    baseline_auc = baseline_metrics["roc_auc"]
    baseline_p90r = precision_at_recall(baseline_scores, labels, 0.9)
    baseline_ece = calibration_error(baseline_scores, labels)

    # --- Calibrator metrics ---
    model = load_model(model_path)
    dataset = PairDataset(eval_pairs)
    loader = DataLoader(dataset, batch_size=64, shuffle=False)

    all_preds = []
    all_labels = []
    model.eval()
    with torch.no_grad():
        for emb_a, emb_b, labs in loader:
            preds = model(emb_a, emb_b).squeeze(-1)
            all_preds.extend(preds.cpu().numpy())
            all_labels.extend(labs.cpu().numpy())

    cal_preds = np.array(all_preds)
    cal_labels = np.array(all_labels)

    cal_metrics = compute_metrics(model, loader)
    cal_auc = cal_metrics["roc_auc"]
    cal_p90r = precision_at_recall(cal_preds, cal_labels, 0.9)
    cal_ece = calibration_error(cal_preds, cal_labels)

    # --- Print comparison ---
    print("=" * 70)
    print("REGRESSION GATE — Calibrator vs Baseline")
    print("=" * 70)
    print(f"\n{'Metric':<30} {'Baseline':>12} {'Calibrator':>12} {'Better?':>10}")
    print("-" * 70)

    results = []

    # AUC-ROC (higher is better)
    auc_better = cal_auc >= baseline_auc
    results.append(auc_better)
    print(f"  {'AUC-ROC':<28} {baseline_auc:>12.4f} {cal_auc:>12.4f} {'YES' if auc_better else 'NO':>10}")

    # Precision@90%Recall (higher is better)
    p90r_better = cal_p90r >= baseline_p90r
    results.append(p90r_better)
    print(f"  {'Precision@90%Recall':<28} {baseline_p90r:>12.4f} {cal_p90r:>12.4f} {'YES' if p90r_better else 'NO':>10}")

    # Calibration Error (lower is better)
    ece_better = cal_ece <= baseline_ece
    results.append(ece_better)
    print(f"  {'Calibration Error (ECE)':<28} {baseline_ece:>12.4f} {cal_ece:>12.4f} {'YES' if ece_better else 'NO':>10}")

    # Additional context
    print(f"\n  {'Best F1':<28} {'—':>12} {cal_metrics['best_f1']:>12.4f}")
    print(f"  {'Best Threshold':<28} {'—':>12} {cal_metrics['best_threshold']:>12.2f}")
    print(f"  {'Eval Pairs':<28} {len(eval_pairs):>12}")

    # Gate decision
    all_pass = all(results)
    print("\n" + "=" * 70)
    if all_pass:
        print("GATE: SHIP — Calibrator beats baseline on all metrics")
    else:
        failed = []
        if not results[0]:
            failed.append("AUC-ROC")
        if not results[1]:
            failed.append("Precision@90%Recall")
        if not results[2]:
            failed.append("ECE")
        print(f"GATE: NO-SHIP — Baseline wins on: {', '.join(failed)}")
    print("=" * 70)

    return all_pass


def main():
    parser = argparse.ArgumentParser(description="Regression gate: calibrator vs baseline")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--model", type=Path,
                        default=Path("rhodesli_ml/artifacts/calibration_v1.pt"))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if not args.model.exists():
        print(f"Model not found: {args.model}")
        print("Run training first: python -m rhodesli_ml.calibration.train")
        return

    passed = evaluate_gate(args.data_dir, args.model, args.seed)
    exit(0 if passed else 1)


if __name__ == "__main__":
    main()
