"""Tests for photo sort controls — upload date, estimated date, filename sorting.

Verifies the _sort_photos helper and the /photos route dropdown options.
"""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def photos_with_upload_dates():
    """Three photos with different upload_date values."""
    return [
        {
            "photo_id": "aaa111",
            "filename": "charlie.jpg",
            "collection": "A",
            "face_count": 1,
            "upload_date": "2026-02-10T00:00:00+00:00",
        },
        {
            "photo_id": "bbb222",
            "filename": "alpha.jpg",
            "collection": "B",
            "face_count": 3,
            "upload_date": "2026-03-01T00:00:00+00:00",
        },
        {
            "photo_id": "ccc333",
            "filename": "bravo.jpg",
            "collection": "A",
            "face_count": 2,
            "upload_date": "2026-01-15T00:00:00+00:00",
        },
        {"photo_id": "ddd444", "filename": "delta.jpg", "collection": "B", "face_count": 0, "upload_date": ""},
    ]


@pytest.fixture
def mock_photo_cache_with_dates():
    """Photo cache with upload_date metadata for route-level tests."""
    return {
        "aaa111": {
            "filename": "charlie.jpg",
            "source": "Source A",
            "collection": "Album 1",
            "faces": [],
            "upload_date": "2026-02-10T00:00:00+00:00",
        },
        "bbb222": {
            "filename": "alpha.jpg",
            "source": "Source B",
            "collection": "Album 2",
            "faces": [],
            "upload_date": "2026-03-01T00:00:00+00:00",
        },
        "ccc333": {
            "filename": "bravo.jpg",
            "source": "Source A",
            "collection": "Album 1",
            "faces": [],
            "upload_date": "2026-01-15T00:00:00+00:00",
        },
    }


def _route_patches(photo_cache):
    """Common patches for route tests."""
    mock_registry = MagicMock()
    mock_registry.list_identities.return_value = []
    return {
        "_build_caches": MagicMock(),
        "_photo_cache": photo_cache,
        "load_registry": MagicMock(return_value=mock_registry),
        "get_identity_for_face": MagicMock(return_value=None),
    }


class TestSortPhotosHelper:
    """Unit tests for the _sort_photos function."""

    def test_upload_newest_sorts_by_upload_date_descending(self, photos_with_upload_dates):
        from app.main import _sort_photos

        result = _sort_photos(photos_with_upload_dates, "upload_newest")
        ids = [p["photo_id"] for p in result]
        # bbb(Mar 1) > aaa(Feb 10) > ccc(Jan 15) > ddd(no date)
        assert ids.index("bbb222") < ids.index("aaa111") < ids.index("ccc333")
        assert ids[-1] == "ddd444", "Photo without upload_date should sort to end"

    def test_upload_oldest_sorts_by_upload_date_ascending(self, photos_with_upload_dates):
        from app.main import _sort_photos

        result = _sort_photos(photos_with_upload_dates, "upload_oldest")
        ids = [p["photo_id"] for p in result]
        # ccc(Jan 15) < aaa(Feb 10) < bbb(Mar 1) < ddd(no date)
        assert ids.index("ccc333") < ids.index("aaa111") < ids.index("bbb222")
        assert ids[-1] == "ddd444", "Photo without upload_date should sort to end"

    def test_filename_az_sorts_alphabetically(self, photos_with_upload_dates):
        from app.main import _sort_photos

        result = _sort_photos(photos_with_upload_dates, "filename_az")
        filenames = [p["filename"] for p in result]
        assert filenames == ["alpha.jpg", "bravo.jpg", "charlie.jpg", "delta.jpg"]

    def test_recently_uploaded_is_alias_for_upload_newest(self, photos_with_upload_dates):
        from app.main import _sort_photos

        result_recent = _sort_photos(list(photos_with_upload_dates), "recently_uploaded")
        result_newest = _sort_photos(list(photos_with_upload_dates), "upload_newest")
        assert [p["photo_id"] for p in result_recent] == [p["photo_id"] for p in result_newest]


class TestPhotosRouteDropdown:
    """Verify the /photos route includes the new sort options in the dropdown."""

    def test_photos_route_has_upload_date_options(self, client, mock_photo_cache_with_dates):
        patches = _route_patches(mock_photo_cache_with_dates)
        with patch.multiple("app.main", **patches):
            resp = client.get("/photos")
        assert resp.status_code == 200
        assert "Upload Date (Newest)" in resp.text
        assert "Upload Date (Oldest)" in resp.text
        assert 'value="upload_newest"' in resp.text
        assert 'value="upload_oldest"' in resp.text

    def test_photos_route_has_filename_option(self, client, mock_photo_cache_with_dates):
        patches = _route_patches(mock_photo_cache_with_dates)
        with patch.multiple("app.main", **patches):
            resp = client.get("/photos")
        assert resp.status_code == 200
        assert "Filename (A-Z)" in resp.text
        assert 'value="filename_az"' in resp.text

    def test_photos_route_default_is_upload_newest(self, client, mock_photo_cache_with_dates):
        """Default sort should be upload_newest — verify it's selected."""
        patches = _route_patches(mock_photo_cache_with_dates)
        with patch.multiple("app.main", **patches):
            resp = client.get("/photos")
        assert resp.status_code == 200
        # The first option should be selected by default
        assert 'value="upload_newest" selected' in resp.text.lower().replace('"', '"')
