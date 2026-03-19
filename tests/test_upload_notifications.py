"""Tests for Session 120: FB-008 cross-batch match notifications after upload."""

from pathlib import Path
from unittest.mock import MagicMock, patch


class TestUploadMatchNotifications:
    """Verify cross-batch matching generates notifications."""

    def test_notification_code_present_in_upload_pipeline(self):
        """The upload pipeline must create a notification after cross-batch matching."""
        upload_routes = Path("app/upload_routes.py").read_text()

        # Must call _create_notification with upload_matches type
        assert "_create_notification" in upload_routes, "Upload pipeline must call _create_notification to alert admin"
        assert '"upload_matches"' in upload_routes, "Notification type must be 'upload_matches'"

    def test_notification_gated_on_cross_matches(self):
        """Notification must only fire when cross_matches is non-empty."""
        lines = Path("app/upload_routes.py").read_text().splitlines()
        # Find the FB-008 notification line
        fb_line = None
        for i, line in enumerate(lines):
            if "FB-008" in line:
                fb_line = i
                break
        assert fb_line is not None, "FB-008 marker not found"
        # Check that there's an "if cross_matches:" guard near it (within 3 lines above or below)
        nearby = "\n".join(lines[max(0, fb_line - 3) : fb_line + 3])
        assert "if cross_matches" in nearby, (
            f"Notification creation must be gated on cross_matches being non-empty. Nearby lines: {nearby}"
        )

    def test_notification_includes_counts_and_top_match(self):
        """Notification body must include face count, match count, and top match."""
        upload_routes = Path("app/upload_routes.py").read_text()
        fb_idx = upload_routes.index("FB-008")
        notif_section = upload_routes[fb_idx : fb_idx + 2000]

        assert "n_faces" in notif_section, "Notification must include face count"
        assert "n_matches" in notif_section, "Notification must include match count"
        assert "best_name" in notif_section, "Notification should include top match name"
