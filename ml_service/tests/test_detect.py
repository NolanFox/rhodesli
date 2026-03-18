"""Tests for the detect-and-embed endpoint.

InsightFace is mocked to avoid needing the actual model during tests.
"""

import io
from unittest.mock import MagicMock, patch

import numpy as np
from PIL import Image


def _create_test_image(width=100, height=100, fmt="JPEG"):
    """Create a minimal test image as bytes."""
    img = Image.new("RGB", (width, height), color=(128, 128, 128))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    buf.seek(0)
    return buf


def _make_mock_face(bbox=None, det_score=0.95, embedding_dim=512):
    """Create a mock InsightFace face object."""
    face = MagicMock()
    face.bbox = np.array(bbox or [10.0, 20.0, 50.0, 80.0])
    face.det_score = det_score
    face.normed_embedding = np.random.randn(embedding_dim).astype(np.float32)
    face.embedding = np.random.randn(embedding_dim).astype(np.float32) * 20.0
    face.kps = np.array([[30.0, 40.0], [40.0, 40.0], [35.0, 50.0]])
    face.landmark_2d_106 = None
    return face


def test_detect_returns_401_without_auth(client):
    """Endpoint requires bearer token authentication."""
    img_buf = _create_test_image()
    resp = client.post(
        "/api/v1/detect-and-embed",
        files={"file": ("test.jpg", img_buf, "image/jpeg")},
    )
    assert resp.status_code in (401, 403)


def test_detect_returns_400_for_non_image(client, auth_headers):
    """Non-image files should be rejected with 400."""
    buf = io.BytesIO(b"not an image at all")
    resp = client.post(
        "/api/v1/detect-and-embed",
        files={"file": ("test.txt", buf, "text/plain")},
        headers=auth_headers,
    )
    assert resp.status_code == 400


@patch("ml_service.detect.get_face_analyzer")
def test_detect_returns_correct_response_shape(mock_analyzer, client, auth_headers):
    """Response should have faces, image_size, processing_time_ms, model_info."""
    mock_face = _make_mock_face()
    mock_fa = MagicMock()
    mock_fa.get.return_value = [mock_face]
    mock_analyzer.return_value = mock_fa

    img_buf = _create_test_image(width=200, height=150)
    resp = client.post(
        "/api/v1/detect-and-embed",
        files={"file": ("test.jpg", img_buf, "image/jpeg")},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()

    # Top-level keys
    assert "faces" in data
    assert "image_size" in data
    assert "processing_time_ms" in data
    assert "model_info" in data

    # Image size
    assert data["image_size"]["width"] == 200
    assert data["image_size"]["height"] == 150

    # Face data
    assert len(data["faces"]) == 1
    face = data["faces"][0]
    assert "bbox" in face
    assert "det_score" in face
    assert "quality" in face
    assert "embedding" in face
    assert len(face["bbox"]) == 4
    assert len(face["embedding"]) == 512


@patch("ml_service.detect.get_face_analyzer")
def test_detect_response_includes_model_info(mock_analyzer, client, auth_headers):
    """model_info should include insightface version and model name."""
    mock_fa = MagicMock()
    mock_fa.get.return_value = []
    mock_analyzer.return_value = mock_fa

    img_buf = _create_test_image()
    resp = client.post(
        "/api/v1/detect-and-embed",
        files={"file": ("test.jpg", img_buf, "image/jpeg")},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()

    model_info = data["model_info"]
    assert model_info["name"] == "buffalo_l"
    assert model_info["embedding_dim"] == 512
    assert "insightface_version" in model_info


@patch("ml_service.detect.get_face_analyzer")
def test_detect_response_includes_processing_time(mock_analyzer, client, auth_headers):
    """processing_time_ms should be a positive number."""
    mock_fa = MagicMock()
    mock_fa.get.return_value = []
    mock_analyzer.return_value = mock_fa

    img_buf = _create_test_image()
    resp = client.post(
        "/api/v1/detect-and-embed",
        files={"file": ("test.jpg", img_buf, "image/jpeg")},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["processing_time_ms"] >= 0


@patch("ml_service.detect.get_face_analyzer")
def test_detect_no_faces_returns_empty_list(mock_analyzer, client, auth_headers):
    """When no faces are detected, return empty faces list (not an error)."""
    mock_fa = MagicMock()
    mock_fa.get.return_value = []
    mock_analyzer.return_value = mock_fa

    img_buf = _create_test_image()
    resp = client.post(
        "/api/v1/detect-and-embed",
        files={"file": ("test.jpg", img_buf, "image/jpeg")},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["faces"] == []
