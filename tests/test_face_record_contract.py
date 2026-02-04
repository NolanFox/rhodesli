"""
Tests that Face ID format is correctly preserved from embeddings.

This test demonstrates the bug where inbox face_ids are ignored
and regenerated as legacy-format IDs.
"""

import numpy as np
import pytest
from unittest.mock import patch


class TestFaceIdPreservation:
    """Test that stored face_id values are used when present."""

    def test_inbox_face_id_is_preserved(self):
        """
        Bug: load_face_embeddings() ignores the face_id field and
        regenerates a wrong legacy-format ID.

        Expected: face_data["inbox_test_123"] exists
        Bug behavior: face_data["photo:face0"] exists instead
        """
        # Sample embedding entry with inbox-style face_id
        mock_embedding = {
            "face_id": "inbox_test_123",
            "filename": "photo.jpg",
            "filepath": "/path/to/photo.jpg",
            "mu": np.zeros(512, dtype=np.float32),
            "sigma_sq": np.full(512, 0.1, dtype=np.float32),
            "det_score": 0.95,
            "bbox": [100, 100, 200, 200],
            "quality": 25.0,
        }

        # Mock embeddings.npy to return our test entry
        mock_embeddings = np.array([mock_embedding], dtype=object)

        with patch("numpy.load", return_value=mock_embeddings):
            with patch("pathlib.Path.exists", return_value=True):
                from app.main import load_face_embeddings

                # Clear cache to force reload
                import app.main
                app.main._face_data_cache = None

                face_data = load_face_embeddings()

        # The key SHOULD be the stored face_id
        assert "inbox_test_123" in face_data, (
            f"Expected 'inbox_test_123' in face_data keys. "
            f"Got keys: {list(face_data.keys())}"
        )

        # The key should NOT be the regenerated legacy format
        assert "photo:face0" not in face_data, (
            "Bug confirmed: face_id was regenerated as legacy format 'photo:face0' "
            "instead of using stored 'inbox_test_123'"
        )

    def test_legacy_face_id_is_generated_when_not_present(self):
        """
        Legacy entries (no face_id field) should still generate IDs.
        """
        # Sample embedding entry WITHOUT face_id (legacy format)
        mock_embedding = {
            "filename": "Image_001.jpg",
            "filepath": "/path/to/Image_001.jpg",
            "mu": np.zeros(512, dtype=np.float32),
            "sigma_sq": np.full(512, 0.1, dtype=np.float32),
            "det_score": 0.95,
            "bbox": [100, 100, 200, 200],
            "quality": 25.0,
        }

        mock_embeddings = np.array([mock_embedding], dtype=object)

        with patch("numpy.load", return_value=mock_embeddings):
            with patch("pathlib.Path.exists", return_value=True):
                from app.main import load_face_embeddings

                import app.main
                app.main._face_data_cache = None

                face_data = load_face_embeddings()

        # Legacy format should be generated
        assert "Image_001:face0" in face_data, (
            f"Expected 'Image_001:face0' for legacy entry. "
            f"Got keys: {list(face_data.keys())}"
        )
