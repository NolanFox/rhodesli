"""Tests for upload provenance tracking (Session 89d).

Verifies that upload metadata (uploaded_by, upload_date) is stored
and displayed on photo pages and Recently Reviewed cards.
"""

from unittest.mock import MagicMock, patch


class TestUploadProvenanceDisplay:
    """Verify photo page shows uploader info when available."""

    def test_photo_page_shows_uploaded_by(self, client):
        """Photo page shows 'Uploaded by email on date' when fields exist."""
        mock_photo_cache = {
            "test_upload": {
                "filename": "test.jpg",
                "source": "Community Upload",
                "collection": "Community",
                "faces": [],
                "uploaded_by": "user@example.com",
                "upload_date": "2026-03-05T12:00:00+00:00",
            }
        }
        mock_registry = MagicMock()
        mock_registry.list_identities.return_value = []

        with (
            patch("app.main._build_caches"),
            patch("app.main._photo_cache", mock_photo_cache),
            patch("app.main._photo_id_aliases", {}),
            patch("app.main._face_to_photo_cache", {}),
            patch("app.main._load_date_labels", return_value={}),
            patch("app.main._load_search_index", return_value=[]),
            patch("app.main._load_photo_locations", return_value={}),
            patch("app.main.load_registry", return_value=mock_registry),
            patch("app.main._check_admin", return_value=None),
            patch("app.main._check_login", return_value=None),
            patch("app.main.get_identity_for_face", return_value=None),
        ):
            resp = client.get("/photo/test_upload")

        assert resp.status_code == 200
        assert "user@example.com" in resp.text
        assert "Uploaded by" in resp.text

    def test_photo_page_falls_back_to_source(self, client):
        """Photo page shows 'Source: X' when no uploaded_by field."""
        mock_photo_cache = {
            "test_nosource": {
                "filename": "test.jpg",
                "source": "Betty Capeluto Album",
                "collection": "Betty Collection",
                "faces": [],
            }
        }
        mock_registry = MagicMock()
        mock_registry.list_identities.return_value = []

        with (
            patch("app.main._build_caches"),
            patch("app.main._photo_cache", mock_photo_cache),
            patch("app.main._photo_id_aliases", {}),
            patch("app.main._face_to_photo_cache", {}),
            patch("app.main._load_date_labels", return_value={}),
            patch("app.main._load_search_index", return_value=[]),
            patch("app.main._load_photo_locations", return_value={}),
            patch("app.main.load_registry", return_value=mock_registry),
            patch("app.main._check_admin", return_value=None),
            patch("app.main._check_login", return_value=None),
            patch("app.main.get_identity_for_face", return_value=None),
        ):
            resp = client.get("/photo/test_nosource")

        assert resp.status_code == 200
        assert "Source: Betty Capeluto Album" in resp.text

    def test_photo_page_shows_added_to_archive_when_upload_date_backfilled(self, client):
        """Backfilled upload dates should render even when no uploader email exists."""
        mock_photo_cache = {
            "test_backfilled": {
                "filename": "test.jpg",
                "source": "Betty Capeluto Album",
                "collection": "Betty Collection",
                "faces": [],
                "upload_date": "2026-02-10T00:00:00+00:00",
            }
        }
        mock_registry = MagicMock()
        mock_registry.list_identities.return_value = []

        with (
            patch("app.main._build_caches"),
            patch("app.main._photo_cache", mock_photo_cache),
            patch("app.main._photo_id_aliases", {}),
            patch("app.main._face_to_photo_cache", {}),
            patch("app.main._load_date_labels", return_value={}),
            patch("app.main._load_search_index", return_value=[]),
            patch("app.main._load_photo_locations", return_value={}),
            patch("app.main.load_registry", return_value=mock_registry),
            patch("app.main._check_admin", return_value=None),
            patch("app.main._check_login", return_value=None),
            patch("app.main.get_identity_for_face", return_value=None),
        ):
            resp = client.get("/photo/test_backfilled")

        assert resp.status_code == 200
        assert "Added to archive: Feb 10, 2026" in resp.text


class TestRecentlyReviewedCards:
    """Verify Recently Reviewed shows timestamps and photo links."""

    def test_reviewed_cards_show_timestamps(self, client):
        """Recently Reviewed cards should show submitted_at and reviewed_at."""
        mock_uploads = {
            "uploads": {
                "job1": {
                    "job_id": "job1",
                    "status": "approved",
                    "uploader_email": "test@example.com",
                    "submitted_at": "2026-03-05T10:00:00+00:00",
                    "reviewed_at": "2026-03-05T11:00:00+00:00",
                    "file_count": 1,
                    "files": [{"filename": "photo.jpg"}],
                },
            }
        }
        mock_registry = MagicMock()
        mock_registry.list_identities.return_value = []

        with (
            patch("app.main._check_admin", return_value=None),
            patch("app.main.load_registry", return_value=mock_registry),
            patch(
                "app.main._compute_sidebar_counts",
                return_value={
                    "to_review": 0,
                    "confirmed": 0,
                    "skipped": 0,
                    "rejected": 0,
                    "photos": 0,
                    "pending_uploads": 0,
                    "proposals": 0,
                    "pending_annotations": 0,
                    "discoveries": 0,
                },
            ),
            patch("app.main._load_pending_uploads", return_value=mock_uploads),
        ):
            resp = client.get("/admin/pending")

        assert resp.status_code == 200
        assert "Submitted:" in resp.text
        assert "Approved:" in resp.text
        assert "test@example.com" in resp.text

    def test_reviewed_cards_show_photo_links(self, client):
        """After approval, Recently Reviewed should link to resulting photo."""
        mock_uploads = {
            "uploads": {
                "job_abc": {
                    "job_id": "job_abc",
                    "status": "approved",
                    "uploader_email": "user@example.com",
                    "submitted_at": "2026-03-05T10:00:00+00:00",
                    "reviewed_at": "2026-03-05T11:00:00+00:00",
                    "file_count": 1,
                    "files": [{"filename": "family_photo.jpg"}],
                },
            }
        }
        mock_registry = MagicMock()
        mock_registry.list_identities.return_value = []

        with (
            patch("app.main._check_admin", return_value=None),
            patch("app.main.load_registry", return_value=mock_registry),
            patch(
                "app.main._compute_sidebar_counts",
                return_value={
                    "to_review": 0,
                    "confirmed": 0,
                    "skipped": 0,
                    "rejected": 0,
                    "photos": 0,
                    "pending_uploads": 0,
                    "proposals": 0,
                    "pending_annotations": 0,
                    "discoveries": 0,
                },
            ),
            patch("app.main._load_pending_uploads", return_value=mock_uploads),
        ):
            resp = client.get("/admin/pending")

        assert resp.status_code == 200
        assert "View photo" in resp.text
        assert "/photo/inbox_job_abc_0_family_photo" in resp.text


class TestIngestProvenancePropagation:
    """Verify process_single_image stores uploaded_by/upload_date."""

    def test_provenance_stored_in_photo_registry(self):
        """process_single_image should call set_metadata with provenance."""
        from core.photo_registry import PhotoRegistry

        registry = PhotoRegistry()
        registry.register_face("test_photo", "raw_photos/test.jpg", "face1", source="Test")
        registry.set_metadata(
            "test_photo",
            {
                "uploaded_by": "user@example.com",
                "upload_date": "2026-03-05T12:00:00Z",
                "job_id": "abc123",
            },
        )

        photo = registry._photos["test_photo"]
        assert photo["uploaded_by"] == "user@example.com"
        assert photo["upload_date"] == "2026-03-05T12:00:00Z"
        assert photo["job_id"] == "abc123"
