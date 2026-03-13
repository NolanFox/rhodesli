"""Tests for pending approval workflow fixes.

Covers:
- Issue 1: Photos appear in browse after approval (HTMX response has correct id)
- Issue 2: Approval status updates immediately (returned Div has card id)
- Issue 3: Auto-confirm identities on approve
- Issue 4: Approve handler returns immediately (processing in background)
- Issue 5: Batch approve endpoint
- Issue 6: Staged uploads can also be approved (not just "pending" ones)
- Regression: logger defined in admin_routes (was missing, caused NameError in reject)
"""

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_pending_upload(job_id: str, status: str = "pending", **extra) -> dict:
    return {
        "job_id": job_id,
        "uploader_email": f"user+{job_id}@example.com",
        "source": "Test Source",
        "collection": "Test Collection",
        "files": ["photo1.jpg"],
        "file_count": 1,
        "submitted_at": "2026-03-01T00:00:00+00:00",
        "status": status,
        **extra,
    }


# ---------------------------------------------------------------------------
# Issue 2: HTMX outerHTML swap — returned Div must carry card id
# ---------------------------------------------------------------------------


class TestApproveResponseHasCardId:
    """After approving, the returned HTML fragment must contain the card id so
    HTMX ``hx_swap='outerHTML'`` replaces the correct element."""

    def test_approve_response_contains_card_id(self, client, auth_enabled, admin_user, tmp_path):
        """Approve response has id=pending-card-{job_id} for HTMX outerHTML swap."""
        with (
            patch("app.main.data_path", tmp_path),
            patch("app.admin_routes._main_mod.data_path", tmp_path),
            patch("app.main.PROCESSING_ENABLED", False),
            patch("app.admin_routes.PROCESSING_ENABLED", False),
        ):
            from app.main import _save_pending_uploads

            _save_pending_uploads({"uploads": {"jobA": _make_pending_upload("jobA")}})

            response = client.post("/admin/pending/jobA/approve")
            assert response.status_code == 200
            assert "Approved" in response.text
            # HTMX outerHTML swap: the response fragment must carry the target id
            assert "pending-card-jobA" in response.text

    def test_reject_response_contains_card_id(self, client, auth_enabled, admin_user, tmp_path):
        """Reject response has id=pending-card-{job_id} for HTMX outerHTML swap."""
        staging_dir = tmp_path / "staging" / "jobB"
        staging_dir.mkdir(parents=True)
        (staging_dir / "photo1.jpg").write_bytes(b"fake")

        with (
            patch("app.main.data_path", tmp_path),
            patch("app.admin_routes._main_mod.data_path", tmp_path),
        ):
            from app.main import _save_pending_uploads

            _save_pending_uploads({"uploads": {"jobB": _make_pending_upload("jobB")}})

            response = client.post("/admin/pending/jobB/reject")
            assert response.status_code == 200
            assert "Rejected" in response.text
            assert "pending-card-jobB" in response.text

    def test_approve_not_found_response_has_card_id(self, client, auth_enabled, admin_user, tmp_path):
        """Even 'not found' response carries the card id."""
        with (
            patch("app.main.data_path", tmp_path),
            patch("app.admin_routes._main_mod.data_path", tmp_path),
        ):
            response = client.post("/admin/pending/ghost/approve")
            assert response.status_code == 200
            assert "pending-card-ghost" in response.text

    def test_reject_not_found_response_has_card_id(self, client, auth_enabled, admin_user, tmp_path):
        """Reject 'not found' response carries the card id."""
        with (
            patch("app.main.data_path", tmp_path),
            patch("app.admin_routes._main_mod.data_path", tmp_path),
        ):
            response = client.post("/admin/pending/ghost/reject")
            assert response.status_code == 200
            assert "pending-card-ghost" in response.text


# ---------------------------------------------------------------------------
# Issue 6: Staged uploads can be approved (previously blocked by != "pending")
# ---------------------------------------------------------------------------


class TestApproveAllowsStagedStatus:
    """Admin uploads have status='staged'. Approval must work for them too."""

    def test_approve_staged_upload(self, client, auth_enabled, admin_user, tmp_path):
        """Staged uploads can be approved."""
        with (
            patch("app.main.data_path", tmp_path),
            patch("app.admin_routes._main_mod.data_path", tmp_path),
            patch("app.main.PROCESSING_ENABLED", False),
            patch("app.admin_routes.PROCESSING_ENABLED", False),
        ):
            from app.main import _save_pending_uploads

            _save_pending_uploads({"uploads": {"jobS": _make_pending_upload("jobS", status="staged")}})

            response = client.post("/admin/pending/jobS/approve")
            assert response.status_code == 200
            assert "Approved" in response.text

            # Verify status updated in JSON
            with open(tmp_path / "pending_uploads.json") as f:
                data = json.load(f)
            assert data["uploads"]["jobS"]["status"] == "approved"

    def test_cannot_approve_already_approved(self, client, auth_enabled, admin_user, tmp_path):
        """Cannot re-approve an already-approved upload."""
        with (
            patch("app.main.data_path", tmp_path),
            patch("app.admin_routes._main_mod.data_path", tmp_path),
        ):
            from app.main import _save_pending_uploads

            _save_pending_uploads({"uploads": {"jobD": _make_pending_upload("jobD", status="approved")}})

            response = client.post("/admin/pending/jobD/approve")
            assert response.status_code == 200
            assert "already approved" in response.text.lower()

    def test_cannot_approve_rejected_upload(self, client, auth_enabled, admin_user, tmp_path):
        """Cannot approve a rejected upload."""
        with (
            patch("app.main.data_path", tmp_path),
            patch("app.admin_routes._main_mod.data_path", tmp_path),
        ):
            from app.main import _save_pending_uploads

            _save_pending_uploads({"uploads": {"jobR": _make_pending_upload("jobR", status="rejected")}})

            response = client.post("/admin/pending/jobR/approve")
            assert response.status_code == 200
            assert "already rejected" in response.text.lower()


# ---------------------------------------------------------------------------
# Issue 3 + 6: Auto-confirm identities created during approval
# ---------------------------------------------------------------------------


class TestAutoConfirmOnApprove:
    """_auto_confirm_job_identities confirms INBOX identities for a given job_id."""

    def test_auto_confirm_confirms_named_inbox_identities(self, tmp_path):
        """Named INBOX identities for this job get auto-confirmed."""
        from core.registry import IdentityRegistry, IdentityState

        identity_path = tmp_path / "identities.json"
        reg = IdentityRegistry()
        # Create a named INBOX identity (simulates a face that matched a named cluster)
        reg.create_identity(
            anchor_ids=["face1"],
            user_source="inbox_ingest",
            name="Solomon Galante",
            state=IdentityState.INBOX,
            provenance={"job_id": "jobX", "source": "test"},
        )
        reg.save(identity_path)

        from app.admin_routes import _auto_confirm_job_identities

        count = _auto_confirm_job_identities(tmp_path, "jobX", user_source="admin_approve:admin@test.com")
        assert count == 1

        # Reload and check state
        reg2 = IdentityRegistry.load(identity_path)
        confirmed = reg2.list_identities(state=IdentityState.CONFIRMED)
        assert len(confirmed) == 1

    def test_auto_confirm_skips_unnamed_inbox_identities(self, tmp_path):
        """INBOX identities with placeholder names are NOT auto-confirmed (require admin review)."""
        from core.registry import IdentityRegistry, IdentityState

        identity_path = tmp_path / "identities.json"
        reg = IdentityRegistry()
        # Default name will be "Unidentified Person XXXX"
        reg.create_identity(
            anchor_ids=["face1"],
            user_source="inbox_ingest",
            state=IdentityState.INBOX,
            provenance={"job_id": "jobX", "source": "test"},
        )
        reg.save(identity_path)

        from app.admin_routes import _auto_confirm_job_identities

        count = _auto_confirm_job_identities(tmp_path, "jobX", user_source="admin_approve:admin@test.com")
        assert count == 0  # Unnamed identities stay INBOX

    def test_auto_confirm_ignores_other_jobs(self, tmp_path):
        """Only identities for the specific job_id are confirmed."""
        from core.registry import IdentityRegistry, IdentityState

        identity_path = tmp_path / "identities.json"
        reg = IdentityRegistry()
        reg.create_identity(
            anchor_ids=["face2"],
            user_source="inbox_ingest",
            name="Leon Capeloto",
            state=IdentityState.INBOX,
            provenance={"job_id": "other_job"},
        )
        reg.save(identity_path)

        from app.admin_routes import _auto_confirm_job_identities

        count = _auto_confirm_job_identities(tmp_path, "jobX", user_source="admin_approve:admin@test.com")
        assert count == 0

    def test_auto_confirm_skips_already_confirmed_identities(self, tmp_path):
        """CONFIRMED identities with same job_id are left untouched (not double-counted)."""
        from core.registry import IdentityRegistry, IdentityState

        identity_path = tmp_path / "identities.json"
        reg = IdentityRegistry()
        # Create named INBOX identity then confirm it before calling _auto_confirm
        iid = reg.create_identity(
            anchor_ids=["face3"],
            user_source="admin",
            name="Isaac Cohen",
            state=IdentityState.INBOX,
            provenance={"job_id": "jobX"},
        )
        reg.confirm_identity(iid, user_source="admin")
        reg.save(identity_path)

        from app.admin_routes import _auto_confirm_job_identities

        count = _auto_confirm_job_identities(tmp_path, "jobX", user_source="admin_approve:admin@test.com")
        assert count == 0  # Already confirmed, not counted again

    def test_auto_confirm_handles_missing_identity_file(self, tmp_path):
        """Returns 0 gracefully when identities.json doesn't exist."""
        from app.admin_routes import _auto_confirm_job_identities

        count = _auto_confirm_job_identities(tmp_path, "jobX", user_source="admin")
        assert count == 0


# ---------------------------------------------------------------------------
# Issue 4: Approve returns immediately (background processing)
# ---------------------------------------------------------------------------


class TestApproveReturnsImmediately:
    """The approve handler must NOT block on face processing."""

    def test_approve_returns_fast_with_processing_enabled(self, client, auth_enabled, admin_user, tmp_path):
        """Approve returns response before background processing completes."""
        staging_dir = tmp_path / "staging" / "jobF"
        staging_dir.mkdir(parents=True)
        (staging_dir / "photo1.jpg").write_bytes(b"fake")

        thread_started = []

        def fake_thread(*args, **kwargs):
            t = MagicMock()
            t.start = lambda: thread_started.append(True)
            return t

        with (
            patch("app.main.data_path", tmp_path),
            patch("app.admin_routes._main_mod.data_path", tmp_path),
            patch("app.main.PROCESSING_ENABLED", True),
            patch("app.admin_routes.PROCESSING_ENABLED", True),
            patch("threading.Thread", side_effect=fake_thread),
        ):
            from app.main import _save_pending_uploads

            _save_pending_uploads({"uploads": {"jobF": _make_pending_upload("jobF")}})

            start = time.monotonic()
            response = client.post("/admin/pending/jobF/approve")
            elapsed = time.monotonic() - start

            assert response.status_code == 200
            assert "Approved" in response.text
            # Response must arrive without waiting for processing
            assert elapsed < 5.0, f"Approve took too long: {elapsed:.2f}s"

    def test_approve_response_mentions_background_processing(self, client, auth_enabled, admin_user, tmp_path):
        """When staging dir exists, response notes background processing."""
        staging_dir = tmp_path / "staging" / "jobG"
        staging_dir.mkdir(parents=True)
        (staging_dir / "photo1.jpg").write_bytes(b"fake")

        with (
            patch("app.main.data_path", tmp_path),
            patch("app.admin_routes._main_mod.data_path", tmp_path),
            patch("app.main.PROCESSING_ENABLED", True),
            patch("app.admin_routes.PROCESSING_ENABLED", True),
            patch("threading.Thread"),
        ):
            from app.main import _save_pending_uploads

            _save_pending_uploads({"uploads": {"jobG": _make_pending_upload("jobG")}})

            response = client.post("/admin/pending/jobG/approve")
            assert response.status_code == 200
            # Processing note visible in response
            assert "background" in response.text.lower() or "processing" in response.text.lower()


# ---------------------------------------------------------------------------
# Issue 5: Batch approve endpoint
# ---------------------------------------------------------------------------


class TestBatchApprove:
    """POST /admin/pending/batch-approve approves multiple uploads at once."""

    def test_batch_approve_multiple_uploads(self, client, auth_enabled, admin_user, tmp_path):
        """Batch approve updates status for all selected job_ids."""
        with (
            patch("app.main.data_path", tmp_path),
            patch("app.admin_routes._main_mod.data_path", tmp_path),
            patch("app.main.PROCESSING_ENABLED", False),
            patch("app.admin_routes.PROCESSING_ENABLED", False),
        ):
            from app.main import _save_pending_uploads

            _save_pending_uploads(
                {
                    "uploads": {
                        "j1": _make_pending_upload("j1"),
                        "j2": _make_pending_upload("j2"),
                        "j3": _make_pending_upload("j3"),
                    }
                }
            )

            response = client.post(
                "/admin/pending/batch-approve",
                content=b"job_ids=j1&job_ids=j2",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            assert response.status_code == 200
            assert "Approved" in response.text or "approved" in response.text

            with open(tmp_path / "pending_uploads.json") as f:
                data = json.load(f)

            assert data["uploads"]["j1"]["status"] == "approved"
            assert data["uploads"]["j2"]["status"] == "approved"
            # j3 was not selected
            assert data["uploads"]["j3"]["status"] == "pending"

    def test_batch_approve_empty_selection(self, client, auth_enabled, admin_user, tmp_path):
        """Batch approve with no job_ids returns helpful message."""
        with (
            patch("app.main.data_path", tmp_path),
            patch("app.admin_routes._main_mod.data_path", tmp_path),
        ):
            response = client.post("/admin/pending/batch-approve", data={})
            assert response.status_code == 200
            assert "no uploads selected" in response.text.lower()

    def test_batch_approve_skips_already_reviewed(self, client, auth_enabled, admin_user, tmp_path):
        """Batch approve skips already-approved/rejected uploads."""
        with (
            patch("app.main.data_path", tmp_path),
            patch("app.admin_routes._main_mod.data_path", tmp_path),
            patch("app.main.PROCESSING_ENABLED", False),
            patch("app.admin_routes.PROCESSING_ENABLED", False),
        ):
            from app.main import _save_pending_uploads

            _save_pending_uploads(
                {
                    "uploads": {
                        "jok": _make_pending_upload("jok"),
                        "jdone": _make_pending_upload("jdone", status="approved"),
                    }
                }
            )

            response = client.post(
                "/admin/pending/batch-approve",
                content=b"job_ids=jok&job_ids=jdone",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            assert response.status_code == 200

            with open(tmp_path / "pending_uploads.json") as f:
                data = json.load(f)

            assert data["uploads"]["jok"]["status"] == "approved"
            assert data["uploads"]["jdone"]["status"] == "approved"  # unchanged

    def test_batch_approve_requires_admin(self, client, auth_enabled, regular_user, tmp_path):
        """Batch approve is admin-only."""
        with (
            patch("app.main.data_path", tmp_path),
            patch("app.admin_routes._main_mod.data_path", tmp_path),
        ):
            response = client.post(
                "/admin/pending/batch-approve",
                content=b"job_ids=j1",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            # Non-admin gets 401/403
            assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Issue 1: Pending page renders Select All + Approve Selected
# ---------------------------------------------------------------------------


class TestPendingPageBatchUI:
    """GET /admin/pending shows batch approve UI when pending items exist."""

    def test_pending_page_shows_select_all_checkbox(self, client, auth_enabled, admin_user, tmp_path):
        """Pending page shows a 'Select All' checkbox for batch operations."""
        with (
            patch("app.main.data_path", tmp_path),
            patch("app.admin_routes._main_mod.data_path", tmp_path),
        ):
            from app.main import _save_pending_uploads

            _save_pending_uploads(
                {
                    "uploads": {
                        "job1": _make_pending_upload("job1"),
                    }
                }
            )

            response = client.get("/admin/pending")
            assert response.status_code == 200
            assert "select-all-pending" in response.text
            assert "Approve Selected" in response.text
            assert "batch-select-checkbox" in response.text

    def test_pending_page_no_batch_ui_when_empty(self, client, auth_enabled, admin_user, tmp_path):
        """Pending page does not show batch approve UI when no pending items."""
        with (
            patch("app.main.data_path", tmp_path),
            patch("app.admin_routes._main_mod.data_path", tmp_path),
        ):
            response = client.get("/admin/pending")
            assert response.status_code == 200
            # No batch toolbar when empty
            assert "Approve Selected" not in response.text

    def test_pending_page_no_batch_ui_for_staged_only(self, client, auth_enabled, admin_user, tmp_path):
        """Staged-only uploads don't show batch approve (it's for contributor uploads)."""
        with (
            patch("app.main.data_path", tmp_path),
            patch("app.admin_routes._main_mod.data_path", tmp_path),
        ):
            from app.main import _save_pending_uploads

            _save_pending_uploads(
                {
                    "uploads": {
                        "staged1": _make_pending_upload("staged1", status="staged"),
                    }
                }
            )

            response = client.get("/admin/pending")
            assert response.status_code == 200
            assert "Approve Selected" not in response.text


# ---------------------------------------------------------------------------
# Regression: logger defined in admin_routes (NameError guard)
# ---------------------------------------------------------------------------


class TestLoggerDefined:
    """admin_routes.py must have a logger defined to avoid NameError on reject."""

    def test_logger_exists_in_admin_routes(self):
        """admin_routes.logger is a standard logging.Logger."""
        import logging

        import app.admin_routes as ar

        assert hasattr(ar, "logger")
        assert isinstance(ar.logger, logging.Logger)
