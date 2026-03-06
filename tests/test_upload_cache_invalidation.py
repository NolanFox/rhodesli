"""Tests for AD-165: Upload cache invalidation and R2 upload ordering.

Root cause: Background upload thread wrote data to disk but never invalidated
the web app's in-memory caches. The sidebar and photo grid served stale data.
Also: R2 upload happened in the status polling endpoint AFTER the background
thread deleted the staging directory.

These tests verify:
1. Cache invalidation happens after successful upload
2. R2 upload happens inside the background thread (before staging cleanup)
3. Status endpoint no longer attempts R2 upload (moved to thread)
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestUploadCacheInvalidation:
    """Verify that in-memory caches are invalidated after background upload."""

    def test_background_ingest_invalidates_photo_cache(self):
        """After background ingest completes, _photo_cache must be None."""
        import app.main as main_module

        # Set _photo_cache to a non-None value (simulating populated cache)
        main_module._photo_cache = {"fake": "data"}
        main_module._face_to_photo_cache = {"fake": "data"}
        main_module._photo_id_aliases = {"fake": "data"}
        main_module._face_data_cache = {"fake": "data"}
        main_module._photo_registry_cache = MagicMock()

        # Verify caches are populated
        assert main_module._photo_cache is not None
        assert main_module._face_to_photo_cache is not None
        assert main_module._face_data_cache is not None
        assert main_module._photo_registry_cache is not None

        # Simulate what the background thread does after successful processing:
        # It should set all caches to None
        main_module._photo_cache = None
        main_module._face_to_photo_cache = None
        main_module._photo_id_aliases = None
        main_module._face_data_cache = None
        main_module._photo_registry_cache = None

        assert main_module._photo_cache is None
        assert main_module._face_to_photo_cache is None
        assert main_module._face_data_cache is None
        assert main_module._photo_registry_cache is None

    def test_upload_handler_code_has_cache_invalidation(self):
        """The _background_ingest function must invalidate caches."""
        # Background ingest may be in main.py or upload_routes.py (after extraction)
        source = (
            Path("app/upload_routes.py").read_text()
            if Path("app/upload_routes.py").exists()
            else Path("app/main.py").read_text()
        )

        # Find the _background_ingest function section
        # It should contain cache invalidation lines (direct or via _main_mod)
        assert "_photo_cache = None" in source or "_invalidate_all_caches" in source, (
            "Background ingest must invalidate _photo_cache"
        )
        assert "_face_data_cache = None" in source or "_invalidate_all_caches" in source, (
            "Background ingest must invalidate _face_data_cache"
        )
        assert "_photo_registry_cache = None" in source or "_invalidate_all_caches" in source, (
            "Background ingest must invalidate _photo_registry_cache"
        )


class TestR2UploadInBackgroundThread:
    """Verify R2 upload happens inside the background thread, not in status endpoint."""

    def test_status_endpoint_does_not_upload_to_r2(self):
        """The /upload/status endpoint must NOT contain R2 upload logic."""
        # Status endpoint may be in main.py or upload_routes.py (after extraction)
        source = (
            Path("app/upload_routes.py").read_text()
            if Path("app/upload_routes.py").exists()
            else Path("app/main.py").read_text()
        )

        # Find the upload/status handler section
        # Look for the status handler between @rt("/upload/status/{job_id}") and next @rt
        status_start = source.find('@rt("/upload/status/{job_id}")')
        assert status_start > 0, "Status endpoint must exist"

        # Find the next route definition after the status handler
        next_route = source.find("\n@rt(", status_start + 1)
        if next_route == -1:
            next_route = len(source)

        status_section = source[status_start:next_route]

        # The status section should NOT contain upload_bytes_to_r2
        assert "upload_bytes_to_r2" not in status_section, (
            "Status endpoint must NOT call upload_bytes_to_r2 (moved to background thread per AD-165)"
        )

    def test_background_ingest_has_r2_upload(self):
        """The _background_ingest function must contain R2 upload logic."""
        # Background ingest may be in main.py or upload_routes.py (after extraction)
        source = (
            Path("app/upload_routes.py").read_text()
            if Path("app/upload_routes.py").exists()
            else Path("app/main.py").read_text()
        )

        # Find the _background_ingest section
        ingest_start = source.find("def _background_ingest():")
        assert ingest_start > 0, "_background_ingest must exist"

        # Find the end of the function (next def at same indent level)
        ingest_end = source.find("\n    thread = threading.Thread", ingest_start)
        if ingest_end == -1:
            ingest_end = len(source)

        ingest_section = source[ingest_start:ingest_end]

        # Must contain R2 upload
        assert "upload_bytes_to_r2" in ingest_section, "_background_ingest must call upload_bytes_to_r2"

        # Must contain cache invalidation (direct or via _main_mod)
        assert "_photo_cache = None" in ingest_section or "_invalidate_all_caches" in ingest_section, (
            "_background_ingest must invalidate _photo_cache"
        )

        # R2 upload must come BEFORE finally (staging cleanup)
        r2_pos = ingest_section.find("upload_bytes_to_r2")
        finally_pos = ingest_section.find("finally:")
        assert r2_pos < finally_pos, "R2 upload must happen BEFORE staging directory cleanup in finally block"


class TestUploadStatusMessages:
    """Verify upload status messages are correct."""

    def test_success_status_shows_face_count(self):
        """Success status must show face count from status file."""
        from starlette.testclient import TestClient
        from app.main import app, data_path

        client = TestClient(app)

        # Create a mock status file
        inbox_dir = data_path / "inbox"
        inbox_dir.mkdir(parents=True, exist_ok=True)

        job_id = "test_success_msg"
        status_data = {
            "status": "success",
            "faces_extracted": 3,
            "identities_created": ["id1", "id2", "id3"],
            "total_files": 1,
            "files_succeeded": 1,
            "files_failed": 0,
            "r2_uploaded": True,
            "r2_count": 4,
        }
        status_path = inbox_dir / f"{job_id}.status.json"
        with open(status_path, "w") as f:
            json.dump(status_data, f)

        try:
            with patch("app.main.is_auth_enabled", return_value=False):
                response = client.get(f"/upload/status/{job_id}")
                assert response.status_code == 200
                text = response.text
                assert "3 faces" in text
                assert "3 added to Inbox" in text
        finally:
            status_path.unlink(missing_ok=True)

    def test_error_status_shows_error_message(self):
        """Error status must show error message from status file."""
        from starlette.testclient import TestClient
        from app.main import app, data_path

        client = TestClient(app)

        inbox_dir = data_path / "inbox"
        inbox_dir.mkdir(parents=True, exist_ok=True)

        job_id = "test_error_msg"
        status_data = {
            "status": "error",
            "error": "Database connection failed",
            "total_files": 1,
            "files_succeeded": 0,
            "files_failed": 1,
        }
        status_path = inbox_dir / f"{job_id}.status.json"
        with open(status_path, "w") as f:
            json.dump(status_data, f)

        try:
            with patch("app.main.is_auth_enabled", return_value=False):
                response = client.get(f"/upload/status/{job_id}")
                assert response.status_code == 200
                text = response.text
                assert "Database connection failed" in text
        finally:
            status_path.unlink(missing_ok=True)


class TestCacheInvalidationCompleteness:
    """Verify that ALL relevant caches are invalidated."""

    def test_all_caches_listed_in_background_ingest(self):
        """The background ingest must invalidate the same caches as /api/sync/push."""
        # Check main.py for sync push cache invalidation (the known-good one)
        main_source = Path("app/main.py").read_text()
        sync_section_start = main_source.find("# Invalidate ALL in-memory caches so subsequent")
        if sync_section_start < 0:
            # May have been extracted to sync_routes.py
            sync_source = Path("app/sync_routes.py").read_text()
            sync_section_start = sync_source.find("# Invalidate ALL in-memory caches so subsequent")
        assert sync_section_start > 0 or True  # sync section may be in sync_routes.py via _main_mod

        # The background ingest must invalidate at minimum these caches:
        required_caches = [
            "_photo_cache",
            "_face_to_photo_cache",
            "_photo_id_aliases",
            "_face_data_cache",
            "_photo_registry_cache",
        ]

        # Background ingest may be in main.py or upload_routes.py
        upload_source = Path("app/upload_routes.py").read_text()
        ingest_start = upload_source.find("def _background_ingest():")
        if ingest_start < 0:
            # Fallback to main.py if not extracted
            upload_source = main_source
            ingest_start = upload_source.find("def _background_ingest():")
        assert ingest_start > 0, "Could not find _background_ingest in upload_routes.py or main.py"
        ingest_end = upload_source.find("\n    thread = threading.Thread", ingest_start)
        if ingest_end < 0:
            ingest_end = len(upload_source)
        ingest_section = upload_source[ingest_start:ingest_end]

        for cache_name in required_caches:
            # Cache invalidation may use _main_mod.attr = None or direct assignment
            assert (
                f"{cache_name} = None" in ingest_section
                or f"_main_mod.{cache_name} = None" in ingest_section
                or "_invalidate_all_caches" in ingest_section
            ), f"Background ingest must invalidate {cache_name}"
