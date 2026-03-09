"""Tests for community data scoping (Session 95b).

Covers:
- community_url_prefix utility
- _get_community_photo_ids / _get_community_identity_ids caching
- _compute_sidebar_counts with community filtering
"""

from unittest.mock import MagicMock, patch

import pytest


# ============================================================================
# community_url_prefix
# ============================================================================


class TestCommunityUrlPrefix:
    """Tests for community_url_prefix utility."""

    def test_rhodes_returns_empty(self):
        from app.main import community_url_prefix

        assert community_url_prefix("rhodes") == ""

    def test_none_returns_empty(self):
        from app.main import community_url_prefix

        assert community_url_prefix(None) == ""

    def test_empty_string_returns_empty(self):
        from app.main import community_url_prefix

        assert community_url_prefix("") == ""

    def test_fox_family_returns_prefix(self):
        from app.main import community_url_prefix

        assert community_url_prefix("fox-family") == "/c/fox-family"

    def test_other_community_returns_prefix(self):
        from app.main import community_url_prefix

        assert community_url_prefix("smith-archive") == "/c/smith-archive"


# ============================================================================
# _get_community_photo_ids
# ============================================================================


class TestGetCommunityPhotoIds:
    """Tests for _get_community_photo_ids."""

    def test_none_community_returns_none(self):
        from app.main import _get_community_photo_ids

        assert _get_community_photo_ids(None) is None

    def test_default_community_returns_none(self):
        from app.main import _get_community_photo_ids

        assert _get_community_photo_ids({"is_default": True, "slug": "rhodes"}) is None

    def test_rhodes_slug_returns_none(self):
        from app.main import _get_community_photo_ids

        assert _get_community_photo_ids({"slug": "rhodes"}) is None

    def test_community_without_id_returns_empty_set(self):
        from app.main import _get_community_photo_ids

        result = _get_community_photo_ids({"slug": "fox-family"})
        assert result == set()

    @patch("app.supabase_data.load_photos_for_community")
    def test_returns_photo_id_set(self, mock_load):
        import app.main

        # Clear cache
        app.main._community_photo_ids_cache = {}
        app.main._community_ids_cache_ts = 0.0

        mock_load.return_value = ["photo1", "photo2", "photo3"]
        community = {"slug": "fox-family", "id": "test-uuid-123"}
        result = app.main._get_community_photo_ids(community)
        assert result == {"photo1", "photo2", "photo3"}
        mock_load.assert_called_once_with("test-uuid-123")

    @patch("app.supabase_data.load_photos_for_community")
    def test_empty_community_returns_empty_set(self, mock_load):
        import app.main

        app.main._community_photo_ids_cache = {}
        app.main._community_ids_cache_ts = 0.0

        mock_load.return_value = []
        community = {"slug": "fox-family", "id": "test-uuid-456"}
        result = app.main._get_community_photo_ids(community)
        assert result == set()

    @patch("app.supabase_data.load_photos_for_community")
    def test_supabase_failure_returns_empty_set(self, mock_load):
        import app.main

        app.main._community_photo_ids_cache = {}
        app.main._community_ids_cache_ts = 0.0

        mock_load.return_value = None
        community = {"slug": "fox-family", "id": "test-uuid-789"}
        result = app.main._get_community_photo_ids(community)
        assert result == set()


# ============================================================================
# _get_community_identity_ids
# ============================================================================


class TestGetCommunityIdentityIds:
    """Tests for _get_community_identity_ids."""

    def test_none_community_returns_none(self):
        from app.main import _get_community_identity_ids

        assert _get_community_identity_ids(None) is None

    def test_default_community_returns_none(self):
        from app.main import _get_community_identity_ids

        assert _get_community_identity_ids({"is_default": True}) is None

    @patch("app.supabase_data.load_identities_for_community")
    def test_returns_identity_id_set(self, mock_load):
        import app.main

        app.main._community_identity_ids_cache = {}
        app.main._community_ids_cache_ts = 0.0

        mock_load.return_value = [
            {"identity_id": "id1", "is_primary": True},
            {"identity_id": "id2", "is_primary": False},
        ]
        community = {"slug": "fox-family", "id": "test-uuid-abc"}
        result = app.main._get_community_identity_ids(community)
        assert result == {"id1", "id2"}


# ============================================================================
# _compute_sidebar_counts with community filtering
# ============================================================================


class TestComputeSidebarCountsCommunity:
    """Tests for _compute_sidebar_counts with community parameter."""

    def _make_registry_mock(self):
        registry = MagicMock()
        from core.registry import IdentityState

        registry.list_identities.side_effect = lambda state: {
            IdentityState.INBOX: [
                {"identity_id": "a1", "name": "A"},
                {"identity_id": "a2", "name": "B"},
            ],
            IdentityState.PROPOSED: [{"identity_id": "a3", "name": "C"}],
            IdentityState.CONFIRMED: [
                {"identity_id": "a4", "name": "D"},
                {"identity_id": "a5", "name": "E"},
            ],
            IdentityState.SKIPPED: [{"identity_id": "a6", "name": "F"}],
            IdentityState.REJECTED: [],
            IdentityState.CONTESTED: [],
        }.get(state, [])
        registry.list_proposed_matches.return_value = []
        return registry

    @patch("app.main._count_discoveries", return_value=0)
    @patch("app.main._load_annotations", return_value={"annotations": []})
    @patch("app.main._count_pending_uploads", return_value=0)
    @patch("app.main._build_caches")
    def test_none_community_returns_all_counts(self, mock_build, mock_pending, mock_ann, mock_disc):
        import app.main

        app.main._photo_cache = {"p1": {}, "p2": {}, "p3": {}}
        registry = self._make_registry_mock()
        counts = app.main._compute_sidebar_counts(registry, community=None)
        assert counts["to_review"] == 3
        assert counts["confirmed"] == 2
        assert counts["skipped"] == 1
        assert counts["photos"] == 3

    @patch("app.main._get_community_identity_ids", return_value={"a1", "a4"})
    @patch("app.main._get_community_photo_ids", return_value={"p1"})
    @patch("app.main._count_pending_uploads", return_value=0)
    @patch("app.main._build_caches")
    def test_community_filters_counts(self, mock_build, mock_pending, mock_photo_ids, mock_id_ids):
        import app.main

        app.main._photo_cache = {"p1": {}, "p2": {}, "p3": {}}
        registry = self._make_registry_mock()
        community = {"slug": "fox-family", "id": "test-uuid"}
        counts = app.main._compute_sidebar_counts(registry, community=community)
        # Only a1 is in inbox, a4 is confirmed — filtered to community set
        assert counts["to_review"] == 1  # a1 only
        assert counts["confirmed"] == 1  # a4 only
        assert counts["skipped"] == 0  # a6 not in set
        assert counts["photos"] == 1  # filtered photo set
        # ML features disabled for non-default
        assert counts["proposals"] == 0
        assert counts["discoveries"] == 0
        assert counts["pending_annotations"] == 0

    @patch("app.main._count_discoveries", return_value=5)
    @patch("app.main._load_annotations", return_value={"annotations": []})
    @patch("app.main._count_pending_uploads", return_value=0)
    @patch("app.main._build_caches")
    def test_backward_compat_no_community_arg(self, mock_build, mock_pending, mock_ann, mock_disc):
        """Existing callers that don't pass community= still work."""
        import app.main

        app.main._photo_cache = {"p1": {}}
        registry = self._make_registry_mock()
        counts = app.main._compute_sidebar_counts(registry)
        assert counts["photos"] == 1
        assert counts["discoveries"] == 5
