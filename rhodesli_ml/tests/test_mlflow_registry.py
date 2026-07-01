"""Tests for MLflow Model Registry integration.

Tests model registration, alias management, and config helpers.
Uses a temporary MLflow tracking directory for isolation.
"""

import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

# CI installs requirements.txt only (no mlflow). This module imports mlflow inside
# tests/fixtures, so --collect-only can't see it; skip the module when mlflow is
# absent (Session 168 Fable P0).
pytest.importorskip("mlflow", exc_type=ImportError)


@pytest.fixture
def tmp_mlflow_dir(tmp_path):
    """Create isolated MLflow tracking directory."""
    mlruns = tmp_path / "mlruns"
    mlruns.mkdir()
    return str(mlruns)


@pytest.fixture
def mock_date_onnx(tmp_path):
    """Create a minimal ONNX model file for date estimation."""
    import onnx
    from onnx import TensorProto, helper

    # Minimal ONNX graph: identity op (image -> logits)
    X = helper.make_tensor_value_info("image", TensorProto.FLOAT, [1, 3, 224, 224])
    Y = helper.make_tensor_value_info("ordinal_logits", TensorProto.FLOAT, [1, 10])

    # Create a simple constant output for testing
    const = helper.make_node("ConstantOfShape", ["shape_input"], ["ordinal_logits"])
    shape_val = helper.make_tensor("shape_input", TensorProto.INT64, [2], [1, 10])
    init = [shape_val]

    # Just use an identity-like graph
    identity = helper.make_node("Identity", ["image"], ["intermediate"])
    reshape_shape = helper.make_tensor("reshape_shape", TensorProto.INT64, [2], [1, 10])

    # Simpler: just create a graph with Shape + ConstantOfShape
    graph = helper.make_graph(
        [
            helper.make_node("Shape", ["image"], ["img_shape"]),
            helper.make_node(
                "ConstantOfShape",
                ["output_shape"],
                ["ordinal_logits"],
                value=helper.make_tensor("val", TensorProto.FLOAT, [1], [0.5]),
            ),
        ],
        "test_date",
        [X],
        [Y],
        [helper.make_tensor("output_shape", TensorProto.INT64, [2], [1, 10])],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)])
    model.ir_version = 8

    path = tmp_path / "date_estimation_v1.onnx"
    onnx.save(model, str(path))
    return path


@pytest.fixture
def mock_calib_onnx(tmp_path):
    """Create a minimal ONNX model file for calibration."""
    import onnx
    from onnx import TensorProto, helper

    A = helper.make_tensor_value_info("embedding_a", TensorProto.FLOAT, [1, 512])
    B = helper.make_tensor_value_info("embedding_b", TensorProto.FLOAT, [1, 512])
    Y = helper.make_tensor_value_info("similarity_score", TensorProto.FLOAT, [1, 1])

    graph = helper.make_graph(
        [
            helper.make_node(
                "ConstantOfShape",
                ["output_shape"],
                ["similarity_score"],
                value=helper.make_tensor("val", TensorProto.FLOAT, [1], [0.5]),
            ),
        ],
        "test_calib",
        [A, B],
        [Y],
        [helper.make_tensor("output_shape", TensorProto.INT64, [2], [1, 1])],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)])
    model.ir_version = 8

    path = tmp_path / "calibration_v1.onnx"
    onnx.save(model, str(path))
    return path


class TestMlflowConfig:
    """Tests for rhodesli_ml/config/mlflow_config.py."""

    def test_tracking_uri_is_absolute(self):
        from rhodesli_ml.config.mlflow_config import MLFLOW_TRACKING_URI

        assert Path(MLFLOW_TRACKING_URI).is_absolute()

    def test_tracking_uri_points_to_mlruns(self):
        from rhodesli_ml.config.mlflow_config import MLFLOW_TRACKING_URI

        assert MLFLOW_TRACKING_URI.endswith("mlruns")

    def test_model_names_are_strings(self):
        from rhodesli_ml.config.mlflow_config import (
            MODEL_DATE_ESTIMATION,
            MODEL_SIMILARITY_CALIBRATION,
        )

        assert isinstance(MODEL_DATE_ESTIMATION, str)
        assert isinstance(MODEL_SIMILARITY_CALIBRATION, str)
        assert "date" in MODEL_DATE_ESTIMATION
        assert "calibration" in MODEL_SIMILARITY_CALIBRATION

    def test_get_client_returns_client(self, tmp_mlflow_dir):
        import mlflow

        with patch(
            "rhodesli_ml.config.mlflow_config.MLFLOW_TRACKING_URI", tmp_mlflow_dir
        ):
            from rhodesli_ml.config.mlflow_config import get_client

            mlflow.set_tracking_uri(tmp_mlflow_dir)
            client = get_client()
            assert client is not None

    def test_artifact_paths_exist(self):
        from rhodesli_ml.config.mlflow_config import (
            DATE_ONNX_PATH,
            CALIBRATION_ONNX_PATH,
            ARTIFACTS_DIR,
        )

        assert ARTIFACTS_DIR.is_dir()
        # The actual ONNX files should exist in the repo
        assert DATE_ONNX_PATH.exists(), f"Missing {DATE_ONNX_PATH}"
        assert CALIBRATION_ONNX_PATH.exists(), f"Missing {CALIBRATION_ONNX_PATH}"


class TestModelRegistration:
    """Tests for model registration in MLflow Registry."""

    def test_register_date_estimation(self, tmp_mlflow_dir, mock_date_onnx):
        """Register date estimation model and verify registry state."""
        import mlflow
        from mlflow import MlflowClient

        mlflow.set_tracking_uri(tmp_mlflow_dir)
        client = MlflowClient(tracking_uri=tmp_mlflow_dir)

        model_name = "test-date-estimation"

        # Create registered model
        client.create_registered_model(model_name, description="Test date model")

        # Log ONNX model in a run
        import onnx

        onnx_model = onnx.load(str(mock_date_onnx))

        input_schema = mlflow.types.Schema([
            mlflow.types.TensorSpec(np.dtype(np.float32), (-1, 3, 224, 224), "image")
        ])
        output_schema = mlflow.types.Schema([
            mlflow.types.TensorSpec(np.dtype(np.float32), (-1, 10), "ordinal_logits")
        ])
        signature = mlflow.models.ModelSignature(
            inputs=input_schema, outputs=output_schema
        )

        exp_id = mlflow.create_experiment("test_date")
        with mlflow.start_run(experiment_id=exp_id):
            mlflow.onnx.log_model(
                onnx_model,
                name="model",
                signature=signature,
                registered_model_name=model_name,
            )
            mlflow.log_metrics({"gate_val_mae": 0.320})

        # Verify registration
        versions = client.search_model_versions(f"name='{model_name}'")
        assert len(versions) >= 1

        # Set and verify champion alias
        latest = max(versions, key=lambda v: int(v.version))
        client.set_registered_model_alias(model_name, "champion", latest.version)

        champion = client.get_model_version_by_alias(model_name, "champion")
        assert champion.version == latest.version

    def test_register_calibration(self, tmp_mlflow_dir, mock_calib_onnx):
        """Register calibration model and verify registry state."""
        import mlflow
        from mlflow import MlflowClient

        mlflow.set_tracking_uri(tmp_mlflow_dir)
        client = MlflowClient(tracking_uri=tmp_mlflow_dir)

        model_name = "test-similarity-calibration"
        client.create_registered_model(model_name, description="Test calib model")

        import onnx

        onnx_model = onnx.load(str(mock_calib_onnx))

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

        exp_id = mlflow.create_experiment("test_calib")
        with mlflow.start_run(experiment_id=exp_id):
            mlflow.onnx.log_model(
                onnx_model,
                name="model",
                signature=signature,
                registered_model_name=model_name,
            )
            mlflow.log_metrics({"gate_best_f1": 0.753})

        versions = client.search_model_versions(f"name='{model_name}'")
        assert len(versions) >= 1

        latest = max(versions, key=lambda v: int(v.version))
        client.set_registered_model_alias(model_name, "champion", latest.version)

        champion = client.get_model_version_by_alias(model_name, "champion")
        assert champion.version == latest.version

    def test_gate_tags_on_version(self, tmp_mlflow_dir, mock_date_onnx):
        """Verify gate status tags are set on model versions."""
        import mlflow
        from mlflow import MlflowClient

        mlflow.set_tracking_uri(tmp_mlflow_dir)
        client = MlflowClient(tracking_uri=tmp_mlflow_dir)

        model_name = "test-gate-tags"
        client.create_registered_model(model_name)

        import onnx

        onnx_model = onnx.load(str(mock_date_onnx))
        exp_id = mlflow.create_experiment("test_gate")
        with mlflow.start_run(experiment_id=exp_id):
            mlflow.onnx.log_model(
                onnx_model,
                name="model",
                registered_model_name=model_name,
            )

        versions = client.search_model_versions(f"name='{model_name}'")
        latest = max(versions, key=lambda v: int(v.version))

        # Set gate tags
        client.set_model_version_tag(model_name, latest.version, "gate_status", "passed")
        client.set_model_version_tag(model_name, latest.version, "deployed_to", "production")

        # Verify tags
        version = client.get_model_version(model_name, latest.version)
        assert version.tags["gate_status"] == "passed"
        assert version.tags["deployed_to"] == "production"

    def test_champion_alias_moves_on_new_version(self, tmp_mlflow_dir, mock_date_onnx):
        """Register two versions, move @champion to the second."""
        import mlflow
        from mlflow import MlflowClient

        mlflow.set_tracking_uri(tmp_mlflow_dir)
        client = MlflowClient(tracking_uri=tmp_mlflow_dir)

        model_name = "test-alias-move"
        client.create_registered_model(model_name)

        import onnx

        onnx_model = onnx.load(str(mock_date_onnx))
        exp_id = mlflow.create_experiment("test_alias")

        # Register v1
        with mlflow.start_run(experiment_id=exp_id):
            mlflow.onnx.log_model(
                onnx_model, name="model",
                registered_model_name=model_name,
            )
        client.set_registered_model_alias(model_name, "champion", "1")

        # Register v2
        with mlflow.start_run(experiment_id=exp_id):
            mlflow.onnx.log_model(
                onnx_model, name="model",
                registered_model_name=model_name,
            )

        # Move champion to v2, set candidate on v1
        client.set_registered_model_alias(model_name, "champion", "2")
        client.set_registered_model_alias(model_name, "candidate", "1")

        champion = client.get_model_version_by_alias(model_name, "champion")
        assert int(champion.version) == 2

        candidate = client.get_model_version_by_alias(model_name, "candidate")
        assert int(candidate.version) == 1

    def test_onnx_model_loadable_from_registry(self, tmp_mlflow_dir, mock_date_onnx):
        """Verify ONNX model can be loaded back from registry."""
        import mlflow
        from mlflow import MlflowClient

        mlflow.set_tracking_uri(tmp_mlflow_dir)
        client = MlflowClient(tracking_uri=tmp_mlflow_dir)

        model_name = "test-loadable"
        client.create_registered_model(model_name)

        import onnx

        onnx_model = onnx.load(str(mock_date_onnx))
        exp_id = mlflow.create_experiment("test_load")
        with mlflow.start_run(experiment_id=exp_id):
            mlflow.onnx.log_model(
                onnx_model, name="model",
                registered_model_name=model_name,
            )

        client.set_registered_model_alias(model_name, "champion", "1")

        # Load from registry via alias
        model_uri = f"models:/{model_name}@champion"
        loaded = mlflow.onnx.load_model(model_uri)
        assert loaded is not None


class TestRegistrationScript:
    """Tests for the register_models.py script functions."""

    def test_ensure_registered_model_idempotent(self, tmp_mlflow_dir):
        """Creating a model twice doesn't raise."""
        import mlflow
        from mlflow import MlflowClient
        from rhodesli_ml.scripts.register_models import _ensure_registered_model

        mlflow.set_tracking_uri(tmp_mlflow_dir)
        client = MlflowClient(tracking_uri=tmp_mlflow_dir)

        _ensure_registered_model(client, "test-idempotent", "Test")
        _ensure_registered_model(client, "test-idempotent", "Test")

        models = client.search_registered_models()
        matching = [m for m in models if m.name == "test-idempotent"]
        assert len(matching) == 1

    def test_find_best_date_run_returns_none_for_empty(self, tmp_mlflow_dir):
        """Returns None when no runs exist."""
        import mlflow
        from mlflow import MlflowClient
        from rhodesli_ml.scripts.register_models import _find_best_date_run

        mlflow.set_tracking_uri(tmp_mlflow_dir)
        client = MlflowClient(tracking_uri=tmp_mlflow_dir)

        result = _find_best_date_run(client, "nonexistent_experiment")
        assert result is None
