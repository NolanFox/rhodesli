"""Tests for shadow write functions in app/supabase_data.py.

Shadow writes are fire-and-forget: they should never raise exceptions,
and should gracefully handle missing Supabase configuration.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.supabase_data import (
    shadow_write_identity,
    shadow_write_identities_batch,
    shadow_write_photo,
    shadow_write_photos_batch,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_supabase_client():
    """Create a mock Supabase client with table().upsert().execute() chain."""
    client = MagicMock()
    execute_mock = MagicMock()
    client.table.return_value.upsert.return_value.execute = execute_mock
    return client


@pytest.fixture
def sample_photo():
    return {
        "photo_id": "abc123def456",
        "path": "Image 001_compress.jpg",
        "source": "Betty's Album",
        "collection": "Betty Capeluto Miami Collection",
        "source_url": "",
        "upload_date": None,
        "width": 800,
        "height": 600,
        "face_ids": ["face1", "face2", "face3"],
        "uploaded_by": None,
        "job_id": None,
    }


@pytest.fixture
def sample_identity():
    return {
        "identity_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "name": "Leon Capeluto",
        "display_name": "Big Leon",
        "state": "CONFIRMED",
        "anchor_ids": ["face1", "face2"],
        "candidate_ids": ["face3"],
        "negative_ids": [],
        "version_id": 5,
        "merged_into": None,
    }


# ---------------------------------------------------------------------------
# shadow_write_photo
# ---------------------------------------------------------------------------


class TestShadowWritePhoto:
    def test_writes_photo_to_supabase(self, mock_supabase_client, sample_photo):
        with patch("app.supabase_data.get_supabase_client", return_value=mock_supabase_client):
            shadow_write_photo(sample_photo)

        mock_supabase_client.table.assert_called_once_with("photos")
        upsert_call = mock_supabase_client.table.return_value.upsert
        upsert_call.assert_called_once()
        row = upsert_call.call_args[0][0]
        assert row["photo_id"] == "abc123def456"
        assert row["path"] == "Image 001_compress.jpg"
        assert row["face_count"] == 3
        assert row["width"] == 800

    def test_no_client_returns_silently(self, sample_photo):
        with patch("app.supabase_data.get_supabase_client", return_value=None):
            # Should not raise
            shadow_write_photo(sample_photo)

    def test_exception_does_not_raise(self, mock_supabase_client, sample_photo):
        mock_supabase_client.table.return_value.upsert.return_value.execute.side_effect = Exception("Connection failed")
        with patch("app.supabase_data.get_supabase_client", return_value=mock_supabase_client):
            # Fire-and-forget: should not raise
            shadow_write_photo(sample_photo)

    def test_empty_photo_data(self, mock_supabase_client):
        with patch("app.supabase_data.get_supabase_client", return_value=mock_supabase_client):
            shadow_write_photo({})

        row = mock_supabase_client.table.return_value.upsert.call_args[0][0]
        assert row["photo_id"] == ""
        assert row["path"] == ""
        assert row["face_count"] == 0

    def test_face_count_from_face_ids(self, mock_supabase_client):
        photo = {"photo_id": "x", "path": "test.jpg", "face_ids": ["a", "b"]}
        with patch("app.supabase_data.get_supabase_client", return_value=mock_supabase_client):
            shadow_write_photo(photo)

        row = mock_supabase_client.table.return_value.upsert.call_args[0][0]
        assert row["face_count"] == 2


# ---------------------------------------------------------------------------
# shadow_write_identity
# ---------------------------------------------------------------------------


class TestShadowWriteIdentity:
    def test_writes_identity_to_supabase(self, mock_supabase_client, sample_identity):
        with patch("app.supabase_data.get_supabase_client", return_value=mock_supabase_client):
            shadow_write_identity(sample_identity)

        mock_supabase_client.table.assert_called_once_with("identities")
        upsert_call = mock_supabase_client.table.return_value.upsert
        upsert_call.assert_called_once()
        row = upsert_call.call_args[0][0]
        assert row["identity_id"] == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        assert row["name"] == "Leon Capeluto"
        assert row["display_name"] == "Big Leon"
        assert row["state"] == "CONFIRMED"
        assert row["version_id"] == 5

    def test_no_client_returns_silently(self, sample_identity):
        with patch("app.supabase_data.get_supabase_client", return_value=None):
            shadow_write_identity(sample_identity)

    def test_exception_does_not_raise(self, mock_supabase_client, sample_identity):
        mock_supabase_client.table.return_value.upsert.return_value.execute.side_effect = Exception("Timeout")
        with patch("app.supabase_data.get_supabase_client", return_value=mock_supabase_client):
            shadow_write_identity(sample_identity)

    def test_empty_identity_data(self, mock_supabase_client):
        with patch("app.supabase_data.get_supabase_client", return_value=mock_supabase_client):
            shadow_write_identity({})

        row = mock_supabase_client.table.return_value.upsert.call_args[0][0]
        assert row["identity_id"] == ""
        assert row["state"] == "INBOX"
        assert row["version_id"] == 1

    def test_merged_into_passed_through(self, mock_supabase_client):
        ident = {
            "identity_id": "abc",
            "name": "Old Name",
            "state": "CONFIRMED",
            "merged_into": "def-456",
        }
        with patch("app.supabase_data.get_supabase_client", return_value=mock_supabase_client):
            shadow_write_identity(ident)

        row = mock_supabase_client.table.return_value.upsert.call_args[0][0]
        assert row["merged_into"] == "def-456"


# ---------------------------------------------------------------------------
# shadow_write_photos_batch
# ---------------------------------------------------------------------------


class TestShadowWritePhotosBatch:
    def test_batch_write(self, mock_supabase_client):
        photos = [{"photo_id": f"photo_{i}", "path": f"img_{i}.jpg", "face_ids": []} for i in range(5)]
        with patch("app.supabase_data.get_supabase_client", return_value=mock_supabase_client):
            count = shadow_write_photos_batch(photos)

        assert count == 5

    def test_no_client_returns_zero(self):
        with patch("app.supabase_data.get_supabase_client", return_value=None):
            count = shadow_write_photos_batch([{"photo_id": "x", "path": "y"}])
        assert count == 0

    def test_empty_list(self, mock_supabase_client):
        with patch("app.supabase_data.get_supabase_client", return_value=mock_supabase_client):
            count = shadow_write_photos_batch([])
        assert count == 0
        mock_supabase_client.table.assert_not_called()

    def test_batch_error_partial_write(self, mock_supabase_client):
        """If one batch fails, earlier batches still count."""
        photos = [
            {"photo_id": f"photo_{i}", "path": f"img_{i}.jpg", "face_ids": []}
            for i in range(150)  # Will be split into 2 batches (100 + 50)
        ]
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                raise Exception("Batch 2 failed")

        mock_supabase_client.table.return_value.upsert.return_value.execute.side_effect = side_effect
        with patch("app.supabase_data.get_supabase_client", return_value=mock_supabase_client):
            count = shadow_write_photos_batch(photos)

        # First batch of 100 succeeded, second batch of 50 failed
        assert count == 100


# ---------------------------------------------------------------------------
# shadow_write_identities_batch
# ---------------------------------------------------------------------------


class TestShadowWriteIdentitiesBatch:
    def test_batch_write(self, mock_supabase_client):
        identities = [{"identity_id": f"id_{i}", "name": f"Person {i}", "state": "INBOX"} for i in range(5)]
        with patch("app.supabase_data.get_supabase_client", return_value=mock_supabase_client):
            count = shadow_write_identities_batch(identities)

        assert count == 5

    def test_no_client_returns_zero(self):
        with patch("app.supabase_data.get_supabase_client", return_value=None):
            count = shadow_write_identities_batch([{"identity_id": "x", "name": "y"}])
        assert count == 0

    def test_empty_list(self, mock_supabase_client):
        with patch("app.supabase_data.get_supabase_client", return_value=mock_supabase_client):
            count = shadow_write_identities_batch([])
        assert count == 0
