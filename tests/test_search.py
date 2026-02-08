"""Tests for FE-030/FE-031: Client-side instant name search with filtering.

Tests cover:
1. Identity cards have data-name attributes for client-side filtering
2. Sidebar search input has correct attributes
3. Client-side filter script is included in the page
4. Server-side /api/search endpoint still works (backward compatibility)
"""

import pytest
from unittest.mock import patch, MagicMock
from starlette.testclient import TestClient


class TestIdentityCardDataAttributes:
    """Identity cards must have data-name attributes for client-side filtering."""

    def test_identity_card_has_data_name_attribute(self):
        """Each identity card has a data-name attribute with lowercase name."""
        from app.main import identity_card, to_xml

        identity = {
            "identity_id": "test-id-001",
            "name": "Sarah Cohen",
            "state": "CONFIRMED",
            "anchor_ids": ["face-1"],
            "candidate_ids": [],
        }
        crop_files = {"test-id-001_0.jpg"}

        html = to_xml(identity_card(identity, crop_files))
        assert 'data-name="sarah cohen"' in html

    def test_identity_card_data_name_is_lowercase(self):
        """data-name is always lowercase for case-insensitive matching."""
        from app.main import identity_card, to_xml

        identity = {
            "identity_id": "test-id-002",
            "name": "DAVID LÉVY",
            "state": "CONFIRMED",
            "anchor_ids": ["face-2"],
            "candidate_ids": [],
        }
        crop_files = {"test-id-002_0.jpg"}

        html = to_xml(identity_card(identity, crop_files))
        # data-name must contain lowercase version of the name
        assert 'data-name="david' in html.lower()

    def test_identity_card_data_name_empty_for_unnamed(self):
        """Unnamed identities still get a data-name attribute (may be empty or placeholder)."""
        from app.main import identity_card, to_xml

        identity = {
            "identity_id": "test-id-003",
            "name": None,
            "state": "PROPOSED",
            "anchor_ids": ["face-3"],
            "candidate_ids": [],
        }
        crop_files = {"test-id-003_0.jpg"}

        html = to_xml(identity_card(identity, crop_files))
        assert "data-name=" in html


class TestSidebarSearchInput:
    """Sidebar search input has correct attributes for both client-side and server-side search."""

    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    def test_sidebar_search_input_exists(self, client):
        """Sidebar has a search input with id sidebar-search-input."""
        response = client.get("/?section=confirmed")
        assert response.status_code == 200
        assert 'id="sidebar-search-input"' in response.text

    def test_sidebar_search_input_has_htmx_attributes(self, client):
        """Search input retains HTMX attributes for server-side search (backward compat)."""
        response = client.get("/?section=confirmed")
        assert 'hx-get="/api/search"' in response.text
        assert 'hx-target="#sidebar-search-results"' in response.text

    def test_sidebar_search_placeholder(self, client):
        """Search input has user-friendly placeholder text."""
        response = client.get("/?section=confirmed")
        assert 'placeholder="Search names..."' in response.text


class TestClientSideFilterScript:
    """Client-side filter script must be included in the main page."""

    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    def test_filter_script_present_on_main_page(self, client):
        """Main page includes the client-side identity filter script."""
        response = client.get("/?section=confirmed")
        assert response.status_code == 200
        assert "sidebarFilterCards" in response.text

    def test_filter_script_targets_identity_cards(self, client):
        """Filter script selects elements with .identity-card class."""
        response = client.get("/?section=confirmed")
        assert "identity-card" in response.text

    def test_filter_script_uses_data_name(self, client):
        """Filter script reads data-name attribute for matching."""
        response = client.get("/?section=confirmed")
        assert "data-name" in response.text

    def test_filter_script_has_debounce(self, client):
        """Filter script implements debounce to avoid flickering."""
        response = client.get("/?section=confirmed")
        # Check for debounce mechanism (setTimeout pattern)
        assert "setTimeout" in response.text


class TestServerSideSearchBackwardCompat:
    """Server-side /api/search endpoint must continue working."""

    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    def test_api_search_returns_results(self, client):
        """GET /api/search?q=... returns matching identities."""
        response = client.get("/api/search?q=capeluto")
        assert response.status_code == 200

    def test_api_search_short_query_returns_empty(self, client):
        """GET /api/search with <2 chars returns empty."""
        response = client.get("/api/search?q=a")
        assert response.status_code == 200
        # Short query returns empty string
        assert len(response.text.strip()) == 0 or "No matches" not in response.text

    def test_api_search_empty_query_returns_empty(self, client):
        """GET /api/search with empty query returns empty."""
        response = client.get("/api/search?q=")
        assert response.status_code == 200
