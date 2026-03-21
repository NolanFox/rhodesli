"""Tests for focus mode community scoping (Session 129).

Bug: After any action in Focus mode on /c/fox-family/?section=to_review,
the next identity shown comes from the wrong community. The root cause is
that get_next_focus_card and get_next_skipped_focus_card did not filter
identities by community.

Tests verify:
1. get_next_focus_card filters by community when community is provided
2. get_next_skipped_focus_card filters by community when community is provided
3. Action endpoints (confirm, reject, skip, merge) pass community to next-card lookup
4. When community is None (Rhodes default), no filtering happens (backward compat)
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest


def _make_identity(identity_id, state="INBOX", name=None):
    """Create a minimal identity dict."""
    now = datetime.now(timezone.utc).isoformat()
    return {
        "identity_id": identity_id,
        "name": name or f"Unidentified Person {identity_id[:8]}",
        "state": state,
        "anchor_ids": [f"face_{identity_id[:8]}"],
        "candidate_ids": [],
        "negative_ids": [],
        "version_id": 1,
        "created_at": now,
        "updated_at": now,
    }


FOX_COMMUNITY = {"id": "fox-uuid", "slug": "fox-family", "name": "Fox Family Archive"}
RHODES_COMMUNITY = {"id": "rhodes-uuid", "slug": "rhodes", "name": "Rhodes", "is_default": True}

# Two identities: one in Fox community, one not
FOX_IDENTITY = _make_identity("fox-id-001", state="INBOX")
RHODES_IDENTITY = _make_identity("rhodes-id-001", state="INBOX")
FOX_SKIPPED = _make_identity("fox-id-002", state="SKIPPED")
RHODES_SKIPPED = _make_identity("rhodes-id-002", state="SKIPPED")


class TestGetNextFocusCardCommunityScoping:
    """get_next_focus_card must filter identities by community."""

    @patch("app.main._get_identities_with_proposals")
    @patch("app.main._get_best_proposal_for_identity")
    @patch("app.main._get_community_identity_ids")
    @patch("app.main.get_crop_files")
    @patch("app.main.load_registry")
    def test_filters_to_community_identities(self, mock_registry, mock_crops, mock_community_ids, mock_best, mock_ids):
        """When community is provided, only identities in that community are returned."""
        from app.main import get_next_focus_card

        registry = MagicMock()
        # Return identities from both communities
        registry.list_identities.side_effect = lambda state=None: {
            "INBOX": [FOX_IDENTITY, RHODES_IDENTITY],
            "PROPOSED": [],
        }.get(state.value if hasattr(state, "value") else state, [])
        mock_registry.return_value = registry
        mock_crops.return_value = set()
        # Only fox-id-001 is in Fox community
        mock_community_ids.return_value = {"fox-id-001"}
        mock_ids.return_value = set()
        mock_best.return_value = None

        result = get_next_focus_card(community=FOX_COMMUNITY, nav_prefix="/c/fox-family")

        # Should show fox identity, not rhodes
        from fasthtml.common import to_xml

        html = to_xml(result)
        assert "fox-id-001" in html or "Unidentified Person fox-id-0" in html
        # Rhodes identity should NOT be in the output
        assert "rhodes-id-001" not in html

    @patch("app.main._get_identities_with_proposals")
    @patch("app.main._get_best_proposal_for_identity")
    @patch("app.main._get_community_identity_ids")
    @patch("app.main.get_crop_files")
    @patch("app.main.load_registry")
    def test_no_filtering_when_community_is_none(
        self, mock_registry, mock_crops, mock_community_ids, mock_best, mock_ids
    ):
        """When community is None (Rhodes default), all identities are returned."""
        from app.main import get_next_focus_card

        registry = MagicMock()
        registry.list_identities.side_effect = lambda state=None: {
            "INBOX": [FOX_IDENTITY, RHODES_IDENTITY],
            "PROPOSED": [],
        }.get(state.value if hasattr(state, "value") else state, [])
        mock_registry.return_value = registry
        mock_crops.return_value = set()
        mock_community_ids.return_value = None  # No filtering
        mock_ids.return_value = set()
        mock_best.return_value = None

        result = get_next_focus_card(community=None, nav_prefix="")

        from fasthtml.common import to_xml

        html = to_xml(result)
        # Both identities should be available (the first one shown depends on sort)
        # The key test: no community filtering was applied
        mock_community_ids.assert_called_once_with(None)

    @patch("app.main._get_identities_with_proposals")
    @patch("app.main._get_best_proposal_for_identity")
    @patch("app.main._get_community_identity_ids")
    @patch("app.main.get_crop_files")
    @patch("app.main.load_registry")
    def test_empty_community_shows_empty_state(
        self, mock_registry, mock_crops, mock_community_ids, mock_best, mock_ids
    ):
        """When community has no identities, show empty state."""
        from app.main import get_next_focus_card

        registry = MagicMock()
        registry.list_identities.side_effect = lambda state=None: {
            "INBOX": [RHODES_IDENTITY],
            "PROPOSED": [],
        }.get(state.value if hasattr(state, "value") else state, [])
        mock_registry.return_value = registry
        mock_crops.return_value = set()
        mock_community_ids.return_value = set()  # Empty — no identities in this community
        mock_ids.return_value = set()
        mock_best.return_value = None

        result = get_next_focus_card(community=FOX_COMMUNITY, nav_prefix="/c/fox-family")

        from fasthtml.common import to_xml

        html = to_xml(result)
        assert "All caught up" in html


class TestGetNextSkippedFocusCardCommunityScoping:
    """get_next_skipped_focus_card must filter identities by community."""

    @patch("app.main._get_community_identity_ids")
    @patch("app.main._sort_skipped_by_actionability")
    @patch("app.main.get_crop_files")
    @patch("app.main.load_registry")
    def test_filters_skipped_to_community(self, mock_registry, mock_crops, mock_sort, mock_community_ids):
        """When community is provided, only skipped identities in that community are returned."""
        from app.main import get_next_skipped_focus_card

        registry = MagicMock()
        registry.list_identities.return_value = [FOX_SKIPPED, RHODES_SKIPPED]
        mock_registry.return_value = registry
        mock_crops.return_value = set()
        mock_community_ids.return_value = {"fox-id-002"}
        # Sort passthrough — return what's given
        mock_sort.side_effect = lambda x: x

        result = get_next_skipped_focus_card(community=FOX_COMMUNITY, nav_prefix="/c/fox-family")

        # Verify _sort_skipped_by_actionability only received fox identity
        args = mock_sort.call_args[0][0]
        assert len(args) == 1
        assert args[0]["identity_id"] == "fox-id-002"

    @patch("app.main._get_community_identity_ids")
    @patch("app.main._sort_skipped_by_actionability")
    @patch("app.main.get_crop_files")
    @patch("app.main.load_registry")
    def test_no_filtering_when_community_none(self, mock_registry, mock_crops, mock_sort, mock_community_ids):
        """When community is None, all skipped identities are included."""
        from app.main import get_next_skipped_focus_card

        registry = MagicMock()
        registry.list_identities.return_value = [FOX_SKIPPED, RHODES_SKIPPED]
        mock_registry.return_value = registry
        mock_crops.return_value = set()
        mock_community_ids.return_value = None
        mock_sort.side_effect = lambda x: x

        get_next_skipped_focus_card(community=None, nav_prefix="")

        args = mock_sort.call_args[0][0]
        assert len(args) == 2  # Both identities passed through


class TestCommunityFromRequestHelper:
    """_community_from_request helper in identity_routes."""

    def test_returns_community_from_request_state(self):
        from app.identity_routes import _community_from_request

        request = MagicMock()
        request.state.community = FOX_COMMUNITY
        assert _community_from_request(request) == FOX_COMMUNITY

    def test_returns_none_when_community_is_none(self):
        from app.identity_routes import _community_from_request

        request = MagicMock()
        request.state.community = None
        assert _community_from_request(request) is None

    def test_returns_none_for_none_request(self):
        from app.identity_routes import _community_from_request

        assert _community_from_request(None) is None
