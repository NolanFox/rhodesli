"""Landing page tests: content, stats, CTAs, photos, auth states.

Tests that the landing page:
- Returns 200 for all users (anonymous and logged-in)
- Contains expected sections: hero, stats, how-it-works, CTA, about
- Shows live stats computed from actual data (not hardcoded zeros)
- Shows correct CTAs based on auth state
- Includes featured photo images with lazy loading
- Works for anonymous users (no auth required)
- Works for logged-in users (shows different CTA)
"""

import pytest
from unittest.mock import patch


class TestLandingPageBasics:
    """Landing page should return 200 and contain core elements."""

    def test_returns_200(self, client):
        """GET / returns 200 OK."""
        response = client.get("/")
        assert response.status_code == 200

    def test_contains_title(self, client):
        """Landing page has the family archive title."""
        response = client.get("/")
        assert "Rhodesli" in response.text

    def test_contains_family_tagline(self, client):
        """Landing page has the family-oriented tagline."""
        response = client.get("/")
        assert "Rhodes-Capeluto" in response.text

    def test_contains_hero_section(self, client):
        """Landing page has the hero section."""
        response = client.get("/")
        assert 'id="hero"' in response.text

    def test_contains_stats_section(self, client):
        """Landing page has the stats section."""
        response = client.get("/")
        assert 'id="stats"' in response.text

    def test_contains_how_it_works_section(self, client):
        """Landing page has the how-it-works section."""
        response = client.get("/")
        assert 'id="how-it-works"' in response.text

    def test_contains_about_section(self, client):
        """Landing page has the about section."""
        response = client.get("/")
        assert 'id="about"' in response.text

    def test_contains_cta_section(self, client):
        """Landing page has a call-to-action section."""
        response = client.get("/")
        assert 'id="cta"' in response.text

    def test_does_not_contain_tech_jargon(self, client):
        """Landing page avoids technical jargon inappropriate for family members."""
        response = client.get("/")
        text = response.text.lower()
        # Should not have "identity system" as a visible heading
        # (it's OK in HTML attributes or code comments)
        assert "forensic" not in text or "forensic" in text.split("<!--")[0] is False


class TestLandingPageStats:
    """Stats section should show live data, not hardcoded zeros."""

    def test_stats_photo_count_present(self, client):
        """Landing page shows photo count."""
        response = client.get("/")
        assert "photos preserved" in response.text

    def test_stats_people_identified_present(self, client):
        """Landing page shows people identified count."""
        response = client.get("/")
        assert "people identified" in response.text

    def test_stats_faces_detected_present(self, client):
        """Landing page shows faces detected count."""
        response = client.get("/")
        assert "faces detected" in response.text

    def test_stats_faces_need_help_present(self, client):
        """Landing page shows faces needing help count."""
        response = client.get("/")
        assert "faces need your help" in response.text

    def test_stats_are_not_all_zero(self, client):
        """Stats reflect actual data -- not all zeros."""
        response = client.get("/")
        text = response.text
        # At minimum, photo_count should be nonzero if data exists
        # The stat cards show the number in a div before the label
        # Check that at least one stat is a nonzero number
        from app.main import _compute_landing_stats
        stats = _compute_landing_stats()
        # At least one stat should be > 0 (project has data)
        assert any(v > 0 for v in stats.values()), \
            f"All landing stats are zero: {stats}. Expected live data."

    def test_stats_match_actual_data(self, client):
        """Stats on the page match what _compute_landing_stats returns."""
        from app.main import _compute_landing_stats
        stats = _compute_landing_stats()
        response = client.get("/")
        text = response.text
        # Each stat number should appear in the page
        assert str(stats["photo_count"]) in text
        assert str(stats["named_count"]) in text
        assert str(stats["total_faces"]) in text
        assert str(stats["needs_help"]) in text


class TestLandingPagePhotos:
    """Hero section should feature actual photos from the archive."""

    def test_hero_has_images(self, client):
        """Landing page hero section contains img tags."""
        response = client.get("/")
        assert "<img" in response.text

    def test_images_use_photo_urls(self, client):
        """Featured images use the app's photo URL pattern."""
        response = client.get("/")
        # In local mode, photos are served from /photos/
        # In R2 mode, from the R2 public URL
        assert "/photos/" in response.text or "r2.dev" in response.text

    def test_images_have_lazy_loading(self, client):
        """Featured images use lazy loading for performance."""
        response = client.get("/")
        assert 'loading="lazy"' in response.text

    def test_images_have_alt_text(self, client):
        """Featured images have alt text for accessibility."""
        response = client.get("/")
        assert 'alt="Rhodes-Capeluto family photo"' in response.text

    def test_hero_has_multiple_photos(self, client):
        """Hero section shows multiple featured photos."""
        response = client.get("/")
        # Count image tags in the hero section
        hero_img_count = response.text.count("Rhodes-Capeluto family photo")
        assert hero_img_count >= 6, f"Expected at least 6 hero photos, found {hero_img_count}"


class TestLandingPageNavigation:
    """Landing page nav should link to key sections of the app."""

    def test_has_photos_link(self, client):
        """Nav has a link to the photos section."""
        response = client.get("/")
        assert "?section=photos" in response.text

    def test_has_people_link(self, client):
        """Nav has a link to the confirmed identities section."""
        response = client.get("/")
        assert "?section=confirmed" in response.text

    def test_has_review_link(self, client):
        """Nav has a link to the review section."""
        response = client.get("/")
        assert "?section=to_review" in response.text


class TestLandingPageAnonymous:
    """Landing page for anonymous (not logged in) visitors."""

    def test_anonymous_sees_start_exploring(self, client, auth_disabled, no_user):
        """Anonymous users see 'Start Exploring' CTA."""
        response = client.get("/")
        assert "Start Exploring" in response.text

    def test_anonymous_with_auth_sees_join(self, client, auth_enabled, no_user):
        """Anonymous users with auth enabled see 'Join the Project' CTA."""
        response = client.get("/")
        assert "Join the Project" in response.text

    def test_anonymous_with_auth_sees_sign_in(self, client, auth_enabled, no_user):
        """Anonymous users with auth enabled see 'Sign In' in nav."""
        response = client.get("/")
        assert "Sign In" in response.text


class TestLandingPageLoggedIn:
    """Landing page for logged-in users."""

    def test_logged_in_sees_continue_reviewing(self, client, auth_enabled, regular_user):
        """Logged-in users see 'Continue Reviewing' CTA."""
        response = client.get("/")
        assert "Continue Reviewing" in response.text

    def test_logged_in_sees_browse_photos(self, client, auth_enabled, regular_user):
        """Logged-in users see 'Browse Photos' secondary CTA."""
        response = client.get("/")
        assert "Browse Photos" in response.text

    def test_logged_in_does_not_see_join(self, client, auth_enabled, regular_user):
        """Logged-in users do NOT see 'Join the Project'."""
        response = client.get("/")
        assert "Join the Project" not in response.text


class TestWorkstationStillWorks:
    """Existing workstation functionality is preserved via section parameter."""

    def test_workstation_returns_200(self, client):
        """GET /?section=to_review returns 200."""
        response = client.get("/?section=to_review")
        assert response.status_code == 200

    def test_workstation_has_sidebar(self, client):
        """Workstation page has the sidebar navigation."""
        response = client.get("/?section=to_review")
        assert "sidebar" in response.text.lower()

    def test_workstation_has_identity_system_title(self, client):
        """Workstation page has 'Rhodesli Identity System' title."""
        response = client.get("/?section=to_review")
        assert "Rhodesli Identity System" in response.text

    def test_photos_section_returns_200(self, client):
        """GET /?section=photos returns 200."""
        response = client.get("/?section=photos")
        assert response.status_code == 200

    def test_confirmed_section_returns_200(self, client):
        """GET /?section=confirmed returns 200."""
        response = client.get("/?section=confirmed")
        assert response.status_code == 200

    def test_skipped_section_returns_200(self, client):
        """GET /?section=skipped returns 200."""
        response = client.get("/?section=skipped")
        assert response.status_code == 200

    def test_rejected_section_returns_200(self, client):
        """GET /?section=rejected returns 200."""
        response = client.get("/?section=rejected")
        assert response.status_code == 200
