"""
Tests for UI clarity: section descriptions, Skipped→Help Identify rename, empty states.
"""

import pytest
from starlette.testclient import TestClient
from unittest.mock import patch


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


class TestSectionDescriptions:
    """Tests for descriptive section headers."""

    def test_inbox_description(self, client):
        """New Matches section has descriptive subtitle."""
        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get("/?section=to_review&view=browse")
            assert response.status_code == 200
            assert "faces the AI matched" in response.text

    def test_confirmed_section_label(self, client):
        """Confirmed section uses 'People' label with description."""
        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get("/?section=confirmed")
            assert response.status_code == 200
            assert "People" in response.text
            assert "identified" in response.text

    def test_skipped_displayed_as_help_identify(self, client):
        """UI shows 'Help Identify' instead of 'Skipped' in section header."""
        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get("/?section=skipped")
            assert response.status_code == 200
            assert "Help Identify" in response.text


class TestSkippedRename:
    """Tests for Skipped → Help Identify UI rename."""

    def test_sidebar_shows_help_identify(self, client):
        """Sidebar navigation shows 'Help Identify' not 'Skipped'."""
        from app.main import sidebar, load_registry, _compute_sidebar_counts
        from fastcore.xml import to_xml
        from unittest.mock import MagicMock

        user = MagicMock()
        user.is_admin = True
        user.email = "test@test.com"
        registry = load_registry()
        counts = _compute_sidebar_counts(registry)
        html = to_xml(sidebar(user=user, current_section="to_review", counts=counts))
        assert "Help Identify" in html
        # Internal URL still uses ?section=skipped for backwards compatibility
        assert "section=skipped" in html

    def test_data_values_unchanged(self):
        """Internal state values remain 'SKIPPED' (display-only change)."""
        from core.registry import IdentityState
        assert IdentityState.SKIPPED.value == "SKIPPED"


class TestEmptyStates:
    """Tests for helpful empty state messages."""

    def test_inbox_empty_state_friendly(self):
        """Empty inbox shows a friendly message."""
        from app.main import render_to_review_section
        from fastcore.xml import to_xml

        html = to_xml(render_to_review_section(
            to_review=[], crop_files=set(),
            counts={"to_review": 0, "confirmed": 0, "skipped": 0},
            view_mode="browse", is_admin=True, sort_by="newest"
        ))
        assert "All caught up" in html

    def test_confirmed_empty_state_helpful(self):
        """Empty confirmed section suggests what to do."""
        from app.main import render_confirmed_section
        from fastcore.xml import to_xml

        html = to_xml(render_confirmed_section(
            confirmed=[], crop_files=set(),
            counts={"confirmed": 0},
            is_admin=True
        ))
        assert "Browse the inbox" in html

    def test_skipped_empty_state_helpful(self):
        """Empty skipped section shows helpful guidance."""
        from app.main import render_skipped_section
        from fastcore.xml import to_xml

        html = to_xml(render_skipped_section(
            skipped=[], crop_files=set(),
            counts={"skipped": 0},
            is_admin=True
        ))
        assert "inbox" in html.lower()

    def test_dismissed_empty_state_explains(self):
        """Empty dismissed section explains what goes there."""
        from app.main import render_rejected_section
        from fastcore.xml import to_xml

        html = to_xml(render_rejected_section(
            dismissed=[], crop_files=set(),
            counts={"rejected": 0},
            is_admin=True
        ))
        assert "Rejected matches" in html
