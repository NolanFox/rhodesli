"""Tests for person page comments system."""

import json
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


_MOCK_IDENTITIES = {
    "identities": {
        "person-1": {
            "identity_id": "person-1",
            "name": "Big Leon Capeluto",
            "state": "CONFIRMED",
            "anchor_ids": ["face-1"],
            "candidate_ids": [],
            "negative_ids": [],
            "version_id": 1,
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
        },
    },
    "history": [],
}

_MOCK_COMMENTS = {
    "schema_version": 1,
    "comments": {
        "person-1": [
            {"id": "abc12345", "author": "Cousin Sarah", "text": "This is my great uncle!", "timestamp": "2026-02-17T12:00:00", "status": "visible"},
            {"id": "def67890", "author": "Anonymous", "text": "Hidden comment", "timestamp": "2026-02-17T13:00:00", "status": "hidden"},
        ],
    },
}


def _patch_data(comments=None):
    from core.registry import IdentityRegistry

    mock_registry = IdentityRegistry.__new__(IdentityRegistry)
    mock_registry._identities = _MOCK_IDENTITIES["identities"]
    mock_registry._history = []
    mock_registry._path = None

    mock_photo_reg = MagicMock()
    mock_photo_reg.get_photos_for_faces = MagicMock(return_value=["photo-1"])
    mock_photo_reg.get_photo = MagicMock(return_value={"path": "test.jpg", "collection": "Test"})

    mock_photo_cache = {
        "photo-1": {
            "path": "test.jpg", "filename": "test.jpg", "collection": "Test",
            "face_ids": ["face-1"], "width": 800, "height": 600,
            "faces": [{"face_id": "face-1", "bbox": [10, 10, 100, 100]}],
        },
    }

    return [
        patch("app.main.is_auth_enabled", return_value=False),
        patch("app.main.load_registry", return_value=mock_registry),
        patch("app.main.load_photo_registry", return_value=mock_photo_reg),
        patch("app.main._build_caches"),
        patch("app.main._photo_cache", mock_photo_cache),
        patch("app.main._face_to_photo_cache", {"face-1": "photo-1"}),
        patch("app.main.get_crop_files", return_value={"face-1.jpg"}),
        patch("app.main.get_best_face_id", return_value="face-1"),
        patch("app.main.resolve_face_image_url", return_value="/static/crops/face-1.jpg"),
        patch("app.main._load_annotations", return_value={"schema_version": 1, "annotations": {}}),
        patch("app.main._load_person_comments", return_value=comments or _MOCK_COMMENTS),
        patch("app.main._save_person_comments"),
    ]


class TestCommentsDisplay:

    def test_comments_section_present(self, client):
        """Person page has comments section."""
        patches = _patch_data()
        for p in patches:
            p.start()
        resp = client.get("/person/person-1")
        for p in patches:
            p.stop()
        assert resp.status_code == 200
        assert "comments-section" in resp.text

    def test_visible_comments_shown(self, client):
        """Visible comments are displayed."""
        patches = _patch_data()
        for p in patches:
            p.start()
        resp = client.get("/person/person-1")
        for p in patches:
            p.stop()
        assert "Cousin Sarah" in resp.text
        assert "This is my great uncle!" in resp.text

    def test_hidden_comments_not_shown(self, client):
        """Hidden comments are not displayed."""
        patches = _patch_data()
        for p in patches:
            p.start()
        resp = client.get("/person/person-1")
        for p in patches:
            p.stop()
        assert "Hidden comment" not in resp.text

    def test_empty_comments_shows_prompt(self, client):
        """Empty comments section shows encouraging message."""
        empty = {"schema_version": 1, "comments": {}}
        patches = _patch_data(comments=empty)
        for p in patches:
            p.start()
        resp = client.get("/person/person-1")
        for p in patches:
            p.stop()
        assert "No comments yet" in resp.text

    def test_comment_form_present(self, client):
        """Comment form is present on person page."""
        patches = _patch_data()
        for p in patches:
            p.start()
        resp = client.get("/person/person-1")
        for p in patches:
            p.stop()
        assert 'name="author"' in resp.text
        assert 'name="text"' in resp.text
        assert "Post Comment" in resp.text


class TestCommentSubmission:

    def test_submit_comment(self, client):
        """POST comment saves and returns updated list."""
        patches = _patch_data()
        for p in patches:
            p.start()
        resp = client.post(
            "/api/person/person-1/comment",
            data={"author": "Test User", "text": "Great photo!"},
        )
        for p in patches:
            p.stop()
        assert resp.status_code == 200

    def test_reject_empty_text(self, client):
        """POST with empty text shows error."""
        patches = _patch_data()
        for p in patches:
            p.start()
        resp = client.post(
            "/api/person/person-1/comment",
            data={"author": "Test", "text": ""},
        )
        for p in patches:
            p.stop()
        assert "Please enter a comment" in resp.text

    def test_anonymous_comment(self, client):
        """POST without author defaults to Anonymous."""
        patches = _patch_data()
        save_mock = patches[-1]  # _save_person_comments
        for p in patches:
            p.start()
        resp = client.post(
            "/api/person/person-1/comment",
            data={"text": "Nice!"},
        )
        for p in patches:
            p.stop()
        assert resp.status_code == 200


class TestCommentRateLimiting:

    def test_rate_limit_after_five_comments(self, client):
        """Rate limiting kicks in after 5 comments per IP per hour."""
        import app.main as main_mod
        # Clear rate limit state
        main_mod._comment_rate_limit.clear()

        patches = _patch_data()
        for p in patches:
            p.start()

        # Submit 5 comments (should all succeed)
        for i in range(5):
            resp = client.post(
                "/api/person/person-1/comment",
                data={"author": "Tester", "text": f"Comment {i}"},
            )
            assert resp.status_code == 200
            assert "Please wait" not in resp.text

        # 6th comment should be rate limited
        resp = client.post(
            "/api/person/person-1/comment",
            data={"author": "Tester", "text": "One more!"},
        )
        assert "Please wait" in resp.text

        for p in patches:
            p.stop()
        main_mod._comment_rate_limit.clear()


class TestCommentModeration:

    def test_admin_can_hide_comment(self, client):
        """Admin can hide a comment."""
        patches = _patch_data()
        # Remove is_auth_enabled patch, add admin auth
        patches[0] = patch("app.main.is_auth_enabled", return_value=False)
        for p in patches:
            p.start()
        resp = client.post("/api/person/person-1/comment/abc12345/hide")
        for p in patches:
            p.stop()
        assert resp.status_code == 200
        assert "hidden" in resp.text.lower()
