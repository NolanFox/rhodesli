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
        # bbb(Mar 1) > aaa(Feb 10) > ccc(Jan 15) > ddd(no archive timestamp)
        assert ids.index("bbb222") < ids.index("aaa111") < ids.index("ccc333")
        assert ids[-1] == "ddd444", "Photo without upload_date or created_at should sort to end"

    def test_upload_oldest_sorts_by_upload_date_ascending(self, photos_with_upload_dates):
        from app.main import _sort_photos

        result = _sort_photos(photos_with_upload_dates, "upload_oldest")
        ids = [p["photo_id"] for p in result]
        # ccc(Jan 15) < aaa(Feb 10) < bbb(Mar 1) < ddd(no archive timestamp)
        assert ids.index("ccc333") < ids.index("aaa111") < ids.index("bbb222")
        assert ids[-1] == "ddd444", "Photo without upload_date or created_at should sort to end"

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

    def test_upload_newest_breaks_same_day_ties_by_created_at(self):
        from app.main import _sort_photos

        photos = [
            {
                "photo_id": "early",
                "filename": "early.jpg",
                "collection": "A",
                "face_count": 1,
                "upload_date": "2026-03-10",
                "created_at": "2026-03-10T08:00:00+00:00",
            },
            {
                "photo_id": "late",
                "filename": "late.jpg",
                "collection": "A",
                "face_count": 1,
                "upload_date": "2026-03-10",
                "created_at": "2026-03-10T20:00:00+00:00",
            },
        ]

        result = _sort_photos(photos, "upload_newest")
        assert [p["photo_id"] for p in result] == ["late", "early"]

    def test_upload_oldest_breaks_same_day_ties_by_created_at(self):
        from app.main import _sort_photos

        photos = [
            {
                "photo_id": "early",
                "filename": "early.jpg",
                "collection": "A",
                "face_count": 1,
                "upload_date": "2026-03-10",
                "created_at": "2026-03-10T08:00:00+00:00",
            },
            {
                "photo_id": "late",
                "filename": "late.jpg",
                "collection": "A",
                "face_count": 1,
                "upload_date": "2026-03-10",
                "created_at": "2026-03-10T20:00:00+00:00",
            },
        ]

        result = _sort_photos(photos, "upload_oldest")
        assert [p["photo_id"] for p in result] == ["early", "late"]

    def test_upload_newest_falls_back_to_created_at_when_upload_date_missing(self):
        from app.main import _sort_photos

        photos = [
            {
                "photo_id": "old-no-upload",
                "filename": "old.jpg",
                "collection": "A",
                "face_count": 1,
                "upload_date": "",
                "created_at": "2026-03-09T08:00:00+00:00",
            },
            {
                "photo_id": "new-no-upload",
                "filename": "new.jpg",
                "collection": "A",
                "face_count": 1,
                "upload_date": "",
                "created_at": "2026-03-10T20:00:00+00:00",
            },
            {
                "photo_id": "no-timestamps",
                "filename": "none.jpg",
                "collection": "A",
                "face_count": 1,
                "upload_date": "",
            },
        ]

        result = _sort_photos(photos, "upload_newest")
        assert [p["photo_id"] for p in result] == ["new-no-upload", "old-no-upload", "no-timestamps"]

    def test_upload_newest_breaks_true_timestamp_ties_by_photo_index_order(self):
        from app.main import _sort_photos

        tied_timestamp = "2026-03-10T17:53:28.672276+00:00"
        photos = [
            {
                "photo_id": "older-entry",
                "filename": "a.jpg",
                "collection": "A",
                "face_count": 1,
                "upload_date": tied_timestamp,
                "photo_index_order": 932,
            },
            {
                "photo_id": "newer-entry",
                "filename": "z.jpg",
                "collection": "A",
                "face_count": 1,
                "upload_date": tied_timestamp,
                "photo_index_order": 938,
            },
        ]

        result = _sort_photos(photos, "upload_newest")
        assert [p["photo_id"] for p in result] == ["newer-entry", "older-entry"]

    def test_upload_oldest_breaks_true_timestamp_ties_by_photo_index_order(self):
        from app.main import _sort_photos

        tied_timestamp = "2026-03-10T17:53:28.672276+00:00"
        photos = [
            {
                "photo_id": "older-entry",
                "filename": "a.jpg",
                "collection": "A",
                "face_count": 1,
                "upload_date": tied_timestamp,
                "photo_index_order": 932,
            },
            {
                "photo_id": "newer-entry",
                "filename": "z.jpg",
                "collection": "A",
                "face_count": 1,
                "upload_date": tied_timestamp,
                "photo_index_order": 938,
            },
        ]

        result = _sort_photos(photos, "upload_oldest")
        assert [p["photo_id"] for p in result] == ["older-entry", "newer-entry"]


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

    def test_photos_route_default_is_newest(self, client, mock_photo_cache_with_dates):
        """Public /photos should default to estimated-date newest for discovery browsing."""
        patches = _route_patches(mock_photo_cache_with_dates)
        with patch.multiple("app.main", **patches):
            resp = client.get("/photos")
        assert resp.status_code == 200
        assert 'value="newest" selected' in resp.text.lower().replace('"', '"')


class TestBuildCachesMetadataFallback:
    """Verify _build_caches merges upload_date even for mismatched photo IDs.

    Bug: photo_index.json uses inbox_* IDs, _photo_cache uses SHA256 IDs.
    get_metadata(sha256_id) returns {} for inbox photos, so upload_date
    was never propagated. Fix: filename-based fallback for metadata.
    """

    def test_upload_date_propagated_for_inbox_photos(self, tmp_path):
        """upload_date should appear in _photo_cache even when IDs mismatch."""
        import json

        from app.main import _build_caches

        # Create a photo_index.json where the photo uses inbox_* ID
        photo_index = {
            "schema_version": 1,
            "photos": {
                "inbox_abc123_0_test": {
                    "path": "raw_photos/test_photo.jpg",
                    "face_ids": ["inbox_abc123_face0"],
                    "source": "Test Source",
                    "collection": "Test Collection",
                    "upload_date": "2026-03-05T12:00:00+00:00",
                    "uploaded_by": "test@example.com",
                    "width": 800,
                    "height": 600,
                }
            },
            "face_to_photo": {"inbox_abc123_face0": "inbox_abc123_0_test"},
        }
        pi_path = tmp_path / "photo_index.json"
        pi_path.write_text(json.dumps(photo_index))

        # _photo_cache uses SHA256 ID for the same file
        fake_cache = {
            "sha256abcdef01": {
                "filename": "raw_photos/test_photo.jpg",
                "faces": [{"face_id": "inbox_abc123_face0", "bbox": [0, 0, 100, 100]}],
                "source": "",
                "collection": "",
            }
        }

        import app.main as main_mod

        # Save originals
        orig_cache = main_mod._photo_cache
        orig_f2p = main_mod._face_to_photo_cache
        orig_aliases = main_mod._photo_id_aliases

        try:
            # Set _photo_cache to our fake (non-None so _build_caches skips load_embeddings)
            # We need to simulate the state AFTER load_embeddings but before metadata merge
            # So we call the merge logic directly by resetting and calling _build_caches
            main_mod._photo_cache = None
            main_mod._face_to_photo_cache = None
            main_mod._photo_id_aliases = None

            with (
                patch.object(main_mod, "load_embeddings_for_photos", return_value=fake_cache),
                patch.object(main_mod, "data_path", tmp_path),
            ):
                _build_caches()

            # Verify upload_date was propagated via filename fallback
            cached = main_mod._photo_cache["sha256abcdef01"]
            assert cached.get("upload_date") == "2026-03-05T12:00:00+00:00", (
                f"upload_date not propagated to _photo_cache: {cached}"
            )
            assert cached.get("uploaded_by") == "test@example.com"
        finally:
            main_mod._photo_cache = orig_cache
            main_mod._face_to_photo_cache = orig_f2p
            main_mod._photo_id_aliases = orig_aliases

    def test_upload_date_propagated_for_matching_ids(self, tmp_path):
        """upload_date works when photo_index and cache use the same ID."""
        import json

        from app.main import _build_caches

        photo_index = {
            "schema_version": 1,
            "photos": {
                "sha256match01": {
                    "path": "raw_photos/match.jpg",
                    "face_ids": [],
                    "source": "Match Source",
                    "collection": "Match Collection",
                    "upload_date": "2026-02-10T00:00:00+00:00",
                    "width": 400,
                    "height": 300,
                }
            },
            "face_to_photo": {},
        }
        pi_path = tmp_path / "photo_index.json"
        pi_path.write_text(json.dumps(photo_index))

        fake_cache = {
            "sha256match01": {
                "filename": "raw_photos/match.jpg",
                "faces": [],
                "source": "",
                "collection": "",
            }
        }

        import app.main as main_mod

        orig_cache = main_mod._photo_cache
        orig_f2p = main_mod._face_to_photo_cache
        orig_aliases = main_mod._photo_id_aliases

        try:
            main_mod._photo_cache = None
            main_mod._face_to_photo_cache = None
            main_mod._photo_id_aliases = None

            with (
                patch.object(main_mod, "load_embeddings_for_photos", return_value=fake_cache),
                patch.object(main_mod, "data_path", tmp_path),
            ):
                _build_caches()

            cached = main_mod._photo_cache["sha256match01"]
            assert cached.get("upload_date") == "2026-02-10T00:00:00+00:00"
        finally:
            main_mod._photo_cache = orig_cache
            main_mod._face_to_photo_cache = orig_f2p
            main_mod._photo_id_aliases = orig_aliases

    def test_duplicate_basename_prefers_richer_inbox_metadata(self, tmp_path):
        """When SHA and inbox IDs share a basename, keep the richer upload metadata."""
        import json

        from app.main import _build_caches

        photo_index = {
            "schema_version": 1,
            "photos": {
                "sha_old": {
                    "path": "family_search_david_capeloto_declaration_of_intent_image.jpg",
                    "face_ids": [],
                    "source": "FamilySearch",
                    "collection": "Immigration Records",
                    "created_at": "2026-03-09T21:50:25.730264+00:00",
                },
                "inbox_new": {
                    "path": "raw_photos/family_search_david_capeloto_declaration_of_intent_image.jpg",
                    "face_ids": [],
                    "source": "FamilySearch",
                    "collection": "Immigration Records",
                    "upload_date": "2026-03-10T17:53:28.672276+00:00",
                    "created_at": "2026-03-10T15:54:58.625824+00:00",
                    "updated_at": "2026-03-10T20:18:21.437235+00:00",
                    "uploaded_by": "admin@example.com",
                },
            },
            "face_to_photo": {},
        }
        (tmp_path / "photo_index.json").write_text(json.dumps(photo_index))

        fake_cache = {
            "d2642d16f5f0139c": {
                "filename": "family_search_david_capeloto_declaration_of_intent_image.jpg",
                "faces": [],
                "source": "",
                "collection": "",
            }
        }

        import app.main as main_mod

        orig_cache = main_mod._photo_cache
        orig_f2p = main_mod._face_to_photo_cache
        orig_aliases = main_mod._photo_id_aliases

        try:
            main_mod._photo_cache = None
            main_mod._face_to_photo_cache = None
            main_mod._photo_id_aliases = None

            with (
                patch.object(main_mod, "load_embeddings_for_photos", return_value=fake_cache),
                patch.object(main_mod, "data_path", tmp_path),
            ):
                _build_caches()

            cached = main_mod._photo_cache["d2642d16f5f0139c"]
            assert cached.get("upload_date") == "2026-03-10T17:53:28.672276+00:00"
            assert cached.get("created_at") == "2026-03-10T15:54:58.625824+00:00"
            assert cached.get("uploaded_by") == "admin@example.com"
        finally:
            main_mod._photo_cache = orig_cache
            main_mod._face_to_photo_cache = orig_f2p
            main_mod._photo_id_aliases = orig_aliases
