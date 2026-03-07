"""Tests for media group API endpoint and browse page media filter/badge.

Covers:
- GET /api/photo/{photo_id}/media-group returns correct structure
- Media group includes back image when present
- Media group returns front-only when no back
- 404 for invalid photo_id
- Browse /photos page has media filter dropdown
- Browse media_filter=has_back accepted
- Browse media_filter=front_only accepted
- Flip badge on browse cards with back images
- Front/Back label toggle test (labels present in flip HTML)
- SQL migration file alter_photos_media_group.sql exists
"""

import pytest
from pathlib import Path
from unittest.mock import patch
from starlette.testclient import TestClient

from app.main import app, load_embeddings_for_photos


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


FAKE_PHOTO = {
    "path": "test_photo.jpg",
    "filename": "test_photo.jpg",
    "media_group_id": "test-group-123",
    "media_role": "front",
    "back_image": "test_photo_back.jpg",
    "back_transcription": "Written on back: 1935",
}

FAKE_PHOTO_NO_BACK = {
    "path": "test_photo2.jpg",
    "filename": "test_photo2.jpg",
}


# =============================================================================
# Media Group API tests
# =============================================================================


class TestMediaGroupAPI:
    """Tests for GET /api/photo/{photo_id}/media-group endpoint."""

    def test_media_group_returns_correct_structure(self, client, real_photo_id):
        """Media group endpoint returns group_id and items list."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        with patch("app.photo_routes._main_mod.get_photo_metadata", return_value=FAKE_PHOTO):
            response = client.get(f"/api/photo/{real_photo_id}/media-group")
        assert response.status_code == 200
        data = response.json()
        assert "group_id" in data
        assert "items" in data
        assert isinstance(data["items"], list)
        assert len(data["items"]) == 2  # front + back

    def test_media_group_includes_back_image(self, client, real_photo_id):
        """When photo has back_image, items include a back entry."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        with patch("app.photo_routes._main_mod.get_photo_metadata", return_value=FAKE_PHOTO):
            response = client.get(f"/api/photo/{real_photo_id}/media-group")
        data = response.json()
        roles = [item["role"] for item in data["items"]]
        assert "front" in roles
        assert "back" in roles
        back_item = [item for item in data["items"] if item["role"] == "back"][0]
        assert back_item["photo_id"] == f"{real_photo_id}_back"
        assert "url" in back_item

    def test_media_group_front_only_without_back(self, client, real_photo_id):
        """When photo has no back_image, items contain only front."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        with patch("app.photo_routes._main_mod.get_photo_metadata", return_value=FAKE_PHOTO_NO_BACK):
            response = client.get(f"/api/photo/{real_photo_id}/media-group")
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["role"] == "front"

    def test_media_group_uses_photo_id_as_default_group(self, client, real_photo_id):
        """When no media_group_id, defaults to photo_id."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        with patch("app.photo_routes._main_mod.get_photo_metadata", return_value=FAKE_PHOTO_NO_BACK):
            response = client.get(f"/api/photo/{real_photo_id}/media-group")
        data = response.json()
        assert data["group_id"] == real_photo_id

    def test_media_group_uses_explicit_group_id(self, client, real_photo_id):
        """When media_group_id is set, it is used as group_id."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        with patch("app.photo_routes._main_mod.get_photo_metadata", return_value=FAKE_PHOTO):
            response = client.get(f"/api/photo/{real_photo_id}/media-group")
        data = response.json()
        assert data["group_id"] == "test-group-123"

    def test_media_group_404_for_missing_photo(self, client):
        """Nonexistent photo returns 404."""
        with patch("app.photo_routes._main_mod.get_photo_metadata", return_value=None):
            response = client.get("/api/photo/nonexistent123/media-group")
        assert response.status_code == 404


# =============================================================================
# Browse page media filter tests
# =============================================================================


class TestBrowseMediaFilter:
    """Tests for media filter on /photos browse page."""

    def test_photos_page_has_media_dropdown(self, client):
        """The /photos page has a Media filter dropdown."""
        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get("/photos")
        html = response.text
        assert "Media:" in html
        assert "All Photos" in html
        assert "Front Only" in html
        assert "Has Back Image" in html

    def test_media_filter_front_only_accepted(self, client):
        """media_filter=front_only is accepted without error."""
        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get("/photos?media_filter=front_only")
        assert response.status_code == 200

    def test_media_filter_has_back_accepted(self, client):
        """media_filter=has_back is accepted without error."""
        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get("/photos?media_filter=has_back")
        assert response.status_code == 200

    def test_media_filter_preserved_in_sort_urls(self, client):
        """media_filter value is preserved in sort/collection dropdown URLs."""
        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get("/photos?media_filter=has_back")
        html = response.text
        # The sort dropdown onChange URL should include media_filter
        assert "media_filter=has_back" in html


# =============================================================================
# Browse page flip badge tests
# =============================================================================


class TestBrowseFlipBadge:
    """Tests for flip icon badge on browse cards with back images."""

    def _make_synthetic_cache(self, with_back=False):
        """Build a synthetic _photo_cache for testing badge rendering."""
        cache = {
            "synth_photo_001": {
                "filename": "test_photo.jpg",
                "collection": "Test Collection",
                "source": "Test",
                "faces": [],
                "width": 800,
                "height": 600,
                "upload_date": "2026-01-01",
            }
        }
        if with_back:
            cache["synth_photo_001"]["back_image"] = "test_photo_back.jpg"
        return cache

    def test_flip_badge_on_card_with_back(self, client):
        """Cards with back images show a flip icon badge on /photos."""
        patched_cache = self._make_synthetic_cache(with_back=True)

        with (
            patch("app.main.is_auth_enabled", return_value=False),
            patch("app.main._photo_cache", patched_cache),
            patch("app.main._build_caches"),
        ):
            response = client.get("/photos")
        html = response.text
        assert "Has back image" in html  # title attribute of the badge

    def test_no_flip_badge_without_back(self, client):
        """Cards without back images do not show a flip icon badge."""
        patched_cache = self._make_synthetic_cache(with_back=False)

        with (
            patch("app.main.is_auth_enabled", return_value=False),
            patch("app.main._photo_cache", patched_cache),
            patch("app.main._build_caches"),
        ):
            response = client.get("/photos")
        html = response.text
        assert "Has back image" not in html


# =============================================================================
# Front/Back label tests
# =============================================================================


class TestFrontBackLabels:
    """Tests that Front/Back labels appear during flip."""

    def test_front_label_on_photo_with_back(self, client, real_photo_id):
        """Photo page shows 'Front' label when back image exists."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        from app.main import get_photo_metadata as real_get

        real_photo = real_get(real_photo_id)
        if not real_photo:
            pytest.skip("Could not load photo data")
        patched = dict(real_photo)
        patched["back_image"] = "test_photo_back.jpg"
        with patch("app.main.get_photo_metadata", return_value=patched):
            response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert "photo-side-label" in html
        assert ">Front<" in html

    def test_back_label_on_photo_with_back(self, client, real_photo_id):
        """Photo page shows 'Back' label in the flip-back div."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        from app.main import get_photo_metadata as real_get

        real_photo = real_get(real_photo_id)
        if not real_photo:
            pytest.skip("Could not load photo data")
        patched = dict(real_photo)
        patched["back_image"] = "test_photo_back.jpg"
        with patch("app.main.get_photo_metadata", return_value=patched):
            response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert ">Back<" in html

    def test_flip_button_toggles_text(self, client, real_photo_id):
        """Flip button JS toggles between 'Turn Over' and 'View Front'."""
        if not real_photo_id:
            pytest.skip("No embeddings available")
        from app.main import get_photo_metadata as real_get

        real_photo = real_get(real_photo_id)
        if not real_photo:
            pytest.skip("Could not load photo data")
        patched = dict(real_photo)
        patched["back_image"] = "test_photo_back.jpg"
        with patch("app.main.get_photo_metadata", return_value=patched):
            response = client.get(f"/photo/{real_photo_id}")
        html = response.text
        assert "Turn Over" in html
        assert "View Front" in html


# =============================================================================
# SQL migration tests
# =============================================================================


class TestSQLMigration:
    """Test that the SQL migration file exists and is valid."""

    def test_alter_migration_file_exists(self):
        """alter_photos_media_group.sql exists."""
        sql_path = Path(__file__).parent.parent / "scripts" / "sql" / "alter_photos_media_group.sql"
        assert sql_path.exists()

    def test_alter_migration_contains_required_columns(self):
        """Migration adds media_group_id, media_role, parent_photo_id, back_image, back_transcription."""
        sql_path = Path(__file__).parent.parent / "scripts" / "sql" / "alter_photos_media_group.sql"
        sql = sql_path.read_text()
        assert "media_group_id" in sql
        assert "media_role" in sql
        assert "parent_photo_id" in sql
        assert "back_image" in sql
        assert "back_transcription" in sql
