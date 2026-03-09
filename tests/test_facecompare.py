"""
Tests for Face Compare routes — /facecompare redirects + API endpoints.

Session 59: Original standalone face comparison tool.
Post-Session 95 (ROUTE-001): /facecompare redirects to /tools/compare.
API endpoints and helper functions still live in match_facecompare_routes.py.
"""

import io
import json
import pickle
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from starlette.testclient import TestClient


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app, follow_redirects=False)


@pytest.fixture
def following_client():
    """Client that follows redirects (for API tests)."""
    from app.main import app

    return TestClient(app)


# ============================================================================
# Phase 1: Landing Page Redirects (ROUTE-001)
# ============================================================================


class TestFaceCompareRedirects:
    """/facecompare now redirects to /tools/compare (ROUTE-001)."""

    def test_facecompare_redirects_to_tools_compare(self, client):
        """GET /facecompare returns 301 redirect to /tools/compare."""
        with patch("app.main.is_auth_enabled", return_value=False):
            resp = client.get("/facecompare")
            assert resp.status_code == 301
            assert resp.headers["location"] == "/tools/compare"

    def test_facecompare_result_redirects(self, client):
        """GET /facecompare/result/{id} returns 301 redirect."""
        with patch("app.main.is_auth_enabled", return_value=False):
            resp = client.get("/facecompare/result/some-result-id")
            assert resp.status_code == 301
            assert resp.headers["location"] == "/compare/result/some-result-id"

    def test_facecompare_redirect_no_auth_required(self, client):
        """Redirect works without authentication."""
        with (
            patch("app.main.is_auth_enabled", return_value=True),
            patch("app.main.get_current_user", return_value=None),
        ):
            resp = client.get("/facecompare")
            assert resp.status_code == 301

    def test_existing_compare_still_works(self, following_client):
        """Existing /compare page is unmodified and still works."""
        with patch("app.main.is_auth_enabled", return_value=False):
            resp = following_client.get("/compare")
            assert resp.status_code == 200
            assert "Compare" in resp.text


# ============================================================================
# Phase 2: Upload Flow (API endpoints still active)
# ============================================================================


class TestFaceCompareUpload:
    """Tests for the /api/facecompare/upload endpoint."""

    @pytest.fixture
    def api_client(self):
        from app.main import app

        return TestClient(app)

    def _make_test_image(self):
        """Create a minimal valid JPEG in memory."""
        from PIL import Image

        img = Image.new("RGB", (100, 100), color="red")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        buf.seek(0)
        return buf

    def test_upload_rejects_no_file(self, api_client):
        """Upload with no file returns error message."""
        with patch("app.main.is_auth_enabled", return_value=False):
            resp = api_client.post("/api/facecompare/upload")
            assert resp.status_code == 200
            assert "No photo uploaded" in resp.text

    def test_upload_rejects_non_image(self, api_client):
        """Upload rejects non-image files."""
        with patch("app.main.is_auth_enabled", return_value=False):
            resp = api_client.post("/api/facecompare/upload", files={"photo": ("test.txt", b"hello", "text/plain")})
            assert resp.status_code == 200
            assert "JPEG" in resp.text or "PNG" in resp.text or "WebP" in resp.text

    def test_upload_rejects_large_file(self, api_client):
        """Upload rejects files over 10MB."""
        with patch("app.main.is_auth_enabled", return_value=False):
            big_content = b"x" * (11 * 1024 * 1024)
            resp = api_client.post("/api/facecompare/upload", files={"photo": ("big.jpg", big_content, "image/jpeg")})
            assert resp.status_code == 200
            assert "too large" in resp.text

    def test_upload_accepts_jpeg(self, api_client):
        """Upload endpoint accepts JPEG files without crashing."""
        buf = self._make_test_image()
        with patch("app.main.is_auth_enabled", return_value=False):
            resp = api_client.post("/api/facecompare/upload", files={"photo": ("test.jpg", buf, "image/jpeg")})
            assert resp.status_code == 200
            # Should either process the photo or show a graceful message
            assert "fc-results" in resp.text or "being set up" in resp.text

    def test_upload_accepts_webp(self, api_client):
        """Upload endpoint accepts WebP suffix."""
        with patch("app.main.is_auth_enabled", return_value=False):
            resp = api_client.post(
                "/api/facecompare/upload", files={"photo": ("test.webp", b"\x00" * 100, "image/webp")}
            )
            assert resp.status_code == 200


# ============================================================================
# Phase 3: Results (helper functions still in match_facecompare_routes.py)
# ============================================================================


class TestFaceCompareResults:
    """Tests for the face compare results rendering."""

    def test_result_card_tiers(self):
        """Result cards have correct tier data attributes."""
        from app.match_facecompare_routes import _fc_result_card

        with (
            patch("app.main.resolve_face_image_url", return_value="/crop.jpg"),
            patch("app.main.get_photo_id_for_face", return_value="photo1"),
        ):
            card = _fc_result_card(
                {
                    "face_id": "f1",
                    "distance": 1.0,
                    "tier": "STRONG MATCH",
                    "confidence_pct": 90,
                    "identity_name": "Leon",
                    "state": "CONFIRMED",
                    "identity_id": "id1",
                },
                set(),
                0,
            )
            assert card is not None
            html = repr(card)
            assert "fc-result-card" in html
            assert "strong-match" in html

    def test_result_card_possible_match(self):
        """Possible match card renders correctly."""
        from app.match_facecompare_routes import _fc_result_card

        with (
            patch("app.main.resolve_face_image_url", return_value="/crop.jpg"),
            patch("app.main.get_photo_id_for_face", return_value="photo1"),
        ):
            card = _fc_result_card(
                {
                    "face_id": "f2",
                    "distance": 1.2,
                    "tier": "POSSIBLE MATCH",
                    "confidence_pct": 65,
                    "identity_name": "Unknown",
                    "state": "PROPOSED",
                    "identity_id": "",
                },
                set(),
                1,
            )
            assert card is not None
            html = repr(card)
            assert "possible-match" in html

    def test_result_card_no_crop_returns_none(self):
        """Card returns None when crop URL cannot be resolved."""
        from app.match_facecompare_routes import _fc_result_card

        with (
            patch("app.main.resolve_face_image_url", return_value=None),
            patch("app.main.get_photo_id_for_face", return_value=None),
        ):
            card = _fc_result_card(
                {
                    "face_id": "f3",
                    "distance": 1.0,
                    "tier": "STRONG MATCH",
                    "confidence_pct": 90,
                    "identity_name": "",
                    "state": "",
                    "identity_id": "",
                },
                set(),
                0,
            )
            assert card is None

    def test_result_card_shows_percentage_not_raw_float(self):
        """Verify compare results show '90%' not '0.73 similarity' (AD-149 calibration)."""
        from app.match_facecompare_routes import _fc_result_card

        with (
            patch("app.main.resolve_face_image_url", return_value="/crop.jpg"),
            patch("app.main.get_photo_id_for_face", return_value="photo1"),
        ):
            card = _fc_result_card(
                {
                    "face_id": "f1",
                    "distance": 0.8,
                    "tier": "STRONG MATCH",
                    "confidence_pct": 90,
                    "identity_name": "Test Person",
                    "state": "CONFIRMED",
                    "identity_id": "id1",
                },
                set(),
                0,
            )
            html = repr(card)
            assert "90%" in html
            assert "0.8 similarity" not in html
            assert "0.80 similarity" not in html

    def test_result_card_shows_calibrated_confidence_labels(self):
        """Verify confidence labels use calibrated thresholds (AD-091)."""
        from app.match_facecompare_routes import _fc_result_card

        test_cases = [
            (90, "Very likely same person"),
            (75, "Strong match"),
            (55, "Possible match"),
            (30, "Some similarity"),
        ]
        for pct, expected_label in test_cases:
            with (
                patch("app.main.resolve_face_image_url", return_value="/crop.jpg"),
                patch("app.main.get_photo_id_for_face", return_value="photo1"),
            ):
                card = _fc_result_card(
                    {
                        "face_id": "f1",
                        "distance": 1.0,
                        "tier": "STRONG MATCH",
                        "confidence_pct": pct,
                        "identity_name": "Test",
                        "state": "CONFIRMED",
                        "identity_id": "id1",
                    },
                    set(),
                    0,
                )
                html = repr(card)
                assert expected_label in html, f"Expected '{expected_label}' for {pct}%, got: {html[:200]}"

    def test_results_section_empty_state(self):
        """Results section shows empty state when no matches."""
        from app.match_facecompare_routes import _fc_results_section

        section = _fc_results_section([], set())
        html = repr(section)
        assert "fc-empty-state" in html

    def test_results_section_with_matches(self):
        """Results section shows match cards when matches exist."""
        from app.match_facecompare_routes import _fc_results_section

        mock_results = [
            {
                "face_id": "f1",
                "distance": 1.0,
                "tier": "STRONG MATCH",
                "confidence_pct": 90,
                "identity_name": "Leon",
                "state": "CONFIRMED",
                "identity_id": "id1",
            },
        ]

        with (
            patch("app.main.resolve_face_image_url", return_value="/crop.jpg"),
            patch("app.main.get_photo_id_for_face", return_value="photo1"),
        ):
            section = _fc_results_section(mock_results, set())
            html = repr(section)
            assert "fc-result-card" in html
            assert "fc-match-summary" in html

    def test_results_section_with_date(self):
        """Results section shows date estimation."""
        from app.match_facecompare_routes import _fc_results_section

        date_info = {
            "predicted_decade": 1930,
            "confidence": 0.7,
            "expected_year": 1935,
            "decade_probabilities": {"1920": 0.1, "1930": 0.7, "1940": 0.2},
        }

        section = _fc_results_section([], set(), date_info=date_info)
        html = repr(section)
        assert "fc-date-estimate" in html
        assert "1930" in html

    def test_results_collection_name(self):
        """Results include collection name."""
        from app.match_facecompare_routes import _fc_result_card

        with (
            patch("app.main.resolve_face_image_url", return_value="/crop.jpg"),
            patch("app.main.get_photo_id_for_face", return_value="photo1"),
        ):
            card = _fc_result_card(
                {
                    "face_id": "f1",
                    "distance": 1.0,
                    "tier": "STRONG MATCH",
                    "confidence_pct": 90,
                    "identity_name": "Leon",
                    "state": "CONFIRMED",
                    "identity_id": "id1",
                },
                set(),
                0,
            )
            html = repr(card)
            assert "Jews of Rhodes Community Archive" in html

    def test_results_person_link(self):
        """Identified persons have links to their person pages."""
        from app.match_facecompare_routes import _fc_result_card

        with (
            patch("app.main.resolve_face_image_url", return_value="/crop.jpg"),
            patch("app.main.get_photo_id_for_face", return_value="photo1"),
        ):
            card = _fc_result_card(
                {
                    "face_id": "f1",
                    "distance": 1.0,
                    "tier": "STRONG MATCH",
                    "confidence_pct": 90,
                    "identity_name": "Leon Franco",
                    "state": "CONFIRMED",
                    "identity_id": "id1",
                },
                set(),
                0,
            )
            html = repr(card)
            assert "/person/id1" in html
            assert "Leon" in html

    def test_results_have_share_button(self):
        """Results section includes share button when result_id is provided."""
        from app.match_facecompare_routes import _fc_results_section

        mock_results = [
            {
                "face_id": "f1",
                "distance": 1.0,
                "tier": "STRONG MATCH",
                "confidence_pct": 90,
                "identity_name": "Leon",
                "state": "CONFIRMED",
                "identity_id": "id1",
            },
        ]

        with (
            patch("app.main.resolve_face_image_url", return_value="/crop.jpg"),
            patch("app.main.get_photo_id_for_face", return_value="photo1"),
        ):
            section = _fc_results_section(mock_results, set(), result_id="abc123")
            html = repr(section)
            assert "fc-share-btn" in html

    def test_results_have_bridge_ctas(self):
        """Results include bridge CTAs to the archive."""
        from app.match_facecompare_routes import _fc_results_section

        mock_results = [
            {
                "face_id": "f1",
                "distance": 1.0,
                "tier": "STRONG MATCH",
                "confidence_pct": 90,
                "identity_name": "Leon",
                "state": "CONFIRMED",
                "identity_id": "id1",
            },
        ]

        with (
            patch("app.main.resolve_face_image_url", return_value="/crop.jpg"),
            patch("app.main.get_photo_id_for_face", return_value="photo1"),
        ):
            section = _fc_results_section(mock_results, set(), result_id="abc123")
            html = repr(section)
            assert "fc-bridge-ctas" in html
            assert "Explore the full archive" in html
            assert "Try another photo" in html


# ============================================================================
# Face selector (API still active)
# ============================================================================


class TestFaceCompareSelector:
    """Tests for the face selection endpoint."""

    @pytest.fixture
    def api_client(self):
        from app.main import app

        return TestClient(app)

    def test_select_missing_upload(self, api_client):
        """Select with missing upload returns error."""
        with patch("app.main.is_auth_enabled", return_value=False):
            resp = api_client.post("/api/facecompare/select?upload_id=nonexistent&face_idx=0")
            assert resp.status_code == 200
            assert "not found" in resp.text.lower() or "try again" in resp.text.lower()

    def test_select_with_valid_data(self, api_client, tmp_path):
        """Select with valid upload data runs comparison."""
        upload_dir = Path("uploads/facecompare")
        upload_dir.mkdir(parents=True, exist_ok=True)
        test_id = "test_sel_123"

        face_data = [{"mu": np.random.randn(512).astype(np.float32).tolist(), "bbox": [10, 10, 50, 50]}]
        (upload_dir / f"{test_id}_faces.pkl").write_bytes(pickle.dumps(face_data))

        from PIL import Image

        img = Image.new("RGB", (100, 100))
        img.save(str(upload_dir / f"{test_id}.jpg"))

        mock_results = [
            {
                "face_id": "f1",
                "distance": 1.0,
                "tier": "STRONG MATCH",
                "confidence_pct": 90,
                "identity_name": "Test",
                "state": "CONFIRMED",
                "identity_id": "id1",
            }
        ]

        with (
            patch("app.main.is_auth_enabled", return_value=False),
            patch("app.main.get_face_data", return_value={}),
            patch("app.main.load_registry") as mock_reg,
            patch("app.main.get_crop_files", return_value=set()),
            patch("core.neighbors.find_similar_faces", return_value=mock_results),
            patch("app.main._save_comparison_result"),
            patch("app.main._generate_result_id", return_value="res123"),
        ):
            mock_reg.return_value = MagicMock()
            resp = api_client.post(f"/api/facecompare/select?upload_id={test_id}&face_idx=0")
            assert resp.status_code == 200
            assert "fc-results" in resp.text

        # Cleanup
        for f in upload_dir.glob(f"{test_id}*"):
            f.unlink()


# ============================================================================
# Cross-cutting: No auth required for redirects
# ============================================================================


class TestFaceCompareNoLoginRequired:
    """Verify the facecompare redirects work without authentication."""

    def test_landing_no_auth(self, client):
        """Landing page redirect works with auth enabled but no user."""
        with (
            patch("app.main.is_auth_enabled", return_value=True),
            patch("app.main.get_current_user", return_value=None),
        ):
            resp = client.get("/facecompare")
            assert resp.status_code == 301

    def test_upload_no_auth(self, following_client):
        """Upload endpoint works without auth."""
        with patch("app.main.is_auth_enabled", return_value=True):
            resp = following_client.post("/api/facecompare/upload")
            assert resp.status_code == 200

    def test_shareable_no_auth(self, client):
        """Shareable URLs redirect without auth."""
        with patch("app.main.is_auth_enabled", return_value=True):
            resp = client.get("/facecompare/result/nonexistent")
            assert resp.status_code == 301
