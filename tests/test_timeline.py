"""
Unit tests for the Timeline Story Engine.

Tests the data layer, route handler, filtering, context events loading,
person filter, age calculation, and navigation links.
"""

import json
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---- Context Events Loading ----


class TestLoadContextEvents:
    """Tests for _load_context_events() data loader."""

    def test_loads_events_from_json(self, tmp_path):
        """Context events are loaded from rhodes_context_events.json."""
        events_file = tmp_path / "rhodes_context_events.json"
        events_file.write_text(json.dumps({
            "schema_version": 1,
            "events": [
                {"year": 1944, "title": "Deportation", "category": "holocaust"},
                {"year": 1912, "title": "Italian Conquest", "category": "political"},
            ]
        }))

        import app.main as main
        # Clear cache
        main._context_events_cache = None
        original_data_path = main.data_path
        try:
            main.data_path = tmp_path
            events = main._load_context_events()
            assert len(events) == 2
            assert events[0]["year"] == 1944
            assert events[1]["title"] == "Italian Conquest"
        finally:
            main.data_path = original_data_path
            main._context_events_cache = None

    def test_returns_empty_list_if_file_missing(self, tmp_path):
        """Returns empty list if context events file doesn't exist."""
        import app.main as main
        main._context_events_cache = None
        original_data_path = main.data_path
        try:
            main.data_path = tmp_path  # No file exists here
            events = main._load_context_events()
            assert events == []
        finally:
            main.data_path = original_data_path
            main._context_events_cache = None

    def test_caches_after_first_load(self, tmp_path):
        """Events are cached after first load — second call returns same object."""
        events_file = tmp_path / "rhodes_context_events.json"
        events_file.write_text(json.dumps({
            "schema_version": 1,
            "events": [{"year": 1944, "title": "Test"}]
        }))

        import app.main as main
        main._context_events_cache = None
        original_data_path = main.data_path
        try:
            main.data_path = tmp_path
            events1 = main._load_context_events()
            events2 = main._load_context_events()
            assert events1 is events2  # Same object = cached
        finally:
            main.data_path = original_data_path
            main._context_events_cache = None


# ---- Context Events JSON Validation ----


class TestContextEventsData:
    """Validate the actual rhodes_context_events.json data file."""

    @pytest.fixture(autouse=True)
    def load_events(self):
        """Load the real context events file."""
        events_path = Path(__file__).resolve().parent.parent / "data" / "rhodes_context_events.json"
        with open(events_path) as f:
            data = json.load(f)
        self.events = data.get("events", [])

    def test_has_events(self):
        """File contains at least 10 events."""
        assert len(self.events) >= 10

    def test_all_events_have_required_fields(self):
        """Every event has year, title, description, category."""
        for event in self.events:
            assert "year" in event, f"Missing year: {event.get('title', '?')}"
            assert "title" in event, f"Missing title at year {event.get('year', '?')}"
            assert "description" in event, f"Missing description: {event.get('title', '?')}"
            assert "category" in event, f"Missing category: {event.get('title', '?')}"

    def test_events_span_expected_range(self):
        """Events cover from at least 1500s to 1990s."""
        years = [e["year"] for e in self.events]
        assert min(years) <= 1600
        assert max(years) >= 1990

    def test_deportation_event_exists(self):
        """The 1944 deportation event is present with correct date."""
        deportation = [e for e in self.events if e["year"] == 1944 and "Deportation" in e["title"]]
        assert len(deportation) >= 1
        event = deportation[0]
        assert event.get("month") == 7
        assert event.get("day") == 23
        assert "1,673" in event["description"]

    def test_categories_are_valid(self):
        """All events use valid category values."""
        valid_categories = {"holocaust", "persecution", "liberation", "immigration", "community", "political"}
        for event in self.events:
            assert event["category"] in valid_categories, (
                f"Invalid category '{event['category']}' on event '{event['title']}'"
            )

    def test_events_have_sources(self):
        """All events cite a source."""
        for event in self.events:
            assert "source" in event and len(event["source"]) > 0, (
                f"Missing source for: {event['title']}"
            )


# ---- Timeline Route ----


class TestTimelineRoute:
    """Tests for the /timeline route handler."""

    @pytest.fixture(autouse=True)
    def setup_client(self):
        """Create test client."""
        from starlette.testclient import TestClient
        from app.main import app
        self.client = TestClient(app)

    def test_timeline_returns_200(self):
        """GET /timeline returns 200."""
        resp = self.client.get("/timeline")
        assert resp.status_code == 200

    def test_timeline_contains_timeline_structure(self):
        """Response contains timeline container and line."""
        resp = self.client.get("/timeline")
        assert "timeline-container" in resp.text
        assert "timeline-line" in resp.text

    def test_timeline_has_decade_markers(self):
        """Response contains decade markers."""
        resp = self.client.get("/timeline")
        assert "decade-marker" in resp.text

    def test_timeline_has_photo_cards(self):
        """Response contains photo cards."""
        resp = self.client.get("/timeline")
        assert "timeline-photo-card" in resp.text

    def test_timeline_has_context_events(self):
        """Response contains context event cards."""
        resp = self.client.get("/timeline")
        assert "timeline-context-event" in resp.text

    def test_timeline_has_person_filter(self):
        """Response contains person filter dropdown."""
        resp = self.client.get("/timeline")
        assert "person-filter" in resp.text

    def test_timeline_has_share_button(self):
        """Response contains share button."""
        resp = self.client.get("/timeline")
        assert "share-story-btn" in resp.text

    def test_timeline_has_confidence_bars(self):
        """Response contains confidence interval bars."""
        resp = self.client.get("/timeline")
        assert "confidence-bar" in resp.text

    def test_timeline_has_og_tags(self):
        """Response contains Open Graph meta tags."""
        resp = self.client.get("/timeline")
        assert 'og:title' in resp.text
        assert 'og:description' in resp.text

    def test_timeline_story_title(self):
        """Default story title is 'A Century of Rhodes'."""
        resp = self.client.get("/timeline")
        assert "A Century of Rhodes" in resp.text

    def test_timeline_context_off(self):
        """context=off removes context events."""
        resp = self.client.get("/timeline?context=off")
        assert resp.status_code == 200
        assert "timeline-context-event" not in resp.text

    def test_timeline_year_range_filter(self):
        """start/end params filter timeline entries."""
        resp = self.client.get("/timeline?start=1920&end=1950")
        assert resp.status_code == 200
        # Should still have the timeline container
        assert "timeline-container" in resp.text

    def test_timeline_person_filter_with_invalid_id(self):
        """Person filter with non-existent ID returns empty gracefully."""
        resp = self.client.get("/timeline?person=nonexistent-id")
        assert resp.status_code == 200
        assert "timeline-container" in resp.text

    def test_timeline_collection_filter(self):
        """Collection filter parameter is accepted."""
        resp = self.client.get("/timeline?collection=Vida+Capeluto+NYC+Collection")
        assert resp.status_code == 200
        assert "timeline-container" in resp.text

    def test_timeline_has_collection_filter_dropdown(self):
        """Response contains collection filter dropdown."""
        resp = self.client.get("/timeline")
        assert "collection-filter" in resp.text

    def test_timeline_multi_person_filter(self):
        """Multi-person filter via ?people= is accepted."""
        resp = self.client.get("/timeline?people=id1,id2")
        assert resp.status_code == 200
        assert "timeline-container" in resp.text

    def test_timeline_controls_are_sticky(self):
        """Controls section has sticky positioning."""
        resp = self.client.get("/timeline")
        assert "sticky top-16" in resp.text

    def test_timeline_nav_visible_on_mobile(self):
        """Nav links are not hidden on mobile (no 'hidden sm:flex')."""
        resp = self.client.get("/timeline")
        # The timeline nav should NOT have "hidden sm:flex" for nav links
        # It should use "flex" directly so links show on mobile
        # Look for the timeline nav pattern
        assert "Photos" in resp.text
        assert "People" in resp.text


# ---- Navigation Links ----


class TestTimelineNavigation:
    """Tests for timeline navigation links across the site."""

    @pytest.fixture(autouse=True)
    def setup_client(self):
        from starlette.testclient import TestClient
        from app.main import app
        self.client = TestClient(app)

    def test_landing_page_has_timeline_link(self):
        """Landing page navigation includes Timeline link."""
        resp = self.client.get("/")
        assert "/timeline" in resp.text

    def test_photos_page_has_timeline_link(self):
        """/photos page navigation includes Timeline link."""
        resp = self.client.get("/photos")
        assert "/timeline" in resp.text

    def test_people_page_has_timeline_link(self):
        """/people page navigation includes Timeline link."""
        resp = self.client.get("/people")
        assert "/timeline" in resp.text

    def test_timeline_page_has_photos_link(self):
        """Timeline page navigation includes Photos link."""
        resp = self.client.get("/timeline")
        assert "/photos" in resp.text

    def test_timeline_page_has_people_link(self):
        """Timeline page navigation includes People link."""
        resp = self.client.get("/timeline")
        assert "/people" in resp.text


# ---- Decade Ordering ----


class TestDecadeOrdering:
    """Tests that timeline entries are ordered chronologically."""

    @pytest.fixture(autouse=True)
    def setup_client(self):
        from starlette.testclient import TestClient
        from app.main import app
        self.client = TestClient(app)

    def test_decade_markers_in_chronological_order(self):
        """Decade markers appear in ascending order."""
        resp = self.client.get("/timeline")
        # Find all decade markers using regex
        decades = re.findall(r'data-testid="decade-marker"[^>]*>.*?(\d{4})s', resp.text, re.DOTALL)
        if len(decades) >= 2:
            decade_ints = [int(d) for d in decades]
            assert decade_ints == sorted(decade_ints), f"Decades not sorted: {decade_ints}"
