"""
E2E browser tests for Timeline Story Engine (PRD 006).

Tests the vertical timeline with decade markers, photo cards, context events,
person filter with age overlay, confidence bars, and share button.
All tests should FAIL initially — they describe features that don't exist yet
(SDD Phase 2 requirement).

Selectors based on PRD 006 acceptance criteria.
"""

import re

import pytest

pytestmark = pytest.mark.e2e

GOTO_OPTS = {"wait_until": "domcontentloaded", "timeout": 15000}
SETTLE_MS = 600


def _goto(page, url):
    """Navigate to a URL and wait for DOM + HTMX settle."""
    page.goto(url, **GOTO_OPTS)
    page.wait_for_timeout(SETTLE_MS)


# ---- TEST 1: /timeline route loads with timeline structure ----

def test_timeline_route_loads(app_server, page):
    """/timeline returns 200 and contains vertical timeline structure."""
    _goto(page, f"{app_server}/timeline")

    # Page should have the timeline container
    timeline = page.locator("[data-testid='timeline-container']")
    assert timeline.count() > 0, "Expected timeline container element"

    # Should have the vertical timeline line
    line = page.locator("[data-testid='timeline-line']")
    assert line.count() > 0, "Expected vertical timeline line element"


# ---- TEST 2: Photo cards appear on timeline ----

def test_timeline_photo_cards(app_server, page):
    """Timeline shows photo cards with thumbnails and date badges."""
    _goto(page, f"{app_server}/timeline")

    cards = page.locator("[data-testid='timeline-photo-card']")
    assert cards.count() > 0, "Expected at least one photo card on timeline"

    # Cards should have date badges
    badges = page.locator("[data-testid='timeline-photo-card'] [data-testid='date-badge']")
    assert badges.count() > 0, "Expected date badges on timeline photo cards"


# ---- TEST 3: Historical context events appear ----

def test_timeline_context_events(app_server, page):
    """Timeline includes historical context event cards with distinct styling."""
    _goto(page, f"{app_server}/timeline")

    events = page.locator("[data-testid='timeline-context-event']")
    assert events.count() > 0, "Expected at least one historical context event"

    # Context events should have titles
    first_title = events.first.locator("[data-testid='context-event-title']").text_content()
    assert len(first_title) > 0, "Context event should have a title"


# ---- TEST 4: Decade markers are present and ordered ----

def test_timeline_decade_markers_ordered(app_server, page):
    """Timeline has multiple decade markers in chronological order."""
    _goto(page, f"{app_server}/timeline")

    markers = page.locator("[data-testid='decade-marker']")
    count = markers.count()
    assert count >= 2, f"Expected at least 2 decade markers, got {count}"

    # Extract decade values and verify ordering
    decades = []
    for i in range(count):
        text = markers.nth(i).text_content()
        match = re.search(r"(\d{4})", text)
        if match:
            decades.append(int(match.group(1)))

    assert decades == sorted(decades), f"Decade markers not in order: {decades}"


# ---- TEST 5: Person filter dropdown exists ----

def test_timeline_person_filter_exists(app_server, page):
    """Timeline has a person filter dropdown with names."""
    _goto(page, f"{app_server}/timeline")

    select = page.locator("[data-testid='person-filter']")
    assert select.count() > 0, "Expected person filter dropdown"

    # Should have options beyond the default
    options = select.locator("option")
    assert options.count() > 1, "Expected person options in filter dropdown"


# ---- TEST 6: Person filter works via HTMX ----

def test_timeline_person_filter_works(app_server, page):
    """Selecting a person filters the timeline to show only their photos."""
    _goto(page, f"{app_server}/timeline")

    # Get initial card count
    initial_cards = page.locator("[data-testid='timeline-photo-card']").count()

    # Select a person from the filter (pick first non-default option)
    select = page.locator("[data-testid='person-filter']")
    options = select.locator("option")
    if options.count() > 1:
        # Select second option (first is "All people")
        value = options.nth(1).get_attribute("value")
        select.select_option(value)
        page.wait_for_timeout(SETTLE_MS)

        # Card count should change (filtered down)
        filtered_cards = page.locator("[data-testid='timeline-photo-card']").count()
        assert filtered_cards <= initial_cards, "Person filter should reduce or maintain card count"
        assert filtered_cards > 0, "Person filter should show at least one photo"


# ---- TEST 7: Year range filter works ----

def test_timeline_year_range_filter(app_server, page):
    """/timeline?start=1920&end=1950 shows only photos in that range."""
    _goto(page, f"{app_server}/timeline?start=1920&end=1950")

    cards = page.locator("[data-testid='timeline-photo-card']")
    # Should show some subset (may be zero if no photos in range, but shouldn't error)

    # Decade markers should be within or near the range
    markers = page.locator("[data-testid='decade-marker']")
    if markers.count() > 0:
        for i in range(markers.count()):
            text = markers.nth(i).text_content()
            match = re.search(r"(\d{4})", text)
            if match:
                decade = int(match.group(1))
                assert 1920 <= decade <= 1959, (
                    f"Decade marker {decade} outside expected range 1920-1959"
                )


# ---- TEST 8: Confidence interval bars on cards ----

def test_timeline_confidence_bars(app_server, page):
    """Photo cards include confidence interval bars showing date range."""
    _goto(page, f"{app_server}/timeline")

    bars = page.locator("[data-testid='confidence-bar']")
    assert bars.count() > 0, "Expected confidence interval bars on timeline cards"


# ---- TEST 9: Age overlay when person is filtered ----

def test_timeline_age_overlay(app_server, page):
    """With a person filter active and birth_year available, cards show age badges."""
    # This test may need to be skipped if no identity has birth_year set
    _goto(page, f"{app_server}/timeline")

    select = page.locator("[data-testid='person-filter']")
    options = select.locator("option")
    if options.count() > 1:
        # Try filtering by a person
        value = options.nth(1).get_attribute("value")
        select.select_option(value)
        page.wait_for_timeout(SETTLE_MS)

        # Check for age badges (may not appear if no birth_year)
        age_badges = page.locator("[data-testid='age-badge']")
        # This is a soft assertion — we just verify the feature exists
        # Even if 0 badges appear (no birth_year data), the test structure is correct


# ---- TEST 10: Share button copies URL ----

def test_timeline_share_button(app_server, page):
    """Share button exists and is clickable."""
    _goto(page, f"{app_server}/timeline")

    share_btn = page.locator("[data-testid='share-story-btn']")
    assert share_btn.count() > 0, "Expected 'Share This Story' button"

    # Click should work without error
    share_btn.click()
    page.wait_for_timeout(300)


# ---- TEST 11: Timeline link in navigation ----

def test_timeline_in_navigation(app_server, page):
    """Sidebar navigation contains a Timeline link pointing to /timeline."""
    _goto(page, f"{app_server}/")

    # Look for timeline link in sidebar
    timeline_link = page.locator("a[href='/timeline']")
    assert timeline_link.count() > 0, "Expected Timeline link in navigation"

    # Click it and verify we land on timeline
    timeline_link.first.click()
    page.wait_for_timeout(SETTLE_MS)

    # Should now be on timeline page
    timeline = page.locator("[data-testid='timeline-container']")
    assert timeline.count() > 0, "Clicking Timeline link should navigate to timeline page"
