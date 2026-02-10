"""
Tests for photo metadata (BE-012) and EXIF extraction (BE-013).
"""

import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from starlette.testclient import TestClient
from fastcore.xml import to_xml


class TestPhotoRegistryMetadata:
    """BE-012: Photo metadata in PhotoRegistry."""

    def _make_registry(self, tmp_path):
        from core.photo_registry import PhotoRegistry
        data = {
            "schema_version": 1,
            "photos": {
                "photo-1": {
                    "path": "img1.jpg",
                    "face_ids": ["face-a"],
                    "source": "Test Collection",
                },
            },
            "face_to_photo": {"face-a": "photo-1"},
        }
        path = tmp_path / "photo_index.json"
        path.write_text(json.dumps(data))
        return PhotoRegistry.load(path), path

    def test_set_metadata_stores_fields(self, tmp_path):
        """set_metadata stores allowlisted fields on photo."""
        registry, _ = self._make_registry(tmp_path)
        result = registry.set_metadata("photo-1", {
            "date_taken": "circa 1945",
            "location": "Rhodes, Greece",
            "caption": "Family gathering",
        })
        assert result is True
        meta = registry.get_metadata("photo-1")
        assert meta["date_taken"] == "circa 1945"
        assert meta["location"] == "Rhodes, Greece"
        assert meta["caption"] == "Family gathering"

    def test_set_metadata_rejects_invalid_keys(self, tmp_path):
        """Invalid keys are silently ignored."""
        registry, _ = self._make_registry(tmp_path)
        registry.set_metadata("photo-1", {
            "date_taken": "1950",
            "invalid_key": "should_be_ignored",
        })
        meta = registry.get_metadata("photo-1")
        assert meta["date_taken"] == "1950"
        assert "invalid_key" not in meta

    def test_set_metadata_returns_false_for_unknown_photo(self, tmp_path):
        """set_metadata returns False for nonexistent photo."""
        registry, _ = self._make_registry(tmp_path)
        result = registry.set_metadata("nonexistent", {"caption": "test"})
        assert result is False

    def test_metadata_survives_save_load(self, tmp_path):
        """Metadata persists through save/load cycle."""
        registry, path = self._make_registry(tmp_path)
        registry.set_metadata("photo-1", {
            "date_taken": "1948-06-15",
            "occasion": "Wedding",
        })
        registry.save(path)

        from core.photo_registry import PhotoRegistry
        loaded = PhotoRegistry.load(path)
        meta = loaded.get_metadata("photo-1")
        assert meta["date_taken"] == "1948-06-15"
        assert meta["occasion"] == "Wedding"

    def test_get_metadata_excludes_structural_fields(self, tmp_path):
        """get_metadata does not return path, face_ids, source, width, height."""
        registry, _ = self._make_registry(tmp_path)
        meta = registry.get_metadata("photo-1")
        assert "path" not in meta
        assert "face_ids" not in meta
        assert "source" not in meta


class TestPhotoMetadataEndpoint:
    """Tests for POST /api/photo/{id}/metadata."""

    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    def test_photo_metadata_requires_admin(self, client):
        """Only admins can set photo metadata."""
        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user", return_value=None):
            response = client.post(
                "/api/photo/fake-id/metadata",
                data={"caption": "Test"}
            )
            assert response.status_code in (401, 403)

    def test_photo_metadata_update_success(self, client):
        """Admin can update photo metadata."""
        # Get a real photo ID from the system
        from app.main import get_photo_metadata, _build_caches, _photo_cache
        _build_caches()
        if not _photo_cache:
            pytest.skip("No photos available for testing")

        test_id = list(_photo_cache.keys())[0]

        with patch("app.main.save_photo_registry"):
            response = client.post(
                f"/api/photo/{test_id}/metadata",
                data={"caption": "Test caption"}
            )
            assert response.status_code == 200


class TestPhotoMetadataDisplay:
    """Tests for _photo_metadata_display helper."""

    def test_displays_metadata_fields(self):
        """Metadata fields render with correct labels."""
        from app.main import _photo_metadata_display

        photo = {
            "date_taken": "circa 1945",
            "location": "Rhodes, Greece",
            "caption": "Family at the beach",
        }
        html = to_xml(_photo_metadata_display(photo))
        assert "Date" in html
        assert "circa 1945" in html
        assert "Location" in html
        assert "Rhodes, Greece" in html
        assert "Caption" in html
        assert "Family at the beach" in html

    def test_empty_when_no_metadata(self):
        """Returns empty span when no metadata fields present."""
        from app.main import _photo_metadata_display

        photo = {"filename": "img.jpg", "faces": []}
        html = to_xml(_photo_metadata_display(photo))
        assert "Date" not in html
        assert "Location" not in html


class TestExifExtraction:
    """BE-013: EXIF extraction utility."""

    def test_extract_exif_returns_empty_for_nonexistent(self, tmp_path):
        """Returns empty dict for nonexistent file."""
        from core.exif import extract_exif
        result = extract_exif(tmp_path / "nonexistent.jpg")
        assert result == {}

    def test_extract_exif_date_format(self):
        """EXIF dates are converted from colon to dash format."""
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("PIL not available")

        from core.exif import extract_exif

        mock_img = MagicMock()
        mock_img._getexif.return_value = {
            36867: "2026:02:10 14:30:00",  # DateTimeOriginal
        }

        with patch("PIL.Image.open", return_value=mock_img):
            result = extract_exif("/fake/path.jpg")
            assert result.get("date_taken") == "2026-02-10 14:30:00"

    def test_gps_conversion(self):
        """GPS coordinates convert from DMS to decimal correctly."""
        from core.exif import _convert_gps

        # 36.4041 N (Rhodes, Greece)
        lat = _convert_gps((36, 24, 14.76), "N")
        assert lat is not None
        assert abs(lat - 36.4041) < 0.001

        # 28.2242 E (Rhodes, Greece)
        lon = _convert_gps((28, 13, 27.12), "E")
        assert lon is not None
        assert abs(lon - 28.2242) < 0.001

    def test_gps_south_west_negative(self):
        """South and West GPS refs produce negative values."""
        from core.exif import _convert_gps

        lat = _convert_gps((33, 51, 54.0), "S")
        assert lat is not None
        assert lat < 0

        lon = _convert_gps((151, 12, 36.0), "W")
        assert lon is not None
        assert lon < 0

    def test_gps_handles_none(self):
        """GPS conversion handles None gracefully."""
        from core.exif import _convert_gps
        assert _convert_gps(None, "N") is None
        assert _convert_gps((36, 24, 14), None) is None
