"""Tests for auto-backup volume function in init_railway_volume.py.

Verifies disk space handling and backup pruning behavior.
"""

import json
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest


def _create_test_data_dir(tmp_path):
    """Create a minimal data directory with files to back up."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "identities.json").write_text(
        json.dumps({"schema_version": 1, "identities": {}})
    )
    (data_dir / "photo_index.json").write_text(
        json.dumps({"schema_version": 1, "photos": {}, "face_to_photo": {}})
    )
    return data_dir


class TestAutoBackupPruning:
    """Verify that old backups are pruned BEFORE creating new ones."""

    def test_prunes_before_creating_new_backup(self, tmp_path):
        """Pruning should happen before new backup creation to prevent ENOSPC."""
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        from init_railway_volume import _auto_backup_volume

        data_dir = _create_test_data_dir(tmp_path)
        backup_root = data_dir / "auto_backups"
        backup_root.mkdir()

        # Create 6 existing backups (more than limit of 5)
        for i in range(6):
            d = backup_root / f"2026010{i}_120000"
            d.mkdir()
            (d / "identities.json").write_text("{}")

        result = _auto_backup_volume(data_dir)

        assert result is not None
        remaining = sorted(d.name for d in backup_root.iterdir() if d.is_dir())
        # Should keep last 4 old + 1 new = 5 total
        assert len(remaining) <= 5

    def test_handles_disk_full_gracefully(self, tmp_path):
        """If disk is full, backup should fail gracefully, not crash."""
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        from init_railway_volume import _auto_backup_volume

        data_dir = _create_test_data_dir(tmp_path)

        with patch("pathlib.Path.mkdir", side_effect=OSError(28, "No space left on device")):
            # Should not raise
            result = _auto_backup_volume(data_dir)
            assert result is None

    def test_creates_backup_of_existing_files(self, tmp_path):
        """Normal backup should copy all existing data files."""
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        from init_railway_volume import _auto_backup_volume

        data_dir = _create_test_data_dir(tmp_path)
        result = _auto_backup_volume(data_dir)

        assert result is not None
        backup_path = Path(result)
        assert (backup_path / "identities.json").exists()
        assert (backup_path / "photo_index.json").exists()

    def test_returns_none_when_no_files_to_backup(self, tmp_path):
        """If no data files exist, should return None."""
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        from init_railway_volume import _auto_backup_volume

        data_dir = tmp_path / "empty_data"
        data_dir.mkdir()
        result = _auto_backup_volume(data_dir)
        assert result is None
