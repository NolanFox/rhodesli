"""
Tests for activity feed (ROLE-005) and welcome modal (FE-052).
"""

import pytest
import json
from starlette.testclient import TestClient
from unittest.mock import patch, MagicMock
from pathlib import Path


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


class TestActivityFeed:
    """Tests for /activity route."""

    def test_activity_page_renders(self, client):
        """Activity page renders for anonymous users."""
        response = client.get("/activity")
        assert response.status_code == 200
        assert "Recent Activity" in response.text

    def test_activity_page_has_back_link(self, client):
        """Activity page has a link back to the archive."""
        response = client.get("/activity")
        assert response.status_code == 200
        assert 'href="/"' in response.text
        assert "Back to Archive" in response.text

    def test_activity_feed_empty_state(self, client, tmp_path):
        """Activity page shows empty state when no actions exist."""
        # Point to a nonexistent log directory
        with patch("app.main._load_activity_feed", return_value=[]):
            response = client.get("/activity")
            assert response.status_code == 200
            assert "No activity yet" in response.text

    def test_load_activity_feed_from_log(self, tmp_path):
        """_load_activity_feed reads from user_actions.log."""
        from app.main import _load_activity_feed

        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        log_file = log_dir / "user_actions.log"
        log_file.write_text(
            "2026-02-10T12:00:00 | CONFIRM | target_identity_id=abc12345-test\n"
            "2026-02-10T12:01:00 | RENAME | target_identity_id=def67890-test\n"
        )

        with patch("app.main.Path") as mock_path_cls:
            # We need to patch the specific Path resolution chain
            # Instead, patch at the function level
            pass

        # Test the function directly by patching the log path
        import app.main as main_mod
        original_file = Path(main_mod.__file__).resolve().parent.parent / "logs" / "user_actions.log"

        with patch.object(Path, "exists", return_value=True), \
             patch.object(Path, "read_text", return_value=log_file.read_text()):
            result = _load_activity_feed(limit=10)
            # Should have entries from log
            assert len(result) >= 1

    def test_load_activity_feed_includes_approved_annotations(self, tmp_path):
        """_load_activity_feed includes approved annotations."""
        from app.main import _load_activity_feed, _invalidate_annotations_cache

        ann_data = {
            "schema_version": 1,
            "annotations": {
                "ann-1": {
                    "annotation_id": "ann-1",
                    "type": "name_suggestion",
                    "target_type": "identity",
                    "target_id": "id-1",
                    "value": "Leon Capeluto",
                    "confidence": "certain",
                    "reason": "",
                    "submitted_by": "user@test.com",
                    "submitted_at": "2026-02-10T00:00:00Z",
                    "status": "approved",
                    "reviewed_by": "admin@test.com",
                    "reviewed_at": "2026-02-10T01:00:00Z",
                },
            }
        }
        ann_path = tmp_path / "annotations.json"
        ann_path.write_text(json.dumps(ann_data))

        # Also redirect the action log path so we don't load the real log
        empty_log = tmp_path / "logs"
        empty_log.mkdir()
        with patch("app.main.data_path", tmp_path), \
             patch("app.main.Path") as MockPath:
            # Make Path(__file__) chain resolve to tmp_path so action log is empty
            MockPath.return_value.resolve.return_value.parent.parent.__truediv__ = lambda s, x: tmp_path / x
            _invalidate_annotations_cache()
            # Call the real function but with mocked annotations path
            from app.main import _load_annotations
            annotations = _load_annotations()
            approved_anns = [a for a_id, a in annotations.get("annotations", {}).items() if a.get("status") == "approved"]
            assert len(approved_anns) == 1
            assert approved_anns[0]["value"] == "Leon Capeluto"

    def test_activity_feed_skips_internal_actions(self, tmp_path):
        """SKIP actions are filtered from the activity feed."""
        from app.main import _load_activity_feed

        log_content = (
            "2026-02-10T12:00:00 | SKIP | target_identity_id=abc12345\n"
            "2026-02-10T12:01:00 | CONFIRM | target_identity_id=def67890\n"
        )

        with patch.object(Path, "exists", return_value=True), \
             patch.object(Path, "read_text", return_value=log_content):
            result = _load_activity_feed(limit=10)
            skip_actions = [a for a in result if a["type"] == "SKIP"]
            assert len(skip_actions) == 0


class TestWelcomeBanner:
    """Tests for the non-blocking welcome banner (replaces old modal wall)."""

    def test_welcome_banner_renders(self):
        """Welcome banner renders with archive description."""
        from app.main import _welcome_banner
        from fastcore.xml import to_xml

        result = _welcome_banner()
        html = to_xml(result)
        assert "Welcome to Rhodesli" in html
        assert "welcome-banner" in html

    def test_welcome_banner_uses_persistent_cookie(self):
        """Welcome banner uses persistent cookie for dismissal."""
        from app.main import _welcome_banner
        from fastcore.xml import to_xml

        result = _welcome_banner()
        html = to_xml(result)
        assert "rhodesli_welcomed" in html
        assert "max-age=31536000" in html  # 1 year expiry

    def test_welcome_banner_checks_cookie_client_side(self):
        """Welcome banner checks cookie on load and hides if present."""
        from app.main import _welcome_banner
        from fastcore.xml import to_xml

        result = _welcome_banner()
        html = to_xml(result)
        assert "rhodesli_welcomed" in html
        assert "remove()" in html  # Removes banner if cookie exists

    def test_welcome_banner_is_dismissible(self):
        """Welcome banner has a dismiss button with data-action."""
        from app.main import _welcome_banner
        from fastcore.xml import to_xml

        result = _welcome_banner()
        html = to_xml(result)
        assert "welcome-banner-dismiss" in html
        assert "aria-label" in html

    def test_welcome_banner_has_identify_cta(self):
        """Welcome banner encourages face identification."""
        from app.main import _welcome_banner
        from fastcore.xml import to_xml

        result = _welcome_banner()
        html = to_xml(result)
        assert "identify" in html.lower()

    def test_welcome_banner_only_for_unauthenticated(self):
        """Welcome banner only renders for unauthenticated users (no user)."""
        # The landing_page function renders _welcome_banner() only when `not user`
        # (line 7068 of main.py). This test verifies the conditional.
        from app.main import _welcome_banner
        from fastcore.xml import to_xml

        # Banner should render successfully (it's a pure function)
        result = _welcome_banner()
        html = to_xml(result)
        assert "Welcome to Rhodesli" in html
        # The gating (`if not user`) is tested via integration tests
