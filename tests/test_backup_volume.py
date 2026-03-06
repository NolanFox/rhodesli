"""Tests for scripts/backup_volume_to_r2.py — R2 volume backup."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# We need to patch env vars and imports before importing the module
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def data_dir(tmp_path):
    """Create a temporary data directory with sample files."""
    d = tmp_path / "data"
    d.mkdir()
    # identities.json
    (d / "identities.json").write_text(json.dumps({"identities": {}}))
    # photo_index.json
    (d / "photo_index.json").write_text(json.dumps({"photos": {}}))
    # embeddings.npy
    np.save(str(d / "embeddings.npy"), np.array([{"face_id": "test"}], dtype=object))
    # date_labels.json
    (d / "date_labels.json").write_text(json.dumps({"photo1": {"label": "1940s"}}))
    # photo_locations.json
    (d / "photo_locations.json").write_text(json.dumps({"photo1": {"location": "Rhodes"}}))
    return d


@pytest.fixture
def data_dir_partial(tmp_path):
    """Data directory with only some files."""
    d = tmp_path / "data"
    d.mkdir()
    (d / "identities.json").write_text(json.dumps({"identities": {}}))
    (d / "photo_index.json").write_text(json.dumps({"photos": {}}))
    # Missing: embeddings.npy, date_labels.json, photo_locations.json
    return d


# ---------------------------------------------------------------------------
# Test: File selection
# ---------------------------------------------------------------------------


class TestFileSelection:
    def test_all_files_found(self, data_dir):
        from scripts.backup_volume_to_r2 import get_files_to_backup

        files = get_files_to_backup(data_dir)
        names = [name for _, name in files]
        assert "identities.json" in names
        assert "photo_index.json" in names
        assert "embeddings.npy" in names
        assert "date_labels.json" in names
        assert "photo_locations.json" in names
        assert len(files) == 5

    def test_missing_files_skipped(self, data_dir_partial):
        from scripts.backup_volume_to_r2 import get_files_to_backup

        files = get_files_to_backup(data_dir_partial)
        names = [name for _, name in files]
        assert "identities.json" in names
        assert "photo_index.json" in names
        assert "embeddings.npy" not in names
        assert len(files) == 2

    def test_empty_dir(self, tmp_path):
        from scripts.backup_volume_to_r2 import get_files_to_backup

        empty = tmp_path / "empty"
        empty.mkdir()
        files = get_files_to_backup(empty)
        assert files == []

    def test_backup_files_list_is_complete(self):
        from scripts.backup_volume_to_r2 import BACKUP_FILES

        expected = [
            "identities.json",
            "photo_index.json",
            "embeddings.npy",
            "date_labels.json",
            "photo_locations.json",
        ]
        assert BACKUP_FILES == expected


# ---------------------------------------------------------------------------
# Test: R2 key generation
# ---------------------------------------------------------------------------


class TestKeyGeneration:
    def test_basic_key(self):
        from scripts.backup_volume_to_r2 import get_backup_key

        key = get_backup_key("2026-03-05", "identities.json")
        assert key == "backups/2026-03-05/identities.json"

    def test_npy_key(self):
        from scripts.backup_volume_to_r2 import get_backup_key

        key = get_backup_key("2026-01-01", "embeddings.npy")
        assert key == "backups/2026-01-01/embeddings.npy"

    def test_prefix_is_consistent(self):
        from scripts.backup_volume_to_r2 import BACKUP_PREFIX, get_backup_key

        key = get_backup_key("2026-03-05", "photo_index.json")
        assert key.startswith(f"{BACKUP_PREFIX}/")

    def test_different_dates_produce_different_keys(self):
        from scripts.backup_volume_to_r2 import get_backup_key

        k1 = get_backup_key("2026-03-01", "identities.json")
        k2 = get_backup_key("2026-03-02", "identities.json")
        assert k1 != k2


# ---------------------------------------------------------------------------
# Test: Pruning logic
# ---------------------------------------------------------------------------


class TestPruning:
    def _make_client(self, dates):
        """Create a mock S3 client that returns given date prefixes."""
        client = MagicMock()
        client.list_objects_v2.return_value = {
            "CommonPrefixes": [{"Prefix": f"backups/{d}/"} for d in dates],
        }
        return client

    def test_prune_old_dates(self):
        from scripts.backup_volume_to_r2 import prune_old_backups

        today = datetime.now(timezone.utc)
        old_date = (today - timedelta(days=10)).strftime("%Y-%m-%d")
        recent_date = (today - timedelta(days=2)).strftime("%Y-%m-%d")
        today_str = today.strftime("%Y-%m-%d")

        client = self._make_client([old_date, recent_date, today_str])
        # For the delete call, return contents
        client.list_objects_v2.side_effect = [
            # First call: list prefixes
            {"CommonPrefixes": [{"Prefix": f"backups/{d}/"} for d in [old_date, recent_date, today_str]]},
            # Second call: list objects for old_date
            {"Contents": [{"Key": f"backups/{old_date}/identities.json"}]},
        ]

        pruned = prune_old_backups(client, "test-bucket", retention_days=7, dry_run=False)
        assert pruned == 1

    def test_nothing_to_prune(self):
        from scripts.backup_volume_to_r2 import prune_old_backups

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")

        client = self._make_client([yesterday, today])
        pruned = prune_old_backups(client, "test-bucket", retention_days=7, dry_run=True)
        assert pruned == 0

    def test_prune_dry_run_does_not_delete(self):
        from scripts.backup_volume_to_r2 import prune_old_backups

        old_date = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%d")
        client = self._make_client([old_date])
        # For listing objects under the old prefix
        client.list_objects_v2.side_effect = [
            {"CommonPrefixes": [{"Prefix": f"backups/{old_date}/"}]},
            {"Contents": [{"Key": f"backups/{old_date}/test.json"}]},
        ]

        pruned = prune_old_backups(client, "test-bucket", retention_days=7, dry_run=True)
        assert pruned == 1
        # delete_objects should NOT have been called
        client.delete_objects.assert_not_called()

    def test_empty_backup_list(self):
        from scripts.backup_volume_to_r2 import prune_old_backups

        client = MagicMock()
        client.list_objects_v2.return_value = {}
        pruned = prune_old_backups(client, "test-bucket", retention_days=7, dry_run=True)
        assert pruned == 0

    def test_retention_days_configurable(self):
        from scripts.backup_volume_to_r2 import prune_old_backups

        today = datetime.now(timezone.utc)
        # 4 days old — should survive 7-day retention but not 3-day
        date_4d = (today - timedelta(days=4)).strftime("%Y-%m-%d")

        client = self._make_client([date_4d])
        # 7-day retention: should NOT prune
        pruned = prune_old_backups(client, "test-bucket", retention_days=7, dry_run=True)
        assert pruned == 0

        # 3-day retention: should prune
        client2 = self._make_client([date_4d])
        client2.list_objects_v2.side_effect = [
            {"CommonPrefixes": [{"Prefix": f"backups/{date_4d}/"}]},
            {"Contents": [{"Key": f"backups/{date_4d}/test.json"}]},
        ]
        pruned = prune_old_backups(client2, "test-bucket", retention_days=3, dry_run=True)
        assert pruned == 1


# ---------------------------------------------------------------------------
# Test: List backup dates
# ---------------------------------------------------------------------------


class TestListBackupDates:
    def test_parses_dates(self):
        from scripts.backup_volume_to_r2 import list_backup_dates

        client = MagicMock()
        client.list_objects_v2.return_value = {
            "CommonPrefixes": [
                {"Prefix": "backups/2026-03-01/"},
                {"Prefix": "backups/2026-03-05/"},
                {"Prefix": "backups/2026-03-03/"},
            ]
        }
        dates = list_backup_dates(client, "test-bucket")
        assert dates == ["2026-03-01", "2026-03-03", "2026-03-05"]

    def test_ignores_invalid_dates(self):
        from scripts.backup_volume_to_r2 import list_backup_dates

        client = MagicMock()
        client.list_objects_v2.return_value = {
            "CommonPrefixes": [
                {"Prefix": "backups/2026-03-01/"},
                {"Prefix": "backups/not-a-date/"},
                {"Prefix": "backups/2026-13-99/"},
            ]
        }
        dates = list_backup_dates(client, "test-bucket")
        assert dates == ["2026-03-01"]

    def test_handles_api_error(self):
        from scripts.backup_volume_to_r2 import list_backup_dates

        client = MagicMock()
        client.list_objects_v2.side_effect = Exception("API error")
        dates = list_backup_dates(client, "test-bucket")
        assert dates == []


# ---------------------------------------------------------------------------
# Test: Delete backup date
# ---------------------------------------------------------------------------


class TestDeleteBackupDate:
    def test_delete_live(self):
        from scripts.backup_volume_to_r2 import delete_backup_date

        client = MagicMock()
        client.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "backups/2026-03-01/identities.json"},
                {"Key": "backups/2026-03-01/photo_index.json"},
            ]
        }
        deleted = delete_backup_date(client, "test-bucket", "2026-03-01", dry_run=False)
        assert deleted == 2
        client.delete_objects.assert_called_once()

    def test_delete_dry_run(self):
        from scripts.backup_volume_to_r2 import delete_backup_date

        client = MagicMock()
        client.list_objects_v2.return_value = {"Contents": [{"Key": "backups/2026-03-01/identities.json"}]}
        deleted = delete_backup_date(client, "test-bucket", "2026-03-01", dry_run=True)
        assert deleted == 1
        client.delete_objects.assert_not_called()

    def test_empty_prefix(self):
        from scripts.backup_volume_to_r2 import delete_backup_date

        client = MagicMock()
        client.list_objects_v2.return_value = {"Contents": []}
        deleted = delete_backup_date(client, "test-bucket", "2026-03-01", dry_run=False)
        assert deleted == 0


# ---------------------------------------------------------------------------
# Test: Full backup run (mocked R2)
# ---------------------------------------------------------------------------


class TestRunBackup:
    @patch("scripts.backup_volume_to_r2.can_write_r2", return_value=False)
    def test_skips_when_no_r2_creds(self, mock_can, data_dir):
        from scripts.backup_volume_to_r2 import run_backup

        result = run_backup(dry_run=True, data_dir=data_dir)
        assert len(result["errors"]) == 1
        assert "credentials" in result["errors"][0]

    @patch("scripts.backup_volume_to_r2.can_write_r2", return_value=True)
    def test_skips_when_no_files(self, mock_can, tmp_path):
        from scripts.backup_volume_to_r2 import run_backup

        empty = tmp_path / "empty"
        empty.mkdir()
        result = run_backup(dry_run=True, data_dir=empty)
        assert len(result["errors"]) == 1
        assert "No data files" in result["errors"][0]

    @patch("scripts.backup_volume_to_r2._get_r2_client")
    @patch("scripts.backup_volume_to_r2.R2_BUCKET_NAME", "test-bucket")
    @patch("scripts.backup_volume_to_r2.can_write_r2", return_value=True)
    def test_dry_run_uploads_nothing(self, mock_can, mock_client, data_dir):
        from scripts.backup_volume_to_r2 import run_backup

        client = MagicMock()
        client.list_objects_v2.return_value = {}
        mock_client.return_value = client

        result = run_backup(dry_run=True, data_dir=data_dir)
        assert result["uploaded"] == 5
        # put_object should NOT be called in dry-run
        client.put_object.assert_not_called()

    @patch("scripts.backup_volume_to_r2._get_r2_client")
    @patch("scripts.backup_volume_to_r2.R2_BUCKET_NAME", "test-bucket")
    @patch("scripts.backup_volume_to_r2.can_write_r2", return_value=True)
    def test_execute_uploads_files(self, mock_can, mock_client, data_dir):
        from scripts.backup_volume_to_r2 import run_backup

        client = MagicMock()
        client.list_objects_v2.return_value = {}
        mock_client.return_value = client

        result = run_backup(dry_run=False, data_dir=data_dir)
        assert result["uploaded"] == 5
        assert client.put_object.call_count == 5
        assert result["errors"] == []

    @patch("scripts.backup_volume_to_r2._get_r2_client")
    @patch("scripts.backup_volume_to_r2.R2_BUCKET_NAME", "test-bucket")
    @patch("scripts.backup_volume_to_r2.can_write_r2", return_value=True)
    def test_upload_error_captured(self, mock_can, mock_client, data_dir):
        from scripts.backup_volume_to_r2 import run_backup

        client = MagicMock()
        client.put_object.side_effect = Exception("Network error")
        client.list_objects_v2.return_value = {}
        mock_client.return_value = client

        result = run_backup(dry_run=False, data_dir=data_dir)
        assert result["uploaded"] == 0
        assert len(result["errors"]) == 5

    @patch("scripts.backup_volume_to_r2._get_r2_client")
    @patch("scripts.backup_volume_to_r2.R2_BUCKET_NAME", "test-bucket")
    @patch("scripts.backup_volume_to_r2.can_write_r2", return_value=True)
    def test_content_type_set_correctly(self, mock_can, mock_client, data_dir):
        from scripts.backup_volume_to_r2 import run_backup

        client = MagicMock()
        client.list_objects_v2.return_value = {}
        mock_client.return_value = client

        run_backup(dry_run=False, data_dir=data_dir)

        # Check that JSON files got application/json content type
        calls = client.put_object.call_args_list
        for call in calls:
            key = call[1]["Key"] if "Key" in call[1] else call[0][0]
            ct = call[1].get("ContentType", "")
            if key.endswith(".json"):
                assert ct == "application/json"
            elif key.endswith(".npy"):
                assert ct == "application/octet-stream"
