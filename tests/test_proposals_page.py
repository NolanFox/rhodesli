"""Tests for the admin proposals page and sidebar nav item."""

import pytest
from unittest.mock import patch

from app.auth import User


class TestProposalsPage:
    """Admin proposals page renders correctly."""

    def test_proposals_page_returns_200(self, client):
        """Proposals page returns 200 when auth is disabled."""
        response = client.get("/admin/proposals")
        assert response.status_code == 200

    def test_proposals_page_has_title(self, client):
        """Proposals page has Proposed Matches heading."""
        response = client.get("/admin/proposals")
        assert "Proposed Matches" in response.text

    def test_proposals_page_loads_list_via_htmx(self, client):
        """Proposals page loads list via HTMX on page load."""
        response = client.get("/admin/proposals")
        text = response.text
        assert "proposed-matches-list" in text
        assert "/api/proposed-matches" in text

    def test_proposals_page_requires_admin(self, client, auth_enabled, no_user):
        """Proposals page returns 401 for unauthenticated users."""
        response = client.get("/admin/proposals")
        assert response.status_code == 401

    def test_proposals_page_rejects_non_admin(self, client, auth_enabled, regular_user):
        """Proposals page returns 403 for non-admin users."""
        response = client.get("/admin/proposals")
        assert response.status_code == 403

    def test_proposals_page_has_sidebar(self, client):
        """Proposals page includes the sidebar."""
        response = client.get("/admin/proposals")
        assert 'id="sidebar"' in response.text

    def test_proposals_page_has_mobile_header(self, client):
        """Proposals page includes mobile header."""
        response = client.get("/admin/proposals")
        assert "mobile-header" in response.text


class TestSidebarProposalsLink:
    """Sidebar includes link to proposals page."""

    def test_sidebar_has_proposals_link(self, client, admin_user):
        """Admin sidebar includes Proposals nav item."""
        response = client.get("/?section=to_review")
        assert "/admin/proposals" in response.text
        assert "Proposals" in response.text

    def test_sidebar_proposals_hidden_for_non_admin(self, client, auth_enabled, regular_user):
        """Proposals link is hidden for non-admin users."""
        response = client.get("/?section=to_review")
        assert "/admin/proposals" not in response.text
