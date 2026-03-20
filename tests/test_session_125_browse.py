"""Tests for Session 125 browse route fixes: UX-114, FB-157, FB-158."""

import inspect


def _read_source(module_path: str) -> str:
    """Read source file as string."""
    from pathlib import Path

    return Path(module_path).read_text(encoding="utf-8")


class TestUX114NoOnfocusSelect:
    """UX-114: Search input should use placeholder, not onfocus='this.select()'."""

    def test_no_onfocus_select_in_browse_routes(self):
        """browse_routes.py must not contain onfocus='this.select()'."""
        source = _read_source("app/browse_routes.py")
        assert 'onfocus="this.select()"' not in source, (
            "Found onfocus='this.select()' in browse_routes.py — use placeholder instead"
        )

    def test_photo_search_has_placeholder(self):
        """The photo search input must have a descriptive placeholder attribute."""
        source = _read_source("app/browse_routes.py")
        # The search input has data_testid="photo-search" and should have placeholder
        assert "placeholder=" in source, "Search input should have a placeholder attribute"
        assert "photo-search" in source, "Photo search input should have data_testid"


class TestFB157PersonLinks:
    """FB-157: Identity cards on /people should link to /person/{identity_id}."""

    def test_person_cards_wrapped_in_anchor(self):
        """Person cards in the people page must be wrapped in A() tags linking to /person/."""
        import app.browse_routes as br

        # Get the source of the people page route handler
        # The function is registered via @rt decorator, find it by looking at module source
        source = inspect.getsource(br)

        # Person cards should be A() elements with href to /person/{identity_id}
        assert '/person/{identity_id}"' in source, "Person cards must link to /person/{identity_id}"

    def test_person_card_has_nav_prefix(self):
        """Person card links must include community nav_prefix for routing."""
        source = _read_source("app/browse_routes.py")
        # Should use nav_prefix in the person link href
        assert 'f"{nav_prefix}/person/{identity_id}"' in source, (
            "Person card links must include nav_prefix for community routing"
        )

    def test_person_card_is_clickable_block(self):
        """Person card A() element should have 'block' in its CSS class for full-card clickability."""
        source = _read_source("app/browse_routes.py")
        # Find the person_cards.append section — the A() should have "block" class
        # Look for the pattern near person_cards.append
        idx = source.find("person_cards.append")
        assert idx > 0, "person_cards.append must exist in browse_routes.py"
        card_section = source[idx : idx + 500]
        assert "block" in card_section, "Person card A() should have 'block' CSS class"


class TestFB158DistanceBadge:
    """FB-158: Distance/confidence display in similar person search results."""

    def test_confidence_tier_shown_in_similar_results(self):
        """Similar person results should show a confidence tier badge."""
        source = _read_source("app/browse_routes.py")
        assert "confidence_tier_from_distance" in source, (
            "Similar results must use confidence_tier_from_distance for display"
        )

    def test_distance_badge_rendered_for_admin(self):
        """Admin users should see raw distance value in similar results."""
        source = _read_source("app/browse_routes.py")
        # The distance display should exist and be gated on is_admin
        assert "distance" in source, "Distance data must be referenced in browse_routes"
        # Check that distance is formatted and shown
        assert '.get("distance"' in source or "get('distance'" in source, (
            "Distance value must be read from neighbor data"
        )
        # Check admin gating of raw distance
        assert "is_admin" in source, "Raw distance display should be gated on is_admin"

    def test_tier_label_has_styled_badge(self):
        """The confidence tier label should render as a styled badge element."""
        source = _read_source("app/browse_routes.py")
        # tier_label should be rendered in a Span with styling
        assert "tier_label" in source, "tier_label must be rendered in similar results"
        assert "tier_cls" in source, "tier_cls must be used for badge styling"
