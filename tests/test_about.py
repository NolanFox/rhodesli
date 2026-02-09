"""Tests for the /about page."""

import pytest


class TestAboutPage:
    """Test the /about route."""

    def test_about_returns_200(self, client, auth_disabled):
        response = client.get("/about")
        assert response.status_code == 200

    def test_about_has_title(self, client, auth_disabled):
        response = client.get("/about")
        assert "About Rhodesli" in response.text

    def test_about_has_what_is_section(self, client, auth_disabled):
        response = client.get("/about")
        assert "What is Rhodesli" in response.text

    def test_about_has_how_to_help(self, client, auth_disabled):
        response = client.get("/about")
        assert "How to Help" in response.text

    def test_about_has_faq(self, client, auth_disabled):
        response = client.get("/about")
        assert "Frequently Asked Questions" in response.text

    def test_about_has_undo_info(self, client, auth_disabled):
        """FAQ should explain that merges can be undone."""
        response = client.get("/about")
        assert "undo" in response.text.lower() or "Undo" in response.text

    def test_about_has_skip_explanation(self, client, auth_disabled):
        """FAQ should explain what Skip means."""
        response = client.get("/about")
        assert "Skip" in response.text

    def test_about_has_back_link(self, client, auth_disabled):
        """About page should link back to the archive."""
        response = client.get("/about")
        assert 'href="/"' in response.text

    def test_about_has_live_stats(self, client, auth_disabled):
        """About page should include live archive statistics."""
        response = client.get("/about")
        assert "photographs" in response.text or "photos" in response.text

    def test_landing_footer_links_to_about(self, client, auth_disabled):
        """Landing page footer should link to /about."""
        response = client.get("/")
        assert "/about" in response.text
