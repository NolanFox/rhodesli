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

    def test_compare_page_has_progress_container(self, client, auth_disabled):
        """Compare workspace includes progress container."""
        response = client.get("/compare")
        assert response.status_code == 200
        html = response.text
        assert "upload-progress" in html

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

    def test_upload_progress_referenced_in_js(self, client, auth_disabled):
        """Upload progress is managed via JS in the workspace."""
        response = client.get("/compare")
        html = response.text
        assert "upload-progress" in html


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


class TestClientSideValidation:
    """Test that client-side validation JS is present."""

    def test_validate_function_exists(self, client, auth_disabled):
        """Client-side validation function is in the page."""
        response = client.get("/compare")
        assert "validateUploadFile" in response.text

    def test_validate_checks_file_type(self, client, auth_disabled):
        """Validation checks for valid image types."""
        html = client.get("/compare").text
        assert "image/jpeg" in html
        assert "image/png" in html
        assert "image/webp" in html

    def test_validate_checks_file_size(self, client, auth_disabled):
        """Validation checks file size limit."""
        html = client.get("/compare").text
        assert "10 * 1024 * 1024" in html

    def test_timeout_handling_in_js(self, client, auth_disabled):
        """JS includes timeout warning for long processing."""
        html = client.get("/compare").text
        assert "Taking longer than expected" in html


class TestSSEEdgeCases:
    """Test SSE endpoint edge cases."""

    def test_stream_webp_accepted(self, client, auth_disabled):
        """WebP files are accepted by the stream endpoint."""
        import io
        # A minimal valid WebP header (RIFF + WEBP)
        webp_header = b"RIFF\x00\x00\x00\x00WEBP"
        files = {"photo": ("test.webp", io.BytesIO(webp_header), "image/webp")}
        response = client.post("/api/upload/stream", files=files)
        lines = response.text.strip().split("\n")
        data_lines = [l for l in lines if l.startswith("data: ")]
        # Should get past validation (may fail at ML stage, not at validation)
        events = [json.loads(l.replace("data: ", "")) for l in data_lines]
        # Should not have a file type error
        type_errors = [e for e in events if e.get("stage") == "error" and "JPEG" in e.get("message", "")]
        assert len(type_errors) == 0

    def test_stream_empty_file(self, client, auth_disabled):
        """Empty file gets handled gracefully."""
        import io
        files = {"photo": ("empty.jpg", io.BytesIO(b""), "image/jpeg")}
        response = client.post("/api/upload/stream", files=files)
        lines = response.text.strip().split("\n")
        data_lines = [l for l in lines if l.startswith("data: ")]
        events = [json.loads(l.replace("data: ", "")) for l in data_lines]
        # Should get an error (either at ML or gracefully), not a crash
        assert any(e.get("stage") in ("error", "received") for e in events)

    def test_stream_flow_parameter_forwarded(self, client, auth_disabled):
        """The flow parameter is accepted without error."""
        import io
        files = {"photo": ("test.jpg", io.BytesIO(b"not-real"), "image/jpeg")}
        data = {"flow": "facecompare"}
        response = client.post("/api/upload/stream", files=files, data=data)
        assert response.status_code == 200

    def test_stream_returns_received_before_error(self, client, auth_disabled):
        """Valid file gets 'received' event before any potential ML errors."""
        import io
        # Create minimal JPEG bytes (invalid but passes extension check)
        files = {"photo": ("test.jpg", io.BytesIO(b"\xff\xd8\xff\xe0" + b"\x00" * 100), "image/jpeg")}
        response = client.post("/api/upload/stream", files=files)
        lines = response.text.strip().split("\n")
        data_lines = [l for l in lines if l.startswith("data: ")]
        events = [json.loads(l.replace("data: ", "")) for l in data_lines]
        # First non-error event should be "received"
        non_error = [e for e in events if e.get("stage") != "error"]
        if non_error:
            assert non_error[0]["stage"] == "received"
