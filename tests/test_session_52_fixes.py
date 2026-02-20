"""Tests for Session 52 — Face overlay clicks + Name These Faces on public page + ML pipeline.

Covers:
- Face overlay clicks work on public /photo/{id} page (regression check)
- "Name These Faces" button on public photo page for admin
- "Name These Faces" hidden for non-admin on public page
- HTMX container for inline sequential identifier on public page
- Compare upload processing (InsightFace-aware)
- Estimate upload processing (Gemini-aware)
- Health check ML status reporting
"""

import pytest
from unittest.mock import patch, MagicMock


def _make_photo(face_count=4, identified_ids=None):
    """Build mock photo with faces and identity data."""
    identified_ids = identified_ids or set()
    faces = []
    for i in range(face_count):
        faces.append({
            "face_id": f"face-{i}",
            "bbox": [10 + i * 100, 10, 90 + i * 100, 90],
        })
    return {
        "filename": "test_thanksgiving.jpg",
        "faces": faces,
        "source": "Test Collection",
        "collection": "Test Album",
    }


def _mock_identity(identified_ids):
    """Return mock get_identity_for_face that identifies faces in identified_ids."""
    def _get(registry, face_id):
        idx = int(face_id.split("-")[1])
        if idx in identified_ids:
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


# ---------------------------------------------------------------------------
# Face overlay clicks on public /photo/{id} page
# ---------------------------------------------------------------------------


class TestPublicPageFaceOverlayClicks:
    """Face overlays on /photo/{id} use <a> tags with href for navigation."""

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    @patch("app.main.get_identity_for_face")
    @patch("app.main.get_crop_files", return_value={})
    def test_identified_face_links_to_person_page(self, mock_crops, mock_get_id,
                                                   mock_reg, mock_dim, mock_meta):
        """Identified face overlays link to /person/{identity_id}."""
        from app.main import public_photo_page, to_xml

        mock_meta.return_value = _make_photo(face_count=2, identified_ids={0})
        mock_get_id.side_effect = _mock_identity({0})
        mock_reg.return_value = MagicMock()

        result = public_photo_page("p1", is_admin=False)
        html = to_xml(result)

        assert 'href="/person/id-0"' in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    @patch("app.main.get_identity_for_face")
    @patch("app.main.get_crop_files", return_value={})
    def test_unidentified_face_links_to_identify_page(self, mock_crops, mock_get_id,
                                                       mock_reg, mock_dim, mock_meta):
        """Unidentified face overlays link to /identify/{identity_id}."""
        from app.main import public_photo_page, to_xml

        mock_meta.return_value = _make_photo(face_count=2, identified_ids=set())
        mock_get_id.side_effect = _mock_identity(set())
        mock_reg.return_value = MagicMock()

        result = public_photo_page("p1", is_admin=False)
        html = to_xml(result)

        assert 'href="/identify/id-0"' in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    @patch("app.main.get_identity_for_face")
    @patch("app.main.get_crop_files", return_value={})
    def test_overlays_are_anchor_tags(self, mock_crops, mock_get_id,
                                      mock_reg, mock_dim, mock_meta):
        """Face overlays are <a> tags (standard links), not JS-only handlers."""
        from app.main import public_photo_page, to_xml

        mock_meta.return_value = _make_photo(face_count=2)
        mock_get_id.side_effect = _mock_identity({0})
        mock_reg.return_value = MagicMock()

        result = public_photo_page("p1", is_admin=False)
        html = to_xml(result)

        # Overlays should be <a> tags with face-overlay-box class
        import re
        # Match <a> tags that have both face-overlay-box class and href (in any order)
        overlay_links = re.findall(r'<a\s[^>]*?(?:class="[^"]*face-overlay-box[^"]*"[^>]*href=|href="[^"]*"[^>]*class="[^"]*face-overlay-box)', html)
        assert len(overlay_links) >= 1, "Face overlays must be <a> tags with href"


# ---------------------------------------------------------------------------
# "Name These Faces" on public /photo/{id} page
# ---------------------------------------------------------------------------


class TestPublicPageNameTheseFaces:
    """Admin sees 'Name These Faces' button on public photo page."""

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    @patch("app.main.get_identity_for_face")
    @patch("app.main.get_crop_files", return_value={})
    def test_admin_sees_name_these_faces_button(self, mock_crops, mock_get_id,
                                                 mock_reg, mock_dim, mock_meta):
        """Admin sees 'Name These Faces' on public page with 2+ unidentified."""
        from app.main import public_photo_page, to_xml

        mock_meta.return_value = _make_photo(face_count=4, identified_ids=set())
        mock_get_id.side_effect = _mock_identity(set())
        mock_reg.return_value = MagicMock()

        result = public_photo_page("p1", is_admin=True)
        html = to_xml(result)

        assert "Name These Faces" in html
        assert "4 unidentified" in html
        assert 'data-testid="name-these-faces-public"' in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    @patch("app.main.get_identity_for_face")
    @patch("app.main.get_crop_files", return_value={})
    def test_non_admin_no_name_these_faces(self, mock_crops, mock_get_id,
                                            mock_reg, mock_dim, mock_meta):
        """Non-admin does NOT see 'Name These Faces' on public page."""
        from app.main import public_photo_page, to_xml

        mock_meta.return_value = _make_photo(face_count=4, identified_ids=set())
        mock_get_id.side_effect = _mock_identity(set())
        mock_reg.return_value = MagicMock()

        result = public_photo_page("p1", is_admin=False)
        html = to_xml(result)

        assert "Name These Faces" not in html
        assert 'data-testid="name-these-faces-public"' not in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    @patch("app.main.get_identity_for_face")
    @patch("app.main.get_crop_files", return_value={})
    def test_button_hidden_few_unidentified(self, mock_crops, mock_get_id,
                                             mock_reg, mock_dim, mock_meta):
        """Button hidden when fewer than 2 faces are unidentified."""
        from app.main import public_photo_page, to_xml

        # 3 faces, 2 identified → only 1 unidentified
        mock_meta.return_value = _make_photo(face_count=3, identified_ids={0, 1})
        mock_get_id.side_effect = _mock_identity({0, 1})
        mock_reg.return_value = MagicMock()

        result = public_photo_page("p1", is_admin=True)
        html = to_xml(result)

        assert "Name These Faces" not in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    @patch("app.main.get_identity_for_face")
    @patch("app.main.get_crop_files", return_value={})
    def test_button_loads_sequential_mode(self, mock_crops, mock_get_id,
                                           mock_reg, mock_dim, mock_meta):
        """Button triggers HTMX load of sequential identifier."""
        from app.main import public_photo_page, to_xml

        mock_meta.return_value = _make_photo(face_count=4, identified_ids=set())
        mock_get_id.side_effect = _mock_identity(set())
        mock_reg.return_value = MagicMock()

        result = public_photo_page("p1", is_admin=True)
        html = to_xml(result)

        # Button should target the inline container with seq=1
        assert "seq=1" in html
        assert "admin-name-faces-container" in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    @patch("app.main.get_identity_for_face")
    @patch("app.main.get_crop_files", return_value={})
    def test_htmx_container_present_for_admin(self, mock_crops, mock_get_id,
                                               mock_reg, mock_dim, mock_meta):
        """HTMX target container exists on page for admin."""
        from app.main import public_photo_page, to_xml

        mock_meta.return_value = _make_photo(face_count=4, identified_ids=set())
        mock_get_id.side_effect = _mock_identity(set())
        mock_reg.return_value = MagicMock()

        result = public_photo_page("p1", is_admin=True)
        html = to_xml(result)

        assert 'id="admin-name-faces-container"' in html


# ---------------------------------------------------------------------------
# Compare upload — ML-aware processing
# ---------------------------------------------------------------------------


class TestCompareUploadProcessing:
    """Compare upload handles both ML-available and ML-unavailable cases."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from app.main import app
        from starlette.testclient import TestClient
        self.client = TestClient(app)

    def test_compare_no_insightface_saves_upload(self):
        """Without InsightFace, upload is saved and shows honest message."""
        import io
        img = io.BytesIO(b'\xff\xd8\xff\xe0' + b'\x00' * 100)  # minimal JPEG header
        with patch("app.main.is_auth_enabled", return_value=False), \
             patch.dict("sys.modules", {"cv2": None, "insightface": None, "insightface.app": None}):
            # Force ImportError for InsightFace detection check
            response = self.client.post(
                "/api/compare/upload",
                files={"photo": ("test.jpg", img, "image/jpeg")},
            )
        assert response.status_code == 200
        html = response.text
        # Should show honest messaging about offline processing
        assert "Photo received" in html or "not yet available" in html
        # Should NOT say "check back soon" with no mechanism
        assert "check back soon" not in html.lower()

    def test_compare_rejects_non_image(self):
        """Non-image files are rejected."""
        import io
        txt = io.BytesIO(b"not an image")
        with patch("app.main.is_auth_enabled", return_value=False):
            response = self.client.post(
                "/api/compare/upload",
                files={"photo": ("test.txt", txt, "text/plain")},
            )
        assert response.status_code == 200
        assert "JPG or PNG" in response.text


# ---------------------------------------------------------------------------
# Health check — ML status
# ---------------------------------------------------------------------------


class TestHealthCheckMLStatus:
    """Health check reports ML pipeline availability."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from app.main import app
        from starlette.testclient import TestClient
        self.client = TestClient(app)

    def test_health_check_returns_processing_enabled(self):
        """Health check includes processing_enabled field."""
        response = self.client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "processing_enabled" in data

    def test_health_check_returns_ml_pipeline_status(self):
        """Health check includes ml_pipeline field."""
        response = self.client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "ml_pipeline" in data
        assert data["ml_pipeline"] in ("ready", "unavailable")


# ---------------------------------------------------------------------------
# Deploy Safety — InsightFace in requirements and Dockerfile
# ---------------------------------------------------------------------------


class TestDeploySafetyML:
    """Verify InsightFace is properly configured for Railway deployment."""

    def test_insightface_in_requirements(self):
        """requirements.txt must include insightface for Railway face detection."""
        from pathlib import Path
        reqs = (Path(__file__).parent.parent / "requirements.txt").read_text()
        assert "insightface" in reqs, \
            "requirements.txt must include insightface for Railway ML processing"

    def test_onnxruntime_in_requirements(self):
        """requirements.txt must include onnxruntime for InsightFace inference."""
        from pathlib import Path
        reqs = (Path(__file__).parent.parent / "requirements.txt").read_text()
        assert "onnxruntime" in reqs, \
            "requirements.txt must include onnxruntime for InsightFace inference"

    def test_dockerfile_downloads_model(self):
        """Dockerfile must pre-download buffalo_l model at build time."""
        from pathlib import Path
        dockerfile = (Path(__file__).parent.parent / "Dockerfile").read_text()
        assert "buffalo_l" in dockerfile, \
            "Dockerfile must download buffalo_l model for face detection"

    def test_dockerfile_has_libgomp(self):
        """Dockerfile must install libgomp1 for ONNX Runtime threading."""
        from pathlib import Path
        dockerfile = (Path(__file__).parent.parent / "Dockerfile").read_text()
        assert "libgomp" in dockerfile, \
            "Dockerfile must install libgomp1 for ONNX Runtime"

    def test_processing_enabled_true_in_dockerfile(self):
        """Dockerfile should set PROCESSING_ENABLED=true for Railway."""
        from pathlib import Path
        dockerfile = (Path(__file__).parent.parent / "Dockerfile").read_text()
        assert "PROCESSING_ENABLED=true" in dockerfile, \
            "Dockerfile must set PROCESSING_ENABLED=true for Railway ML processing"

    def test_google_genai_in_requirements(self):
        """requirements.txt must include google-genai for Gemini date estimation."""
        from pathlib import Path
        reqs = (Path(__file__).parent.parent / "requirements.txt").read_text()
        assert "google-genai" in reqs, \
            "requirements.txt must include google-genai for Gemini date estimation"


# ---------------------------------------------------------------------------
# Estimate upload — graceful degradation
# ---------------------------------------------------------------------------


class TestEstimateUploadProcessing:
    """Estimate upload handles ML + Gemini availability combinations."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from app.main import app
        from starlette.testclient import TestClient
        self.client = TestClient(app)

    def test_estimate_rejects_non_image(self):
        """Non-image files are rejected."""
        import io
        txt = io.BytesIO(b"not an image")
        with patch("app.main.is_auth_enabled", return_value=False):
            response = self.client.post(
                "/api/estimate/upload",
                files={"photo": ("test.txt", txt, "text/plain")},
            )
        assert response.status_code == 200
        assert "JPG or PNG" in response.text

    def test_estimate_rejects_oversized(self):
        """Files over 10MB are rejected."""
        import io
        big = io.BytesIO(b'\xff\xd8\xff\xe0' + b'\x00' * (11 * 1024 * 1024))
        with patch("app.main.is_auth_enabled", return_value=False):
            response = self.client.post(
                "/api/estimate/upload",
                files={"photo": ("big.jpg", big, "image/jpeg")},
            )
        assert response.status_code == 200
        assert "too large" in response.text

    def test_estimate_no_photo(self):
        """Missing photo returns message."""
        with patch("app.main.is_auth_enabled", return_value=False):
            response = self.client.post("/api/estimate/upload")
        assert response.status_code == 200
        assert "No photo" in response.text

    def test_estimate_no_ml_no_gemini_shows_honest_message(self):
        """Without ML or Gemini, shows honest 'photo saved' message."""
        import io
        img = io.BytesIO(b'\xff\xd8\xff\xe0' + b'\x00' * 100)
        with patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main._load_date_labels", return_value={}), \
             patch("core.storage.can_write_r2", return_value=False), \
             patch.dict("os.environ", {"GEMINI_API_KEY": ""}, clear=False), \
             patch.dict("sys.modules", {"cv2": None, "insightface": None, "insightface.app": None}):
            response = self.client.post(
                "/api/estimate/upload",
                files={"photo": ("test.jpg", img, "image/jpeg")},
            )
        assert response.status_code == 200
        html = response.text
        assert "Photo saved" in html
        assert "estimate-upload-result" in html

    def test_estimate_with_gemini_shows_date(self):
        """When Gemini is available, shows estimated date."""
        import io
        img = io.BytesIO(b'\xff\xd8\xff\xe0' + b'\x00' * 100)
        mock_gemini_result = {
            "best_year_estimate": 1938,
            "estimated_decade": 1930,
            "probable_range": [1935, 1945],
            "confidence": "medium",
            "reasoning_summary": "Fashion cues suggest late 1930s",
            "evidence": {
                "print_format": [{"cue": "white border", "strength": "moderate", "suggested_range": [1930, 1950]}],
                "fashion": [],
                "environment": [],
                "technology": [],
            },
        }
        with patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main._load_date_labels", return_value={}), \
             patch("core.storage.can_write_r2", return_value=False), \
             patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}, clear=False), \
             patch.dict("sys.modules", {"cv2": None, "insightface": None, "insightface.app": None}), \
             patch("app.main._call_gemini_date_estimate", return_value=mock_gemini_result):
            response = self.client.post(
                "/api/estimate/upload",
                files={"photo": ("test.jpg", img, "image/jpeg")},
            )
        assert response.status_code == 200
        html = response.text
        assert "1938" in html
        assert "estimate-gemini-result" in html

    def test_estimate_matches_existing_label(self):
        """When the uploaded photo matches an existing date label, show it."""
        import io
        img = io.BytesIO(b'\xff\xd8\xff\xe0' + b'\x00' * 100)
        mock_labels = {
            "testphoto": {
                "estimated_year": 1942,
                "confidence_range": [1938, 1948],
                "scene_analysis": {
                    "photography_style": ["black and white"],
                    "clothing_and_fashion": ["wide-lapel suits"],
                },
            }
        }
        with patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main._load_date_labels", return_value=mock_labels), \
             patch("core.storage.can_write_r2", return_value=False):
            response = self.client.post(
                "/api/estimate/upload",
                files={"photo": ("testphoto.jpg", img, "image/jpeg")},
            )
        assert response.status_code == 200
        html = response.text
        assert "1942" in html
        assert "1938" in html  # range start
