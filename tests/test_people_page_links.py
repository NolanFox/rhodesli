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

    def test_confirmed_section_has_profile_link(self, client, auth_disabled):
        """Confirmed identity cards have 'Profile' link (DD-005 compact pills)."""
        response = client.get("/?section=confirmed")
        html = response.text
        # At least one confirmed identity should have a profile link
        assert "Profile" in html

    def test_profile_link_points_to_person_route(self, client, auth_disabled):
        """Profile link points to /person/{id}."""
        response = client.get("/?section=confirmed")
        html = response.text
        assert "/person/" in html

    def test_profile_link_accessible(self, client, auth_disabled):
        """Profile link is accessible and styled as a pill button (DD-005)."""
        response = client.get("/?section=confirmed")
        html = response.text
        # Should have pill styling
        assert "rounded-full" in html
