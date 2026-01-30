"""
Tests for neighbor discovery module.

Tests find_nearest_neighbors() and sort_faces_by_outlier_score()
functionality for identity matching and cluster inspection.
"""

import numpy as np
import pytest


def create_face_data(face_id: str, mu: np.ndarray = None, sigma_sq_val: float = 0.1):
    """Helper to create face data dict."""
    if mu is None:
        mu = np.random.randn(512).astype(np.float32)
        mu = mu / np.linalg.norm(mu)  # Normalize
    return {
        face_id: {
            "mu": mu,
            "sigma_sq": np.full(512, sigma_sq_val, dtype=np.float32),
        }
    }


class TestFindNearestNeighbors:
    """Tests for find_nearest_neighbors() function."""

    def test_excludes_self(self):
        """Should not include the target identity in results."""
        from core.neighbors import find_nearest_neighbors
        from core.photo_registry import PhotoRegistry
        from core.registry import IdentityRegistry

        photo_registry = PhotoRegistry()
        photo_registry.register_face("photo_1", "/path/1.jpg", "face_a")
        photo_registry.register_face("photo_2", "/path/2.jpg", "face_b")

        identity_registry = IdentityRegistry()
        id_a = identity_registry.create_identity(anchor_ids=["face_a"], user_source="test")
        id_b = identity_registry.create_identity(anchor_ids=["face_b"], user_source="test")

        # Create face data with same embedding (very similar)
        base_mu = np.random.randn(512).astype(np.float32)
        base_mu = base_mu / np.linalg.norm(base_mu)
        face_data = {
            "face_a": {"mu": base_mu.copy(), "sigma_sq": np.full(512, 0.1, dtype=np.float32)},
            "face_b": {"mu": base_mu.copy(), "sigma_sq": np.full(512, 0.1, dtype=np.float32)},
        }

        neighbors = find_nearest_neighbors(
            id_a, identity_registry, photo_registry, face_data, limit=10
        )

        # Should not include self
        neighbor_ids = [n["identity_id"] for n in neighbors]
        assert id_a not in neighbor_ids
        assert id_b in neighbor_ids

    def test_excludes_merged_identities(self):
        """Should not include merged identities in results."""
        from core.neighbors import find_nearest_neighbors
        from core.photo_registry import PhotoRegistry
        from core.registry import IdentityRegistry

        photo_registry = PhotoRegistry()
        photo_registry.register_face("photo_1", "/path/1.jpg", "face_a")
        photo_registry.register_face("photo_2", "/path/2.jpg", "face_b")
        photo_registry.register_face("photo_3", "/path/3.jpg", "face_c")

        identity_registry = IdentityRegistry()
        id_a = identity_registry.create_identity(anchor_ids=["face_a"], user_source="test")
        id_b = identity_registry.create_identity(anchor_ids=["face_b"], user_source="test")
        id_c = identity_registry.create_identity(anchor_ids=["face_c"], user_source="test")

        # Merge id_b into id_a
        identity_registry.merge_identities(id_b, id_a, "test", photo_registry)

        base_mu = np.random.randn(512).astype(np.float32)
        face_data = {
            "face_a": {"mu": base_mu.copy(), "sigma_sq": np.full(512, 0.1, dtype=np.float32)},
            "face_b": {"mu": base_mu.copy(), "sigma_sq": np.full(512, 0.1, dtype=np.float32)},
            "face_c": {"mu": base_mu.copy(), "sigma_sq": np.full(512, 0.1, dtype=np.float32)},
        }

        # Get neighbors for id_c
        neighbors = find_nearest_neighbors(
            id_c, identity_registry, photo_registry, face_data, limit=10
        )

        # Should not include merged id_b
        neighbor_ids = [n["identity_id"] for n in neighbors]
        assert id_b not in neighbor_ids
        assert id_a in neighbor_ids

    def test_sorted_by_mls_descending(self):
        """Results should be sorted by MLS (highest first = most similar)."""
        from core.neighbors import find_nearest_neighbors
        from core.photo_registry import PhotoRegistry
        from core.registry import IdentityRegistry

        photo_registry = PhotoRegistry()
        photo_registry.register_face("photo_1", "/path/1.jpg", "face_a")
        photo_registry.register_face("photo_2", "/path/2.jpg", "face_b")
        photo_registry.register_face("photo_3", "/path/3.jpg", "face_c")

        identity_registry = IdentityRegistry()
        id_a = identity_registry.create_identity(anchor_ids=["face_a"], user_source="test")
        id_b = identity_registry.create_identity(anchor_ids=["face_b"], user_source="test")
        id_c = identity_registry.create_identity(anchor_ids=["face_c"], user_source="test")

        # Create embeddings: a and b are very similar, c is different
        base_mu = np.zeros(512, dtype=np.float32)
        base_mu[0] = 1.0  # Unit vector

        similar_mu = base_mu.copy()
        similar_mu[1] = 0.1  # Small perturbation

        different_mu = np.zeros(512, dtype=np.float32)
        different_mu[100] = 1.0  # Very different direction

        face_data = {
            "face_a": {"mu": base_mu, "sigma_sq": np.full(512, 0.1, dtype=np.float32)},
            "face_b": {"mu": similar_mu, "sigma_sq": np.full(512, 0.1, dtype=np.float32)},
            "face_c": {"mu": different_mu, "sigma_sq": np.full(512, 0.1, dtype=np.float32)},
        }

        neighbors = find_nearest_neighbors(
            id_a, identity_registry, photo_registry, face_data, limit=10
        )

        # id_b should come before id_c (higher MLS)
        assert len(neighbors) == 2
        assert neighbors[0]["identity_id"] == id_b
        assert neighbors[1]["identity_id"] == id_c
        assert neighbors[0]["mls_score"] > neighbors[1]["mls_score"]

    def test_includes_merge_eligibility(self):
        """Each result should indicate if merge is possible."""
        from core.neighbors import find_nearest_neighbors
        from core.photo_registry import PhotoRegistry
        from core.registry import IdentityRegistry

        photo_registry = PhotoRegistry()
        # face_a and face_b in same photo (can't merge)
        photo_registry.register_face("photo_1", "/path/1.jpg", "face_a")
        photo_registry.register_face("photo_1", "/path/1.jpg", "face_b")
        # face_c in different photo (can merge)
        photo_registry.register_face("photo_2", "/path/2.jpg", "face_c")

        identity_registry = IdentityRegistry()
        id_a = identity_registry.create_identity(anchor_ids=["face_a"], user_source="test")
        id_b = identity_registry.create_identity(anchor_ids=["face_b"], user_source="test")
        id_c = identity_registry.create_identity(anchor_ids=["face_c"], user_source="test")

        base_mu = np.random.randn(512).astype(np.float32)
        face_data = {
            "face_a": {"mu": base_mu.copy(), "sigma_sq": np.full(512, 0.1, dtype=np.float32)},
            "face_b": {"mu": base_mu.copy(), "sigma_sq": np.full(512, 0.1, dtype=np.float32)},
            "face_c": {"mu": base_mu.copy(), "sigma_sq": np.full(512, 0.1, dtype=np.float32)},
        }

        neighbors = find_nearest_neighbors(
            id_a, identity_registry, photo_registry, face_data, limit=10
        )

        # Find results for id_b and id_c
        result_b = next(n for n in neighbors if n["identity_id"] == id_b)
        result_c = next(n for n in neighbors if n["identity_id"] == id_c)

        # id_b should be blocked (same photo), id_c should be allowed
        assert result_b["can_merge"] is False
        assert result_b["merge_blocked_reason"] == "co_occurrence"
        assert result_c["can_merge"] is True
        assert result_c["merge_blocked_reason"] is None

    def test_respects_limit(self):
        """Should return at most `limit` neighbors."""
        from core.neighbors import find_nearest_neighbors
        from core.photo_registry import PhotoRegistry
        from core.registry import IdentityRegistry

        photo_registry = PhotoRegistry()
        identity_registry = IdentityRegistry()
        face_data = {}

        # Create 10 identities
        ids = []
        for i in range(10):
            face_id = f"face_{i}"
            photo_registry.register_face(f"photo_{i}", f"/path/{i}.jpg", face_id)
            id_ = identity_registry.create_identity(anchor_ids=[face_id], user_source="test")
            ids.append(id_)

            mu = np.random.randn(512).astype(np.float32)
            face_data[face_id] = {"mu": mu, "sigma_sq": np.full(512, 0.1, dtype=np.float32)}

        # Get neighbors with limit=3
        neighbors = find_nearest_neighbors(
            ids[0], identity_registry, photo_registry, face_data, limit=3
        )

        assert len(neighbors) == 3

    def test_returns_empty_for_no_anchors(self):
        """Should return empty list if identity has no valid anchors."""
        from core.neighbors import find_nearest_neighbors
        from core.photo_registry import PhotoRegistry
        from core.registry import IdentityRegistry

        photo_registry = PhotoRegistry()
        identity_registry = IdentityRegistry()

        # Identity with anchor but no face data
        photo_registry.register_face("photo_1", "/path/1.jpg", "face_a")
        id_a = identity_registry.create_identity(anchor_ids=["face_a"], user_source="test")

        face_data = {}  # No embeddings

        neighbors = find_nearest_neighbors(
            id_a, identity_registry, photo_registry, face_data, limit=10
        )

        assert neighbors == []

    def test_excludes_rejected_identity_pairs(self):
        """Rejected identities should not appear in neighbors (D3)."""
        from core.neighbors import find_nearest_neighbors
        from core.photo_registry import PhotoRegistry
        from core.registry import IdentityRegistry

        photo_registry = PhotoRegistry()
        photo_registry.register_face("photo_1", "/path/1.jpg", "face_a")
        photo_registry.register_face("photo_2", "/path/2.jpg", "face_b")
        photo_registry.register_face("photo_3", "/path/3.jpg", "face_c")

        identity_registry = IdentityRegistry()
        id_a = identity_registry.create_identity(anchor_ids=["face_a"], user_source="test")
        id_b = identity_registry.create_identity(anchor_ids=["face_b"], user_source="test")
        id_c = identity_registry.create_identity(anchor_ids=["face_c"], user_source="test")

        # Reject id_b from id_a's perspective
        identity_registry.reject_identity_pair(id_a, id_b, user_source="test")

        # Create similar embeddings (all would be neighbors without rejection)
        base_mu = np.random.randn(512).astype(np.float32)
        base_mu = base_mu / np.linalg.norm(base_mu)
        face_data = {
            "face_a": {"mu": base_mu.copy(), "sigma_sq": np.full(512, 0.1, dtype=np.float32)},
            "face_b": {"mu": base_mu.copy(), "sigma_sq": np.full(512, 0.1, dtype=np.float32)},
            "face_c": {"mu": base_mu.copy(), "sigma_sq": np.full(512, 0.1, dtype=np.float32)},
        }

        neighbors = find_nearest_neighbors(
            id_a, identity_registry, photo_registry, face_data, limit=10
        )

        neighbor_ids = [n["identity_id"] for n in neighbors]
        assert id_b not in neighbor_ids  # Rejected - should be excluded
        assert id_c in neighbor_ids  # Not rejected - should be included

    def test_rejection_filtering_applied_before_limit(self):
        """Rejected pairs should be filtered BEFORE limit is applied (D3)."""
        from core.neighbors import find_nearest_neighbors
        from core.photo_registry import PhotoRegistry
        from core.registry import IdentityRegistry

        photo_registry = PhotoRegistry()
        identity_registry = IdentityRegistry()
        face_data = {}

        # Create 5 identities
        ids = []
        for i in range(5):
            face_id = f"face_{i}"
            photo_registry.register_face(f"photo_{i}", f"/path/{i}.jpg", face_id)
            id_ = identity_registry.create_identity(anchor_ids=[face_id], user_source="test")
            ids.append(id_)

            mu = np.random.randn(512).astype(np.float32)
            mu = mu / np.linalg.norm(mu)
            face_data[face_id] = {"mu": mu, "sigma_sq": np.full(512, 0.1, dtype=np.float32)}

        # Reject id_1 from id_0's perspective
        identity_registry.reject_identity_pair(ids[0], ids[1], user_source="test")

        # Get neighbors with limit=3
        # Without filtering, would return ids[1], ids[2], ids[3]
        # With filtering, should return ids[2], ids[3], ids[4] (skip rejected ids[1])
        neighbors = find_nearest_neighbors(
            ids[0], identity_registry, photo_registry, face_data, limit=3
        )

        neighbor_ids = [n["identity_id"] for n in neighbors]
        assert ids[1] not in neighbor_ids  # Rejected
        assert len(neighbors) == 3  # Still get 3 results (ids[2], ids[3], ids[4])


class TestSortFacesByOutlierScore:
    """Tests for sort_faces_by_outlier_score() function."""

    def test_outliers_sorted_first(self):
        """Faces furthest from centroid should be sorted first."""
        from core.neighbors import sort_faces_by_outlier_score
        from core.photo_registry import PhotoRegistry
        from core.registry import IdentityRegistry

        photo_registry = PhotoRegistry()
        identity_registry = IdentityRegistry()

        # Create identity with 3 faces
        photo_registry.register_face("photo_1", "/path/1.jpg", "face_a")
        photo_registry.register_face("photo_2", "/path/2.jpg", "face_b")
        photo_registry.register_face("photo_3", "/path/3.jpg", "face_c")

        id_a = identity_registry.create_identity(
            anchor_ids=["face_a", "face_b", "face_c"],
            user_source="test",
        )

        # Create embeddings: a and b are similar, c is very different (outlier)
        base_mu = np.zeros(512, dtype=np.float32)
        base_mu[0] = 1.0

        similar_mu = base_mu.copy()
        similar_mu[1] = 0.1

        outlier_mu = np.zeros(512, dtype=np.float32)
        outlier_mu[100] = 1.0  # Very different

        face_data = {
            "face_a": {"mu": base_mu, "sigma_sq": np.full(512, 0.1, dtype=np.float32)},
            "face_b": {"mu": similar_mu, "sigma_sq": np.full(512, 0.1, dtype=np.float32)},
            "face_c": {"mu": outlier_mu, "sigma_sq": np.full(512, 0.1, dtype=np.float32)},
        }

        sorted_faces = sort_faces_by_outlier_score(id_a, identity_registry, face_data)

        # face_c (outlier) should be first
        assert len(sorted_faces) == 3
        assert sorted_faces[0][0] == "face_c"
        assert sorted_faces[0][1] > sorted_faces[1][1]  # Higher outlier score

    def test_handles_no_anchors(self):
        """Should return empty list for identity with no valid anchors."""
        from core.neighbors import sort_faces_by_outlier_score
        from core.photo_registry import PhotoRegistry
        from core.registry import IdentityRegistry

        photo_registry = PhotoRegistry()
        identity_registry = IdentityRegistry()

        photo_registry.register_face("photo_1", "/path/1.jpg", "face_a")
        id_a = identity_registry.create_identity(anchor_ids=["face_a"], user_source="test")

        face_data = {}  # No embeddings

        sorted_faces = sort_faces_by_outlier_score(id_a, identity_registry, face_data)

        assert sorted_faces == []

    def test_includes_candidates_and_anchors(self):
        """Should include both anchor and candidate faces in sorting."""
        from core.neighbors import sort_faces_by_outlier_score
        from core.photo_registry import PhotoRegistry
        from core.registry import IdentityRegistry

        photo_registry = PhotoRegistry()
        identity_registry = IdentityRegistry()

        photo_registry.register_face("photo_1", "/path/1.jpg", "face_a")
        photo_registry.register_face("photo_2", "/path/2.jpg", "face_b")

        id_a = identity_registry.create_identity(
            anchor_ids=["face_a"],
            candidate_ids=["face_b"],
            user_source="test",
        )

        base_mu = np.random.randn(512).astype(np.float32)
        face_data = {
            "face_a": {"mu": base_mu.copy(), "sigma_sq": np.full(512, 0.1, dtype=np.float32)},
            "face_b": {"mu": base_mu.copy(), "sigma_sq": np.full(512, 0.1, dtype=np.float32)},
        }

        sorted_faces = sort_faces_by_outlier_score(id_a, identity_registry, face_data)

        face_ids = [f[0] for f in sorted_faces]
        assert "face_a" in face_ids
        assert "face_b" in face_ids
