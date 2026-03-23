"""Tests for the multi-claimed face filter in Similar Identities panel.

The filter at identity_routes.py should:
- Keep neighbors that share face IDs (multi-claimed faces) and flag them
- Filter out neighbors with co-occurrence + low distance but no shared faces
  (genuine duplicate face detections)
"""

import pytest
from unittest.mock import MagicMock, patch

from core.photo_registry import PhotoRegistry
from core.registry import IdentityRegistry


class TestDuplicateDetectionFilter:
    """Tests for the duplicate detection filter logic in _get_similar_identities."""

    def _build_neighbor(
        self,
        identity_id="neighbor-1",
        name="Test Person",
        distance=0.0,
        can_merge=True,
        merge_blocked_reason="",
        anchor_face_ids=None,
        candidate_face_ids=None,
        co_occurrence=0,
        state="PROPOSED",
    ):
        """Build a neighbor dict matching what the enrichment loop produces."""
        return {
            "identity_id": identity_id,
            "name": name,
            "distance": distance,
            "can_merge": can_merge,
            "merge_blocked_reason": merge_blocked_reason,
            "anchor_face_ids": anchor_face_ids or [],
            "candidate_face_ids": candidate_face_ids or [],
            "co_occurrence": co_occurrence,
            "state": state,
            "confidence_gap": 0.0,
            "face_count": len(anchor_face_ids or []),
        }

    def _apply_filter(self, target_face_ids, neighbors):
        """Apply the same filter logic as identity_routes.py."""
        target_faces = set(target_face_ids)
        filtered = []
        for n in neighbors:
            if n.get("distance", 1.0) < 0.1 and n.get("co_occurrence", 0) > 0:
                neighbor_faces = set(n.get("anchor_face_ids", []) + n.get("candidate_face_ids", []))
                shared_faces = target_faces & neighbor_faces
                if shared_faces:
                    n["has_shared_faces"] = True
                    n["shared_face_count"] = len(shared_faces)
                    filtered.append(n)
                # else: filtered out (genuine duplicate detection)
            else:
                filtered.append(n)
        return filtered

    def test_keeps_neighbor_with_shared_face_ids(self):
        """Multi-claimed faces: neighbor shares face IDs with target.
        These should NOT be filtered out — they indicate a data integrity issue.
        """
        # Target identity has faces A, B, C
        target_faces = ["face_a", "face_b", "face_c"]
        # Neighbor also claims face_a and face_b (multi-claimed)
        neighbor = self._build_neighbor(
            identity_id="ghost-id",
            distance=0.0,
            co_occurrence=3,
            anchor_face_ids=["face_a", "face_b"],
        )

        result = self._apply_filter(target_faces, [neighbor])
        assert len(result) == 1
        assert result[0]["has_shared_faces"] is True
        assert result[0]["shared_face_count"] == 2

    def test_filters_genuine_co_occurrence_duplicate(self):
        """Genuine co-occurrence: different faces in same photo with near-zero distance.
        These SHOULD be filtered out — they're duplicate face detections.
        """
        target_faces = ["face_a"]
        # Neighbor has completely different face IDs
        neighbor = self._build_neighbor(
            identity_id="dup-id",
            distance=0.02,
            co_occurrence=1,
            anchor_face_ids=["face_x"],
        )

        result = self._apply_filter(target_faces, [neighbor])
        assert len(result) == 0

    def test_keeps_normal_neighbors(self):
        """Normal neighbors (distance > 0.1 or no co-occurrence) should pass through."""
        target_faces = ["face_a"]

        neighbors = [
            # Normal match, decent distance
            self._build_neighbor(identity_id="n1", distance=0.85, co_occurrence=0, anchor_face_ids=["face_x"]),
            # Low distance but no co-occurrence
            self._build_neighbor(identity_id="n2", distance=0.05, co_occurrence=0, anchor_face_ids=["face_y"]),
            # Co-occurrence but high distance
            self._build_neighbor(identity_id="n3", distance=0.5, co_occurrence=1, anchor_face_ids=["face_z"]),
        ]

        result = self._apply_filter(target_faces, neighbors)
        assert len(result) == 3

    def test_shared_faces_flag_includes_candidate_ids(self):
        """Shared face check should include candidate_ids too."""
        target_faces = ["face_a", "face_b"]
        neighbor = self._build_neighbor(
            identity_id="n1",
            distance=0.0,
            co_occurrence=1,
            anchor_face_ids=[],
            candidate_face_ids=["face_a"],
        )

        result = self._apply_filter(target_faces, [neighbor])
        assert len(result) == 1
        assert result[0]["has_shared_faces"] is True
        assert result[0]["shared_face_count"] == 1

    def test_mixed_batch_filters_correctly(self):
        """A batch of neighbors should have some kept, some filtered."""
        target_faces = ["face_a", "face_b"]

        neighbors = [
            # Multi-claimed: shares face_a -> KEEP
            self._build_neighbor(
                identity_id="multi",
                distance=0.0,
                co_occurrence=2,
                anchor_face_ids=["face_a", "face_c"],
            ),
            # Genuine co-occurrence duplicate: no shared faces -> FILTER
            self._build_neighbor(
                identity_id="dup",
                distance=0.01,
                co_occurrence=1,
                anchor_face_ids=["face_x"],
            ),
            # Normal neighbor -> KEEP
            self._build_neighbor(
                identity_id="normal",
                distance=0.7,
                co_occurrence=0,
                anchor_face_ids=["face_y"],
            ),
        ]

        result = self._apply_filter(target_faces, neighbors)
        assert len(result) == 2
        result_ids = {n["identity_id"] for n in result}
        assert "multi" in result_ids
        assert "normal" in result_ids
        assert "dup" not in result_ids


class TestAuditMultiClaimedScript:
    """Tests for the audit_multi_claimed_faces.py script functions."""

    def test_find_multi_claimed_empty(self):
        """No multi-claimed faces in clean data."""
        from scripts.audit_multi_claimed_faces import find_multi_claimed

        identities = [
            {"identity_id": "a", "anchor_ids": ["f1", "f2"], "state": "CONFIRMED"},
            {"identity_id": "b", "anchor_ids": ["f3"], "state": "PROPOSED"},
        ]
        result = find_multi_claimed(identities)
        assert len(result) == 0

    def test_find_multi_claimed_detects_overlap(self):
        """Detects faces claimed by multiple identities."""
        from scripts.audit_multi_claimed_faces import find_multi_claimed

        identities = [
            {"identity_id": "a", "anchor_ids": ["f1", "f2"], "state": "CONFIRMED"},
            {"identity_id": "b", "anchor_ids": ["f1", "f3"], "state": "PROPOSED"},
        ]
        result = find_multi_claimed(identities)
        assert "f1" in result
        assert len(result["f1"]) == 2
        assert "f2" not in result

    def test_find_multi_claimed_skips_merged(self):
        """Merged identities should not be considered."""
        from scripts.audit_multi_claimed_faces import find_multi_claimed

        identities = [
            {"identity_id": "a", "anchor_ids": ["f1"], "state": "CONFIRMED"},
            {
                "identity_id": "b",
                "anchor_ids": ["f1"],
                "state": "PROPOSED",
                "merged_into": "a",
            },
        ]
        result = find_multi_claimed(identities)
        assert len(result) == 0

    def test_pick_owner_prefers_confirmed(self):
        """CONFIRMED identity should win over PROPOSED."""
        from scripts.audit_multi_claimed_faces import pick_owner

        claimants = [
            {
                "identity_id": "proposed",
                "state": "PROPOSED",
                "anchor_ids": ["f1", "f2", "f3"],
                "created_at": "2025-01-01",
            },
            {"identity_id": "confirmed", "state": "CONFIRMED", "anchor_ids": ["f1"], "created_at": "2026-01-01"},
        ]
        owner = pick_owner(claimants)
        assert owner["identity_id"] == "confirmed"

    def test_pick_owner_prefers_more_faces_same_state(self):
        """Same state: identity with more faces wins."""
        from scripts.audit_multi_claimed_faces import pick_owner

        claimants = [
            {"identity_id": "small", "state": "PROPOSED", "anchor_ids": ["f1"], "created_at": "2025-01-01"},
            {"identity_id": "big", "state": "PROPOSED", "anchor_ids": ["f1", "f2", "f3"], "created_at": "2026-01-01"},
        ]
        owner = pick_owner(claimants)
        assert owner["identity_id"] == "big"

    def test_pick_owner_prefers_older_when_tied(self):
        """Same state, same face count: older identity wins."""
        from scripts.audit_multi_claimed_faces import pick_owner

        claimants = [
            {"identity_id": "newer", "state": "PROPOSED", "anchor_ids": ["f1"], "created_at": "2026-06-01"},
            {"identity_id": "older", "state": "PROPOSED", "anchor_ids": ["f1"], "created_at": "2025-01-01"},
        ]
        owner = pick_owner(claimants)
        assert owner["identity_id"] == "older"

    def test_compute_repairs_removes_from_non_owner(self):
        """Non-owner identities should have multi-claimed faces removed."""
        from scripts.audit_multi_claimed_faces import compute_repairs

        multi_claimed = {
            "f1": [
                {"identity_id": "owner", "state": "CONFIRMED", "anchor_ids": ["f1", "f2"], "created_at": "2025-01-01"},
                {
                    "identity_id": "ghost",
                    "state": "PROPOSED",
                    "anchor_ids": ["f1"],
                    "candidate_ids": [],
                    "created_at": "2026-01-01",
                },
            ]
        }
        faces_to_remove, empty_to_merge = compute_repairs(multi_claimed)
        assert "ghost" in faces_to_remove
        assert "f1" in faces_to_remove["ghost"]
        # Ghost has no remaining faces -> should be merged
        assert "ghost" in empty_to_merge
        assert empty_to_merge["ghost"] == "owner"

    def test_compute_repairs_no_merge_if_faces_remain(self):
        """Identity with remaining faces should NOT be marked as merged."""
        from scripts.audit_multi_claimed_faces import compute_repairs

        multi_claimed = {
            "f1": [
                {"identity_id": "owner", "state": "CONFIRMED", "anchor_ids": ["f1", "f2"], "created_at": "2025-01-01"},
                {
                    "identity_id": "partial",
                    "state": "PROPOSED",
                    "anchor_ids": ["f1", "f3"],
                    "candidate_ids": [],
                    "created_at": "2026-01-01",
                },
            ]
        }
        faces_to_remove, empty_to_merge = compute_repairs(multi_claimed)
        assert "partial" in faces_to_remove
        assert "f1" in faces_to_remove["partial"]
        # partial still has f3 -> should NOT be merged
        assert "partial" not in empty_to_merge
