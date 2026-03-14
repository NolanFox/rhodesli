"""Tests for speed-run enrichment flow: all faces, clickable crops, enrichment panel, name save, search."""

import json
import os
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("STORAGE_MODE", "local")


def _get_test_client():
    from starlette.testclient import TestClient
    from app.main import app

    return TestClient(app)


def _admin_session():
    return patch("app.cluster_review_routes._main_mod._check_admin", return_value=None)


def _mock_admin_email(email="admin@test.com"):
    return patch("app.cluster_review_routes._speed_run_admin_email", return_value=email)


def _mock_photo_registry():
    mock_pr = MagicMock()
    mock_pr.get_photo_for_face = MagicMock(return_value="photo-abc123")
    mock_pr.get_photos_for_faces = MagicMock(return_value=set())
    return patch("app.cluster_review_routes._main_mod.load_photo_registry", return_value=mock_pr)


def _make_identity(identity_id="test-id-123", name="Test Person", state="INBOX", num_faces=4):
    """Create a test identity with N faces."""
    face_ids = [f"inbox_face_{i}" for i in range(num_faces)]
    return {
        "identity_id": identity_id,
        "name": name,
        "state": state,
        "anchor_ids": face_ids[:2],
        "candidate_ids": face_ids[2:],
        "negative_ids": [],
    }


def _mock_registry_with_identities(identities_dict):
    """Create a mock registry with multiple identities."""
    mock_reg = MagicMock()
    mock_reg._identities = identities_dict
    mock_reg.promote_candidate = MagicMock()
    mock_reg.reject_candidate = MagicMock()
    mock_reg.rename_identity = MagicMock(return_value="Old Name")
    mock_reg.merge_identities = MagicMock(
        return_value={
            "success": True,
            "source_id": "src",
            "target_id": "tgt",
            "faces_merged": 2,
        }
    )
    mock_reg.get = MagicMock(side_effect=lambda iid: identities_dict.get(iid))
    return patch("app.cluster_review_routes._main_mod.load_registry", return_value=mock_reg)


class TestAllFacesRendered:
    """3A: All faces should render without an overflow cap."""

    def test_cluster_card_shows_all_faces_no_cap(self):
        """A cluster with 12 faces should show 12 face images, not 8 + '+4 more'."""
        from app.cluster_review_routes import _speed_run_cluster_card

        identity = _make_identity(num_faces=12)
        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "app.cluster_review_routes._get_crop_url_for_face",
                    return_value="/static/crops/test.jpg",
                )
            )
            stack.enter_context(
                patch(
                    "app.cluster_review_routes._get_photo_url_for_face",
                    return_value="/photo/test-photo",
                )
            )

            card = _speed_run_cluster_card("test-id", identity, 0, 5, "rhodes")
            html = repr(card)

            # Should have 12 img tags (one per face), not 8
            assert html.count("object-cover rounded-lg") >= 12
            # Should NOT have a "+N more" badge
            assert "+4" not in html
            assert "+more" not in html.lower().replace(" ", "")

    def test_face_crops_are_clickable_with_photo_links(self):
        """Each face crop should be wrapped in an <a> linking to the source photo."""
        from app.cluster_review_routes import _speed_run_cluster_card

        identity = _make_identity(num_faces=3)
        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "app.cluster_review_routes._get_crop_url_for_face",
                    return_value="/static/crops/test.jpg",
                )
            )
            stack.enter_context(
                patch(
                    "app.cluster_review_routes._get_photo_url_for_face",
                    return_value="/photo/test-photo-id",
                )
            )

            card = _speed_run_cluster_card("test-id", identity, 0, 5, "rhodes")
            html = repr(card)

            # Should contain links to photo pages
            assert "/photo/test-photo-id" in html
            assert 'target="_blank"' in html

    def test_scrollable_grid_class(self):
        """Face grid should have max-h-80 overflow-y-auto for scrollability."""
        from app.cluster_review_routes import _speed_run_cluster_card

        identity = _make_identity(num_faces=3)
        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "app.cluster_review_routes._get_crop_url_for_face",
                    return_value="/static/crops/test.jpg",
                )
            )
            stack.enter_context(
                patch(
                    "app.cluster_review_routes._get_photo_url_for_face",
                    return_value="/photo/test-photo",
                )
            )

            card = _speed_run_cluster_card("test-id", identity, 0, 5, "rhodes")
            html = repr(card)

            assert "max-h-80" in html
            assert "overflow-y-auto" in html

    def test_face_crops_112px_minimum(self):
        """Face crops should use w-28 h-28 (112px) — upgraded from 96px."""
        from app.cluster_review_routes import _speed_run_cluster_card

        identity = _make_identity(num_faces=2)
        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "app.cluster_review_routes._get_crop_url_for_face",
                    return_value="/static/crops/test.jpg",
                )
            )
            stack.enter_context(
                patch(
                    "app.cluster_review_routes._get_photo_url_for_face",
                    return_value="/photo/test-photo",
                )
            )

            card = _speed_run_cluster_card("test-id", identity, 0, 5, "rhodes")
            html = repr(card)

            assert "w-28" in html
            assert "h-28" in html


class TestEnrichmentPanel:
    """3B: After confirm-all in speed-run, an enrichment panel should render."""

    def test_enrichment_panel_renders_after_confirm(self):
        """Confirm-all with speed_run=true should return enrichment panel, not next card."""
        client = _get_test_client()
        identity = _make_identity()
        with ExitStack() as stack:
            stack.enter_context(_admin_session())
            stack.enter_context(_mock_registry_with_identities({"test-id-123": identity}))
            stack.enter_context(_mock_admin_email())
            stack.enter_context(patch("app.cluster_review_routes._main_mod.log_user_action"))
            stack.enter_context(patch("app.cluster_review_routes._main_mod.save_registry"))
            stack.enter_context(patch("app.cluster_review_routes._main_mod.datetime"))
            stack.enter_context(patch("app.cluster_review_routes._speed_run_undo_button", return_value=""))
            stack.enter_context(
                patch(
                    "app.cluster_review_routes._get_crop_url_for_face",
                    return_value="/static/crops/test.jpg",
                )
            )
            stack.enter_context(
                patch(
                    "app.cluster_review_routes._get_confirmed_identity_suggestions",
                    return_value=[],
                )
            )

            resp = client.post(
                "/api/cluster-review/confirm-all",
                data={
                    "identity_id": "test-id-123",
                    "speed_run": "true",
                    "offset": "0",
                    "community_slug": "",
                },
            )
            html = resp.text

            # Enrichment panel markers
            assert "Confirmed!" in html
            assert "enrichment-name-input" in html
            assert "Done" in html and "Next Cluster" in html
            assert "Skip" in html

    def test_enrichment_panel_has_data_enrichment_attribute(self):
        """The enrichment panel card should have data-enrichment='true'."""
        from app.cluster_review_routes import _speed_run_enrichment_panel

        identity = _make_identity()
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
                    return_value=[],
                )
            )

            panel = _speed_run_enrichment_panel("test-id", identity, 0, "rhodes")
            html = repr(panel)

            assert 'data-enrichment="true"' in html


class TestSaveNameEndpoint:
    """3B: POST /api/cluster-review/save-name."""

    def test_save_name_renames_and_advances(self):
        client = _get_test_client()
        identity = _make_identity()
        identities = {"test-id-123": identity}
        with ExitStack() as stack:
            stack.enter_context(_admin_session())
            mock_reg = stack.enter_context(_mock_registry_with_identities(identities))
            stack.enter_context(_mock_admin_email())
            stack.enter_context(patch("app.cluster_review_routes._main_mod.log_user_action"))
            stack.enter_context(patch("app.cluster_review_routes._main_mod.save_registry"))
            stack.enter_context(
                patch(
                    "app.cluster_review_routes._speed_run_next_card",
                    return_value="<div>next</div>",
                )
            )

            resp = client.post(
                "/api/cluster-review/save-name",
                data={
                    "identity_id": "test-id-123",
                    "new_name": "Albert Fox",
                    "offset": "0",
                    "community_slug": "",
                },
            )

            assert resp.status_code == 200

    def test_save_name_with_empty_name_still_advances(self):
        client = _get_test_client()
        identity = _make_identity()
        with ExitStack() as stack:
            stack.enter_context(_admin_session())
            stack.enter_context(_mock_registry_with_identities({"test-id-123": identity}))
            stack.enter_context(_mock_admin_email())
            stack.enter_context(
                patch(
                    "app.cluster_review_routes._speed_run_next_card",
                    return_value="<div>next</div>",
                )
            )

            resp = client.post(
                "/api/cluster-review/save-name",
                data={
                    "identity_id": "test-id-123",
                    "new_name": "",
                    "offset": "0",
                    "community_slug": "",
                },
            )

            assert resp.status_code == 200


class TestSearchIdentities:
    """3B: GET /api/cluster-review/search-identities."""

    def test_search_returns_matching_confirmed(self):
        client = _get_test_client()
        identities = {
            "confirmed-1": {
                "name": "Albert Fox",
                "state": "CONFIRMED",
                "anchor_ids": ["face_a"],
                "candidate_ids": [],
                "negative_ids": [],
            },
            "confirmed-2": {
                "name": "Esther Burd",
                "state": "CONFIRMED",
                "anchor_ids": ["face_b"],
                "candidate_ids": [],
                "negative_ids": [],
            },
            "inbox-1": {
                "name": "Some Fox Person",
                "state": "INBOX",
                "anchor_ids": ["face_c"],
                "candidate_ids": [],
                "negative_ids": [],
            },
        }
        with ExitStack() as stack:
            stack.enter_context(_admin_session())
            stack.enter_context(_mock_registry_with_identities(identities))
            stack.enter_context(
                patch(
                    "app.cluster_review_routes._get_crop_url_for_face",
                    return_value="/static/crops/test.jpg",
                )
            )

            resp = client.get("/api/cluster-review/search-identities?q=fox&source_id=inbox-1")
            html = resp.text

            assert "Albert Fox" in html
            # INBOX identity should NOT appear (only CONFIRMED)
            assert "Some Fox Person" not in html

    def test_search_too_short_returns_empty(self):
        client = _get_test_client()
        with ExitStack() as stack:
            stack.enter_context(_admin_session())

            resp = client.get("/api/cluster-review/search-identities?q=a")
            assert resp.status_code == 200


class TestMergeEndpoint:
    """3B: POST /api/cluster-review/merge."""

    def test_merge_succeeds_and_shows_merged_banner(self):
        client = _get_test_client()
        identities = {
            "source-id": _make_identity(identity_id="source-id", name="Unnamed"),
            "target-id": _make_identity(identity_id="target-id", name="Albert Fox", state="CONFIRMED"),
        }
        with ExitStack() as stack:
            stack.enter_context(_admin_session())
            stack.enter_context(_mock_registry_with_identities(identities))
            stack.enter_context(_mock_photo_registry())
            stack.enter_context(_mock_admin_email())
            stack.enter_context(patch("app.cluster_review_routes._main_mod.log_user_action"))
            stack.enter_context(patch("app.cluster_review_routes._main_mod.save_registry"))

            resp = client.post(
                "/api/cluster-review/merge",
                data={
                    "source_id": "source-id",
                    "target_id": "target-id",
                    "offset": "0",
                    "community_slug": "",
                },
            )

            html = resp.text
            assert "Merged!" in html


class TestKeyboardShortcuts:
    """Keyboard shortcuts must continue working (Y/N/S/D/Z)."""

    def test_speed_run_page_has_keyboard_handler(self):
        """The speed-run page should contain the keyboard JS handler."""
        from fasthtml.common import Div

        client = _get_test_client()
        identity = _make_identity()
        with ExitStack() as stack:
            stack.enter_context(_admin_session())
            stack.enter_context(
                patch(
                    "app.cluster_review_routes._get_speed_run_clusters",
                    return_value=[("test-id", identity)],
                )
            )
            stack.enter_context(
                patch(
                    "app.cluster_review_routes._speed_run_cluster_card",
                    return_value=Div("card", id="speed-run-card"),
                )
            )

            resp = client.get("/admin/upload-review?mode=speed")
            html = resp.text

            assert "keydown" in html
            assert "speed-confirm" in html
            assert "speed-reject" in html
            assert "speed-skip" in html
            assert "speed-dismiss" in html
            # Enrichment-mode handling
            assert "data-enrichment" in html

    def test_recent_actions_sidebar_in_page(self):
        """The speed-run page should include the recent actions sidebar container."""
        client = _get_test_client()
        identity = _make_identity()
        from fasthtml.common import Div

        with ExitStack() as stack:
            stack.enter_context(_admin_session())
            stack.enter_context(
                patch(
                    "app.cluster_review_routes._get_speed_run_clusters",
                    return_value=[("test-id", identity)],
                )
            )
            stack.enter_context(
                patch(
                    "app.cluster_review_routes._speed_run_cluster_card",
                    return_value=Div("card", id="speed-run-card"),
                )
            )

            resp = client.get("/admin/upload-review?mode=speed")
            html = resp.text

            assert "speed-run-recent-actions" in html
            assert "speed-run-action-list" in html
            assert "Recent Actions" in html
