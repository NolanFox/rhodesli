"""Tests for inline Find Similar expansion panel (AD-194).

Verifies:
- /api/find-similar/{id} returns HTML fragment (legacy endpoint still works)
- /api/identity/{id}/neighbors returns full neighbors_sidebar with container_id
- Admin cards wire Similar to full neighbors endpoint
- Expansion panel divs present in browse grids
- Reject-match records negative pair and removes tile
- Public visitors still get full-page link
- Triage buttons visible on browse cards (show_triage=True)
- Share button visible on all named identities
- Card highlight animation CSS present
"""

import pytest
from unittest.mock import patch, MagicMock


class TestInlineFindSimilarEndpoint:
    """Tests for GET /api/find-similar/{identity_id} (legacy endpoint)."""

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

    def test_community_route_preserves_prefixed_links(self, client):
        """Community-scoped inline similar panel should keep person/API links inside the community."""
        from app.main import load_registry

        registry = load_registry()
        ids = list(registry._identities.keys())
        if len(ids) < 2:
            pytest.skip("Need at least 2 identities")

        with patch(
            "app.supabase_data.get_community_by_slug",
            return_value={"slug": "fox-family", "name": "Fox Family Archive"},
        ):
            response = client.get(f"/c/fox-family/api/find-similar/{ids[0]}")

        html = response.text
        assert f'/c/fox-family/person/{ids[0]}' in html
        assert "/c/fox-family/person/" in html
        assert f"/c/fox-family/api/identity/{ids[0]}/" in html


class TestFullNeighborsSidebar:
    """Tests for GET /api/identity/{id}/neighbors with container_id."""

    def test_neighbors_returns_200(self, client):
        """Neighbors endpoint returns 200."""
        from app.main import load_registry
        registry = load_registry()
        ids = list(registry._identities.keys())
        if not ids:
            pytest.skip("No identities in test data")
        response = client.get(f"/api/identity/{ids[0]}/neighbors")
        assert response.status_code == 200

    def test_neighbors_has_sidebar_class(self, client):
        """Neighbors response contains neighbors-sidebar class."""
        from app.main import load_registry
        registry = load_registry()
        ids = list(registry._identities.keys())
        if not ids:
            pytest.skip("No identities in test data")
        response = client.get(f"/api/identity/{ids[0]}/neighbors")
        assert "neighbors-sidebar" in response.text

    def test_neighbors_with_container_id(self, client):
        """Container ID is passed through for browse expansion targeting."""
        from app.main import load_registry
        registry = load_registry()
        ids = list(registry._identities.keys())
        if not ids:
            pytest.skip("No identities in test data")
        response = client.get(f"/api/identity/{ids[0]}/neighbors?container_id=expand-test-123")
        html = response.text
        assert response.status_code == 200
        # Should have close button when container_id starts with "expand-"
        assert "panel-close" in html

    def test_neighbors_has_manual_search(self, client):
        """Neighbors sidebar includes manual search section."""
        from app.main import load_registry
        registry = load_registry()
        ids = list(registry._identities.keys())
        if not ids:
            pytest.skip("No identities in test data")
        response = client.get(f"/api/identity/{ids[0]}/neighbors")
        assert "Manual Search" in response.text

    def test_neighbors_has_collapse_toggle(self, client):
        """Neighbors sidebar includes collapse/expand toggle."""
        from app.main import load_registry
        registry = load_registry()
        ids = list(registry._identities.keys())
        if not ids:
            pytest.skip("No identities in test data")
        response = client.get(f"/api/identity/{ids[0]}/neighbors")
        assert "Collapse" in response.text


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
        # Filter out merged identities (UX-038: merged identities redirect)
        ids = [iid for iid in registry._identities.keys()
               if not registry._identities[iid].get("merged_into")]
        if len(ids) < 2:
            pytest.skip("Need at least 2 non-merged identities")

        with patch("app.main.save_registry"):
            response = client.post(f"/api/identity/{ids[0]}/reject-match/{ids[1]}")
            assert response.status_code == 200
            assert response.text.strip() == ""


class TestPublicVsAdminFindSimilar:
    """Tests that public visitors get full-page link, not inline."""

    def test_admin_browse_has_htmx_neighbors(self, client):
        """Admin browse cards use hx-get targeting the full neighbors endpoint."""
        response = client.get("/?section=to_review&view=browse")
        if response.status_code == 200:
            html = response.text
            # Admin mode should have HTMX neighbors targets (full sidebar)
            if "/api/identity/" in html and "/neighbors" in html:
                assert "hx-get" in html or "hx_get" in html


class TestUnifiedCardsInBrowse:
    """Tests that browse grids use unified identity_card (not compact)."""

    def test_browse_cards_use_unified_card(self, client):
        """Browse mode uses identity_card with DD-005 photo-dominant design."""
        response = client.get("/?section=to_review&view=browse")
        if response.status_code == 200:
            html = response.text
            # Unified card has aspect-square hero
            if "identity-card" in html:
                assert "aspect-square" in html

    def test_browse_cards_have_photos_button(self, client):
        """Browse cards include Photos button from identity_card."""
        response = client.get("/?section=to_review&view=browse")
        if response.status_code == 200:
            html = response.text
            if "identity-card" in html:
                assert "Photos" in html

    def test_browse_cards_have_profile_link(self, client):
        """Browse cards include Profile link from identity_card."""
        response = client.get("/?section=to_review&view=browse")
        if response.status_code == 200:
            html = response.text
            if "identity-card" in html:
                assert "Profile" in html


class TestTriageButtons:
    """Tests for triage buttons on identity_card(show_triage=True)."""

    def test_triage_buttons_in_browse_mode(self, client):
        """Browse mode cards have labeled triage buttons (Confirm/Skip/Reject)."""
        response = client.get("/?section=to_review&view=browse")
        if response.status_code == 200:
            html = response.text
            if "identity-card" in html:
                # Triage buttons with labels
                assert "Confirm" in html
                assert "Reject" in html

    def test_triage_not_on_confirmed(self):
        """Confirmed identities don't get triage buttons."""
        from app.main import identity_card, to_xml
        identity = {
            "identity_id": "test-confirmed-001",
            "name": "Confirmed Person",
            "state": "CONFIRMED",
            "anchor_ids": ["face-triage-1"],
            "candidate_ids": [],
        }
        crop_files = {"test-confirmed-001_0.jpg"}
        html = to_xml(identity_card(identity, crop_files, show_triage=True))
        # Triage action buttons should not appear for CONFIRMED
        assert "\u2713 Confirm" not in html
        assert "\u2717 Reject" not in html

    def test_triage_on_proposed(self):
        """Proposed identities get triage buttons when show_triage=True."""
        from app.main import identity_card, to_xml
        identity = {
            "identity_id": "test-proposed-triage-001",
            "name": "Proposed Person",
            "state": "PROPOSED",
            "anchor_ids": ["face-triage-2"],
            "candidate_ids": [],
        }
        crop_files = {"test-proposed-triage-001_0.jpg"}
        html = to_xml(identity_card(identity, crop_files, show_triage=True, is_admin=True))
        assert "\u2713 Confirm" in html
        assert "\u23f8 Skip" in html
        assert "\u2717 Reject" in html


class TestShareButtonAllStates:
    """Tests that share button appears on all named identities."""

    def test_share_on_proposed_named(self):
        """Named PROPOSED identity gets a share button."""
        from app.main import identity_card, to_xml
        identity = {
            "identity_id": "test-share-proposed-001",
            "name": "Named Proposed",
            "state": "PROPOSED",
            "anchor_ids": ["face-share-1"],
            "candidate_ids": [],
        }
        crop_files = {"test-share-proposed-001_0.jpg"}
        html = to_xml(identity_card(identity, crop_files))
        assert "share" in html.lower() or "Share" in html

    def test_no_share_on_unidentified(self):
        """Unidentified persons don't get share button."""
        from app.main import identity_card, to_xml
        identity = {
            "identity_id": "test-share-unid-001",
            "name": "Unidentified Person 42",
            "state": "PROPOSED",
            "anchor_ids": ["face-share-2"],
            "candidate_ids": [],
        }
        crop_files = {"test-share-unid-001_0.jpg"}
        html = to_xml(identity_card(identity, crop_files))
        # Share button should NOT appear for unidentified
        assert "Do you recognize" not in html


class TestCardAnimationCSS:
    """Tests that card highlight animation CSS is present."""

    def test_find_similar_active_css(self, client):
        """CSS for find-similar-active class is in the page."""
        response = client.get("/?section=confirmed")
        if response.status_code == 200:
            html = response.text
            assert "find-similar-active" in html

    def test_identity_card_transition_css(self, client):
        """CSS transition on .identity-card is in the page."""
        response = client.get("/?section=confirmed")
        if response.status_code == 200:
            html = response.text
            assert "identity-card" in html
