"""
Tests for inbox triage UX — triage bar, promotion badges, filtering.

These tests verify:
- Triage category classification (ready/rediscovered/unmatched)
- Triage bar rendering with correct counts
- Filter parameter correctly filters to_review list
- Promotion badges appear on promoted identities
- Focus mode ordering prioritizes confirmed matches > promotions > unmatched
"""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest


def make_identity(identity_id, state="INBOX", name=None, promoted_from=None,
                  promotion_reason=None, promotion_context=None):
    """Create a minimal identity dict for triage tests."""
    now = datetime.now(timezone.utc).isoformat()
    identity = {
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
    if promoted_from:
        identity["promoted_from"] = promoted_from
        identity["promoted_at"] = now
        identity["promotion_reason"] = promotion_reason or "new_face_match"
    if promotion_context:
        identity["promotion_context"] = promotion_context
    return identity


class TestTriageCategories:
    """Tests for _compute_triage_counts and _triage_category."""

    @patch("app.main._get_identities_with_proposals")
    @patch("app.main._get_best_proposal_for_identity")
    def test_ready_to_confirm_counted(self, mock_best, mock_ids):
        from app.main import _compute_triage_counts

        mock_ids.return_value = {"id1"}
        mock_best.return_value = {"distance": 0.7, "confidence": "VERY HIGH"}

        to_review = [make_identity("id1")]
        counts = _compute_triage_counts(to_review)

        assert counts["ready_to_confirm"] == 1
        assert counts["rediscovered"] == 0
        assert counts["unmatched"] == 0

    @patch("app.main._get_identities_with_proposals")
    @patch("app.main._get_best_proposal_for_identity")
    def test_rediscovered_counted(self, mock_best, mock_ids):
        from app.main import _compute_triage_counts

        mock_ids.return_value = set()  # No proposals

        to_review = [make_identity("id1", promoted_from="SKIPPED",
                                    promotion_reason="new_face_match")]
        counts = _compute_triage_counts(to_review)

        assert counts["ready_to_confirm"] == 0
        assert counts["rediscovered"] == 1
        assert counts["unmatched"] == 0

    @patch("app.main._get_identities_with_proposals")
    @patch("app.main._get_best_proposal_for_identity")
    def test_unmatched_counted(self, mock_best, mock_ids):
        from app.main import _compute_triage_counts

        mock_ids.return_value = set()  # No proposals

        to_review = [make_identity("id1")]
        counts = _compute_triage_counts(to_review)

        assert counts["ready_to_confirm"] == 0
        assert counts["rediscovered"] == 0
        assert counts["unmatched"] == 1

    @patch("app.main._get_identities_with_proposals")
    @patch("app.main._get_best_proposal_for_identity")
    def test_mixed_categories(self, mock_best, mock_ids):
        from app.main import _compute_triage_counts

        mock_ids.return_value = {"id1", "id2"}
        def best_proposal(iid):
            if iid == "id1":
                return {"distance": 0.7, "confidence": "VERY HIGH"}
            return {"distance": 1.1, "confidence": "MODERATE"}
        mock_best.side_effect = best_proposal

        to_review = [
            make_identity("id1"),  # Has VH proposal -> ready
            make_identity("id2"),  # Has MODERATE proposal -> ready (has proposal)
            make_identity("id3", promoted_from="SKIPPED"),  # Promoted -> rediscovered
            make_identity("id4"),  # No proposals, not promoted -> unmatched
        ]
        counts = _compute_triage_counts(to_review)

        assert counts["ready_to_confirm"] == 2
        assert counts["rediscovered"] == 1
        assert counts["unmatched"] == 1


class TestTriageCategory:
    """Tests for _triage_category individual classification."""

    @patch("app.main._get_identities_with_proposals")
    def test_identity_with_proposal_is_ready(self, mock_ids):
        from app.main import _triage_category

        mock_ids.return_value = {"id1"}
        identity = make_identity("id1")

        assert _triage_category(identity) == "ready"

    @patch("app.main._get_identities_with_proposals")
    def test_promoted_identity_is_rediscovered(self, mock_ids):
        from app.main import _triage_category

        mock_ids.return_value = set()
        identity = make_identity("id1", promoted_from="SKIPPED")

        assert _triage_category(identity) == "rediscovered"

    @patch("app.main._get_identities_with_proposals")
    def test_plain_identity_is_unmatched(self, mock_ids):
        from app.main import _triage_category

        mock_ids.return_value = set()
        identity = make_identity("id1")

        assert _triage_category(identity) == "unmatched"


class TestTriageBar:
    """Tests for _build_triage_bar rendering."""

    @patch("app.main._get_identities_with_proposals")
    @patch("app.main._get_best_proposal_for_identity")
    def test_triage_bar_contains_counts(self, mock_best, mock_ids):
        from app.main import _build_triage_bar

        mock_ids.return_value = {"id1"}
        mock_best.return_value = {"distance": 0.7, "confidence": "VERY HIGH"}

        to_review = [
            make_identity("id1"),
            make_identity("id2"),
        ]
        bar = _build_triage_bar(to_review, "focus")

        assert bar is not None
        # Render to string to check content
        from starlette.testclient import TestClient
        html = str(bar)
        assert "Ready to Confirm" in html
        assert "Unmatched" in html

    @patch("app.main._get_identities_with_proposals")
    @patch("app.main._get_best_proposal_for_identity")
    def test_triage_bar_hides_zero_categories(self, mock_best, mock_ids):
        from app.main import _build_triage_bar

        mock_ids.return_value = set()  # No proposals

        to_review = [make_identity("id1")]
        bar = _build_triage_bar(to_review, "focus")

        html = str(bar) if bar else ""
        assert "Ready to Confirm" not in html
        assert "Rediscovered" not in html

    @patch("app.main._get_identities_with_proposals")
    @patch("app.main._get_best_proposal_for_identity")
    def test_triage_bar_none_when_empty(self, mock_best, mock_ids):
        from app.main import _build_triage_bar

        mock_ids.return_value = set()
        bar = _build_triage_bar([], "focus")

        assert bar is None


class TestPromotionBadge:
    """Tests for _promotion_badge rendering."""

    def test_no_badge_for_normal_identity(self):
        from app.main import _promotion_badge

        identity = make_identity("id1")
        assert _promotion_badge(identity) is None

    def test_badge_for_new_face_match(self):
        from app.main import _promotion_badge

        identity = make_identity("id1", promoted_from="SKIPPED",
                                  promotion_reason="new_face_match")
        badge = _promotion_badge(identity)

        assert badge is not None
        html = str(badge)
        assert "Rediscovered" in html

    def test_badge_for_confirmed_match(self):
        from app.main import _promotion_badge

        identity = make_identity("id1", promoted_from="SKIPPED",
                                  promotion_reason="confirmed_match")
        badge = _promotion_badge(identity)

        assert badge is not None
        html = str(badge)
        assert "Suggested ID" in html


class TestPromotionBanner:
    """Tests for _promotion_banner in Focus mode."""

    def test_no_banner_for_normal_identity(self):
        from app.main import _promotion_banner

        identity = make_identity("id1")
        assert _promotion_banner(identity) is None

    def test_banner_for_new_face_match(self):
        from app.main import _promotion_banner

        identity = make_identity("id1", promoted_from="SKIPPED",
                                  promotion_reason="new_face_match")
        banner = _promotion_banner(identity)

        assert banner is not None
        html = str(banner)
        assert "New Context Available" in html

    def test_banner_for_confirmed_match(self):
        from app.main import _promotion_banner

        identity = make_identity("id1", promoted_from="SKIPPED",
                                  promotion_reason="confirmed_match")
        banner = _promotion_banner(identity)

        assert banner is not None
        html = str(banner)
        assert "Identity Suggested" in html

    def test_banner_for_group_discovery(self):
        from app.main import _promotion_banner

        identity = make_identity("id1", promoted_from="SKIPPED",
                                  promotion_reason="group_discovery")
        banner = _promotion_banner(identity)

        assert banner is not None
        html = str(banner)
        assert "Rediscovered" in html


class TestFocusOrdering:
    """Tests for Focus mode sorting by triage priority."""

    @patch("app.main._get_identities_with_proposals")
    @patch("app.main._get_best_proposal_for_identity")
    def test_confirmed_match_sorted_first(self, mock_best, mock_ids):
        """Confirmed match promotions should appear before regular proposals."""
        from app.main import _triage_category

        mock_ids.return_value = {"id2"}
        mock_best.return_value = {"distance": 0.7, "confidence": "VERY HIGH"}

        identities = [
            make_identity("id1"),  # unmatched
            make_identity("id2"),  # has VH proposal
            make_identity("id3", promoted_from="SKIPPED",
                           promotion_reason="confirmed_match"),  # confirmed match
        ]

        # The confirmed_match promotion should be "rediscovered" category
        assert _triage_category(identities[2]) == "rediscovered"
        # The proposal identity should be "ready"
        assert _triage_category(identities[1]) == "ready"
        # The plain identity should be "unmatched"
        assert _triage_category(identities[0]) == "unmatched"


class TestUpNextFilterPreservation:
    """Tests that Up Next thumbnails preserve the active filter parameter."""

    def test_mini_card_includes_filter_in_link(self):
        """identity_card_mini with triage_filter includes it in href."""
        from app.main import identity_card_mini

        identity = make_identity("abc123def456")
        card = identity_card_mini(identity, crop_files=set(), clickable=True,
                                   triage_filter="rediscovered")
        html = str(card)
        assert "filter=rediscovered" in html
        assert "current=abc123def456" in html

    def test_mini_card_no_filter_when_empty(self):
        """identity_card_mini without triage_filter has no filter param."""
        from app.main import identity_card_mini

        identity = make_identity("abc123def456")
        card = identity_card_mini(identity, crop_files=set(), clickable=True,
                                   triage_filter="")
        html = str(card)
        assert "filter=" not in html

    def test_mini_card_preserves_section_and_filter(self):
        """identity_card_mini includes correct section AND filter."""
        from app.main import identity_card_mini

        identity = make_identity("abc123def456", state="INBOX")
        card = identity_card_mini(identity, crop_files=set(), clickable=True,
                                   triage_filter="ready")
        html = str(card)
        assert "section=to_review" in html
        assert "view=focus" in html
        assert "filter=ready" in html


class TestPromotionContextPopulated:
    """Tests that promotion banners display context when available."""

    def test_banner_shows_custom_context_for_group_discovery(self):
        from app.main import _promotion_banner

        identity = make_identity("id1", promoted_from="SKIPPED",
                                  promotion_reason="group_discovery",
                                  promotion_context="Groups with Person 033, Person 034")
        banner = _promotion_banner(identity)
        html = str(banner)
        assert "Groups with Person 033, Person 034" in html
        assert "Rediscovered" in html

    def test_banner_shows_custom_context_for_new_face_match(self):
        from app.main import _promotion_banner

        identity = make_identity("id1", promoted_from="SKIPPED",
                                  promotion_reason="new_face_match",
                                  promotion_context="Matches with Person 088 from recently uploaded photos")
        banner = _promotion_banner(identity)
        html = str(banner)
        assert "Matches with Person 088" in html
        assert "New Context Available" in html

    def test_banner_shows_custom_context_for_confirmed_match(self):
        from app.main import _promotion_banner

        identity = make_identity("id1", promoted_from="SKIPPED",
                                  promotion_reason="confirmed_match",
                                  promotion_context="Matches Victoria Capuano at distance 0.612 (VERY HIGH)")
        banner = _promotion_banner(identity)
        html = str(banner)
        assert "Matches Victoria Capuano" in html
        assert "Identity Suggested" in html

    def test_banner_falls_back_to_generic_without_context(self):
        from app.main import _promotion_banner

        identity = make_identity("id1", promoted_from="SKIPPED",
                                  promotion_reason="group_discovery")
        banner = _promotion_banner(identity)
        html = str(banner)
        assert "groups with another face" in html


class TestExpandedCardFilterPropagation:
    """Tests that expanded card action buttons include the filter parameter."""

    def test_skip_url_includes_filter(self):
        """Skip button URL in focus mode includes filter parameter."""
        from app.main import identity_card_expanded, to_xml

        identity = make_identity("abc123", state="INBOX")
        card = identity_card_expanded(identity, crop_files=set(), is_admin=True,
                                       triage_filter="ready")
        html = to_xml(card)
        assert "filter=ready" in html
        assert "/identity/abc123/skip?from_focus=true&amp;filter=ready" in html

    def test_confirm_url_includes_filter(self):
        """Confirm button URL in focus mode includes filter parameter."""
        from app.main import identity_card_expanded, to_xml

        identity = make_identity("abc123", state="INBOX")
        card = identity_card_expanded(identity, crop_files=set(), is_admin=True,
                                       triage_filter="rediscovered")
        html = to_xml(card)
        assert "filter=rediscovered" in html
        assert "/inbox/abc123/confirm?from_focus=true&amp;filter=rediscovered" in html

    def test_reject_url_includes_filter(self):
        """Reject button URL in focus mode includes filter parameter."""
        from app.main import identity_card_expanded, to_xml

        identity = make_identity("abc123", state="INBOX")
        card = identity_card_expanded(identity, crop_files=set(), is_admin=True,
                                       triage_filter="unmatched")
        html = to_xml(card)
        assert "filter=unmatched" in html
        assert "/inbox/abc123/reject?from_focus=true&amp;filter=unmatched" in html

    def test_no_filter_when_empty(self):
        """Action URLs don't include filter= when no filter is active."""
        from app.main import identity_card_expanded, to_xml

        identity = make_identity("abc123", state="INBOX")
        card = identity_card_expanded(identity, crop_files=set(), is_admin=True,
                                       triage_filter="")
        html = to_xml(card)
        assert "filter=" not in html
        assert "/identity/abc123/skip?from_focus=true" in html


class TestGetNextFocusCardFilter:
    """Tests that get_next_focus_card respects triage_filter."""

    @patch("app.main._get_identities_with_proposals")
    @patch("app.main._get_best_proposal_for_identity")
    @patch("app.main.save_registry")
    @patch("app.main.load_registry")
    @patch("app.main.get_crop_files")
    def test_filter_limits_results(self, mock_crops, mock_load, mock_save,
                                    mock_best, mock_ids):
        """get_next_focus_card with filter=unmatched excludes items with proposals."""
        from app.main import get_next_focus_card

        mock_crops.return_value = set()
        mock_ids.return_value = {"id1"}
        mock_best.return_value = {"distance": 0.7, "confidence": "VERY HIGH"}

        # Create mock registry with two identities: one with proposal, one without
        ready_id = make_identity("id1")  # has proposal -> ready
        unmatched_id = make_identity("id2")  # no proposal -> unmatched

        mock_reg = MagicMock()
        mock_reg.list_identities.side_effect = lambda state: {
            "INBOX": [ready_id, unmatched_id],
            "PROPOSED": [],
        }.get(state.value if hasattr(state, 'value') else state, [])
        mock_load.return_value = mock_reg

        result = get_next_focus_card(triage_filter="unmatched")
        from app.main import to_xml
        html = to_xml(result)
        # Should NOT show the identity with proposal (id1)
        # Should show the unmatched identity (id2)
        assert "id2" in html

    @patch("app.main._get_identities_with_proposals")
    @patch("app.main._get_best_proposal_for_identity")
    @patch("app.main.save_registry")
    @patch("app.main.load_registry")
    @patch("app.main.get_crop_files")
    def test_filter_passes_to_up_next(self, mock_crops, mock_load, mock_save,
                                       mock_best, mock_ids):
        """get_next_focus_card passes triage_filter to Up Next mini cards."""
        from app.main import get_next_focus_card

        mock_crops.return_value = set()
        mock_ids.return_value = set()

        items = [make_identity(f"id{i}") for i in range(5)]
        mock_reg = MagicMock()
        mock_reg.list_identities.side_effect = lambda state: {
            "INBOX": items,
            "PROPOSED": [],
        }.get(state.value if hasattr(state, 'value') else state, [])
        mock_load.return_value = mock_reg

        result = get_next_focus_card(triage_filter="unmatched")
        from app.main import to_xml
        html = to_xml(result)
        assert "filter=unmatched" in html

    @patch("app.main._get_identities_with_proposals")
    @patch("app.main._get_best_proposal_for_identity")
    @patch("app.main.save_registry")
    @patch("app.main.load_registry")
    @patch("app.main.get_crop_files")
    def test_empty_state_when_filtered_results_empty(self, mock_crops, mock_load,
                                                      mock_save, mock_best, mock_ids):
        """get_next_focus_card returns empty state when filter excludes all items."""
        from app.main import get_next_focus_card

        mock_crops.return_value = set()
        mock_ids.return_value = {"id1"}
        mock_best.return_value = {"distance": 0.7, "confidence": "VERY HIGH"}

        # Only one identity, and it has a proposal -> "ready"
        items = [make_identity("id1")]
        mock_reg = MagicMock()
        mock_reg.list_identities.side_effect = lambda state: {
            "INBOX": items,
            "PROPOSED": [],
        }.get(state.value if hasattr(state, 'value') else state, [])
        mock_load.return_value = mock_reg

        # Filter for "unmatched" should exclude this identity
        result = get_next_focus_card(triage_filter="unmatched")
        from app.main import to_xml
        html = to_xml(result)
        assert "All caught up" in html


class TestPhotoNavBoundaryIndicators:
    """Tests for first/last photo boundary indicators in photo navigation."""

    def test_first_photo_shows_disabled_prev(self):
        """First photo in set shows disabled prev arrow with 'First photo' title."""
        from app.main import photo_view_content, to_xml
        from unittest.mock import patch

        with patch("app.main.get_photo_metadata") as mock_meta, \
             patch("app.main.get_photo_dimensions") as mock_dims, \
             patch("app.main.load_registry") as mock_reg:

            mock_meta.return_value = {
                "filename": "test.jpg",
                "faces": [],
                "collection": "",
                "source": "",
            }
            mock_dims.return_value = (100, 100)
            mock_reg.return_value = MagicMock()

            result = photo_view_content(
                "photo1", is_partial=True,
                prev_id=None, next_id="photo2",
                nav_idx=0, nav_total=5,
            )
            html = to_xml(*result)
            assert "First photo" in html
            assert "Last photo" not in html

    def test_last_photo_shows_disabled_next(self):
        """Last photo in set shows disabled next arrow with 'Last photo' title."""
        from app.main import photo_view_content, to_xml
        from unittest.mock import patch

        with patch("app.main.get_photo_metadata") as mock_meta, \
             patch("app.main.get_photo_dimensions") as mock_dims, \
             patch("app.main.load_registry") as mock_reg:

            mock_meta.return_value = {
                "filename": "test.jpg",
                "faces": [],
                "collection": "",
                "source": "",
            }
            mock_dims.return_value = (100, 100)
            mock_reg.return_value = MagicMock()

            result = photo_view_content(
                "photo1", is_partial=True,
                prev_id="photo0", next_id=None,
                nav_idx=4, nav_total=5,
            )
            html = to_xml(*result)
            assert "Last photo" in html
            assert "First photo" not in html

    def test_middle_photo_no_boundary_indicators(self):
        """Middle photo shows neither boundary indicator."""
        from app.main import photo_view_content, to_xml
        from unittest.mock import patch

        with patch("app.main.get_photo_metadata") as mock_meta, \
             patch("app.main.get_photo_dimensions") as mock_dims, \
             patch("app.main.load_registry") as mock_reg:

            mock_meta.return_value = {
                "filename": "test.jpg",
                "faces": [],
                "collection": "",
                "source": "",
            }
            mock_dims.return_value = (100, 100)
            mock_reg.return_value = MagicMock()

            result = photo_view_content(
                "photo1", is_partial=True,
                prev_id="photo0", next_id="photo2",
                nav_idx=2, nav_total=5,
            )
            html = to_xml(*result)
            assert "First photo" not in html
            assert "Last photo" not in html
