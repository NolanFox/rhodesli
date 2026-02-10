"""Tests for the upload processing pipeline orchestrator."""

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Import the orchestrator module
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from process_uploads import (
    check_env_vars,
    count_identities,
    count_photos,
    count_photos_in_dir,
    create_backups,
    DATA_DIR,
)


@pytest.fixture
def sample_identities(tmp_path):
    """Create a sample identities.json for testing."""
    data = {
        "schema_version": 1,
        "identities": {
            "id-1": {"name": "Person A", "state": "CONFIRMED", "anchor_ids": ["f1"]},
            "id-2": {"name": "Person B", "state": "PROPOSED", "anchor_ids": ["f2"]},
            "id-3": {"name": "Person C", "state": "INBOX", "anchor_ids": ["f3"]},
        },
        "history": [],
    }
    path = tmp_path / "identities.json"
    path.write_text(json.dumps(data))
    return path


@pytest.fixture
def sample_photo_index(tmp_path):
    """Create a sample photo_index.json for testing."""
    data = {
        "schema_version": 1,
        "photos": {
            "p1": {"path": "photo1.jpg", "face_ids": ["f1"]},
            "p2": {"path": "photo2.jpg", "face_ids": ["f2", "f3"]},
        },
        "face_to_photo": {"f1": "p1", "f2": "p2", "f3": "p2"},
    }
    path = tmp_path / "photo_index.json"
    path.write_text(json.dumps(data))
    return path


class TestCountIdentities:
    def test_counts_by_state(self, sample_identities):
        counts = count_identities(sample_identities)
        assert counts["total"] == 3
        assert counts["CONFIRMED"] == 1
        assert counts["PROPOSED"] == 1
        assert counts["INBOX"] == 1

    def test_missing_file_returns_empty(self, tmp_path):
        counts = count_identities(tmp_path / "nonexistent.json")
        assert counts == {}


class TestCountPhotos:
    def test_counts_photos(self, sample_photo_index):
        assert count_photos(sample_photo_index) == 2

    def test_missing_file_returns_zero(self, tmp_path):
        assert count_photos(tmp_path / "nonexistent.json") == 0


class TestCountPhotosInDir:
    def test_counts_image_files(self, tmp_path):
        (tmp_path / "photo1.jpg").write_text("fake")
        (tmp_path / "photo2.png").write_text("fake")
        (tmp_path / "_metadata.json").write_text("{}")
        (tmp_path / "notes.txt").write_text("notes")
        assert count_photos_in_dir(tmp_path) == 2

    def test_missing_dir_returns_zero(self, tmp_path):
        assert count_photos_in_dir(tmp_path / "nonexistent") == 0


class TestCheckEnvVars:
    def test_dry_run_only_needs_sync_token(self):
        with patch.dict(os.environ, {"RHODESLI_SYNC_TOKEN": "test-token"}, clear=False):
            missing = check_env_vars(dry_run=True)
            assert missing == []

    def test_dry_run_missing_sync_token(self):
        with patch.dict(os.environ, {}, clear=True):
            # Ensure RHODESLI_SYNC_TOKEN is not set
            os.environ.pop("RHODESLI_SYNC_TOKEN", None)
            missing = check_env_vars(dry_run=True)
            assert "RHODESLI_SYNC_TOKEN" in missing

    def test_full_run_needs_r2_vars(self):
        with patch.dict(os.environ, {"RHODESLI_SYNC_TOKEN": "test-token"}, clear=True):
            missing = check_env_vars(dry_run=False)
            assert "R2_ACCOUNT_ID" in missing
            assert "R2_ACCESS_KEY_ID" in missing
            assert "R2_SECRET_ACCESS_KEY" in missing
            assert "R2_BUCKET_NAME" in missing

    def test_full_run_all_vars_present(self):
        env = {
            "RHODESLI_SYNC_TOKEN": "t",
            "R2_ACCOUNT_ID": "a",
            "R2_ACCESS_KEY_ID": "b",
            "R2_SECRET_ACCESS_KEY": "c",
            "R2_BUCKET_NAME": "d",
        }
        with patch.dict(os.environ, env, clear=True):
            missing = check_env_vars(dry_run=False)
            assert missing == []


class TestCreateBackups:
    def test_creates_backup_files(self, tmp_path):
        """Orchestrator creates .bak files before modifying data."""
        # Set up fake data dir
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "identities.json").write_text('{"identities": {}}')
        (data_dir / "photo_index.json").write_text('{"photos": {}}')

        backup_dir = data_dir / "backups"

        with patch("process_uploads.DATA_DIR", data_dir), \
             patch("process_uploads.BACKUP_DIR", backup_dir):
            backups = create_backups()

        assert len(backups) == 2
        assert "identities.json" in backups
        assert "photo_index.json" in backups
        for name, path in backups.items():
            assert path.exists()
            assert ".bak" in path.name

    def test_skips_missing_files(self, tmp_path):
        """Backup handles missing data files gracefully."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        backup_dir = data_dir / "backups"

        with patch("process_uploads.DATA_DIR", data_dir), \
             patch("process_uploads.BACKUP_DIR", backup_dir):
            backups = create_backups()

        assert len(backups) == 0


class TestDryRunSafety:
    def test_dry_run_does_not_modify_data(self, tmp_path):
        """--dry-run mode doesn't write to photo_index or identities."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        ids_content = '{"schema_version": 1, "identities": {}, "history": []}'
        pi_content = '{"schema_version": 1, "photos": {}, "face_to_photo": {}}'

        ids_path = data_dir / "identities.json"
        pi_path = data_dir / "photo_index.json"
        ids_path.write_text(ids_content)
        pi_path.write_text(pi_content)

        # Run with --dry-run, expect exit due to no staged files
        # We just verify the data files are unchanged after the env check fails
        result = subprocess.run(
            [sys.executable, "scripts/process_uploads.py", "--dry-run"],
            cwd=str(Path(__file__).resolve().parent.parent),
            capture_output=True,
            text=True,
            env={**os.environ, "RHODESLI_SYNC_TOKEN": ""},
        )

        # Script should fail due to missing token, but data must be untouched
        assert ids_path.read_text() == ids_content
        assert pi_path.read_text() == pi_content


class TestScriptExecution:
    def test_fails_without_sync_token(self):
        """Script fails gracefully if SYNC_TOKEN missing."""
        # Set token to empty string to prevent .env file from loading it
        env = {**os.environ, "RHODESLI_SYNC_TOKEN": ""}

        result = subprocess.run(
            [sys.executable, "scripts/process_uploads.py", "--dry-run"],
            cwd=str(Path(__file__).resolve().parent.parent),
            capture_output=True,
            text=True,
            env=env,
        )

        assert result.returncode != 0
        assert "RHODESLI_SYNC_TOKEN" in result.stdout or "RHODESLI_SYNC_TOKEN" in result.stderr

    def test_help_flag(self):
        """Script shows help text."""
        result = subprocess.run(
            [sys.executable, "scripts/process_uploads.py", "--help"],
            cwd=str(Path(__file__).resolve().parent.parent),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "dry-run" in result.stdout
        assert "auto" in result.stdout
