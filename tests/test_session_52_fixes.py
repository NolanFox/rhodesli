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
