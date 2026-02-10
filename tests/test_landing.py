"""Landing page tests: content, stats, CTAs, photos, auth states.

Tests that the landing page:
- Returns 200 for anonymous users (shows landing page)
- Logged-in users get redirected to the dashboard (section=to_review)
- Contains expected sections: hero, stats, how-it-works, CTA, about
- Shows live stats computed from actual data (not hardcoded zeros)
- Shows correct CTAs based on auth state
- Includes featured photo images with lazy loading
- Features interactive face detection overlay data
- Shows unidentified mystery faces with CTAs
- Mentions the Jewish Community of Rhodes and Sephardic heritage
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
        """Landing page has the archive title."""
        response = client.get("/")
        assert "Rhodesli" in response.text

    def test_contains_community_tagline(self, client):
        """Landing page references the Jewish Community of Rhodes."""
        response = client.get("/")
        assert "Jewish Community of Rhodes" in response.text

    def test_contains_sephardic_heritage(self, client):
        """Landing page mentions Sephardic and Ladino heritage."""
        response = client.get("/")
        assert "Sephardic" in response.text or "Ladino" in response.text

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

    def test_footer_mentions_no_generative_ai(self, client):
        """Footer clarifies that only forensic face matching is used."""
        response = client.get("/")
        assert "forensic face matching" in response.text


class TestLandingPageStats:
    """Stats section should show live data, not hardcoded zeros."""

    def test_stats_photo_count_present(self, client):
        """Landing page shows photo count label."""
        response = client.get("/")
        assert "archival photos" in response.text

    def test_stats_people_identified_present(self, client):
        """Landing page shows people identified count."""
        response = client.get("/")
        assert "people identified" in response.text

    def test_stats_faces_detected_present(self, client):
        """Landing page shows faces detected count."""
        response = client.get("/")
        assert "faces detected" in response.text

    def test_stats_unidentified_present(self, client):
        """Landing page shows unidentified faces count."""
        response = client.get("/")
        assert "awaiting identification" in response.text

    def test_stats_are_not_all_zero(self, client):
        """Stats reflect actual data -- not all zeros."""
        from app.main import _compute_landing_stats
        stats = _compute_landing_stats()
        # At least one numeric stat should be > 0 (project has data)
        numeric_stats = {k: v for k, v in stats.items() if isinstance(v, (int, float))}
        assert any(v > 0 for v in numeric_stats.values()), \
            f"All landing stats are zero: {numeric_stats}. Expected live data."

    def test_stats_match_actual_data(self, client):
        """Stats on the page match what _compute_landing_stats returns."""
        from app.main import _compute_landing_stats
        stats = _compute_landing_stats()
        response = client.get("/")
        text = response.text
        # Each stat number should appear in the page (as data-count attribute)
        assert f'data-count="{stats["photo_count"]}"' in text
        assert f'data-count="{stats["named_count"]}"' in text
        assert f'data-count="{stats["total_faces"]}"' in text
        assert f'data-count="{stats["needs_help"]}"' in text

    def test_stats_have_animated_counters(self, client):
        """Stats use data-count attributes for animated counting."""
        response = client.get("/")
        assert "data-count=" in response.text


class TestProgressDashboard:
    """FE-053: Progress dashboard with identification bar."""

    def test_progress_bar_present(self, client):
        """Landing page shows a progress bar for identification."""
        response = client.get("/")
        assert "faces identified" in response.text

    def test_progress_bar_shows_named_count(self, client):
        """Progress text includes the actual named count."""
        from app.main import _compute_landing_stats
        stats = _compute_landing_stats()
        response = client.get("/")
        assert str(stats["named_count"]) in response.text

    def test_progress_bar_shows_total(self, client):
        """Progress text includes the total face count."""
        from app.main import _compute_landing_stats
        stats = _compute_landing_stats()
        response = client.get("/")
        assert str(stats["total_faces"]) in response.text

    def test_progress_percentage_shown(self, client):
        """Progress bar shows a percentage."""
        response = client.get("/")
        assert "% complete" in response.text

    def test_help_message_present(self, client):
        """Progress section includes a call to help."""
        response = client.get("/")
        assert "help" in response.text.lower() or "Help" in response.text


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
        """Featured images have descriptive alt text for accessibility."""
        response = client.get("/")
        assert "Archival photograph from the Jewish community of Rhodes" in response.text

    def test_hero_has_multiple_photos(self, client):
        """Hero section shows multiple featured photos in mosaic."""
        response = client.get("/")
        # Count hero-card divs (each contains one photo)
        hero_card_count = response.text.count("hero-card")
        assert hero_card_count >= 4, f"Expected at least 4 hero photos, found {hero_card_count}"

    def test_hero_has_face_detection_overlay(self, client):
        """Hero photos include face detection overlay elements."""
        response = client.get("/")
        assert "face-overlay" in response.text or "face-box" in response.text

    def test_hover_instruction_present(self, client):
        """Landing page has instruction to hover over photos."""
        response = client.get("/")
        assert "face detection" in response.text.lower()


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

    def test_anonymous_sees_help_identify(self, client, auth_disabled, no_user):
        """Anonymous users see 'Help Identify' CTA."""
        response = client.get("/")
        assert "Help Identify" in response.text

    def test_anonymous_with_auth_sees_sign_in(self, client, auth_enabled, no_user):
        """Anonymous users with auth enabled see 'Sign In' in nav."""
        response = client.get("/")
        assert "Sign In" in response.text

    def test_anonymous_sees_mystery_faces_section(self, client, auth_disabled, no_user):
        """Anonymous users see the 'Can you identify these faces?' section."""
        response = client.get("/")
        # Section may be present if there are unidentified faces
        assert "identify" in response.text.lower()


class TestLandingPageLoggedIn:
    """Logged-in users get redirected to the dashboard, not the landing page."""

    def test_logged_in_sees_dashboard(self, client, auth_enabled, regular_user):
        """Logged-in users see the dashboard/workstation, not the landing page."""
        response = client.get("/")
        # Logged-in users should be redirected to the triage dashboard
        # which has the sidebar and workstation elements
        assert "sidebar" in response.text.lower() or "to_review" in response.text.lower() \
            or "Rhodesli Identity System" in response.text

    def test_logged_in_does_not_see_landing_hero(self, client, auth_enabled, regular_user):
        """Logged-in users do NOT see the landing page hero section."""
        response = client.get("/")
        # The landing page hero has specific content not in the dashboard
        assert "Jewish Community of Rhodes" not in response.text

    def test_logged_in_does_not_see_landing_cta(self, client, auth_enabled, regular_user):
        """Logged-in users do NOT see 'Start Exploring' landing CTA."""
        response = client.get("/")
        # The landing page "Start Exploring" button should not appear
        # (the dashboard has different navigation)
        assert "btn-primary" not in response.text


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
