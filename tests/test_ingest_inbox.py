"""
Tests for inbox ingestion pipeline.

These tests verify the subprocess-based ingestion that processes uploaded
files and creates INBOX identities.

Note: Full integration tests require ML dependencies (insightface).
These tests mock the ML layer and focus on the data flow.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestProcessUploadedFile:
    """Tests for the main ingestion entry point."""

    def test_process_single_image_creates_status_file(self):
        """Processing should create a status file with results."""
        from core.ingest_inbox import process_uploaded_file

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create mock data directories
            data_dir = tmpdir / "data"
            inbox_dir = data_dir / "inbox"
            data_dir.mkdir()
            inbox_dir.mkdir()

            # Create mock status function
            job_id = "test_job_001"

            # Mock the heavy processing — extract_faces returns (faces, width, height)
            with patch("core.ingest_inbox.extract_faces") as mock_extract:
                mock_extract.return_value = (
                    [
                        {
                            "face_id": "face_001",
                            "mu": [0.1] * 512,
                            "sigma_sq": [0.5] * 512,
                            "det_score": 0.95,
                            "bbox": [10, 20, 100, 150],
                            "filename": "test.jpg",
                            "filepath": str(tmpdir / "test.jpg"),
                        }
                    ],
                    800,  # width
                    600,  # height
                )

                result = process_uploaded_file(
                    filepath=tmpdir / "test.jpg",
                    job_id=job_id,
                    data_dir=data_dir,
                )

            assert result["status"] == "success"
            assert result["faces_extracted"] == 1
            assert "identities_created" in result

            # Status file should exist
            status_path = inbox_dir / f"{job_id}.status.json"
            assert status_path.exists()

            with open(status_path) as f:
                status = json.load(f)
            assert status["status"] == "success"


    def test_process_single_image_stores_dimensions(self):
        """Processing should store image width/height in photo_index.json."""
        from core.ingest_inbox import process_uploaded_file

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            data_dir = tmpdir / "data"
            inbox_dir = data_dir / "inbox"
            data_dir.mkdir()
            inbox_dir.mkdir()

            job_id = "test_dims_001"

            with patch("core.ingest_inbox.extract_faces") as mock_extract:
                mock_extract.return_value = (
                    [
                        {
                            "face_id": "face_001",
                            "mu": [0.1] * 512,
                            "sigma_sq": [0.5] * 512,
                            "det_score": 0.95,
                            "bbox": [10, 20, 100, 150],
                            "filename": "test.jpg",
                            "filepath": str(tmpdir / "test.jpg"),
                        }
                    ],
                    1920,  # width
                    1080,  # height
                )

                result = process_uploaded_file(
                    filepath=tmpdir / "test.jpg",
                    job_id=job_id,
                    data_dir=data_dir,
                )

            assert result["status"] == "success"

            # Verify dimensions were written to photo_index.json
            photo_index_path = data_dir / "photo_index.json"
            with open(photo_index_path) as f:
                photo_data = json.load(f)

            photos = photo_data.get("photos", {})
            assert len(photos) > 0

            # Find the photo entry and check dimensions
            photo = list(photos.values())[0]
            assert photo["width"] == 1920
            assert photo["height"] == 1080


    def test_process_stores_relative_path_not_absolute(self):
        """Photo path in photo_index.json must be relative (raw_photos/file.jpg), never absolute."""
        from core.ingest_inbox import process_uploaded_file

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            data_dir = tmpdir / "data"
            inbox_dir = data_dir / "inbox"
            data_dir.mkdir()
            inbox_dir.mkdir()

            job_id = "test_relpath_001"

            with patch("core.ingest_inbox.extract_faces") as mock_extract:
                mock_extract.return_value = (
                    [
                        {
                            "face_id": "face_001",
                            "mu": [0.1] * 512,
                            "sigma_sq": [0.5] * 512,
                            "det_score": 0.95,
                            "bbox": [10, 20, 100, 150],
                            "filename": "Sarina2.jpg",
                            "filepath": str(tmpdir / "Sarina2.jpg"),
                        }
                    ],
                    1280,
                    852,
                )

                result = process_uploaded_file(
                    filepath=tmpdir / "Sarina2.jpg",
                    job_id=job_id,
                    data_dir=data_dir,
                )

            assert result["status"] == "success"

            # Verify path is relative, not absolute
            photo_index_path = data_dir / "photo_index.json"
            with open(photo_index_path) as f:
                photo_data = json.load(f)

            photo = list(photo_data["photos"].values())[0]
            assert photo["path"] == "raw_photos/Sarina2.jpg"
            assert not photo["path"].startswith("/"), "Path must not be absolute"


class TestCreateInboxIdentities:
    """Tests for INBOX identity creation from extracted faces."""

    def test_creates_inbox_identity_for_each_face(self):
        """Each extracted face should become an INBOX identity."""
        from core.ingest_inbox import create_inbox_identities
        from core.registry import IdentityRegistry, IdentityState

        registry = IdentityRegistry()

        faces = [
            {"face_id": "face_001", "mu": [0.1] * 512, "filename": "photo1.jpg"},
            {"face_id": "face_002", "mu": [0.2] * 512, "filename": "photo2.jpg"},
        ]

        identity_ids = create_inbox_identities(
            registry=registry,
            faces=faces,
            job_id="test_job",
        )

        assert len(identity_ids) == 2

        for identity_id in identity_ids:
            identity = registry.get_identity(identity_id)
            assert identity["state"] == IdentityState.INBOX.value
            assert identity["provenance"]["source"] == "inbox_ingest"
            assert identity["provenance"]["job_id"] == "test_job"

    def test_inbox_identities_have_face_as_anchor(self):
        """Each INBOX identity should have the face as its sole anchor."""
        from core.ingest_inbox import create_inbox_identities
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()

        faces = [{"face_id": "face_001", "mu": [0.1] * 512}]

        identity_ids = create_inbox_identities(
            registry=registry,
            faces=faces,
            job_id="test_job",
        )

        identity = registry.get_identity(identity_ids[0])
        assert identity["anchor_ids"] == ["face_001"]


class TestGenerateFaceId:
    """Tests for face ID generation."""

    def test_generate_face_id_is_deterministic(self):
        """Same inputs should produce the same face_id."""
        from core.ingest_inbox import generate_face_id

        face_id_1 = generate_face_id(
            filename="test.jpg",
            face_index=0,
            job_id="job123",
        )
        face_id_2 = generate_face_id(
            filename="test.jpg",
            face_index=0,
            job_id="job123",
        )

        assert face_id_1 == face_id_2

    def test_generate_face_id_differs_by_index(self):
        """Different face indices should produce different face_ids."""
        from core.ingest_inbox import generate_face_id

        face_id_1 = generate_face_id(
            filename="test.jpg",
            face_index=0,
            job_id="job123",
        )
        face_id_2 = generate_face_id(
            filename="test.jpg",
            face_index=1,
            job_id="job123",
        )

        assert face_id_1 != face_id_2


class TestPhotoRegistryDimensions:
    """Tests for PhotoRegistry.set_dimensions()."""

    def test_set_dimensions_on_existing_photo(self):
        """set_dimensions should store width/height on an existing photo."""
        from core.photo_registry import PhotoRegistry

        reg = PhotoRegistry()
        reg.register_face("photo_1", "raw_photos/test.jpg", "face_1")
        assert reg.set_dimensions("photo_1", 1920, 1080) is True

        # Verify via save/load round-trip
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "photo_index.json"
            reg.save(path)

            loaded = PhotoRegistry.load(path)
            photo = loaded._photos["photo_1"]
            assert photo["width"] == 1920
            assert photo["height"] == 1080

    def test_set_dimensions_on_unknown_photo(self):
        """set_dimensions should return False for unknown photos."""
        from core.photo_registry import PhotoRegistry

        reg = PhotoRegistry()
        assert reg.set_dimensions("nonexistent", 100, 100) is False

    def test_dimensions_survive_save_load(self):
        """Dimensions should persist through save/load cycle."""
        from core.photo_registry import PhotoRegistry

        reg = PhotoRegistry()
        reg.register_face("p1", "raw_photos/a.jpg", "f1")
        reg.register_face("p2", "raw_photos/b.jpg", "f2")
        reg.set_dimensions("p1", 800, 600)
        # p2 intentionally has no dimensions

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "photo_index.json"
            reg.save(path)
            loaded = PhotoRegistry.load(path)

            assert loaded._photos["p1"]["width"] == 800
            assert loaded._photos["p1"]["height"] == 600
            assert loaded._photos["p2"].get("width") is None


class TestBackfillDimensions:
    """Tests for the backfill_dimensions script."""

    def test_backfill_fixes_missing_dimensions(self):
        """Backfill should add width/height from local image files."""
        from PIL import Image

        from scripts.backfill_dimensions import backfill_dimensions

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create a small test image
            photos_dir = tmpdir / "raw_photos"
            photos_dir.mkdir()
            img = Image.new("RGB", (640, 480))
            img.save(photos_dir / "test_photo.jpg")

            # Create photo_index with missing dimensions
            photo_index = {
                "schema_version": 1,
                "photos": {
                    "photo_1": {
                        "path": "raw_photos/test_photo.jpg",
                        "face_ids": ["f1"],
                        "source": "",
                        "collection": "",
                        "source_url": "",
                    }
                },
                "face_to_photo": {"f1": "photo_1"},
            }
            index_path = tmpdir / "photo_index.json"
            with open(index_path, "w") as f:
                json.dump(photo_index, f)

            # Execute backfill
            fixed = backfill_dimensions(index_path, photos_dir, dry_run=False)
            assert fixed == 1

            # Verify dimensions were written
            with open(index_path) as f:
                data = json.load(f)
            assert data["photos"]["photo_1"]["width"] == 640
            assert data["photos"]["photo_1"]["height"] == 480

    def test_backfill_skips_photos_with_dimensions(self):
        """Backfill should not modify photos that already have dimensions."""
        from scripts.backfill_dimensions import backfill_dimensions

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            photos_dir = tmpdir / "raw_photos"
            photos_dir.mkdir()

            photo_index = {
                "schema_version": 1,
                "photos": {
                    "photo_1": {
                        "path": "raw_photos/existing.jpg",
                        "face_ids": ["f1"],
                        "source": "",
                        "collection": "",
                        "source_url": "",
                        "width": 1920,
                        "height": 1080,
                    }
                },
                "face_to_photo": {"f1": "photo_1"},
            }
            index_path = tmpdir / "photo_index.json"
            with open(index_path, "w") as f:
                json.dump(photo_index, f)

            fixed = backfill_dimensions(index_path, photos_dir, dry_run=False)
            assert fixed == 0

    def test_backfill_dry_run_does_not_modify(self):
        """Dry run should not write any changes."""
        from PIL import Image

        from scripts.backfill_dimensions import backfill_dimensions

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            photos_dir = tmpdir / "raw_photos"
            photos_dir.mkdir()
            img = Image.new("RGB", (640, 480))
            img.save(photos_dir / "test.jpg")

            photo_index = {
                "schema_version": 1,
                "photos": {
                    "p1": {
                        "path": "raw_photos/test.jpg",
                        "face_ids": ["f1"],
                        "source": "",
                        "collection": "",
                        "source_url": "",
                    }
                },
                "face_to_photo": {"f1": "p1"},
            }
            index_path = tmpdir / "photo_index.json"
            with open(index_path, "w") as f:
                json.dump(photo_index, f)

            fixed = backfill_dimensions(index_path, photos_dir, dry_run=True)
            assert fixed == 1

            # Verify file was NOT modified
            with open(index_path) as f:
                data = json.load(f)
            assert "width" not in data["photos"]["p1"]


class TestWriteStatusFile:
    """Tests for status file writing."""

    def test_write_status_creates_json_file(self):
        """Should create a JSON status file."""
        from core.ingest_inbox import write_status_file

        with tempfile.TemporaryDirectory() as tmpdir:
            inbox_dir = Path(tmpdir)

            write_status_file(
                inbox_dir=inbox_dir,
                job_id="test_job",
                status="processing",
                faces_extracted=0,
            )

            status_path = inbox_dir / "test_job.status.json"
            assert status_path.exists()

            with open(status_path) as f:
                status = json.load(f)

            assert status["job_id"] == "test_job"
            assert status["status"] == "processing"
