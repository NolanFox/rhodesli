"""Tests for GEDCOM admin routes.

TEST 5: Confirmed match enriches identity
TEST 9: Admin UI shows pending matches
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from starlette.testclient import TestClient


@pytest.fixture
def admin_client():
    """Test client with admin auth mocked."""
    with patch("app.main.is_auth_enabled", return_value=True), \
         patch("app.main.get_current_user") as mock_user:
        mock_user.return_value = MagicMock(email="admin@test.com", is_admin=True, id="admin-id")
        from app.main import app
        yield TestClient(app)


@pytest.fixture
def anon_client():
    """Test client with no auth."""
    with patch("app.main.is_auth_enabled", return_value=True), \
         patch("app.main.get_current_user", return_value=None):
        from app.main import app
        yield TestClient(app)


class TestGedcomAdminPage:
    """TEST 9: Admin UI shows pending matches."""

    def test_admin_can_access(self, admin_client):
        resp = admin_client.get("/admin/gedcom")
        assert resp.status_code == 200
        assert "GEDCOM Import" in resp.text

    def test_anon_cannot_access(self, anon_client):
        resp = anon_client.get("/admin/gedcom")
        assert resp.status_code in (401, 403)

    def test_shows_upload_form(self, admin_client):
        resp = admin_client.get("/admin/gedcom")
        assert 'type="file"' in resp.text
        assert "Upload" in resp.text

    def test_shows_stats(self, admin_client):
        resp = admin_client.get("/admin/gedcom")
        assert "Total Matches" in resp.text
        assert "Relationships" in resp.text
        assert "Co-occurrences" in resp.text

    def test_shows_pending_matches_when_data_exists(self, admin_client, tmp_path):
        """When gedcom_matches.json has data, show it."""
        matches_data = {
            "schema_version": 1,
            "source_file": "test.ged",
            "matches": [
                {
                    "gedcom_xref": "@I1@",
                    "gedcom_name": "Leon Capeluto",
                    "gedcom_birth_year": 1903,
                    "identity_id": "id-leon",
                    "identity_name": "Big Leon Capeluto",
                    "match_score": 0.92,
                    "match_reason": "test match",
                    "match_layer": 1,
                    "status": "pending",
                }
            ],
        }

        with patch("app.main._load_gedcom_matches", return_value=matches_data):
            resp = admin_client.get("/admin/gedcom")
            assert resp.status_code == 200
            assert "Leon Capeluto" in resp.text
            assert "Big Leon Capeluto" in resp.text
            assert "Confirm" in resp.text
            assert "Reject" in resp.text


class TestGedcomConfirm:
    """TEST 5: Confirmed match enriches identity."""

    def test_confirm_updates_status(self, admin_client, tmp_path):
        # Create test matches file
        matches_path = tmp_path / "gedcom_matches.json"
        matches_data = {
            "schema_version": 1,
            "source_file": "test.ged",
            "matches": [
                {
                    "gedcom_xref": "@I1@",
                    "gedcom_name": "Leon Capeluto",
                    "gedcom_birth_year": 1903,
                    "gedcom_birth_place": "Rhodes",
                    "gedcom_death_year": 1982,
                    "identity_id": "test-id-leon",
                    "identity_name": "Big Leon Capeluto",
                    "match_score": 0.92,
                    "match_reason": "test",
                    "match_layer": 1,
                    "status": "pending",
                }
            ],
        }
        matches_path.write_text(json.dumps(matches_data))

        # Mock registry
        mock_registry = MagicMock()
        mock_identity = {
            "identity_id": "test-id-leon",
            "name": "Big Leon Capeluto",
            "state": "CONFIRMED",
            "version_id": 1,
        }
        mock_registry.get_identity.return_value = mock_identity

        with patch("app.main.data_path", tmp_path), \
             patch("app.main.load_registry", return_value=mock_registry), \
             patch("app.main.save_registry"), \
             patch("app.main._gedcom_matches_cache", None), \
             patch("app.main._birth_year_cache", None):

            resp = admin_client.post("/admin/gedcom/confirm/@I1@")
            assert resp.status_code == 200
            assert "Confirmed" in resp.text

            # Verify set_metadata was called with GEDCOM data
            mock_registry.set_metadata.assert_called_once()
            call_args = mock_registry.set_metadata.call_args
            assert call_args[0][0] == "test-id-leon"
            metadata = call_args[0][1]
            assert metadata["birth_year"] == 1903
            assert metadata["birth_place"] == "Rhodes"
            assert metadata["death_year"] == 1982

    def test_reject_updates_status(self, admin_client, tmp_path):
        matches_path = tmp_path / "gedcom_matches.json"
        matches_data = {
            "schema_version": 1,
            "source_file": "test.ged",
            "matches": [
                {
                    "gedcom_xref": "@I1@",
                    "gedcom_name": "Test Person",
                    "identity_id": "test-id",
                    "identity_name": "Test Identity",
                    "match_score": 0.8,
                    "match_reason": "test",
                    "match_layer": 1,
                    "status": "pending",
                }
            ],
        }
        matches_path.write_text(json.dumps(matches_data))

        with patch("app.main.data_path", tmp_path), \
             patch("app.main._gedcom_matches_cache", None):
            resp = admin_client.post("/admin/gedcom/reject/@I1@")
            assert resp.status_code == 200
            assert "Rejected" in resp.text

            # Verify file updated
            updated = json.loads(matches_path.read_text())
            assert updated["matches"][0]["status"] == "rejected"


class TestGedcomSidebarLink:
    """Verify GEDCOM link appears in admin sidebar."""

    def test_sidebar_has_gedcom_link(self, admin_client):
        resp = admin_client.get("/")
        assert resp.status_code == 200
        assert "/admin/gedcom" in resp.text
        assert "GEDCOM" in resp.text


class TestGedcomPermissions:
    """Permission boundary tests for GEDCOM routes."""

    def test_upload_requires_admin(self, anon_client):
        resp = anon_client.post("/admin/gedcom/upload")
        assert resp.status_code in (401, 403)

    def test_confirm_requires_admin(self, anon_client):
        resp = anon_client.post("/admin/gedcom/confirm/@I1@")
        assert resp.status_code in (401, 403)

    def test_reject_requires_admin(self, anon_client):
        resp = anon_client.post("/admin/gedcom/reject/@I1@")
        assert resp.status_code in (401, 403)

    def test_skip_requires_admin(self, anon_client):
        resp = anon_client.post("/admin/gedcom/skip/@I1@")
        assert resp.status_code in (401, 403)
