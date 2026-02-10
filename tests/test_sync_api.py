"""Tests for sync API endpoints.

Tests the permission matrix and response format for:
- GET /api/sync/status (public)
- GET /api/sync/identities (token-authenticated)
- GET /api/sync/photo-index (token-authenticated)
- POST /api/sync/push (token-authenticated, writes data)
"""

import json

import pytest
from unittest.mock import patch


# ---------------------------------------------------------------------------
# /api/sync/status — public, no auth needed
# ---------------------------------------------------------------------------

class TestSyncStatus:
    """Status endpoint is public and returns data stats."""

    def test_status_returns_200(self, client):
        """Status endpoint is accessible without any auth."""
        response = client.get("/api/sync/status")
        assert response.status_code == 200

    def test_status_contains_expected_fields(self, client):
        """Status response includes identity and photo counts."""
        response = client.get("/api/sync/status")
        data = response.json()
        assert "identities" in data
        assert "confirmed" in data
        assert "proposed" in data
        assert "inbox" in data
        assert "photos" in data
        assert "timestamp" in data

    def test_status_works_with_auth_enabled(self, client, auth_enabled, no_user):
        """Status endpoint works even when auth is enabled and no user is logged in."""
        response = client.get("/api/sync/status")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# /api/sync/identities — requires valid RHODESLI_SYNC_TOKEN
# ---------------------------------------------------------------------------

class TestSyncIdentities:
    """Identities endpoint requires a valid sync token."""

    def test_rejects_without_token(self, client):
        """Request without Authorization header gets 401."""
        with patch("app.main.SYNC_API_TOKEN", "valid-token"):
            response = client.get("/api/sync/identities")
        assert response.status_code == 401

    def test_rejects_wrong_token(self, client):
        """Request with wrong token gets 401."""
        with patch("app.main.SYNC_API_TOKEN", "valid-token"):
            response = client.get(
                "/api/sync/identities",
                headers={"Authorization": "Bearer wrong-token"},
            )
        assert response.status_code == 401

    def test_returns_503_when_token_not_configured(self, client):
        """When RHODESLI_SYNC_TOKEN is empty, returns 503."""
        with patch("app.main.SYNC_API_TOKEN", ""):
            response = client.get(
                "/api/sync/identities",
                headers={"Authorization": "Bearer some-token"},
            )
        assert response.status_code == 503

    def test_returns_data_with_valid_token(self, client, tmp_path):
        """Valid token returns identities JSON."""
        test_data = {
            "schema_version": 1,
            "identities": {"id-1": {"name": "Test Person", "state": "CONFIRMED"}},
        }
        (tmp_path / "identities.json").write_text(json.dumps(test_data))

        with patch("app.main.SYNC_API_TOKEN", "test-token-123"), \
             patch("app.main.data_path", tmp_path):
            response = client.get(
                "/api/sync/identities",
                headers={"Authorization": "Bearer test-token-123"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["schema_version"] == 1
        assert "id-1" in data["identities"]

    def test_returns_404_when_file_missing(self, client, tmp_path):
        """Returns 404 when identities.json doesn't exist."""
        with patch("app.main.SYNC_API_TOKEN", "test-token-123"), \
             patch("app.main.data_path", tmp_path):
            response = client.get(
                "/api/sync/identities",
                headers={"Authorization": "Bearer test-token-123"},
            )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# /api/sync/photo-index — requires valid RHODESLI_SYNC_TOKEN
# ---------------------------------------------------------------------------

class TestSyncPhotoIndex:
    """Photo index endpoint requires a valid sync token."""

    def test_rejects_without_token(self, client):
        """Request without Authorization header gets 401."""
        with patch("app.main.SYNC_API_TOKEN", "valid-token"):
            response = client.get("/api/sync/photo-index")
        assert response.status_code == 401

    def test_rejects_wrong_token(self, client):
        """Request with wrong token gets 401."""
        with patch("app.main.SYNC_API_TOKEN", "valid-token"):
            response = client.get(
                "/api/sync/photo-index",
                headers={"Authorization": "Bearer wrong-token"},
            )
        assert response.status_code == 401

    def test_returns_data_with_valid_token(self, client, tmp_path):
        """Valid token returns photo index JSON."""
        test_data = {
            "schema_version": 1,
            "photos": {"photo-1": {"path": "test.jpg", "face_ids": []}},
            "face_to_photo": {},
        }
        (tmp_path / "photo_index.json").write_text(json.dumps(test_data))

        with patch("app.main.SYNC_API_TOKEN", "test-token-123"), \
             patch("app.main.data_path", tmp_path):
            response = client.get(
                "/api/sync/photo-index",
                headers={"Authorization": "Bearer test-token-123"},
            )
        assert response.status_code == 200
        data = response.json()
        assert "photos" in data
        assert "photo-1" in data["photos"]

    def test_returns_404_when_file_missing(self, client, tmp_path):
        """Returns 404 when photo_index.json doesn't exist."""
        with patch("app.main.SYNC_API_TOKEN", "test-token-123"), \
             patch("app.main.data_path", tmp_path):
            response = client.get(
                "/api/sync/photo-index",
                headers={"Authorization": "Bearer test-token-123"},
            )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/sync/push — push data to production (token-authenticated)
# ---------------------------------------------------------------------------

class TestSyncPush:
    """Push endpoint writes identities and/or photo_index to the data volume."""

    def test_rejects_without_token(self, client):
        """Request without Authorization header gets 401."""
        with patch("app.main.SYNC_API_TOKEN", "valid-token"):
            response = client.post(
                "/api/sync/push",
                json={"identities": {"identities": {}}},
            )
        assert response.status_code == 401

    def test_rejects_wrong_token(self, client):
        """Request with wrong token gets 401."""
        with patch("app.main.SYNC_API_TOKEN", "valid-token"):
            response = client.post(
                "/api/sync/push",
                headers={"Authorization": "Bearer wrong-token"},
                json={"identities": {"identities": {}}},
            )
        assert response.status_code == 401

    def test_returns_503_when_token_not_configured(self, client):
        """When RHODESLI_SYNC_TOKEN is empty, returns 503."""
        with patch("app.main.SYNC_API_TOKEN", ""):
            response = client.post(
                "/api/sync/push",
                headers={"Authorization": "Bearer some-token"},
                json={"identities": {"identities": {}}},
            )
        assert response.status_code == 503

    def test_rejects_empty_body(self, client, tmp_path):
        """Returns 400 when neither identities nor photo_index provided."""
        with patch("app.main.SYNC_API_TOKEN", "test-token"), \
             patch("app.main.data_path", tmp_path):
            response = client.post(
                "/api/sync/push",
                headers={"Authorization": "Bearer test-token"},
                json={},
            )
        assert response.status_code == 400

    def test_pushes_identities(self, client, tmp_path):
        """Writes identities.json when identities key provided."""
        # Seed existing file so backup can be created
        existing = {"schema_version": 1, "identities": {"old": {"state": "CONFIRMED"}}}
        (tmp_path / "identities.json").write_text(json.dumps(existing))

        new_data = {
            "schema_version": 1,
            "identities": {
                "id-1": {"name": "Alice", "state": "CONFIRMED"},
                "id-2": {"name": "Bob", "state": "INBOX"},
            },
        }

        with patch("app.main.SYNC_API_TOKEN", "test-token"), \
             patch("app.main.data_path", tmp_path):
            response = client.post(
                "/api/sync/push",
                headers={"Authorization": "Bearer test-token"},
                json={"identities": new_data},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["results"]["identities"]["status"] == "written"
        assert data["results"]["identities"]["count"] == 2

        # Verify file was written
        written = json.loads((tmp_path / "identities.json").read_text())
        assert "id-1" in written["identities"]
        assert "id-2" in written["identities"]

        # Verify backup was created
        backups = list(tmp_path.glob("identities.json.bak.*"))
        assert len(backups) == 1

    def test_pushes_photo_index(self, client, tmp_path):
        """Writes photo_index.json when photo_index key provided."""
        existing = {"schema_version": 1, "photos": {}, "face_to_photo": {}}
        (tmp_path / "photo_index.json").write_text(json.dumps(existing))

        new_data = {
            "schema_version": 1,
            "photos": {
                "photo-1": {"path": "test.jpg", "face_ids": ["f1"]},
                "photo-2": {"path": "test2.jpg", "face_ids": ["f2"]},
            },
            "face_to_photo": {"f1": "photo-1", "f2": "photo-2"},
        }

        with patch("app.main.SYNC_API_TOKEN", "test-token"), \
             patch("app.main.data_path", tmp_path):
            response = client.post(
                "/api/sync/push",
                headers={"Authorization": "Bearer test-token"},
                json={"photo_index": new_data},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["results"]["photo_index"]["count"] == 2

        # Verify file was written
        written = json.loads((tmp_path / "photo_index.json").read_text())
        assert "photo-1" in written["photos"]

    def test_pushes_both(self, client, tmp_path):
        """Can push both identities and photo_index in one request."""
        (tmp_path / "identities.json").write_text('{"identities": {}}')
        (tmp_path / "photo_index.json").write_text('{"photos": {}, "face_to_photo": {}}')

        with patch("app.main.SYNC_API_TOKEN", "test-token"), \
             patch("app.main.data_path", tmp_path):
            response = client.post(
                "/api/sync/push",
                headers={"Authorization": "Bearer test-token"},
                json={
                    "identities": {"identities": {"id-1": {"state": "INBOX"}}},
                    "photo_index": {"photos": {"p-1": {"path": "x.jpg"}}, "face_to_photo": {}},
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert "identities" in data["results"]
        assert "photo_index" in data["results"]

    def test_creates_backup_before_overwrite(self, client, tmp_path):
        """Existing files are backed up before being overwritten."""
        original = {"identities": {"orig": {"state": "CONFIRMED", "name": "Original"}}}
        (tmp_path / "identities.json").write_text(json.dumps(original))

        with patch("app.main.SYNC_API_TOKEN", "test-token"), \
             patch("app.main.data_path", tmp_path):
            response = client.post(
                "/api/sync/push",
                headers={"Authorization": "Bearer test-token"},
                json={"identities": {"identities": {"new": {"state": "INBOX"}}}},
            )
        assert response.status_code == 200

        # Backup contains original data
        backups = list(tmp_path.glob("identities.json.bak.*"))
        assert len(backups) == 1
        backup_data = json.loads(backups[0].read_text())
        assert "orig" in backup_data["identities"]

    def test_works_without_existing_file(self, client, tmp_path):
        """Push works even when files don't exist yet (no backup needed)."""
        with patch("app.main.SYNC_API_TOKEN", "test-token"), \
             patch("app.main.data_path", tmp_path):
            response = client.post(
                "/api/sync/push",
                headers={"Authorization": "Bearer test-token"},
                json={"identities": {"identities": {"id-1": {"state": "INBOX"}}}},
            )
        assert response.status_code == 200
        assert (tmp_path / "identities.json").exists()
