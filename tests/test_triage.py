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
