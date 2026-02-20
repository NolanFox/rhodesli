"""Tests for Session 51B bug fixes.

Covers:
- BUG 1: Compare upload honest messaging (no "check back soon" without mechanism)
- BUG 2: Name These Faces admin-only visibility (verified, not a bug)
- BUG 3: Estimate tab removed from /compare page
- BUG 4: Supabase keepalive in health check
"""

import io

import pytest
from unittest.mock import patch, MagicMock
from starlette.testclient import TestClient


# ---------------------------------------------------------------------------
# BUG 1: Compare Upload — Honest Messaging
# ---------------------------------------------------------------------------


class TestCompareUploadHonestMessaging:
    """When InsightFace is not available (production), compare upload
    must give honest messaging, not misleading 'check back soon'."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from app.main import app
        self.client = TestClient(app)

    def _make_insightface_unavailable(self):
        """Context manager to simulate production environment (no InsightFace)."""
        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "insightface" or (name == "insightface.app" and "FaceAnalysis" in str(args)):
                raise ImportError("Simulated: insightface not available")
            return original_import(name, *args, **kwargs)

        return patch.object(builtins, "__import__", side_effect=mock_import)

    def test_upload_no_insightface_with_r2_shows_honest_message(self):
        """When InsightFace unavailable + R2 available, show honest messaging."""
        fake_image = io.BytesIO(b"\xff\xd8\xff\xe0" + b"\x00" * 100)

        with self._make_insightface_unavailable(), \
             patch("core.storage.can_write_r2", return_value=True), \
             patch("app.main._save_compare_upload", return_value="test-upload-123"):
            resp = self.client.post(
                "/api/compare/upload",
                files={"photo": ("test.jpg", fake_image, "image/jpeg")},
            )

        assert resp.status_code == 200
        html = resp.text

        # Must show honest message
        assert "Photo received!" in html
        assert "next analysis batch" in html

        # Must provide actionable alternative
        assert "NolanFox@gmail.com" in html
        assert "mailto:" in html

        # Must NOT show misleading "check back soon"
        assert "Check back soon" not in html
        assert "processed shortly" not in html

    def test_upload_no_insightface_no_r2_shows_email_fallback(self):
        """When neither InsightFace nor R2, show email fallback."""
        fake_image = io.BytesIO(b"\xff\xd8\xff\xe0" + b"\x00" * 100)

        with self._make_insightface_unavailable(), \
             patch("core.storage.can_write_r2", return_value=False):
            resp = self.client.post(
                "/api/compare/upload",
                files={"photo": ("test.jpg", fake_image, "image/jpeg")},
            )

        assert resp.status_code == 200
        html = resp.text

        # Must provide actionable fallback
        assert "NolanFox@gmail.com" in html
        assert "mailto:" in html

        # Must NOT show misleading messages
        assert "Check back soon" not in html
        assert "processed shortly" not in html

    def test_upload_no_file_returns_error(self):
        """POST without file returns error message."""
        resp = self.client.post("/api/compare/upload")
        assert resp.status_code == 200
        assert "No photo uploaded" in resp.text

    def test_upload_invalid_type_returns_error(self):
        """POST with non-image file returns validation error."""
        fake_file = io.BytesIO(b"not an image")
        resp = self.client.post(
            "/api/compare/upload",
            files={"photo": ("test.txt", fake_file, "text/plain")},
        )
        assert resp.status_code == 200
        assert "JPG or PNG" in resp.text


# ---------------------------------------------------------------------------
# BUG 2: Name These Faces — Admin-Only (Verified Correct)
# ---------------------------------------------------------------------------


def _make_photo_meta(face_count=3):
    """Build mock photo metadata with configurable face counts."""
    faces = []
    for i in range(face_count):
        faces.append({
            "face_id": f"face-{i}",
            "bbox": [10 + i * 100, 10, 90 + i * 100, 90],
        })
    return {
        "filename": "test_group.jpg",
        "faces": faces,
        "source": "Test Collection",
    }


def _identity_for_face(identified_set):
    """Return a mock get_identity_for_face that marks certain faces as identified."""
    def _get(registry, face_id):
        idx = int(face_id.split("-")[1])
        if idx in identified_set:
            return {
                "identity_id": f"id-{idx}",
                "name": f"Person {idx}",
                "state": "CONFIRMED",
            }
        return {
            "identity_id": f"id-{idx}",
            "name": f"Unidentified Person {idx}",
            "state": "INBOX",
        }
    return _get


class TestNameTheseFacesVisibility51B:
    """'Name These Faces' button is correctly admin-only per AD-104.
    Regression test confirming this is NOT a bug."""

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    @patch("app.main.get_identity_for_face")
    def test_button_visible_for_admin_with_unidentified(self, mock_get_id, mock_reg, mock_dim, mock_meta):
        """Admin sees button when 2+ unidentified faces exist."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = _make_photo_meta(face_count=4)
        mock_get_id.side_effect = _identity_for_face(set())
        mock_reg.return_value = MagicMock()

        result = photo_view_content("p1", is_partial=True, is_admin=True)
        html = to_xml(result)
        assert "Name These Faces" in html
        assert "4 unidentified" in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    @patch("app.main.get_identity_for_face")
    def test_button_hidden_for_non_admin(self, mock_get_id, mock_reg, mock_dim, mock_meta):
        """Non-admin does NOT see button even with unidentified faces."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = _make_photo_meta(face_count=4)
        mock_get_id.side_effect = _identity_for_face(set())
        mock_reg.return_value = MagicMock()

        result = photo_view_content("p1", is_partial=True, is_admin=False)
        html = to_xml(result)
        assert "Name These Faces" not in html


# ---------------------------------------------------------------------------
# BUG 3: Estimate Tab Removed from Compare Page
# ---------------------------------------------------------------------------


class TestEstimateTabRemoved:
    """Estimate Year tab should NOT appear on /compare page.
    /estimate is now a standalone top-nav item."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from app.main import app
        self.client = TestClient(app)

    def test_compare_page_no_estimate_year_tab(self):
        """/compare page should NOT have 'Estimate Year' text as tab."""
        resp = self.client.get("/compare")
        assert resp.status_code == 200
        assert "Estimate Year" not in resp.text

    def test_estimate_page_no_compare_faces_tab(self):
        """/estimate page should NOT have 'Compare Faces' as tab text."""
        resp = self.client.get("/estimate")
        assert resp.status_code == 200
        # "Compare Faces" may appear in the top nav as just "Compare",
        # but the specific tab text "Compare Faces" should not appear
        assert "Compare Faces" not in resp.text

    def test_compare_page_still_functional(self):
        """/compare page renders correctly without tabs."""
        resp = self.client.get("/compare")
        assert resp.status_code == 200
        # Page header and upload form still present
        assert "Compare" in resp.text
        assert "upload" in resp.text.lower()

    def test_estimate_page_still_functional(self):
        """/estimate page renders correctly without tabs."""
        resp = self.client.get("/estimate")
        assert resp.status_code == 200
        assert "When Was This Photo Taken" in resp.text


# ---------------------------------------------------------------------------
# BUG 4: Supabase Keepalive in Health Check
# ---------------------------------------------------------------------------


class TestSupabaseKeepalive:
    """Health check should include Supabase connectivity status
    to prevent free-tier inactivity pause."""

    @pytest.fixture(autouse=True)
    def setup(self):
        import app.main as main_mod
        from app.main import app
        self.client = TestClient(app)
        # Reset throttle so each test gets a fresh ping window
        main_mod._supabase_last_ping = 0.0

    def test_health_check_includes_supabase_status(self):
        """Health check response includes 'supabase' key."""
        resp = self.client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "supabase" in data, \
            f"Health check missing 'supabase' key. Got: {list(data.keys())}"

    def test_health_check_supabase_not_configured(self):
        """When Supabase env vars not set, status is 'not_configured'."""
        from app.main import _ping_supabase
        with patch.dict("os.environ", {"SUPABASE_URL": "", "SUPABASE_ANON_KEY": ""}):
            result = _ping_supabase()
            assert result == "not_configured"

    def test_health_check_still_returns_core_data(self):
        """Health check still returns identity/photo counts."""
        resp = self.client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert data["status"] == "ok"
        assert "identities" in data
        assert "photos" in data

    def test_ping_supabase_handles_error(self):
        """_ping_supabase returns error string on connection failure."""
        from app.main import _ping_supabase
        with patch.dict("os.environ", {"SUPABASE_URL": "https://fake.supabase.co", "SUPABASE_ANON_KEY": "eyJfake"}), \
             patch("httpx.get", side_effect=Exception("Connection refused")):
            result = _ping_supabase()
            assert result.startswith("error:")

    def test_ping_throttled_within_interval(self):
        """Second ping within interval returns 'skipped'."""
        import time
        import app.main as main_mod
        from app.main import _ping_supabase
        # Simulate a recent successful ping
        main_mod._supabase_last_ping = time.time()
        result = _ping_supabase()
        assert result == "skipped"

    def test_ping_fires_after_interval(self):
        """Ping fires again after interval elapses."""
        import time
        import app.main as main_mod
        from app.main import _ping_supabase
        # Simulate ping from over an hour ago
        main_mod._supabase_last_ping = time.time() - 3601
        with patch.dict("os.environ", {"SUPABASE_URL": "", "SUPABASE_ANON_KEY": ""}):
            result = _ping_supabase()
            assert result == "not_configured"  # Fires (not skipped), but env vars empty

    def test_first_ping_always_fires(self):
        """First call (timestamp=0) always fires, never skipped."""
        import app.main as main_mod
        from app.main import _ping_supabase
        main_mod._supabase_last_ping = 0.0
        with patch.dict("os.environ", {"SUPABASE_URL": "", "SUPABASE_ANON_KEY": ""}):
            result = _ping_supabase()
            assert result != "skipped"


# ---------------------------------------------------------------------------
# Auth Disabled Warning
# ---------------------------------------------------------------------------


class TestAuthDisabledWarning:
    """When auth is disabled, _auth_disabled_warning returns a banner."""

    def test_auth_warning_returns_element_when_disabled(self):
        """_auth_disabled_warning returns warning when auth is disabled."""
        from app.main import _auth_disabled_warning, to_xml
        with patch("app.main.is_auth_enabled", return_value=False):
            result = _auth_disabled_warning()
            assert result is not None
            html = to_xml(result)
            assert "auth-disabled-warning" in html
            assert "Authentication is disabled" in html

    def test_auth_warning_returns_none_when_enabled(self):
        """_auth_disabled_warning returns None when auth is enabled."""
        from app.main import _auth_disabled_warning
        with patch("app.main.is_auth_enabled", return_value=True):
            result = _auth_disabled_warning()
            assert result is None
