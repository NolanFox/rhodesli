"""Tests for FB-008: Co-occurrence photo preview on Override button.

Two-step override flow:
1. Override button loads a preview panel via hx_get
2. Preview shows shared photo with face bounding boxes
3. Cancel dismisses; Confirm Override & Merge executes the merge POST
"""

import pytest
from unittest.mock import patch, MagicMock
from starlette.testclient import TestClient


class TestOverridePreviewEndpoint:
    """Tests for GET /api/identity/{target_id}/co-occurrence-preview/{neighbor_id}."""

    def _make_registry_mock(self):
        registry = MagicMock()
        registry.get_all_face_ids.side_effect = lambda iid: {
            "target-id": ["face-t1", "face-t2"],
            "neighbor-id": ["face-n1"],
        }.get(iid, [])

        def get_identity(iid):
            identities = {
                "target-id": {"identity_id": "target-id", "name": "Albert", "state": "CONFIRMED"},
                "neighbor-id": {"identity_id": "neighbor-id", "name": "Harry", "state": "PROPOSED"},
            }
            if iid not in identities:
                raise KeyError(f"Identity {iid} not found")
            return identities[iid]

        registry.get_identity = get_identity
        return registry

    def _make_photo_registry_mock(self):
        photo_registry = MagicMock()
        photo_registry.get_photos_for_faces.return_value = {"photo-1"}
        photo_registry.get_photo_path.return_value = "raw_photos/shared_photo.jpg"
        return photo_registry

    @patch("app.identity_routes._main_mod")
    @patch("app.identity_routes.photo_url", return_value="/photos/shared_photo.jpg")
    def test_preview_returns_200_with_photo(self, mock_photo_url, mock_main):
        """Preview endpoint returns 200 with photo HTML for co-occurring identities."""
        import app.main as main

        registry = self._make_registry_mock()
        photo_registry = self._make_photo_registry_mock()

        mock_main._check_admin.return_value = None
        mock_main.load_registry.return_value = registry
        mock_main.load_photo_registry.return_value = photo_registry
        mock_main.find_shared_photo_filename.return_value = "shared_photo.jpg"
        mock_main.get_photo_dimensions.return_value = (800, 600)
        mock_main.generate_photo_id.return_value = "abc123"
        mock_main.get_photo_metadata.return_value = {
            "filename": "shared_photo.jpg",
            "faces": [
                {"face_id": "face-t1", "bbox": [100, 100, 200, 200]},
                {"face_id": "face-n1", "bbox": [300, 100, 400, 200]},
                {"face_id": "face-other", "bbox": [500, 100, 600, 200]},
            ],
        }
        mock_main.get_identity_for_face.side_effect = lambda reg, fid: {
            "face-t1": {"identity_id": "target-id", "name": "Albert", "state": "CONFIRMED"},
            "face-n1": {"identity_id": "neighbor-id", "name": "Harry", "state": "PROPOSED"},
            "face-other": {"identity_id": "other-id", "name": "Someone", "state": "INBOX"},
        }.get(fid)
        mock_main.community_url_prefix.return_value = "/c/rhodes"

        c = TestClient(main.app)
        resp = c.get("/api/identity/target-id/co-occurrence-preview/neighbor-id")

        assert resp.status_code == 200
        html = resp.text
        # Should show the shared photo
        assert "shared_photo.jpg" in html
        # Should have face overlays with correct colors
        assert "border-amber-400" in html  # Target face
        assert "border-indigo-400" in html  # Neighbor face
        # Should have Cancel and Confirm buttons
        assert "Cancel" in html
        assert "Confirm Override &amp; Merge" in html
        # Should have the warning text
        assert "collage" in html
        # Should have legend
        assert "Target" in html
        assert "Neighbor" in html

    @patch("app.identity_routes._main_mod")
    def test_preview_returns_404_no_shared_photo(self, mock_main):
        """Preview endpoint returns 404 when no shared photo exists."""
        import app.main as main

        registry = self._make_registry_mock()
        photo_registry = self._make_photo_registry_mock()

        mock_main._check_admin.return_value = None
        mock_main.load_registry.return_value = registry
        mock_main.load_photo_registry.return_value = photo_registry
        mock_main.find_shared_photo_filename.return_value = ""
        mock_main.community_url_prefix.return_value = "/c/rhodes"

        c = TestClient(main.app)
        resp = c.get("/api/identity/target-id/co-occurrence-preview/neighbor-id")

        assert resp.status_code == 404
        assert "No shared photo found" in resp.text

    @patch("app.identity_routes._main_mod")
    def test_preview_requires_admin(self, mock_main):
        """Preview endpoint returns 401 for non-admin users."""
        from starlette.responses import Response
        import app.main as main

        mock_main._check_admin.return_value = Response("Unauthorized", status_code=401)

        c = TestClient(main.app)
        resp = c.get("/api/identity/target-id/co-occurrence-preview/neighbor-id")

        assert resp.status_code == 401

    @patch("app.identity_routes._main_mod")
    @patch("app.identity_routes.photo_url", return_value="/photos/shared_photo.jpg")
    def test_preview_confirm_button_has_correct_merge_url(self, mock_photo_url, mock_main):
        """Confirm button in preview panel posts to the override merge endpoint."""
        import app.main as main

        registry = self._make_registry_mock()
        photo_registry = self._make_photo_registry_mock()

        mock_main._check_admin.return_value = None
        mock_main.load_registry.return_value = registry
        mock_main.load_photo_registry.return_value = photo_registry
        mock_main.find_shared_photo_filename.return_value = "shared_photo.jpg"
        mock_main.get_photo_dimensions.return_value = (800, 600)
        mock_main.generate_photo_id.return_value = "abc123"
        mock_main.get_photo_metadata.return_value = {
            "filename": "shared_photo.jpg",
            "faces": [],
        }
        mock_main.community_url_prefix.return_value = "/c/rhodes"

        c = TestClient(main.app)
        resp = c.get("/api/identity/target-id/co-occurrence-preview/neighbor-id")

        assert resp.status_code == 200
        html = resp.text
        # The confirm button should POST to the merge endpoint with override params
        assert "override_co_occurrence=true" in html
        assert "override_reason=collage" in html
        assert "/api/identity/target-id/merge/neighbor-id" in html


class TestOverrideButtonUsesPreview:
    """Tests that Override button in neighbor_card uses hx_get for preview."""

    def test_override_button_has_hx_get_not_hx_confirm(self):
        """Override button should use hx_get to load preview, not hx_confirm."""
        from app.main import neighbor_card, to_xml

        neighbor = {
            "identity_id": "neighbor-abc",
            "name": "Test Person",
            "distance": 0.5,
            "percentile": 0.8,
            "can_merge": False,
            "merge_blocked_reason": "co_occurrence",
            "merge_blocked_reason_display": "Appear together in a photo",
            "anchor_face_ids": ["face-1"],
            "candidate_face_ids": [],
            "co_occurrence": 1,
        }
        crop_files = set()

        html = to_xml(neighbor_card(neighbor, "target-id", crop_files, user_role="admin"))

        # Should have hx_get for the preview endpoint
        assert "co-occurrence-preview" in html
        assert "hx-get" in html
        # Should NOT have hx_confirm (old behavior)
        assert "Are you sure these are the same person" not in html
        # Should NOT have a direct hx-post on the override button
        # (the POST comes from the confirm button inside the preview)
        assert "hx-post" not in html or "override_co_occurrence" not in html.split("hx-get")[0]

    def test_override_preview_container_div_exists(self):
        """Neighbor card should have an empty preview container div when merge blocked by co_occurrence."""
        from app.main import neighbor_card, to_xml

        neighbor = {
            "identity_id": "neighbor-xyz",
            "name": "Another Person",
            "distance": 0.7,
            "percentile": 0.6,
            "can_merge": False,
            "merge_blocked_reason": "co_occurrence",
            "merge_blocked_reason_display": "Appear together in a photo",
            "anchor_face_ids": ["face-2"],
            "candidate_face_ids": [],
            "co_occurrence": 1,
        }
        crop_files = set()

        html = to_xml(neighbor_card(neighbor, "target-id", crop_files, user_role="admin"))

        # Should have the preview container div with the correct ID
        assert 'id="override-preview-neighbor-xyz"' in html

    def test_non_admin_still_sees_blocked_button(self):
        """Non-admin users should still see the 'Blocked' button (not the override preview)."""
        from app.main import neighbor_card, to_xml

        neighbor = {
            "identity_id": "neighbor-abc",
            "name": "Test Person",
            "distance": 0.5,
            "percentile": 0.8,
            "can_merge": False,
            "merge_blocked_reason": "co_occurrence",
            "merge_blocked_reason_display": "Appear together in a photo",
            "anchor_face_ids": ["face-1"],
            "candidate_face_ids": [],
            "co_occurrence": 1,
        }
        crop_files = set()

        html = to_xml(neighbor_card(neighbor, "target-id", crop_files, user_role="viewer"))

        assert "Blocked" in html
        assert "co-occurrence-preview" not in html
