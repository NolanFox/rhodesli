"""
Tests for Face Compare Standalone at /facecompare.

Session 59: Standalone face comparison tool — separate from /compare.
No login required, no archive nav, museum-quality design.
Tests cover: landing page, upload flow, results, shareable URLs.
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
    return TestClient(app)


# ============================================================================
# Phase 1: Landing Page
# ============================================================================

class TestFaceCompareLanding:
    """Tests for the /facecompare standalone landing page."""

    def test_landing_returns_200(self, client):
        """Landing page renders at /facecompare."""
        with patch("app.main.is_auth_enabled", return_value=False):
            resp = client.get("/facecompare")
            assert resp.status_code == 200

    def test_landing_has_upload_form(self, client):
        """Landing page contains upload form/button."""
        with patch("app.main.is_auth_enabled", return_value=False):
            resp = client.get("/facecompare")
            assert 'data-testid="fc-upload-form"' in resp.text
            assert 'data-testid="fc-file-input"' in resp.text

    def test_landing_no_archive_nav(self, client):
        """Landing page does NOT contain the archive navigation bar."""
        with patch("app.main.is_auth_enabled", return_value=False):
            resp = client.get("/facecompare")
            html = resp.text
            # Should NOT have the standard archive nav links
            assert 'href="/photos"' not in html or 'Explore the full archive' in html
            # Should NOT have the archive nav pattern (Collections, People, Map, Timeline in nav)
            assert 'href="/collections"' not in html
            assert 'href="/people"' not in html

    def test_landing_has_meta_tags(self, client):
        """Landing page has SEO meta tags."""
        with patch("app.main.is_auth_enabled", return_value=False):
            resp = client.get("/facecompare")
            html = resp.text
            assert "og:title" in html
            assert "og:description" in html
            assert "Face Compare" in html

    def test_landing_has_title(self, client):
        """Landing page has proper title."""
        with patch("app.main.is_auth_enabled", return_value=False):
            resp = client.get("/facecompare")
            assert "Face Compare" in resp.text

    def test_landing_has_how_it_works(self, client):
        """Landing page has How It Works section."""
        with patch("app.main.is_auth_enabled", return_value=False):
            resp = client.get("/facecompare")
            assert 'data-testid="fc-how-it-works"' in resp.text
            assert "Upload" in resp.text
            assert "Detect" in resp.text
            assert "Discover" in resp.text

    def test_landing_has_hero(self, client):
        """Landing page has hero section with headline."""
        with patch("app.main.is_auth_enabled", return_value=False):
            resp = client.get("/facecompare")
            assert 'data-testid="fc-hero"' in resp.text
            assert "Who is in your photo?" in resp.text

    def test_landing_has_footer_privacy(self, client):
        """Landing page has footer with privacy note."""
        with patch("app.main.is_auth_enabled", return_value=False):
            resp = client.get("/facecompare")
            assert "not stored permanently" in resp.text

    def test_landing_has_serif_font(self, client):
        """Landing page loads Cormorant Garamond serif font."""
        with patch("app.main.is_auth_enabled", return_value=False):
            resp = client.get("/facecompare")
            assert "Cormorant Garamond" in resp.text

    def test_landing_has_htmx(self, client):
        """Landing page includes HTMX for dynamic upload."""
        with patch("app.main.is_auth_enabled", return_value=False):
            resp = client.get("/facecompare")
            assert "htmx.org" in resp.text

    def test_existing_compare_still_works(self, client):
        """Existing /compare page is unmodified and still works."""
        with patch("app.main.is_auth_enabled", return_value=False):
            resp = client.get("/compare")
            assert resp.status_code == 200
            # Should have archive nav elements
            assert "Compare" in resp.text


# ============================================================================
# Phase 2: Upload Flow
# ============================================================================

class TestFaceCompareUpload:
    """Tests for the /api/facecompare/upload endpoint."""

    def _make_test_image(self):
        """Create a minimal valid JPEG in memory."""
        from PIL import Image
        img = Image.new("RGB", (100, 100), color="red")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        buf.seek(0)
        return buf

    def test_upload_rejects_no_file(self, client):
        """Upload with no file returns error message."""
        with patch("app.main.is_auth_enabled", return_value=False):
            resp = client.post("/api/facecompare/upload")
            assert resp.status_code == 200
            assert "No photo uploaded" in resp.text

    def test_upload_rejects_non_image(self, client):
        """Upload rejects non-image files."""
        with patch("app.main.is_auth_enabled", return_value=False):
            resp = client.post("/api/facecompare/upload",
                               files={"photo": ("test.txt", b"hello", "text/plain")})
            assert resp.status_code == 200
            assert "JPEG" in resp.text or "PNG" in resp.text or "WebP" in resp.text

    def test_upload_rejects_large_file(self, client):
        """Upload rejects files over 10MB."""
        with patch("app.main.is_auth_enabled", return_value=False):
            big_content = b"x" * (11 * 1024 * 1024)
            resp = client.post("/api/facecompare/upload",
                               files={"photo": ("big.jpg", big_content, "image/jpeg")})
            assert resp.status_code == 200
            assert "too large" in resp.text

    def test_upload_accepts_jpeg(self, client):
        """Upload endpoint accepts JPEG files without crashing."""
        buf = self._make_test_image()
        with patch("app.main.is_auth_enabled", return_value=False):
            resp = client.post("/api/facecompare/upload",
                               files={"photo": ("test.jpg", buf, "image/jpeg")})
            assert resp.status_code == 200
            # Should either process the photo or show a graceful message
            assert "fc-results" in resp.text or "being set up" in resp.text

    def test_upload_accepts_webp(self, client):
        """Upload endpoint accepts WebP suffix."""
        with patch("app.main.is_auth_enabled", return_value=False):
            # Just test validation — the actual image content doesn't matter for suffix check
            resp = client.post("/api/facecompare/upload",
                               files={"photo": ("test.webp", b"\x00" * 100, "image/webp")})
            assert resp.status_code == 200
            # Either processes or gracefully handles (no 400/500 crash)


# ============================================================================
# Phase 3: Results
# ============================================================================

class TestFaceCompareResults:
    """Tests for the face compare results rendering."""

    def test_result_card_tiers(self):
        """Result cards have correct tier data attributes."""
        from app.main import _fc_result_card

        with patch("app.main.resolve_face_image_url", return_value="/crop.jpg"), \
             patch("app.main.get_photo_id_for_face", return_value="photo1"):
            card = _fc_result_card(
                {"face_id": "f1", "distance": 1.0, "tier": "STRONG MATCH",
                 "confidence_pct": 90, "identity_name": "Leon", "state": "CONFIRMED",
                 "identity_id": "id1"},
                set(), 0,
            )
            assert card is not None
            html = repr(card)
            assert "fc-result-card" in html
            assert "strong-match" in html

    def test_result_card_possible_match(self):
        """Possible match card renders correctly."""
        from app.main import _fc_result_card

        with patch("app.main.resolve_face_image_url", return_value="/crop.jpg"), \
             patch("app.main.get_photo_id_for_face", return_value="photo1"):
            card = _fc_result_card(
                {"face_id": "f2", "distance": 1.2, "tier": "POSSIBLE MATCH",
                 "confidence_pct": 65, "identity_name": "Unknown", "state": "PROPOSED",
                 "identity_id": ""},
                set(), 1,
            )
            assert card is not None
            html = repr(card)
            assert "possible-match" in html

    def test_result_card_no_crop_returns_none(self):
        """Card returns None when crop URL cannot be resolved."""
        from app.main import _fc_result_card

        with patch("app.main.resolve_face_image_url", return_value=None), \
             patch("app.main.get_photo_id_for_face", return_value=None):
            card = _fc_result_card(
                {"face_id": "f3", "distance": 1.0, "tier": "STRONG MATCH",
                 "confidence_pct": 90, "identity_name": "", "state": "",
                 "identity_id": ""},
                set(), 0,
            )
            assert card is None

    def test_results_section_empty_state(self):
        """Results section shows empty state when no matches."""
        from app.main import _fc_results_section

        section = _fc_results_section([], set())
        html = repr(section)
        assert "fc-empty-state" in html

    def test_results_section_with_matches(self):
        """Results section shows match cards when matches exist."""
        from app.main import _fc_results_section

        mock_results = [
            {"face_id": "f1", "distance": 1.0, "tier": "STRONG MATCH",
             "confidence_pct": 90, "identity_name": "Leon", "state": "CONFIRMED",
             "identity_id": "id1"},
        ]

        with patch("app.main.resolve_face_image_url", return_value="/crop.jpg"), \
             patch("app.main.get_photo_id_for_face", return_value="photo1"):
            section = _fc_results_section(mock_results, set())
            html = repr(section)
            assert "fc-result-card" in html
            assert "fc-match-summary" in html

    def test_results_section_with_date(self):
        """Results section shows date estimation."""
        from app.main import _fc_results_section

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
        from app.main import _fc_result_card

        with patch("app.main.resolve_face_image_url", return_value="/crop.jpg"), \
             patch("app.main.get_photo_id_for_face", return_value="photo1"):
            card = _fc_result_card(
                {"face_id": "f1", "distance": 1.0, "tier": "STRONG MATCH",
                 "confidence_pct": 90, "identity_name": "Leon", "state": "CONFIRMED",
                 "identity_id": "id1"},
                set(), 0,
            )
            html = repr(card)
            assert "Jews of Rhodes Community Archive" in html

    def test_results_person_link(self):
        """Identified persons have links to their person pages."""
        from app.main import _fc_result_card

        with patch("app.main.resolve_face_image_url", return_value="/crop.jpg"), \
             patch("app.main.get_photo_id_for_face", return_value="photo1"):
            card = _fc_result_card(
                {"face_id": "f1", "distance": 1.0, "tier": "STRONG MATCH",
                 "confidence_pct": 90, "identity_name": "Leon Franco", "state": "CONFIRMED",
                 "identity_id": "id1"},
                set(), 0,
            )
            html = repr(card)
            assert "/person/id1" in html
            assert "Leon" in html


# ============================================================================
# Phase 4: Shareable Results
# ============================================================================

class TestFaceCompareShareable:
    """Tests for shareable result URLs."""

    def test_shareable_404_for_missing(self, client):
        """Shareable URL returns 404-style page for non-existent UUID."""
        with patch("app.main.is_auth_enabled", return_value=False):
            resp = client.get("/facecompare/result/nonexistent123")
            assert resp.status_code == 200  # Page renders (custom 404 within page)
            assert "not found" in resp.text.lower()

    def test_shareable_renders_result(self, client):
        """Shareable URL renders saved results."""
        from app.main import _save_comparison_result, _generate_result_id

        rid = _generate_result_id()
        _save_comparison_result({
            "result_id": rid,
            "created_at": "2026-02-22T00:00:00Z",
            "query_type": "facecompare_upload",
            "upload_id": "test123",
            "face_index": 0,
            "date_estimation": {"predicted_decade": 1930, "confidence": 0.7,
                                "expected_year": 1935,
                                "decade_probabilities": {"1930": 0.7}},
            "matches": [{"face_id": "f1", "identity_id": "", "identity_name": "",
                         "distance": 1.0, "confidence_pct": 90, "tier": "STRONG MATCH"}],
            "responses": [],
        })

        with patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main.get_crop_files", return_value=set()):
            resp = client.get(f"/facecompare/result/{rid}")
            assert resp.status_code == 200
            assert "Face Compare" in resp.text

    def test_shareable_has_og_tags(self, client):
        """Shareable result page has OG meta tags."""
        from app.main import _save_comparison_result, _generate_result_id

        rid = _generate_result_id()
        _save_comparison_result({
            "result_id": rid,
            "created_at": "2026-02-22T00:00:00Z",
            "query_type": "facecompare_upload",
            "matches": [],
            "responses": [],
        })

        with patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main.get_crop_files", return_value=set()):
            resp = client.get(f"/facecompare/result/{rid}")
            assert "og:title" in resp.text
            assert "og:description" in resp.text

    def test_results_have_share_button(self):
        """Results section includes share button when result_id is provided."""
        from app.main import _fc_results_section

        mock_results = [
            {"face_id": "f1", "distance": 1.0, "tier": "STRONG MATCH",
             "confidence_pct": 90, "identity_name": "Leon", "state": "CONFIRMED",
             "identity_id": "id1"},
        ]

        with patch("app.main.resolve_face_image_url", return_value="/crop.jpg"), \
             patch("app.main.get_photo_id_for_face", return_value="photo1"):
            section = _fc_results_section(mock_results, set(), result_id="abc123")
            html = repr(section)
            assert "fc-share-btn" in html

    def test_results_have_bridge_ctas(self):
        """Results include bridge CTAs to the archive."""
        from app.main import _fc_results_section

        mock_results = [
            {"face_id": "f1", "distance": 1.0, "tier": "STRONG MATCH",
             "confidence_pct": 90, "identity_name": "Leon", "state": "CONFIRMED",
             "identity_id": "id1"},
        ]

        with patch("app.main.resolve_face_image_url", return_value="/crop.jpg"), \
             patch("app.main.get_photo_id_for_face", return_value="photo1"):
            section = _fc_results_section(mock_results, set(), result_id="abc123")
            html = repr(section)
            assert "fc-bridge-ctas" in html
            assert "Explore the full archive" in html
            assert "Try another photo" in html


# ============================================================================
# Phase 2D: Face selector
# ============================================================================

class TestFaceCompareSelector:
    """Tests for the face selection endpoint."""

    def test_select_missing_upload(self, client):
        """Select with missing upload returns error."""
        with patch("app.main.is_auth_enabled", return_value=False):
            resp = client.post("/api/facecompare/select?upload_id=nonexistent&face_idx=0")
            assert resp.status_code == 200
            assert "not found" in resp.text.lower() or "try again" in resp.text.lower()

    def test_select_with_valid_data(self, client, tmp_path):
        """Select with valid upload data runs comparison."""
        # Create test face data
        upload_dir = Path("uploads/facecompare")
        upload_dir.mkdir(parents=True, exist_ok=True)
        test_id = "test_sel_123"

        face_data = [{"mu": np.random.randn(512).astype(np.float32).tolist(),
                      "bbox": [10, 10, 50, 50]}]
        (upload_dir / f"{test_id}_faces.pkl").write_bytes(pickle.dumps(face_data))

        # Create dummy image
        from PIL import Image
        img = Image.new("RGB", (100, 100))
        img.save(str(upload_dir / f"{test_id}.jpg"))

        mock_results = [{"face_id": "f1", "distance": 1.0, "tier": "STRONG MATCH",
                        "confidence_pct": 90, "identity_name": "Test",
                        "state": "CONFIRMED", "identity_id": "id1"}]

        with patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main.get_face_data", return_value={}), \
             patch("app.main.load_registry") as mock_reg, \
             patch("app.main.get_crop_files", return_value=set()), \
             patch("core.neighbors.find_similar_faces", return_value=mock_results), \
             patch("app.main._save_comparison_result"), \
             patch("app.main._generate_result_id", return_value="res123"):
            mock_reg.return_value = MagicMock()
            resp = client.post(f"/api/facecompare/select?upload_id={test_id}&face_idx=0")
            assert resp.status_code == 200
            assert "fc-results" in resp.text

        # Cleanup
        for f in upload_dir.glob(f"{test_id}*"):
            f.unlink()


# ============================================================================
# Cross-cutting
# ============================================================================

class TestFaceCompareNoLoginRequired:
    """Verify the entire facecompare flow works without authentication."""

    def test_landing_no_auth(self, client):
        """Landing page works with auth enabled but no user."""
        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user", return_value=None):
            resp = client.get("/facecompare")
            assert resp.status_code == 200

    def test_upload_no_auth(self, client):
        """Upload endpoint works without auth."""
        with patch("app.main.is_auth_enabled", return_value=True):
            resp = client.post("/api/facecompare/upload")
            assert resp.status_code == 200  # Returns error message, not 401

    def test_shareable_no_auth(self, client):
        """Shareable URLs work without auth."""
        with patch("app.main.is_auth_enabled", return_value=True):
            resp = client.get("/facecompare/result/nonexistent")
            assert resp.status_code == 200  # Returns "not found", not 401
