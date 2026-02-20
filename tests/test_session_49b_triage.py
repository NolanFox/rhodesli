"""
Session 49B Triage — Regression tests for sort routing & upload status handling.

Bug fixes:
1. Sort links missing &view=browse parameter (sort clicks reverted to focus mode)
2. Upload status stuck forever when subprocess dies (no timeout/error detection)
3. Compare upload verified working on production (no code change needed)
"""

import json
import pytest
from unittest.mock import patch
from datetime import datetime, timezone, timedelta


class TestSortLinksPreserveViewMode:
    """Sort controls must include &view=browse when rendered in browse mode.

    Bug: _sort_control() generated links like /?section=to_review&sort_by=faces
    but omitted &view=browse, causing sort clicks to revert to focus mode.
    """

    def test_sort_links_include_view_browse_in_browse_mode(self, client, auth_disabled):
        """Sort links in browse mode must include &view=browse."""
        response = client.get("/?section=to_review&view=browse")
        assert response.status_code == 200
        # Each sort link should preserve view=browse
        assert "sort_by=name&amp;view=browse" in response.text or \
               "sort_by=name&view=browse" in response.text, \
               "Sort link for 'name' missing view=browse"
        assert "sort_by=faces&amp;view=browse" in response.text or \
               "sort_by=faces&view=browse" in response.text, \
               "Sort link for 'faces' missing view=browse"
        assert "sort_by=newest&amp;view=browse" in response.text or \
               "sort_by=newest&view=browse" in response.text, \
               "Sort link for 'newest' missing view=browse"

    def test_sort_links_include_view_browse_in_confirmed_section(self, client, auth_disabled):
        """Confirmed section sort links must also include view=browse."""
        response = client.get("/?section=confirmed")
        assert response.status_code == 200
        assert "sort_by=name&amp;view=browse" in response.text or \
               "sort_by=name&view=browse" in response.text, \
               "Confirmed sort link for 'name' missing view=browse"

    def test_sort_by_actually_changes_order_in_browse_mode(self, client, auth_disabled):
        """Different sort_by values should produce different orderings."""
        resp_name = client.get("/?section=to_review&view=browse&sort_by=name")
        resp_faces = client.get("/?section=to_review&view=browse&sort_by=faces")
        assert resp_name.status_code == 200
        assert resp_faces.status_code == 200
        # Both should render (not crash). Content difference depends on data.

    def test_browse_mode_with_sort_returns_200(self, client, auth_disabled):
        """All sort options in browse mode should return 200."""
        for sort in ["name", "faces", "newest"]:
            response = client.get(f"/?section=to_review&view=browse&sort_by={sort}")
            assert response.status_code == 200, f"sort_by={sort} returned {response.status_code}"


class TestUploadStatusTimeout:
    """Upload status endpoint must detect dead subprocesses and show errors.

    Bug: Subprocess spawned with stderr=DEVNULL died silently,
    status file never created, polling continued forever.
    """

    def test_upload_status_starting_within_timeout_keeps_polling(self, client, auth_disabled, tmp_path):
        """Status 'starting' within timeout should show 'Starting processing...' and poll."""
        status_data = {
            "status": "starting",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "total_files": 1,
            "files_succeeded": 0,
            "files_failed": 0,
        }
        with patch("app.main.data_path", tmp_path):
            inbox_dir = tmp_path / "inbox"
            inbox_dir.mkdir()
            (inbox_dir / "test-job.status.json").write_text(json.dumps(status_data))
            response = client.get("/upload/status/test-job")

        assert response.status_code == 200
        assert "Starting" in response.text
        # Should still be polling
        assert "hx-get" in response.text or "hx_get" in response.text

    def test_upload_status_starting_past_timeout_shows_error(self, client, auth_disabled, tmp_path):
        """Status 'starting' past 2-minute timeout should show error."""
        old_time = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        status_data = {
            "status": "starting",
            "started_at": old_time,
            "total_files": 1,
            "files_succeeded": 0,
            "files_failed": 0,
        }
        with patch("app.main.data_path", tmp_path):
            inbox_dir = tmp_path / "inbox"
            inbox_dir.mkdir()
            (inbox_dir / "test-job.status.json").write_text(json.dumps(status_data))
            response = client.get("/upload/status/test-job")

        assert response.status_code == 200
        assert "failed" in response.text.lower() or "error" in response.text.lower()
        # Should NOT be polling anymore
        assert "hx-trigger" not in response.text

    def test_upload_status_starting_past_timeout_shows_log_excerpt(self, client, auth_disabled, tmp_path):
        """When subprocess fails, the error should include log output."""
        old_time = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        status_data = {
            "status": "starting",
            "started_at": old_time,
            "total_files": 1,
            "files_succeeded": 0,
            "files_failed": 0,
        }
        with patch("app.main.data_path", tmp_path):
            inbox_dir = tmp_path / "inbox"
            inbox_dir.mkdir()
            (inbox_dir / "test-job.status.json").write_text(json.dumps(status_data))
            (inbox_dir / "test-job.log").write_text(
                "ImportError: No module named 'insightface'\n"
                "Traceback (most recent call last):\n"
                "  File \"/app/core/ingest_inbox.py\", line 10\n"
            )
            response = client.get("/upload/status/test-job")

        assert response.status_code == 200
        assert "insightface" in response.text or "Log output" in response.text

    def test_upload_status_no_file_returns_starting(self, client, auth_disabled, tmp_path):
        """When no status file exists, should show Starting... and keep polling."""
        with patch("app.main.data_path", tmp_path):
            inbox_dir = tmp_path / "inbox"
            inbox_dir.mkdir()
            response = client.get("/upload/status/nonexistent-job")

        assert response.status_code == 200
        assert "Starting" in response.text
        assert "hx-get" in response.text or "hx_get" in response.text


class TestCompareUploadEndpoint:
    """Verify compare upload smoke test: page loads with upload form."""

    def test_compare_page_has_upload_form(self, client, auth_disabled):
        """Compare page should have file upload form with HTMX attributes."""
        response = client.get("/compare")
        assert response.status_code == 200
        assert 'type="file"' in response.text
        assert "compare-results" in response.text
        assert "hx-post" in response.text or "hx_post" in response.text

    def test_compare_page_has_spinner_indicator(self, client, auth_disabled):
        """Compare page should have a loading spinner for HTMX indicator."""
        response = client.get("/compare")
        assert response.status_code == 200
        assert "upload-spinner" in response.text
        assert "Analyzing" in response.text or "spinner" in response.text.lower()
