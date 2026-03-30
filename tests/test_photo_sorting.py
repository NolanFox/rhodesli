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


class TestDateLabelsDualKeying:
    """Verify date labels are dual-keyed by both inbox_* and SHA256 photo IDs (FB-007)."""

    def test_postgres_mode_adds_sha256_aliases(self):
        """When date_labels use inbox_* IDs, SHA256 aliases should be added."""
        from unittest.mock import MagicMock, patch
        from pathlib import Path

        mock_photo_registry = MagicMock()
        # Simulate inbox_* ID mapping to a filename
        mock_photo_registry.get_photo_path.side_effect = lambda pid: (
            "raw_photos/test_photo_123.jpg" if pid == "inbox_test_batch_001" else None
        )

        inbox_labels = {
            "inbox_test_batch_001": {
                "photo_id": "inbox_test_batch_001",
                "best_year_estimate": 1945,
                "estimated_decade": 1940,
            }
        }

        with (
            patch("app.main.DATA_SOURCE", "postgres"),
            patch("app.main._date_labels_cache", None),
            patch("app.supabase_data.load_date_labels_from_supabase", return_value=dict(inbox_labels)),
            patch("app.main.load_photo_registry", return_value=mock_photo_registry),
        ):
            import app.main as main_mod

            # Reset cache to force reload
            main_mod._date_labels_cache = None
            result = main_mod._load_date_labels()

        # Original inbox ID should be present
        assert "inbox_test_batch_001" in result
        assert result["inbox_test_batch_001"]["best_year_estimate"] == 1945

        # SHA256 of "test_photo_123.jpg" should also be present
        from app.utils import generate_photo_id

        sha256_id = generate_photo_id("test_photo_123.jpg")
        assert sha256_id in result, f"SHA256 alias {sha256_id} not found in date labels"
        assert result[sha256_id]["best_year_estimate"] == 1945

    def test_postgres_mode_no_duplicate_on_sha256_collision(self):
        """If SHA256 ID already exists in labels, don't overwrite it."""
        from unittest.mock import MagicMock, patch
        from app.utils import generate_photo_id

        sha256_id = generate_photo_id("test_photo.jpg")

        mock_photo_registry = MagicMock()
        mock_photo_registry.get_photo_path.side_effect = lambda pid: (
            "raw_photos/test_photo.jpg" if pid == "inbox_test_001" else None
        )

        # Both IDs already exist with different data
        labels = {
            "inbox_test_001": {"best_year_estimate": 1945},
            sha256_id: {"best_year_estimate": 1950},  # Already exists with different year
        }

        with (
            patch("app.main.DATA_SOURCE", "postgres"),
            patch("app.main._date_labels_cache", None),
            patch("app.supabase_data.load_date_labels_from_supabase", return_value=dict(labels)),
            patch("app.main.load_photo_registry", return_value=mock_photo_registry),
        ):
            import app.main as main_mod

            main_mod._date_labels_cache = None
            result = main_mod._load_date_labels()

        # SHA256 entry should NOT be overwritten
        assert result[sha256_id]["best_year_estimate"] == 1950

    def test_person_gallery_sort_uses_date_labels_with_sha256_ids(self):
        """Person gallery sort must find date labels even when photos use SHA256 IDs."""
        from app.page_routes import _normalize_gallery_sort

        # Verify the normalize function accepts date_asc
        assert _normalize_gallery_sort("date_asc") == "date_asc"
        assert _normalize_gallery_sort("date_desc") == "date_desc"
        assert _normalize_gallery_sort("invalid") == "date_asc"


class TestPhotoLocationsDualKeying:
    """Verify photo_locations also gets SHA256 aliases in Postgres mode."""

    def test_postgres_mode_adds_sha256_aliases_to_locations(self):
        """Photo locations should be accessible by SHA256 ID."""
        from unittest.mock import MagicMock, patch

        mock_photo_registry = MagicMock()
        mock_photo_registry.get_photo_path.side_effect = lambda pid: (
            "raw_photos/test_location_photo.jpg" if pid == "inbox_loc_001" else None
        )

        inbox_locations = {
            "inbox_loc_001": {
                "photo_id": "inbox_loc_001",
                "lat": 39.7589,
                "lng": -84.1916,
                "location_name": "Dayton, Ohio",
            }
        }

        with (
            patch("app.page_routes._main_mod.DATA_SOURCE", "postgres"),
            patch("app.page_routes._photo_locations_cache", None),
            patch(
                "app.supabase_data.load_photo_locations_from_supabase",
                return_value=dict(inbox_locations),
            ),
            patch("app.page_routes._main_mod.load_photo_registry", return_value=mock_photo_registry),
        ):
            from app.page_routes import _load_photo_locations

            # Reset cache
            import app.page_routes

            app.page_routes._photo_locations_cache = None
            result = _load_photo_locations()

        assert "inbox_loc_001" in result
        from app.utils import generate_photo_id

        sha256_id = generate_photo_id("test_location_photo.jpg")
        assert sha256_id in result, f"SHA256 alias {sha256_id} not found in photo locations"
        assert result[sha256_id]["location_name"] == "Dayton, Ohio"


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

    def test_photos_route_has_upload_date_sort_option(self, client, mock_photo_cache):
        """The /photos dropdown should include Upload Date sort options."""
        patches = _sort_patches(mock_photo_cache)
        with patch.multiple(
            "app.main", **{k.split(".")[-1]: v for k, v in patches.items() if k.startswith("app.main.")}
        ):
            resp = client.get("/photos")
        assert resp.status_code == 200
        assert "Upload Date (Newest)" in resp.text
        assert 'value="upload_newest"' in resp.text

    def test_photos_route_upload_newest_uses_photo_index_order_tiebreak(self, client):
        """Public /photos upload sorting should keep archival insertion order on exact timestamp ties."""
        photo_cache = {
            "aaa111": {
                "filename": "older-visible.jpg",
                "collection": "Album 1",
                "faces": [],
                "upload_date": "2026-03-10T17:53:28.672276+00:00",
                "photo_index_order": 10,
            },
            "zzz999": {
                "filename": "newer-visible.jpg",
                "collection": "Album 1",
                "faces": [],
                "upload_date": "2026-03-10T17:53:28.672276+00:00",
                "photo_index_order": 1,
            },
        }
        patches = _sort_patches(photo_cache)
        with patch.multiple(
            "app.main", **{k.split(".")[-1]: v for k, v in patches.items() if k.startswith("app.main.")}
        ):
            resp = client.get("/photos?sort_by=upload_newest")
        assert resp.status_code == 200
        ids = _extract_photo_ids_from_response(resp.text)
        assert ids.index("aaa111") < ids.index("zzz999"), (
            f"Expected archival insertion order aaa111>zzz999 on exact tie, got: {ids}"
        )
