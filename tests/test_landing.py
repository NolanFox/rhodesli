"""Landing page tests: core content, stats, auth states.

Pruned from 61 tests to ~20. Removed: duplicate nav link checks (covered by
test_smoke.py), CSS grid class assertions, redundant stat label tests.
"""



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

    def test_contains_hero_section(self, client):
        """Landing page has the hero section."""
        response = client.get("/")
        assert 'id="hero"' in response.text

    def test_contains_stats_section(self, client):
        """Landing page has the stats section."""
        response = client.get("/")
        assert 'id="stats"' in response.text


class TestLandingPageStats:
    """Stats section should show live data, not hardcoded zeros."""

    def test_stats_are_not_all_zero(self, client):
        """Stats reflect actual data -- not all zeros."""
        from app.main import _compute_landing_stats

        stats = _compute_landing_stats()
        numeric_stats = {k: v for k, v in stats.items() if isinstance(v, (int, float))}
        assert any(v > 0 for v in numeric_stats.values()), (
            f"All landing stats are zero: {numeric_stats}. Expected live data."
        )

    def test_stats_match_actual_data(self, client):
        """Stats on the page match what _compute_landing_stats returns."""
        from app.main import _compute_landing_stats

        stats = _compute_landing_stats()
        response = client.get("/")
        text = response.text
        assert f'data-count="{stats["photo_count"]}"' in text
        assert f'data-count="{stats["named_count"]}"' in text


class TestLandingPagePhotos:
    """Hero section should feature actual photos from the archive."""

    def test_hero_has_images(self, client):
        """Landing page hero section contains img tags."""
        response = client.get("/")
        assert "<img" in response.text

    def test_images_have_lazy_loading(self, client):
        """Featured images use lazy loading for performance."""
        response = client.get("/")
        assert 'loading="lazy"' in response.text

    def test_hero_has_multiple_photos(self, client):
        """Hero section shows multiple featured photos in mosaic."""
        response = client.get("/")
        hero_card_count = response.text.count("hero-card")
        assert hero_card_count >= 4, f"Expected at least 4 hero photos, found {hero_card_count}"


class TestLandingPageNavigation:
    """Landing page nav should link to key public pages."""

    def test_has_photos_link(self, client):
        """Nav has a link to the photos page."""
        response = client.get("/")
        assert 'href="/photos"' in response.text

    def test_has_people_link(self, client):
        """Nav has a link to the people page."""
        response = client.get("/")
        assert 'href="/people"' in response.text

    def test_has_compare_link(self, client):
        """Nav has a link to the compare page."""
        response = client.get("/")
        assert 'href="/tools/compare"' in response.text


class TestLandingPageAnonymous:
    """Landing page for anonymous (not logged in) visitors."""

    def test_anonymous_sees_start_exploring(self, client, auth_disabled, no_user):
        """Anonymous users see 'Start Exploring' CTA."""
        response = client.get("/")
        assert "Start Exploring" in response.text

    def test_anonymous_with_auth_sees_sign_in(self, client, auth_enabled, no_user):
        """Anonymous users with auth enabled see 'Sign In' in nav."""
        response = client.get("/")
        assert "Sign In" in response.text


class TestLandingPageLoggedIn:
    """Logged-in users get redirected to the dashboard, not the landing page."""

    def test_logged_in_sees_dashboard(self, client, auth_enabled, regular_user):
        """Logged-in users see the dashboard/workstation, not the landing page."""
        response = client.get("/")
        assert (
            "sidebar" in response.text.lower()
            or "to_review" in response.text.lower()
            or "Rhodesli Identity System" in response.text
        )


class TestWorkstationStillWorks:
    """Existing workstation functionality is preserved via section parameter."""

    def test_workstation_returns_200(self, client):
        """GET /?section=to_review returns 200."""
        response = client.get("/?section=to_review")
        assert response.status_code == 200

    def test_photos_section_returns_200(self, client):
        """GET /?section=photos returns 200."""
        response = client.get("/?section=photos")
        assert response.status_code == 200


class TestFeatureCards:
    """PRD-024: Feature entry point cards on the landing page."""

    def test_feature_cards_section_present(self, client):
        """Landing page has a feature-cards section."""
        response = client.get("/")
        assert 'data-testid="feature-cards"' in response.text

    def test_feature_cards_has_live_stats(self, client):
        """Feature cards descriptions include live stats."""
        from app.main import _compute_landing_stats

        stats = _compute_landing_stats()
        response = client.get("/")
        assert f"{stats['photo_count']} photos" in response.text


class TestLandingStatsSkippedIncluded:
    """needs_help must include SKIPPED faces."""

    def test_needs_help_includes_skipped(self):
        """_compute_landing_stats includes SKIPPED in needs_help count."""
        from app.main import _compute_landing_stats, load_registry, IdentityState

        stats = _compute_landing_stats()
        registry = load_registry()
        skipped = registry.list_identities(state=IdentityState.SKIPPED)
        skipped_unmerged = [i for i in skipped if not i.get("merged_into")]
        assert stats["needs_help"] >= len(skipped_unmerged)
