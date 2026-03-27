"""Structural tests for _main_mod references and test quality guards.

A1 — Session 141 Track A.
Ensures every _main_mod.X reference in route files resolves to an actual
attribute in app.main, preventing the silent breakage that occurred when
auth functions were not re-exported (Session 140, Lesson 157).
"""

import os
import re

import pytest


def test_all_main_mod_references_resolve():
    """Every _main_mod.X reference in route files must exist in app.main."""
    import app.main as m

    route_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app")
    route_files = [f for f in os.listdir(route_dir) if f.endswith("_routes.py")]
    assert route_files, "No route files found — test setup broken"

    missing = []
    for fname in route_files:
        with open(os.path.join(route_dir, fname)) as fh:
            refs = set(re.findall(r"_main_mod\.(\w+)", fh.read()))
        for ref in refs:
            if not hasattr(m, ref):
                missing.append(f"{fname}: _main_mod.{ref}")

    assert not missing, "Broken _main_mod references:\n" + "\n".join(f"  - {m}" for m in sorted(missing))


@pytest.mark.xfail(reason="17 create=True patches exist — track and reduce over time")
def test_no_create_true_in_mock_patches():
    """Flag mock patches that use create=True — these mask missing attributes.

    create=True in unittest.mock.patch() silently creates attributes that don't
    exist on the target, which hides real breakage. Each usage should be
    reviewed: if the attribute genuinely doesn't exist, fix the code; if it's
    a deliberate test-only extension, add a # noqa: create-true comment.

    Marked xfail so CI stays green while the count is tracked. When all
    create=True patches are removed (or annotated with # noqa: create-true),
    this test will xpass — signaling the xfail marker can be removed.
    """
    test_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tests")
    # Pattern: patch(..., create=True) in various forms
    create_true_pattern = re.compile(r"patch\([^)]*create\s*=\s*True")

    flagged = []
    for root, _dirs, files in os.walk(test_dir):
        for fname in files:
            if not fname.endswith(".py"):
                continue
            fpath = os.path.join(root, fname)
            with open(fpath) as fh:
                content = fh.read()
            for i, line in enumerate(content.splitlines(), 1):
                if create_true_pattern.search(line) and "# noqa: create-true" not in line:
                    rel = os.path.relpath(fpath, test_dir)
                    flagged.append(f"{rel}:{i}: {line.strip()}")

    assert not flagged, (
        f"Found {len(flagged)} mock patch(es) with create=True (review and remove or add '# noqa: create-true'):\n"
        + "\n".join(f"  - {f}" for f in flagged[:20])
    )


class TestToastWithMergeUndo:
    """Tests for FB-002: merge toast includes link to surviving identity."""

    def test_toast_contains_view_link(self):
        """Toast should include a link to the merged identity's person page."""
        from app.identity_routes import toast_with_merge_undo

        result = toast_with_merge_undo(
            "Merged 3 faces into Albert Fox.",
            "test-id-123",
            nav_prefix="/c/rhodes",
            target_name="Albert Fox",
        )
        html = repr(result)
        assert "/c/rhodes/person/test-id-123" in html
        assert "View Albert Fox" in html

    def test_toast_view_link_unnamed_identity(self):
        """For unidentified persons, the link should say just 'View'."""
        from app.identity_routes import toast_with_merge_undo

        result = toast_with_merge_undo(
            "Merged 2 faces into Unidentified Person 42.",
            "test-id-456",
            nav_prefix="/c/rhodes",
            target_name="Unidentified Person 42",
        )
        html = repr(result)
        assert "/c/rhodes/person/test-id-456" in html
        # Should say "View" not "View Unidentified Person 42"
        assert "View Unidentified" not in html
        assert ">View<" in html or ">View " in html

    def test_toast_view_link_no_name(self):
        """When target_name is empty, link should say just 'View'."""
        from app.identity_routes import toast_with_merge_undo

        result = toast_with_merge_undo(
            "Merged 1 face.",
            "test-id-789",
            nav_prefix="",
            target_name="",
        )
        html = repr(result)
        assert "/person/test-id-789" in html
        assert ">View<" in html or ">View " in html

    def test_toast_still_has_undo_button(self):
        """Ensure the undo button is still present alongside the new link."""
        from app.identity_routes import toast_with_merge_undo

        result = toast_with_merge_undo(
            "Merged 3 faces into Albert Fox.",
            "test-id-123",
            nav_prefix="/c/rhodes",
            target_name="Albert Fox",
        )
        html = repr(result)
        assert "Undo" in html
        assert "undo-merge" in html
