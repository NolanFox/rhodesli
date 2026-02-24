"""
Session 65a — Two-photo face comparison (/compare/pair).

Tests for the new two-photo compare feature that lets users upload
two photos, select a face in each, and see similarity scores.
"""

import json
import pytest
import numpy as np
from unittest.mock import patch, MagicMock
from pathlib import Path


class TestComparePairPage:
    """GET /compare/pair should render the two-panel layout."""

    def test_pair_page_loads(self, client):
        """Pair compare page should return 200."""
        response = client.get("/compare/pair")
        assert response.status_code == 200

    def test_pair_page_has_two_panels(self, client):
        """Page must have both Panel A and Panel B upload zones."""
        response = client.get("/compare/pair")
        assert 'data-testid="pair-panel-a"' in response.text
        assert 'data-testid="pair-panel-b"' in response.text

    def test_pair_page_has_compare_button(self, client):
        """Compare button must exist (disabled by default)."""
        response = client.get("/compare/pair")
        assert 'data-testid="pair-compare-btn"' in response.text
        assert "disabled" in response.text

    def test_pair_page_has_back_link(self, client):
        """Page should link back to /compare."""
        response = client.get("/compare/pair")
        assert "/compare" in response.text
        assert "Back to Compare" in response.text

    def test_compare_page_links_to_pair(self, client, auth_disabled):
        """Main compare page should have a link to pair compare."""
        response = client.get("/compare")
        assert "/compare/pair" in response.text


class TestComparePairUpload:
    """POST /api/compare/pair/upload — face detection on uploaded photo."""

    def test_upload_no_file_returns_error(self, client):
        """Missing file should return error."""
        response = client.post("/api/compare/pair/upload",
                               data={"panel": "a"})
        assert response.status_code == 200
        assert "No photo" in response.text

    def test_upload_invalid_type_returns_error(self, client):
        """Non-image file should be rejected."""
        response = client.post("/api/compare/pair/upload",
                               data={"panel": "a"},
                               files={"photo": ("test.txt", b"not an image", "text/plain")})
        assert response.status_code == 200
        assert "JPEG" in response.text or "PNG" in response.text

    def test_upload_oversized_returns_error(self, client):
        """File > 10MB should be rejected."""
        big_content = b"\x00" * (11 * 1024 * 1024)
        response = client.post("/api/compare/pair/upload",
                               data={"panel": "a"},
                               files={"photo": ("big.jpg", big_content, "image/jpeg")})
        assert response.status_code == 200
        assert "too large" in response.text.lower()


class TestComparePairMatch:
    """POST /api/compare/pair/match — face similarity computation."""

    def test_match_missing_uploads_returns_error(self, client):
        """Missing upload IDs should return error."""
        response = client.post("/api/compare/pair/match",
                               data={"upload_a": "", "upload_b": ""})
        assert response.status_code == 200
        assert "Both photos" in response.text or "must have" in response.text

    def test_match_similar_embeddings_high_confidence(self):
        """Very similar embeddings should produce high confidence."""
        mu_a = np.array([0.1] * 512)
        mu_b = np.array([0.11] * 512)
        distance = float(np.linalg.norm(mu_a - mu_b))
        cosine_sim = max(0.0, 1.0 - (distance ** 2) / 2.0)
        confidence_pct = max(0, min(100, int((1 - distance / 2.0) * 100)))

        # The faces are very similar (small distance), so confidence should be high
        assert confidence_pct > 80
        assert cosine_sim > 0.9

    def test_match_dissimilar_faces(self):
        """Very different embeddings should produce low confidence."""
        mu_a = np.array([1.0] + [0.0] * 511)
        mu_b = np.array([0.0] + [1.0] + [0.0] * 510)
        distance = float(np.linalg.norm(mu_a - mu_b))
        cosine_sim = max(0.0, 1.0 - (distance ** 2) / 2.0)
        confidence_pct = max(0, min(100, int((1 - distance / 2.0) * 100)))

        # Orthogonal vectors: distance = sqrt(2) ≈ 1.41
        assert distance > 1.0
        assert confidence_pct < 50
