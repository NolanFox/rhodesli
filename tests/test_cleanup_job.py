"""
Tests for the job cleanup script.

These tests verify that cleanup_job can surgically remove
artifacts from a specific job without affecting other data.
"""

import json
import tempfile
from pathlib import Path

import pytest


def create_test_identity(registry, job_id: str, face_id: str):
    """Helper to create an identity with provenance."""
    from core.registry import IdentityState

    return registry.create_identity(
        anchor_ids=[face_id],
        user_source="ingest_pipeline",
        state=IdentityState.INBOX,
        provenance={
            "job_id": job_id,
            "source": "inbox_ingest",
            "filename": f"{face_id}.jpg",
        },
    )


class TestCleanupDryRun:
    """Tests for dry-run mode (preview only)."""

    def test_dry_run_makes_no_changes(self):
        """Dry run should report changes but not execute them."""
        from scripts.cleanup_job import cleanup_job
        from core.registry import IdentityRegistry, IdentityState

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            data_dir = tmpdir / "data"
            crops_dir = tmpdir / "crops"
            data_dir.mkdir()
            crops_dir.mkdir()

            # Create registry with job artifacts
            registry = IdentityRegistry()
            identity_id = create_test_identity(registry, "job_a", "face_001")
            registry.save(data_dir / "identities.json")

            # Create a crop file
            (crops_dir / "face_001.jpg").write_bytes(b"fake crop")

            # Run dry-run cleanup
            summary = cleanup_job(
                job_id="job_a",
                data_dir=data_dir,
                crops_dir=crops_dir,
                dry_run=True,
            )

            # Verify changes were reported
            assert len(summary["identities_removed"]) == 1
            assert "face_001" in summary["face_ids_orphaned"]

            # Verify nothing was actually deleted
            loaded_registry = IdentityRegistry.load(data_dir / "identities.json")
            assert loaded_registry.get_identity(identity_id) is not None
            assert (crops_dir / "face_001.jpg").exists()


class TestCleanupExecution:
    """Tests for execute mode (actual cleanup)."""

    def test_cleanup_removes_only_target_job(self):
        """Cleanup should only affect the specified job_id."""
        from scripts.cleanup_job import cleanup_job
        from core.registry import IdentityRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            data_dir = tmpdir / "data"
            crops_dir = tmpdir / "crops"
            data_dir.mkdir()
            crops_dir.mkdir()

            # Create registry with artifacts from two jobs
            registry = IdentityRegistry()
            id_job_a = create_test_identity(registry, "job_a", "face_a1")
            id_job_b = create_test_identity(registry, "job_b", "face_b1")
            registry.save(data_dir / "identities.json")

            # Create crop files
            (crops_dir / "face_a1.jpg").write_bytes(b"crop a")
            (crops_dir / "face_b1.jpg").write_bytes(b"crop b")

            # Cleanup job_a
            summary = cleanup_job(
                job_id="job_a",
                data_dir=data_dir,
                crops_dir=crops_dir,
                dry_run=False,
            )

            # Verify job_a artifacts removed
            assert len(summary["identities_removed"]) == 1
            assert id_job_a in summary["identities_removed"]
            assert not (crops_dir / "face_a1.jpg").exists()

            # Verify job_b artifacts intact
            loaded_registry = IdentityRegistry.load(data_dir / "identities.json")
            assert loaded_registry.get_identity(id_job_b) is not None
            assert (crops_dir / "face_b1.jpg").exists()

    def test_cleanup_creates_backup(self):
        """Execute mode should create backup before deletion."""
        from scripts.cleanup_job import cleanup_job
        from core.registry import IdentityRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            data_dir = tmpdir / "data"
            crops_dir = tmpdir / "crops"
            data_dir.mkdir()
            crops_dir.mkdir()

            # Create registry with job artifacts
            registry = IdentityRegistry()
            create_test_identity(registry, "job_a", "face_001")
            registry.save(data_dir / "identities.json")

            # Run cleanup
            summary = cleanup_job(
                job_id="job_a",
                data_dir=data_dir,
                crops_dir=crops_dir,
                dry_run=False,
            )

            # Verify backup was created
            assert summary["backup_path"] is not None
            backup_path = Path(summary["backup_path"])
            assert backup_path.exists()
            assert (backup_path / "identities.json").exists()

    def test_cleanup_orphans_embeddings(self):
        """Face IDs should be added to orphaned_face_ids.json."""
        from scripts.cleanup_job import cleanup_job
        from core.registry import IdentityRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            data_dir = tmpdir / "data"
            crops_dir = tmpdir / "crops"
            data_dir.mkdir()
            crops_dir.mkdir()

            # Create registry with job artifacts
            registry = IdentityRegistry()
            create_test_identity(registry, "job_a", "face_001")
            create_test_identity(registry, "job_a", "face_002")
            registry.save(data_dir / "identities.json")

            # Run cleanup
            summary = cleanup_job(
                job_id="job_a",
                data_dir=data_dir,
                crops_dir=crops_dir,
                dry_run=False,
            )

            # Verify orphaned_face_ids.json was created
            orphan_path = data_dir / "orphaned_face_ids.json"
            assert orphan_path.exists()

            with open(orphan_path) as f:
                orphan_data = json.load(f)

            assert "face_001" in orphan_data["orphaned_face_ids"]
            assert "face_002" in orphan_data["orphaned_face_ids"]


class TestCleanupIdempotency:
    """Tests for cleanup idempotency."""

    def test_idempotent_cleanup(self):
        """Running cleanup twice should be safe."""
        from scripts.cleanup_job import cleanup_job
        from core.registry import IdentityRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            data_dir = tmpdir / "data"
            crops_dir = tmpdir / "crops"
            data_dir.mkdir()
            crops_dir.mkdir()

            # Create registry with job artifacts
            registry = IdentityRegistry()
            create_test_identity(registry, "job_a", "face_001")
            registry.save(data_dir / "identities.json")

            # Run cleanup once
            summary1 = cleanup_job(
                job_id="job_a",
                data_dir=data_dir,
                crops_dir=crops_dir,
                dry_run=False,
            )

            # Run cleanup again (should not error)
            summary2 = cleanup_job(
                job_id="job_a",
                data_dir=data_dir,
                crops_dir=crops_dir,
                dry_run=False,
            )

            # Second run should find nothing to clean
            assert len(summary2["identities_removed"]) == 0
            assert len(summary2["face_ids_orphaned"]) == 0


class TestCleanupPhotoRegistry:
    """Tests for photo registry cleanup."""

    def test_cleanup_removes_photo_registry_entries(self):
        """Cleanup should remove photo registry entries for the job."""
        from scripts.cleanup_job import cleanup_job
        from core.registry import IdentityRegistry
        from core.photo_registry import PhotoRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            data_dir = tmpdir / "data"
            crops_dir = tmpdir / "crops"
            data_dir.mkdir()
            crops_dir.mkdir()

            # Create identity registry
            registry = IdentityRegistry()
            create_test_identity(registry, "job_a", "face_001")
            registry.save(data_dir / "identities.json")

            # Create photo registry
            photo_registry = PhotoRegistry()
            photo_registry.register_face("photo_001", "/path/to/photo.jpg", "face_001")
            photo_registry.save(data_dir / "photo_index.json")

            # Run cleanup
            summary = cleanup_job(
                job_id="job_a",
                data_dir=data_dir,
                crops_dir=crops_dir,
                dry_run=False,
            )

            # Verify photo registry entry was removed
            loaded_photo_registry = PhotoRegistry.load(data_dir / "photo_index.json")
            assert loaded_photo_registry.get_photo_for_face("face_001") is None


class TestCleanupFileHashRegistry:
    """Tests for file hash registry cleanup."""

    def test_cleanup_removes_file_hash_entries(self):
        """Cleanup should remove file hash entries for the job."""
        from scripts.cleanup_job import cleanup_job
        from core.registry import IdentityRegistry
        from core.file_hash_registry import FileHashRegistry

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            data_dir = tmpdir / "data"
            crops_dir = tmpdir / "crops"
            data_dir.mkdir()
            crops_dir.mkdir()

            # Create identity registry
            registry = IdentityRegistry()
            create_test_identity(registry, "job_a", "face_001")
            registry.save(data_dir / "identities.json")

            # Create file hash registry
            hash_registry = FileHashRegistry()
            hash_registry.register_file("hash_abc123", ["face_001"], "job_a", "photo.jpg")
            hash_registry.save(data_dir / "file_hashes.json")

            # Run cleanup
            summary = cleanup_job(
                job_id="job_a",
                data_dir=data_dir,
                crops_dir=crops_dir,
                dry_run=False,
            )

            # Verify hash entry was removed
            loaded_hash_registry = FileHashRegistry.load(data_dir / "file_hashes.json")
            assert loaded_hash_registry.lookup("hash_abc123") is None
            assert "hash_abc123" in summary["file_hashes_removed"]
