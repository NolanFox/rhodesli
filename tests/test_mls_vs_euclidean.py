"""Tests for scripts/evaluate_mls_vs_euclidean.py.

Tests the evaluation logic using synthetic embeddings with known properties.
Does NOT require real data files.
"""

import json
import tempfile
from pathlib import Path

import numpy as np
import pytest

# Add project root to path
import sys

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from scripts.evaluate_mls_vs_euclidean import (
    build_pairs,
    compute_auc,
    compute_euclidean,
    compute_mls,
    compute_precision_at_recall,
    evaluate_metric,
    find_optimal_threshold,
    generate_face_id,
    load_confirmed_identities,
    load_face_data,
    score_pairs,
)


# --- Fixtures ---


def make_face_data(n_faces: int = 10, dim: int = 512, seed: int = 0) -> dict:
    """Create synthetic face_data dict with known embeddings."""
    rng = np.random.default_rng(seed)
    face_data = {}
    for i in range(n_faces):
        face_id = f"test_face_{i}"
        face_data[face_id] = {
            "mu": rng.standard_normal(dim).astype(np.float32),
            "sigma_sq": np.full(dim, 0.2, dtype=np.float32),
        }
    return face_data


def make_clustered_face_data(seed: int = 0) -> tuple[dict, list[dict]]:
    """Create face_data with two clear clusters (for reliable AUC tests).

    Returns (face_data, confirmed_identities).
    Cluster A faces are near [1,0,0,...], cluster B faces are near [0,1,0,...].
    """
    rng = np.random.default_rng(seed)
    dim = 512
    face_data = {}
    noise_scale = 0.05

    # Cluster A: 5 faces near a base vector
    base_a = np.zeros(dim, dtype=np.float32)
    base_a[0] = 1.0
    a_ids = []
    for i in range(5):
        fid = f"cluster_a_face_{i}"
        face_data[fid] = {
            "mu": (base_a + rng.standard_normal(dim).astype(np.float32) * noise_scale),
            "sigma_sq": np.full(dim, 0.2, dtype=np.float32),
        }
        a_ids.append(fid)

    # Cluster B: 5 faces near a different base vector
    base_b = np.zeros(dim, dtype=np.float32)
    base_b[1] = 1.0
    b_ids = []
    for i in range(5):
        fid = f"cluster_b_face_{i}"
        face_data[fid] = {
            "mu": (base_b + rng.standard_normal(dim).astype(np.float32) * noise_scale),
            "sigma_sq": np.full(dim, 0.2, dtype=np.float32),
        }
        b_ids.append(fid)

    confirmed = [
        {"identity_id": "id_a", "name": "Person A", "anchor_ids": a_ids},
        {"identity_id": "id_b", "name": "Person B", "anchor_ids": b_ids},
    ]

    return face_data, confirmed


# --- Unit Tests ---


class TestGenerateFaceId:
    def test_basic(self):
        assert generate_face_id("photo.jpg", 0) == "photo:face0"

    def test_with_path(self):
        assert generate_face_id("raw_photos/photo.jpg", 2) == "photo:face2"

    def test_compress_suffix(self):
        assert generate_face_id("Image 001_compress.jpg", 1) == "Image 001_compress:face1"


class TestComputeEuclidean:
    def test_identical_vectors(self):
        mu = np.ones(512, dtype=np.float32)
        assert compute_euclidean(mu, mu) == pytest.approx(0.0, abs=1e-6)

    def test_known_distance(self):
        mu_a = np.zeros(512, dtype=np.float32)
        mu_b = np.zeros(512, dtype=np.float32)
        mu_b[0] = 3.0
        mu_b[1] = 4.0
        assert compute_euclidean(mu_a, mu_b) == pytest.approx(5.0, abs=1e-5)

    def test_symmetry(self):
        rng = np.random.default_rng(0)
        mu_a = rng.standard_normal(512).astype(np.float32)
        mu_b = rng.standard_normal(512).astype(np.float32)
        assert compute_euclidean(mu_a, mu_b) == pytest.approx(
            compute_euclidean(mu_b, mu_a), abs=1e-6
        )


class TestComputeMLS:
    def test_identical_embeddings_high_score(self):
        mu = np.ones(512, dtype=np.float32)
        sigma = np.full(512, 0.1, dtype=np.float32)
        score = compute_mls(mu, sigma, mu, sigma)
        # MLS of identical embeddings should be the highest possible
        # (only the log penalty term, no distance penalty)
        assert score > -5.0  # reasonable upper bound for scalar sigma

    def test_distant_embeddings_low_score(self):
        mu_a = np.zeros(512, dtype=np.float32)
        mu_b = np.ones(512, dtype=np.float32) * 10.0
        sigma = np.full(512, 0.1, dtype=np.float32)
        score = compute_mls(mu_a, sigma, mu_b, sigma)
        assert score < -1000.0  # very negative for distant embeddings

    def test_higher_sigma_reduces_penalty(self):
        """Higher uncertainty should reduce the distance penalty."""
        mu_a = np.zeros(512, dtype=np.float32)
        mu_b = np.ones(512, dtype=np.float32)
        sigma_low = np.full(512, 0.1, dtype=np.float32)
        sigma_high = np.full(512, 10.0, dtype=np.float32)

        score_low_sigma = compute_mls(mu_a, sigma_low, mu_b, sigma_low)
        score_high_sigma = compute_mls(mu_a, sigma_high, mu_b, sigma_high)

        # High sigma should give a LESS negative score (distance penalty reduced)
        assert score_high_sigma > score_low_sigma

    def test_symmetry(self):
        rng = np.random.default_rng(0)
        mu_a = rng.standard_normal(512).astype(np.float32)
        mu_b = rng.standard_normal(512).astype(np.float32)
        sigma_a = np.full(512, 0.3, dtype=np.float32)
        sigma_b = np.full(512, 0.5, dtype=np.float32)
        assert compute_mls(mu_a, sigma_a, mu_b, sigma_b) == pytest.approx(
            compute_mls(mu_b, sigma_b, mu_a, sigma_a), abs=1e-5
        )


class TestComputeAUC:
    def test_perfect_separation(self):
        labels = np.array([1, 1, 1, 0, 0, 0])
        scores = np.array([0.9, 0.8, 0.7, 0.3, 0.2, 0.1])
        assert compute_auc(labels, scores) == pytest.approx(1.0, abs=1e-6)

    def test_random_labels(self):
        labels = np.array([1, 0, 1, 0, 1, 0])
        scores = np.array([0.5, 0.5, 0.5, 0.5, 0.5, 0.5])
        # All tied scores -> AUC should be around 0.5
        auc = compute_auc(labels, scores)
        assert 0.3 <= auc <= 0.7

    def test_worst_case(self):
        labels = np.array([0, 0, 0, 1, 1, 1])
        scores = np.array([0.9, 0.8, 0.7, 0.3, 0.2, 0.1])
        assert compute_auc(labels, scores) == pytest.approx(0.0, abs=1e-6)

    def test_no_positives(self):
        labels = np.array([0, 0, 0])
        scores = np.array([0.9, 0.5, 0.1])
        assert compute_auc(labels, scores) == 0.5

    def test_no_negatives(self):
        labels = np.array([1, 1, 1])
        scores = np.array([0.9, 0.5, 0.1])
        assert compute_auc(labels, scores) == 0.5


class TestComputePrecisionAtRecall:
    def test_perfect_precision_at_recall(self):
        labels = np.array([1, 1, 1, 0, 0, 0])
        scores = np.array([0.9, 0.8, 0.7, 0.3, 0.2, 0.1])
        # At recall=0.95, we need 3/3 positives -> all 3 positives are top-ranked
        prec = compute_precision_at_recall(labels, scores, 0.95)
        assert prec == pytest.approx(1.0, abs=1e-6)

    def test_lower_precision(self):
        labels = np.array([1, 0, 1, 0, 1, 0])
        scores = np.array([0.9, 0.85, 0.7, 0.6, 0.5, 0.1])
        # To get recall >= 0.95 (3/3), we need top 5 items
        prec = compute_precision_at_recall(labels, scores, 0.95)
        assert prec == pytest.approx(3 / 5, abs=1e-6)

    def test_no_positives(self):
        labels = np.array([0, 0, 0])
        scores = np.array([0.9, 0.5, 0.1])
        assert compute_precision_at_recall(labels, scores, 0.95) == 0.0


class TestFindOptimalThreshold:
    def test_perfect_separation(self):
        labels = np.array([1, 1, 1, 0, 0, 0])
        scores = np.array([0.9, 0.8, 0.7, 0.3, 0.2, 0.1])
        threshold, f1 = find_optimal_threshold(labels, scores)
        assert f1 == pytest.approx(1.0, abs=0.02)  # near-perfect F1
        assert 0.3 < threshold < 0.9  # threshold between clusters


class TestBuildPairs:
    def test_same_pairs_count(self):
        face_data, confirmed = make_clustered_face_data()
        same, cross = build_pairs(confirmed, face_data, cross_pair_count=10, seed=42)
        # 5 faces in cluster A -> C(5,2) = 10 same pairs
        # 5 faces in cluster B -> C(5,2) = 10 same pairs
        assert len(same) == 20

    def test_cross_pairs_count(self):
        face_data, confirmed = make_clustered_face_data()
        same, cross = build_pairs(confirmed, face_data, cross_pair_count=15, seed=42)
        assert len(cross) == 15

    def test_cross_pairs_different_identities(self):
        face_data, confirmed = make_clustered_face_data()
        same, cross = build_pairs(confirmed, face_data, cross_pair_count=10, seed=42)
        for pair in cross:
            assert pair["identity_a"] != pair["identity_b"]

    def test_same_pairs_same_identity(self):
        face_data, confirmed = make_clustered_face_data()
        same, cross = build_pairs(confirmed, face_data, cross_pair_count=10, seed=42)
        for pair in same:
            assert pair["identity_a"] == pair["identity_b"]

    def test_missing_faces_filtered(self):
        """Faces not in face_data are excluded from pairs."""
        face_data = {
            "f1": {"mu": np.zeros(512, dtype=np.float32), "sigma_sq": np.full(512, 0.2, dtype=np.float32)},
            "f2": {"mu": np.ones(512, dtype=np.float32), "sigma_sq": np.full(512, 0.2, dtype=np.float32)},
        }
        confirmed = [
            {"identity_id": "id1", "name": "P1", "anchor_ids": ["f1", "f2", "f_missing"]},
        ]
        same, cross = build_pairs(confirmed, face_data, cross_pair_count=10, seed=42)
        # Only f1 and f2 are valid -> C(2,2) = 1 same pair
        assert len(same) == 1

    def test_single_identity_no_cross_pairs(self):
        face_data, confirmed = make_clustered_face_data()
        same, cross = build_pairs([confirmed[0]], face_data, cross_pair_count=10, seed=42)
        assert len(cross) == 0

    def test_reproducible_with_seed(self):
        face_data, confirmed = make_clustered_face_data()
        _, cross1 = build_pairs(confirmed, face_data, cross_pair_count=10, seed=99)
        _, cross2 = build_pairs(confirmed, face_data, cross_pair_count=10, seed=99)
        assert [p["face_a"] for p in cross1] == [p["face_a"] for p in cross2]


class TestScorePairs:
    def test_scores_added(self):
        face_data, confirmed = make_clustered_face_data()
        same, _ = build_pairs(confirmed, face_data, cross_pair_count=0, seed=42)
        scored = score_pairs(same[:3], face_data)
        for pair in scored:
            assert "euclidean" in pair
            assert "mls" in pair
            assert isinstance(pair["euclidean"], float)
            assert isinstance(pair["mls"], float)

    def test_same_cluster_distances_small(self):
        """Same-cluster faces should have small Euclidean distances."""
        face_data, confirmed = make_clustered_face_data()
        same, _ = build_pairs(confirmed, face_data, cross_pair_count=0, seed=42)
        scored = score_pairs(same, face_data)
        for pair in scored:
            # Within-cluster noise_scale=0.05, so distances should be small
            assert pair["euclidean"] < 5.0


class TestEvaluateMetric:
    def test_euclidean_high_auc_for_separated_clusters(self):
        face_data, confirmed = make_clustered_face_data()
        same, cross = build_pairs(confirmed, face_data, cross_pair_count=25, seed=42)
        scored_same = score_pairs(same, face_data)
        scored_cross = score_pairs(cross, face_data)

        same_euc = np.array([p["euclidean"] for p in scored_same])
        cross_euc = np.array([p["euclidean"] for p in scored_cross])

        results = evaluate_metric(same_euc, cross_euc, "Euclidean", higher_is_same=False)
        assert results["auc"] > 0.95

    def test_mls_returns_valid_auc(self):
        face_data, confirmed = make_clustered_face_data()
        same, cross = build_pairs(confirmed, face_data, cross_pair_count=25, seed=42)
        scored_same = score_pairs(same, face_data)
        scored_cross = score_pairs(cross, face_data)

        same_mls = np.array([p["mls"] for p in scored_same])
        cross_mls = np.array([p["mls"] for p in scored_cross])

        results = evaluate_metric(same_mls, cross_mls, "MLS", higher_is_same=True)
        assert 0.0 <= results["auc"] <= 1.0

    def test_result_keys(self):
        same_scores = np.array([0.5, 0.6, 0.7])
        cross_scores = np.array([1.2, 1.3, 1.4])
        results = evaluate_metric(same_scores, cross_scores, "test", higher_is_same=False)
        expected_keys = {
            "metric", "auc", "precision_at_recall_95", "optimal_threshold",
            "optimal_f1", "same_mean", "same_std", "same_min", "same_max",
            "cross_mean", "cross_std", "cross_min", "cross_max",
        }
        assert set(results.keys()) == expected_keys


class TestLoadFaceData:
    def test_load_from_npy(self, tmp_path):
        """Test loading from a synthetic .npy file."""
        embeddings = np.array([
            {
                "filename": "photo1.jpg",
                "mu": np.ones(512, dtype=np.float32),
                "sigma_sq": np.full(512, 0.2, dtype=np.float32),
                "det_score": 0.9,
                "bbox": [10, 20, 100, 200],
            },
            {
                "filename": "photo1.jpg",
                "mu": np.zeros(512, dtype=np.float32),
                "sigma_sq": np.full(512, 0.3, dtype=np.float32),
                "det_score": 0.8,
                "bbox": [200, 20, 300, 200],
            },
        ], dtype=object)

        np.save(tmp_path / "embeddings.npy", embeddings)
        face_data = load_face_data(tmp_path)
        assert len(face_data) == 2
        assert "photo1:face0" in face_data
        assert "photo1:face1" in face_data
        assert face_data["photo1:face0"]["mu"].shape == (512,)

    def test_load_with_face_id(self, tmp_path):
        """Test loading entries that have explicit face_id."""
        embeddings = np.array([
            {
                "filename": "photo1.jpg",
                "face_id": "inbox_abc123",
                "mu": np.ones(512, dtype=np.float32),
                "sigma_sq": np.full(512, 0.2, dtype=np.float32),
                "det_score": 0.9,
                "bbox": [10, 20, 100, 200],
            },
        ], dtype=object)

        np.save(tmp_path / "embeddings.npy", embeddings)
        face_data = load_face_data(tmp_path)
        assert "inbox_abc123" in face_data

    def test_load_legacy_embeddings_key(self, tmp_path):
        """Legacy `embeddings` rows are normalized into `mu`/`sigma_sq` face data."""
        embeddings = np.array([
            {
                "filename": "photo2.jpg",
                "embeddings": np.ones(512, dtype=np.float32),
                "det_score": 0.75,
            },
        ], dtype=object)

        np.save(tmp_path / "embeddings.npy", embeddings)
        face_data = load_face_data(tmp_path)
        assert "photo2:face0" in face_data
        assert face_data["photo2:face0"]["mu"].shape == (512,)
        assert face_data["photo2:face0"]["sigma_sq"].shape == (512,)

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_face_data(tmp_path)


class TestLoadConfirmedIdentities:
    def test_load_confirmed(self, tmp_path):
        identities = {
            "schema_version": 1,
            "identities": {
                "id1": {
                    "identity_id": "id1",
                    "name": "Alice",
                    "state": "CONFIRMED",
                    "anchor_ids": ["f1", "f2", "f3"],
                    "candidate_ids": [],
                    "negative_ids": [],
                },
                "id2": {
                    "identity_id": "id2",
                    "name": "Bob",
                    "state": "PROPOSED",
                    "anchor_ids": ["f4", "f5"],
                    "candidate_ids": [],
                    "negative_ids": [],
                },
                "id3": {
                    "identity_id": "id3",
                    "name": "Charlie",
                    "state": "CONFIRMED",
                    "anchor_ids": ["f6"],
                    "candidate_ids": [],
                    "negative_ids": [],
                },
            },
        }
        with open(tmp_path / "identities.json", "w") as f:
            json.dump(identities, f)

        confirmed = load_confirmed_identities(tmp_path)
        assert len(confirmed) == 1  # Only Alice (CONFIRMED with 3 anchors)
        assert confirmed[0]["name"] == "Alice"
        assert confirmed[0]["anchor_ids"] == ["f1", "f2", "f3"]

    def test_merged_excluded(self, tmp_path):
        identities = {
            "schema_version": 1,
            "identities": {
                "id1": {
                    "identity_id": "id1",
                    "name": "Alice",
                    "state": "CONFIRMED",
                    "anchor_ids": ["f1", "f2"],
                    "candidate_ids": [],
                    "negative_ids": [],
                    "merged_into": "id2",
                },
            },
        }
        with open(tmp_path / "identities.json", "w") as f:
            json.dump(identities, f)

        confirmed = load_confirmed_identities(tmp_path)
        assert len(confirmed) == 0

    def test_dict_anchor_format(self, tmp_path):
        identities = {
            "schema_version": 1,
            "identities": {
                "id1": {
                    "identity_id": "id1",
                    "name": "Alice",
                    "state": "CONFIRMED",
                    "anchor_ids": [
                        {"face_id": "f1", "provenance": "human"},
                        {"face_id": "f2", "provenance": "human"},
                    ],
                    "candidate_ids": [],
                    "negative_ids": [],
                },
            },
        }
        with open(tmp_path / "identities.json", "w") as f:
            json.dump(identities, f)

        confirmed = load_confirmed_identities(tmp_path)
        assert len(confirmed) == 1
        assert confirmed[0]["anchor_ids"] == ["f1", "f2"]

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_confirmed_identities(tmp_path)
