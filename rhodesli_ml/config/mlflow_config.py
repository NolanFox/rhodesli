"""MLflow configuration for consistent tracking and registry access.

All MLflow operations should use these helpers to ensure consistent
tracking URI across training, evaluation, and registration scripts.

The canonical tracking URI is rhodesli_ml/mlruns (file-backed).
"""

from pathlib import Path

# Canonical tracking URI — all MLflow ops use this
MLFLOW_TRACKING_URI = str(Path(__file__).resolve().parent.parent / "mlruns")

# Model names in the registry
MODEL_DATE_ESTIMATION = "rhodesli-date-estimation"
MODEL_SIMILARITY_CALIBRATION = "rhodesli-similarity-calibration"

# ONNX artifact paths
ARTIFACTS_DIR = Path(__file__).resolve().parent.parent / "artifacts"
DATE_ONNX_PATH = ARTIFACTS_DIR / "date_estimation_v1.onnx"
CALIBRATION_ONNX_PATH = ARTIFACTS_DIR / "calibration_v1.onnx"


def get_client():
    """Get configured MLflow client with canonical tracking URI."""
    import mlflow
    from mlflow import MlflowClient

    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    return MlflowClient(tracking_uri=MLFLOW_TRACKING_URI)


def configure_tracking():
    """Set MLflow tracking URI globally. Call before any mlflow ops."""
    import mlflow

    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
