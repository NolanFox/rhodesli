"""
Tests for batch grouping of INBOX identities.

Tests group_inbox_identities() which compares existing INBOX identities
pairwise and merges similar ones into clusters.

All tests use mock registries per test isolation rules (CLAUDE.md Rule #14).
"""

import numpy as np
import pytest

from core.config import GROUPING_THRESHOLD


def random_embedding(seed: int = None) -> np.ndarray:
    """Generate a random normalized 512-dim embedding."""
    if seed is not None:
        np.random.seed(seed)
    vec = np.random.randn(512).astype(np.float32)
    return vec / np.linalg.norm(vec)


def similar_embedding(base: np.ndarray, distance: float = 0.5) -> np.ndarray:
    """Create an embedding at the given Euclidean distance from base."""
    noise = np.random.randn(512).astype(np.float32)
    noise = noise - np.dot(noise, base) * base
    noise = noise / np.linalg.norm(noise)

    cos_theta = 1 - (distance ** 2) / 2
    cos_theta = np.clip(cos_theta, -1, 1)
    sin_theta = np.sqrt(1 - cos_theta ** 2)

    result = cos_theta * base + sin_theta * noise
    return result.astype(np.float32)


def make_inbox_registry(identities_spec: list[dict]):
    """
    Create an IdentityRegistry with INBOX identities from a spec.

    Args:
        identities_spec: List of dicts with:
            - face_ids: list[str] (face IDs to assign as anchors)
            - name: str (optional, defaults to "Unidentified Person NNN")

    Returns:
        (registry, face_data, photo_registry) tuple ready for group_inbox_identities()
    """
    from core.photo_registry import PhotoRegistry
    from core.registry import IdentityRegistry, IdentityState

    registry = IdentityRegistry()
    face_data = {}
    photo_registry = PhotoRegistry()

    for i, spec in enumerate(identities_spec):
        face_ids = spec["face_ids"]
        name = spec.get("name", f"Unidentified Person {i:03d}")
        embedding = spec["embedding"]

        # Create identity with these face IDs as anchors
        iid = registry.create_identity(
            anchor_ids=face_ids,
            user_source="test",
            name=name,
            state=IdentityState.INBOX,
        )

        # Register face embeddings
        for fid in face_ids:
            face_data[fid] = {
                "mu": np.asarray(embedding, dtype=np.float32),
                "sigma_sq": np.full(512, 0.1, dtype=np.float32),
            }

        # Register each face in a different photo (no co-occurrence by default)
        for j, fid in enumerate(face_ids):
            photo_id = spec.get("photo_id", f"photo_{i}_{j}")
            photo_registry.register_face(photo_id, f"img_{i}_{j}.jpg", fid)

    return registry, face_data, photo_registry


class TestGroupInboxIdentities:
    """Tests for the group_inbox_identities function."""

    def test_similar_faces_grouped_dry_run(self):
        """3 similar inbox faces → 1 group of 3 in dry-run mode."""
        from core.grouping import group_inbox_identities

        base = random_embedding(seed=42)
        specs = [
            {"face_ids": ["face_a"], "embedding": base.copy()},
            {"face_ids": ["face_b"], "embedding": similar_embedding(base, distance=0.3)},
            {"face_ids": ["face_c"], "embedding": similar_embedding(base, distance=0.4)},
        ]

        registry, face_data, photo_registry = make_inbox_registry(specs)

        results = group_inbox_identities(
            registry=registry,
            face_data=face_data,
            photo_registry=photo_registry,
            dry_run=True,
        )

        assert results["total_groups"] == 1
        assert results["groups"][0]["size"] == 3
        # Dry run: no merges applied
        assert results["total_merged"] == 0
        assert results["identities_before"] == 3
        assert results["identities_after"] == 3  # Unchanged in dry run

    def test_similar_faces_merged_execute(self):
        """3 similar inbox faces → merged into 1 identity in execute mode."""
        from core.grouping import group_inbox_identities

        base = random_embedding(seed=42)
        specs = [
            {"face_ids": ["face_a"], "embedding": base.copy()},
            {"face_ids": ["face_b"], "embedding": similar_embedding(base, distance=0.3)},
            {"face_ids": ["face_c"], "embedding": similar_embedding(base, distance=0.4)},
        ]

        registry, face_data, photo_registry = make_inbox_registry(specs)

        results = group_inbox_identities(
            registry=registry,
            face_data=face_data,
            photo_registry=photo_registry,
            dry_run=False,
        )

        assert results["total_groups"] == 1
        assert results["total_merged"] == 2
        assert results["identities_before"] == 3
        assert results["identities_after"] == 1

        # Verify the primary identity now has 3 faces
        primary_id = results["groups"][0]["primary_id"]
        all_face_ids = registry.get_all_face_ids(primary_id)
        assert len(all_face_ids) == 3

    def test_different_faces_not_grouped(self):
        """3 distinct faces → no groups, 3 separate identities."""
        from core.grouping import group_inbox_identities

        specs = [
            {"face_ids": ["face_a"], "embedding": random_embedding(seed=10)},
            {"face_ids": ["face_b"], "embedding": random_embedding(seed=20)},
            {"face_ids": ["face_c"], "embedding": random_embedding(seed=30)},
        ]

        registry, face_data, photo_registry = make_inbox_registry(specs)

        results = group_inbox_identities(
            registry=registry,
            face_data=face_data,
            photo_registry=photo_registry,
            dry_run=False,
        )

        assert results["total_groups"] == 0
        assert results["total_merged"] == 0
        assert results["identities_before"] == 3
        assert results["identities_after"] == 3

    def test_two_groups_of_similar_faces(self):
        """2 people with 3 photos each → 2 groups of 3."""
        from core.grouping import group_inbox_identities

        person_a = random_embedding(seed=100)
        person_b = random_embedding(seed=200)

        specs = [
            {"face_ids": ["a1"], "embedding": person_a.copy()},
            {"face_ids": ["a2"], "embedding": similar_embedding(person_a, distance=0.3)},
            {"face_ids": ["a3"], "embedding": similar_embedding(person_a, distance=0.4)},
            {"face_ids": ["b1"], "embedding": person_b.copy()},
            {"face_ids": ["b2"], "embedding": similar_embedding(person_b, distance=0.3)},
            {"face_ids": ["b3"], "embedding": similar_embedding(person_b, distance=0.4)},
        ]

        registry, face_data, photo_registry = make_inbox_registry(specs)

        results = group_inbox_identities(
            registry=registry,
            face_data=face_data,
            photo_registry=photo_registry,
            dry_run=False,
        )

        assert results["total_groups"] == 2
        assert results["total_merged"] == 4  # 2 groups, each removes 2
        assert results["identities_before"] == 6
        assert results["identities_after"] == 2

        # Each group should have 3 members
        group_sizes = sorted([g["size"] for g in results["groups"]])
        assert group_sizes == [3, 3]

    def test_co_occurrence_blocks_merge(self):
        """Faces from the same photo should NOT be merged even if similar."""
        from core.grouping import group_inbox_identities
        from core.photo_registry import PhotoRegistry
        from core.registry import IdentityRegistry, IdentityState

        base = random_embedding(seed=42)

        registry = IdentityRegistry()
        face_data = {}
        photo_registry = PhotoRegistry()

        # Two identities with similar faces BUT from the same photo
        iid_a = registry.create_identity(
            anchor_ids=["face_a"],
            user_source="test",
            name="Person A",
            state=IdentityState.INBOX,
        )
        iid_b = registry.create_identity(
            anchor_ids=["face_b"],
            user_source="test",
            name="Person B",
            state=IdentityState.INBOX,
        )

        face_data["face_a"] = {
            "mu": base.copy(),
            "sigma_sq": np.full(512, 0.1, dtype=np.float32),
        }
        face_data["face_b"] = {
            "mu": similar_embedding(base, distance=0.3),
            "sigma_sq": np.full(512, 0.1, dtype=np.float32),
        }

        # Both faces registered in the SAME photo — co-occurrence!
        photo_registry.register_face("same_photo", "photo.jpg", "face_a")
        photo_registry.register_face("same_photo", "photo.jpg", "face_b")

        results = group_inbox_identities(
            registry=registry,
            face_data=face_data,
            photo_registry=photo_registry,
            dry_run=False,
        )

        # Grouping algorithm finds the pair, but merge_identities blocks it
        if results["total_groups"] > 0:
            assert results["skipped_co_occurrence"] > 0
            # The merge should have been blocked
            assert results["total_merged"] == 0

    def test_empty_inbox(self):
        """No inbox identities → no groups."""
        from core.grouping import group_inbox_identities
        from core.photo_registry import PhotoRegistry
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        photo_registry = PhotoRegistry()

        results = group_inbox_identities(
            registry=registry,
            face_data={},
            photo_registry=photo_registry,
            dry_run=False,
        )

        assert results["total_groups"] == 0
        assert results["total_merged"] == 0
        assert results["identities_before"] == 0

    def test_single_inbox_identity(self):
        """Only 1 inbox identity → no groups (need at least 2)."""
        from core.grouping import group_inbox_identities

        specs = [
            {"face_ids": ["face_a"], "embedding": random_embedding(seed=42)},
        ]

        registry, face_data, photo_registry = make_inbox_registry(specs)

        results = group_inbox_identities(
            registry=registry,
            face_data=face_data,
            photo_registry=photo_registry,
            dry_run=False,
        )

        assert results["total_groups"] == 0
        assert results["identities_before"] == 1

    def test_threshold_boundary_above(self):
        """Faces just above threshold → NOT grouped."""
        from core.grouping import group_inbox_identities

        base = random_embedding(seed=42)
        specs = [
            {"face_ids": ["face_a"], "embedding": base.copy()},
            {"face_ids": ["face_b"], "embedding": similar_embedding(
                base, distance=GROUPING_THRESHOLD * 1.1
            )},
        ]

        registry, face_data, photo_registry = make_inbox_registry(specs)

        results = group_inbox_identities(
            registry=registry,
            face_data=face_data,
            photo_registry=photo_registry,
            dry_run=False,
        )

        assert results["total_groups"] == 0
        assert results["total_merged"] == 0

    def test_threshold_boundary_below(self):
        """Faces just below threshold → grouped."""
        from core.grouping import group_inbox_identities

        base = random_embedding(seed=42)
        specs = [
            {"face_ids": ["face_a"], "embedding": base.copy()},
            {"face_ids": ["face_b"], "embedding": similar_embedding(
                base, distance=GROUPING_THRESHOLD * 0.8
            )},
        ]

        registry, face_data, photo_registry = make_inbox_registry(specs)

        results = group_inbox_identities(
            registry=registry,
            face_data=face_data,
            photo_registry=photo_registry,
            dry_run=False,
        )

        assert results["total_groups"] == 1
        assert results["total_merged"] == 1

    def test_custom_threshold(self):
        """Custom threshold overrides GROUPING_THRESHOLD."""
        from core.grouping import group_inbox_identities

        base = random_embedding(seed=42)
        # Distance of 0.5 — below default threshold (0.95) but above 0.3
        specs = [
            {"face_ids": ["face_a"], "embedding": base.copy()},
            {"face_ids": ["face_b"], "embedding": similar_embedding(base, distance=0.5)},
        ]

        registry, face_data, photo_registry = make_inbox_registry(specs)

        # Very strict threshold: should NOT group
        results_strict = group_inbox_identities(
            registry=registry,
            face_data=face_data,
            photo_registry=photo_registry,
            threshold=0.3,
            dry_run=True,
        )
        assert results_strict["total_groups"] == 0

        # Lenient threshold: should group
        results_lenient = group_inbox_identities(
            registry=registry,
            face_data=face_data,
            photo_registry=photo_registry,
            threshold=0.8,
            dry_run=True,
        )
        assert results_lenient["total_groups"] == 1

    def test_confirmed_identities_excluded(self):
        """Only INBOX identities are grouped — CONFIRMED are excluded."""
        from core.grouping import group_inbox_identities
        from core.photo_registry import PhotoRegistry
        from core.registry import IdentityRegistry, IdentityState

        base = random_embedding(seed=42)

        registry = IdentityRegistry()
        face_data = {}
        photo_registry = PhotoRegistry()

        # Create one INBOX and one CONFIRMED with similar embeddings
        registry.create_identity(
            anchor_ids=["face_inbox"],
            user_source="test",
            name="Inbox Person",
            state=IdentityState.INBOX,
        )
        registry.create_identity(
            anchor_ids=["face_confirmed"],
            user_source="test",
            name="Confirmed Person",
            state=IdentityState.CONFIRMED,
        )

        for fid in ["face_inbox", "face_confirmed"]:
            face_data[fid] = {
                "mu": base.copy(),
                "sigma_sq": np.full(512, 0.1, dtype=np.float32),
            }
            photo_registry.register_face(f"photo_{fid}", f"{fid}.jpg", fid)

        results = group_inbox_identities(
            registry=registry,
            face_data=face_data,
            photo_registry=photo_registry,
            dry_run=False,
        )

        # Only 1 inbox identity → no groups possible
        assert results["total_groups"] == 0
        assert results["identities_before"] == 1  # Only counted INBOX

    def test_already_merged_identities_excluded(self):
        """Identities with merged_into set are excluded from grouping."""
        from core.grouping import group_inbox_identities
        from core.photo_registry import PhotoRegistry
        from core.registry import IdentityRegistry, IdentityState

        base = random_embedding(seed=42)

        registry = IdentityRegistry()
        face_data = {}
        photo_registry = PhotoRegistry()

        # Create 3 similar inbox identities
        ids = []
        for i in range(3):
            iid = registry.create_identity(
                anchor_ids=[f"face_{i}"],
                user_source="test",
                name=f"Person {i}",
                state=IdentityState.INBOX,
            )
            ids.append(iid)
            face_data[f"face_{i}"] = {
                "mu": base.copy(),
                "sigma_sq": np.full(512, 0.1, dtype=np.float32),
            }
            photo_registry.register_face(f"photo_{i}", f"img_{i}.jpg", f"face_{i}")

        # Manually mark one as already merged
        identity = registry._identities[ids[2]]
        identity["merged_into"] = ids[0]

        results = group_inbox_identities(
            registry=registry,
            face_data=face_data,
            photo_registry=photo_registry,
            dry_run=False,
        )

        # Only 2 non-merged inbox identities → 1 group of 2
        assert results["identities_before"] == 2
        assert results["total_groups"] == 1
        assert results["groups"][0]["size"] == 2

    def test_primary_picks_most_faces(self):
        """Primary identity should be the one with most faces."""
        from core.grouping import group_inbox_identities

        base = random_embedding(seed=42)
        specs = [
            {"face_ids": ["a1"], "embedding": base.copy()},
            {"face_ids": ["b1", "b2", "b3"], "embedding": base.copy()},  # 3 faces
            {"face_ids": ["c1"], "embedding": similar_embedding(base, distance=0.3)},
        ]

        registry, face_data, photo_registry = make_inbox_registry(specs)

        results = group_inbox_identities(
            registry=registry,
            face_data=face_data,
            photo_registry=photo_registry,
            dry_run=True,
        )

        assert results["total_groups"] == 1
        group = results["groups"][0]
        # The primary should be the one with 3 faces
        primary_faces = registry.get_all_face_ids(group["primary_id"])
        assert len(primary_faces) == 3

    def test_merge_results_tracked(self):
        """Execute mode should track individual merge results."""
        from core.grouping import group_inbox_identities

        base = random_embedding(seed=42)
        specs = [
            {"face_ids": ["face_a"], "embedding": base.copy()},
            {"face_ids": ["face_b"], "embedding": similar_embedding(base, distance=0.3)},
        ]

        registry, face_data, photo_registry = make_inbox_registry(specs)

        results = group_inbox_identities(
            registry=registry,
            face_data=face_data,
            photo_registry=photo_registry,
            dry_run=False,
        )

        assert len(results["merge_results"]) == 1
        assert results["merge_results"][0]["success"] is True
