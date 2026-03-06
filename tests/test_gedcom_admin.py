"""Tests for GEDCOM admin page — version management UI (AD-164).

Tests:
- Auth: non-admin gets 401/403
- Page loads for admin with mocked Supabase responses
- Upload endpoint returns diff preview
- Apply/cancel endpoints
- Version history display
- Enrichment queue display
"""

import pytest
from unittest.mock import patch, MagicMock

from starlette.testclient import TestClient


@pytest.fixture
def admin_client():
    """Test client with admin auth mocked."""
    with patch("app.main.is_auth_enabled", return_value=True), patch("app.main.get_current_user") as mock_user:
        mock_user.return_value = MagicMock(email="admin@test.com", is_admin=True, id="admin-id")
        from app.main import app

        yield TestClient(app)


@pytest.fixture
def anon_client():
    """Test client with no auth."""
    with patch("app.main.is_auth_enabled", return_value=True), patch("app.main.get_current_user", return_value=None):
        from app.main import app

        yield TestClient(app)


@pytest.fixture
def non_admin_client():
    """Test client with non-admin user."""
    with patch("app.main.is_auth_enabled", return_value=True), patch("app.main.get_current_user") as mock_user:
        mock_user.return_value = MagicMock(email="user@test.com", is_admin=False, id="user-id")
        from app.main import app

        yield TestClient(app)


# --- Auth Tests ---


class TestGedcomAdminAuth:
    """Auth boundary tests for GEDCOM admin routes."""

    def test_anon_cannot_access_page(self, anon_client):
        resp = anon_client.get("/admin/gedcom")
        assert resp.status_code in (401, 403)

    def test_non_admin_cannot_access_page(self, non_admin_client):
        resp = non_admin_client.get("/admin/gedcom")
        assert resp.status_code in (401, 403)

    def test_anon_cannot_upload(self, anon_client):
        resp = anon_client.post("/admin/gedcom/upload")
        assert resp.status_code in (401, 403)

    def test_anon_cannot_apply(self, anon_client):
        resp = anon_client.post("/admin/gedcom/apply")
        assert resp.status_code in (401, 403)

    def test_anon_cannot_cancel(self, anon_client):
        resp = anon_client.post("/admin/gedcom/cancel")
        assert resp.status_code in (401, 403)

    def test_non_admin_cannot_upload(self, non_admin_client):
        resp = non_admin_client.post("/admin/gedcom/upload")
        assert resp.status_code in (401, 403)

    def test_non_admin_cannot_apply(self, non_admin_client):
        resp = non_admin_client.post("/admin/gedcom/apply")
        assert resp.status_code in (401, 403)

    def test_non_admin_cannot_cancel(self, non_admin_client):
        resp = non_admin_client.post("/admin/gedcom/cancel")
        assert resp.status_code in (401, 403)


# --- Page Load Tests ---


class TestGedcomPageLoad:
    """Tests for the GEDCOM admin page load."""

    def test_admin_can_access(self, admin_client):
        """Admin can load the GEDCOM management page."""
        with (
            patch("app.main._load_gedcom_versions", return_value=[]),
            patch("app.main._load_gedcom_enrichment_queue_count", return_value=0),
        ):
            resp = admin_client.get("/admin/gedcom")
            assert resp.status_code == 200
            assert "GEDCOM Management" in resp.text

    def test_shows_version_info_when_versions_exist(self, admin_client):
        """Page shows version info panel when versions exist in Supabase."""
        versions = [
            {
                "id": "uuid-1",
                "version_number": 3,
                "community_id": "rhodesli",
                "imported_at": "2026-02-24T10:30:00Z",
                "source_file": "Family.ged",
                "source_hash": "abc123",
                "individual_count": 21809,
                "family_count": 8500,
                "summary": {"added": 50, "modified": 10, "removed": 2, "unchanged": 21747},
                "notes": "Added Marcus branch",
            }
        ]
        with (
            patch("app.main._load_gedcom_versions", return_value=versions),
            patch("app.main._load_gedcom_enrichment_queue_count", return_value=5),
        ):
            resp = admin_client.get("/admin/gedcom")
            assert resp.status_code == 200
            assert "gedcom-version-info" in resp.text
            assert "21,809" in resp.text  # Individual count formatted
            assert "8,500" in resp.text  # Family count formatted
            assert "Family.ged" in resp.text
            assert "Added Marcus branch" in resp.text

    def test_shows_no_versions_message_when_empty(self, admin_client):
        """Page shows 'no versions' message when no GEDCOM has been imported."""
        with (
            patch("app.main._load_gedcom_versions", return_value=[]),
            patch("app.main._load_gedcom_enrichment_queue_count", return_value=0),
        ):
            resp = admin_client.get("/admin/gedcom")
            assert resp.status_code == 200
            assert "No versions imported yet" in resp.text

    def test_shows_version_history_table(self, admin_client):
        """Page shows version history table with change badges."""
        versions = [
            {
                "id": "uuid-2",
                "version_number": 2,
                "imported_at": "2026-02-24T10:30:00Z",
                "source_file": "Family_v2.ged",
                "individual_count": 21859,
                "family_count": 8520,
                "summary": {"added": 50, "modified": 10, "removed": 2, "unchanged": 21797},
                "notes": None,
            },
            {
                "id": "uuid-1",
                "version_number": 1,
                "imported_at": "2026-02-23T08:00:00Z",
                "source_file": "Family.ged",
                "individual_count": 21809,
                "family_count": 8500,
                "summary": {"added": 21809, "modified": 0, "removed": 0, "unchanged": 0},
                "notes": "Initial import",
            },
        ]
        with (
            patch("app.main._load_gedcom_versions", return_value=versions),
            patch("app.main._load_gedcom_enrichment_queue_count", return_value=0),
        ):
            resp = admin_client.get("/admin/gedcom")
            assert resp.status_code == 200
            assert "gedcom-version-history" in resp.text
            assert "v2" in resp.text
            assert "v1" in resp.text
            assert "Family_v2.ged" in resp.text
            assert "Initial import" in resp.text

    def test_shows_enrichment_queue_count(self, admin_client):
        """Page shows re-enrichment queue count."""
        versions = [
            {
                "id": "uuid-1",
                "version_number": 1,
                "imported_at": "2026-02-24T10:30:00Z",
                "source_file": "Family.ged",
                "individual_count": 21809,
                "family_count": 8500,
                "summary": {},
            }
        ]
        with (
            patch("app.main._load_gedcom_versions", return_value=versions),
            patch("app.main._load_gedcom_enrichment_queue_count", return_value=12),
        ):
            resp = admin_client.get("/admin/gedcom")
            assert resp.status_code == 200
            assert "Re-Enrichment Queue" in resp.text
            assert "12" in resp.text

    def test_shows_upload_form(self, admin_client):
        """Page shows the upload form with notes field."""
        with (
            patch("app.main._load_gedcom_versions", return_value=[]),
            patch("app.main._load_gedcom_enrichment_queue_count", return_value=0),
        ):
            resp = admin_client.get("/admin/gedcom")
            assert resp.status_code == 200
            assert 'type="file"' in resp.text
            assert "Upload" in resp.text
            assert "notes" in resp.text.lower()

    def test_admin_nav_bar_present(self, admin_client):
        """Page includes the admin navigation bar."""
        with (
            patch("app.main._load_gedcom_versions", return_value=[]),
            patch("app.main._load_gedcom_enrichment_queue_count", return_value=0),
        ):
            resp = admin_client.get("/admin/gedcom")
            assert resp.status_code == 200
            assert "admin-nav-bar" in resp.text


# --- Upload Tests ---


class TestGedcomUpload:
    """Tests for the GEDCOM upload endpoint (AD-164)."""

    def test_upload_no_file_returns_error(self, admin_client):
        """Upload with no file shows error message."""
        with (
            patch("app.main._load_gedcom_versions", return_value=[]),
            patch("app.main._load_gedcom_enrichment_queue_count", return_value=0),
        ):
            resp = admin_client.post("/admin/gedcom/upload")
            assert resp.status_code == 200
            assert "No file selected" in resp.text


# --- Apply/Cancel Tests ---


class TestGedcomApplyCancel:
    """Tests for apply/cancel of GEDCOM upload preview (AD-164)."""

    def test_cancel_clears_preview(self, admin_client):
        """Cancel endpoint clears the upload preview and returns cancellation message."""
        import app.admin_routes as admin_mod

        admin_mod._gedcom_upload_preview = {"tmp_path": "/nonexistent/test.ged"}
        resp = admin_client.post("/admin/gedcom/cancel")
        assert resp.status_code == 200
        assert "cancelled" in resp.text.lower()
        assert admin_mod._gedcom_upload_preview is None

    def test_apply_with_no_preview_returns_error(self, admin_client):
        """Apply without a pending preview returns an error."""
        import app.admin_routes as admin_mod

        admin_mod._gedcom_upload_preview = None
        resp = admin_client.post("/admin/gedcom/apply")
        assert resp.status_code == 200
        assert "No pending upload" in resp.text


# --- Helper Function Tests ---


class TestGedcomVersionHelpers:
    """Tests for GEDCOM version helper functions."""

    def test_load_versions_returns_empty_when_no_supabase(self):
        """_load_gedcom_versions returns empty list when Supabase is not configured."""
        from app.main import _load_gedcom_versions

        with patch("app.supabase_data.get_supabase_client", return_value=None):
            result = _load_gedcom_versions()
            assert result == []

    def test_load_versions_returns_data(self):
        """_load_gedcom_versions returns version list from Supabase."""
        from app.main import _load_gedcom_versions

        mock_sb = MagicMock()
        mock_resp = MagicMock()
        mock_resp.data = [
            {"version_number": 2, "source_file": "v2.ged"},
            {"version_number": 1, "source_file": "v1.ged"},
        ]
        mock_sb.table.return_value.select.return_value.order.return_value.execute.return_value = mock_resp
        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
            result = _load_gedcom_versions()
            assert len(result) == 2
            assert result[0]["version_number"] == 2

    def test_load_versions_handles_error(self):
        """_load_gedcom_versions returns empty on error."""
        from app.main import _load_gedcom_versions

        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.order.return_value.execute.side_effect = Exception("DB error")
        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
            result = _load_gedcom_versions()
            assert result == []

    def test_load_enrichment_count_returns_zero_when_no_supabase(self):
        """_load_gedcom_enrichment_queue_count returns 0 when Supabase not configured."""
        from app.main import _load_gedcom_enrichment_queue_count

        with patch("app.supabase_data.get_supabase_client", return_value=None):
            result = _load_gedcom_enrichment_queue_count()
            assert result == 0

    def test_load_enrichment_count_returns_count(self):
        """_load_gedcom_enrichment_queue_count returns count from Supabase."""
        from app.main import _load_gedcom_enrichment_queue_count

        mock_sb = MagicMock()
        mock_resp = MagicMock()
        mock_resp.count = 7
        mock_resp.data = [{"id": "a"}, {"id": "b"}, {"id": "c"}, {"id": "d"}, {"id": "e"}, {"id": "f"}, {"id": "g"}]
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_resp
        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
            result = _load_gedcom_enrichment_queue_count()
            assert result == 7

    def test_load_enrichment_count_handles_error(self):
        """_load_gedcom_enrichment_queue_count returns 0 on error."""
        from app.main import _load_gedcom_enrichment_queue_count

        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.side_effect = Exception("DB error")
        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
            result = _load_gedcom_enrichment_queue_count()
            assert result == 0


# --- Navigation Tests ---


class TestGedcomNavigation:
    """GEDCOM link appears in admin navigation."""

    def test_gedcom_in_admin_nav(self, admin_client):
        """GEDCOM link is present in the admin sidebar navigation."""
        resp = admin_client.get("/")
        assert resp.status_code == 200
        assert "/admin/gedcom" in resp.text
        assert "GEDCOM" in resp.text
