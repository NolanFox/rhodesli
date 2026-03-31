"""Tests for /people/{id}/similar — full-page Find Similar layout."""

from unittest.mock import patch, MagicMock

import pytest


_TEST_IDENTITIES = {
    "identities": {
        "id-leon": {
            "identity_id": "id-leon",
            "name": "Big Leon Capeluto",
            "state": "CONFIRMED",
            "anchor_ids": ["face-leon1", "face-leon2"],
            "candidate_ids": [],
            "metadata": {"gender": "M"},
            "version_id": 1,
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
        },
        "id-nace": {
            "identity_id": "id-nace",
            "name": "Nace Capeluto",
            "state": "CONFIRMED",
            "anchor_ids": ["face-nace1"],
            "candidate_ids": [],
            "metadata": {"gender": "M"},
            "version_id": 1,
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
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

    with (
        patch("app.main.is_auth_enabled", return_value=False),
        patch("app.main.load_registry", return_value=mock_reg),
        patch("app.main.get_crop_files", return_value={"face-leon1.jpg", "face-nace1.jpg"}),
        patch("app.main.resolve_face_image_url", return_value="/static/crops/face.jpg"),
        patch("app.main.get_best_face_id", return_value="face-leon1"),
        patch("app.main.get_face_data", return_value={}),
        patch("app.main.load_photo_registry", return_value=MagicMock()),
        patch("core.neighbors.find_nearest_neighbors", return_value=mock_neighbors),
    ):
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
        assert "Back to Profile" in resp.text
        assert "All People" in resp.text

    def test_shows_similar_results(self, client, mock_similar_data):
        resp = client.get("/people/id-leon/similar")
        assert "Similar Face" in resp.text

    def test_shows_confidence_tier(self, client, mock_similar_data):
        resp = client.get("/people/id-leon/similar")
        # 0.95 distance = Moderate tier under unified scoring (AD-200)
        assert "Moderate" in resp.text

    def test_404_for_unknown(self, client, mock_similar_data):
        resp = client.get("/people/unknown-id/similar")
        assert resp.status_code == 404

    def test_has_view_profile_link(self, client, mock_similar_data):
        resp = client.get("/people/id-leon/similar")
        assert "View Profile" in resp.text

    def test_responsive_grid(self, client, mock_similar_data):
        resp = client.get("/people/id-leon/similar")
        assert "similar-grid" in resp.text

    def test_share_button_on_similar_page(self, client, mock_similar_data):
        """Share button should appear on similar page for confirmed, named identities."""
        resp = client.get("/people/id-leon/similar")
        assert "share-photo" in resp.text
        assert "Jews of Rhodes Heritage Archive" in resp.text

    def test_confidence_tier_colors(self, client, mock_similar_data):
        """Moderate confidence tier (0.95 distance) should use amber color (AD-200)."""
        resp = client.get("/people/id-leon/similar")
        assert "bg-amber-500" in resp.text

    def test_back_to_profile_link_uses_person_route(self, client, mock_similar_data):
        """Back link should point to /person/{id}, not /people/{id}."""
        resp = client.get("/people/id-leon/similar")
        assert "/person/id-leon" in resp.text

    def test_share_script_included(self, client, mock_similar_data):
        """Standalone similar page should include share JS handler."""
        resp = client.get("/people/id-leon/similar")
        assert "_sharePhotoUrl" in resp.text

    def test_admin_actions_present_on_full_page(self, client, mock_similar_data):
        """Admin-capable similar page keeps Merge / Not Same actions available."""
        resp = client.get("/people/id-leon/similar")
        assert "Merge" in resp.text
        assert "Not Same" in resp.text
        assert "/api/identity/id-leon/merge/id-nace?source=similar_page" in resp.text
        assert 'data-testid="similar-admin-summary"' in resp.text
        assert "View Person" in resp.text
        assert 'data-testid="similar-result-state"' in resp.text

    def test_community_route_preserves_prefixed_links(self, client, mock_similar_data):
        """Community-scoped similar page should keep person and API links inside the community."""
        with (
            patch(
                "app.supabase_data.get_community_by_slug",
                return_value={"slug": "fox-family", "name": "Fox Family Archive"},
            ),
            patch(
                "app.main._get_proposal_targets_for_identity",
                return_value=[{"face_id": "inbox-1"}, {"face_id": "inbox-2"}],
            ),
        ):
            resp = client.get("/c/fox-family/people/id-leon/similar")
        html = resp.text
        assert "/c/fox-family/person/id-leon" in html
        assert "/c/fox-family/person/id-nace" in html
        assert "/c/fox-family/api/identity/id-leon/merge/id-nace?source=similar_page" in html
        assert "/c/fox-family/admin/upload-review#identity-group-id-leon" in html
