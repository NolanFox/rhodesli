"""Tests for community sync functions in app/supabase_data.py (PRD-035)."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_supabase():
    """Mock Supabase client for community sync tests."""
    with patch("app.supabase_data.get_supabase_client") as mock_get:
        client = MagicMock()
        mock_get.return_value = client
        yield client


class TestLoadCommunities:
    def test_returns_list_of_communities(self, mock_supabase):
        from app.supabase_data import load_communities

        mock_supabase.table.return_value.select.return_value.order.return_value.execute.return_value = MagicMock(
            data=[
                {"id": "abc", "slug": "rhodes", "name": "Jewish Community of Rhodes"},
                {"id": "def", "slug": "fox-family", "name": "Fox Family Archive"},
            ]
        )
        result = load_communities()
        assert len(result) == 2
        assert result[0]["slug"] == "rhodes"
        assert result[1]["slug"] == "fox-family"

    def test_returns_none_when_supabase_unavailable(self):
        from app.supabase_data import load_communities

        with patch("app.supabase_data.get_supabase_client", return_value=None):
            result = load_communities()
            assert result is None

    def test_returns_empty_list_when_no_communities(self, mock_supabase):
        from app.supabase_data import load_communities

        mock_supabase.table.return_value.select.return_value.order.return_value.execute.return_value = MagicMock(
            data=[]
        )
        result = load_communities()
        assert result == []


class TestGetCommunityBySlug:
    def test_returns_community_for_valid_slug(self, mock_supabase):
        from app.supabase_data import get_community_by_slug

        mock_supabase.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = (
            MagicMock(data=[{"id": "abc", "slug": "rhodes", "name": "Jewish Community of Rhodes"}])
        )
        result = get_community_by_slug("rhodes")
        assert result["slug"] == "rhodes"
        assert result["id"] == "abc"

    def test_returns_none_for_unknown_slug(self, mock_supabase):
        from app.supabase_data import get_community_by_slug

        mock_supabase.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = (
            MagicMock(data=[])
        )
        result = get_community_by_slug("nonexistent")
        assert result is None

    def test_returns_none_when_supabase_unavailable(self):
        from app.supabase_data import get_community_by_slug

        with patch("app.supabase_data.get_supabase_client", return_value=None):
            assert get_community_by_slug("rhodes") is None


class TestLoadPhotosForCommunity:
    def test_returns_photo_ids(self, mock_supabase):
        from app.supabase_data import load_photos_for_community

        mock_result = MagicMock(data=[{"photo_id": "p1"}, {"photo_id": "p2"}])
        mock_supabase.table.return_value.select.return_value.eq.return_value.range.return_value.execute.return_value = (
            mock_result
        )

        result = load_photos_for_community("community-uuid")
        assert result == ["p1", "p2"]

    def test_returns_none_when_supabase_unavailable(self):
        from app.supabase_data import load_photos_for_community

        with patch("app.supabase_data.get_supabase_client", return_value=None):
            assert load_photos_for_community("x") is None

    def test_returns_empty_list_for_empty_community(self, mock_supabase):
        from app.supabase_data import load_photos_for_community

        mock_supabase.table.return_value.select.return_value.eq.return_value.range.return_value.execute.return_value = (
            MagicMock(data=[])
        )
        result = load_photos_for_community("community-uuid")
        assert result == []


class TestLoadIdentitiesForCommunity:
    def test_returns_identity_rows(self, mock_supabase):
        from app.supabase_data import load_identities_for_community

        mock_result = MagicMock(
            data=[
                {"identity_id": "id1", "is_primary": True},
                {"identity_id": "id2", "is_primary": False},
            ]
        )
        mock_supabase.table.return_value.select.return_value.eq.return_value.range.return_value.execute.return_value = (
            mock_result
        )

        result = load_identities_for_community("community-uuid")
        assert len(result) == 2
        assert result[0]["identity_id"] == "id1"
        assert result[0]["is_primary"] is True

    def test_returns_none_when_supabase_unavailable(self):
        from app.supabase_data import load_identities_for_community

        with patch("app.supabase_data.get_supabase_client", return_value=None):
            assert load_identities_for_community("x") is None


class TestCreateCommunity:
    def test_creates_community(self, mock_supabase):
        from app.supabase_data import create_community

        mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"id": "new-uuid", "slug": "test-community", "name": "Test"}]
        )
        result = create_community({"slug": "test-community", "name": "Test", "r2_prefix": "test/"})
        assert result["slug"] == "test-community"
        mock_supabase.table.assert_called_with("communities")

    def test_returns_none_when_supabase_unavailable(self):
        from app.supabase_data import create_community

        with patch("app.supabase_data.get_supabase_client", return_value=None):
            assert create_community({"slug": "x"}) is None


class TestUpdateCommunity:
    def test_updates_community(self, mock_supabase):
        from app.supabase_data import update_community

        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[{"id": "uuid", "name": "Updated Name"}]
        )
        result = update_community("uuid", {"name": "Updated Name"})
        assert result["name"] == "Updated Name"

    def test_returns_none_when_supabase_unavailable(self):
        from app.supabase_data import update_community

        with patch("app.supabase_data.get_supabase_client", return_value=None):
            assert update_community("x", {"name": "y"}) is None


class TestCreateUploadBatch:
    def test_creates_batch(self, mock_supabase):
        from app.supabase_data import create_upload_batch

        mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"id": "batch-uuid", "source_description": "Box 1"}]
        )
        result = create_upload_batch({"community_id": "comm-uuid", "source_description": "Box 1", "photo_count": 10})
        assert result["id"] == "batch-uuid"

    def test_returns_none_when_supabase_unavailable(self):
        from app.supabase_data import create_upload_batch

        with patch("app.supabase_data.get_supabase_client", return_value=None):
            assert create_upload_batch({}) is None


class TestAddPhotoToCommunity:
    def test_adds_photo(self, mock_supabase):
        from app.supabase_data import add_photo_to_community

        mock_supabase.table.return_value.upsert.return_value.execute.return_value = MagicMock(data=[{}])
        result = add_photo_to_community("photo-1", "community-uuid")
        assert result is True

    def test_returns_false_when_supabase_unavailable(self):
        from app.supabase_data import add_photo_to_community

        with patch("app.supabase_data.get_supabase_client", return_value=None):
            assert add_photo_to_community("p", "c") is False


class TestAddIdentityToCommunity:
    def test_adds_identity(self, mock_supabase):
        from app.supabase_data import add_identity_to_community

        mock_supabase.table.return_value.upsert.return_value.execute.return_value = MagicMock(data=[{}])
        result = add_identity_to_community("id-1", "community-uuid", is_primary=True)
        assert result is True

    def test_returns_false_when_supabase_unavailable(self):
        from app.supabase_data import add_identity_to_community

        with patch("app.supabase_data.get_supabase_client", return_value=None):
            assert add_identity_to_community("i", "c") is False
