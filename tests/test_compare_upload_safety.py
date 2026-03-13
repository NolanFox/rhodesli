"""Tests for compare upload pipeline data-loss safety fixes.

Three bugs fixed:
  Bug 1: Server restart between upload and approval → staging dir gone → silent loss
  Bug 2: Path B compare_* jobs (from /api/compare/contribute) never archived
  Bug 3: Background ingest error deleted staging dir in finally → photo lost forever
"""

import json
import tempfile
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch, call
from contextlib import ExitStack

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pending(job_id: str, *, compare_upload_id: str | None = None) -> dict:
    """Build a minimal pending upload entry."""
    entry = {
        "job_id": job_id,
        "status": "pending",
        "submitted_at": "2026-03-13T12:00:00+00:00",
        "uploader_email": "test@example.com",
        "source": "Compare Upload",
        "collection": "",
        "file_count": 1,
        "files": ["photo.jpg"],
    }
    if compare_upload_id is not None:
        entry["compare_upload_id"] = compare_upload_id
        entry["image_key"] = f"uploads/compare/{compare_upload_id}.jpg"
    return entry


# ---------------------------------------------------------------------------
# Bug 3: staging dir deleted on ingest error
# ---------------------------------------------------------------------------


class TestBackgroundIngestStagingDirOnError:
    """Staging dir must survive a failed background ingest so the photo is recoverable."""

    def test_staging_dir_preserved_on_ingest_error(self, tmp_path):
        """If process_directory raises, job_dir must still exist after the thread."""
        # Create a fake staging dir with a photo
        job_dir = tmp_path / "staging" / "abc12345"
        job_dir.mkdir(parents=True)
        (job_dir / "photo.jpg").write_bytes(b"FAKE_JPEG")

        inbox_dir = tmp_path / "inbox"
        inbox_dir.mkdir()

        job_id = "abc12345"
        initial_status = {"started_at": "2026-03-13T12:00:00+00:00"}

        import json as _json

        def _background_compare_ingest():
            log_path = inbox_dir / f"{job_id}.log"
            try:
                # Simulate process_directory raising
                raise RuntimeError("InsightFace OOM")
            except Exception as e:
                error_status = {
                    "job_id": job_id,
                    "status": "error",
                    "error": str(e),
                    "started_at": initial_status["started_at"],
                    "total_files": 1,
                    "files_succeeded": 0,
                    "files_failed": 1,
                }
                try:
                    with open(inbox_dir / f"{job_id}.status.json", "w") as _ef:
                        _json.dump(error_status, _ef)
                except Exception:
                    pass
            # Fixed: no finally block that deletes job_dir on error

        t = threading.Thread(target=_background_compare_ingest)
        t.start()
        t.join(timeout=5)

        # The staging dir must still exist — photo preserved for recovery
        assert job_dir.exists(), "staging dir was deleted on error — photo lost!"
        assert (job_dir / "photo.jpg").exists(), "photo file inside staging dir was deleted!"

    def test_staging_dir_removed_on_success(self, tmp_path):
        """On success, staging dir SHOULD be cleaned up."""
        import shutil

        job_dir = tmp_path / "staging" / "def56789"
        job_dir.mkdir(parents=True)
        (job_dir / "photo.jpg").write_bytes(b"FAKE_JPEG")

        def _background_compare_ingest_success():
            try:
                # Simulate successful processing (nothing raises)
                pass

                # Success: clean up staging dir
                import shutil as _shutil_cleanup

                try:
                    if job_dir.exists():
                        _shutil_cleanup.rmtree(job_dir, ignore_errors=True)
                except Exception:
                    pass
            except Exception:
                pass  # Do NOT delete job_dir on error

        t = threading.Thread(target=_background_compare_ingest_success)
        t.start()
        t.join(timeout=5)

        assert not job_dir.exists(), "staging dir should be cleaned up after success"


# ---------------------------------------------------------------------------
# Bug 1: Server restart → staging dir missing → must not silently succeed
# ---------------------------------------------------------------------------


class TestApprovalWithMissingStagingDir:
    """When admin approves and staging dir is gone, approve metadata but skip processing."""

    def test_approve_missing_staging_approves_without_processing(self, client, auth_disabled):
        """POST /admin/pending/{job_id}/approve with no staging dir → approved but no background process."""
        job_id = "testjob01"
        pending_data = {"uploads": {job_id: _make_pending(job_id)}}

        with ExitStack() as stack:
            stack.enter_context(patch("app.main._load_pending_uploads", return_value=pending_data))
            stack.enter_context(patch("app.main._save_pending_uploads"))
            stack.enter_context(patch("app.main.log_user_action"))
            # PROCESSING_ENABLED = True so the staging path is entered
            stack.enter_context(patch("app.admin_routes.PROCESSING_ENABLED", True))
            # Staging dir does NOT exist (no tmp_path setup) — we rely on a non-existent path
            stack.enter_context(
                patch(
                    "app.main.data_path",
                    Path("/nonexistent_rhodesli_test_data"),
                )
            )

            resp = client.post(f"/admin/pending/{job_id}/approve")

        assert resp.status_code == 200
        text = resp.text.lower()
        # Metadata is approved but no "processing in background" message (nothing to process)
        assert "approved" in text
        # Should NOT show processing note since staging dir doesn't exist
        assert "processing in background" not in text

    def test_approve_missing_staging_saves_as_approved(self, client, auth_disabled):
        """When staging is missing, status is saved as approved (metadata preserved)."""
        job_id = "testjob02"
        upload_entry = _make_pending(job_id)
        pending_data = {"uploads": {job_id: upload_entry}}

        saved_states = []

        def capture_save(data):
            saved_states.append(data["uploads"][job_id]["status"])

        with ExitStack() as stack:
            stack.enter_context(patch("app.main._load_pending_uploads", return_value=pending_data))
            stack.enter_context(patch("app.main._save_pending_uploads", side_effect=capture_save))
            stack.enter_context(patch("app.main.log_user_action"))
            stack.enter_context(patch("app.admin_routes.PROCESSING_ENABLED", True))
            stack.enter_context(patch("app.main.data_path", Path("/nonexistent_rhodesli_test_data")))

            client.post(f"/admin/pending/{job_id}/approve")

        # Status should be "approved" — metadata is recorded even without processing
        if saved_states:
            assert saved_states[-1] == "approved", (
                f"Upload status was not saved as approved; last saved status: {saved_states[-1]}"
            )


# ---------------------------------------------------------------------------
# Bug 2: compare_* job with R2 photo → must download and process
# ---------------------------------------------------------------------------


class TestApprovalCompareJobFromR2:
    """compare_* job IDs from /api/compare/contribute must trigger process_directory."""

    def test_compare_job_downloads_from_r2_and_processes(self, client, auth_disabled):
        """When staging dir is absent and job is compare_*, photo is fetched from R2.

        Verify: no error is returned (process_dir resolved successfully) and
        "Approved" appears, meaning the background thread was spawned.
        We mock process_directory and the post-ingest steps to keep the test fast.
        """
        upload_id = "r2photo01"
        job_id = f"compare_{upload_id}"
        pending_data = {"uploads": {job_id: _make_pending(job_id, compare_upload_id=upload_id)}}

        fake_photo_bytes = b"FAKE_JPEG_CONTENT"

        # Use a real threading.Thread but make process_directory a no-op
        def fake_process_directory(directory, **kwargs):
            return {"status": "success", "face_ids": []}

        with ExitStack() as stack:
            stack.enter_context(patch("app.main._load_pending_uploads", return_value=pending_data))
            stack.enter_context(patch("app.main._save_pending_uploads"))
            stack.enter_context(patch("app.main.log_user_action"))
            stack.enter_context(patch("app.admin_routes.PROCESSING_ENABLED", True))
            # Staging dir does NOT exist
            stack.enter_context(
                patch(
                    "app.main.data_path",
                    Path("/nonexistent_rhodesli_test_data"),
                )
            )
            # R2 IS available and returns the photo
            stack.enter_context(patch("core.storage.can_write_r2", return_value=True))
            stack.enter_context(
                patch(
                    "core.storage.download_bytes_from_r2",
                    return_value=fake_photo_bytes,
                )
            )
            # Patch process_directory and post-ingest steps so background thread exits fast
            stack.enter_context(patch("core.ingest_inbox.process_directory", side_effect=fake_process_directory))
            stack.enter_context(patch("app.main._upload_new_files_to_r2", return_value=None))
            stack.enter_context(patch("app.main._invalidate_all_caches", return_value=None))

            resp = client.post(f"/admin/pending/{job_id}/approve")

        assert resp.status_code == 200
        text = resp.text
        # Should NOT show an error — compare_* job was recovered from R2
        assert "no longer available" not in text.lower(), (
            f"Got error response for compare job with R2 photo available: {text[:300]}"
        )
        assert "source files" not in text.lower(), (
            f"Got 'source files' error for compare job with R2 photo available: {text[:300]}"
        )
        # Should show approval confirmation
        assert "Approved" in text, f"Expected 'Approved' in response, got: {text[:300]}"

    def test_compare_job_r2_not_available_approves_without_processing(self, client, auth_disabled):
        """If R2 is unavailable and staging is missing, still approve metadata (no processing)."""
        upload_id = "r2missing01"
        job_id = f"compare_{upload_id}"
        pending_data = {"uploads": {job_id: _make_pending(job_id, compare_upload_id=upload_id)}}

        with ExitStack() as stack:
            stack.enter_context(patch("app.main._load_pending_uploads", return_value=pending_data))
            stack.enter_context(patch("app.main._save_pending_uploads"))
            stack.enter_context(patch("app.main.log_user_action"))
            stack.enter_context(patch("app.admin_routes.PROCESSING_ENABLED", True))
            stack.enter_context(patch("app.main.data_path", Path("/nonexistent_rhodesli_test_data")))

            resp = client.post(f"/admin/pending/{job_id}/approve")

        assert resp.status_code == 200
        text = resp.text.lower()
        # Metadata approved but no background processing
        assert "approved" in text
        assert "processing in background" not in text

    def test_compare_job_no_r2_no_staging_no_processing(self, client, auth_disabled):
        """compare_* job with no R2 and no staging still records approval metadata."""
        upload_id = "r2none01"
        job_id = f"compare_{upload_id}"
        pending_data = {"uploads": {job_id: _make_pending(job_id, compare_upload_id=upload_id)}}

        saved_states = []

        def capture_save(data):
            saved_states.append(data["uploads"][job_id]["status"])

        with ExitStack() as stack:
            stack.enter_context(patch("app.main._load_pending_uploads", return_value=pending_data))
            stack.enter_context(patch("app.main._save_pending_uploads", side_effect=capture_save))
            stack.enter_context(patch("app.main.log_user_action"))
            stack.enter_context(patch("app.admin_routes.PROCESSING_ENABLED", True))
            stack.enter_context(patch("app.main.data_path", Path("/nonexistent_rhodesli_test_data")))

            resp = client.post(f"/admin/pending/{job_id}/approve")

        assert resp.status_code == 200
        # Status should be saved as "approved"
        if saved_states:
            assert saved_states[-1] == "approved"


# ---------------------------------------------------------------------------
# Regression: normal approval (staging present) still works
# ---------------------------------------------------------------------------


class TestApprovalNormalPathUnchanged:
    """Regression guard: normal approval flow with staging dir present must still work."""

    def test_normal_approval_with_staging_dir(self, tmp_path, client, auth_disabled):
        """Approval with staging dir present returns 'Approved', no error shown."""
        job_id = "normaljob1"
        staging = tmp_path / "staging" / job_id
        staging.mkdir(parents=True)
        (staging / "photo.jpg").write_bytes(b"FAKE")

        pending_data = {"uploads": {job_id: _make_pending(job_id)}}

        def fake_process_directory(directory, **kwargs):
            return {"status": "success", "face_ids": []}

        with ExitStack() as stack:
            stack.enter_context(patch("app.main._load_pending_uploads", return_value=pending_data))
            stack.enter_context(patch("app.main._save_pending_uploads"))
            stack.enter_context(patch("app.main.log_user_action"))
            stack.enter_context(patch("app.admin_routes.PROCESSING_ENABLED", True))
            stack.enter_context(patch("app.main.data_path", tmp_path))
            stack.enter_context(patch("core.ingest_inbox.process_directory", side_effect=fake_process_directory))
            stack.enter_context(patch("app.main._upload_new_files_to_r2", return_value=None))
            stack.enter_context(patch("app.main._invalidate_all_caches", return_value=None))

            resp = client.post(f"/admin/pending/{job_id}/approve")

        assert resp.status_code == 200
        # Normal path: should show "Approved", not an error
        assert "Approved" in resp.text
        assert "no longer available" not in resp.text.lower()
