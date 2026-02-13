"""Tests for the internal People page enhancements.

Tests cover:
- Identity cards have "Public Page" link for confirmed identities
- The link points to /person/{id}
"""

import pytest
from starlette.testclient import TestClient

from app.main import app, load_registry


@pytest.fixture
def client():
    return TestClient(app)


class TestPeoplePagePublicLinks:
    """Internal People page has links to public person pages."""

    def test_confirmed_section_has_public_page_link(self, client, auth_disabled):
        """Confirmed identity cards have 'Public Page' link."""
        response = client.get("/?section=confirmed")
        html = response.text
        # At least one confirmed identity should have a public page link
        assert "Public Page" in html

    def test_public_page_link_points_to_person_route(self, client, auth_disabled):
        """Public Page link points to /person/{id}."""
        response = client.get("/?section=confirmed")
        html = response.text
        assert "/person/" in html

    def test_public_page_link_opens_new_tab(self, client, auth_disabled):
        """Public Page link opens in a new tab."""
        response = client.get("/?section=confirmed")
        html = response.text
        # The link should have target="_blank"
        assert 'target="_blank"' in html
