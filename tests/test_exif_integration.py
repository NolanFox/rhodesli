"""
Tests for EXIF extraction integration with the ingestion pipeline.

Verifies that:
- process_single_image() stores EXIF metadata on photo records
- The camera field is accepted by PhotoRegistry.set_metadata()
- GPS coordinates are formatted as a location string
- EXIF extraction failures do not break ingestion
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestExifIntegrationInIngestion:
    """Tests that process_single_image() extracts and stores EXIF metadata."""

    def _make_data_dir(self, tmp_path):
        """Create minimal data directory structure for ingestion."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "inbox").mkdir()
        crops_dir = tmp_path / "crops"
        crops_dir.mkdir()

        # Create minimal photo_index.json
        photo_index_path = data_dir / "photo_index.json"
        photo_index_path.write_text(json.dumps({
            "schema_version": 1,
            "photos": {},
            "face_to_photo": {},
        }))

        # Create minimal identities.json
        identity_path = data_dir / "identities.json"
        identity_path.write_text(json.dumps({
            "schema_version": 1,
            "identities": {},
            "history": [],
        }))

        return data_dir, crops_dir

    @patch("core.ingest_inbox.extract_faces")
    @patch("core.ingest_inbox.generate_crop")
    @patch("core.embeddings_io.atomic_append_embeddings", new_callable=MagicMock)
    def test_exif_metadata_stored_on_photo(
        self, mock_append, mock_crop, mock_extract, tmp_path
    ):
        """process_single_image() should store EXIF date, camera, and GPS on the photo."""
        from core.ingest_inbox import process_single_image
        from core.photo_registry import PhotoRegistry

        data_dir, crops_dir = self._make_data_dir(tmp_path)

        # Mock face extraction to return one face
        mock_extract.return_value = [
            {
                "face_id": "face_001",
                "mu": [0.1] * 512,
                "sigma_sq": [0.5] * 512,
                "det_score": 0.95,
                "bbox": [10, 20, 100, 150],
                "filename": "test_photo.jpg",
                "filepath": str(tmp_path / "test_photo.jpg"),
            }
        ]
        mock_crop.return_value = "face_001.jpg"

        # Mock EXIF extraction to return rich metadata
        exif_return = {
            "date_taken": "1952-06-15 14:30:00",
            "camera": "Canon EOS 5D",
            "gps_lat": 36.4341,
            "gps_lon": 28.2176,
        }

        with patch("core.exif.extract_exif", return_value=exif_return) as mock_exif:
            result = process_single_image(
                filepath=tmp_path / "test_photo.jpg",
                job_id="exif_test_001",
                file_index=0,
                embeddings_path=data_dir / "embeddings.npy",
                photo_index_path=data_dir / "photo_index.json",
                identity_path=data_dir / "identities.json",
                crops_dir=crops_dir,
            )

        assert result["faces_extracted"] == 1
        mock_exif.assert_called_once_with(tmp_path / "test_photo.jpg")

        # Reload the photo registry and verify metadata was stored
        registry = PhotoRegistry.load(data_dir / "photo_index.json")
        photo_id = "inbox_exif_test_001_0_test_photo"
        metadata = registry.get_metadata(photo_id)

        assert metadata["date_taken"] == "1952-06-15 14:30:00"
        assert metadata["camera"] == "Canon EOS 5D"
        assert metadata["location"] == "36.4341, 28.2176"

    @patch("core.ingest_inbox.extract_faces")
    @patch("core.ingest_inbox.generate_crop")
    @patch("core.embeddings_io.atomic_append_embeddings", new_callable=MagicMock)
    def test_exif_with_only_date(
        self, mock_append, mock_crop, mock_extract, tmp_path
    ):
        """Only date_taken should be stored when camera and GPS are absent."""
        from core.ingest_inbox import process_single_image
        from core.photo_registry import PhotoRegistry

        data_dir, crops_dir = self._make_data_dir(tmp_path)

        mock_extract.return_value = [
            {
                "face_id": "face_002",
                "mu": [0.1] * 512,
                "sigma_sq": [0.5] * 512,
                "det_score": 0.95,
                "bbox": [10, 20, 100, 150],
                "filename": "old_photo.jpg",
                "filepath": str(tmp_path / "old_photo.jpg"),
            }
        ]
        mock_crop.return_value = "face_002.jpg"

        exif_return = {"date_taken": "1945-03-20"}

        with patch("core.exif.extract_exif", return_value=exif_return):
            process_single_image(
                filepath=tmp_path / "old_photo.jpg",
                job_id="exif_test_002",
                file_index=0,
                embeddings_path=data_dir / "embeddings.npy",
                photo_index_path=data_dir / "photo_index.json",
                identity_path=data_dir / "identities.json",
                crops_dir=crops_dir,
            )

        registry = PhotoRegistry.load(data_dir / "photo_index.json")
        photo_id = "inbox_exif_test_002_0_old_photo"
        metadata = registry.get_metadata(photo_id)

        assert metadata["date_taken"] == "1945-03-20"
        assert "camera" not in metadata
        assert "location" not in metadata

    @patch("core.ingest_inbox.extract_faces")
    @patch("core.ingest_inbox.generate_crop")
    @patch("core.embeddings_io.atomic_append_embeddings", new_callable=MagicMock)
    def test_exif_empty_does_not_save_metadata(
        self, mock_append, mock_crop, mock_extract, tmp_path
    ):
        """No metadata should be saved when extract_exif returns empty dict."""
        from core.ingest_inbox import process_single_image
        from core.photo_registry import PhotoRegistry

        data_dir, crops_dir = self._make_data_dir(tmp_path)

        mock_extract.return_value = [
            {
                "face_id": "face_003",
                "mu": [0.1] * 512,
                "sigma_sq": [0.5] * 512,
                "det_score": 0.95,
                "bbox": [10, 20, 100, 150],
                "filename": "no_exif.jpg",
                "filepath": str(tmp_path / "no_exif.jpg"),
            }
        ]
        mock_crop.return_value = "face_003.jpg"

        with patch("core.exif.extract_exif", return_value={}):
            process_single_image(
                filepath=tmp_path / "no_exif.jpg",
                job_id="exif_test_003",
                file_index=0,
                embeddings_path=data_dir / "embeddings.npy",
                photo_index_path=data_dir / "photo_index.json",
                identity_path=data_dir / "identities.json",
                crops_dir=crops_dir,
            )

        registry = PhotoRegistry.load(data_dir / "photo_index.json")
        photo_id = "inbox_exif_test_003_0_no_exif"
        metadata = registry.get_metadata(photo_id)

        # No EXIF fields should be present
        assert "date_taken" not in metadata
        assert "camera" not in metadata
        assert "location" not in metadata

    @patch("core.ingest_inbox.extract_faces")
    @patch("core.ingest_inbox.generate_crop")
    @patch("core.embeddings_io.atomic_append_embeddings", new_callable=MagicMock)
    def test_exif_failure_does_not_break_ingestion(
        self, mock_append, mock_crop, mock_extract, tmp_path
    ):
        """EXIF extraction errors should be silently caught; ingestion continues."""
        from core.ingest_inbox import process_single_image

        data_dir, crops_dir = self._make_data_dir(tmp_path)

        mock_extract.return_value = [
            {
                "face_id": "face_004",
                "mu": [0.1] * 512,
                "sigma_sq": [0.5] * 512,
                "det_score": 0.95,
                "bbox": [10, 20, 100, 150],
                "filename": "corrupt.jpg",
                "filepath": str(tmp_path / "corrupt.jpg"),
            }
        ]
        mock_crop.return_value = "face_004.jpg"

        with patch(
            "core.exif.extract_exif",
            side_effect=RuntimeError("PIL crashed"),
        ):
            result = process_single_image(
                filepath=tmp_path / "corrupt.jpg",
                job_id="exif_test_004",
                file_index=0,
                embeddings_path=data_dir / "embeddings.npy",
                photo_index_path=data_dir / "photo_index.json",
                identity_path=data_dir / "identities.json",
                crops_dir=crops_dir,
            )

        # Ingestion should still succeed
        assert result["faces_extracted"] == 1
        assert len(result["identity_ids"]) >= 1

    @patch("core.ingest_inbox.extract_faces")
    @patch("core.ingest_inbox.generate_crop")
    @patch("core.embeddings_io.atomic_append_embeddings", new_callable=MagicMock)
    def test_gps_without_lat_does_not_set_location(
        self, mock_append, mock_crop, mock_extract, tmp_path
    ):
        """If only gps_lat is present (no gps_lon), location should NOT be set."""
        from core.ingest_inbox import process_single_image
        from core.photo_registry import PhotoRegistry

        data_dir, crops_dir = self._make_data_dir(tmp_path)

        mock_extract.return_value = [
            {
                "face_id": "face_005",
                "mu": [0.1] * 512,
                "sigma_sq": [0.5] * 512,
                "det_score": 0.95,
                "bbox": [10, 20, 100, 150],
                "filename": "partial_gps.jpg",
                "filepath": str(tmp_path / "partial_gps.jpg"),
            }
        ]
        mock_crop.return_value = "face_005.jpg"

        # Only gps_lat, no gps_lon
        exif_return = {"gps_lat": 36.4341}

        with patch("core.exif.extract_exif", return_value=exif_return):
            process_single_image(
                filepath=tmp_path / "partial_gps.jpg",
                job_id="exif_test_005",
                file_index=0,
                embeddings_path=data_dir / "embeddings.npy",
                photo_index_path=data_dir / "photo_index.json",
                identity_path=data_dir / "identities.json",
                crops_dir=crops_dir,
            )

        registry = PhotoRegistry.load(data_dir / "photo_index.json")
        photo_id = "inbox_exif_test_005_0_partial_gps"
        metadata = registry.get_metadata(photo_id)

        assert "location" not in metadata


class TestCameraInPhotoRegistryAllowlist:
    """Tests that 'camera' is accepted by PhotoRegistry.set_metadata()."""

    def test_camera_field_accepted(self):
        """set_metadata() should accept and store the 'camera' field."""
        from core.photo_registry import PhotoRegistry

        registry = PhotoRegistry()
        registry.register_face("photo_001", "test.jpg", "face_001")

        result = registry.set_metadata("photo_001", {"camera": "Nikon F3"})

        assert result is True
        metadata = registry.get_metadata("photo_001")
        assert metadata["camera"] == "Nikon F3"

    def test_camera_field_persists_through_save_load(self, tmp_path):
        """Camera metadata should survive save/load cycle."""
        from core.photo_registry import PhotoRegistry

        registry = PhotoRegistry()
        registry.register_face("photo_001", "test.jpg", "face_001")
        registry.set_metadata("photo_001", {"camera": "Leica M6"})

        path = tmp_path / "photo_index.json"
        registry.save(path)

        loaded = PhotoRegistry.load(path)
        metadata = loaded.get_metadata("photo_001")
        assert metadata["camera"] == "Leica M6"

    def test_all_exif_fields_accepted_together(self):
        """set_metadata() should accept date_taken, camera, and location together."""
        from core.photo_registry import PhotoRegistry

        registry = PhotoRegistry()
        registry.register_face("photo_001", "test.jpg", "face_001")

        result = registry.set_metadata("photo_001", {
            "date_taken": "1950-01-01",
            "camera": "Hasselblad 500C",
            "location": "36.4341, 28.2176",
        })

        assert result is True
        metadata = registry.get_metadata("photo_001")
        assert metadata["date_taken"] == "1950-01-01"
        assert metadata["camera"] == "Hasselblad 500C"
        assert metadata["location"] == "36.4341, 28.2176"


class TestGpsLocationFormatting:
    """Tests for GPS coordinate to location string formatting."""

    def test_gps_formatted_as_comma_separated(self, tmp_path):
        """GPS lat/lon should be formatted as 'lat, lon' string."""
        from core.ingest_inbox import process_single_image
        from core.photo_registry import PhotoRegistry

        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "inbox").mkdir()
        crops_dir = tmp_path / "crops"
        crops_dir.mkdir()

        (data_dir / "photo_index.json").write_text(json.dumps({
            "schema_version": 1,
            "photos": {},
            "face_to_photo": {},
        }))
        (data_dir / "identities.json").write_text(json.dumps({
            "schema_version": 1,
            "identities": {},
            "history": [],
        }))

        with patch("core.ingest_inbox.extract_faces") as mock_extract, \
             patch("core.ingest_inbox.generate_crop") as mock_crop, \
             patch("core.embeddings_io.atomic_append_embeddings"):
            mock_extract.return_value = [
                {
                    "face_id": "face_gps",
                    "mu": [0.1] * 512,
                    "sigma_sq": [0.5] * 512,
                    "det_score": 0.95,
                    "bbox": [10, 20, 100, 150],
                    "filename": "gps_test.jpg",
                    "filepath": str(tmp_path / "gps_test.jpg"),
                }
            ]
            mock_crop.return_value = "face_gps.jpg"

            exif_return = {
                "gps_lat": -33.8688,
                "gps_lon": 151.2093,
            }

            with patch("core.exif.extract_exif", return_value=exif_return):
                process_single_image(
                    filepath=tmp_path / "gps_test.jpg",
                    job_id="gps_format_test",
                    file_index=0,
                    embeddings_path=data_dir / "embeddings.npy",
                    photo_index_path=data_dir / "photo_index.json",
                    identity_path=data_dir / "identities.json",
                    crops_dir=crops_dir,
                )

        registry = PhotoRegistry.load(data_dir / "photo_index.json")
        photo_id = "inbox_gps_format_test_0_gps_test"
        metadata = registry.get_metadata(photo_id)

        assert metadata["location"] == "-33.8688, 151.2093"
