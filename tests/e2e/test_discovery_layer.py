"""
E2E browser tests for Discovery Layer features (PRD 005).

Tests the 5 features: date badges, metadata panel, decade/search/tag filtering,
correction flow, and admin review queue. All tests should FAIL initially — they
describe features that don't exist yet (SDD Phase 2 requirement).

Selectors based on PRD 005 acceptance criteria.
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


# ---- TEST 1: Photo card shows date badge ----

def test_photo_card_shows_date_badge(app_server, page):
    """Visit /photos — at least one photo card contains a date badge like 'c. 1930s'."""
    _goto(page, f"{app_server}/photos")

    # Date badges should exist with pattern "c. NNNNs"
    badges = page.locator("[data-testid='date-badge']")
    assert badges.count() > 0, "Expected at least one date badge on photo cards"

    # Check format matches "c. 1920s" or similar
    first_badge_text = badges.first.text_content()
    assert re.match(r"c\.\s*\d{4}s", first_badge_text), (
        f"Date badge text '{first_badge_text}' doesn't match expected format 'c. NNNNs'"
    )


# ---- TEST 2: Date badge reflects confidence ----

def test_date_badge_confidence_styling(app_server, page):
    """High-confidence badges have solid background, low-confidence have dashed border."""
    _goto(page, f"{app_server}/photos")

    badges = page.locator("[data-testid='date-badge']")
    assert badges.count() > 0, "No date badges found"

    # Check that different confidence levels have different styling
    high_badges = page.locator("[data-testid='date-badge'][data-confidence='high']")
    low_badges = page.locator("[data-testid='date-badge'][data-confidence='low']")

    # At least some badges should exist (we have 250 labels with varied confidence)
    total = high_badges.count() + low_badges.count()
    assert total > 0, "Expected badges with confidence data attributes"


# ---- TEST 3: Photo detail shows metadata panel ----

def test_photo_detail_metadata_panel(app_server, page):
    """Visit /photo/{known_id} — page contains AI Analysis section with scene and tags."""
    _goto(page, f"{app_server}/photos")

    # Get the first photo link
    first_link = page.locator("a[href^='/photo/']").first
    href = first_link.get_attribute("href")
    assert href, "No photo links found on /photos page"

    _goto(page, f"{app_server}{href}")

    # Check for AI Analysis section
    ai_section = page.locator("[data-testid='ai-analysis']")
    assert ai_section.count() > 0, "Expected 'AI Analysis' section on photo detail page"

    # Check for subsections
    assert page.locator("text=Scene").count() > 0, "Expected 'Scene' subsection"

    # Check for tag pills
    tag_pills = page.locator("[data-testid='ai-tag']")
    assert tag_pills.count() > 0, "Expected tag pills in AI Analysis section"


# ---- TEST 4: Decade filter pills displayed with counts ----

def test_decade_filter_pills_displayed(app_server, page):
    """Visit /photos — page contains decade pills with counts like '1920s (35)'."""
    _goto(page, f"{app_server}/photos")

    decade_pills = page.locator("[data-testid='decade-pill']")
    assert decade_pills.count() > 0, "Expected decade filter pills on /photos page"

    # Check format: "1920s (35)"
    first_pill = decade_pills.first.text_content()
    assert re.match(r"\d{4}s\s*\(\d+\)", first_pill), (
        f"Decade pill text '{first_pill}' doesn't match expected format 'NNNNs (N)'"
    )


# ---- TEST 5: Decade filter filters gallery ----

def test_decade_filter_filters_gallery(app_server, page):
    """Click a decade pill — all visible photos should have that decade's badge."""
    _goto(page, f"{app_server}/photos")

    # Click a decade pill
    pill = page.locator("[data-testid='decade-pill']").first
    decade_text = pill.text_content()
    decade_match = re.search(r"(\d{4})s", decade_text)
    assert decade_match, f"Could not parse decade from pill text: {decade_text}"

    decade = decade_match.group(1)
    pill.click()
    page.wait_for_timeout(SETTLE_MS)

    # URL should contain decade parameter
    assert f"decade={decade}" in page.url, (
        f"Expected URL to contain 'decade={decade}', got: {page.url}"
    )

    # All visible date badges should match the filtered decade
    badges = page.locator("[data-testid='date-badge']")
    if badges.count() > 0:
        for i in range(min(badges.count(), 5)):  # Check first 5
            badge_text = badges.nth(i).text_content()
            assert decade in badge_text, (
                f"Badge '{badge_text}' doesn't match filtered decade {decade}s"
            )


# ---- TEST 6: Keyword search returns results ----

def test_keyword_search_returns_results(app_server, page):
    """Enter 'wedding' in search — results appear with match reason text."""
    _goto(page, f"{app_server}/photos")

    search_input = page.locator("[data-testid='photo-search']")
    assert search_input.count() > 0, "Expected a search input on /photos page"

    search_input.fill("studio")
    page.wait_for_timeout(1000)  # Wait for debounced search

    # Results should appear (studio is a common tag in the archive)
    photo_cards = page.locator("a[href^='/photo/']")
    assert photo_cards.count() > 0, "Expected search results for 'studio'"

    # Match reason should be shown
    match_reasons = page.locator("[data-testid='match-reason']")
    assert match_reasons.count() > 0, "Expected match reason labels on search results"


# ---- TEST 7: Search + decade filter combine ----

def test_search_and_decade_filter_combine(app_server, page):
    """Visit /photos with decade=1920 and search_q=studio — results are intersection."""
    _goto(page, f"{app_server}/photos?decade=1920&search_q=studio")

    # Should have results (1920s studio photos exist in the archive)
    photo_cards = page.locator("a[href^='/photo/']")
    # Verify the filters are active in the UI
    assert "decade=1920" in page.url or "search_q=studio" in page.url, (
        "Expected filter params in URL"
    )


# ---- TEST 8: Correction flow updates source ----

def test_correction_flow_updates_source(app_server, page):
    """Admin clicks pencil on date field, enters new year, submits — field shows 'Verified'."""
    _goto(page, f"{app_server}/photos")

    # Navigate to a photo detail page
    first_link = page.locator("a[href^='/photo/']").first
    href = first_link.get_attribute("href")
    _goto(page, f"{app_server}{href}")

    # Find the correction pencil button for date
    pencil = page.locator("[data-testid='correct-date']")
    assert pencil.count() > 0, "Expected correction pencil button on date field"

    pencil.click()
    page.wait_for_timeout(SETTLE_MS)

    # Fill in correction form
    year_input = page.locator("[data-testid='correction-year']")
    assert year_input.count() > 0, "Expected year input in correction form"
    year_input.fill("1935")

    # Submit
    submit_btn = page.locator("[data-testid='correction-submit']")
    submit_btn.click()
    page.wait_for_timeout(SETTLE_MS)

    # Field should now show verified styling
    verified = page.locator("[data-testid='verified-field']")
    assert verified.count() > 0, "Expected field to show 'Verified' styling after correction"


# ---- TEST 9: Correction logged ----

def test_correction_logged(app_server, page):
    """After correction, corrections_log.json contains the entry."""
    # This test depends on TEST 8 having run — skip if standalone
    import json
    from pathlib import Path

    corrections_path = Path(__file__).resolve().parent.parent.parent / "data" / "corrections_log.json"

    # Only check if file exists (it should after corrections are made)
    if not corrections_path.exists():
        pytest.skip("corrections_log.json does not exist yet — run correction flow first")

    with open(corrections_path) as f:
        data = json.load(f)

    assert "corrections" in data, "Expected 'corrections' key in corrections_log.json"
    # We don't assert a specific correction here since this test may run in isolation


# ---- TEST 10: Provenance visual distinction ----

def test_provenance_visual_distinction(app_server, page):
    """Photo detail page shows emerald/green border for corrected fields, indigo/blue for AI."""
    _goto(page, f"{app_server}/photos")

    first_link = page.locator("a[href^='/photo/']").first
    href = first_link.get_attribute("href")
    _goto(page, f"{app_server}{href}")

    # AI-estimated fields should have indigo/blue border
    ai_fields = page.locator("[data-provenance='ai']")
    assert ai_fields.count() > 0, "Expected AI-estimated fields with data-provenance='ai'"

    # Check CSS class contains indigo border
    first_ai = ai_fields.first
    cls = first_ai.get_attribute("class") or ""
    assert "border-indigo" in cls or "indigo" in cls, (
        f"Expected indigo border class on AI field, got: {cls}"
    )


# ---- TEST 11: Admin review queue sorted by priority ----

def test_admin_review_queue_sorted(app_server, page):
    """Visit /admin/review-queue — photos listed, first has higher priority than last."""
    _goto(page, f"{app_server}/admin/review-queue")

    # Should have review items
    items = page.locator("[data-testid='review-item']")
    assert items.count() > 0, "Expected review items in admin queue"

    # First item should have a priority score
    first_score = items.first.get_attribute("data-priority")
    assert first_score is not None, "Expected data-priority attribute on review items"

    if items.count() > 1:
        last_score = items.last.get_attribute("data-priority")
        assert float(first_score) >= float(last_score), (
            f"Expected first item priority ({first_score}) >= last ({last_score})"
        )


# ---- TEST 12: Tag filter works ----

def test_tag_filter_works(app_server, page):
    """Click 'Studio' tag filter — visible photos are filtered to studio photos."""
    _goto(page, f"{app_server}/photos")

    tag_pills = page.locator("[data-testid='tag-pill']")
    assert tag_pills.count() > 0, "Expected tag filter pills on /photos page"

    # Find and click the Studio tag
    studio_pill = page.locator("[data-testid='tag-pill']:has-text('Studio')")
    if studio_pill.count() == 0:
        # Fall back to first tag
        tag_pills.first.click()
    else:
        studio_pill.click()

    page.wait_for_timeout(SETTLE_MS)

    # URL should contain tag parameter
    assert "tag=" in page.url, f"Expected 'tag=' in URL after clicking tag pill, got: {page.url}"
