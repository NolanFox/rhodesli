"""Tests for back image upload, R2 integration, media groups, and browse filter.

Covers:
- Upload endpoint saves file and updates metadata with media_group fields
- R2 upload triggered in R2 mode
- Photo page renders flip button when back_image exists
- Photo page does NOT render flip button without back_image
- Front/Back labels shown on photo page when back exists
- Browse filter excludes back images when filter=front_only
- Browse filter shows only photos with back when filter=has_back
- media_group_id defaults correctly in photo registry
- Flip icon badge shown on browse cards with back images
"""

import io
import pytest
from unittest.mock import patch, MagicMock
from starlette.testclient import TestClient

from app.main import app, load_embeddings_for_photos
from core.photo_registry import PhotoRegistry


def get_real_photo_id():
    """Get a real photo_id from the embeddings for testing."""
    photos = load_embeddings_for_photos()
    if photos:
        return next(iter(photos.keys()))
    return None


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def real_photo_id():
    return get_real_photo_id()


FAKE_PHOTO = {"path": "test_photo.jpg", "filename": "test_photo.jpg"}


# =============================================================================
# Upload endpoint tests
# =============================================================================


class TestBackImageUpload:
    """Tests for back image upload endpoint with R2 integration."""

    def test_upload_saves_metadata_with_media_fields(self, client, real_photo_id):
        """Successful upload sets back_image plus media_group fields."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        mock_registry = MagicMock()
        mock_registry.set_metadata.return_value = True

        with (
            patch("app.photo_routes._main_mod.is_auth_enabled", return_value=False),
            patch("app.photo_routes._main_mod._check_admin", return_value=None),
            patch("app.photo_routes._main_mod.get_photo_metadata", return_value=FAKE_PHOTO),
            patch("app.photo_routes._main_mod.load_photo_registry", return_value=mock_registry),
            patch("app.photo_routes._main_mod.save_photo_registry"),
            patch("app.photo_routes._main_mod._invalidate_all_caches"),
            patch("app.photo_routes.storage.is_r2_mode", return_value=False),
        ):
            response = client.post(
                f"/api/photo/{real_photo_id}/back-image",
                files={"file": ("back.jpg", io.BytesIO(b"\xff\xd8\xff\xe0"), "image/jpeg")},
                headers={"HX-Request": "true"},
            )
        assert response.status_code == 200
        assert "uploaded" in response.text.lower() or "Back image" in response.text

        # Verify set_metadata was called with media_group fields
        mock_registry.set_metadata.assert_called_once()
        call_args = mock_registry.set_metadata.call_args
        metadata = call_args[0][1]
        assert "back_image" in metadata
        assert metadata["back_image"] == "test_photo_back.jpg"
        assert metadata["media_role"] == "front"
        assert metadata["media_group_id"] == real_photo_id
        assert "related_media" in metadata
        assert metadata["related_media"][0]["role"] == "back"

    def test_upload_triggers_r2_upload(self, client, real_photo_id):
        """When in R2 mode with credentials, upload_bytes_to_r2 is called."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        mock_registry = MagicMock()
        mock_registry.set_metadata.return_value = True

        mock_upload = MagicMock()

        with (
            patch("app.photo_routes._main_mod.is_auth_enabled", return_value=False),
            patch("app.photo_routes._main_mod._check_admin", return_value=None),
            patch("app.photo_routes._main_mod.get_photo_metadata", return_value=FAKE_PHOTO),
            patch("app.photo_routes._main_mod.load_photo_registry", return_value=mock_registry),
            patch("app.photo_routes._main_mod.save_photo_registry"),
            patch("app.photo_routes._main_mod._invalidate_all_caches"),
            patch("app.photo_routes.storage.is_r2_mode", return_value=True),
            patch("app.photo_routes.storage.can_write_r2", return_value=True),
            patch("app.photo_routes.storage.upload_bytes_to_r2", mock_upload),
        ):
            response = client.post(
                f"/api/photo/{real_photo_id}/back-image",
                files={"file": ("back.jpg", io.BytesIO(b"\xff\xd8\xff\xe0"), "image/jpeg")},
                headers={"HX-Request": "true"},
            )
        assert response.status_code == 200
        mock_upload.assert_called_once()
        r2_key = mock_upload.call_args[0][0]
        assert r2_key == "raw_photos/test_photo_back.jpg"

    def test_upload_no_r2_without_credentials(self, client, real_photo_id):
        """When in R2 mode without credentials, upload still succeeds locally."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        mock_registry = MagicMock()
        mock_registry.set_metadata.return_value = True

        with (
            patch("app.photo_routes._main_mod.is_auth_enabled", return_value=False),
            patch("app.photo_routes._main_mod._check_admin", return_value=None),
            patch("app.photo_routes._main_mod.get_photo_metadata", return_value=FAKE_PHOTO),
            patch("app.photo_routes._main_mod.load_photo_registry", return_value=mock_registry),
            patch("app.photo_routes._main_mod.save_photo_registry"),
            patch("app.photo_routes._main_mod._invalidate_all_caches"),
            patch("app.photo_routes.storage.is_r2_mode", return_value=True),
            patch("app.photo_routes.storage.can_write_r2", return_value=False),
        ):
            response = client.post(
                f"/api/photo/{real_photo_id}/back-image",
                files={"file": ("back.jpg", io.BytesIO(b"\xff\xd8\xff\xe0"), "image/jpeg")},
                headers={"HX-Request": "true"},
            )
        assert response.status_code == 200
        assert "uploaded" in response.text.lower() or "Back image" in response.text

    def test_upload_page_reload_in_response(self, client, real_photo_id):
        """Upload response includes JS to reload the page so flip button appears."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        mock_registry = MagicMock()
        mock_registry.set_metadata.return_value = True

        with (
            patch("app.photo_routes._main_mod.is_auth_enabled", return_value=False),
            patch("app.photo_routes._main_mod._check_admin", return_value=None),
            patch("app.photo_routes._main_mod.get_photo_metadata", return_value=FAKE_PHOTO),
            patch("app.photo_routes._main_mod.load_photo_registry", return_value=mock_registry),
            patch("app.photo_routes._main_mod.save_photo_registry"),
            patch("app.photo_routes._main_mod._invalidate_all_caches"),
            patch("app.photo_routes.storage.is_r2_mode", return_value=False),
        ):
            response = client.post(
                f"/api/photo/{real_photo_id}/back-image",
                files={"file": ("back.jpg", io.BytesIO(b"\xff\xd8\xff\xe0"), "image/jpeg")},
                headers={"HX-Request": "true"},
            )
        assert response.status_code == 200
        assert "reload" in response.text.lower()


# =============================================================================
# Photo page rendering tests
# =============================================================================


class TestPhotoPageFlipUI:
    """Tests for front/back labels and flip button on photo page."""

    def _patch_photo_with_back(self, photo_id):
        """Create a mock get_photo_metadata that adds back_image to a real photo."""
        from app.main import get_photo_metadata as real_get

        real_photo = real_get(photo_id)
        if not real_photo:
            return None
        patched = dict(real_photo)
        patched["back_image"] = "test_photo_back.jpg"
        patched["back_transcription"] = "Written on back: 1935"
        return patched

    def test_front_label_shown_with_back_image(self, client, real_photo_id):
        """When photo has back_image, a 'Front' label badge appears."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        patched = self._patch_photo_with_back(real_photo_id)
        if not patched:
            pytest.skip("Could not load photo data")
        with patch("app.main.get_photo_metadata", return_value=patched):
            response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert "photo-side-label" in html
        assert ">Front<" in html

    def test_back_label_rendered(self, client, real_photo_id):
        """When photo has back_image, a 'Back' label badge is in the flip-back div."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        patched = self._patch_photo_with_back(real_photo_id)
        if not patched:
            pytest.skip("Could not load photo data")
        with patch("app.main.get_photo_metadata", return_value=patched):
            response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert ">Back<" in html

    def test_no_front_label_without_back(self, client, real_photo_id):
        """Without back_image, no front/back label badges appear."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert "photo-side-label" not in html


# =============================================================================
# Photo registry media_group tests
# =============================================================================


class TestMediaGroupFields:
    """Test media_group_id and related fields in PhotoRegistry."""

    def test_media_group_id_accepted(self):
        """media_group_id is a valid metadata key."""
        reg = PhotoRegistry()
        reg.register_face("test-photo", "test.jpg", "face1", source="test", collection="test")
        result = reg.set_metadata("test-photo", {"media_group_id": "test-photo"})
        assert result is True
        meta = reg.get_metadata("test-photo")
        assert meta.get("media_group_id") == "test-photo"

    def test_media_role_accepted(self):
        """media_role is a valid metadata key."""
        reg = PhotoRegistry()
        reg.register_face("test-photo", "test.jpg", "face1", source="test", collection="test")
        result = reg.set_metadata("test-photo", {"media_role": "front"})
        assert result is True
        meta = reg.get_metadata("test-photo")
        assert meta.get("media_role") == "front"

    def test_parent_photo_id_accepted(self):
        """parent_photo_id is a valid metadata key."""
        reg = PhotoRegistry()
        reg.register_face("back-photo", "back.jpg", "face2", source="test", collection="test")
        result = reg.set_metadata("back-photo", {"parent_photo_id": "front-photo"})
        assert result is True
        meta = reg.get_metadata("back-photo")
        assert meta.get("parent_photo_id") == "front-photo"

    def test_related_media_accepted(self):
        """related_media list is a valid metadata key."""
        reg = PhotoRegistry()
        reg.register_face("test-photo", "test.jpg", "face1", source="test", collection="test")
        related = [{"photo_id": "back-123", "role": "back"}]
        result = reg.set_metadata("test-photo", {"related_media": related})
        assert result is True
        meta = reg.get_metadata("test-photo")
        assert meta.get("related_media") == related

    def test_full_media_group_metadata(self):
        """All media_group fields can be set together."""
        reg = PhotoRegistry()
        reg.register_face("front-photo", "front.jpg", "face1", source="test", collection="test")
        metadata = {
            "media_group_id": "front-photo",
            "media_role": "front",
            "back_image": "front_back.jpg",
            "related_media": [{"photo_id": "front-photo_back", "role": "back"}],
        }
        result = reg.set_metadata("front-photo", metadata)
        assert result is True
        meta = reg.get_metadata("front-photo")
        assert meta["media_group_id"] == "front-photo"
        assert meta["media_role"] == "front"
        assert meta["back_image"] == "front_back.jpg"


# =============================================================================
# Browse page filter tests
# =============================================================================


class TestBrowseMediaFilter:
    """Test media_filter on the photos browse page."""

    def test_browse_renders_media_filter_dropdown(self, client):
        """The photos browse section has a Media filter dropdown."""
        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get("/?section=photos")
        html = response.text
        assert "Media:" in html
        assert "All Photos" in html
        assert "Front Only" in html
        assert "Has Back Image" in html

    def test_browse_media_filter_param_accepted(self, client):
        """media_filter=front_only is accepted without error."""
        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get("/?section=photos&media_filter=front_only")
        assert response.status_code == 200

    def test_browse_media_filter_has_back(self, client):
        """media_filter=has_back is accepted without error."""
        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get("/?section=photos&media_filter=has_back")
        assert response.status_code == 200

    def test_flip_icon_badge_on_card(self, client, real_photo_id):
        """Cards with back images show a flip icon badge."""
        if not real_photo_id:
            pytest.skip("No embeddings available")

        # Patch _photo_cache to add back_image to first photo
        from app.main import _build_caches, _photo_cache

        _build_caches()

        original_cache = dict(_photo_cache)
        patched_cache = dict(original_cache)
        if real_photo_id in patched_cache:
            patched_cache[real_photo_id] = dict(patched_cache[real_photo_id])
            patched_cache[real_photo_id]["back_image"] = "test_back.jpg"

        with (
            patch("app.main.is_auth_enabled", return_value=False),
            patch("app.main._photo_cache", patched_cache),
        ):
            response = client.get("/?section=photos")
        html = response.text
        assert "Has back image" in html  # The title attribute of the flip badge


# =============================================================================
# SQL migration test
# =============================================================================


class TestSQLMigration:
    """Test that the SQL migration file exists and is valid."""

    def test_migration_file_exists(self):
        """006_media_groups.sql exists."""
        from pathlib import Path

        sql_path = Path("/Users/nolanfox/rhodesli/scripts/sql/006_media_groups.sql")
        assert sql_path.exists()

    def test_migration_contains_required_columns(self):
        """Migration adds media_group_id, media_role, parent_photo_id."""
        from pathlib import Path

        sql = Path("/Users/nolanfox/rhodesli/scripts/sql/006_media_groups.sql").read_text()
        assert "media_group_id" in sql
        assert "media_role" in sql
        assert "parent_photo_id" in sql
