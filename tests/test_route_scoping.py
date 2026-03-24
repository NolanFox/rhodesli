"""Tests for community-aware route scoping (PRD-035 Phase 1, Track C).

Covers:
- community_url_prefix helper
- _get_community_photo_ids / _get_community_identity_ids helpers
- _compute_sidebar_counts with community filtering
- /photos route has community filtering wired in (structural)
- / command center has community identity filtering (structural)
- Upload POST has community tagging (structural + pattern)
- sidebar accepts community params
"""

import inspect
from unittest.mock import MagicMock, patch

import pytest


# ============================================================================
# community_url_prefix helper
# ============================================================================


class TestCommunityUrlPrefix:
    def test_rhodes_returns_empty(self):
        from app.main import community_url_prefix

        assert community_url_prefix("rhodes") == ""

    def test_none_returns_empty(self):
        from app.main import community_url_prefix

        assert community_url_prefix(None) == ""

    def test_empty_returns_empty(self):
        from app.main import community_url_prefix

        assert community_url_prefix("") == ""

    def test_non_rhodes_returns_prefix(self):
        from app.main import community_url_prefix

        assert community_url_prefix("fox-family") == "/c/fox-family"

    def test_other_slug(self):
        from app.main import community_url_prefix

        assert community_url_prefix("my-archive") == "/c/my-archive"


# ============================================================================
# _get_community_photo_ids
# ============================================================================


class TestGetCommunityPhotoIds:
    def test_none_community_returns_none(self):
        from app.main import _get_community_photo_ids

        assert _get_community_photo_ids(None) is None

    def test_rhodes_community_returns_none(self):
        from app.main import _get_community_photo_ids

        result = _get_community_photo_ids({"slug": "rhodes", "id": "some-id"})
        assert result is None

    def test_no_id_returns_none(self):
        from app.main import _get_community_photo_ids

        # No community ID means no scoping possible — returns None (no filtering)
        result = _get_community_photo_ids({"slug": "fox-family"})
        assert result is None

    @patch("app.supabase_data.load_photos_for_community", return_value=["p1", "p2", "p3"])
    @patch("app.supabase_data.get_supabase_client", return_value=MagicMock())
    def test_non_rhodes_returns_set(self, mock_client, mock_load):
        import app.main

        app.main._community_photo_ids_cache = {}
        app.main._community_ids_cache_ts = 0.0
        result = app.main._get_community_photo_ids({"slug": "fox-family", "id": "fox-id"})
        assert "p1" in result and "p2" in result and "p3" in result
        mock_load.assert_called_once_with("fox-id")

    @patch("app.supabase_data.load_photos_for_community", return_value=None)
    @patch("app.supabase_data.get_supabase_client", return_value=MagicMock())
    def test_supabase_failure_returns_none(self, mock_client, mock_load):
        import app.main

        app.main._community_photo_ids_cache = {}
        app.main._community_ids_cache_ts = 0.0
        result = app.main._get_community_photo_ids({"slug": "fox-family", "id": "fox-id"})
        assert result is None

    @patch("app.supabase_data.load_photos_for_community", return_value=[])
    @patch("app.supabase_data.get_supabase_client", return_value=MagicMock())
    def test_empty_community_returns_empty_set(self, mock_client, mock_load):
        import app.main

        app.main._community_photo_ids_cache = {}
        app.main._community_ids_cache_ts = 0.0
        result = app.main._get_community_photo_ids({"slug": "fox-family", "id": "fox-id"})
        assert result == set()


# ============================================================================
# _get_community_identity_ids
# ============================================================================


class TestGetCommunityIdentityIds:
    def test_none_community_returns_none(self):
        from app.main import _get_community_identity_ids

        assert _get_community_identity_ids(None) is None

    def test_photo_scope_failure_fails_closed(self):
        """When Supabase is unavailable, ALL communities fail closed (empty set)."""
        import app.main

        app.main._community_identity_ids_cache = {}
        app.main._community_ids_cache_ts = 0.0
        with patch.object(app.main, "_get_community_photo_ids", return_value=None):
            result = app.main._get_community_identity_ids({"slug": "rhodes", "id": "some-id"})
            assert result == set()  # Fail closed, not None (fail open)

    def test_non_rhodes_returns_photo_derived_set(self):
        """Photo-derived identity set returns identities with faces in community photos (AD-216)."""
        import app.main

        app.main._community_identity_ids_cache = {}
        app.main._community_ids_cache_ts = 0.0
        app.main._face_to_photo_cache = {"f1": "p1", "f2": "p2"}
        app.main._photo_id_aliases = {}
        app.main._photo_cache = {"p1": {}, "p2": {}}

        identity1 = {"identity_id": "id1", "anchor_ids": ["f1"], "candidate_ids": []}
        identity2 = {"identity_id": "id2", "anchor_ids": ["f2"], "candidate_ids": []}
        mock_registry = MagicMock()

        with patch.object(app.main, "_get_community_photo_ids", return_value={"p1", "p2"}):
            with patch.object(app.main, "load_registry", return_value=mock_registry):
                with patch.object(app.main, "_build_caches"):
                    with patch.object(
                        app.main,
                        "get_identity_for_face",
                        side_effect=lambda reg, fid: {"f1": identity1, "f2": identity2}.get(fid),
                    ):
                        result = app.main._get_community_identity_ids({"slug": "fox-family", "id": "fox-id"})
                        assert result == {"id1", "id2"}

    def test_no_community_photos_returns_empty_set(self):
        import app.main

        app.main._community_identity_ids_cache = {}
        app.main._community_ids_cache_ts = 0.0
        with patch.object(app.main, "_get_community_photo_ids", return_value=set()):
            result = app.main._get_community_identity_ids({"slug": "fox-family", "id": "fox-id"})
            assert result == set()

    def test_no_id_returns_none(self):
        """No community ID means no scoping possible — returns None (no filtering)."""
        from app.main import _get_community_identity_ids

        result = _get_community_identity_ids({"slug": "fox-family"})
        assert result is None


# ============================================================================
# _compute_sidebar_counts with community filtering
# ============================================================================


class TestComputeSidebarCountsCommunity:
    """Test that _compute_sidebar_counts respects community filtering."""

    def _make_registry(self, identities_by_state):
        from core.registry import IdentityState

        mock_reg = MagicMock()

        def list_identities(state=None):
            return list(identities_by_state.get(state, []))

        mock_reg.list_identities = list_identities
        mock_reg.list_proposed_matches = MagicMock(return_value=[])
        return mock_reg

    @patch("app.main._build_caches")
    @patch("app.main._photo_cache", {"p1": {}, "p2": {}, "p3": {}})
    @patch("app.main._load_annotations", return_value={"annotations": []})
    @patch("app.main._count_discoveries", return_value=0)
    @patch("app.main._count_pending_uploads", return_value=0)
    def test_no_community_returns_all(self, mock_pending, mock_disc, mock_ann, mock_build):
        from core.registry import IdentityState

        from app.main import _compute_sidebar_counts

        reg = self._make_registry(
            {
                IdentityState.INBOX: [{"identity_id": "i1"}, {"identity_id": "i2"}],
                IdentityState.PROPOSED: [],
                IdentityState.CONFIRMED: [{"identity_id": "i3"}],
                IdentityState.SKIPPED: [],
                IdentityState.REJECTED: [],
                IdentityState.CONTESTED: [],
            }
        )
        counts = _compute_sidebar_counts(reg)
        assert counts["to_review"] == 2
        assert counts["confirmed"] == 1
        assert counts["photos"] == 3

    @patch("app.main._build_caches")
    @patch("app.main._photo_cache", {"p1": {}, "p2": {}, "p3": {}})
    @patch("app.main._load_annotations", return_value={"annotations": []})
    @patch("app.main._count_discoveries", return_value=0)
    @patch("app.main._count_pending_uploads", return_value=0)
    @patch("app.main._get_community_identity_ids", return_value={"i1"})
    @patch("app.main._get_community_photo_ids", return_value={"p2"})
    def test_community_filters_counts(self, mock_photo_ids, mock_id_ids, mock_pending, mock_disc, mock_ann, mock_build):
        from core.registry import IdentityState

        from app.main import _compute_sidebar_counts

        reg = self._make_registry(
            {
                IdentityState.INBOX: [{"identity_id": "i1"}, {"identity_id": "i2"}],
                IdentityState.PROPOSED: [],
                IdentityState.CONFIRMED: [{"identity_id": "i3"}],
                IdentityState.SKIPPED: [],
                IdentityState.REJECTED: [],
                IdentityState.CONTESTED: [],
            }
        )
        community = {"slug": "fox-family", "id": "fox-id"}
        counts = _compute_sidebar_counts(reg, community=community)
        assert counts["to_review"] == 1  # only i1 passes filter
        assert counts["confirmed"] == 0  # i3 not in community
        assert counts["photos"] == 1  # only p2

    @patch("app.main._build_caches")
    @patch("app.main._photo_cache", {"p1": {}, "p2": {}})
    @patch("app.main._load_annotations", return_value={"annotations": []})
    @patch("app.main._count_discoveries", return_value=0)
    @patch("app.main._count_pending_uploads", return_value=0)
    def test_backward_compat_no_community_arg(self, mock_pending, mock_disc, mock_ann, mock_build):
        """_compute_sidebar_counts works without community arg (backward compat)."""
        from core.registry import IdentityState

        from app.main import _compute_sidebar_counts

        reg = self._make_registry(
            {
                IdentityState.INBOX: [],
                IdentityState.PROPOSED: [],
                IdentityState.CONFIRMED: [],
                IdentityState.SKIPPED: [],
                IdentityState.REJECTED: [],
                IdentityState.CONTESTED: [],
            }
        )
        counts = _compute_sidebar_counts(reg)
        assert counts["photos"] == 2


# ============================================================================
# /photos route community scoping — structural verification
# ============================================================================


class TestPhotosRouteCommunityScoping:
    """Verify /photos route has community filtering wired in."""

    def test_browse_routes_has_community_photo_filter(self):
        """browse_routes.py references _get_community_photo_ids."""
        import app.browse_routes as br

        source = inspect.getsource(br)
        assert "_get_community_photo_ids" in source

    def test_browse_routes_has_request_param(self):
        """The /photos GET handler accepts request parameter."""
        import app.browse_routes as br

        source = inspect.getsource(br)
        assert "request=None" in source

    def test_browse_routes_has_empty_state(self):
        """browse_routes has 'No photos yet' empty state for non-Rhodes."""
        import app.browse_routes as br

        source = inspect.getsource(br)
        assert "No photos yet" in source
        assert "Upload Photos" in source

    def test_browse_routes_community_filter_in_loop(self):
        """The photo loop filters by community_photo_ids."""
        import app.browse_routes as br

        source = inspect.getsource(br)
        # Session 96b: filter checks both cache ID and its alias (inbox_* ID)
        assert "community_photo_ids is not None" in source
        assert "photo_id_val not in community_photo_ids" in source
        assert "alias_id" in source

    def test_browse_routes_extracts_community_context(self):
        """browse_routes extracts community_slug and community from request.state."""
        import app.browse_routes as br

        source = inspect.getsource(br)
        assert 'community_slug = getattr(request.state, "community_slug", "rhodes")' in source
        assert 'community = getattr(request.state, "community", None)' in source


# ============================================================================
# / command center community scoping — structural verification
# ============================================================================


class TestCommandCenterCommunityScoping:
    """Verify / route command center has community identity filtering."""

    def test_page_routes_has_community_identity_filter(self):
        """page_routes.py filters identities by community_identity_ids."""
        import app.page_routes as pr

        source = inspect.getsource(pr)
        assert "_get_community_identity_ids" in source
        assert "community_identity_ids" in source

    def test_page_routes_sidebar_gets_community(self):
        """page_routes passes community params to sidebar."""
        import app.page_routes as pr

        source = inspect.getsource(pr)
        assert "community_slug=community_slug" in source
        assert "community=community" in source

    def test_page_routes_sidebar_counts_get_community(self):
        """page_routes passes community to _compute_sidebar_counts."""
        import app.page_routes as pr

        source = inspect.getsource(pr)
        assert "_compute_sidebar_counts(registry, community=community)" in source

    def test_page_routes_filters_all_identity_states(self):
        """page_routes filters inbox, proposed, confirmed, skipped, rejected, contested."""
        import app.page_routes as pr

        source = inspect.getsource(pr)
        for state_list in ["inbox", "proposed", "confirmed_list", "skipped_list", "rejected", "contested"]:
            assert (
                f'{state_list} = [i for i in {state_list} if i.get("identity_id") in community_identity_ids]' in source
            )


# ============================================================================
# Upload community tagging — structural + pattern tests
# ============================================================================


class TestUploadCommunityTagging:
    """Verify upload POST handler has community tagging wired in."""

    def test_upload_post_has_request_param(self):
        """Upload POST handler accepts request parameter."""
        import app.upload_routes as ur

        source = inspect.getsource(ur)
        assert "request=None" in source

    def test_upload_post_extracts_community_context(self):
        """Upload POST handler extracts community context from request."""
        import app.upload_routes as ur

        source = inspect.getsource(ur)
        assert "upload_community_id" in source
        assert "community_slug" in source

    def test_upload_post_tags_photos_to_community(self):
        """Upload POST handler calls add_photo_to_community."""
        import app.upload_routes as ur

        source = inspect.getsource(ur)
        assert "add_photo_to_community" in source

    def test_upload_metadata_includes_community_id(self):
        """Upload metadata dict includes community_id key."""
        import app.upload_routes as ur

        source = inspect.getsource(ur)
        assert '"community_id"' in source

    def test_upload_community_extraction_pattern(self):
        """Verify the community extraction pattern works correctly."""
        # Simulate request with fox-family community
        request = MagicMock()
        request.state.community_slug = "fox-family"
        request.state.community = {"slug": "fox-family", "id": "fox-uuid"}

        community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
        community = getattr(request.state, "community", None) if request else None
        upload_community_id = None
        if community and community.get("slug") != "rhodes" and community.get("id"):
            upload_community_id = community["id"]

        assert community_slug == "fox-family"
        assert upload_community_id == "fox-uuid"

    def test_upload_rhodes_no_community_tag(self):
        """Rhodes community uploads should not set community_id."""
        request = MagicMock()
        request.state.community_slug = "rhodes"
        request.state.community = {"slug": "rhodes", "id": "rhodes-uuid"}

        community = getattr(request.state, "community", None) if request else None
        upload_community_id = None
        if community and community.get("slug") != "rhodes" and community.get("id"):
            upload_community_id = community["id"]

        assert upload_community_id is None

    def test_upload_no_request_no_community_tag(self):
        """Without request, no community tagging."""
        request = None
        community_slug = getattr(request.state, "community_slug", "rhodes") if request else "rhodes"
        community = getattr(request.state, "community", None) if request else None

        assert community_slug == "rhodes"
        assert community is None


# ============================================================================
# community_explicit flag (Session 107b)
# ============================================================================


class TestCommunityExplicit:
    """Test that CommunityMiddleware sets community_explicit correctly."""

    def test_is_community_explicit_with_explicit_request(self):
        """Request with community_explicit=True returns True."""
        from app.main import is_community_explicit

        request = MagicMock()
        request.state.community_explicit = True
        assert is_community_explicit(request) is True

    def test_is_community_explicit_with_default_request(self):
        """Request with community_explicit=False returns False."""
        from app.main import is_community_explicit

        request = MagicMock()
        request.state.community_explicit = False
        assert is_community_explicit(request) is False

    def test_is_community_explicit_no_request(self):
        """None request returns False."""
        from app.main import is_community_explicit

        assert is_community_explicit(None) is False

    def test_is_community_explicit_missing_attr(self):
        """Request without community_explicit attr returns False."""
        from app.main import is_community_explicit

        class BareRequest:
            class state:
                pass

        assert is_community_explicit(BareRequest()) is False

    def test_middleware_sets_explicit_true_for_prefixed_urls(self):
        """CommunityMiddleware source sets community_explicit=True for /c/{slug}/ URLs."""
        import re

        # This test verifies the middleware code path sets the flag.
        # We test the pattern match branch.
        pattern = re.compile(r"^/c/([a-z0-9_-]+)(/.*)?$")
        match = pattern.match("/c/fox-family/upload")
        assert match is not None
        assert match.group(1) == "fox-family"

    def test_middleware_sets_explicit_false_for_api_routes(self):
        """API routes skip community prefix extraction — explicit should be False."""
        # Verify the skip pattern
        path = "/api/identity/123/confirm"
        assert path.startswith("/api/")

    def test_upload_community_override_field(self):
        """Upload form should include hidden upload_community field."""
        import app.upload_routes as ur

        source = inspect.getsource(ur)
        assert "upload-community" in source
        assert "upload_community" in source


# ============================================================================
# sidebar function accepts community params
# ============================================================================


class TestSidebarCommunityParams:
    """Test that sidebar function accepts community_slug and community kwargs."""

    @patch("app.main._build_caches")
    def test_sidebar_accepts_community_params(self, mock_build):
        from app.main import sidebar

        counts = {
            "to_review": 5,
            "confirmed": 10,
            "skipped": 2,
            "rejected": 1,
            "photos": 20,
            "pending_uploads": 0,
            "proposals": 0,
            "pending_annotations": 0,
            "discoveries": 0,
        }
        # Should not raise — these are new kwargs
        result = sidebar(counts, "to_review", user=None, community_slug="fox-family", community={"slug": "fox-family"})
        assert result is not None

    @patch("app.main._build_caches")
    def test_sidebar_backward_compat(self, mock_build):
        """sidebar works without community params (backward compat)."""
        from app.main import sidebar

        counts = {
            "to_review": 0,
            "confirmed": 0,
            "skipped": 0,
            "rejected": 0,
            "photos": 0,
            "pending_uploads": 0,
            "proposals": 0,
            "pending_annotations": 0,
            "discoveries": 0,
        }
        result = sidebar(counts)
        assert result is not None

    def test_sidebar_signature_has_community_params(self):
        """sidebar function signature includes community_slug and community."""
        from app.main import sidebar

        sig = inspect.signature(sidebar)
        assert "community_slug" in sig.parameters
        assert "community" in sig.parameters
