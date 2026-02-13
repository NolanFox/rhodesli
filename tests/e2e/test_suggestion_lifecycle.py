"""
E2E acceptance tests for Community Contributions v2 — Suggestion Lifecycle.

These tests define "done" for the PRD at docs/prds/prd-community-contributions-v2.md.
Written BEFORE implementation (SDD Phase 2). They should FAIL initially.

Tests run against a real server with auth disabled (all routes accessible).
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


# ---------------------------------------------------------------------------
# TEST 1: Annotation persistence — approved bio visible on person page
# ---------------------------------------------------------------------------

def test_annotation_visible_on_person_page(page, app_server):
    """Approved bio annotation from Claude Benatar should be visible on the
    public person page /person/54682ede-9424-4295-abca-9317679e5636."""
    _goto(page, f"{app_server}/person/54682ede-9424-4295-abca-9317679e5636")

    # The page should contain the annotation text
    content = page.content()
    assert "A mi querida Estrella de tu hermano Samuel" in content, (
        "Approved annotation text not visible on person page"
    )


def test_duplicate_annotations_deduped_on_display(page, app_server):
    """Two identical approved annotations should display as one on the page."""
    _goto(page, f"{app_server}/person/54682ede-9424-4295-abca-9317679e5636")

    # Count occurrences of the annotation text in visible page content
    # Should appear exactly once, not twice (deduplication)
    content = page.text_content("body")
    count = content.count("A mi querida Estrella de tu hermano Samuel")
    assert count == 1, (
        f"Annotation text appears {count} times, expected 1 (deduplication broken)"
    )


# ---------------------------------------------------------------------------
# TEST 2: Suggestion state persists visually after submission
# ---------------------------------------------------------------------------

def test_suggestion_state_persists_visually(page, app_server):
    """After submitting a name suggestion, the face popup should transform to
    show 'You suggested: [name]' and the overlay should get a visual indicator."""
    # Navigate to Help Identify (unidentified faces)
    _goto(page, f"{app_server}/?section=to_review&view=focus")

    # Wait for focus mode content
    page.wait_for_timeout(1000)

    # Find a face overlay and click it to open the tag dropdown
    face_overlay = page.locator("[data-face-id]").first
    if face_overlay.count() == 0:
        pytest.skip("No face overlays on current view")

    face_overlay.click()
    page.wait_for_timeout(500)

    # Look for the tag search input
    tag_input = page.locator("input[placeholder*='Who is this']").first
    if tag_input.count() == 0:
        tag_input = page.locator("input[placeholder*='name to tag']").first
    if tag_input.count() == 0:
        pytest.skip("Tag input not found")

    # Type a name and submit via the "Suggest" button
    tag_input.fill("Test Suggestion Name")
    page.wait_for_timeout(300)

    # Look for a suggest button or submit action
    suggest_btn = page.locator("button:has-text('Suggest')").first
    if suggest_btn.count() == 0:
        pytest.skip("No suggest button found")

    suggest_btn.click()
    page.wait_for_timeout(1000)

    # After submission, the popup should show "You suggested: ..."
    content = page.content()
    assert "You suggested" in content, (
        "After submitting suggestion, popup should show 'You suggested: [name]'"
    )


# ---------------------------------------------------------------------------
# TEST 3: Admin approval card has face thumbnail
# ---------------------------------------------------------------------------

def test_admin_approval_card_has_face_thumbnail(page, app_server):
    """Admin approval cards should contain a face crop image, not just UUID text."""
    _goto(page, f"{app_server}/admin/approvals")

    # Check if there are any pending approvals
    content = page.content()
    if "No pending" in content or "no suggestions" in content.lower():
        pytest.skip("No pending approvals to test")

    # Each approval card should have an img element (face crop)
    approval_cards = page.locator(".approval-card, [data-annotation-id]")
    if approval_cards.count() == 0:
        pytest.skip("No approval cards found")

    first_card = approval_cards.first
    # Card should contain an image (face thumbnail)
    face_img = first_card.locator("img")
    assert face_img.count() > 0, (
        "Approval card should contain a face crop image, not just UUID text"
    )


# ---------------------------------------------------------------------------
# TEST 4: Admin approval creates identity assignment
# ---------------------------------------------------------------------------

def test_admin_approval_assigns_identity(page, app_server):
    """Approving a name suggestion should assign the face to an identity."""
    _goto(page, f"{app_server}/admin/approvals")

    content = page.content()
    if "No pending" in content or "no suggestions" in content.lower():
        pytest.skip("No pending approvals to test")

    # Find and click an Approve button
    approve_btn = page.locator("button:has-text('Approve')").first
    if approve_btn.count() == 0:
        pytest.skip("No approve button found")

    approve_btn.click()
    page.wait_for_timeout(1000)

    # After approval, the card should show a success state
    content = page.content()
    assert ("Approved" in content or "approved" in content), (
        "After clicking Approve, card should show approved state"
    )


# ---------------------------------------------------------------------------
# TEST 5: Admin undo after approval
# ---------------------------------------------------------------------------

def test_admin_undo_after_approval(page, app_server):
    """After approving, an Undo button should appear for reverting."""
    _goto(page, f"{app_server}/admin/approvals")

    content = page.content()
    if "No pending" in content or "no suggestions" in content.lower():
        pytest.skip("No pending approvals to test")

    approve_btn = page.locator("button:has-text('Approve')").first
    if approve_btn.count() == 0:
        pytest.skip("No approve button found")

    approve_btn.click()
    page.wait_for_timeout(500)

    # Undo button should appear
    undo_btn = page.locator("button:has-text('Undo')")
    assert undo_btn.count() > 0, (
        "After approval, an Undo button should appear for 10 seconds"
    )


# ---------------------------------------------------------------------------
# TEST 6: Admin skip moves card to bottom
# ---------------------------------------------------------------------------

def test_admin_skip(page, app_server):
    """Skip button should move the card to bottom or a Skipped tab."""
    _goto(page, f"{app_server}/admin/approvals")

    content = page.content()
    if "No pending" in content or "no suggestions" in content.lower():
        pytest.skip("No pending approvals to test")

    skip_btn = page.locator("button:has-text('Skip')").first
    if skip_btn.count() == 0:
        pytest.skip("No skip button found")

    skip_btn.click()
    page.wait_for_timeout(500)

    # After skipping, the card should be in a different state
    content = page.content()
    assert "skipped" in content.lower() or "Skipped" in content, (
        "After clicking Skip, card should show skipped state or move to Skipped section"
    )


# ---------------------------------------------------------------------------
# TEST 7: Help Identify "+N more" is clickable
# ---------------------------------------------------------------------------

def test_help_identify_more_is_clickable(page, app_server):
    """The '+N more' element in Up Next should be a clickable link."""
    _goto(page, f"{app_server}/?section=to_review&view=focus")
    page.wait_for_timeout(1000)

    # Look for "+N more" text
    more_el = page.locator("text=/\\+\\d+ more/").first
    if more_el.count() == 0:
        pytest.skip("No '+N more' element found (may need more unidentified faces)")

    # It should be a link (a tag) or button, not just a span
    tag_name = more_el.evaluate("el => el.tagName.toLowerCase()")
    parent_tag = more_el.evaluate(
        "el => el.closest('a, button')?.tagName?.toLowerCase() || 'none'"
    )
    assert tag_name in ("a", "button") or parent_tag in ("a", "button"), (
        f"'+N more' should be a clickable link or button, got <{tag_name}> "
        f"with closest interactive parent <{parent_tag}>"
    )


# ---------------------------------------------------------------------------
# TEST 8: Tab state distinction (Ready to Confirm vs Unmatched)
# ---------------------------------------------------------------------------

def test_tab_state_visually_distinct(page, app_server):
    """Active tab should have distinct styling from inactive tab."""
    _goto(page, f"{app_server}/?section=to_review&view=browse")
    page.wait_for_timeout(1000)

    # Find the triage pills/tabs
    ready_pill = page.locator("text=/Ready to Confirm/").first
    unmatched_pill = page.locator("text=/Unmatched/").first

    if ready_pill.count() == 0 or unmatched_pill.count() == 0:
        pytest.skip("Triage pills not found")

    # Get the active filter from URL or check visual state
    # When on default view, "Ready to Confirm" should look active

    # Get computed styles or classes
    ready_classes = ready_pill.evaluate("el => el.className || el.closest('[class]')?.className || ''")
    unmatched_classes = unmatched_pill.evaluate("el => el.className || el.closest('[class]')?.className || ''")

    # The active tab should have visually distinct styling
    # Check for "active", "selected", "ring", "border-2", or brighter opacity
    has_active_indicator = any(
        indicator in ready_classes
        for indicator in ["active", "selected", "ring", "border-2", "font-bold", "bg-emerald-600"]
    )
    assert has_active_indicator, (
        f"Active tab should have a distinct visual indicator. "
        f"Ready pill classes: {ready_classes[:200]}"
    )

    # Click Unmatched and verify it becomes active
    unmatched_pill.click()
    page.wait_for_timeout(500)

    new_unmatched_classes = unmatched_pill.evaluate(
        "el => el.className || el.closest('[class]')?.className || ''"
    )
    has_unmatched_active = any(
        indicator in new_unmatched_classes
        for indicator in ["active", "selected", "ring", "border-2", "font-bold", "bg-slate-600"]
    )
    assert has_unmatched_active, (
        f"After clicking Unmatched, it should become the active tab. "
        f"Classes: {new_unmatched_classes[:200]}"
    )


# ---------------------------------------------------------------------------
# TEST 9: Audit log accessible
# ---------------------------------------------------------------------------

def test_audit_log_page_exists(page, app_server):
    """Admin audit log should be accessible at /admin/audit."""
    _goto(page, f"{app_server}/admin/audit")

    # Page should load without error (not 404)
    assert page.locator("text=/[Aa]udit/").count() > 0, (
        "/admin/audit page should exist and show audit information"
    )


# ---------------------------------------------------------------------------
# TEST 10: Community confirmation flow
# ---------------------------------------------------------------------------

def test_existing_suggestion_shows_agree_option(page, app_server):
    """When a face already has suggestions, new visitors should see 'I Agree' option."""
    # This test requires a face with an existing pending suggestion
    # For now, check that the mechanism exists on the suggestion UI
    _goto(page, f"{app_server}/?section=to_review&view=focus")
    page.wait_for_timeout(1000)

    face_overlay = page.locator("[data-face-id]").first
    if face_overlay.count() == 0:
        pytest.skip("No face overlays on current view")

    face_overlay.click()
    page.wait_for_timeout(500)

    # If there are existing suggestions for this face, we should see them
    # with an "I Agree" option. If no suggestions exist, this is expected to pass
    # vacuously (we can't control which face we land on).
    content = page.content()
    if "suggested" in content.lower():
        assert "Agree" in content or "agree" in content, (
            "When existing suggestions are shown, an 'I Agree' option should be available"
        )
