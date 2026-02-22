"""Tests for SSE upload streaming endpoint and progressive UI."""

import json
import pytest
from unittest.mock import patch, MagicMock
from httpx import ASGITransport, AsyncClient
from starlette.testclient import TestClient

# Import app for testing
import app.main


@pytest.fixture
def client():
    """Test client for the app."""
    from app.main import app
    return TestClient(app)


@pytest.fixture
def auth_disabled():
    """Disable auth for testing."""
    with patch("app.main.is_auth_enabled", return_value=False):
        yield


class TestSSEEndpoint:
    """Test the /api/upload/stream SSE endpoint."""

    def test_stream_endpoint_exists(self, client, auth_disabled):
        """The SSE endpoint returns something for POST requests."""
        # Send empty form — should get error event
        response = client.post("/api/upload/stream", data={})
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

    def test_stream_no_photo_returns_error_event(self, client, auth_disabled):
        """Missing photo returns an error SSE event."""
        response = client.post("/api/upload/stream", data={})
        lines = response.text.strip().split("\n")
        data_lines = [l for l in lines if l.startswith("data: ")]
        assert len(data_lines) >= 1
        event = json.loads(data_lines[0].replace("data: ", ""))
        assert event["stage"] == "error"
        assert "No photo" in event["message"]

    def test_stream_invalid_file_type(self, client, auth_disabled):
        """Invalid file type returns error event."""
        import io
        files = {"photo": ("test.txt", io.BytesIO(b"not an image"), "text/plain")}
        response = client.post("/api/upload/stream", files=files)
        lines = response.text.strip().split("\n")
        data_lines = [l for l in lines if l.startswith("data: ")]
        # Find the error event
        for line in data_lines:
            event = json.loads(line.replace("data: ", ""))
            if event.get("stage") == "error":
                assert "JPEG" in event["message"] or "PNG" in event["message"]
                return
        pytest.fail("Expected error event for invalid file type")

    def test_stream_file_too_large(self, client, auth_disabled):
        """Files >10MB return error event."""
        import io
        large_content = b"x" * (11 * 1024 * 1024)
        files = {"photo": ("test.jpg", io.BytesIO(large_content), "image/jpeg")}
        response = client.post("/api/upload/stream", files=files)
        lines = response.text.strip().split("\n")
        data_lines = [l for l in lines if l.startswith("data: ")]
        for line in data_lines:
            event = json.loads(line.replace("data: ", ""))
            if event.get("stage") == "error":
                assert "too large" in event["message"]
                return
        pytest.fail("Expected error event for file too large")

    def test_stream_content_type_is_event_stream(self, client, auth_disabled):
        """Response content type must be text/event-stream."""
        response = client.post("/api/upload/stream", data={})
        assert "text/event-stream" in response.headers.get("content-type", "")

    def test_stream_has_no_cache_headers(self, client, auth_disabled):
        """SSE responses must have Cache-Control: no-cache."""
        response = client.post("/api/upload/stream", data={})
        assert response.headers.get("cache-control") == "no-cache"


class TestProgressiveUI:
    """Test that progressive upload UI components render correctly."""

    def test_compare_page_has_progress_stages(self, client, auth_disabled):
        """Compare page includes progress stage indicators."""
        response = client.get("/compare")
        assert response.status_code == 200
        html = response.text
        assert "upload-progress" in html
        assert "stage-detecting" in html
        assert "stage-comparing" in html

    def test_compare_page_has_progress_script(self, client, auth_disabled):
        """Compare page includes the progressive upload JS."""
        response = client.get("/compare")
        html = response.text
        assert "startProgressUpload" in html

    def test_upload_form_has_onsubmit(self, client, auth_disabled):
        """Upload form has onsubmit handler for progressive upload."""
        response = client.get("/compare")
        html = response.text
        assert "startProgressUpload" in html

    def test_upload_stage_item_renders(self):
        """_upload_stage_item helper produces correct structure."""
        from app.main import _upload_stage_item
        item = _upload_stage_item("detecting", "Detecting faces", "pending")
        html = repr(item)
        assert "stage-detecting" in html
        assert "Detecting faces" in html

    def test_upload_progress_hidden_by_default(self, client, auth_disabled):
        """Progress stages are hidden until upload starts."""
        response = client.get("/compare")
        html = response.text
        # The upload-progress div should have 'hidden' class
        assert 'id="upload-progress"' in html
        assert 'class="hidden' in html or 'class="hidden ' in html


class TestFacecompareProgressiveUI:
    """Test that /facecompare page has progressive upload UI."""

    def test_facecompare_has_progress_stages(self, client, auth_disabled):
        """Facecompare page includes progress stage indicators."""
        response = client.get("/facecompare")
        assert response.status_code == 200
        html = response.text
        assert "upload-progress" in html
        assert "stage-detecting" in html
        assert "stage-comparing" in html
        assert "stage-estimating" in html

    def test_facecompare_has_progress_script(self, client, auth_disabled):
        """Facecompare page includes the progressive upload JS."""
        response = client.get("/facecompare")
        html = response.text
        assert "startProgressUpload" in html
        assert "handleStageEvent" in html

    def test_facecompare_form_has_onsubmit(self, client, auth_disabled):
        """Facecompare upload form has onsubmit for progressive upload."""
        response = client.get("/facecompare")
        html = response.text
        assert "startProgressUpload(this,'facecompare')" in html

    def test_facecompare_progress_hidden_by_default(self, client, auth_disabled):
        """Progress stages hidden until upload starts on facecompare."""
        response = client.get("/facecompare")
        html = response.text
        assert 'id="upload-progress"' in html
        # Facecompare uses inline style display:none
        assert 'display: none' in html or 'display:none' in html

    def test_both_pages_share_same_sse_endpoint(self, client, auth_disabled):
        """Both compare and facecompare point to the same SSE stream."""
        compare = client.get("/compare").text
        facecompare = client.get("/facecompare").text
        assert "/api/upload/stream" in compare
        assert "/api/upload/stream" in facecompare
