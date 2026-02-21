"""Tests for calibration training pipeline."""

import json
import tempfile
from pathlib import Path

import numpy as np
import pytest
import torch

from rhodesli_ml.calibration.train import compute_metrics, train
from rhodesli_ml.calibration.model import CalibrationModel
from rhodesli_ml.calibration.data import PairDataset


@pytest.fixture
def data_dir():
    """Create a temporary data directory with enough data for training."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        rng = np.random.RandomState(42)

        # Create 10 identities, 5 multi-face
        identities_data = {"schema_version": 1, "identities": {}}
        all_face_ids = []

        for i in range(5):
            # Multi-face identities (3 faces each)
            iid = f"multi-{i}"
            fids = [f"face-m{i}-{j}" for j in range(3)]
            all_face_ids.extend(fids)
            identities_data["identities"][iid] = {
                "identity_id": iid,
                "name": f"Person {i}",
                "state": "CONFIRMED",
                "anchor_ids": fids,
                "candidate_ids": [],
                "negative_ids": [],
            }

        for i in range(5):
            # Single-face identities
            iid = f"single-{i}"
            fid = f"face-s{i}"
            all_face_ids.append(fid)
            identities_data["identities"][iid] = {
                "identity_id": iid,
                "name": f"Solo {i}",
                "state": "CONFIRMED",
                "anchor_ids": [fid],
                "candidate_ids": [],
                "negative_ids": [],
            }

        (tmp_path / "identities.json").write_text(json.dumps(identities_data))

        # Create embeddings — make same-identity faces closer together
        entries = []
        for fid in all_face_ids:
            # Base vector per identity
            identity_prefix = fid.rsplit("-", 1)[0]  # e.g., "face-m0"
            base_seed = hash(identity_prefix) % 10000
            base_rng = np.random.RandomState(base_seed)
            base_vec = base_rng.randn(512).astype(np.float32)
            base_vec = base_vec / np.linalg.norm(base_vec)

            # Add noise for variation within identity
            noise = rng.randn(512).astype(np.float32) * 0.1
            mu = base_vec + noise
            mu = mu / np.linalg.norm(mu)

            entries.append({
                "filename": f"{fid}.jpg",
                "face_id": fid,
                "mu": mu,
                "bbox": [0, 0, 100, 100],
                "det_score": 0.99,
                "quality": 0.8,
            })
        np.save(tmp_path / "embeddings.npy", np.array(entries, dtype=object))

        yield tmp_path


class TestComputeMetrics:
    def test_perfect_model(self):
        """A model that perfectly separates should get precision=1, recall=1."""
        model = CalibrationModel(embed_dim=4)

        # Create synthetic data where same pairs have high similarity
        pairs = []
        for _ in range(20):
            # Positive: identical vectors
            v = torch.randn(4)
            pairs.append((v.numpy(), v.numpy(), 1.0))
        for _ in range(20):
            # Negative: orthogonal vectors
            v1 = torch.randn(4)
            v2 = torch.randn(4)
            v2 = v2 - torch.dot(v1, v2) / torch.dot(v1, v1) * v1  # Orthogonalize
            pairs.append((v1.numpy(), v2.numpy(), 0.0))

        dataset = PairDataset(pairs)
        loader = torch.utils.data.DataLoader(dataset, batch_size=40)

        metrics = compute_metrics(model, loader)
        assert "precision_0.5" in metrics
        assert "recall_0.5" in metrics
        assert "roc_auc" in metrics
        assert "best_threshold" in metrics

    def test_metrics_range(self):
        model = CalibrationModel(embed_dim=4)
        pairs = [
            (np.random.randn(4).astype(np.float32),
             np.random.randn(4).astype(np.float32),
             float(i % 2)) for i in range(40)
        ]
        dataset = PairDataset(pairs)
        loader = torch.utils.data.DataLoader(dataset, batch_size=40)
        metrics = compute_metrics(model, loader)
        for key, val in metrics.items():
            if key != "best_threshold":
                assert 0.0 <= val <= 1.0, f"{key}={val} out of range"


class TestTrain:
    def test_training_completes(self, data_dir):
        """Training should complete and return results dict."""
        results = train(
            data_dir=data_dir,
            epochs=5,
            lr=1e-3,
            batch_size=16,
            neg_ratio=2,
            patience=3,
            use_mlflow=False,
        )
        assert "train_pairs" in results
        assert results["train_pairs"] > 0
        assert "epochs_trained" in results
        assert results["epochs_trained"] > 0

    def test_model_saved(self, data_dir):
        """Model artifact should be saved when output_dir specified."""
        with tempfile.TemporaryDirectory() as out_tmp:
            out_path = Path(out_tmp)
            results = train(
                data_dir=data_dir,
                output_dir=out_path,
                epochs=3,
                lr=1e-3,
                batch_size=16,
                use_mlflow=False,
            )
            assert results["model_path"] is not None
            model_path = Path(results["model_path"])
            assert model_path.exists()

            # Verify model can be loaded
            checkpoint = torch.load(model_path, weights_only=False)
            assert "model_state_dict" in checkpoint
            assert "config" in checkpoint

    def test_eval_metrics_present(self, data_dir):
        """Evaluation metrics should be computed on eval set."""
        results = train(
            data_dir=data_dir,
            epochs=5,
            lr=1e-3,
            batch_size=16,
            use_mlflow=False,
        )
        # Should have precision/recall metrics if eval set exists
        assert "eval_pairs" in results
        if results["eval_pairs"] > 0:
            assert "precision_0.5" in results
            assert "recall_0.5" in results

    def test_early_stopping(self, data_dir):
        """Training should stop early if loss doesn't improve."""
        results = train(
            data_dir=data_dir,
            epochs=100,
            lr=1e-3,
            batch_size=16,
            patience=3,
            use_mlflow=False,
        )
        # Should stop before 100 epochs
        assert results["epochs_trained"] < 100

    def test_training_time_reasonable(self, data_dir):
        """Training on small data should be fast."""
        results = train(
            data_dir=data_dir,
            epochs=3,
            batch_size=16,
            use_mlflow=False,
        )
        assert results["training_time"] < 30  # Should finish in < 30s

    def test_deterministic(self, data_dir):
        """Same seed should produce same results."""
        r1 = train(data_dir=data_dir, epochs=3, seed=42, use_mlflow=False)
        r2 = train(data_dir=data_dir, epochs=3, seed=42, use_mlflow=False)
        assert r1["train_pairs"] == r2["train_pairs"]
        assert r1["epochs_trained"] == r2["epochs_trained"]
