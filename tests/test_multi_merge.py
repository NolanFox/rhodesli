"""Tests for the bulk-merge (multi-merge) endpoint.

POST /api/identity/{identity_id}/bulk-merge
Accepts bulk_ids (list of identity UUIDs to merge into the target).
Requires admin. Uses load_registry, save_registry, load_photo_registry.
"""

import pytest
from unittest.mock import MagicMock, patch

from starlette.testclient import TestClient


class TestBulkMerge:
    """Tests for POST /api/identity/{identity_id}/bulk-merge."""

    def _make_identity(self, identity_id, name=None, state="PROPOSED",
                       anchor_ids=None, candidate_ids=None):
        """Helper: create a minimal identity dict matching the registry schema.

        Default name uses 'Unidentified Person ...' format so _is_real_name()
        returns False, avoiding name-conflict blocks during merge.
        """
        return {
            "identity_id": identity_id,
            "name": name or f"Unidentified Person {identity_id[:8]}",
            "state": state,
            "anchor_ids": anchor_ids or [],
            "candidate_ids": candidate_ids or [],
            "negative_ids": [],
            "version_id": 1,
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }

    def _make_registry(self, identities_list):
        """Helper: build a real IdentityRegistry populated with test identities."""
        from core.registry import IdentityRegistry
        registry = IdentityRegistry()
        for ident in identities_list:
            registry._identities[ident["identity_id"]] = ident
        return registry

    def _make_photo_registry(self):
        """Helper: build a mock PhotoRegistry that allows all merges (no co-occurrence)."""
        photo_reg = MagicMock()
        photo_reg.get_photos_for_faces.return_value = set()
        return photo_reg

    def test_bulk_merge_two_identities(self, client, auth_disabled):
        """Merge 2 identities via bulk-merge endpoint."""
        target_id = "aaaa-target-1111"
        source_id = "bbbb-source-2222"

        target = self._make_identity(
            target_id, name="Leon Capeluto", state="CONFIRMED",
            anchor_ids=["face_t1", "face_t2"],
        )
        source = self._make_identity(
            source_id, state="PROPOSED",
            anchor_ids=["face_s1"],
            candidate_ids=["face_s2"],
        )

        registry = self._make_registry([target, source])
        photo_reg = self._make_photo_registry()

        with patch("app.main.load_registry", return_value=registry), \
             patch("app.main.load_photo_registry", return_value=photo_reg), \
             patch("app.main.save_registry") as mock_save:

            resp = client.post(
                f"/api/identity/{target_id}/bulk-merge",
                data={"bulk_ids": source_id},
            )

            assert resp.status_code == 200
            # save_registry should be called since at least one merge succeeded
            mock_save.assert_called_once_with(registry)

            # Verify source is marked as merged
            source_after = registry._identities[source_id]
            assert source_after.get("merged_into") is not None

    def test_bulk_merge_three_identities(self, client, auth_disabled):
        """Merge 3 identities, all faces end up in target."""
        target_id = "aaaa-target-1111"
        source1_id = "bbbb-source-2222"
        source2_id = "cccc-source-3333"

        target = self._make_identity(
            target_id, name="Leon Capeluto", state="CONFIRMED",
            anchor_ids=["face_t1"],
        )
        source1 = self._make_identity(
            source1_id, state="PROPOSED",
            anchor_ids=["face_s1a", "face_s1b"],
        )
        source2 = self._make_identity(
            source2_id, state="PROPOSED",
            anchor_ids=["face_s2a"],
            candidate_ids=["face_s2b"],
        )

        registry = self._make_registry([target, source1, source2])
        photo_reg = self._make_photo_registry()

        with patch("app.main.load_registry", return_value=registry), \
             patch("app.main.load_photo_registry", return_value=photo_reg), \
             patch("app.main.save_registry"):

            resp = client.post(
                f"/api/identity/{target_id}/bulk-merge",
                data={"bulk_ids": [source1_id, source2_id]},
            )

            assert resp.status_code == 200

            # Both sources should be marked as merged
            assert registry._identities[source1_id].get("merged_into") is not None
            assert registry._identities[source2_id].get("merged_into") is not None

            # Target should have absorbed all faces from both sources
            target_after = registry._identities[target_id]
            all_target_anchors = target_after["anchor_ids"]
            all_target_candidates = target_after["candidate_ids"]
            all_faces = all_target_anchors + all_target_candidates

            assert "face_s1a" in all_faces
            assert "face_s1b" in all_faces
            assert "face_s2a" in all_faces
            assert "face_s2b" in all_faces

    def test_bulk_merge_returns_success_message(self, client, auth_disabled):
        """Response contains success message with correct counts."""
        target_id = "aaaa-target-1111"
        source_id = "bbbb-source-2222"

        target = self._make_identity(
            target_id, name="Leon Capeluto", state="CONFIRMED",
            anchor_ids=["face_t1"],
        )
        source = self._make_identity(
            source_id, state="PROPOSED",
            anchor_ids=["face_s1"],
            candidate_ids=["face_s2"],
        )

        registry = self._make_registry([target, source])
        photo_reg = self._make_photo_registry()

        with patch("app.main.load_registry", return_value=registry), \
             patch("app.main.load_photo_registry", return_value=photo_reg), \
             patch("app.main.save_registry"):

            resp = client.post(
                f"/api/identity/{target_id}/bulk-merge",
                data={"bulk_ids": source_id},
            )

            assert resp.status_code == 200
            body = resp.text

            # Should contain a positive merged count and face count
            assert "Merged 1 identit" in body
            # The source had 2 faces (1 anchor + 1 candidate)
            assert "2 faces" in body

            # Should NOT contain failure indicators
            assert "Merged 0" not in body
            assert "failed" not in body.lower()

    def test_bulk_merge_no_selection_returns_warning(self, client, auth_disabled):
        """Submitting with no bulk_ids returns warning toast."""
        target_id = "aaaa-target-1111"

        resp = client.post(
            f"/api/identity/{target_id}/bulk-merge",
            data={},
        )

        assert resp.status_code == 200
        body = resp.text
        assert "No identities selected" in body

    def test_bulk_merge_requires_admin(self, client, auth_enabled, regular_user):
        """Non-admin users get 403."""
        target_id = "aaaa-target-1111"
        source_id = "bbbb-source-2222"

        resp = client.post(
            f"/api/identity/{target_id}/bulk-merge",
            data={"bulk_ids": source_id},
            headers={"HX-Request": "true"},
        )

        # Non-admin should be rejected with 403
        assert resp.status_code == 403
