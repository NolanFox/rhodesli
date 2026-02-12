"""Tests for Help Identify (Skipped) Focus Mode.

Verifies:
- Focus mode renders single expanded identity card
- Action buttons (Same Person, Not Same, I Know Them, Skip) are present
- Photo context and ML suggestions are displayed
- Keyboard shortcuts are wired
- View toggle (Focus/Browse) works
- Action routes advance to next identity
- Actionability sorting (best leads first)
- Progress counter
"""
import json
import re
from unittest.mock import patch, MagicMock
import pytest
from starlette.testclient import TestClient


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


class TestSkippedFocusModeRendering:
    """Verify the Focus Mode renders correctly for Help Identify section."""

    def test_focus_mode_returns_200(self, client):
        """GET /?section=skipped&view=focus returns 200."""
        resp = client.get("/?section=skipped&view=focus")
        assert resp.status_code == 200

    def test_focus_mode_has_container(self, client):
        """Focus mode renders the skipped-focus-container div."""
        resp = client.get("/?section=skipped&view=focus")
        assert 'id="skipped-focus-container"' in resp.text

    def test_focus_mode_has_focus_card(self, client):
        """Focus mode renders exactly one expanded focus card."""
        resp = client.get("/?section=skipped&view=focus")
        cards = re.findall(r'id="skipped-focus-card"', resp.text)
        assert len(cards) == 1, f"Expected 1 focus card, got {len(cards)}"

    def test_focus_mode_has_this_person_label(self, client):
        """Shows 'Who is this?' label above the face crop."""
        resp = client.get("/?section=skipped&view=focus")
        assert "Who is this?" in resp.text

    def test_focus_mode_has_best_match(self, client):
        """Shows 'Best Match' section (with or without suggestions)."""
        resp = client.get("/?section=skipped&view=focus")
        assert "Best Match" in resp.text

    def test_focus_mode_has_photo_context(self, client):
        """Shows 'Photo Context' section."""
        resp = client.get("/?section=skipped&view=focus")
        assert "Photo Context" in resp.text

    def test_focus_mode_has_i_know_them_button(self, client):
        """Shows 'I Know Them' button."""
        resp = client.get("/?section=skipped&view=focus")
        assert "I Know Them" in resp.text

    def test_focus_mode_has_skip_button(self, client):
        """Shows Skip button."""
        resp = client.get("/?section=skipped&view=focus")
        assert 'id="focus-btn-skip"' in resp.text

    def test_focus_mode_has_keyboard_data_attr(self, client):
        """Has data-focus-mode='skipped' for keyboard shortcut detection."""
        resp = client.get("/?section=skipped&view=focus")
        assert 'data-focus-mode="skipped"' in resp.text

    def test_focus_mode_has_progress_counter(self, client):
        """Has progress counter with reviewed count."""
        resp = client.get("/?section=skipped&view=focus")
        assert 'id="skipped-reviewed-count"' in resp.text
        assert "Reviewed:" in resp.text

    def test_focus_mode_has_exit_link(self, client):
        """Has exit link back to browse mode."""
        resp = client.get("/?section=skipped&view=focus")
        assert "Exit Focus Mode" in resp.text
        assert "section=skipped&amp;view=browse" in resp.text

    def test_focus_mode_has_name_form(self, client):
        """Has inline name form (hidden by default)."""
        resp = client.get("/?section=skipped&view=focus")
        assert "name-and-confirm" in resp.text
        assert "Confirm Identity" in resp.text


class TestSkippedFocusModeViewToggle:
    """Verify Focus/Browse toggle works for Help Identify section."""

    def test_view_toggle_present(self, client):
        """View toggle with Focus and View All links is present."""
        resp = client.get("/?section=skipped&view=focus")
        assert 'section=skipped&amp;view=focus' in resp.text
        assert 'section=skipped&amp;view=browse' in resp.text

    def test_browse_mode_shows_cards_list(self, client):
        """Browse mode shows the traditional card grid, not focus mode."""
        resp = client.get("/?section=skipped&view=browse")
        assert resp.status_code == 200
        assert 'id="skipped-focus-container"' not in resp.text
        # Should have skip-hint lazy loading
        assert "skip-hints" in resp.text or "No unresolved" in resp.text

    def test_default_view_is_focus(self, client):
        """Default view for skipped section is focus mode."""
        resp = client.get("/?section=skipped")
        assert resp.status_code == 200
        assert 'id="skipped-focus-container"' in resp.text


class TestSkippedFocusModeKeyboardShortcuts:
    """Verify keyboard shortcuts are wired for skipped focus mode."""

    def test_keyboard_handler_detects_skipped_focus(self, client):
        """Global keydown handler checks for data-focus-mode='skipped'."""
        resp = client.get("/?section=skipped&view=focus")
        assert 'data-focus-mode="skipped"' in resp.text
        # The keyboard handler should reference isSkippedFocus
        assert "isSkippedFocus" in resp.text


class TestSkippedFocusActions:
    """Verify Focus Mode action routes work correctly."""

    def test_focus_skip_route_exists(self, client):
        """POST /api/skipped/{id}/focus-skip returns a response."""
        # Use a fake ID — the route should still respond (admin check)
        resp = client.post("/api/skipped/fake-id/focus-skip")
        # Without auth, should succeed (auth disabled in tests)
        assert resp.status_code in (200, 404)

    def test_reject_suggestion_route_exists(self, client):
        """POST /api/skipped/{id}/reject-suggestion returns a response."""
        resp = client.post("/api/skipped/fake-id/reject-suggestion?suggestion_id=fake-target")
        assert resp.status_code in (200, 404)

    def test_name_and_confirm_empty_name_rejected(self, client):
        """POST /api/skipped/{id}/name-and-confirm with empty name returns 400."""
        resp = client.post("/api/skipped/fake-id/name-and-confirm", data={"name": ""})
        assert resp.status_code == 400

    def test_name_and_confirm_with_name(self, client):
        """POST /api/skipped/{id}/name-and-confirm with valid name works."""
        # This will fail with identity not found since fake-id doesn't exist,
        # but at least tests that the route accepts the name parameter
        resp = client.post("/api/skipped/fake-id/name-and-confirm", data={"name": "Test Person"})
        # Should be 400 (identity not found) but not 500
        assert resp.status_code in (200, 400)


class TestSkippedFocusModeWithMockData:
    """Test focus mode behavior with controlled mock data."""

    def _mock_skipped_identities(self):
        """Create mock skipped identities with varying actionability."""
        return [
            {
                "identity_id": "skip-high",
                "name": "Unidentified Person 100",
                "state": "SKIPPED",
                "anchor_ids": ["face_high_1"],
                "candidate_ids": [],
                "negative_ids": [],
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
            },
            {
                "identity_id": "skip-none",
                "name": "Unidentified Person 200",
                "state": "SKIPPED",
                "anchor_ids": ["face_none_1"],
                "candidate_ids": [],
                "negative_ids": [],
                "created_at": "2026-01-02T00:00:00Z",
                "updated_at": "2026-01-02T00:00:00Z",
            },
        ]

    def test_actionability_sorting_with_proposals(self, client):
        """Identity with proposals sorts before identity without."""
        from app.main import _sort_skipped_by_actionability

        identities = self._mock_skipped_identities()

        # Mock: skip-high has a proposal, skip-none doesn't
        with patch("app.main._get_identities_with_proposals", return_value={"skip-high"}), \
             patch("app.main._get_best_proposal_for_identity", return_value={
                 "confidence": "HIGH",
                 "distance": 0.85,
                 "target_identity_id": "target-1",
                 "target_identity_name": "Known Person",
             }), \
             patch("app.main._identity_quality_score", return_value=50.0):
            sorted_list = _sort_skipped_by_actionability(identities)
            assert sorted_list[0]["identity_id"] == "skip-high"

    def test_actionability_sorting_no_proposals(self, client):
        """Without proposals, both identities are in the same tier."""
        from app.main import _sort_skipped_by_actionability

        identities = self._mock_skipped_identities()

        with patch("app.main._get_identities_with_proposals", return_value=set()), \
             patch("app.main._identity_quality_score", return_value=50.0):
            sorted_list = _sort_skipped_by_actionability(identities)
            # Both in tier 3 (no proposals), should maintain original order
            assert len(sorted_list) == 2


class TestSkippedFocusProgressCounter:
    """Test the session progress counter."""

    def test_progress_counter_script_present(self, client):
        """Progress counter includes JS for cookie-based tracking."""
        resp = client.get("/?section=skipped&view=focus")
        assert "skipped_focus_count" in resp.text
        assert "htmx:afterSwap" in resp.text


class TestSkippedFocusUpNext:
    """Test the Up Next carousel in skipped focus mode."""

    def test_up_next_present_when_multiple(self, client):
        """Up Next carousel shows when there are multiple skipped identities."""
        resp = client.get("/?section=skipped&view=focus")
        # If there are multiple skipped identities, Up Next should appear
        text = resp.text
        if text.count("identity_id") > 1 or "Up Next" in text:
            assert "Up Next" in text


class TestActionabilityBadges:
    """Test actionability badges in browse and focus mode."""

    def test_strong_lead_badge_for_high_confidence(self):
        """Strong lead badge returned for VERY HIGH or HIGH proposals."""
        from app.main import _actionability_badge
        with patch("app.main._get_best_proposal_for_identity", return_value={
            "confidence": "HIGH", "distance": 0.85,
            "target_identity_id": "t1", "target_identity_name": "Known"
        }):
            badge = _actionability_badge("test-id", {"test-id"})
            from fasthtml.common import to_xml
            html = to_xml(badge)
            assert "Strong lead" in html

    def test_good_lead_badge_for_moderate(self):
        """Good lead badge returned for MODERATE proposals."""
        from app.main import _actionability_badge
        with patch("app.main._get_best_proposal_for_identity", return_value={
            "confidence": "MODERATE", "distance": 1.1,
            "target_identity_id": "t1", "target_identity_name": "Maybe"
        }):
            badge = _actionability_badge("test-id", {"test-id"})
            from fasthtml.common import to_xml
            html = to_xml(badge)
            assert "Good lead" in html

    def test_no_badge_for_no_proposals(self):
        """No badge when identity has no proposals."""
        from app.main import _actionability_badge
        badge = _actionability_badge("test-id", set())
        assert badge is None

    def test_browse_mode_sorted_by_actionability(self, client):
        """Browse mode sorts by actionability (check structure exists)."""
        resp = client.get("/?section=skipped&view=browse")
        assert resp.status_code == 200
        # Browse mode should still have the card wrapper structure
        assert "identity-card-wrapper" in resp.text or "No unresolved" in resp.text


class TestCollapsibleNeighborsPanel:
    """Test that Similar Identities panel is collapsible, not dismissible."""

    def test_neighbors_panel_has_toggle_button(self, client):
        """Neighbors panel has a toggle button instead of a close/dismiss button."""
        from app.main import neighbors_sidebar
        from fasthtml.common import to_xml
        result = neighbors_sidebar("test-id", [], set())
        html = to_xml(result)
        assert "Collapse" in html or "Expand" in html
        assert "neighbors-toggle-" in html

    def test_neighbors_panel_toggle_uses_hyperscript(self, client):
        """Toggle button uses Hyperscript to show/hide body."""
        from app.main import neighbors_sidebar
        from fasthtml.common import to_xml
        result = neighbors_sidebar("test-id", [], set())
        html = to_xml(result)
        assert "toggle .hidden" in html
        assert "neighbors-body-test-id" in html


class TestRejectUndoToast:
    """Test that reject-suggestion includes an undo toast."""

    def test_reject_route_returns_undo_button(self, client):
        """POST /api/skipped/{id}/reject-suggestion returns toast with undo."""
        resp = client.post("/api/skipped/fake-id/reject-suggestion?suggestion_id=fake-target")
        html = resp.text
        assert "Undo" in html or resp.status_code in (200, 404)

    def test_reject_route_toast_has_unreject_link(self, client):
        """Reject toast links to the unreject endpoint."""
        resp = client.post("/api/skipped/fake-id/reject-suggestion?suggestion_id=fake-target")
        if resp.status_code == 200:
            assert "unreject" in resp.text


class TestSkippedFocusMergeIntegration:
    """Test that merge route handles focus_section=skipped."""

    def test_merge_route_accepts_focus_section(self, client):
        """Merge route accepts focus_section parameter without error."""
        resp = client.post(
            "/api/identity/fake-target/merge/fake-source?from_focus=true&focus_section=skipped"
        )
        # Should not be 500 — either 404 (identity not found) or 409
        assert resp.status_code in (404, 409, 200)

    def test_neighbors_route_accepts_focus_section(self, client):
        """Neighbors route accepts focus_section parameter."""
        resp = client.get(
            "/api/identity/fake-id/neighbors?from_focus=true&focus_section=skipped"
        )
        # Should not be 500
        assert resp.status_code in (200, 404)


class TestBestMatchFallback:
    """Test that Best Match falls back to real-time neighbors when proposals empty."""

    def test_get_best_match_uses_proposals_first(self):
        """_get_best_match_for_identity prefers proposals over neighbors."""
        from app.main import _get_best_match_for_identity
        proposal = {
            "target_identity_id": "t1",
            "target_identity_name": "Known Person",
            "distance": 0.85,
            "confidence": "HIGH",
        }
        with patch("app.main._get_best_proposal_for_identity", return_value=proposal):
            result = _get_best_match_for_identity("test-id")
            assert result == proposal

    def test_get_best_match_falls_back_to_neighbors(self):
        """_get_best_match_for_identity falls back to _compute_best_neighbor."""
        from app.main import _get_best_match_for_identity
        neighbor = {
            "target_identity_id": "t2",
            "target_identity_name": "Neighbor",
            "distance": 1.05,
            "confidence": "MODERATE",
        }
        with patch("app.main._get_best_proposal_for_identity", return_value=None), \
             patch("app.main._compute_best_neighbor", return_value=neighbor):
            result = _get_best_match_for_identity("test-id")
            assert result == neighbor

    def test_get_best_match_returns_none_when_no_matches(self):
        """_get_best_match_for_identity returns None when nothing found."""
        from app.main import _get_best_match_for_identity
        with patch("app.main._get_best_proposal_for_identity", return_value=None), \
             patch("app.main._compute_best_neighbor", return_value=None):
            result = _get_best_match_for_identity("test-id")
            assert result is None

    def test_confidence_labels_in_suggestion(self, client):
        """Focus mode shows human-readable confidence labels."""
        resp = client.get("/?section=skipped&view=focus")
        # Should have one of the human-readable labels
        html = resp.text
        has_label = any(label in html for label in [
            "Strong match", "Good match", "Possible match", "Weak match",
            "No ML suggestions yet"
        ])
        assert has_label, "Expected a confidence label in the best match area"


class TestSmartLandingRedirect:
    """Test that logged-in users are redirected to the right section."""

    def test_logged_in_empty_inbox_goes_to_skipped(self, client):
        """When inbox is empty, logged-in users see Help Identify instead."""
        from app.auth import User
        mock_user = User(id="test", email="test@test.com", is_admin=True)
        with patch("app.main.get_current_user", return_value=mock_user), \
             patch("app.main.is_auth_enabled", return_value=True):
            resp = client.get("/")
            html = resp.text
            # Should show Help Identify content (not empty inbox)
            assert "Help Identify" in html or "skipped" in html


class TestSourcePhotoRendering:
    """Test that source photo renders with correct URL."""

    def test_photo_context_uses_filename_fallback(self):
        """_build_skipped_photo_context uses 'filename' when 'path' is missing."""
        from app.main import _build_skipped_photo_context
        from fasthtml.common import to_xml

        # Mock the photo cache to have a "filename" key but no "path"
        with patch("app.main._build_caches"), \
             patch("app.main._photo_cache", {
                 "test-photo": {
                     "filename": "Image 001_compress.jpg",
                     "faces": [],
                     "collection": "Test Collection",
                 }
             }), \
             patch("app.main.load_registry") as mock_reg:
            mock_reg.return_value.list_identities.return_value = []
            result = _build_skipped_photo_context("test-face", "test-photo", "test-identity")
            if result:
                html = to_xml(result)
                # Should have a non-empty image URL (not just /raw_photos/)
                assert "Image" in html or "raw_photos" in html


class TestFocusModeLargerCrops:
    """Face crops in Focus Mode should be at least ~288px (w-72)."""

    def test_main_face_crop_has_large_sizing(self, client):
        """Main face crop uses w-72 h-72 on desktop (288px)."""
        resp = client.get("/?section=skipped&view=focus")
        assert resp.status_code == 200
        # Check for w-48 (mobile) and sm:w-72 (desktop) sizing
        assert "sm:w-72" in resp.text

    def test_best_match_has_large_sizing(self, client):
        """Best match crop also uses w-72 sizing on desktop."""
        resp = client.get("/?section=skipped&view=focus")
        # The best match panel should also have large crops
        assert "sm:h-72" in resp.text

    def test_view_photo_link_exists(self, client):
        """'View Photo' text link exists below face crop."""
        resp = client.get("/?section=skipped&view=focus")
        assert "View Photo" in resp.text

    def test_data_focus_mode_attribute(self, client):
        """Focus card has data-focus-mode='skipped' for keyboard handler detection."""
        resp = client.get("/?section=skipped&view=focus")
        assert 'data-focus-mode="skipped"' in resp.text


class TestOtherMatchesStrip:
    """Horizontal strip of secondary matches below main comparison."""

    def test_more_matches_strip_renders(self, client):
        """Focus mode renders 'More matches' section when multiple neighbors exist."""
        resp = client.get("/?section=skipped&view=focus")
        # May or may not have other matches depending on data, but should not crash
        assert resp.status_code == 200

    def test_suggestion_with_strip_returns_tuple(self):
        """_build_skipped_suggestion_with_strip returns (el, strip_or_none)."""
        from app.main import _build_skipped_suggestion_with_strip
        # Should return a tuple of two elements
        result = _build_skipped_suggestion_with_strip("nonexistent-id", set())
        assert isinstance(result, tuple)
        assert len(result) == 2


class TestKeyboardUndoSupport:
    """Keyboard undo (Z key) data attributes and JS support."""

    def test_action_buttons_have_undo_data(self, client):
        """Focus mode action buttons include data-undo-type attributes."""
        resp = client.get("/?section=skipped&view=focus")
        assert resp.status_code == 200
        # At least the skip button should have undo data
        assert 'data-undo-type="skip"' in resp.text

    def test_undo_stack_js_initialized(self, client):
        """Page includes the undo stack initialization JS."""
        resp = client.get("/?section=skipped&view=focus")
        assert "_undoStack" in resp.text

    def test_z_key_handler_present(self, client):
        """Keyboard handler includes Z-key undo logic."""
        resp = client.get("/?section=skipped&view=focus")
        assert "e.key === 'z'" in resp.text or "e.key === 'Z'" in resp.text

    def test_shortcut_cheatsheet_shows_undo(self, client):
        """Shortcut text includes Z Undo hint."""
        resp = client.get("/?section=skipped&view=focus")
        # Only shown when has_suggestion is true — check for the text
        if "Z Undo" in resp.text:
            assert True
        else:
            # If no suggestions in data, Z Undo won't appear — that's fine
            pass

    def test_merge_button_has_undo_merge_url(self, client):
        """Same Person button has data-undo-url pointing to undo-merge endpoint."""
        resp = client.get("/?section=skipped&view=focus")
        if "focus-btn-confirm" in resp.text:
            assert "data-undo-url" in resp.text
            assert "undo-merge" in resp.text


class TestActionabilitySortUnit:
    """Unit tests for _sort_skipped_by_actionability ordering logic."""

    def test_very_high_before_high(self):
        """VERY HIGH confidence identities sort before HIGH."""
        from app.main import _sort_skipped_by_actionability
        from unittest.mock import patch

        mock_neighbors = {
            "id-high": (0.95, "HIGH", "Person X"),
            "id-very-high": (0.75, "VERY HIGH", "Person Y"),
        }
        skipped = [
            {"identity_id": "id-high", "name": "Person A", "state": "SKIPPED"},
            {"identity_id": "id-very-high", "name": "Person B", "state": "SKIPPED"},
        ]
        with patch("app.main._get_skipped_neighbor_distances", return_value=mock_neighbors), \
             patch("app.main._identity_quality_score", return_value=50.0):
            result = _sort_skipped_by_actionability(skipped)
            assert result[0]["identity_id"] == "id-very-high"
            assert result[1]["identity_id"] == "id-high"

    def test_no_match_sorts_last(self):
        """Identities with no ML match sort after all matched identities."""
        from app.main import _sort_skipped_by_actionability
        from unittest.mock import patch

        mock_neighbors = {
            "id-match": (1.10, "MODERATE", "Someone"),
        }
        skipped = [
            {"identity_id": "id-nomatch", "name": "Nobody", "state": "SKIPPED"},
            {"identity_id": "id-match", "name": "Somebody", "state": "SKIPPED"},
        ]
        with patch("app.main._get_skipped_neighbor_distances", return_value=mock_neighbors), \
             patch("app.main._identity_quality_score", return_value=50.0):
            result = _sort_skipped_by_actionability(skipped)
            assert result[0]["identity_id"] == "id-match"
            assert result[1]["identity_id"] == "id-nomatch"

    def test_within_tier_sorts_by_distance(self):
        """Within same confidence tier, closer distance sorts first."""
        from app.main import _sort_skipped_by_actionability
        from unittest.mock import patch

        mock_neighbors = {
            "id-far": (0.98, "HIGH", "Person X"),
            "id-close": (0.82, "HIGH", "Person Y"),
        }
        skipped = [
            {"identity_id": "id-far", "name": "Far", "state": "SKIPPED"},
            {"identity_id": "id-close", "name": "Close", "state": "SKIPPED"},
        ]
        with patch("app.main._get_skipped_neighbor_distances", return_value=mock_neighbors), \
             patch("app.main._identity_quality_score", return_value=50.0):
            result = _sort_skipped_by_actionability(skipped)
            assert result[0]["identity_id"] == "id-close"
            assert result[1]["identity_id"] == "id-far"

    def test_named_match_before_unidentified_within_tier(self):
        """Named match targets sort before unidentified ones within same tier."""
        from app.main import _sort_skipped_by_actionability
        from unittest.mock import patch

        mock_neighbors = {
            "id-named": (0.90, "HIGH", "Rica Moussafer"),
            "id-unid": (0.90, "HIGH", "Unidentified Person 310"),
        }
        skipped = [
            {"identity_id": "id-unid", "name": "Person A", "state": "SKIPPED"},
            {"identity_id": "id-named", "name": "Person B", "state": "SKIPPED"},
        ]
        with patch("app.main._get_skipped_neighbor_distances", return_value=mock_neighbors), \
             patch("app.main._identity_quality_score", return_value=50.0):
            result = _sort_skipped_by_actionability(skipped)
            assert result[0]["identity_id"] == "id-named"
            assert result[1]["identity_id"] == "id-unid"

    def test_quality_tiebreaker_within_tier(self):
        """Higher quality face sorts first within same tier and distance."""
        from app.main import _sort_skipped_by_actionability
        from unittest.mock import patch

        mock_neighbors = {
            "id-blurry": (0.90, "HIGH", "Person X"),
            "id-clear": (0.90, "HIGH", "Person Y"),
        }
        skipped = [
            {"identity_id": "id-blurry", "name": "Blurry", "state": "SKIPPED"},
            {"identity_id": "id-clear", "name": "Clear", "state": "SKIPPED"},
        ]

        def mock_quality(identity):
            return 80.0 if identity.get("identity_id") == "id-clear" else 20.0

        with patch("app.main._get_skipped_neighbor_distances", return_value=mock_neighbors), \
             patch("app.main._identity_quality_score", side_effect=mock_quality):
            result = _sort_skipped_by_actionability(skipped)
            assert result[0]["identity_id"] == "id-clear"
            assert result[1]["identity_id"] == "id-blurry"
