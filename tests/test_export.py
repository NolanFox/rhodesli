"""Tests for admin data export endpoints.

Tests the permission matrix and response format for:
- GET /admin/export/identities
- GET /admin/export/photo-index
- GET /admin/export/all
"""

import io
import json
import zipfile

import pytest
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Route lists for matrix testing
# ---------------------------------------------------------------------------

ADMIN_EXPORT_GET_ROUTES = [
    "/admin/export/identities",
    "/admin/export/photo-index",
    "/admin/export/all",
]


# ---------------------------------------------------------------------------
# Permission tests: anonymous users get 401
# ---------------------------------------------------------------------------

class TestExportAnonymous:
    """Anonymous users should get 401 on all export routes."""

    def test_export_routes_return_401_for_anonymous(self, client, auth_enabled, no_user):
        """Anonymous users get 401 on admin export GET routes."""
        for route in ADMIN_EXPORT_GET_ROUTES:
            response = client.get(route, follow_redirects=False)
            assert response.status_code == 401, \
                f"{route} returned {response.status_code}, expected 401"

    def test_export_routes_never_redirect(self, client, auth_enabled, no_user):
        """Export routes return 401, not 303 redirect (HTMX compatibility)."""
        for route in ADMIN_EXPORT_GET_ROUTES:
            response = client.get(route, follow_redirects=False)
            assert response.status_code != 303, \
                f"{route} returned 303 redirect — MUST use 401 for HTMX compatibility"


# ---------------------------------------------------------------------------
# Permission tests: non-admin users get 403
# ---------------------------------------------------------------------------

class TestExportNonAdmin:
    """Non-admin users should get 403 on all export routes."""

    def test_export_routes_return_403_for_non_admin(self, client, auth_enabled, regular_user):
        """Non-admin users get 403 on admin export routes."""
        for route in ADMIN_EXPORT_GET_ROUTES:
            response = client.get(route, follow_redirects=False)
            assert response.status_code == 403, \
                f"{route} returned {response.status_code}, expected 403"


# ---------------------------------------------------------------------------
# Permission tests: auth disabled means everyone passes
# ---------------------------------------------------------------------------

class TestExportAuthDisabled:
    """When auth is disabled, export routes should not return 401/403."""

    def test_export_routes_pass_when_auth_disabled(self, client, auth_disabled):
        """Export routes don't block when auth is disabled."""
        for route in ADMIN_EXPORT_GET_ROUTES:
            response = client.get(route, follow_redirects=False)
            assert response.status_code not in (401, 403), \
                f"{route} returned {response.status_code} with auth disabled"


# ---------------------------------------------------------------------------
# Functional tests: admin can download files
# ---------------------------------------------------------------------------

class TestExportIdentities:
    """Admin can download identities.json."""

    def test_returns_json_for_admin(self, client, auth_enabled, admin_user, tmp_path):
        """GET /admin/export/identities returns JSON with attachment header."""
        test_data = {"identities": {"id-1": {"name": "Test"}}}
        test_file = tmp_path / "identities.json"
        test_file.write_text(json.dumps(test_data))

        with patch("app.main.data_path", tmp_path):
            response = client.get("/admin/export/identities")

        assert response.status_code == 200
        assert "attachment" in response.headers.get("content-disposition", "")
        assert "identities.json" in response.headers.get("content-disposition", "")
        assert response.json() == test_data

    def test_returns_404_when_file_missing(self, client, auth_enabled, admin_user, tmp_path):
        """GET /admin/export/identities returns 404 when file doesn't exist."""
        with patch("app.main.data_path", tmp_path):
            response = client.get("/admin/export/identities")

        assert response.status_code == 404


class TestExportPhotoIndex:
    """Admin can download photo_index.json."""

    def test_returns_json_for_admin(self, client, auth_enabled, admin_user, tmp_path):
        """GET /admin/export/photo-index returns JSON with attachment header."""
        test_data = {"photos": {"photo-1": {"path": "test.jpg"}}}
        test_file = tmp_path / "photo_index.json"
        test_file.write_text(json.dumps(test_data))

        with patch("app.main.data_path", tmp_path):
            response = client.get("/admin/export/photo-index")

        assert response.status_code == 200
        assert "attachment" in response.headers.get("content-disposition", "")
        assert "photo_index.json" in response.headers.get("content-disposition", "")
        assert response.json() == test_data

    def test_returns_404_when_file_missing(self, client, auth_enabled, admin_user, tmp_path):
        """GET /admin/export/photo-index returns 404 when file doesn't exist."""
        with patch("app.main.data_path", tmp_path):
            response = client.get("/admin/export/photo-index")

        assert response.status_code == 404


class TestExportAll:
    """Admin can download a ZIP of both files."""

    def test_returns_zip_for_admin(self, client, auth_enabled, admin_user, tmp_path):
        """GET /admin/export/all returns ZIP containing both data files."""
        identities_data = {"identities": {"id-1": {"name": "Test"}}}
        photo_data = {"photos": {"photo-1": {"path": "test.jpg"}}}

        (tmp_path / "identities.json").write_text(json.dumps(identities_data))
        (tmp_path / "photo_index.json").write_text(json.dumps(photo_data))

        with patch("app.main.data_path", tmp_path):
            response = client.get("/admin/export/all")

        assert response.status_code == 200
        assert "attachment" in response.headers.get("content-disposition", "")
        assert "rhodesli-data-export.zip" in response.headers.get("content-disposition", "")
        assert response.headers.get("content-type") == "application/zip"

        # Verify ZIP contents
        buf = io.BytesIO(response.content)
        with zipfile.ZipFile(buf, "r") as zf:
            names = zf.namelist()
            assert "identities.json" in names
            assert "photo_index.json" in names

            # Verify file contents inside ZIP
            with zf.open("identities.json") as f:
                assert json.load(f) == identities_data
            with zf.open("photo_index.json") as f:
                assert json.load(f) == photo_data

    def test_returns_zip_with_partial_files(self, client, auth_enabled, admin_user, tmp_path):
        """GET /admin/export/all works when only one file exists."""
        identities_data = {"identities": {}}
        (tmp_path / "identities.json").write_text(json.dumps(identities_data))
        # photo_index.json intentionally missing

        with patch("app.main.data_path", tmp_path):
            response = client.get("/admin/export/all")

        assert response.status_code == 200

        buf = io.BytesIO(response.content)
        with zipfile.ZipFile(buf, "r") as zf:
            names = zf.namelist()
            assert "identities.json" in names
            assert "photo_index.json" not in names

    def test_returns_empty_zip_when_no_files(self, client, auth_enabled, admin_user, tmp_path):
        """GET /admin/export/all returns an empty ZIP when no data files exist."""
        with patch("app.main.data_path", tmp_path):
            response = client.get("/admin/export/all")

        assert response.status_code == 200

        buf = io.BytesIO(response.content)
        with zipfile.ZipFile(buf, "r") as zf:
            assert zf.namelist() == []
