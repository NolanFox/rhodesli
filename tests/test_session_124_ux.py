"""Tests for Session 124 — UX improvements from Antigravity design audit."""

import re

from pathlib import Path


def test_mobile_close_button_touch_target():
    """Mobile nav close button must have at least p-3 for 44px touch target."""
    main_py = Path("app/main.py").read_text()
    # Find the fallback close button (non-JS mobile nav)
    # Should use p-3 not p-1
    assert 'cls="text-slate-400 hover:text-white p-3 -mr-2 -mt-2"' in main_py, (
        "Fallback mobile close button should have p-3 padding for 44px touch target"
    )


def test_active_learning_buttons_responsive_padding():
    """Active learning Same/Different buttons should be touch-friendly on mobile."""
    routes = Path("app/cluster_review_routes.py").read_text()
    # Should have responsive padding: larger on mobile, compact on desktop
    assert "py-3 sm:px-3 sm:py-1.5" in routes, (
        "Active learning buttons should have responsive padding (py-3 mobile, py-1.5 desktop)"
    )


def test_identity_group_buttons_responsive_padding():
    """Identity group Confirm All/Reject All buttons should be touch-friendly on mobile."""
    routes = Path("app/cluster_review_routes.py").read_text()
    # The batch action buttons should have responsive padding
    lines = routes.split("\n")
    confirm_all_found = False
    for i, line in enumerate(lines):
        if '"Confirm All"' in line and "identity_id" in routes.split("\n")[i + 3]:
            # Check nearby cls line for responsive padding
            context = "\n".join(lines[max(0, i - 2) : i + 5])
            if "py-3 sm:px-3 sm:py-1.5" in context:
                confirm_all_found = True
                break
    assert confirm_all_found, "Identity group batch buttons should have responsive padding"
