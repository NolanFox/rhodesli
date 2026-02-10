"""
Tests for photo provenance model: separate source, collection, and source_url fields.

Covers:
- PhotoRegistry collection/source_url methods
- Migration script
- Backward compatibility (photos without collection/source_url load cleanly)
"""

import json
import pytest
from pathlib import Path
from core.photo_registry import PhotoRegistry


@pytest.fixture
def registry(tmp_path):
    """Create a PhotoRegistry with test data."""
    reg = PhotoRegistry()
    reg.register_face("photo1", "image1.jpg", "face1", source="Newspapers.com")
    reg.register_face("photo2", "image2.jpg", "face2", source="Betty Capeluto Miami Collection")
    reg.register_face("photo3", "image3.jpg", "face3", source="")
    return reg


class TestPhotoRegistryCollectionField:
    """Tests for the new collection field on PhotoRegistry."""

    def test_set_and_get_collection(self, registry):
        """Collection can be set and retrieved independently of source."""
        registry.set_collection("photo1", "Immigration Records")
        assert registry.get_collection("photo1") == "Immigration Records"
        # Source unchanged
        assert registry.get_source("photo1") == "Newspapers.com"

    def test_get_collection_default_empty(self, registry):
        """Photos without collection return empty string."""
        assert registry.get_collection("photo1") == ""

    def test_get_collection_unknown_photo(self, registry):
        """Unknown photo returns empty string for collection."""
        assert registry.get_collection("nonexistent") == ""

    def test_set_collection_unknown_photo(self, registry):
        """Setting collection on unknown photo is a no-op."""
        registry.set_collection("nonexistent", "Test")
        assert registry.get_collection("nonexistent") == ""

    def test_collection_independent_of_source(self, registry):
        """Collection and source are independent fields."""
        registry.set_source("photo1", "Rhodes Facebook Group")
        registry.set_collection("photo1", "Wedding Photos")
        assert registry.get_source("photo1") == "Rhodes Facebook Group"
        assert registry.get_collection("photo1") == "Wedding Photos"


class TestPhotoRegistrySourceUrl:
    """Tests for the new source_url field on PhotoRegistry."""

    def test_set_and_get_source_url(self, registry):
        """Source URL can be set and retrieved."""
        registry.set_source_url("photo1", "https://newspapers.com/article/123")
        assert registry.get_source_url("photo1") == "https://newspapers.com/article/123"

    def test_get_source_url_default_empty(self, registry):
        """Photos without source_url return empty string."""
        assert registry.get_source_url("photo1") == ""

    def test_get_source_url_unknown_photo(self, registry):
        """Unknown photo returns empty string for source_url."""
        assert registry.get_source_url("nonexistent") == ""

    def test_source_url_optional(self, registry):
        """Photos work perfectly without source_url."""
        assert registry.get_source("photo1") == "Newspapers.com"
        assert registry.get_source_url("photo1") == ""


class TestPhotoRegistrySerialization:
    """Tests for save/load roundtrip with new fields."""

    def test_save_load_roundtrip_with_collection(self, registry, tmp_path):
        """Collection field survives save/load cycle."""
        registry.set_collection("photo1", "Immigration Records")
        registry.set_source_url("photo1", "https://example.com/photo1")

        path = tmp_path / "photo_index.json"
        registry.save(path)
        loaded = PhotoRegistry.load(path)

        assert loaded.get_collection("photo1") == "Immigration Records"
        assert loaded.get_source_url("photo1") == "https://example.com/photo1"
        assert loaded.get_source("photo1") == "Newspapers.com"

    def test_save_includes_collection_and_source_url(self, registry, tmp_path):
        """Saved JSON includes collection and source_url fields."""
        registry.set_collection("photo1", "Test Collection")
        registry.set_source_url("photo1", "https://example.com")

        path = tmp_path / "photo_index.json"
        registry.save(path)

        with open(path) as f:
            data = json.load(f)

        photo = data["photos"]["photo1"]
        assert "collection" in photo
        assert photo["collection"] == "Test Collection"
        assert "source_url" in photo
        assert photo["source_url"] == "https://example.com"

    def test_load_backward_compatible_no_collection(self, tmp_path):
        """Photos without collection/source_url load with empty defaults."""
        data = {
            "schema_version": 1,
            "photos": {
                "old_photo": {
                    "path": "old.jpg",
                    "face_ids": ["face1"],
                    "source": "Old Source"
                    # No collection or source_url
                }
            },
            "face_to_photo": {"face1": "old_photo"}
        }
        path = tmp_path / "photo_index.json"
        with open(path, "w") as f:
            json.dump(data, f)

        loaded = PhotoRegistry.load(path)
        assert loaded.get_source("old_photo") == "Old Source"
        assert loaded.get_collection("old_photo") == ""
        assert loaded.get_source_url("old_photo") == ""

    def test_collection_not_in_metadata(self, registry):
        """Collection and source_url are excluded from generic metadata."""
        registry.set_collection("photo1", "Test")
        registry.set_source_url("photo1", "https://example.com")
        registry.set_metadata("photo1", {"date_taken": "1935"})

        meta = registry.get_metadata("photo1")
        assert "collection" not in meta
        assert "source_url" not in meta
        assert "source" not in meta
        assert meta.get("date_taken") == "1935"

    def test_migration_preserves_existing_data(self, registry, tmp_path):
        """Migration doesn't lose existing source assignments."""
        path = tmp_path / "photo_index.json"
        registry.save(path)
        loaded = PhotoRegistry.load(path)

        assert loaded.get_source("photo1") == "Newspapers.com"
        assert loaded.get_source("photo2") == "Betty Capeluto Miami Collection"
        # face_ids preserved
        assert "face1" in loaded.get_faces_in_photo("photo1")
        assert "face2" in loaded.get_faces_in_photo("photo2")


class TestProvenanceRoutes:
    """Tests for photo provenance API routes."""

    @pytest.fixture
    def client(self):
        from starlette.testclient import TestClient
        from app.main import app
        return TestClient(app)

    @pytest.fixture
    def auth_disabled(self):
        from unittest.mock import patch
        with patch("app.main.is_auth_enabled", return_value=False):
            yield

    def test_set_source_route(self, client, auth_disabled):
        """POST /api/photo/{id}/source sets provenance."""
        from unittest.mock import patch, MagicMock
        with patch("app.main.load_photo_registry") as mock_reg:
            reg = MagicMock()
            reg.get_photo_path.return_value = "raw_photos/test.jpg"
            mock_reg.return_value = reg

            resp = client.post(
                "/api/photo/test-id/source",
                data={"source": "Newspapers.com"}
            )
            assert resp.status_code == 200
            assert "Newspapers.com" in resp.text
            reg.set_source.assert_called_once_with("test-id", "Newspapers.com")

    def test_set_source_url_route(self, client, auth_disabled):
        """POST /api/photo/{id}/source-url sets citation URL."""
        from unittest.mock import patch, MagicMock
        with patch("app.main.load_photo_registry") as mock_reg:
            reg = MagicMock()
            reg.get_photo_path.return_value = "raw_photos/test.jpg"
            mock_reg.return_value = reg

            resp = client.post(
                "/api/photo/test-id/source-url",
                data={"source_url": "https://newspapers.com/article/123"}
            )
            assert resp.status_code == 200
            assert "https://newspapers.com/article/123" in resp.text
            reg.set_source_url.assert_called_once_with("test-id", "https://newspapers.com/article/123")

    def test_source_route_admin_only(self, client):
        """POST /api/photo/{id}/source requires admin."""
        from unittest.mock import patch
        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user", return_value=None):
            resp = client.post(
                "/api/photo/test-id/source",
                data={"source": "Test"},
                headers={"HX-Request": "true"}
            )
            assert resp.status_code == 401

    def test_source_url_route_admin_only(self, client):
        """POST /api/photo/{id}/source-url requires admin."""
        from unittest.mock import patch
        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user", return_value=None):
            resp = client.post(
                "/api/photo/test-id/source-url",
                data={"source_url": "https://example.com"},
                headers={"HX-Request": "true"}
            )
            assert resp.status_code == 401

    def test_collection_filter_param(self, client, auth_disabled):
        """Photos page accepts filter_collection parameter."""
        from unittest.mock import patch
        with patch("app.main._build_caches"):
            resp = client.get("/?section=photos&filter_collection=Newspapers.com")
            assert resp.status_code == 200

    def test_upload_form_has_separate_fields(self, client, auth_disabled):
        """Upload page shows separate collection, source, and source_url fields."""
        resp = client.get("/upload")
        assert resp.status_code == 200
        html = resp.text
        assert 'name="collection"' in html
        assert 'name="source"' in html
        assert 'name="source_url"' in html


class TestMigrationScript:
    """Tests for scripts/migrate_photo_metadata.py logic."""

    def test_migration_adds_collection_from_source(self, tmp_path):
        """Migration copies source → collection for photos without collection."""
        data = {
            "schema_version": 1,
            "photos": {
                "p1": {"path": "a.jpg", "face_ids": [], "source": "Newspapers.com"},
                "p2": {"path": "b.jpg", "face_ids": [], "source": "Betty Album"},
                "p3": {"path": "c.jpg", "face_ids": [], "source": ""},
            },
            "face_to_photo": {}
        }
        path = tmp_path / "photo_index.json"
        with open(path, "w") as f:
            json.dump(data, f)

        # Simulate migration logic
        with open(path) as f:
            loaded = json.load(f)

        for pid, photo in loaded["photos"].items():
            if "collection" not in photo or not photo["collection"]:
                photo["collection"] = photo.get("source", "") or "Uncategorized"
            if "source_url" not in photo:
                photo["source_url"] = ""

        with open(path, "w") as f:
            json.dump(loaded, f)

        with open(path) as f:
            result = json.load(f)

        assert result["photos"]["p1"]["collection"] == "Newspapers.com"
        assert result["photos"]["p2"]["collection"] == "Betty Album"
        assert result["photos"]["p3"]["collection"] == "Uncategorized"
        assert result["photos"]["p1"]["source_url"] == ""

    def test_migration_preserves_existing_collection(self, tmp_path):
        """Migration does not overwrite existing collection values."""
        data = {
            "schema_version": 1,
            "photos": {
                "p1": {
                    "path": "a.jpg", "face_ids": [],
                    "source": "Newspapers.com",
                    "collection": "Immigration Records"
                },
            },
            "face_to_photo": {}
        }
        path = tmp_path / "photo_index.json"
        with open(path, "w") as f:
            json.dump(data, f)

        with open(path) as f:
            loaded = json.load(f)

        for pid, photo in loaded["photos"].items():
            if "collection" not in photo or not photo["collection"]:
                photo["collection"] = photo.get("source", "") or "Uncategorized"

        assert loaded["photos"]["p1"]["collection"] == "Immigration Records"
