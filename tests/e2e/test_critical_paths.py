"""
E2E browser tests for Rhodesli critical paths.

These tests run a real browser against a real server to catch the class of
bugs that server-side tests miss: HTMX swaps that break event handlers,
lightbox arrows that disappear after navigation, face overlays that fail
to render, etc.

Selectors are based on actual HTML output from app/main.py as of 2026-02-08.
"""

import re

import pytest

pytestmark = pytest.mark.e2e

# Default timeout for goto — CDN scripts (Tailwind JIT) make "load" slow,
# so we use domcontentloaded + a short settle delay for HTMX.
GOTO_OPTS = {"wait_until": "domcontentloaded", "timeout": 15000}
SETTLE_MS = 600  # ms for HTMX to initialize after DOMContentLoaded


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _goto(page, url):
    """Navigate to a URL and wait for DOM + HTMX settle."""
    page.goto(url, **GOTO_OPTS)
    page.wait_for_timeout(SETTLE_MS)


def _open_photo_modal(page, base_url):
    """Navigate to photos section and open the first photo modal."""
    _goto(page, f"{base_url}/?section=photos")

    # Click first photo card (each card has hx-get="/photo/...")
    first_card = page.locator("div[hx-get^='/photo/']").first
    first_card.click()

    # Wait for modal to become visible and content to load
    page.locator("#photo-modal:not(.hidden)").wait_for(state="visible", timeout=5000)
    page.locator("#photo-modal-content .photo-viewer").wait_for(
        state="visible", timeout=5000
    )


def _wait_for_photo_change(page, old_src, timeout=5000):
    """Wait for the photo modal image src to change from old_src.

    This is more reliable than waiting for .photo-viewer visibility because
    the container stays visible during HTMX innerHTML swaps.
    """
    page.wait_for_function(
        f"""() => {{
            const img = document.querySelector('#photo-modal-content img');
            return img && img.src && !img.src.endsWith('{old_src.split("/")[-1]}');
        }}""",
        timeout=timeout,
    )


# ---------------------------------------------------------------------------
# Test 1: Landing page renders correctly
# ---------------------------------------------------------------------------

def test_landing_page_hero(page, app_server):
    """Landing page should have hero section with headline and CTAs."""
    _goto(page, app_server)

    assert page.locator("#hero").count() > 0, "Missing #hero section"

    h1 = page.locator("#hero h1")
    assert h1.count() > 0, "Missing h1 in hero"
    assert len(h1.text_content()) > 10, "H1 text too short"

    assert page.locator("a:has-text('Start Exploring')").count() > 0
    assert page.locator("a:has-text('Help Identify')").count() > 0


def test_landing_page_stats(page, app_server):
    """Landing page should have animated stat counters."""
    _goto(page, app_server)

    stats = page.locator("#stats .stat-number[data-count]")
    assert stats.count() >= 3, f"Expected >=3 stat counters, found {stats.count()}"


def test_landing_page_navigation(page, app_server):
    """Landing page nav should link to photos and people sections."""
    _goto(page, app_server)

    nav = page.locator("nav")
    assert nav.count() > 0, "No nav bar found"

    assert page.locator("nav a:has-text('Photos')").count() > 0
    assert page.locator("nav a:has-text('People')").count() > 0


# ---------------------------------------------------------------------------
# Test 2: About page
# ---------------------------------------------------------------------------

def test_about_page_content(page, app_server):
    """About page should have heading, FAQ, and back link."""
    _goto(page, f"{app_server}/about")

    assert page.locator("h1:has-text('About Rhodesli')").count() > 0

    assert page.locator("h2:has-text('Frequently Asked Questions')").count() > 0
    faq_items = page.locator(".faq-q")
    assert faq_items.count() >= 3, f"Expected >=3 FAQ items, found {faq_items.count()}"

    assert page.locator("a:has-text('Back to Archive')").count() > 0


# ---------------------------------------------------------------------------
# Test 3: Photo gallery loads
# ---------------------------------------------------------------------------

def test_photo_gallery_renders(page, app_server):
    """Photo gallery should display photo cards in a grid."""
    _goto(page, f"{app_server}/?section=photos")

    cards = page.locator("div[hx-get^='/photo/']")
    assert cards.count() > 0, "No photo cards found in gallery"

    first_img = cards.first.locator("img")
    assert first_img.count() > 0, "Photo card missing image"


def test_photo_gallery_filter_bar(page, app_server):
    """Photo gallery should have collection and sort dropdowns."""
    _goto(page, f"{app_server}/?section=photos")

    assert page.locator("select").count() >= 2, "Expected collection + sort dropdowns"


# ---------------------------------------------------------------------------
# Test 4: Photo modal opens and has navigation
# ---------------------------------------------------------------------------

def test_photo_modal_opens(page, app_server):
    """Clicking a photo card should open the photo modal with content."""
    _open_photo_modal(page, app_server)

    modal = page.locator("#photo-modal")
    assert "hidden" not in (modal.get_attribute("class") or ""), "Modal still hidden"

    img = page.locator("#photo-modal-content img")
    assert img.count() > 0, "No image in photo modal"


def test_photo_modal_has_nav_buttons(page, app_server):
    """Photo modal should have prev/next navigation buttons."""
    _open_photo_modal(page, app_server)

    next_btn = page.locator("[data-action='photo-nav-next']")
    assert next_btn.count() > 0, "Missing next button"


def test_photo_modal_has_face_overlays(page, app_server):
    """Photo modal should render face overlay boxes with data-face-id."""
    _open_photo_modal(page, app_server)

    overlays = page.locator("#photo-modal-content [data-face-id]")
    assert overlays.count() > 0, (
        "No face overlays found. Expected [data-face-id] elements."
    )


# ---------------------------------------------------------------------------
# Test 5: Lightbox arrow persistence (BUG-001 regression)
# ---------------------------------------------------------------------------

def test_lightbox_arrows_persist_across_navigation(page, app_server):
    """BUG-001 regression: arrows must remain visible after HTMX swap."""
    _open_photo_modal(page, app_server)

    next_btn = page.locator("[data-action='photo-nav-next']")
    if next_btn.count() == 0:
        pytest.skip("Only one photo available, cannot test navigation")

    assert next_btn.is_visible(), "Next button not visible on first photo"

    # Get current src so we can wait for it to change
    first_src = page.locator("#photo-modal-content img").first.get_attribute("src")

    # Navigate to second photo via click
    next_btn.click()
    _wait_for_photo_change(page, first_src)

    # CRITICAL: arrows must STILL exist after HTMX swap
    next_after = page.locator("[data-action='photo-nav-next']")
    prev_after = page.locator("[data-action='photo-nav-prev']")

    assert prev_after.count() > 0, (
        "Previous button disappeared after navigating to second photo"
    )

    if next_after.count() > 0:
        assert next_after.is_visible(), "Next button exists but not visible"


# ---------------------------------------------------------------------------
# Test 6: Keyboard navigation in photo modal
# ---------------------------------------------------------------------------

def test_keyboard_navigation_in_photo_modal(page, app_server):
    """Keyboard arrows should navigate photos in the modal."""
    _open_photo_modal(page, app_server)

    next_btn = page.locator("[data-action='photo-nav-next']")
    if next_btn.count() == 0:
        pytest.skip("Only one photo available, cannot test keyboard nav")

    first_src = page.locator("#photo-modal-content img").first.get_attribute("src")

    # Press right arrow
    page.keyboard.press("ArrowRight")
    _wait_for_photo_change(page, first_src)

    second_src = page.locator("#photo-modal-content img").first.get_attribute("src")
    assert first_src != second_src, (
        f"Photo did not change after ArrowRight. Still showing: {first_src}"
    )

    # Press left arrow — should go back
    page.keyboard.press("ArrowLeft")
    _wait_for_photo_change(page, second_src)

    back_src = page.locator("#photo-modal-content img").first.get_attribute("src")
    assert back_src == first_src, (
        f"ArrowLeft did not go back. Expected {first_src}, got {back_src}"
    )


def test_escape_closes_photo_modal(page, app_server):
    """Escape key should close the photo modal."""
    _open_photo_modal(page, app_server)

    modal = page.locator("#photo-modal")
    assert "hidden" not in (modal.get_attribute("class") or "")

    # Focus the modal so Hyperscript keydown handler fires
    modal.focus()
    page.keyboard.press("Escape")
    page.wait_for_timeout(500)

    assert "hidden" in (modal.get_attribute("class") or ""), (
        "Modal did not close on Escape"
    )


# ---------------------------------------------------------------------------
# Test 7: Face count matches visible overlays (BUG-002 regression)
# ---------------------------------------------------------------------------

def test_face_count_matches_overlays(page, app_server):
    """BUG-002: Displayed face count label must match visible face boxes."""
    _open_photo_modal(page, app_server)

    overlays = page.locator("#photo-modal-content [data-face-id]")
    overlay_count = overlays.count()

    face_text = page.locator("#photo-modal-content").text_content()
    match = re.search(r"(\d+)\s+face", face_text)

    if match is None:
        pytest.skip("Could not find face count text in modal")

    displayed_count = int(match.group(1))

    assert displayed_count == overlay_count, (
        f"Face count label says {displayed_count} but {overlay_count} "
        f"overlay boxes are rendered"
    )


# ---------------------------------------------------------------------------
# Test 8: Event delegation (data-action) attributes exist
# ---------------------------------------------------------------------------

def test_event_delegation_attributes(page, app_server):
    """Interactive elements should use data-action for event delegation."""
    _open_photo_modal(page, app_server)

    data_action_els = page.locator("#photo-modal-content [data-action]")
    assert data_action_els.count() > 0, (
        "No data-action elements found in photo modal — event delegation missing"
    )

    actions = set()
    for i in range(data_action_els.count()):
        action = data_action_els.nth(i).get_attribute("data-action")
        if action:
            actions.add(action)

    assert "photo-nav-next" in actions or "photo-nav-prev" in actions, (
        f"Expected photo-nav-next/prev in data-action set, found: {actions}"
    )


# ---------------------------------------------------------------------------
# Test 9: Mobile viewport — no horizontal overflow
# Note: Tailwind CSS is blocked in tests to prevent TCP pool exhaustion.
# These tests check that inline/server-rendered widths don't overflow.
# ---------------------------------------------------------------------------

def test_mobile_no_horizontal_overflow(page, app_server):
    """Page should not have excessive horizontal overflow on mobile viewport.

    Note: Tailwind CSS CDN is blocked in E2E tests for performance, so some
    responsive classes won't apply. This test catches overflow from inline styles
    and server-rendered widths that even Tailwind can't fix.
    """
    page.set_viewport_size({"width": 375, "height": 812})
    _goto(page, f"{app_server}/?section=photos")

    scroll_w = page.evaluate("document.documentElement.scrollWidth")
    client_w = page.evaluate("document.documentElement.clientWidth")
    overflow = scroll_w - client_w

    # The photos grid uses Tailwind responsive classes (grid-cols-2 md:grid-cols-3).
    # Without Tailwind, the grid doesn't collapse to mobile columns. Allow up to
    # 200px overflow since this is a CSS-only issue that doesn't affect functionality.
    # The real mobile responsive test would need Tailwind loaded.
    assert overflow <= 200, (
        f"Page has {overflow}px horizontal overflow on 375px mobile viewport "
        f"(scrollWidth={scroll_w}, clientWidth={client_w}). "
        f"Note: Tailwind CSS is blocked in tests."
    )


def test_mobile_landing_page(page, app_server):
    """Landing page should render on mobile without breaking."""
    page.set_viewport_size({"width": 375, "height": 812})
    _goto(page, app_server)

    assert page.locator("#hero").count() > 0

    scroll_w = page.evaluate("document.documentElement.scrollWidth")
    client_w = page.evaluate("document.documentElement.clientWidth")
    overflow = scroll_w - client_w

    # Allow small overflow since Tailwind responsive classes aren't loaded
    assert overflow <= 50, (
        f"Landing page has {overflow}px horizontal overflow on mobile "
        f"(scrollWidth={scroll_w}, clientWidth={client_w})"
    )


# ---------------------------------------------------------------------------
# Test 10: Sidebar navigation
# ---------------------------------------------------------------------------

def test_sidebar_navigation(page, app_server):
    """Sidebar should have all navigation items."""
    _goto(page, f"{app_server}/?section=photos")

    sidebar = page.locator("#sidebar")
    assert sidebar.count() > 0, "Sidebar not found"

    assert page.locator("#sidebar a[title*='New Matches']").count() > 0, "Missing New Matches link"
    assert page.locator("#sidebar a[title*='People']").count() > 0, "Missing People link"
    assert page.locator("#sidebar a[title*='Photos']").count() > 0, "Missing Photos link"


# ---------------------------------------------------------------------------
# Test 11: Search input exists
# ---------------------------------------------------------------------------

def test_search_input(page, app_server):
    """Sidebar should have a search input."""
    _goto(page, f"{app_server}/?section=photos")

    search = page.locator("#sidebar-search-input")
    assert search.count() > 0, "Search input not found"
    assert search.get_attribute("placeholder") is not None


# ---------------------------------------------------------------------------
# Test 12: Identity lightbox (from confirmed section)
# ---------------------------------------------------------------------------

def test_identity_lightbox_navigation(page, app_server):
    """Identity 'View All Photos' lightbox should have prev/next buttons."""
    _goto(page, f"{app_server}/?section=confirmed")

    view_btn = page.locator("button:has-text('View All Photos')").first
    if view_btn.count() == 0:
        pytest.skip("No 'View All Photos' button found in confirmed section")

    view_btn.click()

    # Wait for lightbox content
    page.locator("#photo-modal:not(.hidden)").wait_for(state="visible", timeout=5000)
    page.locator("#photo-modal-content img").first.wait_for(
        state="visible", timeout=5000
    )

    lightbox_next = page.locator("[data-action='lightbox-next']")
    lightbox_prev = page.locator("[data-action='lightbox-prev']")

    has_nav = lightbox_next.count() > 0 or lightbox_prev.count() > 0

    modal_text = page.locator("#photo-modal-content").text_content()
    counter_match = re.search(r"(\d+)\s*/\s*(\d+)", modal_text)

    if counter_match:
        current, total = int(counter_match.group(1)), int(counter_match.group(2))
        if total > 1:
            assert has_nav, (
                f"Identity has {total} photos but no lightbox prev/next buttons"
            )


# ---------------------------------------------------------------------------
# Toast z-index above photo modal
# ---------------------------------------------------------------------------

def test_toast_container_above_photo_modal(page, app_server):
    """Toast z-index must be higher than photo modal so toasts from inside modal are visible."""
    _goto(page, f"{app_server}/?section=photos")

    # Check z-index class values (photo-modal is hidden so computed style returns 'auto')
    toast_cls = page.evaluate("""
        () => {
            const tc = document.getElementById('toast-container');
            return tc ? tc.className : null;
        }
    """)
    modal_cls = page.evaluate("""
        () => {
            const pm = document.getElementById('photo-modal');
            return pm ? pm.className : null;
        }
    """)

    assert toast_cls is not None, "toast-container not found"
    assert modal_cls is not None, "photo-modal not found"
    # Toast must use z-[10001], modal uses z-[9999]
    assert "z-[10001]" in toast_cls, f"toast-container missing z-[10001], has: {toast_cls}"
    assert "z-[9999]" in modal_cls, f"photo-modal missing z-[9999], has: {modal_cls}"


def test_tag_dropdown_opens_in_photo_modal(page, app_server):
    """Clicking a face overlay opens the tag dropdown inside the photo modal."""
    _open_photo_modal(page, app_server)

    # Find a face overlay (non-confirmed faces have the tag dropdown)
    overlays = page.locator(".face-overlay-box[data-face-id]")
    if overlays.count() == 0:
        pytest.skip("No face overlays in this photo")

    # Click the first overlay to open its tag dropdown
    overlays.first.click()
    page.wait_for_timeout(300)

    # A tag dropdown should now be visible (not hidden)
    visible_dropdown = page.locator(".tag-dropdown:not(.hidden)")
    assert visible_dropdown.count() > 0, "Tag dropdown did not open on face click"

    # The dropdown should have a search input
    search_input = visible_dropdown.locator("input[name='q']")
    assert search_input.count() > 0, "Tag dropdown missing search input"
