"""Tests for photo page sorting by estimated date (Session 89d).

Verifies that "Newest First" / "Oldest First" sort by best_year_estimate
from date_labels.json, not by filename.
"""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_photo_cache():
    """Three photos with different filenames to prove sort isn't alphabetical."""
    return {
        "aaa111": {
            "filename": "aaa_early_photo.jpg",
            "source": "Collection A",
            "collection": "Album 1",
            "faces": [],
        },
        "bbb222": {
            "filename": "bbb_middle_photo.jpg",
            "source": "Collection B",
            "collection": "Album 2",
            "faces": [{"face_id": "f1", "bbox": [0, 0, 1, 1]}],
        },
        "ccc333": {
            "filename": "ccc_recent_photo.jpg",
            "source": "Collection A",
            "collection": "Album 1",
            "faces": [{"face_id": "f2", "bbox": [0, 0, 1, 1]}, {"face_id": "f3", "bbox": [1, 1, 2, 2]}],
        },
    }


@pytest.fixture
def mock_date_labels():
    """Date labels where alphabetical filename order != chronological order.

    aaa = 1955 (middle), bbb = 1920 (oldest), ccc = 1980 (newest).
    """
    return {
        "aaa111": {"photo_id": "aaa111", "best_year_estimate": 1955, "estimated_decade": 1950},
        "bbb222": {"photo_id": "bbb222", "best_year_estimate": 1920, "estimated_decade": 1920},
        "ccc333": {"photo_id": "ccc333", "best_year_estimate": 1980, "estimated_decade": 1980},
    }


@pytest.fixture
def mock_date_labels_with_missing():
    """Only two photos have dates — one is missing."""
    return {
        "aaa111": {"photo_id": "aaa111", "best_year_estimate": 1955},
        "ccc333": {"photo_id": "ccc333", "best_year_estimate": 1980},
    }


def _extract_photo_ids_from_response(text):
    """Extract photo IDs from the response HTML by looking for /photo/ links."""
    import re

    return re.findall(r"/photo/([a-z0-9]+)", text)


def _sort_patches(photo_cache, date_labels=None):
    """Common patch context for sorting tests."""
    mock_registry = MagicMock()
    mock_registry.list_identities.return_value = []

    patches = {
        "app.main._build_caches": MagicMock(),
        "app.main._photo_cache": photo_cache,
        "app.main.load_registry": MagicMock(return_value=mock_registry),
        "app.main.get_identity_for_face": MagicMock(return_value=None),
    }
    if date_labels is not None:
        patches["app.main._load_date_labels"] = MagicMock(return_value=date_labels)
    return patches


class TestPhotoSortByDate:
    """Verify sorting uses date_labels best_year_estimate, not filename."""

    def test_newest_first_sorts_by_year_descending(self, client, mock_photo_cache, mock_date_labels):
        patches = _sort_patches(mock_photo_cache, mock_date_labels)
        with patch.multiple(
            "app.main", **{k.split(".")[-1]: v for k, v in patches.items() if k.startswith("app.main.")}
        ):
            resp = client.get("/?section=photos&sort_by=newest")
        assert resp.status_code == 200
        ids = _extract_photo_ids_from_response(resp.text)
        # Newest first: ccc(1980), aaa(1955), bbb(1920)
        assert ids.index("ccc333") < ids.index("aaa111") < ids.index("bbb222"), (
            f"Expected newest-first order ccc>aaa>bbb, got: {ids}"
        )

    def test_oldest_first_sorts_by_year_ascending(self, client, mock_photo_cache, mock_date_labels):
        patches = _sort_patches(mock_photo_cache, mock_date_labels)
        with patch.multiple(
            "app.main", **{k.split(".")[-1]: v for k, v in patches.items() if k.startswith("app.main.")}
        ):
            resp = client.get("/?section=photos&sort_by=oldest")
        assert resp.status_code == 200
        ids = _extract_photo_ids_from_response(resp.text)
        # Oldest first: bbb(1920), aaa(1955), ccc(1980)
        assert ids.index("bbb222") < ids.index("aaa111") < ids.index("ccc333"), (
            f"Expected oldest-first order bbb>aaa>ccc, got: {ids}"
        )

    def test_no_date_photos_sort_to_end_newest(self, client, mock_photo_cache, mock_date_labels_with_missing):
        patches = _sort_patches(mock_photo_cache, mock_date_labels_with_missing)
        with patch.multiple(
            "app.main", **{k.split(".")[-1]: v for k, v in patches.items() if k.startswith("app.main.")}
        ):
            resp = client.get("/?section=photos&sort_by=newest")
        assert resp.status_code == 200
        ids = _extract_photo_ids_from_response(resp.text)
        # bbb222 has no date, should sort to end (year=0 in newest mode)
        assert ids.index("ccc333") < ids.index("aaa111"), f"Expected ccc before aaa, got: {ids}"
        assert ids.index("bbb222") > ids.index("aaa111"), f"Expected bbb222 (no date) at end, got: {ids}"

    def test_no_date_photos_sort_to_end_oldest(self, client, mock_photo_cache, mock_date_labels_with_missing):
        patches = _sort_patches(mock_photo_cache, mock_date_labels_with_missing)
        with patch.multiple(
            "app.main", **{k.split(".")[-1]: v for k, v in patches.items() if k.startswith("app.main.")}
        ):
            resp = client.get("/?section=photos&sort_by=oldest")
        assert resp.status_code == 200
        ids = _extract_photo_ids_from_response(resp.text)
        # bbb222 has no date, should sort to end (year=9999 in oldest mode)
        assert ids.index("aaa111") < ids.index("ccc333"), f"Expected aaa before ccc, got: {ids}"
        assert ids.index("bbb222") > ids.index("ccc333"), f"Expected bbb222 (no date) at end, got: {ids}"


class TestPhotoSortBySource:
    """Verify 'By Source' sort option works."""

    def test_by_source_sorts_alphabetically(self, client, mock_photo_cache, mock_date_labels):
        patches = _sort_patches(mock_photo_cache, mock_date_labels)
        with patch.multiple(
            "app.main", **{k.split(".")[-1]: v for k, v in patches.items() if k.startswith("app.main.")}
        ):
            resp = client.get("/?section=photos&sort_by=by_source")
        assert resp.status_code == 200
        ids = _extract_photo_ids_from_response(resp.text)
        # Collection A (aaa111, ccc333) before Collection B (bbb222)
        assert ids.index("bbb222") > ids.index("aaa111"), f"Expected Collection A before Collection B, got: {ids}"

    def test_by_source_option_in_dropdown(self, client, mock_photo_cache):
        patches = _sort_patches(mock_photo_cache)
        with patch.multiple(
            "app.main", **{k.split(".")[-1]: v for k, v in patches.items() if k.startswith("app.main.")}
        ):
            resp = client.get("/?section=photos")
        assert resp.status_code == 200
        assert "By Source" in resp.text
        assert 'value="by_source"' in resp.text


class TestPhotosRouteSort:
    """Test the /photos route sorting (separate from /?section=photos)."""

    def test_photos_route_newest_sorts_by_date(self, client, mock_photo_cache, mock_date_labels):
        """The /photos route must sort by date, not filename."""
        patches = _sort_patches(mock_photo_cache, mock_date_labels)
        with patch.multiple(
            "app.main", **{k.split(".")[-1]: v for k, v in patches.items() if k.startswith("app.main.")}
        ):
            resp = client.get("/photos?sort_by=newest")
        assert resp.status_code == 200
        ids = _extract_photo_ids_from_response(resp.text)
        # Newest first: ccc(1980), aaa(1955), bbb(1920)
        assert ids.index("ccc333") < ids.index("aaa111") < ids.index("bbb222"), (
            f"Expected newest-first order ccc>aaa>bbb on /photos route, got: {ids}"
        )

    def test_photos_route_has_recently_uploaded_option(self, client, mock_photo_cache):
        """The /photos dropdown should include Recently Uploaded."""
        patches = _sort_patches(mock_photo_cache)
        with patch.multiple(
            "app.main", **{k.split(".")[-1]: v for k, v in patches.items() if k.startswith("app.main.")}
        ):
            resp = client.get("/photos")
        assert resp.status_code == 200
        assert "Recently Uploaded" in resp.text
        assert 'value="recently_uploaded"' in resp.text
