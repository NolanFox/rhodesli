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

            # Mock the heavy processing
            with patch("core.ingest_inbox.extract_faces") as mock_extract:
                mock_extract.return_value = [
                    {
                        "face_id": "face_001",
                        "mu": [0.1] * 512,
                        "sigma_sq": [0.5] * 512,
                        "det_score": 0.95,
                        "bbox": [10, 20, 100, 150],
                        "filename": "test.jpg",
                        "filepath": str(tmpdir / "test.jpg"),
                    }
                ]

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
