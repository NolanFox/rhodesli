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

        _invalidate_annotations_cache()

        # Use a large limit so real action log entries don't push out the annotation
        with patch("app.main.data_path", tmp_path):
            result = _load_activity_feed(limit=500)
            approved = [a for a in result if a["type"] == "annotation_approved"]
            assert len(approved) == 1
            assert "Leon Capeluto" in approved[0]["description"]

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


class TestWelcomeModal:
    """Tests for the first-time user welcome modal (FE-052)."""

    def test_welcome_modal_renders_on_first_visit(self):
        """Welcome modal appears on first visit (no 'welcomed' in session)."""
        from app.main import _welcome_modal
        from fastcore.xml import to_xml

        sess = {}
        result = _welcome_modal(sess)
        html = to_xml(result)
        assert "Welcome to Rhodesli" in html
        assert "welcome-modal" in html
        assert "Got it!" in html

    def test_welcome_modal_hidden_on_return_visit(self):
        """Welcome modal does not appear when session has 'welcomed' flag."""
        from app.main import _welcome_modal
        from fastcore.xml import to_xml

        sess = {"welcomed": True}
        result = _welcome_modal(sess)
        html = to_xml(result)
        assert "Welcome to Rhodesli" not in html

    def test_welcome_modal_sets_session_flag(self):
        """Welcome modal sets 'welcomed' flag in session."""
        from app.main import _welcome_modal

        sess = {}
        _welcome_modal(sess)
        assert sess["welcomed"] is True

    def test_welcome_modal_handles_none_session(self):
        """Welcome modal handles None session gracefully."""
        from app.main import _welcome_modal
        from fastcore.xml import to_xml

        result = _welcome_modal(None)
        html = to_xml(result)
        assert "Welcome to Rhodesli" in html

    def test_welcome_modal_mentions_suggest_name(self):
        """Welcome modal tells users about the Suggest Name feature."""
        from app.main import _welcome_modal
        from fastcore.xml import to_xml

        result = _welcome_modal({})
        html = to_xml(result)
        assert "Suggest Name" in html
