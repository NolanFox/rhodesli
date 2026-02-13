"""Tests for Phase 4: Instagram-style face tagging with autocomplete."""

import pytest
from unittest.mock import patch, MagicMock


class TestTagDropdownInOverlay:
    """Tests for the tag dropdown appearing in face overlays."""

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    @patch("app.main.get_identity_for_face")
    def test_face_overlay_has_tag_dropdown_admin(self, mock_get_id, mock_reg, mock_dim, mock_meta):
        """Admin face overlay shows 'Type name to tag' placeholder."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = {
            "filename": "test.jpg",
            "faces": [{"face_id": "face-1", "bbox": [10, 10, 100, 100]}],
            "source": "Test",
        }
        mock_get_id.return_value = {
            "identity_id": "id-1",
            "name": "Test Person",
            "state": "CONFIRMED",
        }
        mock_reg.return_value = MagicMock()

        result = photo_view_content("p1", is_partial=True, is_admin=True)
        html = to_xml(result)

        # Should have tag dropdown
        assert "tag-dropdown-" in html
        assert "Type name to tag" in html
        assert "/api/face/tag-search" in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    @patch("app.main.get_identity_for_face")
    def test_face_overlay_has_tag_dropdown_nonadmin(self, mock_get_id, mock_reg, mock_dim, mock_meta):
        """Non-admin face overlay shows 'Who is this person?' placeholder."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = {
            "filename": "test.jpg",
            "faces": [{"face_id": "face-1", "bbox": [10, 10, 100, 100]}],
            "source": "Test",
        }
        mock_get_id.return_value = {
            "identity_id": "id-1",
            "name": "Test Person",
            "state": "CONFIRMED",
        }
        mock_reg.return_value = MagicMock()

        result = photo_view_content("p1", is_partial=True, is_admin=False)
        html = to_xml(result)

        assert "tag-dropdown-" in html
        assert "Who is this person?" in html
        assert "/api/face/tag-search" in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    @patch("app.main.get_identity_for_face")
    def test_face_overlay_has_go_to_face_card(self, mock_get_id, mock_reg, mock_dim, mock_meta):
        """Tag dropdown includes 'Go to Face Card' button."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = {
            "filename": "test.jpg",
            "faces": [{"face_id": "face-1", "bbox": [10, 10, 100, 100]}],
        }
        mock_get_id.return_value = {
            "identity_id": "id-1",
            "name": "Test Person",
            "state": "INBOX",
        }
        mock_reg.return_value = MagicMock()

        result = photo_view_content("p1", is_partial=True)
        html = to_xml(result)

        assert "Go to Face Card" in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    @patch("app.main.get_identity_for_face", return_value=None)
    def test_unidentified_face_has_tag_dropdown(self, mock_get_id, mock_reg, mock_dim, mock_meta):
        """Unidentified faces also get a tag dropdown."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = {
            "filename": "test.jpg",
            "faces": [{"face_id": "face-1", "bbox": [10, 10, 100, 100]}],
        }
        mock_reg.return_value = MagicMock()

        # Admin mode: shows "Type name to tag"
        result = photo_view_content("p1", is_partial=True, is_admin=True)
        html = to_xml(result)

        assert "tag-dropdown-" in html
        assert "Type name to tag" in html


class TestTagSearchEndpoint:
    """Tests for the /api/face/tag-search endpoint."""

    def test_tag_search_returns_results(self, client):
        """Tag search returns compact result cards with merge buttons."""
        with patch("app.main.load_registry") as mock_reg, \
             patch("app.main.get_identity_for_face", return_value=None), \
             patch("app.main.get_crop_files", return_value=set()), \
             patch("app.main.resolve_face_image_url", return_value=None):
            registry = MagicMock()
            registry.search_identities.return_value = [
                {"identity_id": "id-1", "name": "Leon Capeluto", "face_count": 5, "preview_face_id": "f1"},
                {"identity_id": "id-2", "name": "Moise Capeluto", "face_count": 3, "preview_face_id": "f2"},
            ]
            mock_reg.return_value = registry

            resp = client.get("/api/face/tag-search?face_id=test-face&q=capel")
            html = resp.text

            assert "Leon Capeluto" in html
            assert "Moise Capeluto" in html
            assert "/api/face/tag" in html

    def test_tag_search_minimum_query_length(self, client):
        """Tag search requires at least 2 characters."""
        resp = client.get("/api/face/tag-search?face_id=test-face&q=a")
        html = resp.text
        # Should return empty container (no results, no error)
        assert "Leon" not in html

    def test_tag_search_excludes_current_identity(self, client):
        """Tag search excludes the face's current identity from results."""
        with patch("app.main.load_registry") as mock_reg, \
             patch("app.main.get_identity_for_face") as mock_get_id, \
             patch("app.main.get_crop_files", return_value=set()), \
             patch("app.main.resolve_face_image_url", return_value=None):
            mock_get_id.return_value = {"identity_id": "current-id", "name": "Me"}
            registry = MagicMock()
            registry.search_identities.return_value = []
            mock_reg.return_value = registry

            client.get("/api/face/tag-search?face_id=test-face&q=test")

            # Verify exclude_id was passed
            registry.search_identities.assert_called_once()
            call_kwargs = registry.search_identities.call_args
            assert call_kwargs[1].get("exclude_id") == "current-id" or \
                   (len(call_kwargs[0]) > 1 and call_kwargs[0][1] == "current-id") or \
                   call_kwargs.kwargs.get("exclude_id") == "current-id"


class TestTagSearchNonAdmin:
    """Tests for non-admin tag-search behavior (annotation-based)."""

    def test_nonadmin_tag_search_returns_suggest_buttons(self, client, auth_enabled, regular_user):
        """Non-admin tag search returns 'Suggest match' buttons, not merge buttons."""
        with patch("app.main.load_registry") as mock_reg, \
             patch("app.main.get_identity_for_face") as mock_get_id, \
             patch("app.main.get_crop_files", return_value=set()), \
             patch("app.main.resolve_face_image_url", return_value=None):
            mock_get_id.return_value = {"identity_id": "source-id", "name": "Unknown"}
            registry = MagicMock()
            registry.search_identities.return_value = [
                {"identity_id": "id-1", "name": "Leon Capeluto", "face_count": 5, "preview_face_id": "f1"},
            ]
            mock_reg.return_value = registry

            resp = client.get("/api/face/tag-search?face_id=test-face&q=leon")
            html = resp.text

            assert "Leon Capeluto" in html
            assert "Suggest match" in html
            # Should use annotation endpoint, NOT direct merge
            assert "/api/annotations/submit" in html
            assert "/api/face/tag?" not in html

    def test_nonadmin_create_shows_suggest_label(self, client, auth_enabled, regular_user):
        """Non-admin 'Create' button says 'Suggest' and submits annotation."""
        with patch("app.main.load_registry") as mock_reg, \
             patch("app.main.get_identity_for_face") as mock_get_id, \
             patch("app.main.get_crop_files", return_value=set()), \
             patch("app.main.resolve_face_image_url", return_value=None):
            mock_get_id.return_value = {"identity_id": "source-id", "name": "Unknown"}
            registry = MagicMock()
            registry.search_identities.return_value = []
            mock_reg.return_value = registry

            resp = client.get("/api/face/tag-search?face_id=test-face&q=Sarina+Benatar")
            html = resp.text

            assert 'Suggest &quot;Sarina Benatar&quot;' in html or 'Suggest "Sarina Benatar"' in html
            assert "Submit for review" in html
            assert "/api/annotations/submit" in html
            assert "/api/face/create-identity" not in html

    def test_admin_tag_search_still_returns_merge_buttons(self, client, auth_disabled):
        """Admin tag search returns direct merge buttons (auth disabled = admin)."""
        with patch("app.main.load_registry") as mock_reg, \
             patch("app.main.get_identity_for_face", return_value=None), \
             patch("app.main.get_crop_files", return_value=set()), \
             patch("app.main.resolve_face_image_url", return_value=None):
            registry = MagicMock()
            registry.search_identities.return_value = [
                {"identity_id": "id-1", "name": "Leon Capeluto", "face_count": 5, "preview_face_id": "f1"},
            ]
            mock_reg.return_value = registry

            resp = client.get("/api/face/tag-search?face_id=test-face&q=leon")
            html = resp.text

            assert "Leon Capeluto" in html
            assert "/api/face/tag?" in html
            assert "Suggest match" not in html

    def test_anonymous_tag_search_returns_suggest_buttons(self, client, auth_enabled, no_user):
        """Anonymous user tag search returns suggestion buttons (triggers login on submit)."""
        with patch("app.main.load_registry") as mock_reg, \
             patch("app.main.get_identity_for_face") as mock_get_id, \
             patch("app.main.get_crop_files", return_value=set()), \
             patch("app.main.resolve_face_image_url", return_value=None):
            mock_get_id.return_value = {"identity_id": "source-id", "name": "Unknown"}
            registry = MagicMock()
            registry.search_identities.return_value = [
                {"identity_id": "id-1", "name": "Leon Capeluto", "face_count": 5, "preview_face_id": "f1"},
            ]
            mock_reg.return_value = registry

            resp = client.get("/api/face/tag-search?face_id=test-face&q=leon")
            html = resp.text

            assert "Leon Capeluto" in html
            assert "Suggest match" in html
            assert "/api/annotations/submit" in html


class TestTagMergeEndpoint:
    """Tests for the /api/face/tag POST endpoint."""

    def test_tag_requires_admin(self, client, auth_enabled, regular_user):
        """Tag merge requires admin permissions."""
        resp = client.post("/api/face/tag?face_id=f1&target_id=t1",
                          headers={"HX-Request": "true"})
        assert resp.status_code in (401, 403)

    def test_tag_merges_identity(self, client, auth_disabled):
        """Tag endpoint merges the face's identity into the target."""
        with patch("app.main.load_registry") as mock_reg, \
             patch("app.main.load_photo_registry") as mock_photo_reg, \
             patch("app.main.save_registry"), \
             patch("app.main.get_identity_for_face") as mock_get_id, \
             patch("app.main.get_photo_id_for_face", return_value=None):
            source = {"identity_id": "source-id", "name": "Unknown"}
            mock_get_id.return_value = source

            registry = MagicMock()
            registry.get_identity.return_value = {"identity_id": "target-id", "name": "Leon"}
            registry.merge_identities.return_value = {
                "success": True,
                "faces_merged": 1,
                "source_id": "source-id",
                "target_id": "target-id",
                "direction_swapped": False,
            }
            mock_reg.return_value = registry
            mock_photo_reg.return_value = MagicMock()

            resp = client.post("/api/face/tag?face_id=f1&target_id=target-id")
            assert resp.status_code == 200
            assert "Tagged as Leon" in resp.text

    def test_tag_same_identity_returns_info(self, client, auth_disabled):
        """Tagging with the face's own identity returns info message."""
        with patch("app.main.load_registry") as mock_reg, \
             patch("app.main.load_photo_registry"), \
             patch("app.main.get_identity_for_face") as mock_get_id:
            mock_get_id.return_value = {"identity_id": "same-id", "name": "Same"}
            mock_reg.return_value = MagicMock()

            resp = client.post("/api/face/tag?face_id=f1&target_id=same-id")
            assert resp.status_code == 200
            assert "already belongs" in resp.text

    def test_tag_face_not_found(self, client, auth_disabled):
        """Tagging a face that doesn't exist returns error."""
        with patch("app.main.load_registry") as mock_reg, \
             patch("app.main.load_photo_registry"), \
             patch("app.main.get_identity_for_face", return_value=None):
            mock_reg.return_value = MagicMock()

            resp = client.post("/api/face/tag?face_id=nonexistent&target_id=t1")
            assert resp.status_code == 404
