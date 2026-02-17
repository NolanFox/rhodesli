"""Tests for /identify pages — shareable identification crowdsourcing."""

import json
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


# Mock data — one confirmed identity and one unidentified
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
        "unknown-2": {
            "identity_id": "unknown-2",
            "name": "Unidentified Person 43",
            "state": "PROPOSED",
            "anchor_ids": ["face-u2"],
            "candidate_ids": [],
            "negative_ids": [],
            "version_id": 1,
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
        },
    },
    "history": [],
}


def _patch_data():
    """Return patches for identify page tests."""
    from core.registry import IdentityRegistry

    mock_registry = IdentityRegistry.__new__(IdentityRegistry)
    mock_registry._identities = _MOCK_IDENTITIES["identities"]
    mock_registry._history = []
    mock_registry._path = None

    mock_photo_reg = MagicMock()
    mock_photo_reg.get_photos_for_faces = MagicMock(return_value=["photo-1"])
    mock_photo_reg.get_photo = MagicMock(return_value={"path": "test.jpg", "collection": "Test"})

    return [
        patch("app.main.is_auth_enabled", return_value=False),
        patch("app.main.load_registry", return_value=mock_registry),
        patch("app.main.load_photo_registry", return_value=mock_photo_reg),
        patch("app.main._build_caches"),
        patch("app.main.get_crop_files", return_value={"face-u1.jpg", "face-u2.jpg", "face-c1.jpg"}),
        patch("app.main.get_best_face_id", return_value="face-u1"),
        patch("app.main.resolve_face_image_url", return_value="/static/crops/face-u1.jpg"),
        patch("app.main._load_identification_responses", return_value={"schema_version": 1, "responses": []}),
        patch("app.main._save_identification_responses"),
    ]


class TestIdentifyPage:

    def test_renders_for_unidentified_person(self, client):
        """GET /identify/{id} returns 200 for unidentified person."""
        patches = _patch_data()
        for p in patches:
            p.start()
        resp = client.get("/identify/unknown-1")
        for p in patches:
            p.stop()
        assert resp.status_code == 200
        assert "Can you identify this person?" in resp.text

    def test_has_og_tags(self, client):
        """Page has Open Graph tags with face image."""
        patches = _patch_data()
        for p in patches:
            p.start()
        resp = client.get("/identify/unknown-1")
        for p in patches:
            p.stop()
        assert "og:title" in resp.text
        assert "og:image" in resp.text
        assert "Can you identify this person?" in resp.text

    def test_has_response_form(self, client):
        """Page has a name/relationship/email form."""
        patches = _patch_data()
        for p in patches:
            p.start()
        resp = client.get("/identify/unknown-1")
        for p in patches:
            p.stop()
        assert 'name="name"' in resp.text
        assert 'name="relationship"' in resp.text
        assert 'name="email"' in resp.text
        assert "Yes, I know this person!" in resp.text

    def test_redirects_for_identified_person(self, client):
        """GET /identify/{id} redirects to /person/{id} for confirmed identity."""
        patches = _patch_data()
        for p in patches:
            p.start()
        resp = client.get("/identify/confirmed-1", follow_redirects=False)
        for p in patches:
            p.stop()
        assert resp.status_code == 303
        assert "/person/confirmed-1" in resp.headers["location"]

    def test_404_for_nonexistent(self, client):
        """GET /identify/{invalid} shows not found."""
        patches = _patch_data()
        for p in patches:
            p.start()
        resp = client.get("/identify/nonexistent-id")
        for p in patches:
            p.stop()
        assert resp.status_code == 200
        assert "not found" in resp.text.lower()

    def test_has_share_button(self, client):
        """Page has a share button for crowdsourcing."""
        patches = _patch_data()
        for p in patches:
            p.start()
        resp = client.get("/identify/unknown-1")
        for p in patches:
            p.stop()
        assert "share-photo" in resp.text
        assert "Share to help identify" in resp.text


class TestIdentifyResponse:

    def test_submit_identification(self, client):
        """POST response saves identification for admin review."""
        patches = _patch_data()
        for p in patches:
            p.start()
        resp = client.post(
            "/api/identify/unknown-1/respond",
            data={"name": "Sarah Capeluto", "relationship": "My grandmother", "email": "test@example.com"},
        )
        for p in patches:
            p.stop()
        assert resp.status_code == 200
        assert "Thank you" in resp.text
        assert "Sarah Capeluto" in resp.text

    def test_reject_empty_name(self, client):
        """POST with empty name shows error."""
        patches = _patch_data()
        for p in patches:
            p.start()
        resp = client.post(
            "/api/identify/unknown-1/respond",
            data={"name": "", "relationship": ""},
        )
        for p in patches:
            p.stop()
        assert resp.status_code == 200
        assert "Please enter a name" in resp.text


class TestMatchConfirmation:

    def test_renders_side_by_side(self, client):
        """GET /identify/{a}/match/{b} shows two faces side by side."""
        patches = _patch_data()
        for p in patches:
            p.start()
        resp = client.get("/identify/unknown-1/match/unknown-2")
        for p in patches:
            p.stop()
        assert resp.status_code == 200
        assert "Are these the same person?" in resp.text
        assert "Yes, Same Person" in resp.text
        assert "No, Different People" in resp.text
        assert "Not Sure" in resp.text

    def test_has_og_tags(self, client):
        """Match page has Open Graph tags."""
        patches = _patch_data()
        for p in patches:
            p.start()
        resp = client.get("/identify/unknown-1/match/unknown-2")
        for p in patches:
            p.stop()
        assert "og:title" in resp.text
        assert "Are these the same person?" in resp.text

    def test_match_response_yes(self, client):
        """POST yes response saves confirmation."""
        patches = _patch_data()
        for p in patches:
            p.start()
        resp = client.post(
            "/api/identify/unknown-1/match/unknown-2/respond",
            data={"answer": "yes"},
        )
        for p in patches:
            p.stop()
        assert resp.status_code == 200
        assert "confirmed" in resp.text.lower() or "same person" in resp.text.lower()

    def test_match_response_no(self, client):
        """POST no response saves rejection."""
        patches = _patch_data()
        for p in patches:
            p.start()
        resp = client.post(
            "/api/identify/unknown-1/match/unknown-2/respond",
            data={"answer": "no"},
        )
        for p in patches:
            p.stop()
        assert resp.status_code == 200
        assert "different" in resp.text.lower()

    def test_match_response_unsure(self, client):
        """POST unsure response is accepted."""
        patches = _patch_data()
        for p in patches:
            p.start()
        resp = client.post(
            "/api/identify/unknown-1/match/unknown-2/respond",
            data={"answer": "unsure"},
        )
        for p in patches:
            p.stop()
        assert resp.status_code == 200
        assert "Thank you" in resp.text

    def test_match_invalid_response(self, client):
        """POST invalid answer shows error."""
        patches = _patch_data()
        for p in patches:
            p.start()
        resp = client.post(
            "/api/identify/unknown-1/match/unknown-2/respond",
            data={"answer": "maybe"},
        )
        for p in patches:
            p.stop()
        assert resp.status_code == 200
        assert "Invalid" in resp.text

    def test_match_nonexistent_person(self, client):
        """GET with nonexistent person shows not found."""
        patches = _patch_data()
        for p in patches:
            p.start()
        resp = client.get("/identify/unknown-1/match/nonexistent")
        for p in patches:
            p.stop()
        assert resp.status_code == 200
        assert "not found" in resp.text.lower()
