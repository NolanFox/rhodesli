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

    def test_banner_shows_people_count(self, client, auth_disabled):
        """Banner should show the People count (renamed from Confirmed)."""
        response = client.get("/?section=confirmed")
        assert "People" in response.text

    def test_banner_shows_help_identify_count(self, client, auth_disabled):
        """Banner should show the Help Identify count (renamed from Skipped)."""
        response = client.get("/?section=to_review")
        assert "Help Identify" in response.text

    def test_banner_no_duplicate_focus_mode_button(self, client, auth_disabled):
        """Banner should NOT have a standalone Focus Mode button (removed in v0.28.2).

        Focus/Browse toggle now lives in each section's header instead.
        """
        response = client.get("/?section=confirmed")
        assert response.status_code == 200
        # The "Focus Mode" CTA button was removed from the banner
        # Focus toggle is in section headers (section_header function)
        assert "admin-dashboard-banner" in response.text

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
