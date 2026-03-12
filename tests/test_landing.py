"""Tests for the neutral platform root and explicit archive entry."""


class TestPlatformRootBasics:
    """Anonymous root should be a neutral platform entry."""

    def test_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_contains_platform_root_shell(self, client):
        response = client.get("/")
        assert 'data-testid="platform-root"' in response.text
        assert "Choose an archive" in response.text

    def test_contains_archive_directory(self, client):
        response = client.get("/")
        assert 'id="archive-directory"' in response.text
        assert 'data-testid="archive-card"' in response.text

    def test_contains_explicit_rhodes_archive_path(self, client):
        response = client.get("/")
        assert 'href="/c/rhodes/"' in response.text

    def test_contains_global_tools(self, client):
        response = client.get("/")
        assert 'href="/tools/compare"' in response.text
        assert 'href="/tools/estimate"' in response.text
        assert 'href="/about"' in response.text

    def test_contains_stats_section(self, client):
        response = client.get("/")
        assert 'id="stats"' in response.text


class TestPlatformRootAuthStates:
    """Auth-specific behavior on the root route."""

    def test_anonymous_with_auth_sees_sign_in(self, client, auth_enabled, no_user):
        response = client.get("/")
        assert "Sign In" in response.text

    def test_logged_in_sees_dashboard(self, client, auth_enabled, regular_user):
        response = client.get("/")
        assert (
            "sidebar" in response.text.lower()
            or "to_review" in response.text.lower()
            or "Rhodesli Identity System" in response.text
        )


class TestExplicitArchiveEntry:
    """Explicit community prefixes should still land in a concrete archive."""

    def test_explicit_rhodes_path_shows_archive_landing(self, client):
        response = client.get("/c/rhodes/")
        assert response.status_code == 200
        assert "Jewish Community of Rhodes" in response.text
        assert 'id="hero"' in response.text

    def test_workstation_routes_still_work(self, client):
        assert client.get("/?section=to_review").status_code == 200
        assert client.get("/?section=photos").status_code == 200


class TestLandingStatsSkippedIncluded:
    """needs_help must include SKIPPED faces."""

    def test_needs_help_includes_skipped(self):
        from app.main import IdentityState, _compute_landing_stats, load_registry

        stats = _compute_landing_stats()
        registry = load_registry()
        skipped = registry.list_identities(state=IdentityState.SKIPPED)
        skipped_unmerged = [i for i in skipped if not i.get("merged_into")]
        assert stats["needs_help"] >= len(skipped_unmerged)
