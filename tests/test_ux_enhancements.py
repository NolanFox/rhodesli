"""
Tests for UX enhancements:
1. Compare modal "View Photo" links with hx-get targeting /photo/{id}/partial
2. Post-merge guidance banner (Grouped vs Merge complete)
3. Grouped badge for unnamed multi-face identities

Pruned: removed CSS class assertions (compare modal size, zoom hyperscript,
cursor classes). Kept functional behavior tests.
"""

import pytest
from unittest.mock import patch, MagicMock

from starlette.testclient import TestClient


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app)


# ---------------------------------------------------------------------------
# Helpers: build mock registries for route-level tests
# ---------------------------------------------------------------------------


def _make_identity(identity_id, name=None, state="PROPOSED", anchor_ids=None, candidate_ids=None):
    """Create a minimal identity dict matching the registry schema."""
    return {
        "identity_id": identity_id,
        "name": name or f"Unidentified Person {identity_id[:8]}",
        "state": state,
        "anchor_ids": anchor_ids or [],
        "candidate_ids": candidate_ids or [],
        "negative_ids": [],
        "version_id": 1,
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "history": [],
    }


def _make_registry(identities_list):
    """Build a real IdentityRegistry populated with test identities."""
    from core.registry import IdentityRegistry

    registry = IdentityRegistry()
    for ident in identities_list:
        registry._identities[ident["identity_id"]] = ident
    return registry


def _make_photo_registry_mock():
    """Build a mock PhotoRegistry that allows all merges (no co-occurrence)."""
    photo_reg = MagicMock()
    photo_reg.get_photos_for_faces.return_value = set()
    return photo_reg


# ---------------------------------------------------------------------------
# 1. Compare modal "View Photo" links
# ---------------------------------------------------------------------------


class TestCompareViewPhotoLinks:
    """The compare endpoint should include 'View Photo' buttons."""

    def _build_compare_mocks(self):
        target = _make_identity("target-aaa", name="Leon Capeluto", state="CONFIRMED", anchor_ids=["face-t1"])
        neighbor = _make_identity("neighbor-bbb", name="Betty Capeluto", state="CONFIRMED", anchor_ids=["face-n1"])
        registry = _make_registry([target, neighbor])
        crop_files = {"face-t1.jpg", "face-n1.jpg"}
        face_to_photo = {"face-t1": "photo-001", "face-n1": "photo-002"}
        photo_cache = {
            "photo-001": {"filename": "img1.jpg", "faces": [{"face_id": "face-t1"}], "source": "test"},
            "photo-002": {"filename": "img2.jpg", "faces": [{"face_id": "face-n1"}], "source": "test"},
        }
        return registry, crop_files, face_to_photo, photo_cache

    def test_compare_faces_view_has_view_photo_buttons(self, client):
        """Faces view includes 'View Photo' buttons for both sides."""
        registry, crop_files, face_to_photo, photo_cache = self._build_compare_mocks()

        with (
            patch("app.main.is_auth_enabled", return_value=False),
            patch("app.main.load_registry", return_value=registry),
            patch("app.main.get_crop_files", return_value=crop_files),
            patch("app.main.resolve_face_image_url", return_value="/static/crops/face.jpg"),
            patch("app.main._face_to_photo_cache", face_to_photo),
            patch("app.main._photo_cache", photo_cache),
            patch("app.main._build_caches"),
        ):
            resp = client.get("/api/identity/target-aaa/compare/neighbor-bbb?view=faces")
            assert resp.status_code == 200
            html = resp.text
            assert "View Photo" in html
            assert 'hx-get="/photo/photo-001/partial' in html
            assert 'hx-get="/photo/photo-002/partial' in html

    def test_view_photo_button_includes_face_param(self, client):
        """View Photo buttons pass the face ID as a query parameter."""
        registry, crop_files, face_to_photo, photo_cache = self._build_compare_mocks()

        with (
            patch("app.main.is_auth_enabled", return_value=False),
            patch("app.main.load_registry", return_value=registry),
            patch("app.main.get_crop_files", return_value=crop_files),
            patch("app.main.resolve_face_image_url", return_value="/static/crops/face.jpg"),
            patch("app.main._face_to_photo_cache", face_to_photo),
            patch("app.main._photo_cache", photo_cache),
            patch("app.main._build_caches"),
        ):
            resp = client.get("/api/identity/target-aaa/compare/neighbor-bbb?view=faces")
            html = resp.text
            assert "face=face-t1" in html
            assert "face=face-n1" in html


# ---------------------------------------------------------------------------
# 2. Post-merge guidance banner
# ---------------------------------------------------------------------------


class TestPostMergeGuidanceBanner:
    """After a merge, the response should include a guidance banner."""

    def test_unnamed_merge_shows_grouped_message(self, client, auth_disabled):
        """Merging an unnamed identity shows 'Grouped' with 'Add a name' CTA."""
        target = _make_identity("target-111", state="PROPOSED", anchor_ids=["face-a"])
        source = _make_identity("source-222", state="INBOX", anchor_ids=["face-b"])
        registry = _make_registry([target, source])
        photo_reg = _make_photo_registry_mock()

        with (
            patch("app.main.load_registry", return_value=registry),
            patch("app.main.load_photo_registry", return_value=photo_reg),
            patch("app.main.save_registry"),
            patch("app.main.get_crop_files", return_value=set()),
            patch("app.main.resolve_face_image_url", return_value=None),
            patch("app.main._post_merge_suggestions", return_value=None),
            patch("app.main._merge_annotations"),
            patch("app.main.log_user_action"),
        ):
            resp = client.post("/api/identity/target-111/merge/source-222")
            assert resp.status_code == 200
            html = resp.text
            assert "Grouped" in html
            assert "Add a name" in html

    def test_named_merge_shows_merge_complete(self, client, auth_disabled):
        """Merging a named identity shows 'Merge complete' success message."""
        target = _make_identity("target-333", name="Leon Capeluto", state="CONFIRMED", anchor_ids=["face-a"])
        source = _make_identity("source-444", state="INBOX", anchor_ids=["face-b"])
        registry = _make_registry([target, source])
        photo_reg = _make_photo_registry_mock()

        with (
            patch("app.main.load_registry", return_value=registry),
            patch("app.main.load_photo_registry", return_value=photo_reg),
            patch("app.main.save_registry"),
            patch("app.main.get_crop_files", return_value=set()),
            patch("app.main.resolve_face_image_url", return_value=None),
            patch("app.main._post_merge_suggestions", return_value=None),
            patch("app.main._merge_annotations"),
            patch("app.main.log_user_action"),
        ):
            resp = client.post("/api/identity/target-333/merge/source-444")
            assert resp.status_code == 200
            html = resp.text
            assert "Merge complete" in html
            assert "Leon Capeluto" in html


# ---------------------------------------------------------------------------
# 3. Grouped badge for unnamed multi-face identities
# ---------------------------------------------------------------------------


class TestGroupedBadge:
    """Unnamed identities with >1 face should show a 'Grouped (N faces)' badge."""

    def test_unnamed_multi_face_shows_grouped_badge(self):
        """Unnamed identity with 3 faces shows 'Grouped (3 faces)' badge."""
        from app.main import identity_card
        from fastcore.xml import to_xml

        identity = _make_identity(
            "grouped-id-1",
            name="Unidentified Person 042",
            state="PROPOSED",
            anchor_ids=["face-a", "face-b", "face-c"],
        )
        crop_files = {"face-a.jpg", "face-b.jpg", "face-c.jpg"}

        with (
            patch("app.main.resolve_face_image_url", return_value="/static/crops/placeholder.jpg"),
            patch("app.main._face_to_photo_cache", {}),
            patch("app.main._photo_cache", {}),
            patch("app.main._build_caches"),
        ):
            card = identity_card(identity, crop_files)

        if card is None:
            pytest.skip("identity_card returned None (no face cards rendered)")

        html = to_xml(card)
        assert "Grouped (3 faces)" in html

    def test_named_identity_no_grouped_badge(self):
        """Named identity (even with multiple faces) does NOT show grouped badge."""
        from app.main import identity_card
        from fastcore.xml import to_xml

        identity = _make_identity(
            "named-id-1",
            name="Leon Capeluto",
            state="CONFIRMED",
            anchor_ids=["face-a", "face-b", "face-c"],
        )
        crop_files = {"face-a.jpg", "face-b.jpg", "face-c.jpg"}

        with (
            patch("app.main.resolve_face_image_url", return_value="/static/crops/placeholder.jpg"),
            patch("app.main._face_to_photo_cache", {}),
            patch("app.main._photo_cache", {}),
            patch("app.main._build_caches"),
        ):
            card = identity_card(identity, crop_files)

        if card is None:
            pytest.skip("identity_card returned None (no face cards rendered)")

        html = to_xml(card)
        assert "Grouped" not in html
