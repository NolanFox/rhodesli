"""Tests for Session 134 Track A UX fixes.

FB-100: Cross-community badge on speed-run suggestions.
FB-113: "Identified" label for CONFIRMED person pages (was "Under Review").
"""

import os
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("STORAGE_MODE", "local")


def _make_identity(identity_id="test-id-123", name="Test Person", state="INBOX", num_faces=4):
    face_ids = [f"inbox_face_{i}" for i in range(num_faces)]
    return {
        "identity_id": identity_id,
        "name": name,
        "state": state,
        "anchor_ids": face_ids[:2],
        "candidate_ids": face_ids[2:],
        "negative_ids": [],
    }


class TestFB100CrossCommunityBadge:
    """FB-100: Speed-run enrichment panel shows community badge for cross-community suggestions."""

    def test_cross_community_suggestion_shows_badge(self):
        """When a suggestion is from a different community, a badge should appear."""
        from app.cluster_review_routes import _speed_run_enrichment_panel

        identity = _make_identity(state="CONFIRMED")
        community = {"id": "comm-1", "slug": "fox-family", "name": "Fox Family"}

        # Create a suggestion from a different community
        suggestions = [
            {
                "identity_id": "sug-id-1",
                "name": "Big Leon Capeluto",
                "face_count": 5,
                "best_face_id": "inbox_sug_face_0",
                "distance": 0.92,
            }
        ]

        # The cross-community badge should show "Rhodes" for a Rhodes identity
        cross_badge = MagicMock()
        cross_badge.__bool__ = MagicMock(return_value=True)

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "app.cluster_review_routes._get_crop_url_for_face",
                    return_value="/static/crops/test.jpg",
                )
            )
            stack.enter_context(
                patch(
                    "app.cluster_review_routes._get_confirmed_identity_suggestions",
                    return_value=suggestions,
                )
            )
            mock_badge_fn = stack.enter_context(
                patch(
                    "app.cluster_review_routes._main_mod._cross_community_badge",
                    return_value=cross_badge,
                )
            )

            panel = _speed_run_enrichment_panel("test-id-123", identity, 0, "fox-family", community=community)
            html = repr(panel)

            # The badge function should have been called with the suggestion's identity_id
            mock_badge_fn.assert_called_once_with("sug-id-1", community)

    def test_no_badge_when_no_community_context(self):
        """When community is None, no cross-community badge is shown."""
        from app.cluster_review_routes import _speed_run_enrichment_panel

        identity = _make_identity(state="CONFIRMED")

        suggestions = [
            {
                "identity_id": "sug-id-1",
                "name": "Some Person",
                "face_count": 3,
                "best_face_id": "inbox_sug_face_0",
                "distance": 0.90,
            }
        ]

        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "app.cluster_review_routes._get_crop_url_for_face",
                    return_value="/static/crops/test.jpg",
                )
            )
            stack.enter_context(
                patch(
                    "app.cluster_review_routes._get_confirmed_identity_suggestions",
                    return_value=suggestions,
                )
            )
            mock_badge_fn = stack.enter_context(
                patch(
                    "app.cluster_review_routes._main_mod._cross_community_badge",
                    return_value=None,
                )
            )
            panel = _speed_run_enrichment_panel("test-id-123", identity, 0, "", community=None)
            html = repr(panel)

            # Badge function should NOT have been called (community is None)
            mock_badge_fn.assert_not_called()


class TestFB113IdentifiedLabel:
    """FB-113: CONFIRMED person pages show 'Identified', not 'Under Review'."""

    def _render_person_page(self, identity, person_id="person-123"):
        """Helper to render person page and return HTML."""
        from starlette.testclient import TestClient
        from app.main import app

        client = TestClient(app)

        mock_reg = MagicMock()
        mock_reg.get_identity = MagicMock(return_value=identity)
        mock_reg._identities = {person_id: identity}
        mock_reg.list_identities = MagicMock(return_value=[identity])

        with ExitStack() as stack:
            stack.enter_context(patch("app.main.load_registry", return_value=mock_reg))
            stack.enter_context(patch("app.person_routes._main_mod.load_registry", return_value=mock_reg))
            stack.enter_context(patch("app.person_routes._main_mod._get_birth_year", return_value=(None, None, None)))
            stack.enter_context(
                patch("app.person_routes._main_mod._get_proposal_targets_for_identity", return_value=[])
            )
            stack.enter_context(patch("app.person_routes._main_mod.get_crop_files", return_value={}))
            stack.enter_context(
                patch("app.person_routes._main_mod.resolve_face_image_url", return_value="/static/crops/test.jpg")
            )
            stack.enter_context(
                patch(
                    "app.person_routes._main_mod.load_photo_registry",
                    return_value=MagicMock(
                        get_photo_for_face=MagicMock(return_value=None),
                        get_photos_for_faces=MagicMock(return_value=set()),
                        _photos={},
                        _face_to_photo={},
                    ),
                )
            )
            stack.enter_context(patch("app.person_routes._main_mod._check_admin", return_value="denied"))

            resp = client.get(f"/person/{person_id}")
            return resp.text

    def test_confirmed_person_shows_identified_badge(self):
        """CONFIRMED person pages should show 'Identified', not 'Confirmed' or 'Under Review'."""
        identity = _make_identity(
            identity_id="person-123",
            name="Leon Capeluto",
            state="CONFIRMED",
        )
        html = self._render_person_page(identity)
        assert "Identified" in html
        assert "Under Review" not in html

    def test_non_confirmed_person_shows_under_review(self):
        """Non-CONFIRMED person pages should still show 'Under Review'."""
        identity = _make_identity(
            identity_id="person-123",
            name="Unidentified Person 42",
            state="PROPOSED",
        )
        html = self._render_person_page(identity)
        assert "Under Review" in html
        assert "Identified" not in html

    def test_inbox_person_shows_under_review(self):
        """INBOX person pages should show 'Under Review'."""
        identity = _make_identity(
            identity_id="person-123",
            name="Unidentified Person 99",
            state="INBOX",
        )
        html = self._render_person_page(identity)
        assert "Under Review" in html
