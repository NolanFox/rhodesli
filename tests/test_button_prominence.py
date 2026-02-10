"""
Tests for button prominence: View All Photos and Find Similar are styled buttons.
"""

import pytest
from starlette.testclient import TestClient
from unittest.mock import patch


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


class TestButtonProminence:
    """View All Photos and Find Similar should be visible styled buttons."""

    def test_view_all_photos_is_styled_button(self, client):
        """View All Photos renders as a styled button in the identity detail view."""
        with patch("app.main.is_auth_enabled", return_value=False):
            # Get the confirmed section which shows identity cards
            response = client.get("/?section=confirmed")
            assert response.status_code == 200
            html = response.text
            if "View All Photos" in html:
                # Should have button styling (bg, border, rounded) not just underline
                idx = html.index("View All Photos")
                # Check surrounding context for button styling
                context = html[max(0, idx - 200):idx + 50]
                assert "border" in context
                assert "rounded" in context

    def test_find_similar_is_styled_button(self, client):
        """Find Similar renders as a styled button in the identity detail view."""
        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get("/?section=confirmed")
            assert response.status_code == 200
            html = response.text
            if "Find Similar" in html:
                idx = html.index("Find Similar")
                context = html[max(0, idx - 200):idx + 50]
                assert "border" in context
                assert "rounded" in context

    def test_buttons_not_underline_text(self, client):
        """Buttons should NOT be styled as underline text links."""
        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get("/?section=confirmed")
            html = response.text
            if "View All Photos" in html:
                idx = html.index("View All Photos")
                context = html[max(0, idx - 200):idx + 50]
                # Should NOT be just an underline text link
                assert "underline" not in context
