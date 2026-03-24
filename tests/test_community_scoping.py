"""Tests for community data scoping (Session 95b).

Covers:
- community_url_prefix utility
- _get_community_photo_ids / _get_community_identity_ids caching
- _compute_sidebar_counts with community filtering
"""

import os
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

    def test_default_community_falls_back_to_none_without_supabase(self):
        """When Supabase is unavailable, Rhodes/default falls back to None (no filtering)."""
        from app.main import _get_community_photo_ids

        # Without Supabase, all communities fall back to None
        assert _get_community_photo_ids({"is_default": True, "slug": "rhodes"}) is None

    def test_rhodes_slug_falls_back_to_none_without_supabase(self):
        from app.main import _get_community_photo_ids

        assert _get_community_photo_ids({"slug": "rhodes"}) is None

    def test_community_without_id_returns_none(self):
        """Community dict without an ID can't be scoped — falls back to None."""
        from app.main import _get_community_photo_ids

        result = _get_community_photo_ids({"slug": "fox-family"})
        assert result is None

    @patch("app.supabase_data.get_supabase_client")
    @patch("app.supabase_data.load_photos_for_community")
    def test_returns_photo_id_set(self, mock_load, mock_client):
        import app.main

        # Clear cache
        app.main._community_photo_ids_cache = {}
        app.main._community_ids_cache_ts = 0.0

        mock_client.return_value = True  # Supabase available
        mock_load.return_value = ["photo1", "photo2", "photo3"]
        community = {"slug": "fox-family", "id": "test-uuid-123"}
        result = app.main._get_community_photo_ids(community)
        assert result == {"photo1", "photo2", "photo3"}
        mock_load.assert_called_once_with("test-uuid-123")

    @patch("app.supabase_data.get_supabase_client")
    @patch("app.supabase_data.load_photos_for_community")
    def test_empty_community_returns_empty_set(self, mock_load, mock_client):
        import app.main

        app.main._community_photo_ids_cache = {}
        app.main._community_ids_cache_ts = 0.0

        mock_client.return_value = True
        mock_load.return_value = []
        community = {"slug": "fox-family", "id": "test-uuid-456"}
        result = app.main._get_community_photo_ids(community)
        assert result == set()

    @patch("app.supabase_data.get_supabase_client")
    @patch("app.supabase_data.load_photos_for_community")
    def test_supabase_failure_returns_none(self, mock_load, mock_client):
        import app.main

        app.main._community_photo_ids_cache = {}
        app.main._community_ids_cache_ts = 0.0

        mock_client.return_value = True
        mock_load.return_value = None
        community = {"slug": "fox-family", "id": "test-uuid-789"}
        result = app.main._get_community_photo_ids(community)
        assert result is None

    @patch("app.supabase_data.get_supabase_client")
    @patch("app.supabase_data.load_photos_for_community")
    def test_supabase_failure_is_not_cached(self, mock_load, mock_client):
        """Transient Supabase failures should NOT be cached — they would disable
        community filtering for the full TTL, causing cross-community data leakage."""
        import app.main

        app.main._community_photo_ids_cache = {}
        app.main._community_ids_cache_ts = 0.0

        mock_client.return_value = True
        mock_load.return_value = None
        community = {"slug": "fox-family", "id": "test-uuid-cache"}

        assert app.main._get_community_photo_ids(community) is None
        assert app.main._get_community_photo_ids(community) is None
        # Called TWICE because failures are not cached — each call retries Supabase
        assert mock_load.call_count == 2


# ============================================================================
# _get_community_identity_ids
# ============================================================================


class TestGetCommunityIdentityIds:
    """Tests for _get_community_identity_ids."""

    def test_none_community_returns_none(self):
        from app.main import _get_community_identity_ids

        assert _get_community_identity_ids(None) is None

    def test_default_community_falls_back_to_none_without_supabase(self):
        """When Supabase is unavailable, default community falls back to None (no filtering)."""
        from app.main import _get_community_identity_ids

        # Without Supabase, photo-derived set can't be computed, falls back to None
        assert _get_community_identity_ids({"is_default": True}) is None

    def test_returns_identity_id_set_from_photos(self):
        """Photo-derived identity set: finds identities with faces in community photos (AD-216)."""
        import app.main

        app.main._community_identity_ids_cache = {}
        app.main._community_ids_cache_ts = 0.0

        # Mock: community has photos p1 and p2
        with patch.object(app.main, "_get_community_photo_ids", return_value={"p1", "p2"}):
            # Mock: face_to_photo_cache maps faces to photos
            app.main._face_to_photo_cache = {"f1": "p1", "f2": "p2", "f3": "p3"}
            app.main._photo_id_aliases = {}
            app.main._photo_cache = {"p1": {}, "p2": {}, "p3": {}}

            # Mock: registry maps faces to identities
            mock_registry = MagicMock()
            identity1 = {"identity_id": "id1", "name": "A", "anchor_ids": ["f1"], "candidate_ids": []}
            identity2 = {"identity_id": "id2", "name": "B", "anchor_ids": [], "candidate_ids": ["f2"]}
            mock_registry.list_identities.return_value = [identity1, identity2]

            with patch.object(app.main, "load_registry", return_value=mock_registry):
                with patch.object(app.main, "_build_caches"):
                    with patch.object(
                        app.main,
                        "get_identity_for_face",
                        side_effect=lambda reg, fid: {"f1": identity1, "f2": identity2}.get(fid),
                    ):
                        community = {"slug": "fox-family", "id": "test-uuid-abc"}
                        result = app.main._get_community_identity_ids(community)
                        assert result == {"id1", "id2"}

    def test_photo_scope_failure_fails_closed_for_non_rhodes(self):
        """When photo scope unavailable, non-Rhodes communities fail closed (empty set)."""
        import app.main

        app.main._community_identity_ids_cache = {}
        app.main._community_ids_cache_ts = 0.0

        with patch.object(app.main, "_get_community_photo_ids", return_value=None):
            community = {"slug": "fox-family", "id": "test-uuid-def"}
            result = app.main._get_community_identity_ids(community)
            assert result == set()  # Empty set = show nothing, not None = show everything

    def test_photo_scope_failure_fails_closed_for_rhodes(self):
        """When photo scope unavailable, Rhodes also fails closed (empty set).

        Previously Rhodes failed open (returned None = show everything), which
        caused cross-community data leakage when Supabase was unavailable.
        Fixed: ALL communities fail closed when Supabase errors occur.
        """
        import app.main

        app.main._community_identity_ids_cache = {}
        app.main._community_ids_cache_ts = 0.0

        with patch.object(app.main, "_get_community_photo_ids", return_value=None):
            community = {"slug": "rhodes", "id": "rhodes-uuid"}
            result = app.main._get_community_identity_ids(community)
            assert result == set()  # Empty set = fail closed, not None = show everything

    def test_supabase_error_fails_closed_not_open(self):
        """When Supabase returns an error (e.g. 402 egress exceeded), ALL communities
        fail closed — no identities shown rather than leaking all identities.

        Regression test for: Supabase egress quota exceeded caused Rhodes page
        to show ALL 1853 identities including Fox Family data.
        """
        import app.main

        app.main._community_identity_ids_cache = {}
        app.main._community_ids_cache_ts = 0.0

        # Simulate Supabase error by having _get_community_photo_ids return None
        with patch.object(app.main, "_get_community_photo_ids", return_value=None):
            # Rhodes community
            rhodes = {"slug": "rhodes", "id": "rhodes-uuid"}
            result_rhodes = app.main._get_community_identity_ids(rhodes)
            assert result_rhodes == set(), "Rhodes must fail closed on Supabase error"

            # Fox Family community
            app.main._community_identity_ids_cache = {}
            fox = {"slug": "fox-family", "id": "fox-uuid"}
            result_fox = app.main._get_community_identity_ids(fox)
            assert result_fox == set(), "Fox Family must fail closed on Supabase error"

        # But when community is None (no community middleware), return None (no filtering)
        result_none = app.main._get_community_identity_ids(None)
        assert result_none is None, "No community context should return None (no filtering)"


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

    @patch("app.main._count_discoveries", return_value=2)
    @patch("app.main._load_annotations", return_value={"annotations": {"ann-1": {"status": "pending"}}})
    @patch("app.main._get_community_identity_ids", return_value={"a1", "a4"})
    @patch("app.main._get_community_photo_ids", return_value={"p1"})
    @patch("app.main._count_pending_uploads", return_value=0)
    @patch("app.main._build_caches")
    def test_community_filters_counts(self, mock_build, mock_pending, mock_photo_ids, mock_id_ids, mock_ann, mock_disc):
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
        # ML features now computed for all communities (AD-216)
        assert counts["proposals"] == 0  # registry mock returns []
        assert counts["discoveries"] == 2
        assert counts["pending_annotations"] == 1

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

    @patch("app.main._count_discoveries", return_value=0)
    @patch("app.main._load_annotations", return_value={"annotations": []})
    @patch("app.main._get_community_identity_ids", return_value={"fox1", "fox2"})
    @patch("app.main._get_community_photo_ids", return_value={"p1"})
    @patch("app.main._count_pending_uploads", return_value=0)
    @patch("app.main._build_caches")
    def test_proposals_json_counted_for_community(
        self, mock_build, mock_pending, mock_photo_ids, mock_id_ids, mock_ann, mock_disc, tmp_path
    ):
        """COMMUNITY-010: ML proposals should be counted in sidebar (via unified reader)."""
        import app.main

        app.main._photo_cache = {"p1": {}}
        registry = self._make_registry_mock()

        # Mock _load_proposals (unified reader — Supabase or JSON, PRD-051 Session 114)
        mock_proposals = {
            "proposals": [
                {"source_identity_id": "fox1", "target_identity_id": "roland", "distance": 0.8},
                {"source_identity_id": "fox2", "target_identity_id": "roland", "distance": 0.9},
                {"source_identity_id": "other1", "target_identity_id": "other2", "distance": 0.7},
            ],
            "generated_at": "2026-03-17",
        }

        community = {"slug": "fox-family", "id": "test-uuid"}
        with patch.object(app.main, "_load_proposals", return_value=mock_proposals):
            counts = app.main._compute_sidebar_counts(registry, community=community)
        # Only 2 proposals match community identity set (fox1, fox2)
        assert counts["proposals"] == 2


# ============================================================================
# Photo-derived identity set tests (AD-216)
# ============================================================================


class TestPhotoDerivedIdentitySet:
    """Tests for photo-derived community identity set computation."""

    def test_includes_identities_from_candidate_ids(self):
        """Identities with candidate_ids (not just anchor_ids) should be included."""
        import app.main

        app.main._community_identity_ids_cache = {}
        app.main._community_ids_cache_ts = 0.0
        app.main._face_to_photo_cache = {"f1": "p1"}
        app.main._photo_id_aliases = {}
        app.main._photo_cache = {"p1": {}}

        identity_with_candidate = {"identity_id": "id1", "anchor_ids": [], "candidate_ids": ["f1"]}

        with patch.object(app.main, "_get_community_photo_ids", return_value={"p1"}):
            with patch.object(app.main, "load_registry", return_value=MagicMock()):
                with patch.object(app.main, "_build_caches"):
                    with patch.object(
                        app.main,
                        "get_identity_for_face",
                        side_effect=lambda reg, fid: identity_with_candidate if fid == "f1" else None,
                    ):
                        result = app.main._get_community_identity_ids({"slug": "fox-family", "id": "fox-id"})
                        assert "id1" in result

    def test_returns_empty_for_community_with_no_photos(self):
        """Community with 0 photos should return empty set."""
        import app.main

        app.main._community_identity_ids_cache = {}
        app.main._community_ids_cache_ts = 0.0

        with patch.object(app.main, "_get_community_photo_ids", return_value=set()):
            result = app.main._get_community_identity_ids({"slug": "empty-community", "id": "empty-id"})
            assert result == set()

    def test_returns_none_for_rhodes(self):
        """Rhodes/default community should return None (no filter)."""
        import app.main

        assert app.main._get_community_identity_ids(None) is None
        assert app.main._get_community_identity_ids({"slug": "rhodes"}) is None
        assert app.main._get_community_identity_ids({"is_default": True}) is None


# ============================================================================
# Cross-community search verification (Act 5)
# ============================================================================


class TestCrossCommunitySearch:
    """Verify search is global (not community-scoped) for cross-community merges."""

    def test_search_api_searches_all_identities(self):
        """Search must find identities from ALL communities, not just current."""
        import app.identity_routes
        import inspect

        # Verify search handler uses registry.search_identities() without community filter
        source = inspect.getsource(app.identity_routes)
        # The search should call registry.search_identities(q) without filtering by community
        assert "search_identities" in source
        # No community filtering in the search handler
        assert (
            "community_identity_ids" not in source.split("def get(q:")[1].split("def ")[0]
            if "def get(q:" in source
            else True
        )
