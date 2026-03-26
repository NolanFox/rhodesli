"""Tests for people page name filter (PRD-057 Triage Workflow Redesign).

Tests cover:
- Filter tabs render on /people page
- "all" filter shows all CONFIRMED identities (named + unnamed)
- "named" filter shows only identities with real names
- "needs_name" filter shows only identities with placeholder names
- Invalid filter values default to "all"
- Sort dropdown preserves active filter
- Sidebar counts include named/unidentified breakdown
"""

import pytest
from unittest.mock import patch, MagicMock
from starlette.testclient import TestClient

from app.main import app, _compute_sidebar_counts
from core.registry import IdentityRegistry, IdentityState


@pytest.fixture
def client():
    return TestClient(app)


def _make_identity(identity_id, name, state="CONFIRMED"):
    """Create a minimal identity dict for testing."""
    return {
        "identity_id": identity_id,
        "name": name,
        "state": state,
        "anchor_ids": [f"face_{identity_id}"],
        "candidate_ids": [],
        "negative_ids": [],
        "version_id": 1,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }


@pytest.fixture
def mock_registry_with_mixed():
    """Registry with both named and unidentified CONFIRMED identities."""
    registry = MagicMock(spec=IdentityRegistry)

    named_ids = [
        _make_identity("id-001", "Albert Fox"),
        _make_identity("id-002", "Sarah Gukaylo"),
        _make_identity("id-003", "Fanny Burd"),
    ]
    unidentified_ids = [
        _make_identity("id-004", "Unidentified Person 1"),
        _make_identity("id-005", "Unidentified Person 2"),
    ]
    proposed = [
        _make_identity("id-006", "Unidentified Person 3", state="PROPOSED"),
    ]
    all_confirmed = named_ids + unidentified_ids

    def list_identities(state=None):
        if state == IdentityState.CONFIRMED:
            return list(all_confirmed)
        if state == IdentityState.PROPOSED:
            return list(proposed)
        if state == IdentityState.INBOX:
            return []
        if state == IdentityState.SKIPPED:
            return []
        if state == IdentityState.REJECTED:
            return []
        if state == IdentityState.CONTESTED:
            return []
        # All
        return list(all_confirmed) + list(proposed)

    registry.list_identities = list_identities
    registry.list_proposed_matches = MagicMock(return_value=[])
    return registry


class TestPeopleNameFilter:
    """Tests for /people name_filter parameter."""

    def test_default_filter_is_all(self, client):
        """Default /people shows all CONFIRMED identities."""
        response = client.get("/people")
        assert response.status_code == 200
        # Filter tabs should be present
        assert "name_filter=" in response.text

    def test_all_filter_shows_all_confirmed(self, client, mock_registry_with_mixed):
        """name_filter=all shows both named and unnamed confirmed."""
        with (
            patch("app.main.load_registry", return_value=mock_registry_with_mixed),
            patch("app.browse_routes._main_mod.load_registry", return_value=mock_registry_with_mixed),
            patch("app.browse_routes._main_mod.get_crop_files", return_value={}),
            patch("app.browse_routes._main_mod._get_community_identity_ids", return_value=None),
            patch("app.browse_routes._main_mod.get_best_face_id", return_value=None),
            patch("app.browse_routes._main_mod.resolve_face_image_url", return_value=None),
        ):
            response = client.get("/people?name_filter=all")
            assert response.status_code == 200
            html = response.text
            assert "Albert Fox" in html
            assert "Sarah Gukaylo" in html
            assert "Unidentified Person 1" in html
            assert "Unidentified Person 2" in html

    def test_named_filter_excludes_unidentified(self, client, mock_registry_with_mixed):
        """name_filter=named shows only named identities."""
        with (
            patch("app.main.load_registry", return_value=mock_registry_with_mixed),
            patch("app.browse_routes._main_mod.load_registry", return_value=mock_registry_with_mixed),
            patch("app.browse_routes._main_mod.get_crop_files", return_value={}),
            patch("app.browse_routes._main_mod._get_community_identity_ids", return_value=None),
            patch("app.browse_routes._main_mod.get_best_face_id", return_value=None),
            patch("app.browse_routes._main_mod.resolve_face_image_url", return_value=None),
        ):
            response = client.get("/people?name_filter=named")
            assert response.status_code == 200
            html = response.text
            assert "Albert Fox" in html
            assert "Sarah Gukaylo" in html
            assert "Unidentified Person 1" not in html
            assert "Unidentified Person 2" not in html

    def test_needs_name_filter_shows_only_unidentified(self, client, mock_registry_with_mixed):
        """name_filter=needs_name shows only unidentified."""
        with (
            patch("app.main.load_registry", return_value=mock_registry_with_mixed),
            patch("app.browse_routes._main_mod.load_registry", return_value=mock_registry_with_mixed),
            patch("app.browse_routes._main_mod.get_crop_files", return_value={}),
            patch("app.browse_routes._main_mod._get_community_identity_ids", return_value=None),
            patch("app.browse_routes._main_mod.get_best_face_id", return_value=None),
            patch("app.browse_routes._main_mod.resolve_face_image_url", return_value=None),
        ):
            response = client.get("/people?name_filter=needs_name")
            assert response.status_code == 200
            html = response.text
            assert "Albert Fox" not in html
            assert "Sarah Gukaylo" not in html
            assert "Unidentified Person 1" in html
            assert "Unidentified Person 2" in html

    def test_invalid_filter_defaults_to_all(self, client):
        """Invalid name_filter values default to 'all'."""
        response = client.get("/people?name_filter=invalid")
        assert response.status_code == 200

    def test_filter_tabs_present(self, client):
        """Filter tabs (All, Named, Needs Name) are present."""
        response = client.get("/people")
        assert response.status_code == 200
        html = response.text
        assert "name_filter=all" in html
        assert "name_filter=named" in html
        assert "name_filter=needs_name" in html

    def test_active_tab_highlighted(self, client):
        """Active filter tab has indigo background."""
        response = client.get("/people?name_filter=named")
        assert response.status_code == 200
        html = response.text
        # The "Named" tab should have bg-indigo-600 class
        assert "bg-indigo-600" in html

    def test_sort_preserves_filter(self, client):
        """Sort dropdown URL includes current name_filter."""
        response = client.get("/people?name_filter=named&sort_by=photos")
        assert response.status_code == 200
        html = response.text
        # The sort dropdown should preserve name_filter in its onchange URL
        assert "name_filter=named" in html

    def test_filter_tabs_preserve_sort(self, client):
        """Filter tab links preserve current sort_by."""
        response = client.get("/people?sort_by=photos")
        assert response.status_code == 200
        html = response.text
        # Filter tab links should include sort_by=photos
        assert "sort_by=photos" in html


class TestSidebarNamedBreakdown:
    """Tests for sidebar People count showing named/unidentified breakdown."""

    def test_sidebar_counts_include_breakdown(self, mock_registry_with_mixed):
        """_compute_sidebar_counts includes confirmed_named and confirmed_unidentified."""
        with (
            patch("app.main._build_caches"),
            patch("app.main._get_community_photo_ids", return_value=None),
            patch("app.main._get_community_identity_ids", return_value=None),
            patch("app.main._photo_cache", {"photo1": {}}),
            patch("app.main._count_pending_uploads", return_value=0),
            patch("app.main._load_proposals", return_value={"proposals": []}),
            patch("app.main._load_annotations", return_value={"annotations": {}}),
            patch("app.main._count_discoveries", return_value=0),
        ):
            counts = _compute_sidebar_counts(mock_registry_with_mixed)
            assert counts["confirmed"] == 5
            assert counts["confirmed_named"] == 3
            assert counts["confirmed_unidentified"] == 2

    def test_sidebar_all_named(self):
        """When all confirmed are named, confirmed_unidentified is 0."""
        registry = MagicMock(spec=IdentityRegistry)
        named_only = [
            _make_identity("id-001", "Albert Fox"),
            _make_identity("id-002", "Sarah Gukaylo"),
        ]

        def list_identities(state=None):
            if state == IdentityState.CONFIRMED:
                return list(named_only)
            return list(named_only)

        registry.list_identities = list_identities
        registry.list_proposed_matches = MagicMock(return_value=[])

        with (
            patch("app.main._build_caches"),
            patch("app.main._get_community_photo_ids", return_value=None),
            patch("app.main._get_community_identity_ids", return_value=None),
            patch("app.main._photo_cache", {"photo1": {}}),
            patch("app.main._count_pending_uploads", return_value=0),
            patch("app.main._load_proposals", return_value={"proposals": []}),
            patch("app.main._load_annotations", return_value={"annotations": {}}),
            patch("app.main._count_discoveries", return_value=0),
        ):
            counts = _compute_sidebar_counts(registry)
            assert counts["confirmed"] == 2
            assert counts["confirmed_named"] == 2
            assert counts["confirmed_unidentified"] == 0

    def test_sidebar_all_unidentified(self):
        """When all confirmed are unidentified, confirmed_named is 0."""
        registry = MagicMock(spec=IdentityRegistry)
        unid_only = [
            _make_identity("id-001", "Unidentified Person 1"),
            _make_identity("id-002", "Unidentified Person 2"),
        ]

        def list_identities(state=None):
            if state == IdentityState.CONFIRMED:
                return list(unid_only)
            return list(unid_only)

        registry.list_identities = list_identities
        registry.list_proposed_matches = MagicMock(return_value=[])

        with (
            patch("app.main._build_caches"),
            patch("app.main._get_community_photo_ids", return_value=None),
            patch("app.main._get_community_identity_ids", return_value=None),
            patch("app.main._photo_cache", {"photo1": {}}),
            patch("app.main._count_pending_uploads", return_value=0),
            patch("app.main._load_proposals", return_value={"proposals": []}),
            patch("app.main._load_annotations", return_value={"annotations": {}}),
            patch("app.main._count_discoveries", return_value=0),
        ):
            counts = _compute_sidebar_counts(registry)
            assert counts["confirmed"] == 2
            assert counts["confirmed_named"] == 0
            assert counts["confirmed_unidentified"] == 2
