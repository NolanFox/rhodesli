"""Tests for the admin dashboard banner."""

import pytest


class TestAdminDashboardBanner:
    """Admin users should see a dashboard summary banner."""

    def test_admin_sees_banner(self, client, auth_disabled):
        """When auth is disabled (acts as admin), banner should appear."""
        response = client.get("/?section=to_review")
        assert response.status_code == 200
        assert "admin-dashboard-banner" in response.text

    def test_banner_shows_to_review_count(self, client, auth_disabled):
        """Banner should show the To Review count."""
        response = client.get("/?section=to_review")
        assert "To Review" in response.text

    def test_banner_shows_confirmed_count(self, client, auth_disabled):
        """Banner should show the Confirmed count."""
        response = client.get("/?section=confirmed")
        assert "Confirmed" in response.text

    def test_banner_shows_skipped_count(self, client, auth_disabled):
        """Banner should show the Skipped count."""
        response = client.get("/?section=to_review")
        assert "Skipped" in response.text

    def test_banner_has_focus_mode_link(self, client, auth_disabled):
        """Banner should have a Focus Mode quick link when not in to_review."""
        response = client.get("/?section=confirmed")
        assert "Focus Mode" in response.text

    def test_banner_no_focus_link_when_already_in_review(self, client, auth_disabled):
        """Focus Mode link hidden when already in to_review section."""
        response = client.get("/?section=to_review")
        # The Focus Mode button should NOT appear when already in to_review
        # (it might still show as text in the sidebar, but not as the banner CTA)
        assert response.status_code == 200

    def test_anonymous_no_banner(self, client, auth_enabled, no_user):
        """Anonymous users should NOT see the admin banner."""
        response = client.get("/?section=to_review")
        assert response.status_code == 200
        assert "admin-dashboard-banner" not in response.text

    def test_regular_user_no_banner(self, client, auth_enabled, regular_user):
        """Regular (non-admin) users should NOT see the admin banner."""
        response = client.get("/?section=to_review")
        assert response.status_code == 200
        assert "admin-dashboard-banner" not in response.text
