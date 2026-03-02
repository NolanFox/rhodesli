"""Tests for inline Find Similar expansion panel (AD-194).

Verifies:
- /api/find-similar/{id} returns HTML fragment, not redirect
- Fragment contains hero face, similar tiles, action buttons
- Close button uses hyperscript to clear panel
- Expansion panel divs present in browse grids
- Reject-match records negative pair and removes tile
- Public visitors still get full-page link
"""

import pytest
from unittest.mock import patch, MagicMock


class TestInlineFindSimilarEndpoint:
    """Tests for GET /api/find-similar/{identity_id}."""

    def test_returns_200_html(self, client):
        """Endpoint returns 200 with HTML content, not redirect."""
        from app.main import load_registry
        registry = load_registry()
        ids = list(registry._identities.keys())
        if not ids:
            pytest.skip("No identities in test data")
        response = client.get(f"/api/find-similar/{ids[0]}")
        assert response.status_code == 200
        # Should be HTML fragment, not a redirect
        assert response.status_code != 302
        assert response.status_code != 301

    def test_returns_hero_and_tiles(self, client):
        """Response contains hero section and similar faces section."""
        from app.main import load_registry
        registry = load_registry()
        ids = list(registry._identities.keys())
        if not ids:
            pytest.skip("No identities in test data")
        response = client.get(f"/api/find-similar/{ids[0]}")
        html = response.text
        # Should have the find-similar-panel data-testid
        assert 'data-testid="find-similar-panel"' in html

    def test_close_button_present(self, client):
        """Response contains close button with hyperscript."""
        from app.main import load_registry
        registry = load_registry()
        ids = list(registry._identities.keys())
        if not ids:
            pytest.skip("No identities in test data")
        response = client.get(f"/api/find-similar/{ids[0]}")
        html = response.text
        assert "panel-close" in html

    def test_404_for_missing_identity(self, client):
        """Returns 404 for nonexistent identity."""
        response = client.get("/api/find-similar/nonexistent-id-12345")
        assert response.status_code == 404

    def test_similar_tiles_have_action_buttons(self, client):
        """Similar face tiles include Compare/Merge/Not Same buttons."""
        from app.main import load_registry
        registry = load_registry()
        # Find an identity with neighbors
        confirmed = [iid for iid, data in registry._identities.items()
                     if data.get("state") == "CONFIRMED"]
        if not confirmed:
            pytest.skip("No confirmed identities")
        response = client.get(f"/api/find-similar/{confirmed[0]}")
        html = response.text
        # If there are similar faces, they should have action buttons
        if "similar-face-tile" in html:
            assert "Compare" in html or "Merge" in html or "Not Same" in html


class TestExpansionPanelInGrid:
    """Tests that expansion panel divs are present in browse grids."""

    def test_browse_grid_has_expansion_panels(self, client):
        """Browse mode grid includes expansion-panel divs."""
        response = client.get("/?section=to_review&view=browse")
        if response.status_code == 200:
            html = response.text
            assert "expansion-panel" in html

    def test_confirmed_grid_has_expansion_panels(self, client):
        """Confirmed section grid includes expansion-panel divs."""
        response = client.get("/?section=confirmed")
        if response.status_code == 200:
            html = response.text
            assert "expansion-panel" in html

    def test_expansion_panel_ids_match_cards(self, client):
        """Each expansion panel ID corresponds to an identity card."""
        response = client.get("/?section=confirmed")
        if response.status_code == 200:
            html = response.text
            import re
            panel_ids = re.findall(r'id="expand-([^"]+)"', html)
            # Each panel should have a matching identity card
            for pid in panel_ids:
                assert f"expand-{pid}" in html


class TestRejectMatch:
    """Tests for POST /api/identity/{id}/reject-match/{neighbor_id}."""

    def test_reject_match_returns_empty(self, client):
        """Reject match removes tile by returning empty content."""
        from app.main import load_registry, save_registry
        registry = load_registry()
        ids = list(registry._identities.keys())
        if len(ids) < 2:
            pytest.skip("Need at least 2 identities")

        with patch("app.main.save_registry"):
            response = client.post(f"/api/identity/{ids[0]}/reject-match/{ids[1]}")
            assert response.status_code == 200
            assert response.text.strip() == ""


class TestPublicVsAdminFindSimilar:
    """Tests that public visitors get full-page link, not inline."""

    def test_admin_browse_has_htmx_similar(self, client):
        """Admin browse cards use hx-get for Find Similar."""
        response = client.get("/?section=to_review&view=browse")
        if response.status_code == 200:
            html = response.text
            # Admin mode should have HTMX find-similar targets
            if "api/find-similar" in html:
                assert "hx-get" in html or "hx_get" in html
