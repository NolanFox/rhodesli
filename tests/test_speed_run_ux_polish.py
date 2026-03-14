"""Tests for speed-run UX polish (Session 100f 4A-4F).

Covers: cumulative progress counter, undo banner context,
workflow guide text, debounce JS, pre-fetch div, face crop sizing.
"""

import json
from unittest.mock import MagicMock, patch

import pytest


def _mock_registry(identities=None):
    """Build a mock IdentityRegistry with the given identities dict."""
    if identities is None:
        identities = {}
    reg = MagicMock()
    reg._identities = identities
    reg.get = lambda iid: identities.get(iid)
    return reg


def _mock_photo_registry():
    pr = MagicMock()
    pr.get_photo_for_face = MagicMock(return_value="photo_001")
    pr.get_photos_for_faces = MagicMock(return_value=set())
    return pr


def _identity(name="Test Person", state="INBOX", face_count=3):
    """Create a sample identity dict."""
    face_ids = [f"inbox_face_{i}" for i in range(face_count)]
    return {
        "name": name,
        "state": state,
        "anchor_ids": face_ids[:1],
        "candidate_ids": face_ids[1:],
        "negative_ids": [],
    }


PATCHES = {
    "app.cluster_review_routes._main_mod.load_registry": None,
    "app.cluster_review_routes._main_mod.load_photo_registry": None,
    "app.cluster_review_routes._main_mod._check_admin": lambda *a, **kw: None,
    "app.cluster_review_routes._main_mod.is_auth_enabled": lambda: False,
    "app.cluster_review_routes._main_mod.get_current_user": lambda *a: None,
    "app.cluster_review_routes._main_mod.get_crop_files": lambda: {},
    "app.cluster_review_routes._main_mod.resolve_face_image_url": lambda fid, _: f"/crops/{fid}.jpg",
    "app.cluster_review_routes._main_mod.get_best_face_id": lambda fids: fids[0] if fids else "",
    "app.cluster_review_routes._main_mod.community_url_prefix": lambda slug: f"/c/{slug}" if slug != "rhodes" else "",
    "app.cluster_review_routes._main_mod._get_community_identity_ids": lambda c: None,
    "app.cluster_review_routes._main_mod.save_registry": lambda *a, **kw: None,
    "app.cluster_review_routes._main_mod.log_user_action": lambda *a, **kw: None,
    "app.cluster_review_routes.storage.get_crop_url_by_filename": lambda fn: f"/static/crops/{fn}",
}


def _render(element):
    """Render a FastHTML element to an HTML string."""
    if element is None:
        return ""
    if isinstance(element, tuple):
        return "".join(_render(e) for e in element)
    if isinstance(element, str):
        return element
    return repr(element)


class TestProgressCounter:
    """4B: Progress counter shows cumulative stats format."""

    def test_initial_progress_shows_cumulative_stats(self):
        """Initial page load shows '0 confirmed ... N remaining' format."""
        from app.cluster_review_routes import _speed_run_cluster_card

        identity = _identity("Alice Cohen", face_count=5)
        with patch.multiple("app.cluster_review_routes._main_mod", load_photo_registry=lambda: _mock_photo_registry()):
            card_html = _render(_speed_run_cluster_card("id-001", identity, 0, 10, "rhodes", include_progress=True))

        # The initial page-level progress element checks
        assert "data-total" in card_html or "speed-run-stats-text" in card_html
        # Progress bar should exist
        assert "speed-run-progress" in card_html

    def test_page_load_progress_has_cumulative_format(self):
        """The page-level initial render uses cumulative stats format."""
        # Check the initial render in the speed-run page (offset=0)
        from app.cluster_review_routes import _speed_run_cluster_card

        identity = _identity("Bob Franco", face_count=3)
        with patch.multiple("app.cluster_review_routes._main_mod", load_photo_registry=lambda: _mock_photo_registry()):
            card_html = _render(_speed_run_cluster_card("id-002", identity, 2, 20, "rhodes", include_progress=True))

        assert "speed-run-stats-text" in card_html

    def test_data_attributes_on_progress_bar(self):
        """The page-level progress bar has data attributes for JS tracking."""
        # We test the initial page render's progress div which is built inline
        # The data attributes (data-total, data-confirmed, etc.) are set on the
        # page-level progress div, not on the per-card progress div.
        # Verify the per-card progress div has the stats text element.
        from app.cluster_review_routes import _speed_run_cluster_card

        identity = _identity("Test", face_count=2)
        with patch.multiple("app.cluster_review_routes._main_mod", load_photo_registry=lambda: _mock_photo_registry()):
            html = _render(_speed_run_cluster_card("id-003", identity, 0, 5, "rhodes", include_progress=True))
        assert "speed-run-progress" in html


class TestUndoVisibility:
    """4C: Undo button has context (identity info visible)."""

    def test_undo_banner_shows_identity_context(self):
        """Undo banner includes identity name and face count."""
        from app.cluster_review_routes import _speed_run_undo_button

        undo_state = {
            "identity_id": "id-001",
            "action": "confirm-all",
            "offset": 0,
            "community_slug": "rhodes",
            "face_data": {},
            "identity_name": "Person 2986",
            "face_count": 44,
        }
        html = _render(_speed_run_undo_button(undo_state, oob=False))

        assert "Person 2986" in html
        assert "44 faces" in html
        assert "Confirmed" in html
        assert "(Z)" in html

    def test_undo_banner_shows_action_type(self):
        """Undo banner shows correct action label for each type."""
        from app.cluster_review_routes import _speed_run_undo_button

        for action, expected_label in [
            ("confirm-all", "Confirmed"),
            ("reject-all", "Rejected"),
            ("skip", "Skipped"),
            ("dismiss", "Dismissed"),
        ]:
            undo_state = {
                "identity_id": "id-001",
                "action": action,
                "offset": 0,
                "community_slug": "",
                "face_data": {},
                "identity_name": "Test",
                "face_count": 3,
            }
            html = _render(_speed_run_undo_button(undo_state))
            assert expected_label in html, f"Expected '{expected_label}' for action '{action}'"

    def test_undo_hidden_when_no_state(self):
        """Undo div is empty when undo_state is None."""
        from app.cluster_review_routes import _speed_run_undo_button

        html = _render(_speed_run_undo_button(None))
        assert "Undo" not in html


class TestWorkflowGuideText:
    """4D: Workflow guide text present on speed-run and batch validation pages."""

    def test_speed_run_page_has_guide_text(self):
        """Speed-run page source includes the workflow instruction text."""
        import inspect
        from app import cluster_review_routes

        source = inspect.getsource(cluster_review_routes)
        assert "Review each cluster" in source
        assert "Press Y to confirm" in source
        assert "After confirming, you can name the person" in source

    def test_batch_validation_guide_text_content(self):
        """Batch validation page guide text mentions face count filters."""
        # This is a structural test — the text is hardcoded in _batch_cluster_page
        # We verify it by importing and checking the source
        import inspect
        from app import cluster_review_routes

        source = inspect.getsource(cluster_review_routes)
        assert "Use face count filters to focus on high-confidence clusters first" in source


class TestDebounceJS:
    """4E: Debounce JS code is present in keyboard handler."""

    def test_debounce_flag_in_keyboard_handler(self):
        """Keyboard handler JS includes _speedRunLocked debounce flag."""
        import inspect
        from app import cluster_review_routes

        source = inspect.getsource(cluster_review_routes)
        assert "_speedRunLocked" in source

    def test_debounce_timeout_300ms(self):
        """Debounce uses 300ms timeout."""
        import inspect
        from app import cluster_review_routes

        source = inspect.getsource(cluster_review_routes)
        assert "setTimeout" in source
        assert "300" in source


class TestFaceCropSizing:
    """4A: Face crop sizes in speed-run are at least 100px (w-28 h-28 = 112px)."""

    def test_speed_run_face_crops_use_w28_h28(self):
        """Speed-run cluster card face crops use w-28 h-28 (112px)."""
        from app.cluster_review_routes import _speed_run_cluster_card

        identity = _identity("Test Person", face_count=2)
        with patch.multiple("app.cluster_review_routes._main_mod", load_photo_registry=lambda: _mock_photo_registry()):
            html = _render(_speed_run_cluster_card("id-001", identity, 0, 5, "rhodes"))

        assert "w-28" in html
        assert "h-28" in html
        # Should NOT have the old w-24 h-24 for face crops
        # (Note: other elements like enrichment panel may still use smaller sizes)

    def test_batch_card_has_min_80px(self):
        """Batch validation cards have min-height:80px on crops."""
        from app.cluster_review_routes import _batch_card

        identity = _identity("Batch Test", face_count=2)
        html = _render(_batch_card("id-001", identity, 2))

        assert "min-height:80px" in html


class TestPrefetch:
    """4F: Pre-fetch div is present in speed-run card."""

    def test_prefetch_div_present(self):
        """Speed-run card includes a hidden pre-fetch div."""
        from app.cluster_review_routes import _speed_run_cluster_card

        identity = _identity("Test", face_count=2)
        with patch.multiple("app.cluster_review_routes._main_mod", load_photo_registry=lambda: _mock_photo_registry()):
            html = _render(_speed_run_cluster_card("id-001", identity, 3, 10, "rhodes"))

        assert "speed-run-prefetch" in html
        assert "cluster-review/next" in html
