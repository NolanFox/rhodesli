"""
Tests for deploy data safety gate (AD-134).

Verifies the triple protection in init_railway_volume.py:
- Protection A: Never-overwrite for user-modified files
- Protection B: Auto-backup before sync
- Protection C: Count-based safety gate

These tests prevent the 5th+ occurrence of deploy data loss.
"""

import json
import runpy
import sys
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def mock_volume(tmp_path):
    """Create a mock Railway volume with data directory."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def mock_bundle(tmp_path):
    """Create a mock Docker bundle directory."""
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    return bundle_dir


def _write_identities(path, confirmed=0, total=10):
    """Helper to create an identities.json file with specified counts."""
    identities = {}
    for i in range(total):
        state = "CONFIRMED" if i < confirmed else "INBOX"
        identities[f"id-{i:04d}"] = {
            "identity_id": f"id-{i:04d}",
            "name": f"Person {i}",
            "state": state,
            "anchor_ids": [],
            "candidate_ids": [],
        }
    data = {"schema_version": 1, "identities": identities}
    with open(path, "w") as f:
        json.dump(data, f)


def _write_photo_index(path, photo_count=10):
    """Helper to create a photo_index.json with specified photo count."""
    photos = {}
    for i in range(photo_count):
        photos[f"photo-{i:04d}"] = {
            "path": f"raw_photos/photo_{i}.jpg",
            "face_ids": [f"photo_{i}:face0"],
        }
    data = {"schema_version": 1, "photos": photos, "face_to_photo": {}}
    with open(path, "w") as f:
        json.dump(data, f)


class TestCountConfirmedIdentities:
    """Tests for _count_confirmed_identities helper."""

    def test_counts_confirmed(self, tmp_path):
        from scripts.init_railway_volume import _count_confirmed_identities

        path = tmp_path / "identities.json"
        _write_identities(path, confirmed=5, total=20)
        assert _count_confirmed_identities(path) == 5

    def test_counts_zero_confirmed(self, tmp_path):
        from scripts.init_railway_volume import _count_confirmed_identities

        path = tmp_path / "identities.json"
        _write_identities(path, confirmed=0, total=10)
        assert _count_confirmed_identities(path) == 0


class TestInitRailwayVolumeBootstrap:
    def test_script_bootstraps_project_root_for_core_imports(self, monkeypatch):
        script_path = Path("scripts/init_railway_volume.py").resolve()
        project_root = str(script_path.parent.parent)

        filtered_path = [p for p in sys.path if Path(p or ".").resolve() != Path(project_root).resolve()]
        monkeypatch.setattr(sys, "path", filtered_path)

        runpy.run_path(str(script_path), run_name="scripts.init_railway_volume_bootstrap_test")

        assert sys.path[0] == project_root

    def test_returns_negative_on_missing_file(self, tmp_path):
        from scripts.init_railway_volume import _count_confirmed_identities

        path = tmp_path / "nonexistent.json"
        assert _count_confirmed_identities(path) == -1

    def test_returns_negative_on_corrupt_file(self, tmp_path):
        from scripts.init_railway_volume import _count_confirmed_identities

        path = tmp_path / "corrupt.json"
        path.write_text("not valid json{{{")
        assert _count_confirmed_identities(path) == -1


class TestIsVolumeUserModified:
    """Tests for _is_volume_user_modified — the safety gate check."""

    def test_blocks_when_volume_has_more_confirmed(self, mock_volume, mock_bundle):
        from scripts.init_railway_volume import _is_volume_user_modified

        # Volume: 55 confirmed (user made changes)
        _write_identities(mock_volume / "identities.json", confirmed=55, total=100)
        # Bundle: 46 confirmed (stale deploy data)
        _write_identities(mock_bundle / "identities.json", confirmed=46, total=100)

        with patch("scripts.init_railway_volume.BUNDLED_DATA", mock_bundle):
            assert _is_volume_user_modified(mock_volume, "identities.json") is True

    def test_allows_when_bundle_has_more_confirmed(self, mock_volume, mock_bundle):
        from scripts.init_railway_volume import _is_volume_user_modified

        # Volume: 46 confirmed
        _write_identities(mock_volume / "identities.json", confirmed=46, total=100)
        # Bundle: 55 confirmed (new data from pipeline)
        _write_identities(mock_bundle / "identities.json", confirmed=55, total=100)

        with patch("scripts.init_railway_volume.BUNDLED_DATA", mock_bundle):
            assert _is_volume_user_modified(mock_volume, "identities.json") is False

    def test_allows_when_counts_equal(self, mock_volume, mock_bundle):
        from scripts.init_railway_volume import _is_volume_user_modified

        _write_identities(mock_volume / "identities.json", confirmed=46, total=100)
        _write_identities(mock_bundle / "identities.json", confirmed=46, total=100)

        with patch("scripts.init_railway_volume.BUNDLED_DATA", mock_bundle):
            assert _is_volume_user_modified(mock_volume, "identities.json") is False

    def test_blocks_photo_index_more_photos(self, mock_volume, mock_bundle):
        from scripts.init_railway_volume import _is_volume_user_modified

        _write_photo_index(mock_volume / "photo_index.json", photo_count=300)
        _write_photo_index(mock_bundle / "photo_index.json", photo_count=271)

        with patch("scripts.init_railway_volume.BUNDLED_DATA", mock_bundle):
            assert _is_volume_user_modified(mock_volume, "photo_index.json") is True

    def test_allows_photo_index_fewer_photos(self, mock_volume, mock_bundle):
        from scripts.init_railway_volume import _is_volume_user_modified

        _write_photo_index(mock_volume / "photo_index.json", photo_count=271)
        _write_photo_index(mock_bundle / "photo_index.json", photo_count=300)

        with patch("scripts.init_railway_volume.BUNDLED_DATA", mock_bundle):
            assert _is_volume_user_modified(mock_volume, "photo_index.json") is False

    def test_allows_other_files(self, mock_volume, mock_bundle):
        from scripts.init_railway_volume import _is_volume_user_modified

        # Non-protected files always return False
        (mock_volume / "proposals.json").write_text("{}")
        (mock_bundle / "proposals.json").write_text("{}")

        with patch("scripts.init_railway_volume.BUNDLED_DATA", mock_bundle):
            assert _is_volume_user_modified(mock_volume, "proposals.json") is False

    def test_allows_when_volume_file_missing(self, mock_volume, mock_bundle):
        from scripts.init_railway_volume import _is_volume_user_modified

        _write_identities(mock_bundle / "identities.json", confirmed=46, total=100)
        # Volume file doesn't exist

        with patch("scripts.init_railway_volume.BUNDLED_DATA", mock_bundle):
            assert _is_volume_user_modified(mock_volume, "identities.json") is False

    def test_blocks_embeddings_more_entries(self, mock_volume, mock_bundle):
        """AD-165: embeddings.npy must be protected when volume has more entries."""
        import numpy as np
        from scripts.init_railway_volume import _is_volume_user_modified

        # Volume: 550 entries (upload added new faces)
        volume_embeddings = np.array([{"filename": f"img_{i}.jpg"} for i in range(550)], dtype=object)
        np.save(str(mock_volume / "embeddings.npy"), volume_embeddings)

        # Bundle: 547 entries (stale deploy data)
        bundle_embeddings = np.array([{"filename": f"img_{i}.jpg"} for i in range(547)], dtype=object)
        np.save(str(mock_bundle / "embeddings.npy"), bundle_embeddings)

        with patch("scripts.init_railway_volume.BUNDLED_DATA", mock_bundle):
            assert _is_volume_user_modified(mock_volume, "embeddings.npy") is True

    def test_allows_embeddings_fewer_entries(self, mock_volume, mock_bundle):
        """AD-165: embeddings.npy can be overwritten when bundle has more entries."""
        import numpy as np
        from scripts.init_railway_volume import _is_volume_user_modified

        # Volume: 547 entries
        volume_embeddings = np.array([{"filename": f"img_{i}.jpg"} for i in range(547)], dtype=object)
        np.save(str(mock_volume / "embeddings.npy"), volume_embeddings)

        # Bundle: 550 entries (pipeline generated more)
        bundle_embeddings = np.array([{"filename": f"img_{i}.jpg"} for i in range(550)], dtype=object)
        np.save(str(mock_bundle / "embeddings.npy"), bundle_embeddings)

        with patch("scripts.init_railway_volume.BUNDLED_DATA", mock_bundle):
            assert _is_volume_user_modified(mock_volume, "embeddings.npy") is False

    def test_allows_embeddings_equal_entries(self, mock_volume, mock_bundle):
        """AD-165: embeddings.npy can be overwritten when counts are equal."""
        import numpy as np
        from scripts.init_railway_volume import _is_volume_user_modified

        entries = np.array([{"filename": f"img_{i}.jpg"} for i in range(547)], dtype=object)
        np.save(str(mock_volume / "embeddings.npy"), entries)
        np.save(str(mock_bundle / "embeddings.npy"), entries)

        with patch("scripts.init_railway_volume.BUNDLED_DATA", mock_bundle):
            assert _is_volume_user_modified(mock_volume, "embeddings.npy") is False

    def test_blocks_date_labels_with_reanalyzed_entries(self, mock_volume, mock_bundle):
        """date_labels.json must be protected when volume has reanalyzed entries."""
        import json
        from scripts.init_railway_volume import _is_volume_user_modified

        # Volume: has a reanalyzed entry
        volume_data = {
            "labels": [
                {"photo_id": "test123", "estimated_decade": 1930, "reanalyzed_at": "2026-03-05T00:00:00Z"},
            ]
        }
        (mock_volume / "date_labels.json").write_text(json.dumps(volume_data))

        # Bundle: no reanalyzed entries
        bundle_data = {
            "labels": [
                {"photo_id": "test123", "estimated_decade": 1930},
            ]
        }
        (mock_bundle / "date_labels.json").write_text(json.dumps(bundle_data))

        with patch("scripts.init_railway_volume.BUNDLED_DATA", mock_bundle):
            assert _is_volume_user_modified(mock_volume, "date_labels.json") is True

    def test_allows_date_labels_without_reanalyzed(self, mock_volume, mock_bundle):
        """date_labels.json can be overwritten when no reanalyzed entries."""
        import json
        from scripts.init_railway_volume import _is_volume_user_modified

        data = {"labels": [{"photo_id": "test123", "estimated_decade": 1930}]}
        (mock_volume / "date_labels.json").write_text(json.dumps(data))
        (mock_bundle / "date_labels.json").write_text(json.dumps(data))

        with patch("scripts.init_railway_volume.BUNDLED_DATA", mock_bundle):
            assert _is_volume_user_modified(mock_volume, "date_labels.json") is False

    def test_blocks_photo_locations_with_reanalyzed_entries(self, mock_volume, mock_bundle):
        """photo_locations.json must be protected when volume has reanalyzed entries."""
        import json
        from scripts.init_railway_volume import _is_volume_user_modified

        volume_data = {
            "photos": {
                "test123": {"location_name": "Asheville", "reanalyzed_at": "2026-03-05T00:00:00Z"},
            }
        }
        (mock_volume / "photo_locations.json").write_text(json.dumps(volume_data))
        bundle_data = {"photos": {"test123": {"location_name": "Brooklyn"}}}
        (mock_bundle / "photo_locations.json").write_text(json.dumps(bundle_data))

        with patch("scripts.init_railway_volume.BUNDLED_DATA", mock_bundle):
            assert _is_volume_user_modified(mock_volume, "photo_locations.json") is True


class TestAutoBackupVolume:
    """Tests for _auto_backup_volume — pre-sync backup."""

    def test_creates_backup_directory(self, mock_volume):
        from scripts.init_railway_volume import _auto_backup_volume

        _write_identities(mock_volume / "identities.json", confirmed=10)
        result = _auto_backup_volume(mock_volume)

        assert result is not None
        backup_dir = Path(result)
        assert backup_dir.exists()
        assert (backup_dir / "identities.json").exists()

    def test_backs_up_multiple_files(self, mock_volume):
        from scripts.init_railway_volume import _auto_backup_volume

        _write_identities(mock_volume / "identities.json", confirmed=10)
        _write_photo_index(mock_volume / "photo_index.json")
        (mock_volume / "annotations.json").write_text('{"annotations": []}')

        result = _auto_backup_volume(mock_volume)
        backup_dir = Path(result)

        assert (backup_dir / "identities.json").exists()
        assert (backup_dir / "photo_index.json").exists()
        assert (backup_dir / "annotations.json").exists()

    def test_returns_none_when_no_files(self, mock_volume):
        from scripts.init_railway_volume import _auto_backup_volume

        result = _auto_backup_volume(mock_volume)
        assert result is None

    def test_prunes_old_backups(self, mock_volume):
        from scripts.init_railway_volume import _auto_backup_volume

        _write_identities(mock_volume / "identities.json", confirmed=5)

        # Create 12 fake backup dirs
        backup_root = mock_volume / "auto_backups"
        backup_root.mkdir()
        for i in range(12):
            d = backup_root / f"2026010{i:02d}_120000"
            d.mkdir()
            (d / "identities.json").write_text("{}")

        assert len(list(backup_root.iterdir())) == 12

        _auto_backup_volume(mock_volume)

        # Should be pruned to at most 10 (including the new one)
        assert len(list(backup_root.iterdir())) <= 10


class TestSyncEssentialFilesIntegration:
    """Integration tests for _sync_essential_files with safety gate."""

    def test_blocks_overwrite_when_volume_has_more_confirmed(self, mock_volume, mock_bundle):
        from scripts.init_railway_volume import _sync_essential_files

        # Volume: 55 confirmed (user data)
        _write_identities(mock_volume / "identities.json", confirmed=55, total=100)
        # Bundle: 46 confirmed (stale)
        _write_identities(mock_bundle / "identities.json", confirmed=46, total=100)

        with (
            patch("scripts.init_railway_volume.BUNDLED_DATA", mock_bundle),
            patch("scripts.init_railway_volume.REQUIRED_DATA_FILES", ["identities.json"]),
            patch("scripts.init_railway_volume.OPTIONAL_SYNC_FILES", []),
        ):
            updated = _sync_essential_files(mock_volume)

        assert updated == 0

        # Verify volume was NOT overwritten
        result = json.load(open(mock_volume / "identities.json"))
        ids = result.get("identities", {})
        confirmed = sum(1 for v in ids.values() if v.get("state") == "CONFIRMED")
        assert confirmed == 55

    def test_allows_overwrite_when_bundle_has_more_confirmed(self, mock_volume, mock_bundle):
        from scripts.init_railway_volume import _sync_essential_files

        # Volume: 46 confirmed
        _write_identities(mock_volume / "identities.json", confirmed=46, total=100)
        # Bundle: 55 confirmed (new pipeline data)
        _write_identities(mock_bundle / "identities.json", confirmed=55, total=100)

        with (
            patch("scripts.init_railway_volume.BUNDLED_DATA", mock_bundle),
            patch("scripts.init_railway_volume.REQUIRED_DATA_FILES", ["identities.json"]),
            patch("scripts.init_railway_volume.OPTIONAL_SYNC_FILES", []),
        ):
            updated = _sync_essential_files(mock_volume)

        assert updated == 1

        # Verify volume WAS overwritten with bundle data
        result = json.load(open(mock_volume / "identities.json"))
        ids = result.get("identities", {})
        confirmed = sum(1 for v in ids.values() if v.get("state") == "CONFIRMED")
        assert confirmed == 55

    def test_creates_bak_file_on_allowed_overwrite(self, mock_volume, mock_bundle):
        from scripts.init_railway_volume import _sync_essential_files

        _write_identities(mock_volume / "identities.json", confirmed=46, total=100)
        _write_identities(mock_bundle / "identities.json", confirmed=55, total=100)

        with (
            patch("scripts.init_railway_volume.BUNDLED_DATA", mock_bundle),
            patch("scripts.init_railway_volume.REQUIRED_DATA_FILES", ["identities.json"]),
            patch("scripts.init_railway_volume.OPTIONAL_SYNC_FILES", []),
        ):
            _sync_essential_files(mock_volume)

        bak_files = list(mock_volume.glob("identities.json.bak.*"))
        assert len(bak_files) >= 1

    def test_creates_auto_backup_before_sync(self, mock_volume, mock_bundle):
        from scripts.init_railway_volume import _sync_essential_files

        _write_identities(mock_volume / "identities.json", confirmed=46, total=100)
        _write_identities(mock_bundle / "identities.json", confirmed=55, total=100)

        with (
            patch("scripts.init_railway_volume.BUNDLED_DATA", mock_bundle),
            patch("scripts.init_railway_volume.REQUIRED_DATA_FILES", ["identities.json"]),
            patch("scripts.init_railway_volume.OPTIONAL_SYNC_FILES", []),
        ):
            _sync_essential_files(mock_volume)

        auto_backups = mock_volume / "auto_backups"
        assert auto_backups.exists()
        backup_dirs = list(auto_backups.iterdir())
        assert len(backup_dirs) >= 1

    def test_non_protected_files_still_sync(self, mock_volume, mock_bundle):
        """Files like proposals.json should still sync normally."""
        from scripts.init_railway_volume import _sync_essential_files

        (mock_volume / "proposals.json").write_text('{"old": true}')
        (mock_bundle / "proposals.json").write_text('{"new": true}')

        with (
            patch("scripts.init_railway_volume.BUNDLED_DATA", mock_bundle),
            patch("scripts.init_railway_volume.REQUIRED_DATA_FILES", []),
            patch("scripts.init_railway_volume.OPTIONAL_SYNC_FILES", ["proposals.json"]),
        ):
            updated = _sync_essential_files(mock_volume)

        assert updated == 1
        result = json.load(open(mock_volume / "proposals.json"))
        assert result == {"new": True}


class TestSyncEssentialFilesRegresssion:
    """Regression tests for the exact scenario that caused data loss."""

    def test_session_49b_scenario(self, mock_volume, mock_bundle):
        """Reproduce: user confirms 9 identities on production, deploy overwrites.

        This is the exact scenario from Session 49B data loss.
        Before fix: volume would be overwritten to 46 confirmed (data lost).
        After fix: volume stays at 55 confirmed (safety gate blocks overwrite).
        """
        from scripts.init_railway_volume import _sync_essential_files

        # Simulate: production volume has 49B user confirmations
        _write_identities(mock_volume / "identities.json", confirmed=55, total=775)
        # Simulate: Docker bundle has pre-49B data (stale)
        _write_identities(mock_bundle / "identities.json", confirmed=46, total=775)

        with (
            patch("scripts.init_railway_volume.BUNDLED_DATA", mock_bundle),
            patch("scripts.init_railway_volume.REQUIRED_DATA_FILES", ["identities.json"]),
            patch("scripts.init_railway_volume.OPTIONAL_SYNC_FILES", []),
        ):
            updated = _sync_essential_files(mock_volume)

        # Safety gate MUST block the overwrite
        assert updated == 0

        # Volume MUST still have 55 confirmed
        result = json.load(open(mock_volume / "identities.json"))
        ids = result.get("identities", {})
        confirmed = sum(1 for v in ids.values() if v.get("state") == "CONFIRMED")
        assert confirmed == 55, (
            f"Session 49B regression: expected 55 confirmed but got {confirmed}. "
            f"Safety gate failed to protect user data!"
        )
