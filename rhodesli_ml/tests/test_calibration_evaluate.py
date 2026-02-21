"""Tests for calibration evaluation against baseline."""

import json
import tempfile
from pathlib import Path

import numpy as np
import pytest
import torch

from rhodesli_ml.calibration.evaluate import (
    compare_baseline_vs_calibrated,
    euclidean_baseline_metrics,
    load_model,
)
from rhodesli_ml.calibration.model import CalibrationModel
from rhodesli_ml.calibration.train import train


@pytest.fixture
def data_dir():
    """Create test data directory."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        rng = np.random.RandomState(42)

        identities_data = {"schema_version": 1, "identities": {}}
        all_face_ids = []

        for i in range(5):
            iid = f"multi-{i}"
            fids = [f"face-m{i}-{j}" for j in range(3)]
            all_face_ids.extend(fids)
            identities_data["identities"][iid] = {
                "identity_id": iid, "name": f"Person {i}", "state": "CONFIRMED",
                "anchor_ids": fids, "candidate_ids": [], "negative_ids": [],
            }

        for i in range(5):
            iid = f"single-{i}"
            fid = f"face-s{i}"
            all_face_ids.append(fid)
            identities_data["identities"][iid] = {
                "identity_id": iid, "name": f"Solo {i}", "state": "CONFIRMED",
                "anchor_ids": [fid], "candidate_ids": [], "negative_ids": [],
            }

        (tmp_path / "identities.json").write_text(json.dumps(identities_data))

        entries = []
        for fid in all_face_ids:
            identity_prefix = fid.rsplit("-", 1)[0]
            base_rng = np.random.RandomState(hash(identity_prefix) % 10000)
            base_vec = base_rng.randn(512).astype(np.float32)
            base_vec = base_vec / np.linalg.norm(base_vec)
            noise = rng.randn(512).astype(np.float32) * 0.1
            mu = base_vec + noise
            mu = mu / np.linalg.norm(mu)
            entries.append({
                "filename": f"{fid}.jpg", "face_id": fid, "mu": mu,
                "bbox": [0, 0, 100, 100], "det_score": 0.99, "quality": 0.8,
            })
        np.save(tmp_path / "embeddings.npy", np.array(entries, dtype=object))
        yield tmp_path


@pytest.fixture
def trained_model(data_dir):
    """Train a small model and return its path."""
    with tempfile.TemporaryDirectory() as out_tmp:
        out_path = Path(out_tmp)
        results = train(
            data_dir=data_dir, output_dir=out_path,
            epochs=5, batch_size=16, use_mlflow=False,
        )
        model_path = Path(results["model_path"])
        yield model_path


class TestEuclideanBaseline:
    def test_metrics_computed(self):
        pairs = [
            (np.random.randn(512).astype(np.float32),
             np.random.randn(512).astype(np.float32),
             float(i % 2)) for i in range(40)
        ]
        metrics = euclidean_baseline_metrics(pairs)
        assert "precision_0.5" in metrics
        assert "recall_0.5" in metrics
        assert "roc_auc" in metrics

    def test_identical_pairs_high_score(self):
        """Identical embeddings should produce high match scores."""
        v = np.random.randn(512).astype(np.float32)
        v = v / np.linalg.norm(v)
        pairs = [(v, v, 1.0)] * 10 + [
            (np.random.randn(512).astype(np.float32),
             np.random.randn(512).astype(np.float32), 0.0)
            for _ in range(10)
        ]
        metrics = euclidean_baseline_metrics(pairs)
        assert metrics["precision_0.5"] > 0  # Should detect identical pairs

    def test_metrics_range(self):
        pairs = [
            (np.random.randn(512).astype(np.float32),
             np.random.randn(512).astype(np.float32),
             float(i % 2)) for i in range(40)
        ]
        metrics = euclidean_baseline_metrics(pairs)
        for key, val in metrics.items():
            if key != "best_threshold":
                assert 0.0 <= val <= 1.0, f"{key}={val} out of range"


class TestLoadModel:
    def test_load_saved_model(self, trained_model):
        model = load_model(trained_model)
        assert isinstance(model, CalibrationModel)
        # Model should be in eval mode
        assert not model.training

    def test_model_produces_output(self, trained_model):
        model = load_model(trained_model)
        emb_a = torch.randn(1, 512)
        emb_b = torch.randn(1, 512)
        with torch.no_grad():
            out = model(emb_a, emb_b)
        assert out.shape == (1, 1)
        assert 0 <= out.item() <= 1


class TestCompareBaselineVsCalibrated:
    def test_comparison_returns_all_keys(self, data_dir, trained_model):
        results = compare_baseline_vs_calibrated(data_dir, trained_model)
        assert "baseline" in results
        assert "calibrated" in results
        assert "deltas" in results

    def test_deltas_computed(self, data_dir, trained_model):
        results = compare_baseline_vs_calibrated(data_dir, trained_model)
        assert len(results["deltas"]) > 0
        # Deltas should be differences
        for key in results["deltas"]:
            if key in results["baseline"] and key in results["calibrated"]:
                expected = results["calibrated"][key] - results["baseline"][key]
                assert abs(results["deltas"][key] - expected) < 0.001
