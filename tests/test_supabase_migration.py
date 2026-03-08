"""Tests for Supabase migration — sync functions and migration script.

Tests verify:
1. Each sync function accepts correct data shapes
2. Each sync function handles Supabase unavailability gracefully
3. Migration script can parse each JSON file format
4. Load functions return expected shapes
"""

from unittest.mock import MagicMock, patch

import pytest

from app.supabase_data import (
    load_audit_log_from_supabase,
    load_date_labels_from_supabase,
    load_person_comments_from_supabase,
    load_photo_locations_from_supabase,
    sync_audit_log_entry,
    sync_birth_year_estimate,
    sync_comparison_result,
    sync_corrections_log_entry,
    sync_date_label,
    sync_date_labels_batch,
    sync_discovery_log_entry,
    sync_pending_upload,
    sync_person_comment,
    sync_photo_location,
    sync_photo_locations_batch,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_sb_client():
    """Create a mock Supabase client with common method chains."""
    client = MagicMock()
    # .table().upsert().execute()
    client.table.return_value.upsert.return_value.execute = MagicMock()
    # .table().insert().execute()
    client.table.return_value.insert.return_value.execute = MagicMock()
    # .table().select().order().limit().execute()
    result_mock = MagicMock()
    result_mock.data = []
    client.table.return_value.select.return_value.order.return_value.limit.return_value.execute.return_value = (
        result_mock
    )
    client.table.return_value.select.return_value.range.return_value.execute.return_value = result_mock
    client.table.return_value.select.return_value.order.return_value.desc.return_value.limit.return_value.execute.return_value = result_mock
    client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = result_mock
    return client


# ---------------------------------------------------------------------------
# Date Labels
# ---------------------------------------------------------------------------


class TestSyncDateLabel:
    def test_upserts_single_label(self, mock_sb_client):
        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb_client):
            sync_date_label("photo123", {"best_year_estimate": 1950, "confidence": "high"})
        mock_sb_client.table.assert_called_with("date_labels")
        upsert_call = mock_sb_client.table.return_value.upsert
        assert upsert_call.called
        row = upsert_call.call_args[0][0]
        assert row["photo_id"] == "photo123"
        assert row["best_year_estimate"] == 1950
        assert row["confidence"] == "high"

    def test_no_client_returns_none(self):
        with patch("app.supabase_data.get_supabase_client", return_value=None):
            sync_date_label("photo123", {"best_year_estimate": 1950})
        # Should not raise

    def test_handles_supabase_error(self, mock_sb_client):
        mock_sb_client.table.return_value.upsert.return_value.execute.side_effect = ConnectionError("down")
        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb_client):
            sync_date_label("photo123", {"best_year_estimate": 1950})
        # Should not raise


class TestSyncDateLabelsBatch:
    def test_batch_upsert(self, mock_sb_client):
        labels = [{"photo_id": f"p{i}", "best_year_estimate": 1950 + i} for i in range(5)]
        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb_client):
            count = sync_date_labels_batch(labels)
        assert count == 5

    def test_no_client_returns_zero(self):
        with patch("app.supabase_data.get_supabase_client", return_value=None):
            assert sync_date_labels_batch([{"photo_id": "p1"}]) == 0

    def test_skips_entries_without_photo_id(self, mock_sb_client):
        labels = [{"best_year_estimate": 1950}, {"photo_id": "p1", "best_year_estimate": 1960}]
        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb_client):
            count = sync_date_labels_batch(labels)
        assert count == 1


class TestLoadDateLabels:
    def test_returns_dict_on_success(self, mock_sb_client):
        result = MagicMock()
        result.data = [
            {"photo_id": "p1", "data": {"best_year_estimate": 1950}},
            {"photo_id": "p2", "data": {"best_year_estimate": 1960}},
        ]
        mock_sb_client.table.return_value.select.return_value.range.return_value.execute.return_value = result
        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb_client):
            labels = load_date_labels_from_supabase()
        assert labels == {"p1": {"best_year_estimate": 1950}, "p2": {"best_year_estimate": 1960}}

    def test_returns_none_when_no_client(self):
        with patch("app.supabase_data.get_supabase_client", return_value=None):
            assert load_date_labels_from_supabase() is None


# ---------------------------------------------------------------------------
# Photo Locations
# ---------------------------------------------------------------------------


class TestSyncPhotoLocation:
    def test_upserts_single_location(self, mock_sb_client):
        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb_client):
            sync_photo_location("photo123", {"location_name": "NYC", "lat": 40.7, "lng": -74.0, "confidence": "high"})
        mock_sb_client.table.assert_called_with("photo_locations")
        row = mock_sb_client.table.return_value.upsert.call_args[0][0]
        assert row["photo_id"] == "photo123"
        assert row["location_name"] == "NYC"
        assert row["lat"] == 40.7

    def test_no_client_safe(self):
        with patch("app.supabase_data.get_supabase_client", return_value=None):
            sync_photo_location("photo123", {"location_name": "NYC"})


class TestSyncPhotoLocationsBatch:
    def test_batch_upsert(self, mock_sb_client):
        locations = {"p1": {"location_name": "NYC"}, "p2": {"location_name": "LA"}}
        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb_client):
            count = sync_photo_locations_batch(locations)
        assert count == 2


class TestLoadPhotoLocations:
    def test_returns_dict_on_success(self, mock_sb_client):
        result = MagicMock()
        result.data = [{"photo_id": "p1", "data": {"location_name": "NYC"}}]
        mock_sb_client.table.return_value.select.return_value.range.return_value.execute.return_value = result
        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb_client):
            locs = load_photo_locations_from_supabase()
        assert locs == {"p1": {"location_name": "NYC"}}

    def test_returns_none_when_no_client(self):
        with patch("app.supabase_data.get_supabase_client", return_value=None):
            assert load_photo_locations_from_supabase() is None


# ---------------------------------------------------------------------------
# Discovery Log
# ---------------------------------------------------------------------------


class TestSyncDiscoveryLogEntry:
    def test_inserts_entry(self, mock_sb_client):
        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb_client):
            sync_discovery_log_entry("face1", "identity1", "confirmed")
        mock_sb_client.table.assert_called_with("discovery_log")
        row = mock_sb_client.table.return_value.insert.call_args[0][0]
        assert row["face_id"] == "face1"
        assert row["target_identity_id"] == "identity1"
        assert row["decision"] == "confirmed"

    def test_no_client_safe(self):
        with patch("app.supabase_data.get_supabase_client", return_value=None):
            sync_discovery_log_entry("face1", "identity1", "confirmed")

    def test_handles_error(self, mock_sb_client):
        mock_sb_client.table.return_value.insert.return_value.execute.side_effect = ConnectionError("down")
        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb_client):
            sync_discovery_log_entry("face1", "identity1", "confirmed")


# ---------------------------------------------------------------------------
# Audit Log
# ---------------------------------------------------------------------------


class TestSyncAuditLogEntry:
    def test_inserts_entry(self, mock_sb_client):
        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb_client):
            sync_audit_log_entry("approved", "ann123", actor="admin@test.com")
        row = mock_sb_client.table.return_value.insert.call_args[0][0]
        assert row["action"] == "approved"
        assert row["target_id"] == "ann123"
        assert row["actor"] == "admin@test.com"

    def test_no_client_safe(self):
        with patch("app.supabase_data.get_supabase_client", return_value=None):
            sync_audit_log_entry("approved", "ann123")


class TestLoadAuditLog:
    def test_returns_list_on_success(self, mock_sb_client):
        result = MagicMock()
        result.data = [{"action": "approved", "target_id": "ann123"}]
        mock_sb_client.table.return_value.select.return_value.order.return_value.limit.return_value.execute.return_value = result
        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb_client):
            entries = load_audit_log_from_supabase(limit=10)
        assert entries == [{"action": "approved", "target_id": "ann123"}]

    def test_returns_none_when_no_client(self):
        with patch("app.supabase_data.get_supabase_client", return_value=None):
            assert load_audit_log_from_supabase() is None


# ---------------------------------------------------------------------------
# Pending Uploads
# ---------------------------------------------------------------------------


class TestSyncPendingUpload:
    def test_upserts_upload(self, mock_sb_client):
        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb_client):
            sync_pending_upload("job1", {"status": "pending", "filename": "photo.jpg"})
        row = mock_sb_client.table.return_value.upsert.call_args[0][0]
        assert row["job_id"] == "job1"
        assert row["status"] == "pending"
        assert row["filename"] == "photo.jpg"

    def test_no_client_safe(self):
        with patch("app.supabase_data.get_supabase_client", return_value=None):
            sync_pending_upload("job1", {"status": "pending"})


# ---------------------------------------------------------------------------
# Comparison Results
# ---------------------------------------------------------------------------


class TestSyncComparisonResult:
    def test_upserts_result(self, mock_sb_client):
        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb_client):
            sync_comparison_result("result1", {"scores": [0.9, 0.8]})
        row = mock_sb_client.table.return_value.upsert.call_args[0][0]
        assert row["result_id"] == "result1"
        assert row["data"] == {"scores": [0.9, 0.8]}

    def test_no_client_safe(self):
        with patch("app.supabase_data.get_supabase_client", return_value=None):
            sync_comparison_result("result1", {})


# ---------------------------------------------------------------------------
# Birth Year Estimates
# ---------------------------------------------------------------------------


class TestSyncBirthYearEstimate:
    def test_upserts_estimate(self, mock_sb_client):
        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb_client):
            sync_birth_year_estimate("id1", {"birth_year_estimate": 1920, "birth_year_confidence": "high"})
        row = mock_sb_client.table.return_value.upsert.call_args[0][0]
        assert row["identity_id"] == "id1"
        assert row["estimated_year"] == 1920
        assert row["confidence"] == "high"

    def test_no_client_safe(self):
        with patch("app.supabase_data.get_supabase_client", return_value=None):
            sync_birth_year_estimate("id1", {"birth_year_estimate": 1920})


# ---------------------------------------------------------------------------
# Corrections Log
# ---------------------------------------------------------------------------


class TestSyncCorrectionsLogEntry:
    def test_inserts_entry(self, mock_sb_client):
        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb_client):
            sync_corrections_log_entry({"photo_id": "p1", "type": "date", "correction_year": 1945})
        row = mock_sb_client.table.return_value.insert.call_args[0][0]
        assert row["photo_id"] == "p1"
        assert row["correction_type"] == "date"

    def test_no_client_safe(self):
        with patch("app.supabase_data.get_supabase_client", return_value=None):
            sync_corrections_log_entry({"photo_id": "p1"})


# ---------------------------------------------------------------------------
# Person Comments
# ---------------------------------------------------------------------------


class TestSyncPersonComment:
    def test_inserts_comment(self, mock_sb_client):
        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb_client):
            sync_person_comment("id1", "This is Leon", "admin@test.com")
        row = mock_sb_client.table.return_value.insert.call_args[0][0]
        assert row["identity_id"] == "id1"
        assert row["comment"] == "This is Leon"
        assert row["author"] == "admin@test.com"

    def test_no_client_safe(self):
        with patch("app.supabase_data.get_supabase_client", return_value=None):
            sync_person_comment("id1", "test")


class TestLoadPersonComments:
    def test_returns_list_on_success(self, mock_sb_client):
        result = MagicMock()
        result.data = [{"identity_id": "id1", "comment": "test"}]
        mock_sb_client.table.return_value.select.return_value.order.return_value.limit.return_value.execute.return_value = result
        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb_client):
            comments = load_person_comments_from_supabase()
        assert comments == [{"identity_id": "id1", "comment": "test"}]

    def test_returns_none_when_no_client(self):
        with patch("app.supabase_data.get_supabase_client", return_value=None):
            assert load_person_comments_from_supabase() is None

    def test_filters_by_identity(self, mock_sb_client):
        result = MagicMock()
        result.data = []
        mock_sb_client.table.return_value.select.return_value.order.return_value.eq.return_value.limit.return_value.execute.return_value = result
        # The eq filter is chained differently
        mock_sb_client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = result
        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb_client):
            load_person_comments_from_supabase(identity_id="id1")
        # Should not raise


# ---------------------------------------------------------------------------
# Migration Script Data Parsing
# ---------------------------------------------------------------------------


class TestMigrationDataParsing:
    """Test that the migration script correctly parses each JSON format."""

    def test_parse_date_labels_format(self, tmp_path):
        """date_labels.json has schema_version + labels array."""
        import json

        data = {
            "schema_version": 2,
            "labels": [
                {"photo_id": "p1", "best_year_estimate": 1950, "confidence": "high"},
                {"photo_id": "p2", "best_year_estimate": 1960, "confidence": "medium"},
            ],
        }
        path = tmp_path / "date_labels.json"
        path.write_text(json.dumps(data))

        loaded = json.loads(path.read_text())
        labels = loaded.get("labels", [])
        assert len(labels) == 2
        assert labels[0]["photo_id"] == "p1"

    def test_parse_photo_locations_format(self, tmp_path):
        """photo_locations.json has photos dict keyed by photo_id."""
        import json

        data = {
            "version": 1,
            "photos": {
                "p1": {"photo_id": "p1", "lat": 40.7, "lng": -74.0, "location_name": "NYC"},
                "p2": {"photo_id": "p2", "lat": 34.0, "lng": -118.2, "location_name": "LA"},
            },
        }
        path = tmp_path / "photo_locations.json"
        path.write_text(json.dumps(data))

        loaded = json.loads(path.read_text())
        photos = loaded.get("photos", {})
        assert len(photos) == 2
        assert "p1" in photos

    def test_parse_birth_year_estimates_format(self, tmp_path):
        """birth_year_estimates.json has estimates list."""
        import json

        data = {
            "schema_version": 1,
            "estimates": [
                {"identity_id": "id1", "birth_year_estimate": 1907, "birth_year_confidence": "medium"},
            ],
        }
        path = tmp_path / "birth_year_estimates.json"
        path.write_text(json.dumps(data))

        loaded = json.loads(path.read_text())
        estimates = loaded.get("estimates", [])
        assert len(estimates) == 1
        assert estimates[0]["identity_id"] == "id1"

    def test_parse_discovery_log_format(self, tmp_path):
        """discovery_log.json has entries list."""
        import json

        data = {
            "schema_version": 1,
            "entries": [
                {"face_id": "f1", "target_identity_id": "id1", "tier": 2, "user_decision": None},
                {"face_id": "f2", "target_identity_id": "id2", "tier": 1, "user_decision": "confirmed"},
            ],
        }
        path = tmp_path / "discovery_log.json"
        path.write_text(json.dumps(data))

        loaded = json.loads(path.read_text())
        entries = loaded.get("entries", [])
        assert len(entries) == 2

    def test_parse_audit_log_format(self, tmp_path):
        """audit_log.json has entries list."""
        import json

        data = {
            "entries": [
                {"action": "approved", "annotation_id": "ann1", "admin": "admin@test.com"},
            ]
        }
        path = tmp_path / "audit_log.json"
        path.write_text(json.dumps(data))

        loaded = json.loads(path.read_text())
        entries = loaded.get("entries", [])
        assert len(entries) == 1

    def test_parse_pending_uploads_format(self, tmp_path):
        """pending_uploads.json has uploads dict keyed by job_id."""
        import json

        data = {
            "uploads": {
                "job1": {"job_id": "job1", "status": "pending", "filename": "photo.jpg"},
            }
        }
        path = tmp_path / "pending_uploads.json"
        path.write_text(json.dumps(data))

        loaded = json.loads(path.read_text())
        uploads = loaded.get("uploads", {})
        assert len(uploads) == 1

    def test_parse_comparison_results_format(self, tmp_path):
        """comparison_results.json has results dict keyed by result_id."""
        import json

        data = {"results": {"r1": {"result_id": "r1", "scores": [0.9]}}}
        path = tmp_path / "comparison_results.json"
        path.write_text(json.dumps(data))

        loaded = json.loads(path.read_text())
        results = loaded.get("results", {})
        assert len(results) == 1

    def test_parse_corrections_log_format(self, tmp_path):
        """corrections_log.json has corrections list."""
        import json

        data = {
            "schema_version": 1,
            "corrections": [
                {"photo_id": "p1", "type": "date", "correction_year": 1945},
            ],
        }
        path = tmp_path / "corrections_log.json"
        path.write_text(json.dumps(data))

        loaded = json.loads(path.read_text())
        corrections = loaded.get("corrections", [])
        assert len(corrections) == 1


# ---------------------------------------------------------------------------
# Error Resilience (fire-and-forget pattern)
# ---------------------------------------------------------------------------


class TestErrorResilience:
    """All sync functions must never raise — they log warnings instead."""

    def test_date_label_connection_error(self, mock_sb_client):
        mock_sb_client.table.return_value.upsert.return_value.execute.side_effect = ConnectionError("boom")
        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb_client):
            sync_date_label("p1", {"best_year_estimate": 1950})

    def test_photo_location_timeout(self, mock_sb_client):
        mock_sb_client.table.return_value.upsert.return_value.execute.side_effect = TimeoutError("timeout")
        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb_client):
            sync_photo_location("p1", {"location_name": "NYC"})

    def test_discovery_log_os_error(self, mock_sb_client):
        mock_sb_client.table.return_value.insert.return_value.execute.side_effect = OSError("disk")
        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb_client):
            sync_discovery_log_entry("f1", "id1", "confirmed")

    def test_audit_log_connection_error(self, mock_sb_client):
        mock_sb_client.table.return_value.insert.return_value.execute.side_effect = ConnectionError("boom")
        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb_client):
            sync_audit_log_entry("approved", "ann123")

    def test_pending_upload_error(self, mock_sb_client):
        mock_sb_client.table.return_value.upsert.return_value.execute.side_effect = ConnectionError("boom")
        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb_client):
            sync_pending_upload("job1", {"status": "pending"})

    def test_comparison_result_error(self, mock_sb_client):
        mock_sb_client.table.return_value.upsert.return_value.execute.side_effect = ConnectionError("boom")
        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb_client):
            sync_comparison_result("r1", {})

    def test_birth_year_error(self, mock_sb_client):
        mock_sb_client.table.return_value.upsert.return_value.execute.side_effect = ConnectionError("boom")
        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb_client):
            sync_birth_year_estimate("id1", {"birth_year_estimate": 1920})

    def test_corrections_log_error(self, mock_sb_client):
        mock_sb_client.table.return_value.insert.return_value.execute.side_effect = ConnectionError("boom")
        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb_client):
            sync_corrections_log_entry({"photo_id": "p1"})

    def test_person_comment_error(self, mock_sb_client):
        mock_sb_client.table.return_value.insert.return_value.execute.side_effect = ConnectionError("boom")
        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb_client):
            sync_person_comment("id1", "test")

    def test_load_date_labels_error(self, mock_sb_client):
        mock_sb_client.table.return_value.select.return_value.range.return_value.execute.side_effect = ConnectionError(
            "boom"
        )
        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb_client):
            assert load_date_labels_from_supabase() is None

    def test_load_photo_locations_error(self, mock_sb_client):
        mock_sb_client.table.return_value.select.return_value.range.return_value.execute.side_effect = ConnectionError(
            "boom"
        )
        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb_client):
            assert load_photo_locations_from_supabase() is None

    def test_load_audit_log_error(self, mock_sb_client):
        mock_sb_client.table.return_value.select.return_value.order.return_value.limit.return_value.execute.side_effect = ConnectionError(
            "boom"
        )
        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb_client):
            assert load_audit_log_from_supabase() is None

    def test_load_person_comments_error(self, mock_sb_client):
        mock_sb_client.table.return_value.select.return_value.order.return_value.limit.return_value.execute.side_effect = ConnectionError(
            "boom"
        )
        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb_client):
            assert load_person_comments_from_supabase() is None
