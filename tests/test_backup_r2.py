"""Tests for R2 backup and restore scripts."""

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Backup script tests
# ---------------------------------------------------------------------------


class TestGetR2Client:
    """Tests for get_r2_client()."""

    def test_missing_env_vars_raises(self):
        from scripts.backup_to_r2 import get_r2_client

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(EnvironmentError, match="R2_ACCOUNT_ID"):
                get_r2_client()

    def test_partial_env_vars_raises(self):
        from scripts.backup_to_r2 import get_r2_client

        with patch.dict(
            os.environ,
            {"R2_ACCOUNT_ID": "acct", "R2_ACCESS_KEY_ID": "key"},
            clear=True,
        ):
            with pytest.raises(EnvironmentError, match="R2_SECRET_ACCESS_KEY"):
                get_r2_client()

    def test_creates_client_with_correct_endpoint(self):
        from scripts.backup_to_r2 import get_r2_client

        env = {
            "R2_ACCOUNT_ID": "test-acct",
            "R2_ACCESS_KEY_ID": "test-key",
            "R2_SECRET_ACCESS_KEY": "test-secret",
        }
        with patch.dict(os.environ, env, clear=True), patch("boto3.client") as mock_client:
            get_r2_client()

        mock_client.assert_called_once_with(
            "s3",
            endpoint_url="https://test-acct.r2.cloudflarestorage.com",
            aws_access_key_id="test-key",
            aws_secret_access_key="test-secret",
        )


class TestGetBucketName:
    """Tests for get_bucket_name()."""

    def test_missing_bucket_raises(self):
        from scripts.backup_to_r2 import get_bucket_name

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(EnvironmentError, match="R2_BUCKET_NAME"):
                get_bucket_name()

    def test_returns_bucket_name(self):
        from scripts.backup_to_r2 import get_bucket_name

        with patch.dict(os.environ, {"R2_BUCKET_NAME": "my-bucket"}, clear=True):
            assert get_bucket_name() == "my-bucket"


class TestBackupFiles:
    """Tests for backup_files()."""

    def test_generates_correct_r2_keys(self, tmp_path):
        from scripts.backup_to_r2 import backup_files

        # Create test files
        (tmp_path / "identities.json").write_text("{}")
        (tmp_path / "photo_index.json").write_text("{}")

        client = MagicMock()
        success, skipped = backup_files(client, "bucket", tmp_path, dry_run=False)

        # Check put_object was called with correct keys
        calls = client.put_object.call_args_list
        keys_uploaded = {c.kwargs["Key"] for c in calls}

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assert f"backups/{today}/identities.json" in keys_uploaded
        assert f"backups/{today}/photo_index.json" in keys_uploaded
        assert success == 2

    def test_missing_files_skipped_with_warning(self, tmp_path, capsys):
        from scripts.backup_to_r2 import backup_files

        # No files exist
        client = MagicMock()
        success, skipped = backup_files(client, "bucket", tmp_path, dry_run=False)

        assert skipped == 5  # All 5 files missing
        assert success == 0
        output = capsys.readouterr().out
        assert "WARNING" in output
        assert "identities.json" in output

    def test_dry_run_does_not_upload(self, tmp_path):
        from scripts.backup_to_r2 import backup_files

        (tmp_path / "identities.json").write_text("{}")
        (tmp_path / "embeddings.npy").write_bytes(b"\x00" * 100)

        client = MagicMock()
        success, skipped = backup_files(client, "bucket", tmp_path, dry_run=True)

        client.put_object.assert_not_called()
        assert success == 2

    def test_all_five_files_backed_up(self, tmp_path):
        from scripts.backup_to_r2 import BACKUP_FILES, backup_files

        for f in BACKUP_FILES:
            (tmp_path / f).write_text("{}")

        client = MagicMock()
        success, skipped = backup_files(client, "bucket", tmp_path, dry_run=False)

        assert success == 5
        assert skipped == 0
        assert client.put_object.call_count == 5


class TestListBackupDates:
    """Tests for list_backup_dates()."""

    def test_lists_dates_sorted(self):
        from scripts.backup_to_r2 import list_backup_dates

        client = MagicMock()
        paginator = MagicMock()
        client.get_paginator.return_value = paginator
        paginator.paginate.return_value = [
            {
                "CommonPrefixes": [
                    {"Prefix": "backups/2026-03-05/"},
                    {"Prefix": "backups/2026-03-07/"},
                    {"Prefix": "backups/2026-03-06/"},
                ]
            }
        ]

        dates = list_backup_dates(client, "bucket")
        assert dates == ["2026-03-05", "2026-03-06", "2026-03-07"]

    def test_empty_bucket(self):
        from scripts.backup_to_r2 import list_backup_dates

        client = MagicMock()
        paginator = MagicMock()
        client.get_paginator.return_value = paginator
        paginator.paginate.return_value = [{}]

        dates = list_backup_dates(client, "bucket")
        assert dates == []


class TestPruneOldBackups:
    """Tests for prune_old_backups()."""

    def test_prunes_old_backups(self):
        from scripts.backup_to_r2 import prune_old_backups

        old_date = (datetime.now(timezone.utc) - timedelta(days=35)).strftime("%Y-%m-%d")
        recent_date = (datetime.now(timezone.utc) - timedelta(days=5)).strftime("%Y-%m-%d")

        client = MagicMock()
        # Mock list_backup_dates via paginator
        list_paginator = MagicMock()
        list_paginator.paginate.return_value = [
            {
                "CommonPrefixes": [
                    {"Prefix": f"backups/{old_date}/"},
                    {"Prefix": f"backups/{recent_date}/"},
                ]
            }
        ]

        # Mock object listing for deletion
        delete_paginator = MagicMock()
        delete_paginator.paginate.return_value = [
            {
                "Contents": [
                    {"Key": f"backups/{old_date}/identities.json"},
                    {"Key": f"backups/{old_date}/photo_index.json"},
                ]
            }
        ]

        # First paginator call = list dates, second = list objects for deletion
        client.get_paginator.return_value = list_paginator

        # We need different paginators for different calls
        call_count = [0]
        original_paginate = None

        def paginator_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return list_paginator
            return delete_paginator

        client.get_paginator.side_effect = paginator_side_effect

        pruned = prune_old_backups(client, "bucket", dry_run=False)
        assert pruned == 1
        client.delete_objects.assert_called_once()

    def test_prune_dry_run_does_not_delete(self):
        from scripts.backup_to_r2 import prune_old_backups

        old_date = (datetime.now(timezone.utc) - timedelta(days=35)).strftime("%Y-%m-%d")

        client = MagicMock()
        paginator = MagicMock()
        client.get_paginator.return_value = paginator
        paginator.paginate.return_value = [{"CommonPrefixes": [{"Prefix": f"backups/{old_date}/"}]}]

        pruned = prune_old_backups(client, "bucket", dry_run=True)
        assert pruned == 1
        client.delete_objects.assert_not_called()

    def test_no_old_backups_to_prune(self):
        from scripts.backup_to_r2 import prune_old_backups

        recent = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        client = MagicMock()
        paginator = MagicMock()
        client.get_paginator.return_value = paginator
        paginator.paginate.return_value = [{"CommonPrefixes": [{"Prefix": f"backups/{recent}/"}]}]

        pruned = prune_old_backups(client, "bucket", dry_run=False)
        assert pruned == 0


# ---------------------------------------------------------------------------
# Restore script tests
# ---------------------------------------------------------------------------


class TestRestoreBackup:
    """Tests for restore_backup()."""

    def test_restores_files_to_data_dir(self, tmp_path):
        from scripts.restore_from_r2 import restore_backup

        client = MagicMock()
        paginator = MagicMock()
        client.get_paginator.return_value = paginator
        paginator.paginate.return_value = [
            {
                "Contents": [
                    {"Key": "backups/2026-03-07/identities.json", "Size": 1024},
                    {"Key": "backups/2026-03-07/embeddings.npy", "Size": 2048},
                ]
            }
        ]

        # Mock get_object responses
        body1 = MagicMock()
        body1.read.return_value = b'{"identities": {}}'
        body2 = MagicMock()
        body2.read.return_value = b"\x00" * 100

        client.get_object.side_effect = [
            {"Body": body1},
            {"Body": body2},
        ]

        restored = restore_backup(client, "bucket", "2026-03-07", tmp_path)
        assert restored == 2
        assert (tmp_path / "identities.json").exists()
        assert (tmp_path / "embeddings.npy").exists()

    def test_creates_data_dir_if_missing(self, tmp_path):
        from scripts.restore_from_r2 import restore_backup

        dest = tmp_path / "nonexistent" / "subdir"

        client = MagicMock()
        paginator = MagicMock()
        client.get_paginator.return_value = paginator
        paginator.paginate.return_value = [
            {
                "Contents": [
                    {"Key": "backups/2026-03-07/identities.json", "Size": 512},
                ]
            }
        ]

        body = MagicMock()
        body.read.return_value = b"{}"
        client.get_object.return_value = {"Body": body}

        restored = restore_backup(client, "bucket", "2026-03-07", dest)
        assert restored == 1
        assert dest.exists()

    def test_empty_backup_returns_zero(self, tmp_path):
        from scripts.restore_from_r2 import restore_backup

        client = MagicMock()
        paginator = MagicMock()
        client.get_paginator.return_value = paginator
        paginator.paginate.return_value = [{}]

        restored = restore_backup(client, "bucket", "2026-03-07", tmp_path)
        assert restored == 0


class TestBackupFilesList:
    """Verify the backup files list contains expected files."""

    def test_backup_files_contains_critical_files(self):
        from scripts.backup_to_r2 import BACKUP_FILES

        assert "identities.json" in BACKUP_FILES
        assert "photo_index.json" in BACKUP_FILES
        assert "embeddings.npy" in BACKUP_FILES
        assert "date_labels.json" in BACKUP_FILES
        assert "photo_locations.json" in BACKUP_FILES
        assert len(BACKUP_FILES) == 5
