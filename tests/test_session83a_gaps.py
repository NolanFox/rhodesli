"""Tests for Session 83a continuation — 5 UX gaps from user feedback.

Gap 1: Unidentified person contextual explanation
Gap 2: Bidirectional admin/public links
Gap 3: Face card consistency across views
Gap 4: Compare discoverability CTAs
Gap 5: Help Identify submission persistence
"""

import json
from unittest.mock import MagicMock, patch
from contextlib import ExitStack

import pytest
from starlette.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


# --- Shared mock data ---

_MOCK_IDENTITIES = {
    "identities": {
        "confirmed-1": {
            "identity_id": "confirmed-1",
            "name": "Big Leon Capeluto",
            "state": "CONFIRMED",
            "anchor_ids": ["face-c1"],
            "candidate_ids": [],
            "negative_ids": [],
            "version_id": 1,
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
        },
        "unknown-1": {
            "identity_id": "unknown-1",
            "name": "Unidentified Person 42",
            "state": "INBOX",
            "anchor_ids": ["face-u1"],
            "candidate_ids": [],
            "negative_ids": [],
            "version_id": 1,
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
        },
        "proposed-1": {
            "identity_id": "proposed-1",
            "name": "Unidentified Person 43",
            "state": "PROPOSED",
            "anchor_ids": ["face-p1"],
            "candidate_ids": [],
            "negative_ids": [],
            "version_id": 1,
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
        },
    },
    "history": [],
}


def _base_patches():
    """Return common patches for person/identify page tests."""
    from core.registry import IdentityRegistry

    mock_registry = IdentityRegistry.__new__(IdentityRegistry)
    mock_registry._identities = _MOCK_IDENTITIES["identities"]
    mock_registry._history = []
    mock_registry._path = None

    mock_photo_reg = MagicMock()
    mock_photo_reg.get_photos_for_faces = MagicMock(return_value=["photo-1"])
    mock_photo_reg.get_photo = MagicMock(return_value={"path": "test.jpg", "collection": "Test"})
    mock_photo_reg._photos = {"photo-1": {"path": "test.jpg", "collection": "Test Collection"}}

    return [
        patch("app.main.is_auth_enabled", return_value=False),
        patch("app.main.load_registry", return_value=mock_registry),
        patch("app.main.load_photo_registry", return_value=mock_photo_reg),
        patch("app.main._build_caches"),
        patch("app.main.get_crop_files", return_value={"face-u1.jpg", "face-c1.jpg", "face-p1.jpg"}),
        patch("app.main.get_best_face_id", return_value="face-u1"),
        patch("app.main.resolve_face_image_url", return_value="/static/crops/face-u1.jpg"),
        patch("app.main.get_photo_id_for_face", return_value="photo-1"),
        patch("app.main.get_photo_metadata", return_value={
            "filename": "test.jpg", "collection": "Test Collection",
            "width": 800, "height": 600,
            "faces": [{"face_id": "face-u1", "bbox": [100, 100, 200, 200]}],
        }),
        patch("app.main._get_date_badge", return_value=("c. 1950s", "medium", "Estimated: 1950s")),
        patch("app.main._load_identification_responses", return_value={"schema_version": 1, "responses": []}),
        patch("app.main._save_identification_responses"),
        patch("app.main._photo_cache", {"photo-1": {"path": "test.jpg", "collection": "Test Collection"}}),
        patch("app.main._face_to_photo_cache", {"face-u1": "photo-1", "face-c1": "photo-1", "face-p1": "photo-1"}),
        patch("app.main.get_identity_for_face", return_value=None),
        patch("app.main._load_date_labels", return_value={}),
        patch("app.main._get_birth_year", return_value=(None, None, None)),
    ]


# ============================================================
# Gap 1: Unidentified Person contextual explanation
# ============================================================

class TestGap1UnidentifiedExplanation:
    """Explanation text appears for unidentified persons, not for confirmed."""

    def test_person_page_shows_explanation_for_inbox(self, client):
        with ExitStack() as stack:
            for p in _base_patches():
                stack.enter_context(p)
            resp = client.get("/person/unknown-1")
        assert resp.status_code == 200
        body = resp.text
        assert "hasn&#x27;t been identified yet" in body or "hasn't been identified yet" in body
        assert "unidentified-explanation" in body

    def test_person_page_shows_explanation_for_proposed(self, client):
        with ExitStack() as stack:
            for p in _base_patches():
                stack.enter_context(p)
            resp = client.get("/person/proposed-1")
        assert resp.status_code == 200
        body = resp.text
        assert "unidentified-explanation" in body

    def test_person_page_no_explanation_for_confirmed(self, client):
        with ExitStack() as stack:
            for p in _base_patches():
                stack.enter_context(p)
            resp = client.get("/person/confirmed-1")
        assert resp.status_code == 200
        assert "unidentified-explanation" not in resp.text

    def test_identify_page_shows_ai_note(self, client):
        with ExitStack() as stack:
            for p in _base_patches():
                stack.enter_context(p)
            resp = client.get("/identify/unknown-1")
        assert resp.status_code == 200
        assert "identify-ai-note" in resp.text


# ============================================================
# Gap 2: Bidirectional admin/public links
# ============================================================

class TestGap2BidirectionalLinks:
    """Admin sees Edit in Admin on person page; Focus view has View Public Page."""

    def test_person_page_admin_sees_edit_in_admin(self, client):
        """Admin user sees 'Edit in Admin' link on person page."""
        with ExitStack() as stack:
            for p in _base_patches():
                stack.enter_context(p)
            resp = client.get("/person/unknown-1")
        # Auth disabled = admin, so Edit in Admin should appear
        assert resp.status_code == 200
        assert "Edit in Admin" in resp.text or "View in Admin" in resp.text

    def test_identify_page_admin_sees_admin_link(self, client):
        """Admin user sees admin link on identify page."""
        from app.auth import User
        admin_user = User(id="test", email="admin@test.com", is_admin=True)
        with ExitStack() as stack:
            for p in _base_patches():
                stack.enter_context(p)
            stack.enter_context(patch("app.main.is_auth_enabled", return_value=True))
            stack.enter_context(patch("app.main.get_current_user", return_value=admin_user))
            resp = client.get("/identify/unknown-1")
        assert resp.status_code == 200
        assert "View in Admin" in resp.text


# ============================================================
# Gap 3: Face card consistency across views
# ============================================================

class TestGap3FaceCardConsistency:
    """Face cards across views have consistent core actions."""

    def test_help_page_cards_have_similar_and_profile_links(self, client):
        """Help page face cards have Similar and Profile links."""
        with ExitStack() as stack:
            for p in _base_patches():
                stack.enter_context(p)
            stack.enter_context(patch("app.main.get_face_quality", return_value=0.9))
            resp = client.get("/help")
        assert resp.status_code == 200
        body = resp.text
        # Help page renders cards for unidentified people with Similar + Profile links
        assert "Similar" in body or "/similar" in body
        assert "Profile" in body or "/person/" in body

    def test_identity_card_profile_link_for_inbox(self, client):
        """Identity card in People section shows Profile link for INBOX state."""
        with ExitStack() as stack:
            for p in _base_patches():
                stack.enter_context(p)
            # The identity_card function is used on the People page; test via person page
            # which includes a Profile link for all states
            resp = client.get("/person/unknown-1")
        assert resp.status_code == 200
        assert "/person/unknown-1" in resp.text

    def test_focus_view_has_public_page_link(self):
        """Focus view's identity_card_expanded includes View Public Page link."""
        from app.main import identity_card_expanded

        with ExitStack() as stack:
            for p in _base_patches():
                stack.enter_context(p)
            html = repr(identity_card_expanded(
                identity=_MOCK_IDENTITIES["identities"]["unknown-1"],
                crop_files={"face-u1.jpg"},
            ))
        assert "View Public Page" in html
        assert "/person/unknown-1" in html


# ============================================================
# Gap 4: Compare discoverability CTAs
# ============================================================

class TestGap4CompareDiscoverability:
    """Compare CTAs appear on person page and identify page."""

    def test_person_page_has_compare_cta(self, client):
        with ExitStack() as stack:
            for p in _base_patches():
                stack.enter_context(p)
            resp = client.get("/person/unknown-1")
        assert resp.status_code == 200
        assert "/compare" in resp.text or "/facecompare" in resp.text

    def test_identify_page_has_compare_suggestion(self, client):
        with ExitStack() as stack:
            for p in _base_patches():
                stack.enter_context(p)
            resp = client.get("/identify/unknown-1")
        assert resp.status_code == 200
        assert "Compare" in resp.text or "compare" in resp.text


# ============================================================
# Gap 5: Help Identify submission persistence
# ============================================================

class TestGap5SubmissionPersistence:
    """Submission success state survives page refresh via query param."""

    def test_identify_page_shows_success_banner_with_query_param(self, client):
        with ExitStack() as stack:
            for p in _base_patches():
                stack.enter_context(p)
            resp = client.get("/identify/unknown-1?submitted=true&name=Isaac+Cohen")
        assert resp.status_code == 200
        body = resp.text
        assert "Isaac Cohen" in body or "Isaac+Cohen" in body
        assert "submitted" in body.lower() or "thank" in body.lower()

    def test_identify_page_no_banner_without_query_param(self, client):
        with ExitStack() as stack:
            for p in _base_patches():
                stack.enter_context(p)
            resp = client.get("/identify/unknown-1")
        assert resp.status_code == 200
        assert "submission-success-banner" not in resp.text
