"""Tests for Help Identify (Skipped) Focus Mode.

Verifies:
- Focus mode renders and returns 200
- Action buttons are present
- View toggle (Focus/Browse) works
- Action routes work
- Actionability sorting (best leads first)
- Best match fallback logic

Pruned: CSS class assertions (crop sizing, hyperscript details, keyboard shortcut
JS strings, progress counter selectors). Kept functional behavior tests.
"""

from unittest.mock import patch
import pytest
from starlette.testclient import TestClient


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app)


def _render_path(path: str) -> str:
    """Render a route via TestClient (reset caches for xdist safety)."""
    import app.main as main

    # Reset ALL caches so data is loaded fresh from disk (xdist isolation)
    main._photo_cache = None
    main._face_to_photo_cache = None
    main._photo_id_aliases = None
    main._face_data_cache = None
    main._crop_files_cache = None
    main._skipped_neighbor_cache = None
    main._photo_registry_cache = None
    main._discovery_cache = None

    c = TestClient(main.app)
    return c.get(path).text


def _render_skipped_focus_html() -> str:
    """Render skipped focus mode."""
    return _render_path("/?section=skipped&view=focus")


class TestSkippedFocusModeRendering:
    """Verify the Focus Mode renders correctly for Help Identify section."""

    def test_focus_mode_returns_200(self, client):
        """GET /?section=skipped&view=focus returns 200."""
        resp = client.get("/?section=skipped&view=focus")
        assert resp.status_code == 200

    def test_focus_mode_has_container(self, client):
        """Focus mode renders the skipped-focus-container div."""
        html = _render_path("/?section=skipped&view=focus")
        assert 'id="skipped-focus-container"' in html

    def test_focus_mode_has_this_person_label(self, client):
        """Shows 'Who is this?' label above the face crop."""
        html = _render_path("/?section=skipped&view=focus")
        assert "Who is this?" in html

    def test_focus_mode_has_best_match(self, client):
        """Shows 'Best Match' section (with or without suggestions)."""
        html = _render_path("/?section=skipped&view=focus")
        assert "Best Match" in html

    def test_focus_mode_has_i_know_them_button(self, client):
        """Shows 'I Know Them' button."""
        html = _render_path("/?section=skipped&view=focus")
        assert "I Know Them" in html


class TestSkippedFocusModeViewToggle:
    """Verify Focus/Browse toggle works for Help Identify section."""

    def test_view_toggle_present(self, client):
        """View toggle with Focus and View All links is present."""
        html = _render_path("/?section=skipped&view=focus")
        assert "section=skipped&amp;view=focus" in html
        assert "section=skipped&amp;view=browse" in html

    def test_browse_mode_shows_cards_list(self, client):
        """Browse mode shows the traditional card grid, not focus mode."""
        html = _render_path("/?section=skipped&view=browse")
        assert 'id="skipped-focus-container"' not in html

    def test_default_view_is_focus(self, client):
        """Default view for skipped section is focus mode."""
        html = _render_path("/?section=skipped")
        assert 'id="skipped-focus-container"' in html


class TestSkippedFocusActions:
    """Verify Focus Mode action routes work correctly."""

    def test_focus_skip_route_exists(self, client):
        """POST /api/skipped/{id}/focus-skip returns a response."""
        resp = client.post("/api/skipped/fake-id/focus-skip")
        assert resp.status_code in (200, 404)

    def test_name_and_confirm_empty_name_rejected(self, client):
        """POST /api/skipped/{id}/name-and-confirm with empty name returns 400."""
        resp = client.post("/api/skipped/fake-id/name-and-confirm", data={"name": ""})
        assert resp.status_code == 400

    def test_name_and_confirm_with_name(self, client):
        """POST /api/skipped/{id}/name-and-confirm with valid name works."""
        resp = client.post("/api/skipped/fake-id/name-and-confirm", data={"name": "Test Person"})
        assert resp.status_code in (200, 400)


class TestSkippedFocusModeWithMockData:
    """Test focus mode behavior with controlled mock data."""

    def _mock_skipped_identities(self):
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

        with (
            patch("app.main._get_identities_with_proposals", return_value={"skip-high"}),
            patch(
                "app.main._get_best_proposal_for_identity",
                return_value={
                    "confidence": "HIGH",
                    "distance": 0.85,
                    "target_identity_id": "target-1",
                    "target_identity_name": "Known Person",
                },
            ),
            patch("app.main._identity_quality_score", return_value=50.0),
        ):
            sorted_list = _sort_skipped_by_actionability(identities)
            assert sorted_list[0]["identity_id"] == "skip-high"


class TestActionabilityBadges:
    """Test actionability badges in browse and focus mode."""

    def test_strong_lead_badge_for_high_confidence(self):
        """Strong lead badge returned for HIGH proposals."""
        from app.main import _actionability_badge

        with patch(
            "app.main._get_best_proposal_for_identity",
            return_value={
                "confidence": "HIGH",
                "distance": 0.85,
                "target_identity_id": "t1",
                "target_identity_name": "Known",
            },
        ):
            badge = _actionability_badge("test-id", {"test-id"})
            from fasthtml.common import to_xml

            html = to_xml(badge)
            assert "Strong lead" in html

    def test_no_badge_for_no_proposals(self):
        """No badge when identity has no proposals."""
        from app.main import _actionability_badge

        badge = _actionability_badge("test-id", set())
        assert badge is None


class TestSkippedFocusMergeIntegration:
    """Test that merge route handles focus_section=skipped."""

    def test_merge_route_accepts_focus_section(self, client):
        """Merge route accepts focus_section parameter without error."""
        resp = client.post("/api/identity/fake-target/merge/fake-source?from_focus=true&focus_section=skipped")
        assert resp.status_code in (404, 409, 200)

    def test_neighbors_route_accepts_focus_section(self, client):
        """Neighbors route accepts focus_section parameter."""
        resp = client.get("/api/identity/fake-id/neighbors?from_focus=true&focus_section=skipped")
        assert resp.status_code in (200, 404)


class TestBestMatchFallback:
    """Test that Best Match falls back to real-time neighbors when proposals empty."""

    def test_get_best_match_uses_proposals_first(self):
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
        from app.main import _get_best_match_for_identity

        neighbor = {
            "target_identity_id": "t2",
            "target_identity_name": "Neighbor",
            "distance": 1.05,
            "confidence": "MODERATE",
        }
        with (
            patch("app.main._get_best_proposal_for_identity", return_value=None),
            patch("app.main._compute_best_neighbor", return_value=neighbor),
        ):
            result = _get_best_match_for_identity("test-id")
            assert result == neighbor

    def test_get_best_match_returns_none_when_no_matches(self):
        from app.main import _get_best_match_for_identity

        with (
            patch("app.main._get_best_proposal_for_identity", return_value=None),
            patch("app.main._compute_best_neighbor", return_value=None),
        ):
            result = _get_best_match_for_identity("test-id")
            assert result is None


class TestOtherMatchesStrip:
    """Horizontal strip of secondary matches below main comparison."""

    def test_suggestion_with_strip_returns_tuple(self):
        from app.main import _build_skipped_suggestion_with_strip

        result = _build_skipped_suggestion_with_strip("nonexistent-id", set())
        assert isinstance(result, tuple)
        assert len(result) == 3
        assert result[2] is None


class TestShareMatchButton:
    """Test that Share Match buttons appear in neighbor cards."""

    def test_neighbor_card_has_share_match_button(self):
        from app.main import neighbor_card
        from fasthtml.common import to_xml

        neighbor = {
            "identity_id": "neighbor-abc",
            "name": "Test Person",
            "distance": 0.8,
            "percentile": 0.5,
            "confidence_gap": 10.0,
            "can_merge": True,
            "face_count": 1,
            "co_occurrence": 0,
            "anchor_face_ids": [],
            "candidate_face_ids": [],
            "state": "PROPOSED",
        }
        card = neighbor_card(neighbor, "target-xyz", set())
        html = to_xml(card)
        assert "/identify/target-xyz/match/neighbor-abc" in html


class TestActionabilitySortUnit:
    """Unit tests for _sort_skipped_by_actionability ordering logic."""

    def test_very_high_before_high(self):
        from app.main import _sort_skipped_by_actionability

        mock_neighbors = {
            "id-high": (0.95, "HIGH", "Person X"),
            "id-very-high": (0.75, "VERY HIGH", "Person Y"),
        }
        skipped = [
            {"identity_id": "id-high", "name": "Person A", "state": "SKIPPED"},
            {"identity_id": "id-very-high", "name": "Person B", "state": "SKIPPED"},
        ]
        with (
            patch("app.main._get_skipped_neighbor_distances", return_value=mock_neighbors),
            patch("app.main._identity_quality_score", return_value=50.0),
        ):
            result = _sort_skipped_by_actionability(skipped)
            assert result[0]["identity_id"] == "id-very-high"

    def test_no_match_sorts_last(self):
        from app.main import _sort_skipped_by_actionability

        mock_neighbors = {
            "id-match": (1.10, "MODERATE", "Someone"),
        }
        skipped = [
            {"identity_id": "id-nomatch", "name": "Nobody", "state": "SKIPPED"},
            {"identity_id": "id-match", "name": "Somebody", "state": "SKIPPED"},
        ]
        with (
            patch("app.main._get_skipped_neighbor_distances", return_value=mock_neighbors),
            patch("app.main._identity_quality_score", return_value=50.0),
        ):
            result = _sort_skipped_by_actionability(skipped)
            assert result[0]["identity_id"] == "id-match"

    def test_within_tier_sorts_by_distance(self):
        from app.main import _sort_skipped_by_actionability

        mock_neighbors = {
            "id-far": (0.98, "HIGH", "Person X"),
            "id-close": (0.82, "HIGH", "Person Y"),
        }
        skipped = [
            {"identity_id": "id-far", "name": "Far", "state": "SKIPPED"},
            {"identity_id": "id-close", "name": "Close", "state": "SKIPPED"},
        ]
        with (
            patch("app.main._get_skipped_neighbor_distances", return_value=mock_neighbors),
            patch("app.main._identity_quality_score", return_value=50.0),
        ):
            result = _sort_skipped_by_actionability(skipped)
            assert result[0]["identity_id"] == "id-close"
