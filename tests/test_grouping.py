"""
Tests for face grouping during ingestion.

These tests define the expected behavior of group_faces():
- Similar faces (distance < threshold) should be grouped together
- Different faces should remain in separate groups
- Grouping is transitive (A~B and B~C means A,B,C in same group)
- Conservative: borderline cases should NOT be grouped
"""

import numpy as np
import pytest


def make_face(face_id: str, embedding: np.ndarray) -> dict:
    """
    Create a minimal face dict for testing.

    Args:
        face_id: Unique face identifier
        embedding: 512-dimensional embedding vector (mu)

    Returns:
        Face dict compatible with group_faces()
    """
    return {
        "face_id": face_id,
        "mu": embedding,
    }


def random_embedding(seed: int = None) -> np.ndarray:
    """
    Generate a random normalized 512-dim embedding.

    Uses normalization to match real InsightFace embeddings.
    """
    if seed is not None:
        np.random.seed(seed)
    vec = np.random.randn(512).astype(np.float32)
    return vec / np.linalg.norm(vec)


def similar_embedding(base: np.ndarray, distance: float = 0.5) -> np.ndarray:
    """
    Create an embedding at approximately the given Euclidean distance from base.

    Args:
        base: Reference embedding (normalized)
        distance: Target Euclidean distance from base

    Returns:
        New normalized embedding approximately `distance` away from base
    """
    # Add noise proportional to desired distance
    # For normalized vectors, distance = sqrt(2 - 2*cos(theta))
    # Small distances ≈ linear perturbation
    noise = np.random.randn(512).astype(np.float32)
    noise = noise / np.linalg.norm(noise)

    # Interpolate: move `distance/2` in the noise direction
    # (heuristic that works for small distances on unit sphere)
    perturbed = base + (distance / 2) * noise
    return perturbed / np.linalg.norm(perturbed)


class TestGroupFaces:
    """Tests for the group_faces function."""

    def test_identical_faces_grouped(self):
        """10 copies of same embedding → 1 group with 10 faces."""
        from core.grouping import group_faces

        # Same embedding for all faces
        embedding = random_embedding(seed=42)
        faces = [make_face(f"face_{i}", embedding.copy()) for i in range(10)]

        groups = group_faces(faces)

        assert len(groups) == 1, f"Expected 1 group, got {len(groups)}"
        assert len(groups[0]) == 10, f"Expected 10 faces in group, got {len(groups[0])}"

    def test_different_faces_not_grouped(self):
        """10 different people → 10 separate groups."""
        from core.grouping import group_faces

        # Each face has a unique random embedding
        faces = [make_face(f"face_{i}", random_embedding(seed=i)) for i in range(10)]

        groups = group_faces(faces)

        assert len(groups) == 10, f"Expected 10 groups, got {len(groups)}"
        for group in groups:
            assert len(group) == 1, f"Expected 1 face per group, got {len(group)}"

    def test_mixed_batch_two_people(self):
        """5 faces of person A + 3 faces of person B → 2 groups."""
        from core.grouping import group_faces

        # Person A: 5 identical embeddings
        embedding_a = random_embedding(seed=100)
        faces_a = [make_face(f"person_a_{i}", embedding_a.copy()) for i in range(5)]

        # Person B: 3 identical embeddings (different from A)
        embedding_b = random_embedding(seed=200)
        faces_b = [make_face(f"person_b_{i}", embedding_b.copy()) for i in range(3)]

        # Combine and shuffle
        faces = faces_a + faces_b
        np.random.seed(42)
        np.random.shuffle(faces)

        groups = group_faces(faces)

        assert len(groups) == 2, f"Expected 2 groups, got {len(groups)}"
        group_sizes = sorted([len(g) for g in groups])
        assert group_sizes == [3, 5], f"Expected group sizes [3, 5], got {group_sizes}"

    def test_empty_input(self):
        """Empty face list → empty group list."""
        from core.grouping import group_faces

        groups = group_faces([])

        assert groups == [], f"Expected empty list, got {groups}"

    def test_single_face(self):
        """Single face → single group with one face."""
        from core.grouping import group_faces

        faces = [make_face("only_face", random_embedding(seed=1))]

        groups = group_faces(faces)

        assert len(groups) == 1, f"Expected 1 group, got {len(groups)}"
        assert len(groups[0]) == 1, f"Expected 1 face in group, got {len(groups[0])}"
        assert groups[0][0]["face_id"] == "only_face"

    def test_transitive_grouping(self):
        """
        Transitive closure: A~B and B~C should group A,B,C together.

        Even if A is not directly similar to C, they should be in the
        same group because B connects them.
        """
        from core.grouping import group_faces
        from core.config import GROUPING_THRESHOLD

        # Create a chain: A -- B -- C
        # A and B are similar, B and C are similar, but A and C are farther apart
        base = random_embedding(seed=42)

        # A is the base
        embedding_a = base.copy()

        # B is close to A (well under threshold)
        embedding_b = similar_embedding(base, distance=GROUPING_THRESHOLD * 0.4)

        # C is close to B but farther from A
        embedding_c = similar_embedding(embedding_b, distance=GROUPING_THRESHOLD * 0.4)

        faces = [
            make_face("face_a", embedding_a),
            make_face("face_b", embedding_b),
            make_face("face_c", embedding_c),
        ]

        groups = group_faces(faces)

        # All three should be in one group due to transitivity
        assert len(groups) == 1, f"Expected 1 group (transitive), got {len(groups)}"
        assert len(groups[0]) == 3, f"Expected 3 faces in group, got {len(groups[0])}"

    def test_conservative_threshold_no_grouping(self):
        """
        Faces just above threshold should NOT be grouped.

        This tests the conservative nature of grouping:
        borderline cases should err on the side of NOT grouping.
        """
        from core.grouping import group_faces
        from core.config import GROUPING_THRESHOLD

        base = random_embedding(seed=42)

        # Create a face that's JUST above the threshold (should not group)
        distant = similar_embedding(base, distance=GROUPING_THRESHOLD * 1.1)

        faces = [
            make_face("face_base", base),
            make_face("face_distant", distant),
        ]

        groups = group_faces(faces)

        # Should NOT be grouped - two separate identities
        assert len(groups) == 2, f"Expected 2 groups (not similar enough), got {len(groups)}"

    def test_faces_just_under_threshold_grouped(self):
        """
        Faces just under threshold SHOULD be grouped.

        Verifies the threshold is applied correctly.
        """
        from core.grouping import group_faces
        from core.config import GROUPING_THRESHOLD

        base = random_embedding(seed=42)

        # Create a face that's JUST under the threshold (should group)
        close = similar_embedding(base, distance=GROUPING_THRESHOLD * 0.8)

        faces = [
            make_face("face_base", base),
            make_face("face_close", close),
        ]

        groups = group_faces(faces)

        # Should be grouped - same identity
        assert len(groups) == 1, f"Expected 1 group (similar enough), got {len(groups)}"
        assert len(groups[0]) == 2

    def test_output_contains_original_face_dicts(self):
        """
        Groups should contain the original face dicts, not just face_ids.

        This ensures downstream code can access all face metadata.
        """
        from core.grouping import group_faces

        embedding = random_embedding(seed=42)
        faces = [
            {"face_id": "f1", "mu": embedding.copy(), "extra_field": "value1"},
            {"face_id": "f2", "mu": embedding.copy(), "extra_field": "value2"},
        ]

        groups = group_faces(faces)

        assert len(groups) == 1
        # Check that original dicts are preserved (not just face_ids)
        face_ids_in_group = {f["face_id"] for f in groups[0]}
        assert face_ids_in_group == {"f1", "f2"}

        # Check extra fields are preserved
        extras = {f["extra_field"] for f in groups[0]}
        assert extras == {"value1", "value2"}


class TestGroupingThreshold:
    """Tests specifically for threshold configuration."""

    def test_threshold_exists_in_config(self):
        """GROUPING_THRESHOLD should be defined in core.config."""
        from core.config import GROUPING_THRESHOLD

        assert isinstance(GROUPING_THRESHOLD, (int, float))
        assert GROUPING_THRESHOLD > 0
        assert GROUPING_THRESHOLD < 2.0  # Reasonable upper bound for Euclidean distance

    def test_threshold_is_conservative(self):
        """
        GROUPING_THRESHOLD should be <= MATCH_THRESHOLD_HIGH.

        Grouping should be MORE conservative than "high confidence" matching.
        """
        from core.config import GROUPING_THRESHOLD, MATCH_THRESHOLD_HIGH

        assert GROUPING_THRESHOLD <= MATCH_THRESHOLD_HIGH, (
            f"GROUPING_THRESHOLD ({GROUPING_THRESHOLD}) should be <= "
            f"MATCH_THRESHOLD_HIGH ({MATCH_THRESHOLD_HIGH}) for conservative grouping"
        )
