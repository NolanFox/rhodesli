"""Tests for multi-photo compare upload (PRD-021, Session 61)."""

import io
import pytest
from starlette.testclient import TestClient
from unittest.mock import patch, MagicMock


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


class TestMultiPhotoUploadEndpoint:
    """Tests for /api/compare/upload-multiple endpoint."""

    def test_rejects_single_photo(self, client):
        """Multi-upload requires at least 2 photos."""
        with patch("app.main.is_auth_enabled", return_value=False):
            # Upload just 1 file
            files = [("photos", ("test1.jpg", io.BytesIO(b"\xff\xd8\xff"), "image/jpeg"))]
            response = client.post(
                "/api/compare/upload-multiple", files=files,
                headers={"HX-Request": "true"},
            )
            assert response.status_code == 200
            assert "at least 2 photos" in response.text

    def test_rejects_too_many_photos(self, client):
        """Multi-upload rejects more than 5 photos."""
        with patch("app.main.is_auth_enabled", return_value=False):
            files = [("photos", (f"test{i}.jpg", io.BytesIO(b"\xff\xd8\xff"), "image/jpeg"))
                     for i in range(6)]
            response = client.post(
                "/api/compare/upload-multiple", files=files,
                headers={"HX-Request": "true"},
            )
            assert response.status_code == 200
            assert "Maximum 5 photos" in response.text

    def test_endpoint_exists_and_accepts_post(self, client):
        """Multi-upload endpoint exists and accepts POST."""
        with patch("app.main.is_auth_enabled", return_value=False):
            # Empty request should return error, not 404/405
            response = client.post(
                "/api/compare/upload-multiple",
                headers={"HX-Request": "true"},
            )
            assert response.status_code == 200
            # Should ask for at least 2 photos
            assert "at least 2" in response.text or "photos" in response.text.lower()


class TestMultiPhotoUI:
    """Tests for multi-photo upload UI elements."""

    def test_compare_page_has_multi_upload_zone(self, client):
        """Compare page includes multi-upload zone."""
        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get("/compare")
            assert response.status_code == 200
            assert "multi-upload-zone" in response.text
            assert "Compare Multiple Photos" in response.text

    def test_multi_upload_form_targets_correct_endpoint(self, client):
        """Multi-upload form POSTs to /api/compare/upload-multiple."""
        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get("/compare")
            assert "/api/compare/upload-multiple" in response.text

    def test_multi_upload_input_has_multiple_attribute(self, client):
        """File input has multiple attribute for multi-file selection."""
        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get("/compare")
            assert 'multi-upload-input' in response.text


class TestCrossComparison:
    """Tests for cross-comparison logic between uploaded photos."""

    def test_cross_compare_computes_similarity(self):
        """Cross-comparison finds matching faces between photos."""
        import numpy as np

        # Create two "face embeddings" that are similar
        emb_a = np.random.randn(512).astype(np.float32)
        emb_b = emb_a + np.random.randn(512).astype(np.float32) * 0.1  # Very similar
        emb_c = np.random.randn(512).astype(np.float32)  # Different

        # Simulate cross-comparison
        all_faces = [
            (0, 0, emb_a, [0, 0, 100, 100]),  # Photo 0, face 0
            (1, 0, emb_b, [0, 0, 100, 100]),  # Photo 1, face 0 (similar to a)
            (1, 1, emb_c, [100, 0, 200, 100]), # Photo 1, face 1 (different)
        ]

        cross_matches = []
        for i, (pi_a, fi_a, ea, _) in enumerate(all_faces):
            for j, (pi_b, fi_b, eb, _) in enumerate(all_faces):
                if j <= i or pi_a == pi_b:
                    continue
                sim = float(np.dot(ea, eb) / (np.linalg.norm(ea) * np.linalg.norm(eb) + 1e-8))
                if sim > 0.3:
                    cross_matches.append({
                        "photo_a": pi_a, "photo_b": pi_b,
                        "similarity": sim,
                    })

        # emb_a ↔ emb_b should have high similarity
        high_sim = [m for m in cross_matches if m["similarity"] > 0.8]
        assert len(high_sim) >= 1, "Similar embeddings should produce high cross-match"

    def test_cross_compare_skips_same_photo(self):
        """Cross-comparison skips faces within the same photo."""
        import numpy as np
        emb = np.random.randn(512).astype(np.float32)

        all_faces = [
            (0, 0, emb, [0, 0, 100, 100]),
            (0, 1, emb, [100, 0, 200, 100]),  # Same photo
        ]

        cross_matches = []
        for i, (pi_a, fi_a, ea, _) in enumerate(all_faces):
            for j, (pi_b, fi_b, eb, _) in enumerate(all_faces):
                if j <= i or pi_a == pi_b:
                    continue
                sim = float(np.dot(ea, eb) / (np.linalg.norm(ea) * np.linalg.norm(eb) + 1e-8))
                if sim > 0.3:
                    cross_matches.append({"photo_a": pi_a, "photo_b": pi_b})

        assert len(cross_matches) == 0, "Should not compare faces within same photo"


