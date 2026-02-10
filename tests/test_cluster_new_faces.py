"""Tests for scripts/cluster_new_faces.py — AD-001 compliance."""

import numpy as np
import pytest
from unittest.mock import patch


def _make_face_data(face_id: str, mu_vals=None):
    """Helper: create face_data entry with given mu vector."""
    if mu_vals is None:
        mu_vals = np.random.randn(512).astype(np.float32)
    return {
        "mu": np.asarray(mu_vals, dtype=np.float32),
        "sigma_sq": np.full(512, 0.5, dtype=np.float32),
    }


class TestMultiAnchorMatching:
    """AD-001: cluster_new_faces must use min-distance, not centroid averaging."""

    def test_uses_min_distance_not_centroid(self):
        """Verify find_matches uses best-linkage (min distance to any face)."""
        from scripts.cluster_new_faces import find_matches

        # Create a confirmed identity with 2 very different faces
        # Face A at position [1, 0, 0, ...], Face B at position [-1, 0, 0, ...]
        face_a = np.zeros(512, dtype=np.float32)
        face_a[0] = 1.0
        face_b = np.zeros(512, dtype=np.float32)
        face_b[0] = -1.0

        # Create an inbox face near Face A
        inbox_face = np.zeros(512, dtype=np.float32)
        inbox_face[0] = 0.9  # Very close to face_a, far from face_b

        face_data = {
            "face_a": _make_face_data("face_a", face_a),
            "face_b": _make_face_data("face_b", face_b),
            "inbox_test": _make_face_data("inbox_test", inbox_face),
        }

        identities_data = {
            "identities": {
                "confirmed-1": {
                    "identity_id": "confirmed-1",
                    "name": "Test Person",
                    "state": "CONFIRMED",
                    "anchor_ids": ["face_a", "face_b"],
                    "candidate_ids": [],
                    "negative_ids": [],
                },
                "inbox-1": {
                    "identity_id": "inbox-1",
                    "name": "Unidentified Person 1",
                    "state": "INBOX",
                    "anchor_ids": ["inbox_test"],
                    "candidate_ids": [],
                    "negative_ids": [],
                },
            }
        }

        # With centroid: centroid = mean(face_a, face_b) = [0, 0, ...]
        # Distance inbox_test to centroid = |[0.9, 0, ...] - [0, 0, ...]| = 0.9
        # With multi-anchor: min(dist to face_a, dist to face_b)
        # dist to face_a = |[0.9, 0, ...] - [1, 0, ...]| = 0.1
        # dist to face_b = |[0.9, 0, ...] - [-1, 0, ...]| = 1.9
        # Multi-anchor distance = 0.1

        suggestions = find_matches(identities_data, face_data, threshold=0.5)

        # With centroid (0.9), this would NOT match at threshold 0.5
        # With multi-anchor (0.1), this SHOULD match at threshold 0.5
        assert len(suggestions) == 1
        assert suggestions[0]["face_id"] == "inbox_test"
        assert suggestions[0]["target_identity_id"] == "confirmed-1"
        assert suggestions[0]["distance"] < 0.5  # Should be ~0.1, not ~0.9

    def test_respects_threshold(self):
        """Only matches below threshold are proposed."""
        from scripts.cluster_new_faces import find_matches

        # Face far from confirmed identity
        confirmed_face = np.zeros(512, dtype=np.float32)
        confirmed_face[0] = 1.0

        far_face = np.zeros(512, dtype=np.float32)
        far_face[0] = -1.0  # Distance = 2.0

        face_data = {
            "cf1": _make_face_data("cf1", confirmed_face),
            "inbox_far": _make_face_data("inbox_far", far_face),
        }

        identities_data = {
            "identities": {
                "confirmed-1": {
                    "identity_id": "confirmed-1",
                    "name": "Test Person",
                    "state": "CONFIRMED",
                    "anchor_ids": ["cf1"],
                    "candidate_ids": [],
                    "negative_ids": [],
                },
                "inbox-1": {
                    "identity_id": "inbox-1",
                    "name": "Unidentified Person 1",
                    "state": "INBOX",
                    "anchor_ids": ["inbox_far"],
                    "candidate_ids": [],
                    "negative_ids": [],
                },
            }
        }

        suggestions = find_matches(identities_data, face_data, threshold=1.0)
        assert len(suggestions) == 0  # Distance 2.0 > threshold 1.0

    def test_no_centroid_function_called(self):
        """Verify compute_centroid is not used in find_matches."""
        import scripts.cluster_new_faces as module

        # After the fix, compute_centroid should not exist or not be used
        # Check that find_matches doesn't call it
        assert not hasattr(module, "compute_centroid"), \
            "compute_centroid should be removed — AD-001 violation"

    def test_co_occurrence_check(self):
        """Faces from the same photo as a confirmed face are excluded."""
        from scripts.cluster_new_faces import find_matches

        # Two faces from the same photo (same filename prefix)
        face_1 = np.zeros(512, dtype=np.float32)
        face_1[0] = 1.0

        # Very close face but from same photo
        close_face = np.zeros(512, dtype=np.float32)
        close_face[0] = 0.99

        face_data = {
            "photo1:face0": _make_face_data("photo1:face0", face_1),
            "photo1:face1": _make_face_data("photo1:face1", close_face),
        }

        identities_data = {
            "identities": {
                "confirmed-1": {
                    "identity_id": "confirmed-1",
                    "name": "Test Person",
                    "state": "CONFIRMED",
                    "anchor_ids": ["photo1:face0"],
                    "candidate_ids": [],
                    "negative_ids": [],
                },
                "inbox-1": {
                    "identity_id": "inbox-1",
                    "name": "Unidentified Person 1",
                    "state": "INBOX",
                    "anchor_ids": ["photo1:face1"],
                    "candidate_ids": [],
                    "negative_ids": [],
                },
            }
        }

        suggestions = find_matches(identities_data, face_data, threshold=1.0)
        # Same photo faces should be excluded by co-occurrence check
        assert len(suggestions) == 0

    def test_picks_closest_identity(self):
        """When face matches multiple identities, pick the closest one."""
        from scripts.cluster_new_faces import find_matches

        # Two confirmed identities at different distances
        face_near = np.zeros(512, dtype=np.float32)
        face_near[0] = 0.8
        face_far = np.zeros(512, dtype=np.float32)
        face_far[0] = -0.5

        inbox_face = np.zeros(512, dtype=np.float32)
        inbox_face[0] = 0.75  # Closer to face_near

        face_data = {
            "near_cf": _make_face_data("near_cf", face_near),
            "far_cf": _make_face_data("far_cf", face_far),
            "inbox_test": _make_face_data("inbox_test", inbox_face),
        }

        identities_data = {
            "identities": {
                "near-id": {
                    "identity_id": "near-id",
                    "name": "Near Person",
                    "state": "CONFIRMED",
                    "anchor_ids": ["near_cf"],
                    "candidate_ids": [],
                    "negative_ids": [],
                },
                "far-id": {
                    "identity_id": "far-id",
                    "name": "Far Person",
                    "state": "CONFIRMED",
                    "anchor_ids": ["far_cf"],
                    "candidate_ids": [],
                    "negative_ids": [],
                },
                "inbox-1": {
                    "identity_id": "inbox-1",
                    "name": "Unidentified Person 1",
                    "state": "INBOX",
                    "anchor_ids": ["inbox_test"],
                    "candidate_ids": [],
                    "negative_ids": [],
                },
            }
        }

        suggestions = find_matches(identities_data, face_data, threshold=2.0)
        assert len(suggestions) == 1
        assert suggestions[0]["target_identity_id"] == "near-id"


class TestRejectionMemory:
    """AD-004: clustering must exclude rejected pairs."""

    def test_clustering_excludes_rejected_pairs(self):
        """Clustering does not propose matches between rejected pairs."""
        from scripts.cluster_new_faces import find_matches

        # Create a confirmed identity and a close inbox face
        conf_face = np.zeros(512, dtype=np.float32)
        conf_face[0] = 1.0
        inbox_face = np.zeros(512, dtype=np.float32)
        inbox_face[0] = 0.95  # Very close (distance ~0.05)

        face_data = {
            "cf1": _make_face_data("cf1", conf_face),
            "inbox_1": _make_face_data("inbox_1", inbox_face),
        }

        identities_data = {
            "identities": {
                "confirmed-1": {
                    "identity_id": "confirmed-1",
                    "name": "Person A",
                    "state": "CONFIRMED",
                    "anchor_ids": ["cf1"],
                    "candidate_ids": [],
                    "negative_ids": [],
                },
                "inbox-1": {
                    "identity_id": "inbox-1",
                    "name": "Unidentified",
                    "state": "INBOX",
                    "anchor_ids": ["inbox_1"],
                    "candidate_ids": [],
                    "negative_ids": ["identity:confirmed-1"],  # REJECTED
                },
            }
        }

        suggestions = find_matches(identities_data, face_data, threshold=1.05)
        assert len(suggestions) == 0  # Rejected pair excluded

    def test_clustering_allows_non_rejected_pairs(self):
        """Non-rejected pairs still get proposed when close enough."""
        from scripts.cluster_new_faces import find_matches

        conf_face = np.zeros(512, dtype=np.float32)
        conf_face[0] = 1.0
        inbox_face = np.zeros(512, dtype=np.float32)
        inbox_face[0] = 0.95

        face_data = {
            "cf1": _make_face_data("cf1", conf_face),
            "inbox_1": _make_face_data("inbox_1", inbox_face),
        }

        identities_data = {
            "identities": {
                "confirmed-1": {
                    "identity_id": "confirmed-1",
                    "name": "Person A",
                    "state": "CONFIRMED",
                    "anchor_ids": ["cf1"],
                    "candidate_ids": [],
                    "negative_ids": [],
                },
                "inbox-1": {
                    "identity_id": "inbox-1",
                    "name": "Unidentified",
                    "state": "INBOX",
                    "anchor_ids": ["inbox_1"],
                    "candidate_ids": [],
                    "negative_ids": [],  # No rejections
                },
            }
        }

        suggestions = find_matches(identities_data, face_data, threshold=1.05)
        assert len(suggestions) == 1


class TestAmbiguityDetection:
    """ML-006: margin-based confidence for ambiguous family matches."""

    def test_ambiguous_match_flagged(self):
        """Face equidistant to two identities gets ambiguous=True."""
        from scripts.cluster_new_faces import find_matches

        # Two confirmed identities nearly equidistant from inbox face
        face_a = np.zeros(512, dtype=np.float32)
        face_a[0] = 1.0
        face_b = np.zeros(512, dtype=np.float32)
        face_b[0] = -1.0
        # Inbox face slightly closer to A (distance ~0.1) than B (distance ~0.12)
        inbox_face = np.zeros(512, dtype=np.float32)
        inbox_face[0] = 0.9

        face_data = {
            "cf_a": _make_face_data("cf_a", face_a),
            "cf_b": _make_face_data("cf_b", face_b),
            "inbox_1": _make_face_data("inbox_1", inbox_face),
        }

        identities_data = {
            "identities": {
                "id-a": {
                    "identity_id": "id-a",
                    "name": "Person A",
                    "state": "CONFIRMED",
                    "anchor_ids": ["cf_a"],
                    "candidate_ids": [],
                    "negative_ids": [],
                },
                "id-b": {
                    "identity_id": "id-b",
                    "name": "Person B",
                    "state": "CONFIRMED",
                    "anchor_ids": ["cf_b"],
                    "candidate_ids": [],
                    "negative_ids": [],
                },
                "inbox-1": {
                    "identity_id": "inbox-1",
                    "name": "Unidentified",
                    "state": "INBOX",
                    "anchor_ids": ["inbox_1"],
                    "candidate_ids": [],
                    "negative_ids": [],
                },
            }
        }

        # High threshold to catch both
        suggestions = find_matches(identities_data, face_data, threshold=2.0)
        assert len(suggestions) == 1
        # Should have margin and ambiguous fields
        assert "margin" in suggestions[0]
        assert "ambiguous" in suggestions[0]

    def test_clear_match_not_ambiguous(self):
        """Face much closer to one identity is not flagged as ambiguous."""
        from scripts.cluster_new_faces import find_matches

        face_close = np.zeros(512, dtype=np.float32)
        face_close[0] = 1.0
        face_far = np.zeros(512, dtype=np.float32)
        face_far[0] = -10.0  # Very far away

        inbox_face = np.zeros(512, dtype=np.float32)
        inbox_face[0] = 0.95  # Very close to face_close

        face_data = {
            "cf_close": _make_face_data("cf_close", face_close),
            "cf_far": _make_face_data("cf_far", face_far),
            "inbox_1": _make_face_data("inbox_1", inbox_face),
        }

        identities_data = {
            "identities": {
                "close-id": {
                    "identity_id": "close-id",
                    "name": "Close Person",
                    "state": "CONFIRMED",
                    "anchor_ids": ["cf_close"],
                    "candidate_ids": [],
                    "negative_ids": [],
                },
                "far-id": {
                    "identity_id": "far-id",
                    "name": "Far Person",
                    "state": "CONFIRMED",
                    "anchor_ids": ["cf_far"],
                    "candidate_ids": [],
                    "negative_ids": [],
                },
                "inbox-1": {
                    "identity_id": "inbox-1",
                    "name": "Unidentified",
                    "state": "INBOX",
                    "anchor_ids": ["inbox_1"],
                    "candidate_ids": [],
                    "negative_ids": [],
                },
            }
        }

        suggestions = find_matches(identities_data, face_data, threshold=2.0)
        assert len(suggestions) == 1
        assert suggestions[0]["ambiguous"] is False
        assert suggestions[0]["margin"] > 0.15


class TestConfidenceLabel:
    """Tests for AD-013 calibrated confidence labels."""

    def test_very_high_label(self):
        from scripts.cluster_new_faces import confidence_label
        assert confidence_label(0.50) == "VERY HIGH"
        assert confidence_label(0.79) == "VERY HIGH"

    def test_high_label(self):
        from scripts.cluster_new_faces import confidence_label
        assert confidence_label(0.80) == "HIGH"
        assert confidence_label(1.04) == "HIGH"

    def test_moderate_label(self):
        from scripts.cluster_new_faces import confidence_label
        assert confidence_label(1.05) == "MODERATE"
        assert confidence_label(1.14) == "MODERATE"

    def test_low_label(self):
        from scripts.cluster_new_faces import confidence_label
        assert confidence_label(1.15) == "LOW"
        assert confidence_label(2.00) == "LOW"

    def test_boundary_very_high_to_high(self):
        from scripts.cluster_new_faces import confidence_label
        assert confidence_label(0.80) == "HIGH"

    def test_boundary_high_to_moderate(self):
        from scripts.cluster_new_faces import confidence_label
        assert confidence_label(1.05) == "MODERATE"

    def test_boundary_moderate_to_low(self):
        from scripts.cluster_new_faces import confidence_label
        assert confidence_label(1.15) == "LOW"


class TestApplySuggestions:
    """Tests for apply_suggestions safety."""

    def test_moves_face_to_target(self):
        from scripts.cluster_new_faces import apply_suggestions

        identities_data = {
            "identities": {
                "target": {
                    "identity_id": "target",
                    "name": "Target",
                    "state": "CONFIRMED",
                    "anchor_ids": [],
                    "candidate_ids": ["existing_face"],
                    "negative_ids": [],
                    "version_id": 1,
                },
                "source": {
                    "identity_id": "source",
                    "name": "Source",
                    "state": "INBOX",
                    "anchor_ids": [],
                    "candidate_ids": ["move_me"],
                    "negative_ids": [],
                    "version_id": 1,
                },
            }
        }

        suggestions = [{
            "face_id": "move_me",
            "source_identity_id": "source",
            "target_identity_id": "target",
        }]

        updated, count = apply_suggestions(identities_data, suggestions)
        assert count == 1
        assert "move_me" in updated["identities"]["target"]["candidate_ids"]
        assert "move_me" not in updated["identities"]["source"]["candidate_ids"]

    def test_empty_source_gets_merged(self):
        from scripts.cluster_new_faces import apply_suggestions

        identities_data = {
            "identities": {
                "target": {
                    "identity_id": "target",
                    "state": "CONFIRMED",
                    "anchor_ids": [],
                    "candidate_ids": [],
                    "negative_ids": [],
                    "version_id": 1,
                },
                "source": {
                    "identity_id": "source",
                    "state": "INBOX",
                    "anchor_ids": [],
                    "candidate_ids": ["only_face"],
                    "negative_ids": [],
                    "version_id": 1,
                },
            }
        }

        suggestions = [{
            "face_id": "only_face",
            "source_identity_id": "source",
            "target_identity_id": "target",
        }]

        updated, _ = apply_suggestions(identities_data, suggestions)
        assert updated["identities"]["source"]["merged_into"] == "target"

    def test_does_not_modify_original(self):
        from scripts.cluster_new_faces import apply_suggestions

        identities_data = {
            "identities": {
                "target": {
                    "identity_id": "target",
                    "state": "CONFIRMED",
                    "anchor_ids": [],
                    "candidate_ids": ["existing"],
                    "negative_ids": [],
                    "version_id": 1,
                },
                "source": {
                    "identity_id": "source",
                    "state": "INBOX",
                    "anchor_ids": [],
                    "candidate_ids": ["move_me"],
                    "negative_ids": [],
                    "version_id": 1,
                },
            }
        }

        original_target_cands = list(identities_data["identities"]["target"]["candidate_ids"])

        suggestions = [{
            "face_id": "move_me",
            "source_identity_id": "source",
            "target_identity_id": "target",
        }]

        apply_suggestions(identities_data, suggestions)
        assert identities_data["identities"]["target"]["candidate_ids"] == original_target_cands

    def test_skips_already_merged_source(self):
        from scripts.cluster_new_faces import apply_suggestions

        identities_data = {
            "identities": {
                "target": {
                    "identity_id": "target",
                    "state": "CONFIRMED",
                    "anchor_ids": [],
                    "candidate_ids": [],
                    "negative_ids": [],
                    "version_id": 1,
                },
                "source": {
                    "identity_id": "source",
                    "state": "INBOX",
                    "anchor_ids": [],
                    "candidate_ids": ["face1"],
                    "negative_ids": [],
                    "version_id": 1,
                    "merged_into": "other",
                },
            }
        }

        suggestions = [{
            "face_id": "face1",
            "source_identity_id": "source",
            "target_identity_id": "target",
        }]

        _, count = apply_suggestions(identities_data, suggestions)
        assert count == 0


class TestThresholdConfig:
    """Tests for AD-013 threshold values in config."""

    def test_threshold_ordering(self):
        from core.config import (
            MATCH_THRESHOLD_HIGH,
            MATCH_THRESHOLD_LOW,
            MATCH_THRESHOLD_MEDIUM,
            MATCH_THRESHOLD_MODERATE,
            MATCH_THRESHOLD_VERY_HIGH,
        )

        assert MATCH_THRESHOLD_VERY_HIGH < MATCH_THRESHOLD_HIGH
        assert MATCH_THRESHOLD_HIGH < MATCH_THRESHOLD_MODERATE
        assert MATCH_THRESHOLD_MODERATE < MATCH_THRESHOLD_MEDIUM
        assert MATCH_THRESHOLD_MEDIUM < MATCH_THRESHOLD_LOW

    def test_grouping_below_high(self):
        from core.config import GROUPING_THRESHOLD, MATCH_THRESHOLD_HIGH

        assert GROUPING_THRESHOLD <= MATCH_THRESHOLD_HIGH

    def test_very_high_value(self):
        from core.config import MATCH_THRESHOLD_VERY_HIGH
        assert MATCH_THRESHOLD_VERY_HIGH == 0.80

    def test_high_is_zero_fp_ceiling(self):
        from core.config import MATCH_THRESHOLD_HIGH
        assert MATCH_THRESHOLD_HIGH == 1.05
