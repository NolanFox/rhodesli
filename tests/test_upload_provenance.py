"""Tests for upload provenance tracking (Session 89d).

Verifies that upload metadata (uploaded_by, upload_date) is stored
and displayed on photo pages and Recently Reviewed cards.
"""

from unittest.mock import MagicMock, patch


class TestUploadProvenanceDisplay:
    """Verify photo page shows uploader info when available."""

    def test_helper_returns_detail_and_summary_strings(self):
        """Shared provenance helper returns full/detail strings for cards and photo pages."""
        from app.main import _get_upload_provenance_display

        display = _get_upload_provenance_display(
            {
                "uploaded_by": "user@example.com",
                "upload_date": "2026-03-05T12:00:00+00:00",
            }
        )

        assert display is not None
        assert display["headline"] == "Uploaded Mar 5, 2026 at 12:00 PM UTC"
        assert display["subline"] == "by user@example.com"
        assert display["full_text"] == "Uploaded by user@example.com on Mar 5, 2026 at 12:00 PM UTC"

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
        assert "Mar 5, 2026 at 12:00 PM UTC" in resp.text

    def test_photo_page_shows_source_in_metadata_section(self, client):
        """Photo page shows source in collection/source section, not in provenance line (BUG-5 fix)."""
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
        # Source appears in the collection/source section
        assert "Betty Capeluto Album" in resp.text
        # The provenance line should NOT show "Source: Betty Capeluto Album" as a separate line
        # (BUG-5 fix removed duplicate source from _build_upload_provenance_line)
        from app.main import _build_upload_provenance_line
        from fasthtml.common import to_xml

        result = _build_upload_provenance_line({"source": "Betty Capeluto Album"})
        assert result is None, "Provenance line should not show source fallback"

    def test_photo_page_shows_archive_timestamp_when_upload_date_backfilled(self, client):
        """Backfilled upload dates should render with explicit missing-uploader wording."""
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
        assert "Archive entry recorded on Feb 10, 2026 at 12:00 AM UTC" in resp.text
        assert "uploader not recorded for this import" in resp.text

    def test_workstation_photos_cards_surface_provenance_summary(self, client):
        """Workstation photo cards show upload/archive provenance without opening the photo."""
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
            patch("app.main.load_registry", return_value=mock_registry),
            patch("app.main.get_identity_for_face", return_value=None),
        ):
            resp = client.get("/?section=photos&sort_by=upload_newest")

        assert resp.status_code == 200
        assert "Uploaded Mar 5, 2026 at 12:00 PM UTC" in resp.text
        assert "by user@example.com" in resp.text

    def test_public_photos_cards_surface_archive_provenance_summary(self, client):
        """Public /photos cards show archive-entry timing even without uploader attribution."""
        mock_photo_cache = {
            "test_backfilled": {
                "filename": "test.jpg",
                "collection": "Betty Collection",
                "faces": [],
                "upload_date": "2026-02-10T00:00:00+00:00",
                "photo_index_order": 5,
            }
        }
        mock_registry = MagicMock()
        mock_registry.list_identities.return_value = []

        with (
            patch("app.main._build_caches"),
            patch("app.main._photo_cache", mock_photo_cache),
            patch("app.main.load_registry", return_value=mock_registry),
            patch("app.main.get_identity_for_face", return_value=None),
        ):
            resp = client.get("/photos?sort_by=upload_newest")

        assert resp.status_code == 200
        assert "Archive entry Feb 10, 2026 at 12:00 AM UTC" in resp.text
        assert "Uploader not recorded for this import" in resp.text


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


class TestApplySuggestionsReturnValue:
    """BUG-1 fix: apply_suggestions returns (data, count), not just data."""

    def test_apply_suggestions_returns_tuple(self):
        """apply_suggestions must return (updated_data, applied_count) tuple."""
        from scripts.cluster_new_faces import apply_suggestions

        identities_data = {
            "schema_version": 1,
            "identities": {
                "source-id": {
                    "identity_id": "source-id",
                    "name": "Unknown",
                    "state": "INBOX",
                    "anchor_ids": ["face1"],
                    "candidate_ids": [],
                    "negative_ids": [],
                    "version_id": 1,
                },
                "target-id": {
                    "identity_id": "target-id",
                    "name": "Known Person",
                    "state": "CONFIRMED",
                    "anchor_ids": ["face2"],
                    "candidate_ids": [],
                    "negative_ids": [],
                    "version_id": 1,
                },
            },
        }
        suggestions = [
            {
                "face_id": "face1",
                "source_identity_id": "source-id",
                "target_identity_id": "target-id",
                "distance": 0.7,
            }
        ]

        result = apply_suggestions(identities_data, suggestions)
        # Must be a tuple of (dict, int)
        assert isinstance(result, tuple), f"apply_suggestions should return tuple, got {type(result)}"
        updated_data, applied_count = result
        assert isinstance(updated_data, dict)
        assert isinstance(applied_count, int)
        assert applied_count == 1
        assert updated_data["schema_version"] == 1
        assert "face1" in updated_data["identities"]["target-id"]["candidate_ids"]


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
