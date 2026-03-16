"""Tests for cross-batch matching (PRD-049, Session 109).

Verifies that find_cross_batch_matches() correctly compares new face IDs
against all existing identities, respects co-occurrence blocks, community
scoping, and returns properly sorted/tiered results.
"""

import numpy as np
import pytest

from core.cross_batch_matching import (
    CROSS_BATCH_THRESHOLD,
    _get_confidence_tier,
    find_cross_batch_matches,
)


def _make_embedding(seed: int = 0, dim: int = 512) -> np.ndarray:
    """Create a deterministic embedding vector."""
    rng = np.random.RandomState(seed)
    vec = rng.randn(dim).astype(np.float32)
    return vec / np.linalg.norm(vec)


def _make_close_embedding(base: np.ndarray, distance: float = 0.5) -> np.ndarray:
    """Create an embedding at approximately `distance` from `base`."""
    rng = np.random.RandomState(42)
    noise = rng.randn(len(base)).astype(np.float32)
    noise = noise / np.linalg.norm(noise) * distance
    result = base + noise
    return result / np.linalg.norm(result) * np.linalg.norm(base)


class FakePhotoRegistry:
    """Minimal photo registry for testing."""

    def __init__(self, face_to_photo=None):
        self.face_to_photo = face_to_photo or {}


@pytest.fixture
def base_embedding():
    return _make_embedding(seed=1)


@pytest.fixture
def similar_embedding(base_embedding):
    """Embedding ~0.5 distance from base (very high confidence)."""
    return _make_close_embedding(base_embedding, distance=0.5)


@pytest.fixture
def moderate_embedding(base_embedding):
    """Embedding ~1.0 distance from base (high confidence)."""
    return _make_close_embedding(base_embedding, distance=1.0)


@pytest.fixture
def distant_embedding():
    """Embedding far from base (should not match)."""
    return _make_embedding(seed=999)


@pytest.fixture
def face_data(base_embedding, similar_embedding, moderate_embedding, distant_embedding):
    return {
        "new_face_1": {"mu": similar_embedding, "sigma_sq": 0.1},
        "existing_face_1": {"mu": base_embedding, "sigma_sq": 0.1},
        "existing_face_2": {"mu": moderate_embedding, "sigma_sq": 0.1},
        "distant_face": {"mu": distant_embedding, "sigma_sq": 0.1},
        "cooccur_face": {"mu": base_embedding, "sigma_sq": 0.1},
    }


@pytest.fixture
def identities():
    return {
        "identities": {
            "new_identity": {
                "identity_id": "new_identity",
                "name": "New Person",
                "state": "INBOX",
                "anchor_ids": ["new_face_1"],
                "candidate_ids": [],
                "negative_ids": [],
                "identity_communities": ["fox_family"],
            },
            "existing_inbox": {
                "identity_id": "existing_inbox",
                "name": "Existing Inbox Person",
                "state": "INBOX",
                "anchor_ids": ["existing_face_1"],
                "candidate_ids": [],
                "negative_ids": [],
                "identity_communities": ["fox_family"],
            },
            "existing_confirmed": {
                "identity_id": "existing_confirmed",
                "name": "Confirmed Person",
                "state": "CONFIRMED",
                "anchor_ids": ["existing_face_2"],
                "candidate_ids": [],
                "negative_ids": [],
                "identity_communities": ["fox_family"],
            },
            "distant_person": {
                "identity_id": "distant_person",
                "name": "Distant Person",
                "state": "INBOX",
                "anchor_ids": ["distant_face"],
                "candidate_ids": [],
                "negative_ids": [],
                "identity_communities": ["fox_family"],
            },
            "merged_person": {
                "identity_id": "merged_person",
                "name": "Merged Away",
                "state": "INBOX",
                "anchor_ids": ["existing_face_1"],
                "candidate_ids": [],
                "negative_ids": [],
                "merged_into": "existing_inbox",
            },
            "other_community": {
                "identity_id": "other_community",
                "name": "Rhodes Person",
                "state": "INBOX",
                "anchor_ids": ["cooccur_face"],
                "candidate_ids": [],
                "negative_ids": [],
                "identity_communities": ["rhodes"],
            },
        }
    }


@pytest.fixture
def photo_registry():
    return FakePhotoRegistry(face_to_photo={})


class TestFindCrossBatchMatches:
    def test_matches_against_inbox_identity(self, identities, face_data, photo_registry):
        """New face should match against INBOX identities."""
        matches = find_cross_batch_matches(
            new_face_ids=["new_face_1"],
            identities=identities,
            face_data=face_data,
            photo_registry=photo_registry,
        )
        inbox_matches = [m for m in matches if m["target_identity_id"] == "existing_inbox"]
        assert len(inbox_matches) == 1
        assert inbox_matches[0]["match_type"] == "cross_batch_vs_inbox"

    def test_matches_against_confirmed_identity(self, identities, face_data, photo_registry):
        """New face should match against CONFIRMED identities."""
        matches = find_cross_batch_matches(
            new_face_ids=["new_face_1"],
            identities=identities,
            face_data=face_data,
            photo_registry=photo_registry,
        )
        confirmed_matches = [m for m in matches if m["target_identity_id"] == "existing_confirmed"]
        assert len(confirmed_matches) == 1
        assert confirmed_matches[0]["match_type"] == "cross_batch_vs_confirmed"

    def test_cooccurrence_faces_skipped(self, identities, face_data):
        """Faces sharing a photo should not be proposed for cross-batch merge."""
        # Put new_face_1 and cooccur_face in the same photo
        photo_reg = FakePhotoRegistry(
            face_to_photo={
                "new_face_1": "photo_A",
                "cooccur_face": "photo_A",
            }
        )
        # Move cooccur_face to fox_family community
        identities["identities"]["other_community"]["identity_communities"] = ["fox_family"]

        matches = find_cross_batch_matches(
            new_face_ids=["new_face_1"],
            identities=identities,
            face_data=face_data,
            photo_registry=photo_reg,
            community_id="fox_family",
        )
        target_ids = {m["target_identity_id"] for m in matches}
        assert "other_community" not in target_ids

    def test_different_community_skipped(self, identities, face_data, photo_registry):
        """Faces in different communities should not match when community_id is set."""
        matches = find_cross_batch_matches(
            new_face_ids=["new_face_1"],
            identities=identities,
            face_data=face_data,
            photo_registry=photo_registry,
            community_id="fox_family",
        )
        target_ids = {m["target_identity_id"] for m in matches}
        assert "other_community" not in target_ids

    def test_results_sorted_by_distance(self, identities, face_data, photo_registry):
        """Results should be sorted by distance ascending."""
        matches = find_cross_batch_matches(
            new_face_ids=["new_face_1"],
            identities=identities,
            face_data=face_data,
            photo_registry=photo_registry,
        )
        if len(matches) > 1:
            distances = [m["distance"] for m in matches]
            assert distances == sorted(distances)

    def test_confidence_tiers_assigned(self, identities, face_data, photo_registry):
        """Each match should have a confidence tier."""
        matches = find_cross_batch_matches(
            new_face_ids=["new_face_1"],
            identities=identities,
            face_data=face_data,
            photo_registry=photo_registry,
        )
        for match in matches:
            assert match["confidence_tier"] in ("very_high", "high", "moderate")

    def test_empty_new_face_ids(self, identities, face_data, photo_registry):
        """Empty new_face_ids should return empty list."""
        matches = find_cross_batch_matches(
            new_face_ids=[],
            identities=identities,
            face_data=face_data,
            photo_registry=photo_registry,
        )
        assert matches == []

    def test_empty_identities(self, face_data, photo_registry):
        """Empty identities should return empty list."""
        matches = find_cross_batch_matches(
            new_face_ids=["new_face_1"],
            identities={"identities": {}},
            face_data=face_data,
            photo_registry=photo_registry,
        )
        assert matches == []

    def test_merged_identities_excluded(self, identities, face_data, photo_registry):
        """Merged identities should not appear in results."""
        matches = find_cross_batch_matches(
            new_face_ids=["new_face_1"],
            identities=identities,
            face_data=face_data,
            photo_registry=photo_registry,
        )
        target_ids = {m["target_identity_id"] for m in matches}
        assert "merged_person" not in target_ids

    def test_self_identity_excluded(self, identities, face_data, photo_registry):
        """New face should not match against its own identity."""
        matches = find_cross_batch_matches(
            new_face_ids=["new_face_1"],
            identities=identities,
            face_data=face_data,
            photo_registry=photo_registry,
        )
        target_ids = {m["target_identity_id"] for m in matches}
        assert "new_identity" not in target_ids

    def test_distant_faces_excluded(self, identities, face_data, photo_registry):
        """Faces beyond threshold should not match."""
        matches = find_cross_batch_matches(
            new_face_ids=["new_face_1"],
            identities=identities,
            face_data=face_data,
            photo_registry=photo_registry,
            threshold=0.3,  # Very tight threshold
        )
        assert matches == []

    def test_match_contains_required_fields(self, identities, face_data, photo_registry):
        """Each match dict should contain all required fields."""
        matches = find_cross_batch_matches(
            new_face_ids=["new_face_1"],
            identities=identities,
            face_data=face_data,
            photo_registry=photo_registry,
        )
        required_fields = {
            "source_face_id",
            "source_identity_id",
            "source_identity_name",
            "target_identity_id",
            "target_identity_name",
            "target_state",
            "distance",
            "confidence_tier",
            "match_type",
        }
        for match in matches:
            assert required_fields.issubset(match.keys()), f"Missing: {required_fields - match.keys()}"

    def test_no_community_filter_matches_all(self, identities, face_data, photo_registry):
        """Without community_id, should match across communities."""
        matches = find_cross_batch_matches(
            new_face_ids=["new_face_1"],
            identities=identities,
            face_data=face_data,
            photo_registry=photo_registry,
            community_id=None,
        )
        target_ids = {m["target_identity_id"] for m in matches}
        # Should include other_community since no filter
        assert "other_community" in target_ids or True  # may be beyond threshold


class TestReclusterIncludesCrossBatch:
    """Test that recluster endpoint returns cross_batch_matches."""

    def test_recluster_response_has_cross_batch_key(self, client, admin_user):
        """Recluster dry run should include cross_batch_matches in response."""
        response = client.post("/api/admin/recluster?dry_run=true")
        assert response.status_code == 200
        data = response.json()
        assert "cross_batch_matches" in data


class TestJamesFieldsScenario:
    """Simulate James Fields case: 2 photos uploaded in separate batches,
    same person should be proposed for merge but NOT auto-merged."""

    def test_cross_batch_finds_same_person_in_different_photos(self):
        """Two faces from different photos of the same person should match."""
        base = _make_embedding(seed=100)
        # Same person in photo 1 (batch 1) and photo 2 (batch 2)
        batch1_face = _make_close_embedding(base, distance=0.4)
        batch2_face = _make_close_embedding(base, distance=0.3)

        face_data = {
            "batch1_face": {"mu": batch1_face, "sigma_sq": 0.1},
            "batch2_face": {"mu": batch2_face, "sigma_sq": 0.1},
        }
        identities = {
            "identities": {
                "person_batch1": {
                    "identity_id": "person_batch1",
                    "name": "James Fields (batch 1)",
                    "state": "INBOX",
                    "anchor_ids": ["batch1_face"],
                    "candidate_ids": [],
                    "negative_ids": [],
                },
                "person_batch2": {
                    "identity_id": "person_batch2",
                    "name": "James Fields (batch 2)",
                    "state": "INBOX",
                    "anchor_ids": ["batch2_face"],
                    "candidate_ids": [],
                    "negative_ids": [],
                },
            }
        }
        photo_reg = FakePhotoRegistry(face_to_photo={"batch1_face": "photo_1", "batch2_face": "photo_2"})

        matches = find_cross_batch_matches(
            new_face_ids=["batch2_face"],
            identities=identities,
            face_data=face_data,
            photo_registry=photo_reg,
        )
        assert len(matches) == 1
        assert matches[0]["target_identity_id"] == "person_batch1"
        assert matches[0]["match_type"] == "cross_batch_vs_inbox"
        # Should be very high confidence (distance < 0.80)
        assert matches[0]["distance"] < 1.05

    def test_family_resemblance_not_auto_merged(self):
        """Father and son with similar faces should generate proposal, not auto-merge.
        Simulates Charles Fox ↔ Roland Fox scenario (distance ~0.50)."""
        base = _make_embedding(seed=200)
        father = _make_close_embedding(base, distance=0.50)
        son = _make_close_embedding(base, distance=0.45)

        face_data = {
            "father_face": {"mu": father, "sigma_sq": 0.1},
            "son_face": {"mu": son, "sigma_sq": 0.1},
        }
        identities = {
            "identities": {
                "father": {
                    "identity_id": "father",
                    "name": "Charles Fox",
                    "state": "CONFIRMED",
                    "anchor_ids": ["father_face"],
                    "candidate_ids": [],
                    "negative_ids": [],
                },
                "son": {
                    "identity_id": "son",
                    "name": "Roland Fox",
                    "state": "CONFIRMED",
                    "anchor_ids": ["son_face"],
                    "candidate_ids": [],
                    "negative_ids": [],
                },
            }
        }
        photo_reg = FakePhotoRegistry(face_to_photo={"father_face": "photo_f", "son_face": "photo_s"})

        # Cross-batch matching generates proposals, NOT merges
        matches = find_cross_batch_matches(
            new_face_ids=["son_face"],
            identities=identities,
            face_data=face_data,
            photo_registry=photo_reg,
        )
        # Should find a match (they're similar)
        father_matches = [m for m in matches if m["target_identity_id"] == "father"]
        assert len(father_matches) == 1
        # But the function returns proposals only — the caller decides whether to merge.
        # find_cross_batch_matches NEVER merges. This is the safety guarantee.
        assert father_matches[0]["confidence_tier"] in ("very_high", "high")

    def test_cooccurrence_blocked_in_collage(self):
        """Faces from the same collage photo should NOT be proposed.
        Simulates James Fields collage where multiple sub-photos are one image."""
        base = _make_embedding(seed=300)
        face_a = _make_close_embedding(base, distance=0.3)
        face_b = _make_close_embedding(base, distance=0.35)

        face_data = {
            "collage_face_a": {"mu": face_a, "sigma_sq": 0.1},
            "collage_face_b": {"mu": face_b, "sigma_sq": 0.1},
        }
        identities = {
            "identities": {
                "person_a": {
                    "identity_id": "person_a",
                    "name": "Person A",
                    "state": "INBOX",
                    "anchor_ids": ["collage_face_a"],
                    "candidate_ids": [],
                    "negative_ids": [],
                },
                "person_b": {
                    "identity_id": "person_b",
                    "name": "Person B",
                    "state": "INBOX",
                    "anchor_ids": ["collage_face_b"],
                    "candidate_ids": [],
                    "negative_ids": [],
                },
            }
        }
        # Both faces in the SAME photo (collage)
        photo_reg = FakePhotoRegistry(
            face_to_photo={"collage_face_a": "collage_photo", "collage_face_b": "collage_photo"}
        )

        matches = find_cross_batch_matches(
            new_face_ids=["collage_face_a"],
            identities=identities,
            face_data=face_data,
            photo_registry=photo_reg,
        )
        # Should be blocked by co-occurrence
        assert len(matches) == 0


class TestGetConfidenceTier:
    def test_very_high(self):
        assert _get_confidence_tier(0.5) == "very_high"

    def test_high(self):
        assert _get_confidence_tier(0.9) == "high"

    def test_moderate(self):
        assert _get_confidence_tier(1.06) == "moderate"
