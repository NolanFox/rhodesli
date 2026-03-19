"""Tests for ML service detection wrapper in core/ingest_inbox.py (Session 117).

Verifies that detect_faces() correctly:
1. Uses ML service when configured
2. Falls back to local when not configured
3. Falls back to local on ML service errors
4. Transforms ML service response to correct PFE format
"""

import os
import numpy as np
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path


class TestDetectFacesFeatureFlag:
    """Test that detect_faces() respects the ML_SERVICE_URL feature flag."""

    def test_uses_local_when_not_configured(self):
        """When ML_SERVICE_URL is empty, detect_faces delegates to extract_faces."""
        from core.ingest_inbox import detect_faces

        mock_client = MagicMock()
        mock_client.is_configured = False

        with patch("core.ml_client.get_ml_client", return_value=mock_client):
            with patch("core.ingest_inbox.extract_faces") as mock_extract:
                mock_extract.return_value = ([], 640, 480)
                result = detect_faces(Path("/fake/image.jpg"))

                mock_extract.assert_called_once()
                assert result == ([], 640, 480)

    def test_falls_back_on_ml_service_error(self):
        """When ML service fails, detect_faces falls back to extract_faces."""
        from core.ingest_inbox import detect_faces

        mock_client = MagicMock()
        mock_client.is_configured = True
        mock_client.detect_and_embed = AsyncMock(side_effect=ConnectionError("timeout"))

        with patch("core.ml_client.get_ml_client", return_value=mock_client):
            with patch("core.ingest_inbox.extract_faces") as mock_extract:
                mock_extract.return_value = ([], 640, 480)
                result = detect_faces(Path("/fake/image.jpg"))

                mock_extract.assert_called_once()


class TestTransformMLResponse:
    """Test that ML service response is correctly transformed to PFE format."""

    def _make_ml_response(self, num_faces=1):
        """Create a mock ML service response."""
        faces = []
        for i in range(num_faces):
            embedding = np.random.randn(512).astype(np.float32)
            faces.append(
                {
                    "bbox": [10 + i * 50, 20, 60 + i * 50, 80],
                    "det_score": 0.95 - i * 0.1,
                    "quality": float(np.linalg.norm(embedding)),
                    "embedding": embedding.tolist(),
                }
            )
        return {
            "faces": faces,
            "image_size": {"width": 640, "height": 480},
            "processing_time_ms": 150,
        }

    def test_transformed_face_has_required_keys(self):
        """Transformed face must have all PFE keys."""
        from core.ingest_inbox import detect_faces

        ml_response = self._make_ml_response(1)

        mock_client = MagicMock()
        mock_client.is_configured = True
        mock_client.detect_and_embed = AsyncMock(return_value=ml_response)

        with patch("core.ml_client.get_ml_client", return_value=mock_client):
            faces, w, h = detect_faces(Path("/fake/image.jpg"))

        assert len(faces) == 1
        face = faces[0]
        # Required PFE keys
        assert "mu" in face
        assert "sigma_sq" in face
        assert "det_score" in face
        assert "bbox" in face
        assert "filename" in face
        assert "filepath" in face
        assert "quality" in face

    def test_embedding_is_normalized(self):
        """mu should be L2-normalized."""
        from core.ingest_inbox import detect_faces

        ml_response = self._make_ml_response(1)

        mock_client = MagicMock()
        mock_client.is_configured = True
        mock_client.detect_and_embed = AsyncMock(return_value=ml_response)

        with patch("core.ml_client.get_ml_client", return_value=mock_client):
            faces, _, _ = detect_faces(Path("/fake/image.jpg"))

        mu = faces[0]["mu"]
        norm = float(np.linalg.norm(mu))
        assert abs(norm - 1.0) < 0.01, f"mu should be unit-normalized, got norm={norm}"

    def test_embedding_is_512_dim(self):
        """mu should be 512-dimensional."""
        from core.ingest_inbox import detect_faces

        ml_response = self._make_ml_response(1)

        mock_client = MagicMock()
        mock_client.is_configured = True
        mock_client.detect_and_embed = AsyncMock(return_value=ml_response)

        with patch("core.ml_client.get_ml_client", return_value=mock_client):
            faces, _, _ = detect_faces(Path("/fake/image.jpg"))

        assert faces[0]["mu"].shape == (512,)
        assert faces[0]["mu"].dtype == np.float32

    def test_image_dimensions_returned(self):
        """detect_faces should return image dimensions from ML service."""
        from core.ingest_inbox import detect_faces

        ml_response = self._make_ml_response(1)

        mock_client = MagicMock()
        mock_client.is_configured = True
        mock_client.detect_and_embed = AsyncMock(return_value=ml_response)

        with patch("core.ml_client.get_ml_client", return_value=mock_client):
            _, w, h = detect_faces(Path("/fake/image.jpg"))

        assert w == 640
        assert h == 480

    def test_multiple_faces(self):
        """Should handle multiple faces in response."""
        from core.ingest_inbox import detect_faces

        ml_response = self._make_ml_response(3)

        mock_client = MagicMock()
        mock_client.is_configured = True
        mock_client.detect_and_embed = AsyncMock(return_value=ml_response)

        with patch("core.ml_client.get_ml_client", return_value=mock_client):
            faces, _, _ = detect_faces(Path("/fake/image.jpg"))

        assert len(faces) == 3

    def test_zero_faces(self):
        """Should handle empty faces list."""
        from core.ingest_inbox import detect_faces

        ml_response = {"faces": [], "image_size": {"width": 640, "height": 480}, "processing_time_ms": 50}

        mock_client = MagicMock()
        mock_client.is_configured = True
        mock_client.detect_and_embed = AsyncMock(return_value=ml_response)

        with patch("core.ml_client.get_ml_client", return_value=mock_client):
            faces, w, h = detect_faces(Path("/fake/image.jpg"))

        assert len(faces) == 0
        assert w == 640
        assert h == 480

    def test_det_score_preserved(self):
        """det_score from ML service should be preserved."""
        from core.ingest_inbox import detect_faces

        ml_response = self._make_ml_response(1)
        ml_response["faces"][0]["det_score"] = 0.87

        mock_client = MagicMock()
        mock_client.is_configured = True
        mock_client.detect_and_embed = AsyncMock(return_value=ml_response)

        with patch("core.ml_client.get_ml_client", return_value=mock_client):
            faces, _, _ = detect_faces(Path("/fake/image.jpg"))

        assert faces[0]["det_score"] == 0.87

    def test_bbox_preserved(self):
        """bbox from ML service should be preserved."""
        from core.ingest_inbox import detect_faces

        ml_response = self._make_ml_response(1)
        ml_response["faces"][0]["bbox"] = [10, 20, 100, 150]

        mock_client = MagicMock()
        mock_client.is_configured = True
        mock_client.detect_and_embed = AsyncMock(return_value=ml_response)

        with patch("core.ml_client.get_ml_client", return_value=mock_client):
            faces, _, _ = detect_faces(Path("/fake/image.jpg"))

        assert faces[0]["bbox"] == [10, 20, 100, 150]
