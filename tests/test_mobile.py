"""Mobile responsive tests: viewport meta, 404 page, favicon.

Keeps core structural tests (viewport, 404, favicon) and removes
brittle CSS class assertions (Tailwind classes change frequently).
"""



# ---------------------------------------------------------------------------
# Viewport meta tag tests — essential for mobile rendering
# ---------------------------------------------------------------------------


class TestViewportMeta:
    """Key pages must include the viewport meta tag for mobile scaling."""

    def test_landing_page_has_viewport_meta(self, client):
        """Landing page includes viewport meta tag."""
        response = client.get("/")
        assert response.status_code == 200
        assert 'name="viewport"' in response.text

    def test_workstation_has_viewport_meta(self, client):
        """Workstation page includes viewport meta tag."""
        response = client.get("/?section=to_review")
        assert response.status_code == 200
        assert 'name="viewport"' in response.text


# ---------------------------------------------------------------------------
# Styled 404 catch-all tests
# ---------------------------------------------------------------------------


class TestStyled404CatchAll:
    """Unknown routes must return a styled 404 page, not bare text."""

    def test_unknown_route_returns_404(self, client):
        """Arbitrary unknown path returns 404 status."""
        response = client.get("/nonexistent-page-xyz")
        assert response.status_code == 404

    def test_unknown_route_has_styled_page(self, client):
        """404 page has styled content, not bare text."""
        response = client.get("/nonexistent-page-xyz")
        assert "Rhodesli" in response.text
        assert "Page not found" in response.text


# ---------------------------------------------------------------------------
# Favicon tests
# ---------------------------------------------------------------------------


class TestFavicon:
    """Pages must include a favicon to prevent console 404 errors."""

    def test_landing_page_has_favicon(self, client):
        """Landing page includes favicon link."""
        response = client.get("/")
        assert 'rel="icon"' in response.text
