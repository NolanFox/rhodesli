"""Tests for scripts/compare_ml_embeddings.py — Session 120 Phase 1."""

import numpy as np
import pytest
import sys
from pathlib import Path

# Add project root to path so we can import the script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from compare_ml_embeddings import (
    compute_cosine_similarity,
    compute_iou,
    match_faces_by_order_and_iou,
    compare_embeddings,
    check_exit_code,
    SIMILARITY_THRESHOLD,
)


# --- Test cosine similarity ---


class TestCosineSimilarity:
    def test_identical_normed_vectors(self):
        """Identical L2-normed vectors should have similarity 1.0."""
        vec = np.random.randn(512).astype(np.float32)
        vec = vec / np.linalg.norm(vec)
        assert compute_cosine_similarity(vec, vec) == pytest.approx(1.0, abs=1e-6)

    def test_orthogonal_vectors(self):
        """Orthogonal vectors should have similarity ~0.0."""
        a = np.zeros(512, dtype=np.float32)
        b = np.zeros(512, dtype=np.float32)
        a[0] = 1.0
        b[1] = 1.0
        assert compute_cosine_similarity(a, b) == pytest.approx(0.0, abs=1e-6)

    def test_opposite_vectors(self):
        """Opposite vectors should have similarity -1.0."""
        vec = np.random.randn(512).astype(np.float32)
        vec = vec / np.linalg.norm(vec)
        assert compute_cosine_similarity(vec, -vec) == pytest.approx(-1.0, abs=1e-6)

    def test_slightly_different_vectors(self):
        """Slightly perturbed vectors should have similarity close to but < 1.0."""
        vec = np.random.randn(512).astype(np.float32)
        vec = vec / np.linalg.norm(vec)
        noise = np.random.randn(512).astype(np.float32) * 0.001
        perturbed = vec + noise
        perturbed = perturbed / np.linalg.norm(perturbed)
        sim = compute_cosine_similarity(vec, perturbed)
        assert 0.999 < sim < 1.0


# --- Test IoU computation ---


class TestIoU:
    def test_identical_boxes(self):
        assert compute_iou([0, 0, 100, 100], [0, 0, 100, 100]) == pytest.approx(1.0)

    def test_no_overlap(self):
        assert compute_iou([0, 0, 50, 50], [100, 100, 200, 200]) == pytest.approx(0.0)

    def test_partial_overlap(self):
        # 50x50 overlap, each box is 100x100
        # intersection=2500, union=2*10000-2500=17500
        iou = compute_iou([0, 0, 100, 100], [50, 50, 150, 150])
        assert iou == pytest.approx(2500 / 17500, abs=1e-6)

    def test_one_inside_other(self):
        # Small box fully inside big box
        # intersection = 50*50=2500, union = 100*100 = 10000
        iou = compute_iou([0, 0, 100, 100], [25, 25, 75, 75])
        assert iou == pytest.approx(2500 / 10000, abs=1e-6)


# --- Test face matching ---


class TestFaceMatching:
    def test_same_count_matches_by_order(self):
        """When counts match, faces are matched by index order."""
        local = [{"bbox": [0, 0, 50, 50]}, {"bbox": [100, 100, 200, 200]}]
        remote = [{"bbox": [0, 0, 55, 55]}, {"bbox": [95, 95, 200, 200]}]
        matches = match_faces_by_order_and_iou(local, remote)
        assert matches == [(0, 0), (1, 1)]

    def test_different_count_uses_iou(self):
        """When counts differ, IoU matching is used."""
        local = [
            {"bbox": [0, 0, 100, 100]},
            {"bbox": [200, 200, 300, 300]},
        ]
        # Remote has an extra face, plus the two that match
        remote = [
            {"bbox": [200, 200, 300, 300]},  # matches local[1]
            {"bbox": [500, 500, 600, 600]},  # no match
            {"bbox": [0, 0, 100, 100]},  # matches local[0]
        ]
        matches = match_faces_by_order_and_iou(local, remote)
        # local[0] -> remote[2] (bbox [0,0,100,100])
        # local[1] -> remote[0] (bbox [200,200,300,300])
        assert (0, 2) in matches
        assert (1, 0) in matches
        assert len(matches) == 2

    def test_no_overlap_no_matches_with_iou_fallback(self):
        """Faces with no bounding box overlap should not match when using IoU fallback."""
        # Different counts to trigger IoU matching instead of order matching
        local = [{"bbox": [0, 0, 50, 50]}]
        remote = [{"bbox": [500, 500, 600, 600]}, {"bbox": [700, 700, 800, 800]}]
        matches = match_faces_by_order_and_iou(local, remote)
        assert matches == []

    def test_empty_lists(self):
        matches = match_faces_by_order_and_iou([], [])
        assert matches == []


# --- Test compare_embeddings ---


class TestCompareEmbeddings:
    def _make_face(self, seed=42, bbox=None):
        """Create a face dict with a random normed embedding."""
        rng = np.random.RandomState(seed)
        emb = rng.randn(512).astype(np.float32)
        emb = emb / np.linalg.norm(emb)
        return {"mu": emb, "embedding": emb, "bbox": bbox or [0, 0, 100, 100]}

    def test_identical_embeddings_similarity_1(self):
        """Identical embeddings should produce similarity 1.0."""
        face = self._make_face(seed=1)
        local = [{"mu": face["mu"], "bbox": [0, 0, 100, 100]}]
        remote = [{"embedding": face["embedding"], "bbox": [0, 0, 100, 100]}]
        results = compare_embeddings(local, remote)
        assert len(results) == 1
        assert results[0]["cosine_similarity"] == pytest.approx(1.0, abs=1e-5)
        assert results[0]["pass"] is True

    def test_different_embeddings_low_similarity(self):
        """Very different embeddings should produce low similarity."""
        face_a = self._make_face(seed=1)
        face_b = self._make_face(seed=999)
        local = [{"mu": face_a["mu"], "bbox": [0, 0, 100, 100]}]
        remote = [{"embedding": face_b["embedding"], "bbox": [0, 0, 100, 100]}]
        results = compare_embeddings(local, remote)
        assert len(results) == 1
        assert results[0]["cosine_similarity"] < SIMILARITY_THRESHOLD
        assert results[0]["pass"] is False


# --- Test exit code logic ---


class TestExitCode:
    def test_all_pass(self):
        results = [
            {"pass": True, "cosine_similarity": 0.9999},
            {"pass": True, "cosine_similarity": 1.0},
        ]
        assert check_exit_code(results) == 0

    def test_one_fail(self):
        results = [
            {"pass": True, "cosine_similarity": 0.9999},
            {"pass": False, "cosine_similarity": 0.95},
        ]
        assert check_exit_code(results) == 1

    def test_all_fail(self):
        results = [{"pass": False, "cosine_similarity": 0.5}]
        assert check_exit_code(results) == 1

    def test_empty_results(self):
        """No matches should return exit code 1."""
        assert check_exit_code([]) == 1


# --- Test local-only mode ---


class TestLocalOnlyMode:
    def test_local_only_no_ml_service_needed(self):
        """In local-only mode, compare_embeddings is never called.
        Verify extract_local_faces can be called without ML service config."""
        # This test just validates the function signature and logic;
        # actual InsightFace is too heavy for unit tests.
        # Instead we test that the script's argparse handles --local-only.
        import subprocess

        result = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve().parent.parent / "scripts" / "compare_ml_embeddings.py"),
                "--photo",
                "/nonexistent/photo.jpg",
                "--local-only",
            ],
            capture_output=True,
            text=True,
        )
        # Should exit 1 because the photo doesn't exist
        assert result.returncode == 1
        assert "not found" in result.stderr.lower() or "not found" in result.stdout.lower()
