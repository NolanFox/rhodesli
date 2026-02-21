"""Training script for similarity calibration model.

Trains a Siamese MLP on embedding pairs with MLflow experiment tracking.
Supports early stopping, hyperparameter configuration, and model export.

Usage:
    python -m rhodesli_ml.calibration.train --data-dir data/ --epochs 100
    python -m rhodesli_ml.calibration.train --lr 5e-4 --batch-size 128

Decision provenance: AD-123, AD-124, AD-125.
"""

import argparse
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from rhodesli_ml.calibration.data import (
    PairDataset,
    generate_pairs,
    load_confirmed_identities,
    load_face_embeddings,
    split_identities,
)
from rhodesli_ml.calibration.model import CalibrationModel


def compute_metrics(
    model: CalibrationModel,
    dataloader: DataLoader,
    thresholds: list[float] | None = None,
) -> dict:
    """Compute precision, recall, F1 at various thresholds.

    Returns dict with per-threshold metrics and overall AUC.
    """
    if thresholds is None:
        thresholds = [0.3, 0.4, 0.5, 0.6, 0.7]

    model.eval()
    all_preds = []
    all_labels = []

    with torch.no_grad():
        for emb_a, emb_b, labels in dataloader:
            preds = model(emb_a, emb_b).squeeze(-1)
            all_preds.extend(preds.cpu().numpy())
            all_labels.extend(labels.cpu().numpy())

    preds = np.array(all_preds)
    labels = np.array(all_labels)

    metrics = {}
    best_f1 = 0.0
    best_threshold = 0.5

    for t in thresholds:
        predicted_pos = preds >= t
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

    # ROC-AUC (simple trapezoidal approximation)
    sorted_idx = np.argsort(-preds)
    sorted_labels = labels[sorted_idx]
    n_pos = np.sum(labels == 1.0)
    n_neg = np.sum(labels == 0.0)

    if n_pos > 0 and n_neg > 0:
        tpr_list = []
        fpr_list = []
        tp_count = 0
        fp_count = 0
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


def train(
    data_dir: Path,
    output_dir: Path | None = None,
    epochs: int = 200,
    lr: float = 5e-4,
    batch_size: int = 64,
    neg_ratio: int = 3,
    hard_neg_threshold: float = 1.2,
    patience: int = 20,
    weight_decay: float = 1e-2,
    seed: int = 42,
    use_mlflow: bool = True,
) -> dict:
    """Train the calibration model and return metrics.

    Returns dict with training results including metrics and model path.
    """
    torch.manual_seed(seed)
    np.random.seed(seed)

    # Data preparation
    identities = load_confirmed_identities(data_dir)
    face_embeddings = load_face_embeddings(data_dir)

    train_ids, eval_ids = split_identities(
        identities, face_embeddings, seed=seed
    )

    train_pairs = generate_pairs(
        train_ids, face_embeddings,
        neg_ratio=neg_ratio,
        hard_neg_threshold=hard_neg_threshold,
        seed=seed,
    )
    eval_pairs = generate_pairs(
        eval_ids, face_embeddings,
        neg_ratio=neg_ratio,
        hard_neg_threshold=hard_neg_threshold,
        seed=seed + 1,
    )

    if not train_pairs:
        return {"error": "No training pairs generated", "train_pairs": 0}

    train_dataset = PairDataset(train_pairs)
    eval_dataset = PairDataset(eval_pairs) if eval_pairs else None

    train_loader = DataLoader(
        train_dataset, batch_size=batch_size, shuffle=True,
        generator=torch.Generator().manual_seed(seed),
    )
    eval_loader = DataLoader(
        eval_dataset, batch_size=batch_size, shuffle=False,
    ) if eval_dataset else None

    # Model
    model = CalibrationModel(embed_dim=512)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)
    criterion = nn.BCELoss()

    # MLflow setup
    mlflow_run = None
    if use_mlflow:
        try:
            import mlflow
            mlflow.set_tracking_uri(f"file:{Path('mlruns').resolve()}")
            mlflow.set_experiment("rhodesli-similarity-calibration")
            mlflow_run = mlflow.start_run()
            mlflow.log_params({
                "lr": lr,
                "batch_size": batch_size,
                "neg_ratio": neg_ratio,
                "hard_neg_threshold": hard_neg_threshold,
                "weight_decay": weight_decay,
                "epochs": epochs,
                "patience": patience,
                "seed": seed,
                "train_pairs": len(train_pairs),
                "eval_pairs": len(eval_pairs) if eval_pairs else 0,
                "train_identities": len(train_ids),
                "eval_identities": len(eval_ids),
                "model": "siamese_mlp_compact",
                "embed_dim": 512,
                "hidden_dim": 32,
            })
        except ImportError:
            use_mlflow = False

    # Training loop
    best_eval_loss = float("inf")
    best_model_state = None
    epochs_without_improvement = 0
    start_time = time.time()

    train_losses = []
    eval_losses = []

    for epoch in range(epochs):
        # Train
        model.train()
        epoch_loss = 0.0
        n_batches = 0
        for emb_a, emb_b, labels in train_loader:
            optimizer.zero_grad()
            preds = model(emb_a, emb_b).squeeze(-1)
            loss = criterion(preds, labels)
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item()
            n_batches += 1

        avg_train_loss = epoch_loss / max(n_batches, 1)
        train_losses.append(avg_train_loss)

        # Evaluate
        avg_eval_loss = float("inf")
        if eval_loader:
            model.eval()
            eval_loss = 0.0
            n_eval = 0
            with torch.no_grad():
                for emb_a, emb_b, labels in eval_loader:
                    preds = model(emb_a, emb_b).squeeze(-1)
                    loss = criterion(preds, labels)
                    eval_loss += loss.item()
                    n_eval += 1
            avg_eval_loss = eval_loss / max(n_eval, 1)
            eval_losses.append(avg_eval_loss)

        # MLflow per-epoch logging
        if use_mlflow:
            try:
                import mlflow
                mlflow.log_metrics({
                    "train_loss": avg_train_loss,
                    "eval_loss": avg_eval_loss if eval_loader else 0,
                }, step=epoch)
            except Exception:
                pass

        # Early stopping
        if avg_eval_loss < best_eval_loss:
            best_eval_loss = avg_eval_loss
            best_model_state = {k: v.clone() for k, v in model.state_dict().items()}
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1

        if epochs_without_improvement >= patience:
            print(f"Early stopping at epoch {epoch + 1} (patience={patience})")
            break

        if (epoch + 1) % 10 == 0 or epoch == 0:
            print(f"Epoch {epoch + 1}/{epochs} | "
                  f"Train Loss: {avg_train_loss:.4f} | "
                  f"Eval Loss: {avg_eval_loss:.4f}")

    training_time = time.time() - start_time

    # Restore best model
    if best_model_state:
        model.load_state_dict(best_model_state)

    # Final evaluation
    final_metrics = {}
    if eval_loader:
        final_metrics = compute_metrics(model, eval_loader)

    # Save model
    model_path = None
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        model_path = output_dir / "calibration_v1.pt"
        torch.save({
            "model_state_dict": model.state_dict(),
            "config": {
                "embed_dim": 512,
                "hidden_dim": 32,
                "dropout": 0.5,
            },
            "metrics": final_metrics,
            "training_time": training_time,
        }, model_path)
        print(f"Model saved to {model_path}")

    # MLflow final logging
    if use_mlflow:
        try:
            import mlflow
            mlflow.log_metrics({
                **final_metrics,
                "training_time_seconds": training_time,
                "epochs_trained": epoch + 1,
            })
            if model_path:
                mlflow.log_artifact(str(model_path))
            mlflow.end_run()
        except Exception:
            pass

    results = {
        "train_pairs": len(train_pairs),
        "eval_pairs": len(eval_pairs) if eval_pairs else 0,
        "epochs_trained": epoch + 1,
        "training_time": round(training_time, 2),
        "best_eval_loss": round(best_eval_loss, 4) if best_eval_loss < float("inf") else None,
        "model_path": str(model_path) if model_path else None,
        **final_metrics,
    }

    return results


def main():
    parser = argparse.ArgumentParser(description="Train similarity calibration model")
    parser.add_argument("--data-dir", type=Path, default=Path("data"),
                        help="Path to data directory")
    parser.add_argument("--output-dir", type=Path,
                        default=Path("rhodesli_ml/artifacts"),
                        help="Output directory for model artifacts")
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--lr", type=float, default=5e-4)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--neg-ratio", type=int, default=3)
    parser.add_argument("--patience", type=int, default=20)
    parser.add_argument("--weight-decay", type=float, default=1e-2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-mlflow", action="store_true")
    args = parser.parse_args()

    results = train(
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        epochs=args.epochs,
        lr=args.lr,
        batch_size=args.batch_size,
        neg_ratio=args.neg_ratio,
        patience=args.patience,
        weight_decay=args.weight_decay,
        seed=args.seed,
        use_mlflow=not args.no_mlflow,
    )

    print("\n" + "=" * 60)
    print("TRAINING RESULTS")
    print("=" * 60)
    for k, v in results.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
