"""Tests for staged file sync API endpoints.

Tests the permission matrix and response format for:
- GET /api/sync/staged (list staged files)
- GET /api/sync/staged/download/{path} (download staged file)
- POST /api/sync/staged/clear (clear staged files)
"""

import json

import pytest
from unittest.mock import patch


# ---------------------------------------------------------------------------
# GET /api/sync/staged — list staged files
# ---------------------------------------------------------------------------

class TestStagedList:
    """List staged files endpoint requires valid sync token."""

    def test_rejects_without_token(self, client):
        """Request without Authorization header gets 401."""
        with patch("app.main.SYNC_API_TOKEN", "valid-token"):
            response = client.get("/api/sync/staged")
        assert response.status_code == 401

    def test_rejects_wrong_token(self, client):
        """Request with wrong token gets 401."""
        with patch("app.main.SYNC_API_TOKEN", "valid-token"):
            response = client.get(
                "/api/sync/staged",
                headers={"Authorization": "Bearer wrong-token"},
            )
        assert response.status_code == 401

    def test_returns_503_when_token_not_configured(self, client):
        """When RHODESLI_SYNC_TOKEN is empty, returns 503."""
        with patch("app.main.SYNC_API_TOKEN", ""):
            response = client.get(
                "/api/sync/staged",
                headers={"Authorization": "Bearer some-token"},
            )
        assert response.status_code == 503

    def test_empty_staging_dir(self, client, tmp_path):
        """Returns empty list when staging dir exists but is empty."""
        staging_dir = tmp_path / "staging"
        staging_dir.mkdir()

        with patch("app.main.SYNC_API_TOKEN", "test-token"), \
             patch("app.main.data_path", tmp_path):
            response = client.get(
                "/api/sync/staged",
                headers={"Authorization": "Bearer test-token"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["files"] == []
        assert data["total_files"] == 0
        assert data["total_size_bytes"] == 0

    def test_no_staging_dir(self, client, tmp_path):
        """Returns empty list when staging dir doesn't exist."""
        with patch("app.main.SYNC_API_TOKEN", "test-token"), \
             patch("app.main.data_path", tmp_path):
            response = client.get(
                "/api/sync/staged",
                headers={"Authorization": "Bearer test-token"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["total_files"] == 0

    def test_lists_files(self, client, tmp_path):
        """Returns file list with metadata when staged files exist."""
        staging_dir = tmp_path / "staging"
        job_dir = staging_dir / "abc123"
        job_dir.mkdir(parents=True)
        (job_dir / "photo1.jpg").write_bytes(b"x" * 1024)
        (job_dir / "photo2.jpg").write_bytes(b"y" * 2048)
        (job_dir / "_metadata.json").write_text('{"source": "test"}')

        with patch("app.main.SYNC_API_TOKEN", "test-token"), \
             patch("app.main.data_path", tmp_path):
            response = client.get(
                "/api/sync/staged",
                headers={"Authorization": "Bearer test-token"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["total_files"] == 3
        assert data["total_size_bytes"] == 1024 + 2048 + len('{"source": "test"}')
        filenames = [f["filename"] for f in data["files"]]
        assert "photo1.jpg" in filenames
        assert "photo2.jpg" in filenames
        # Each file has required fields
        for f in data["files"]:
            assert "filename" in f
            assert "path" in f
            assert "size_bytes" in f
            assert "uploaded_at" in f

    def test_lists_nested_files(self, client, tmp_path):
        """Files in subdirectories (job dirs) are listed with relative paths."""
        staging_dir = tmp_path / "staging"
        (staging_dir / "job1").mkdir(parents=True)
        (staging_dir / "job2").mkdir(parents=True)
        (staging_dir / "job1" / "img_a.jpg").write_bytes(b"a")
        (staging_dir / "job2" / "img_b.jpg").write_bytes(b"b")

        with patch("app.main.SYNC_API_TOKEN", "test-token"), \
             patch("app.main.data_path", tmp_path):
            response = client.get(
                "/api/sync/staged",
                headers={"Authorization": "Bearer test-token"},
            )
        data = response.json()
        assert data["total_files"] == 2
        paths = [f["path"] for f in data["files"]]
        # Paths should be relative to staging root
        assert any("job1" in p and "img_a.jpg" in p for p in paths)
        assert any("job2" in p and "img_b.jpg" in p for p in paths)


# ---------------------------------------------------------------------------
# GET /api/sync/staged/download/{path} — download staged file
# ---------------------------------------------------------------------------

class TestStagedDownload:
    """Download endpoint requires auth and validates paths."""

    def test_rejects_without_token(self, client):
        """Request without Authorization header gets 401."""
        with patch("app.main.SYNC_API_TOKEN", "valid-token"):
            response = client.get("/api/sync/staged/download/somefile.jpg")
        assert response.status_code == 401

    def test_blocks_path_traversal_dotdot(self, client, tmp_path):
        """Rejects paths containing '..' to prevent directory traversal.

        Note: HTTP clients normalize /../ before sending, so we use
        URL-encoded dots (%2e%2e) which some servers decode.
        Starlette normalizes these too, so we test that files outside
        staging are not served even if the path seems valid.
        """
        # Create a file OUTSIDE staging to ensure it's not served
        (tmp_path / "staging").mkdir()
        (tmp_path / "secret.txt").write_text("sensitive data")

        with patch("app.main.SYNC_API_TOKEN", "test-token"), \
             patch("app.main.data_path", tmp_path):
            # Try to access a file outside staging — the resolved path check blocks this
            response = client.get(
                "/api/sync/staged/download/secret.txt",
                headers={"Authorization": "Bearer test-token"},
            )
        # File doesn't exist inside staging, so 404
        assert response.status_code == 404

    def test_blocks_absolute_path(self, client, tmp_path):
        """Files outside the staging directory are never served."""
        (tmp_path / "staging").mkdir()

        with patch("app.main.SYNC_API_TOKEN", "test-token"), \
             patch("app.main.data_path", tmp_path):
            response = client.get(
                "/api/sync/staged/download/etc/passwd",
                headers={"Authorization": "Bearer test-token"},
            )
        assert response.status_code == 404

    def test_returns_404_for_missing_file(self, client, tmp_path):
        """Returns 404 when requested file doesn't exist."""
        (tmp_path / "staging").mkdir()

        with patch("app.main.SYNC_API_TOKEN", "test-token"), \
             patch("app.main.data_path", tmp_path):
            response = client.get(
                "/api/sync/staged/download/nonexistent.jpg",
                headers={"Authorization": "Bearer test-token"},
            )
        assert response.status_code == 404

    def test_returns_file_bytes(self, client, tmp_path):
        """Returns actual file content for valid path."""
        staging_dir = tmp_path / "staging"
        job_dir = staging_dir / "abc123"
        job_dir.mkdir(parents=True)
        content = b"fake-jpeg-content-here"
        (job_dir / "photo.jpg").write_bytes(content)

        with patch("app.main.SYNC_API_TOKEN", "test-token"), \
             patch("app.main.data_path", tmp_path):
            response = client.get(
                "/api/sync/staged/download/abc123/photo.jpg",
                headers={"Authorization": "Bearer test-token"},
            )
        assert response.status_code == 200
        assert response.content == content


# ---------------------------------------------------------------------------
# POST /api/sync/staged/clear — remove staged files
# ---------------------------------------------------------------------------

class TestStagedClear:
    """Clear endpoint requires auth and removes specified files."""

    def test_rejects_without_token(self, client):
        """Request without Authorization header gets 401."""
        with patch("app.main.SYNC_API_TOKEN", "valid-token"):
            response = client.post(
                "/api/sync/staged/clear",
                json={"all": True},
            )
        assert response.status_code == 401

    def test_clear_all(self, client, tmp_path):
        """Clears entire staging directory when all=true."""
        staging_dir = tmp_path / "staging"
        job_dir = staging_dir / "job1"
        job_dir.mkdir(parents=True)
        (job_dir / "photo.jpg").write_bytes(b"x")
        (job_dir / "_metadata.json").write_text("{}")

        with patch("app.main.SYNC_API_TOKEN", "test-token"), \
             patch("app.main.data_path", tmp_path):
            response = client.post(
                "/api/sync/staged/clear",
                headers={"Authorization": "Bearer test-token"},
                json={"all": True},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["cleared"] == "all"
        assert data["count"] >= 1
        # Staging dir should be empty
        assert list(staging_dir.iterdir()) == []

    def test_clear_specific_files(self, client, tmp_path):
        """Removes only specified files/directories."""
        staging_dir = tmp_path / "staging"
        job1 = staging_dir / "job1"
        job2 = staging_dir / "job2"
        job1.mkdir(parents=True)
        job2.mkdir(parents=True)
        (job1 / "photo.jpg").write_bytes(b"x")
        (job2 / "photo.jpg").write_bytes(b"y")

        with patch("app.main.SYNC_API_TOKEN", "test-token"), \
             patch("app.main.data_path", tmp_path):
            response = client.post(
                "/api/sync/staged/clear",
                headers={"Authorization": "Bearer test-token"},
                json={"files": ["job1"]},
            )
        assert response.status_code == 200
        data = response.json()
        assert "job1" in data["removed"]
        assert data["count"] == 1
        # job1 should be gone, job2 should remain
        assert not job1.exists()
        assert job2.exists()

    def test_clear_rejects_path_traversal(self, client, tmp_path):
        """Path traversal attempts are reported as errors."""
        (tmp_path / "staging").mkdir()

        with patch("app.main.SYNC_API_TOKEN", "test-token"), \
             patch("app.main.data_path", tmp_path):
            response = client.post(
                "/api/sync/staged/clear",
                headers={"Authorization": "Bearer test-token"},
                json={"files": ["../../../etc/passwd"]},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert len(data["errors"]) == 1
        assert data["errors"][0]["error"] == "invalid path"

    def test_clear_no_files_specified(self, client, tmp_path):
        """Returns 400 when no files specified and all is not true."""
        with patch("app.main.SYNC_API_TOKEN", "test-token"), \
             patch("app.main.data_path", tmp_path):
            response = client.post(
                "/api/sync/staged/clear",
                headers={"Authorization": "Bearer test-token"},
                json={"files": []},
            )
        assert response.status_code == 400

    def test_clear_nonexistent_files(self, client, tmp_path):
        """Reports errors for files that don't exist."""
        (tmp_path / "staging").mkdir()

        with patch("app.main.SYNC_API_TOKEN", "test-token"), \
             patch("app.main.data_path", tmp_path):
            response = client.post(
                "/api/sync/staged/clear",
                headers={"Authorization": "Bearer test-token"},
                json={"files": ["nonexistent_job"]},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert len(data["errors"]) == 1
        assert data["errors"][0]["error"] == "not found"
