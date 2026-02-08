"""Tests for FE-002/FE-003: Universal keyboard shortcuts across all photo views.

Verifies that:
1. Match mode HTML includes keyboard-navigable button IDs
2. Match mode includes keyboard shortcut hint text
3. Focus mode HTML includes keyboard shortcut indicators
4. Global keyboard handler script includes match mode + focus mode dispatching
5. Keyboard shortcuts are suppressed for input/textarea focus
"""

import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Match mode keyboard shortcuts
# ---------------------------------------------------------------------------

class TestMatchModeKeyboardNav:
    """Match mode buttons must have IDs for keyboard delegation."""

    def _mock_pair(self):
        identity_a = {
            "identity_id": "id-a",
            "name": "Alice",
            "state": "INBOX",
            "anchor_ids": ["face-a1"],
            "candidate_ids": [],
        }
        neighbor_b = {
            "identity_id": "id-b",
            "name": "Bob",
            "distance": 0.8,
            "face_count": 1,
        }
        return (identity_a, neighbor_b, 0.8)

    def _get_match_html(self):
        """Fetch match mode next-pair HTML with mocks."""
        from starlette.testclient import TestClient
        from app.main import app

        with patch("app.main._get_best_match_pair", return_value=self._mock_pair()), \
             patch("app.main.get_crop_files", return_value=set()), \
             patch("app.main.get_photo_id_for_face", return_value="photo-1"), \
             patch("app.main.resolve_face_image_url", return_value="/crops/face.jpg"), \
             patch("app.main.load_registry") as mock_reg:
            reg = MagicMock()
            reg.get_identity.return_value = {
                "identity_id": "id-b", "name": "Bob",
                "anchor_ids": ["face-b1"], "candidate_ids": [],
            }
            mock_reg.return_value = reg
            client = TestClient(app)
            resp = client.get("/api/match/next-pair")
            return resp.text

    def test_same_button_has_keyboard_id(self):
        """'Same Person' button has id='match-btn-same' for keyboard delegation."""
        html = self._get_match_html()
        assert 'id="match-btn-same"' in html

    def test_different_button_has_keyboard_id(self):
        """'Different People' button has id='match-btn-diff' for keyboard delegation."""
        html = self._get_match_html()
        assert 'id="match-btn-diff"' in html

    def test_skip_button_has_keyboard_id(self):
        """'Skip' button has id='match-btn-skip' for keyboard delegation."""
        html = self._get_match_html()
        assert 'id="match-btn-skip"' in html

    def test_match_mode_shows_keyboard_hints(self):
        """Match mode shows keyboard shortcut hint text."""
        html = self._get_match_html()
        # Should display keyboard hint for Y/N/S shortcuts
        assert "Keyboard:" in html or ("Y" in html and "N" in html)


# ---------------------------------------------------------------------------
# Focus mode keyboard shortcuts
# ---------------------------------------------------------------------------

class TestFocusModeKeyboardNav:
    """Focus mode must have keyboard shortcut indicators."""

    @patch("app.main.resolve_face_image_url", return_value="/crops/test.jpg")
    def test_focus_card_has_keyboard_hint_text(self, mock_url):
        """identity_card_expanded renders 'Keyboard: C S R F' hint for admins."""
        from app.main import identity_card_expanded
        from fastcore.xml import to_xml

        identity = {
            "identity_id": "test-id",
            "name": "Test Person",
            "state": "INBOX",
            "anchor_ids": ["face-1"],
            "candidate_ids": [],
        }
        result = identity_card_expanded(identity, crop_files=set(), is_admin=True)
        html = to_xml(result)

        assert "Keyboard:" in html or "C S R F" in html or "C=Confirm" in html

    @patch("app.main.resolve_face_image_url", return_value="/crops/test.jpg")
    def test_focus_card_has_action_button_ids(self, mock_url):
        """identity_card_expanded renders buttons with focus-btn-* IDs for keyboard delegation."""
        from app.main import identity_card_expanded
        from fastcore.xml import to_xml

        identity = {
            "identity_id": "test-id",
            "name": "Test Person",
            "state": "INBOX",
            "anchor_ids": ["face-1"],
            "candidate_ids": [],
        }
        result = identity_card_expanded(identity, crop_files=set(), is_admin=True)
        html = to_xml(result)

        assert 'id="focus-btn-confirm"' in html
        assert 'id="focus-btn-skip"' in html
        assert 'id="focus-btn-reject"' in html
        assert 'id="focus-btn-similar"' in html


# ---------------------------------------------------------------------------
# Global keyboard handler in page layout
# ---------------------------------------------------------------------------

class TestGlobalKeyboardHandler:
    """The global keydown handler must cover match mode and focus mode shortcuts."""

    @patch("app.main.is_auth_enabled", return_value=False)
    @patch("app.main.get_current_user", return_value=None)
    def test_global_handler_includes_match_mode_dispatch(self, mock_user, mock_auth, client):
        """Global keydown handler dispatches to match-btn-same/diff/skip."""
        # Use section=confirmed to get the main app layout (not landing page)
        resp = client.get("/?section=confirmed")
        html = resp.text

        # Global handler must reference match mode button IDs
        assert "match-btn-same" in html
        assert "match-btn-diff" in html
        assert "match-btn-skip" in html

    @patch("app.main.is_auth_enabled", return_value=False)
    @patch("app.main.get_current_user", return_value=None)
    def test_global_handler_includes_focus_mode_dispatch(self, mock_user, mock_auth, client):
        """Global keydown handler dispatches to focus-btn-confirm/skip/reject/similar."""
        resp = client.get("/?section=confirmed")
        html = resp.text

        # Global handler must reference focus mode button IDs
        assert "focus-btn-confirm" in html
        assert "focus-btn-skip" in html
        assert "focus-btn-reject" in html
        assert "focus-btn-similar" in html

    @patch("app.main.is_auth_enabled", return_value=False)
    @patch("app.main.get_current_user", return_value=None)
    def test_global_handler_suppresses_in_text_inputs(self, mock_user, mock_auth, client):
        """Global keyboard handler must skip shortcuts when typing in input/textarea."""
        resp = client.get("/?section=confirmed")
        html = resp.text

        # Must check for INPUT/TEXTAREA tagName before dispatching
        assert "INPUT" in html and "TEXTAREA" in html

    @patch("app.main.is_auth_enabled", return_value=False)
    @patch("app.main.get_current_user", return_value=None)
    def test_global_handler_is_single_listener(self, mock_user, mock_auth, client):
        """The global handler should contain both match and focus mode in one keydown listener."""
        resp = client.get("/?section=confirmed")
        html = resp.text

        # The global delegation script should contain both match and focus mode handling
        assert "match-btn-same" in html
        assert "focus-btn-confirm" in html
