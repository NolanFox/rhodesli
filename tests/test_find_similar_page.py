"""Tests for /people/{id}/similar — full-page Find Similar layout."""

from unittest.mock import patch, MagicMock

import pytest


_TEST_IDENTITIES = {
    "identities": {
        "id-leon": {
            "identity_id": "id-leon", "name": "Big Leon Capeluto", "state": "CONFIRMED",
            "anchor_ids": ["face-leon1", "face-leon2"], "candidate_ids": [],
            "metadata": {"gender": "M"}, "version_id": 1,
            "created_at": "2025-01-01T00:00:00Z", "updated_at": "2025-01-01T00:00:00Z",
        },
        "id-nace": {
            "identity_id": "id-nace", "name": "Nace Capeluto", "state": "CONFIRMED",
            "anchor_ids": ["face-nace1"], "candidate_ids": [],
            "metadata": {"gender": "M"}, "version_id": 1,
            "created_at": "2025-01-01T00:00:00Z", "updated_at": "2025-01-01T00:00:00Z",
        },
    }
}


@pytest.fixture
def mock_similar_data():
    mock_reg = MagicMock()
    mock_reg.list_identities.return_value = list(_TEST_IDENTITIES["identities"].values())

    def mock_get(pid):
        ident = _TEST_IDENTITIES["identities"].get(pid)
        if not ident:
            raise KeyError(pid)
        return ident

    mock_reg.get_identity = mock_get

    mock_neighbors = [
        {"identity_id": "id-nace", "distance": 0.95, "can_merge": True, "merge_blocked_reason": ""},
    ]

    with patch("app.main.is_auth_enabled", return_value=False), \
         patch("app.main.load_registry", return_value=mock_reg), \
         patch("app.main.get_crop_files", return_value={"face-leon1.jpg", "face-nace1.jpg"}), \
         patch("app.main.resolve_face_image_url", return_value="/static/crops/face.jpg"), \
         patch("app.main.get_best_face_id", return_value="face-leon1"), \
         patch("app.main.get_face_data", return_value={}), \
         patch("app.main.load_photo_registry", return_value=MagicMock()), \
         patch("core.neighbors.find_nearest_neighbors", return_value=mock_neighbors):
        yield


class TestFindSimilarPage:
    def test_returns_200(self, client, mock_similar_data):
        resp = client.get("/people/id-leon/similar")
        assert resp.status_code == 200

    def test_shows_hero_name(self, client, mock_similar_data):
        resp = client.get("/people/id-leon/similar")
        assert "Big Leon Capeluto" in resp.text

    def test_shows_back_link(self, client, mock_similar_data):
        resp = client.get("/people/id-leon/similar")
        assert "Back to People" in resp.text

    def test_shows_similar_results(self, client, mock_similar_data):
        resp = client.get("/people/id-leon/similar")
        assert "Similar Face" in resp.text

    def test_shows_confidence_tier(self, client, mock_similar_data):
        resp = client.get("/people/id-leon/similar")
        # 0.95 distance = High confidence tier
        assert "High" in resp.text

    def test_404_for_unknown(self, client, mock_similar_data):
        resp = client.get("/people/unknown-id/similar")
        assert resp.status_code == 404

    def test_has_view_profile_link(self, client, mock_similar_data):
        resp = client.get("/people/id-leon/similar")
        assert "View Profile" in resp.text

    def test_responsive_grid(self, client, mock_similar_data):
        resp = client.get("/people/id-leon/similar")
        assert "similar-grid" in resp.text
