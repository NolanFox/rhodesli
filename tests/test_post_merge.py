"""
Tests for post-merge re-evaluation (ML-005).

After a merge, the system should suggest nearby unmatched faces
that may also belong to the merged identity.
"""

import numpy as np
import pytest
from unittest.mock import patch, MagicMock


def _make_face_data(face_id, mu_vals):
    """Helper: create face_data entry with given mu vector."""
    return {
        face_id: {
            "mu": np.asarray(mu_vals, dtype=np.float32),
            "sigma_sq": np.full(512, 0.1, dtype=np.float32),
        }
    }


class TestPostMergeSuggestions:
    """ML-005: post-merge re-evaluation suggests nearby unmatched faces."""

    def test_suggest_similar_after_merge(self):
        """After merging, nearby unmatched faces are suggested."""
        from core.neighbors import find_nearest_neighbors
        from core.registry import IdentityRegistry
        from core.photo_registry import PhotoRegistry

        photo_registry = PhotoRegistry()
        photo_registry.register_face("p1", "photo1.jpg", "anchor_face")
        photo_registry.register_face("p2", "photo2.jpg", "nearby_face")
        photo_registry.register_face("p3", "photo3.jpg", "far_face")

        registry = IdentityRegistry()
        target_id = registry.create_identity(
            anchor_ids=["anchor_face"], user_source="test", name="Leon"
        )
        nearby_id = registry.create_identity(
            anchor_ids=["nearby_face"], user_source="test"
        )
        far_id = registry.create_identity(
            anchor_ids=["far_face"], user_source="test"
        )

        # Anchor at [1, 0, ...], nearby at [0.95, 0, ...], far at [-5, 0, ...]
        anchor = np.zeros(512, dtype=np.float32)
        anchor[0] = 1.0
        nearby = np.zeros(512, dtype=np.float32)
        nearby[0] = 0.95
        far = np.zeros(512, dtype=np.float32)
        far[0] = -5.0

        face_data = {}
        face_data.update(_make_face_data("anchor_face", anchor))
        face_data.update(_make_face_data("nearby_face", nearby))
        face_data.update(_make_face_data("far_face", far))

        neighbors = find_nearest_neighbors(
            target_id, registry, photo_registry, face_data, limit=5
        )

        # Nearby face should be closest
        assert len(neighbors) >= 1
        assert neighbors[0]["identity_id"] == nearby_id
        assert neighbors[0]["distance"] < 0.1  # Very close

    def test_suggest_similar_uses_multi_anchor(self):
        """Suggestions use min-distance across all anchors (AD-001)."""
        from core.neighbors import find_nearest_neighbors
        from core.registry import IdentityRegistry
        from core.photo_registry import PhotoRegistry

        photo_registry = PhotoRegistry()
        photo_registry.register_face("p1", "a.jpg", "anchor_1")
        photo_registry.register_face("p2", "b.jpg", "anchor_2")
        photo_registry.register_face("p3", "c.jpg", "candidate_face")

        registry = IdentityRegistry()
        # Identity with 2 anchors at opposite ends
        target_id = registry.create_identity(
            anchor_ids=["anchor_1", "anchor_2"], user_source="test"
        )
        cand_id = registry.create_identity(
            anchor_ids=["candidate_face"], user_source="test"
        )

        a1 = np.zeros(512, dtype=np.float32)
        a1[0] = 1.0
        a2 = np.zeros(512, dtype=np.float32)
        a2[0] = -1.0
        # Candidate close to anchor_2
        cand = np.zeros(512, dtype=np.float32)
        cand[0] = -0.95

        face_data = {}
        face_data.update(_make_face_data("anchor_1", a1))
        face_data.update(_make_face_data("anchor_2", a2))
        face_data.update(_make_face_data("candidate_face", cand))

        neighbors = find_nearest_neighbors(
            target_id, registry, photo_registry, face_data, limit=5
        )

        assert len(neighbors) == 1
        # Should use min distance (to anchor_2), not centroid or max
        assert neighbors[0]["distance"] < 0.1

    def test_suggest_similar_excludes_rejected_pairs(self):
        """Faces previously rejected via 'Not Same' are excluded."""
        from core.neighbors import find_nearest_neighbors
        from core.registry import IdentityRegistry
        from core.photo_registry import PhotoRegistry

        photo_registry = PhotoRegistry()
        photo_registry.register_face("p1", "a.jpg", "anchor")
        photo_registry.register_face("p2", "b.jpg", "rejected_face")

        registry = IdentityRegistry()
        target_id = registry.create_identity(
            anchor_ids=["anchor"], user_source="test"
        )
        rejected_id = registry.create_identity(
            anchor_ids=["rejected_face"], user_source="test"
        )
        # Mark as rejected
        registry._identities[target_id]["negative_ids"] = [f"identity:{rejected_id}"]

        anchor = np.zeros(512, dtype=np.float32)
        anchor[0] = 1.0
        close = np.zeros(512, dtype=np.float32)
        close[0] = 0.99  # Very close but rejected

        face_data = {}
        face_data.update(_make_face_data("anchor", anchor))
        face_data.update(_make_face_data("rejected_face", close))

        neighbors = find_nearest_neighbors(
            target_id, registry, photo_registry, face_data, limit=5
        )

        # Rejected identity should be excluded
        assert all(n["identity_id"] != rejected_id for n in neighbors)


class TestPostMergeSuggestionsUI:
    """Tests for the _post_merge_suggestions UI function."""

    def test_no_suggestions_returns_empty(self):
        """When no high-confidence matches exist, returns empty Span."""
        from app.main import _post_merge_suggestions
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        target_id = registry.create_identity(
            anchor_ids=["face1"], user_source="test"
        )

        # Mock find_nearest_neighbors to return nothing close
        with patch("app.main.get_face_data", return_value={}), \
             patch("app.main.load_photo_registry"), \
             patch("core.neighbors.find_nearest_neighbors", return_value=[]):
            result = _post_merge_suggestions(target_id, registry, set())

        # Should return an empty Span (no suggestions)
        assert result is not None

    def test_high_confidence_suggestions_shown(self):
        """High-confidence matches shown in suggestion panel."""
        from app.main import _post_merge_suggestions, MATCH_THRESHOLD_HIGH
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        target_id = registry.create_identity(
            anchor_ids=["face1"], user_source="test", name="Leon"
        )
        neighbor_id = registry.create_identity(
            anchor_ids=["face2"], user_source="test", name="Unknown"
        )

        mock_neighbors = [{
            "identity_id": neighbor_id,
            "name": "Unknown",
            "distance": 0.5,  # Well below HIGH threshold
            "face_count": 1,
            "can_merge": True,
            "merge_blocked_reason": None,
            "rank": 1,
            "percentile": 1.0,
            "confidence_gap": 50.0,
        }]

        with patch("core.neighbors.find_nearest_neighbors", return_value=mock_neighbors):
            with patch("app.main.get_face_data", return_value={}), \
                 patch("app.main.load_photo_registry"):
                result = _post_merge_suggestions(target_id, registry, set())

        # Should contain suggestion content
        from fastcore.xml import to_xml
        html = to_xml(result)
        assert "might also want to review" in html
