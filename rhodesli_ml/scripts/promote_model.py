"""Automated model promotion pipeline.

Runs regression gate, registers model version in MLflow, and promotes
to @champion if the gate passes. The key deliverable of Session 58.

Flow:
  1. Load ONNX model from --onnx-path
  2. Run regression gate on evaluation data
  3. Register new model version in MLflow with gate metrics
  4. If gate passed -> assign @champion alias, demote previous to @candidate
  5. If gate failed -> tag as failed, do NOT promote
  6. Copy ONNX to artifacts/ for git push to production

Usage:
  # Promote date estimation model after retraining
  python -m rhodesli_ml.scripts.promote_model \\
    --model rhodesli-date-estimation \\
    --onnx-path rhodesli_ml/artifacts/date_estimation_v1.onnx \\
    --labels-path rhodesli_ml/data/date_labels.json

  # Dry run (evaluate gate without registering)
  python -m rhodesli_ml.scripts.promote_model \\
    --model rhodesli-date-estimation \\
    --onnx-path rhodesli_ml/artifacts/date_estimation_v1.onnx \\
    --dry-run

Decision provenance: AD-130 (MLflow Model Registry with Alias-Based Promotion)
"""

import argparse
import shutil
from pathlib import Path


def run_date_gate(onnx_path: Path, labels_path: Path, gate_config: dict | None = None) -> dict:
    """Run regression gate for date estimation model.

    Returns structured result with metrics, pass/fail, and failure reasons.
    """
    import json

    import numpy as np
    import onnxruntime as ort

    from rhodesli_ml.data.date_dataset import NUM_DECADES, decade_to_index
    from rhodesli_ml.date_inference.inference_onnx import ONNXDateEstimationInference

    default_gate = {
        "min_adjacent_accuracy": 0.70,
        "max_mae_decades": 1.5,
    }
    gate_config = gate_config or default_gate

    # Load labels
    with open(labels_path) as f:
        labels = json.load(f)

    if not labels:
        return {
            "passed": False,
            "metrics": {},
            "thresholds": gate_config,
            "failure_reasons": ["No evaluation data available"],
        }

    # Load model
    inference = ONNXDateEstimationInference(onnx_path)

    # For each label with a known decade, check prediction
    predictions = []
    true_indices = []
    pred_indices = []

    for label in labels:
        decade = label.get("estimated_decade") or label.get("decade")
        if decade is None:
            continue

        photo_path = label.get("photo_path")
        if photo_path and Path(photo_path).exists():
            from PIL import Image

            img = np.array(Image.open(photo_path).convert("RGB"))
            result = inference.predict_from_image(img)
        else:
            # Skip entries without accessible photos
            continue

        true_idx = decade_to_index(decade)
        pred_decade = result["predicted_decade"]
        pred_idx = decade_to_index(pred_decade)

        true_indices.append(true_idx)
        pred_indices.append(pred_idx)

    if not true_indices:
        return {
            "passed": False,
            "metrics": {"n_samples": 0},
            "thresholds": gate_config,
            "failure_reasons": ["No photos available for evaluation"],
        }

    true_arr = np.array(true_indices)
    pred_arr = np.array(pred_indices)

    exact_accuracy = float(np.mean(true_arr == pred_arr))
    adjacent_accuracy = float(np.mean(np.abs(true_arr - pred_arr) <= 1))
    mae = float(np.mean(np.abs(true_arr - pred_arr)))

    metrics = {
        "exact_accuracy": round(exact_accuracy, 4),
        "adjacent_accuracy": round(adjacent_accuracy, 4),
        "mae_decades": round(mae, 4),
        "n_samples": len(true_indices),
    }

    failure_reasons = []
    if adjacent_accuracy < gate_config["min_adjacent_accuracy"]:
        failure_reasons.append(
            f"Adjacent accuracy {adjacent_accuracy:.3f} < {gate_config['min_adjacent_accuracy']}"
        )
    if mae > gate_config["max_mae_decades"]:
        failure_reasons.append(
            f"MAE {mae:.3f} > {gate_config['max_mae_decades']}"
        )

    return {
        "passed": len(failure_reasons) == 0,
        "metrics": metrics,
        "thresholds": gate_config,
        "failure_reasons": failure_reasons,
    }


def promote(
    model_name: str,
    onnx_path: Path,
    gate_result: dict,
    dry_run: bool = False,
) -> bool:
    """Register model version in MLflow and promote if gate passed.

    Returns True if model was promoted (or would be in dry run).
    """
    import mlflow
    from rhodesli_ml.config.mlflow_config import (
        configure_tracking,
        get_client,
        ARTIFACTS_DIR,
        MODEL_DATE_ESTIMATION,
        MODEL_SIMILARITY_CALIBRATION,
    )

    configure_tracking()
    client = get_client()

    passed = gate_result["passed"]
    metrics = gate_result["metrics"]

    print(f"\n{'='*50}")
    print(f"Model: {model_name}")
    print(f"Gate:  {'PASSED' if passed else 'FAILED'}")
    for k, v in metrics.items():
        print(f"  {k}: {v}")
    if not passed:
        for reason in gate_result["failure_reasons"]:
            print(f"  FAIL: {reason}")
    print(f"{'='*50}")

    if dry_run:
        print(f"[DRY RUN] Would {'promote' if passed else 'register as failed'}")
        return passed

    # Register the ONNX model
    import onnx

    onnx_model = onnx.load(str(onnx_path))

    # Determine experiment
    exp_name_map = {
        MODEL_DATE_ESTIMATION: "rhodesli_date_estimation",
        MODEL_SIMILARITY_CALIBRATION: "rhodesli-similarity-calibration",
    }
    exp_name = exp_name_map.get(model_name, "default")
    experiment = mlflow.get_experiment_by_name(exp_name)
    exp_id = experiment.experiment_id if experiment else mlflow.create_experiment(exp_name)

    with mlflow.start_run(experiment_id=exp_id, run_name=f"promote_{model_name}"):
        model_info = mlflow.onnx.log_model(
            onnx_model,
            name="model",
            registered_model_name=model_name,
        )

        # Log all gate metrics
        mlflow_metrics = {f"gate_{k}": v for k, v in metrics.items() if isinstance(v, (int, float))}
        mlflow.log_metrics(mlflow_metrics)

        mlflow.set_tag("gate_status", "passed" if passed else "failed")
        mlflow.set_tag("promotion_source", str(onnx_path))

    # Get the version we just created
    versions = client.search_model_versions(f"name='{model_name}'")
    latest = max(versions, key=lambda v: int(v.version))

    # Tag the version
    client.set_model_version_tag(
        model_name, latest.version,
        "gate_status", "passed" if passed else "failed"
    )
    for k, v in metrics.items():
        client.set_model_version_tag(model_name, latest.version, f"gate_{k}", str(v))

    if passed:
        # Find current champion before moving alias
        try:
            current_champion = client.get_model_version_by_alias(model_name, "champion")
            if int(current_champion.version) != int(latest.version):
                # Demote current champion to candidate
                client.set_registered_model_alias(
                    model_name, "candidate", current_champion.version
                )
                print(f"  Previous champion v{current_champion.version} -> @candidate")
        except Exception:
            pass  # No current champion

        # Promote new version
        client.set_registered_model_alias(model_name, "champion", latest.version)
        client.set_model_version_tag(
            model_name, latest.version, "deployed_to", "production"
        )
        print(f"  v{latest.version} -> @champion")

        # Copy ONNX to artifacts dir for git push
        dest = ARTIFACTS_DIR / onnx_path.name
        if onnx_path.resolve() != dest.resolve():
            shutil.copy2(onnx_path, dest)
            print(f"  Copied to {dest}")

        print("\n  Model promoted. Run `git push` to deploy to production.")
    else:
        print(f"\n  Model FAILED gate. Not promoted. v{latest.version} tagged as failed.")

    return passed


def main():
    parser = argparse.ArgumentParser(
        description="Automated model promotion: gate -> register -> alias -> export"
    )
    parser.add_argument(
        "--model",
        required=True,
        help="Registered model name (e.g., rhodesli-date-estimation)",
    )
    parser.add_argument(
        "--onnx-path",
        type=Path,
        required=True,
        help="Path to the ONNX model to promote",
    )
    parser.add_argument(
        "--labels-path",
        type=Path,
        default=Path("rhodesli_ml/data/date_labels.json"),
        help="Path to evaluation labels (for date estimation gate)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run gate but don't register or promote",
    )
    parser.add_argument(
        "--skip-gate",
        action="store_true",
        help="Skip regression gate (use for initial registration only)",
    )
    args = parser.parse_args()

    if not args.onnx_path.exists():
        print(f"ERROR: ONNX model not found: {args.onnx_path}")
        return

    from rhodesli_ml.config.mlflow_config import MODEL_DATE_ESTIMATION

    # Run gate (unless skipped)
    if args.skip_gate:
        gate_result = {
            "passed": True,
            "metrics": {"gate_skipped": 1},
            "thresholds": {},
            "failure_reasons": [],
        }
        print("Gate skipped (--skip-gate)")
    elif args.model == MODEL_DATE_ESTIMATION:
        print(f"Running regression gate on {args.onnx_path}...")
        gate_result = run_date_gate(args.onnx_path, args.labels_path)
    else:
        # For non-date models, skip gate (no automated gate yet)
        gate_result = {
            "passed": True,
            "metrics": {"gate_type": "manual"},
            "thresholds": {},
            "failure_reasons": [],
        }
        print(f"No automated gate for {args.model} — manual approval assumed")

    # Promote
    promote(args.model, args.onnx_path, gate_result, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
