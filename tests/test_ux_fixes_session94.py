"""Tests for Session 94 Track A: UX-042 and UX-134 fixes."""

from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Mock data for identify page tests
# ---------------------------------------------------------------------------

_MOCK_IDENTITIES = {
    "identities": {
        "unknown-1": {
            "identity_id": "unknown-1",
            "name": "Unidentified Person 42",
            "state": "INBOX",
            "anchor_ids": ["face-u1", "face-u2"],
            "candidate_ids": [],
            "negative_ids": [],
            "version_id": 1,
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
        },
    },
    "history": [],
}


def _patch_identify():
    """Patches for identify page tests with multiple faces."""
    from core.registry import IdentityRegistry

    mock_registry = IdentityRegistry.__new__(IdentityRegistry)
    mock_registry._identities = _MOCK_IDENTITIES["identities"]
    mock_registry._history = []
    mock_registry._path = None

    mock_photo_reg = MagicMock()
    mock_photo_reg.get_photos_for_faces = MagicMock(return_value=["photo-abc123", "photo-def456"])
    mock_photo_reg._photos = {}

    def _mock_get_photo_id_for_face(fid):
        if fid == "face-u1":
            return "photo-abc123"
        elif fid == "face-u2":
            return "photo-def456"
        return None

    def _mock_resolve(fid, crops):
        return f"/static/crops/{fid}.jpg" if crops else None

    return [
        patch("app.main.is_auth_enabled", return_value=False),
        patch("app.main.load_registry", return_value=mock_registry),
        patch("app.main.load_photo_registry", return_value=mock_photo_reg),
        patch("app.main._build_caches"),
        patch(
            "app.main._photo_cache",
            {
                "photo-abc123": {"path": "test1.jpg", "collection": "Test Collection A"},
                "photo-def456": {"path": "test2.jpg", "collection": "Test Collection B"},
            },
        ),
        patch("app.main.get_crop_files", return_value={"face-u1.jpg", "face-u2.jpg"}),
        patch("app.main.get_best_face_id", return_value="face-u1"),
        patch("app.main.resolve_face_image_url", side_effect=_mock_resolve),
        patch("app.main._load_identification_responses", return_value={"schema_version": 1, "responses": []}),
        patch("app.main.get_photo_id_for_face", side_effect=_mock_get_photo_id_for_face),
    ]


# ---------------------------------------------------------------------------
# UX-042: Shareable identity page source photo links
# ---------------------------------------------------------------------------


class TestUX042SourcePhotoLinks:
    """UX-042: Each face on the identify page should link to its source photo."""

    def test_identify_page_has_source_photo_cards(self, client):
        """Identity page shows source photo cards with links."""
        patches = _patch_identify()
        for p in patches:
            p.start()
        try:
            resp = client.get("/identify/unknown-1")
            assert resp.status_code == 200
            # Should have source photo card test IDs
            assert "source-photo-card" in resp.text
            # Should link to both source photos
            assert "/photo/photo-abc123" in resp.text
            assert "/photo/photo-def456" in resp.text
        finally:
            for p in patches:
                p.stop()

    def test_identify_page_has_source_photos_section(self, client):
        """Identity page has the source photos section with test ID."""
        patches = _patch_identify()
        for p in patches:
            p.start()
        try:
            resp = client.get("/identify/unknown-1")
            assert resp.status_code == 200
            assert "source-photos-section" in resp.text
            assert "Appears in these photos" in resp.text
        finally:
            for p in patches:
                p.stop()

    def test_identify_page_shows_collection_labels(self, client):
        """Source photo cards show collection labels."""
        patches = _patch_identify()
        for p in patches:
            p.start()
        try:
            resp = client.get("/identify/unknown-1")
            assert resp.status_code == 200
            assert "Test Collection A" in resp.text
            assert "Test Collection B" in resp.text
        finally:
            for p in patches:
                p.stop()

    def test_identify_page_still_has_view_source_photo_link(self, client):
        """The main 'View source photo' link is still present."""
        patches = _patch_identify()
        for p in patches:
            p.start()
        try:
            resp = client.get("/identify/unknown-1")
            assert resp.status_code == 200
            assert "view-source-photo-link" in resp.text
        finally:
            for p in patches:
                p.stop()


# ---------------------------------------------------------------------------
# UX-134: Mobile landing page horizontal overflow
# ---------------------------------------------------------------------------


class TestUX134MobileLandingOverflow:
    """UX-134: Landing page should not overflow horizontally on mobile."""

    def test_landing_page_has_overflow_hidden(self, client):
        """Landing page container has overflow-x: hidden CSS."""
        with (
            patch("app.main.is_auth_enabled", return_value=False),
            patch("app.main.get_current_user", return_value=None),
        ):
            resp = client.get("/")
            assert resp.status_code == 200
            assert "landing-container" in resp.text
            assert "overflow-x: hidden" in resp.text

    def test_landing_page_has_box_sizing(self, client):
        """Landing page sets box-sizing: border-box on all children."""
        with (
            patch("app.main.is_auth_enabled", return_value=False),
            patch("app.main.get_current_user", return_value=None),
        ):
            resp = client.get("/")
            assert resp.status_code == 200
            assert "box-sizing: border-box" in resp.text

    def test_landing_page_images_max_width(self, client):
        """Landing page images have max-width: 100% to prevent overflow."""
        with (
            patch("app.main.is_auth_enabled", return_value=False),
            patch("app.main.get_current_user", return_value=None),
        ):
            resp = client.get("/")
            assert resp.status_code == 200
            assert "max-width: 100%" in resp.text

    def test_landing_page_max_viewport_width(self, client):
        """Landing page container has max-width: 100vw."""
        with (
            patch("app.main.is_auth_enabled", return_value=False),
            patch("app.main.get_current_user", return_value=None),
        ):
            resp = client.get("/")
            assert resp.status_code == 200
            assert "max-width: 100vw" in resp.text
