"""Tests for /identify pages — shareable identification crowdsourcing."""

import json
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


# Mock data — one confirmed identity and two unidentified
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


def _patch_data(responses=None):
    """Return patches for identify page tests.

    Args:
        responses: Optional list of identification responses to pre-populate.
    """
    from core.registry import IdentityRegistry

    mock_registry = IdentityRegistry.__new__(IdentityRegistry)
    mock_registry._identities = _MOCK_IDENTITIES["identities"]
    mock_registry._history = []
    mock_registry._path = None

    mock_photo_reg = MagicMock()
    mock_photo_reg.get_photos_for_faces = MagicMock(return_value=["photo-1"])
    mock_photo_reg.get_photo = MagicMock(return_value={"path": "test.jpg", "collection": "Test"})

    resp_data = {"schema_version": 1, "responses": responses or []}

    return [
        patch("app.main.is_auth_enabled", return_value=False),
        patch("app.main.load_registry", return_value=mock_registry),
        patch("app.main.load_photo_registry", return_value=mock_photo_reg),
        patch("app.main._build_caches"),
        patch("app.main.get_crop_files", return_value={"face-u1.jpg", "face-u2.jpg", "face-c1.jpg"}),
        patch("app.main.get_best_face_id", return_value="face-u1"),
        patch("app.main.resolve_face_image_url", return_value="/static/crops/face-u1.jpg"),
        patch("app.main.get_photo_id_for_face", return_value="photo-1"),
        patch("app.main.get_photo_metadata", return_value={
            "filename": "test.jpg", "collection": "Test Collection",
            "width": 800, "height": 600, "faces": [
                {"face_id": "face-u1", "bbox": [100, 100, 200, 200]},
            ],
        }),
        patch("app.main._get_date_badge", return_value=("c. 1950s", "medium", "Estimated: 1950s")),
        patch("app.main._load_identification_responses", return_value=resp_data),
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
        """MC-1/MC-2: GET /identify/{a}/match/{b} shows two faces side by side."""
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

    def test_shows_source_photos(self, client):
        """MC-3: Match page shows source photos section."""
        patches = _patch_data()
        for p in patches:
            p.start()
        resp = client.get("/identify/unknown-1/match/unknown-2")
        for p in patches:
            p.stop()
        assert "Source Photos" in resp.text

    def test_shows_face_highlight_on_source_photo(self, client):
        """MC-3: Source photo has face bbox overlay for highlighting."""
        patches = _patch_data()
        for p in patches:
            p.start()
        resp = client.get("/identify/unknown-1/match/unknown-2")
        for p in patches:
            p.stop()
        # Bbox overlay should have percentage-based positioning
        assert "border-amber-400" in resp.text

    def test_shows_collection_metadata(self, client):
        """MC-3: Match page shows collection and date metadata."""
        patches = _patch_data()
        for p in patches:
            p.start()
        resp = client.get("/identify/unknown-1/match/unknown-2")
        for p in patches:
            p.stop()
        assert "Test Collection" in resp.text
        assert "c. 1950s" in resp.text

    def test_has_og_tags(self, client):
        """MC-4: Match page has Open Graph tags with correct image URL."""
        patches = _patch_data()
        for p in patches:
            p.start()
        resp = client.get("/identify/unknown-1/match/unknown-2")
        for p in patches:
            p.stop()
        assert "og:title" in resp.text
        assert "og:image" in resp.text
        assert "og:url" in resp.text
        assert "Are these the same person?" in resp.text
        # OG image should be absolute URL
        assert "rhodesli.nolanandrewfox.com" in resp.text

    def test_has_responder_name_and_note_fields(self, client):
        """MC-5: Match page has optional name and note input fields."""
        patches = _patch_data()
        for p in patches:
            p.start()
        resp = client.get("/identify/unknown-1/match/unknown-2")
        for p in patches:
            p.stop()
        assert 'name="responder_name"' in resp.text
        assert 'name="responder_note"' in resp.text
        assert "Your name" in resp.text
        assert "How do you know" in resp.text

    def test_match_response_yes(self, client):
        """MC-5: POST yes response saves confirmation."""
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

    def test_match_response_saves_name_and_note(self, client):
        """MC-6: Response includes responder name and note."""
        saved_data = {}

        def capture_save(data):
            saved_data.update(data)

        patches = _patch_data()
        for p in patches:
            p.start()
        # Override the save mock to capture data
        with patch("app.main._save_identification_responses", side_effect=capture_save):
            with patch("app.main._match_rate_limit", {}):
                resp = client.post(
                    "/api/identify/unknown-1/match/unknown-2/respond",
                    data={
                        "answer": "yes",
                        "responder_name": "Cousin Sarah",
                        "responder_note": "That's definitely Uncle Marco",
                    },
                )
        for p in patches:
            p.stop()
        assert resp.status_code == 200
        # Check saved data has name and note
        last_response = saved_data["responses"][-1]
        assert last_response["responder_name"] == "Cousin Sarah"
        assert last_response["responder_note"] == "That's definitely Uncle Marco"
        assert last_response["answer"] == "yes"
        assert last_response["type"] == "match_confirmation"

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

    def test_match_share_button(self, client):
        """MC-7/MC-8: Match page has share button with correct URL."""
        patches = _patch_data()
        for p in patches:
            p.start()
        resp = client.get("/identify/unknown-1/match/unknown-2")
        for p in patches:
            p.stop()
        assert "share-photo" in resp.text
        assert "Share This Match" in resp.text
        assert "/identify/unknown-1/match/unknown-2" in resp.text

    def test_shows_response_count_when_responses_exist(self, client):
        """MC-9: Match page shows community response count."""
        existing_responses = [
            {"type": "match_confirmation", "person_a": "unknown-1", "person_b": "unknown-2",
             "answer": "yes", "timestamp": "2026-02-17T10:00:00", "status": "pending"},
            {"type": "match_confirmation", "person_a": "unknown-1", "person_b": "unknown-2",
             "answer": "yes", "timestamp": "2026-02-17T11:00:00", "status": "pending"},
            {"type": "match_confirmation", "person_a": "unknown-1", "person_b": "unknown-2",
             "answer": "unsure", "timestamp": "2026-02-17T12:00:00", "status": "pending"},
        ]
        patches = _patch_data(responses=existing_responses)
        for p in patches:
            p.start()
        resp = client.get("/identify/unknown-1/match/unknown-2")
        for p in patches:
            p.stop()
        assert "3 people have weighed in" in resp.text
        assert "2 Yes" in resp.text
        assert "1 Not Sure" in resp.text

    def test_response_count_checks_both_orderings(self, client):
        """MC-9: Response counts work regardless of person ordering in URL."""
        # Response stored with reversed ordering
        existing_responses = [
            {"type": "match_confirmation", "person_a": "unknown-2", "person_b": "unknown-1",
             "answer": "no", "timestamp": "2026-02-17T10:00:00", "status": "pending"},
        ]
        patches = _patch_data(responses=existing_responses)
        for p in patches:
            p.start()
        resp = client.get("/identify/unknown-1/match/unknown-2")
        for p in patches:
            p.stop()
        assert "1 person has weighed in" in resp.text

    def test_rate_limiting(self, client):
        """MC-10: Rate limiting blocks excessive responses from same IP."""
        patches = _patch_data()
        for p in patches:
            p.start()

        # Reset rate limit state
        with patch("app.main._match_rate_limit", {"testip_hash": []}):
            from datetime import datetime
            # Manually fill rate limit to simulate 10 responses
            import app.main as main_mod
            old_rl = main_mod._match_rate_limit
            main_mod._match_rate_limit = {}
            # Submit 10 responses to fill rate limit
            for i in range(10):
                resp = client.post(
                    "/api/identify/unknown-1/match/unknown-2/respond",
                    data={"answer": "yes"},
                )
                assert resp.status_code == 200

            # 11th should be rate limited
            resp = client.post(
                "/api/identify/unknown-1/match/unknown-2/respond",
                data={"answer": "yes"},
            )
            assert resp.status_code == 200
            assert "try again later" in resp.text.lower()

            # Restore
            main_mod._match_rate_limit = old_rl

        for p in patches:
            p.stop()

    def test_explore_archive_link(self, client):
        """Match page has a link to explore the archive."""
        patches = _patch_data()
        for p in patches:
            p.start()
        resp = client.get("/identify/unknown-1/match/unknown-2")
        for p in patches:
            p.stop()
        assert "Explore the Archive" in resp.text
        assert 'href="/photos"' in resp.text

    def test_displays_person_labels_not_unidentified(self, client):
        """Match page shows 'Person A/B' instead of 'Unidentified Person 42'."""
        patches = _patch_data()
        for p in patches:
            p.start()
        resp = client.get("/identify/unknown-1/match/unknown-2")
        for p in patches:
            p.stop()
        # Should NOT show "Unidentified Person 42" — should show "Person A" or "Person B"
        assert "Unidentified Person 42" not in resp.text
        assert "Person A" in resp.text or "Person B" in resp.text


class TestMatchResponseCounts:

    def test_get_match_response_counts_empty(self, client):
        """Counts are all zero with no responses."""
        from app.main import _get_match_response_counts
        with patch("app.main._load_identification_responses",
                   return_value={"schema_version": 1, "responses": []}):
            counts = _get_match_response_counts("a", "b")
        assert counts == {"yes": 0, "no": 0, "unsure": 0, "total": 0}

    def test_get_match_response_counts_with_data(self, client):
        """Counts correctly tally responses for a pair."""
        from app.main import _get_match_response_counts
        responses = [
            {"type": "match_confirmation", "person_a": "a", "person_b": "b", "answer": "yes"},
            {"type": "match_confirmation", "person_a": "a", "person_b": "b", "answer": "yes"},
            {"type": "match_confirmation", "person_a": "b", "person_b": "a", "answer": "no"},
            {"type": "match_confirmation", "person_a": "a", "person_b": "b", "answer": "unsure"},
            # Different pair — should not be counted
            {"type": "match_confirmation", "person_a": "c", "person_b": "d", "answer": "yes"},
            # Different type — should not be counted
            {"type": "identification", "person_id": "a", "name": "Test"},
        ]
        with patch("app.main._load_identification_responses",
                   return_value={"schema_version": 1, "responses": responses}):
            counts = _get_match_response_counts("a", "b")
        assert counts["yes"] == 2
        assert counts["no"] == 1
        assert counts["unsure"] == 1
        assert counts["total"] == 4

    def test_community_summary_returns_none_with_no_responses(self, client):
        """Community summary is None when no responses exist."""
        from app.main import _match_community_summary
        with patch("app.main._load_identification_responses",
                   return_value={"schema_version": 1, "responses": []}):
            result = _match_community_summary("a", "b")
        assert result is None
