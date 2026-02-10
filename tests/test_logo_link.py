"""Tests for logo/header linking to home page (BUG-007).

The Rhodesli logo/title in the sidebar must link to the home page.
"""

import pytest
from starlette.testclient import TestClient


class TestLogoLinksHome:
    """Rhodesli logo in sidebar must be a clickable link to /."""

    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    def test_sidebar_logo_is_link_to_home(self, client):
        """The Rhodesli header text must be inside an <a href='/'> tag."""
        response = client.get("/?section=confirmed")
        assert response.status_code == 200
        # The logo should be a link to home
        assert 'href="/"' in response.text or "href='/'" in response.text, (
            "Rhodesli logo/title must link to home page"
        )

    def test_logo_link_contains_rhodesli_text(self, client):
        """The sidebar header link to / must contain 'Rhodesli' text."""
        import re
        response = client.get("/?section=photos")
        assert response.status_code == 200
        # Find the <a> tag with href="/" that contains "Rhodesli"
        # The sidebar logo link should wrap the H1 with Rhodesli text
        pattern = r'<a[^>]*href="/"[^>]*>.*?Rhodesli.*?</a>'
        match = re.search(pattern, response.text, re.DOTALL)
        assert match, "Sidebar must have an <a href='/'> link containing 'Rhodesli'"
