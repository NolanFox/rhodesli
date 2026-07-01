"""Tests for the model promotion pipeline.

Tests gate -> register -> alias -> export workflow.
Uses temporary MLflow directories for isolation.
"""

import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

# CI installs requirements.txt only (no mlflow). The promote pipeline (gate/register/
# promote) uses mlflow in a fixture + tests, imported at runtime, so --collect-only
# can't see it; skip the module when mlflow is absent (Session 168 Fable P0).
pytest.importorskip("mlflow", exc_type=ImportError)


@pytest.fixture
def tmp_mlflow_dir(tmp_path):
    """Create isolated MLflow tracking directory."""
    mlruns = tmp_path / "mlruns"
    mlruns.mkdir()
    return str(mlruns)


@pytest.fixture
def mock_onnx(tmp_path):
    """Create a minimal ONNX model file."""
    import onnx
    from onnx import TensorProto, helper

    X = helper.make_tensor_value_info("image", TensorProto.FLOAT, [1, 3, 224, 224])
    Y = helper.make_tensor_value_info("ordinal_logits", TensorProto.FLOAT, [1, 10])

    graph = helper.make_graph(
        [
            helper.make_node(
                "ConstantOfShape",
                ["output_shape"],
                ["ordinal_logits"],
                value=helper.make_tensor("val", TensorProto.FLOAT, [1], [0.5]),
            ),
        ],
        "test",
        [X],
        [Y],
        [helper.make_tensor("output_shape", TensorProto.INT64, [2], [1, 10])],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)])
    model.ir_version = 8

    path = tmp_path / "test_model.onnx"
    onnx.save(model, str(path))
    return path


@pytest.fixture
def patched_mlflow(tmp_mlflow_dir, tmp_path):
    """Patch MLflow config to use temp directory."""
    import mlflow

    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)

    mlflow.set_tracking_uri(tmp_mlflow_dir)

    with patch("rhodesli_ml.config.mlflow_config.MLFLOW_TRACKING_URI", tmp_mlflow_dir), \
         patch("rhodesli_ml.config.mlflow_config.ARTIFACTS_DIR", artifacts_dir):
        yield {
            "tracking_uri": tmp_mlflow_dir,
            "artifacts_dir": artifacts_dir,
        }


class TestPromote:
    """Tests for the promote() function."""

    def test_promote_passing_model(self, patched_mlflow, mock_onnx):
        """Passing gate result -> model registered as @champion."""
        import mlflow
        from mlflow import MlflowClient
        from rhodesli_ml.scripts.promote_model import promote

        client = MlflowClient(tracking_uri=patched_mlflow["tracking_uri"])
        model_name = "test-promote-pass"
        client.create_registered_model(model_name)
        mlflow.create_experiment("rhodesli_date_estimation")

        gate_result = {
            "passed": True,
            "metrics": {
                "exact_accuracy": 0.73,
                "adjacent_accuracy": 0.96,
                "mae_decades": 0.32,
                "n_samples": 250,
            },
            "thresholds": {"min_adjacent_accuracy": 0.70, "max_mae_decades": 1.5},
            "failure_reasons": [],
        }

        # Need to also patch the model name mapping
        with patch.dict(
            "rhodesli_ml.scripts.promote_model.__builtins__",
        ):
            result = promote(model_name, mock_onnx, gate_result)

        assert result is True

        # Verify champion alias
        champion = client.get_model_version_by_alias(model_name, "champion")
        assert champion is not None
        assert champion.tags["gate_status"] == "passed"

    def test_promote_failing_model(self, patched_mlflow, mock_onnx):
        """Failing gate result -> model registered but NOT @champion."""
        import mlflow
        from mlflow import MlflowClient
        from rhodesli_ml.scripts.promote_model import promote

        client = MlflowClient(tracking_uri=patched_mlflow["tracking_uri"])
        model_name = "test-promote-fail"
        client.create_registered_model(model_name)
        mlflow.create_experiment("rhodesli_date_estimation_fail")

        gate_result = {
            "passed": False,
            "metrics": {
                "exact_accuracy": 0.30,
                "adjacent_accuracy": 0.50,
                "mae_decades": 2.1,
                "n_samples": 250,
            },
            "thresholds": {"min_adjacent_accuracy": 0.70, "max_mae_decades": 1.5},
            "failure_reasons": ["Adjacent accuracy 0.500 < 0.70"],
        }

        result = promote(model_name, mock_onnx, gate_result)

        assert result is False

        # Version registered but no champion alias
        versions = client.search_model_versions(f"name='{model_name}'")
        assert len(versions) >= 1
        latest = max(versions, key=lambda v: int(v.version))
        assert latest.tags["gate_status"] == "failed"

        # No champion alias
        with pytest.raises(Exception):
            client.get_model_version_by_alias(model_name, "champion")

    def test_promote_demotes_previous_champion(self, patched_mlflow, mock_onnx):
        """Promoting new champion demotes previous to @candidate."""
        import mlflow
        import onnx
        from mlflow import MlflowClient
        from rhodesli_ml.scripts.promote_model import promote

        client = MlflowClient(tracking_uri=patched_mlflow["tracking_uri"])
        model_name = "test-promote-demote"
        client.create_registered_model(model_name)

        exp_id = mlflow.create_experiment("rhodesli_date_estimation_demote")

        # Register v1 as champion
        onnx_model = onnx.load(str(mock_onnx))
        with mlflow.start_run(experiment_id=exp_id):
            mlflow.onnx.log_model(onnx_model, name="model", registered_model_name=model_name)
        client.set_registered_model_alias(model_name, "champion", "1")

        # Promote v2
        gate_result = {
            "passed": True,
            "metrics": {"mae_decades": 0.25, "adjacent_accuracy": 0.97, "n_samples": 300},
            "thresholds": {},
            "failure_reasons": [],
        }

        result = promote(model_name, mock_onnx, gate_result)
        assert result is True

        champion = client.get_model_version_by_alias(model_name, "champion")
        assert int(champion.version) == 2

        candidate = client.get_model_version_by_alias(model_name, "candidate")
        assert int(candidate.version) == 1

    def test_dry_run_no_registration(self, patched_mlflow, mock_onnx):
        """Dry run does not create model versions."""
        from mlflow import MlflowClient
        from rhodesli_ml.scripts.promote_model import promote

        client = MlflowClient(tracking_uri=patched_mlflow["tracking_uri"])
        model_name = "test-dry-run"
        client.create_registered_model(model_name)

        gate_result = {
            "passed": True,
            "metrics": {"mae_decades": 0.32},
            "thresholds": {},
            "failure_reasons": [],
        }

        result = promote(model_name, mock_onnx, gate_result, dry_run=True)
        assert result is True

        versions = client.search_model_versions(f"name='{model_name}'")
        assert len(versions) == 0

    def test_promote_copies_onnx_to_artifacts(self, patched_mlflow, mock_onnx):
        """Successful promotion copies ONNX to artifacts directory."""
        import mlflow
        from mlflow import MlflowClient
        from rhodesli_ml.scripts.promote_model import promote

        client = MlflowClient(tracking_uri=patched_mlflow["tracking_uri"])
        model_name = "test-copy-onnx"
        client.create_registered_model(model_name)
        mlflow.create_experiment("rhodesli_date_estimation_copy")

        gate_result = {
            "passed": True,
            "metrics": {"mae_decades": 0.32, "n_samples": 250},
            "thresholds": {},
            "failure_reasons": [],
        }

        result = promote(model_name, mock_onnx, gate_result)
        assert result is True

        # ONNX should be copied to artifacts dir
        dest = patched_mlflow["artifacts_dir"] / mock_onnx.name
        assert dest.exists()


class TestDateGate:
    """Tests for run_date_gate()."""

    def test_gate_with_no_labels(self, tmp_path):
        """Empty labels -> gate fails."""
        labels_path = tmp_path / "empty_labels.json"
        labels_path.write_text("[]")

        from rhodesli_ml.scripts.promote_model import run_date_gate

        result = run_date_gate(
            Path("rhodesli_ml/artifacts/date_estimation_v1.onnx"),
            labels_path,
        )
        assert result["passed"] is False
        assert "No evaluation data" in result["failure_reasons"][0]

    def test_gate_result_structure(self, tmp_path):
        """Gate result has all required keys."""
        labels_path = tmp_path / "empty.json"
        labels_path.write_text("[]")

        from rhodesli_ml.scripts.promote_model import run_date_gate

        result = run_date_gate(
            Path("rhodesli_ml/artifacts/date_estimation_v1.onnx"),
            labels_path,
        )
        assert "passed" in result
        assert "metrics" in result
        assert "thresholds" in result
        assert "failure_reasons" in result
        assert isinstance(result["passed"], bool)
        assert isinstance(result["failure_reasons"], list)

    def test_gate_with_no_photos_available(self, tmp_path):
        """Labels with no accessible photos -> fails gracefully."""
        labels_path = tmp_path / "labels.json"
        labels_path.write_text(json.dumps([
            {"photo_path": "/nonexistent/photo.jpg", "estimated_decade": 1940},
            {"photo_path": "/nonexistent/photo2.jpg", "estimated_decade": 1950},
        ]))

        from rhodesli_ml.scripts.promote_model import run_date_gate

        result = run_date_gate(
            Path("rhodesli_ml/artifacts/date_estimation_v1.onnx"),
            labels_path,
        )
        assert result["passed"] is False
        assert "No photos available" in result["failure_reasons"][0]
