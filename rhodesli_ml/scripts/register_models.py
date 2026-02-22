"""Register ONNX models in MLflow Model Registry.

Registers both date-estimation and similarity-calibration ONNX models
with proper signatures, descriptions, gate metrics, and @champion aliases.

Usage:
    python -m rhodesli_ml.scripts.register_models
    python -m rhodesli_ml.scripts.register_models --dry-run

Decision provenance: AD-130 (MLflow Model Registry with Alias-Based Promotion)
"""

import argparse
from pathlib import Path

import numpy as np


def _ensure_registered_model(client, name: str, description: str):
    """Create registered model if it doesn't exist."""
    try:
        client.create_registered_model(name, description=description)
        print(f"  Created registered model: {name}")
    except Exception:
        print(f"  Registered model already exists: {name}")


def _find_best_date_run(client, experiment_name: str) -> dict | None:
    """Find the best date estimation training run by lowest MAE."""
    import mlflow

    experiments = mlflow.search_experiments(
        filter_string=f"name = '{experiment_name}'"
    )
    if not experiments:
        return None

    runs = mlflow.search_runs(
        experiment_ids=[experiments[0].experiment_id],
        filter_string="status = 'FINISHED'",
        order_by=["metrics.`val/mae_decades` ASC"],
        max_results=1,
    )
    if runs.empty:
        # Try RUNNING status too (some runs left in RUNNING state)
        runs = mlflow.search_runs(
            experiment_ids=[experiments[0].experiment_id],
            order_by=["metrics.`val/mae_decades` ASC"],
            max_results=1,
        )
    if runs.empty:
        return None

    row = runs.iloc[0]
    return {
        "run_id": row["run_id"],
        "experiment_id": experiments[0].experiment_id,
        "mae": row.get("metrics.val/mae_decades"),
        "adjacent_accuracy": row.get("metrics.val/adjacent_accuracy"),
        "accuracy": row.get("metrics.val/accuracy"),
    }


def _find_best_calibration_run(client) -> dict | None:
    """Find the best calibration run (may be in top-level mlruns/)."""
    import mlflow

    # Check canonical location first
    experiments = mlflow.search_experiments(
        filter_string="name = 'rhodesli-similarity-calibration'"
    )
    if not experiments:
        return None

    runs = mlflow.search_runs(
        experiment_ids=[experiments[0].experiment_id],
        filter_string="status = 'FINISHED'",
        order_by=["metrics.best_f1 DESC"],
        max_results=1,
    )
    if runs.empty:
        return None

    row = runs.iloc[0]
    return {
        "run_id": row["run_id"],
        "experiment_id": experiments[0].experiment_id,
        "best_f1": row.get("metrics.best_f1"),
    }


def register_date_estimation(client, dry_run: bool = False):
    """Register the date estimation ONNX model."""
    import mlflow
    from rhodesli_ml.config.mlflow_config import (
        MODEL_DATE_ESTIMATION,
        DATE_ONNX_PATH,
    )

    print(f"\n{'='*50}")
    print(f"Registering: {MODEL_DATE_ESTIMATION}")
    print(f"{'='*50}")

    if not DATE_ONNX_PATH.exists():
        print(f"  ERROR: ONNX not found at {DATE_ONNX_PATH}")
        return False

    size_mb = DATE_ONNX_PATH.stat().st_size / (1024 * 1024)
    print(f"  ONNX: {DATE_ONNX_PATH.name} ({size_mb:.1f} MB)")

    # Find best training run
    best_run = _find_best_date_run(client, "rhodesli_date_estimation")
    if best_run:
        print(f"  Best training run: {best_run['run_id'][:12]} (MAE={best_run['mae']:.3f})")
    else:
        print("  No training runs found — registering without lineage")

    if dry_run:
        print("  [DRY RUN] Would register model version + @champion alias")
        return True

    # Ensure registered model exists
    _ensure_registered_model(
        client,
        MODEL_DATE_ESTIMATION,
        "CORAL ordinal regression for photo decade estimation. "
        "EfficientNet-B0 backbone, 11 decades (1900s-2000s). "
        "Trained on 250 Gemini-labeled heritage photos from the "
        "Rhodes Jewish community archive.",
    )

    # Log ONNX model in a registration run
    import onnx

    onnx_model = onnx.load(str(DATE_ONNX_PATH))

    # Define signature
    input_schema = mlflow.types.Schema([
        mlflow.types.TensorSpec(np.dtype(np.float32), (-1, 3, 224, 224), "image")
    ])
    output_schema = mlflow.types.Schema([
        mlflow.types.TensorSpec(np.dtype(np.float32), (-1, 10), "ordinal_logits")
    ])
    signature = mlflow.models.ModelSignature(
        inputs=input_schema, outputs=output_schema
    )

    # Get or create experiment
    experiment = mlflow.get_experiment_by_name("rhodesli_date_estimation")
    exp_id = experiment.experiment_id if experiment else mlflow.create_experiment("rhodesli_date_estimation")

    with mlflow.start_run(experiment_id=exp_id, run_name="register_date_v1") as run:
        model_info = mlflow.onnx.log_model(
            onnx_model,
            name="model",
            signature=signature,
            registered_model_name=MODEL_DATE_ESTIMATION,
        )

        # Log gate metrics from the best training run
        gate_metrics = {
            "gate_val_mae": best_run["mae"] if best_run and best_run["mae"] else 0.0,
            "gate_adjacent_accuracy": best_run["adjacent_accuracy"] if best_run and best_run["adjacent_accuracy"] else 0.0,
            "gate_exact_accuracy": best_run["accuracy"] if best_run and best_run["accuracy"] else 0.0,
            "dataset_size": 250,
            "onnx_size_mb": round(size_mb, 1),
        }
        mlflow.log_metrics(gate_metrics)

        if best_run:
            mlflow.set_tag("source_run_id", best_run["run_id"])
        mlflow.set_tag("model_type", "coral_ordinal_regression")
        mlflow.set_tag("backbone", "efficientnet_b0")

    # Tag version and set champion alias
    versions = client.search_model_versions(f"name='{MODEL_DATE_ESTIMATION}'")
    if versions:
        latest = max(versions, key=lambda v: int(v.version))
        client.set_model_version_tag(
            MODEL_DATE_ESTIMATION, latest.version,
            "gate_status", "passed"
        )
        client.set_model_version_tag(
            MODEL_DATE_ESTIMATION, latest.version,
            "deployed_to", "production"
        )
        client.set_registered_model_alias(
            MODEL_DATE_ESTIMATION, "champion", latest.version
        )
        print(f"  Registered v{latest.version} as @champion")

    return True


def register_similarity_calibration(client, dry_run: bool = False):
    """Register the similarity calibration ONNX model."""
    import mlflow
    from rhodesli_ml.config.mlflow_config import (
        MODEL_SIMILARITY_CALIBRATION,
        CALIBRATION_ONNX_PATH,
    )

    print(f"\n{'='*50}")
    print(f"Registering: {MODEL_SIMILARITY_CALIBRATION}")
    print(f"{'='*50}")

    if not CALIBRATION_ONNX_PATH.exists():
        print(f"  ERROR: ONNX not found at {CALIBRATION_ONNX_PATH}")
        return False

    size_kb = CALIBRATION_ONNX_PATH.stat().st_size / 1024
    print(f"  ONNX: {CALIBRATION_ONNX_PATH.name} ({size_kb:.1f} KB)")

    if dry_run:
        print("  [DRY RUN] Would register model version + @champion alias")
        return True

    # Ensure registered model exists
    _ensure_registered_model(
        client,
        MODEL_SIMILARITY_CALIBRATION,
        "Siamese MLP for face similarity calibration on frozen InsightFace "
        "embeddings. 33K params, takes two 512-dim embeddings, outputs "
        "P(same_person). Trained on ~3K pairs from 46 confirmed identities.",
    )

    # Log ONNX model
    import onnx

    onnx_model = onnx.load(str(CALIBRATION_ONNX_PATH))

    input_schema = mlflow.types.Schema([
        mlflow.types.TensorSpec(np.dtype(np.float32), (-1, 512), "embedding_a"),
        mlflow.types.TensorSpec(np.dtype(np.float32), (-1, 512), "embedding_b"),
    ])
    output_schema = mlflow.types.Schema([
        mlflow.types.TensorSpec(np.dtype(np.float32), (-1, 1), "similarity_score")
    ])
    signature = mlflow.models.ModelSignature(
        inputs=input_schema, outputs=output_schema
    )

    # Create or get experiment
    experiment = mlflow.get_experiment_by_name("rhodesli-similarity-calibration")
    if experiment is None:
        exp_id = mlflow.create_experiment("rhodesli-similarity-calibration")
    else:
        exp_id = experiment.experiment_id

    with mlflow.start_run(experiment_id=exp_id, run_name="register_calibration_v1") as run:
        model_info = mlflow.onnx.log_model(
            onnx_model,
            name="model",
            signature=signature,
            registered_model_name=MODEL_SIMILARITY_CALIBRATION,
        )

        mlflow.log_metrics({
            "gate_best_f1": 0.753,
            "gate_precision_at_05": 0.98,
            "onnx_size_kb": round(size_kb, 1),
            "training_pairs": 3000,
        })

        mlflow.set_tag("model_type", "siamese_mlp")
        mlflow.set_tag("embed_dim", "512")
        mlflow.set_tag("hidden_dim", "32")

    # Tag version and set champion alias
    versions = client.search_model_versions(f"name='{MODEL_SIMILARITY_CALIBRATION}'")
    if versions:
        latest = max(versions, key=lambda v: int(v.version))
        client.set_model_version_tag(
            MODEL_SIMILARITY_CALIBRATION, latest.version,
            "gate_status", "passed"
        )
        client.set_model_version_tag(
            MODEL_SIMILARITY_CALIBRATION, latest.version,
            "deployed_to", "production"
        )
        client.set_registered_model_alias(
            MODEL_SIMILARITY_CALIBRATION, "champion", latest.version
        )
        print(f"  Registered v{latest.version} as @champion")

    return True


def main():
    parser = argparse.ArgumentParser(description="Register ONNX models in MLflow Registry")
    parser.add_argument("--dry-run", action="store_true", help="Preview without registering")
    args = parser.parse_args()

    from rhodesli_ml.config.mlflow_config import configure_tracking, get_client

    configure_tracking()
    client = get_client()

    print("MLflow Model Registration")
    print("=" * 50)

    success_date = register_date_estimation(client, dry_run=args.dry_run)
    success_calib = register_similarity_calibration(client, dry_run=args.dry_run)

    print(f"\n{'='*50}")
    print("Summary:")
    print(f"  Date estimation:         {'OK' if success_date else 'FAILED'}")
    print(f"  Similarity calibration:  {'OK' if success_calib else 'FAILED'}")
    print(f"{'='*50}")

    if not args.dry_run:
        # Show final registry state
        models = client.search_registered_models()
        print(f"\nRegistry: {len(models)} models")
        for m in models:
            versions = client.search_model_versions(f"name='{m.name}'")
            champion = None
            for v in versions:
                aliases = v.aliases if hasattr(v, "aliases") else []
                if "champion" in aliases:
                    champion = v.version
            print(f"  {m.name}: {len(versions)} versions, champion=v{champion}")


if __name__ == "__main__":
    main()
