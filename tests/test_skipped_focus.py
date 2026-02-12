"""Tests for Needs Help (Skipped) Focus Mode.

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
    """Verify the Focus Mode renders correctly for Needs Help section."""

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
    """Verify Focus/Browse toggle works for Needs Help section."""

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
             }):
            sorted_list = _sort_skipped_by_actionability(identities)
            assert sorted_list[0]["identity_id"] == "skip-high"

    def test_actionability_sorting_no_proposals(self, client):
        """Without proposals, both identities are in the same tier."""
        from app.main import _sort_skipped_by_actionability

        identities = self._mock_skipped_identities()

        with patch("app.main._get_identities_with_proposals", return_value=set()):
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
