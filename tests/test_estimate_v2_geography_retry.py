"""
Tests for TOOLS-005 / PRD-055 Flow 3: geography retry in /tools/estimate.

After an initial estimate, the user can supply a different location. The system
re-runs Gemini with the user-supplied location as a constraint (reusing the
stored image, no re-upload) and shows the original + revised estimates side by
side. Retries share the upload rate-limit budget.
"""

import io
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def _fake_image_bytes():
    """Return minimal bytes that pass the upload validation."""
    return io.BytesIO(b"\xff\xd8\xff" + b"\x00" * 1024)


def _upload_patches():
    """Common patches for the initial upload endpoint."""
    return [
        patch("app.main.is_auth_enabled", return_value=False),
        patch("app.main._build_caches"),
        patch("app.main._load_date_labels", return_value={}),
        patch("core.storage.can_write_r2", return_value=False),
        patch("core.storage.get_upload_url", return_value="/uploads/test.jpg"),
        patch("app.estimate_routes.check_rate_limit", return_value=True),
        patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}),
    ]


def _retry_patches():
    """Common patches for the retry endpoint (image already stored)."""
    return [
        patch("app.main.is_auth_enabled", return_value=False),
        patch("app.estimate_routes.check_rate_limit", return_value=True),
        patch(
            "app.estimate_routes._load_estimate_upload_bytes",
            return_value=(b"\xff\xd8\xff" + b"\x00" * 64, ".jpg"),
        ),
        patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}),
    ]


class TestEstimateV2GeographyRetry:
    """Tests for geography retry on the estimate results flow."""

    def test_results_have_retry_button(self, client):
        """After an estimate, results include a 'Try different location' control."""
        gemini_patch = patch("app.estimate_routes._call_gemini_date_estimate")
        with ExitStack() as stack:
            for p in _upload_patches():
                stack.enter_context(p)
            mock_gemini = stack.enter_context(gemini_patch)
            mock_gemini.return_value = {
                "best_year_estimate": 1935,
                "estimated_decade": 1930,
                "location": {"primary_location": "New York, USA"},
            }

            resp = client.post(
                "/api/estimate/upload",
                files={"photo": ("test.jpg", _fake_image_bytes(), "image/jpeg")},
            )
            assert resp.status_code == 200
            assert "Try different location" in resp.text
            assert 'hx-post="/api/estimate/retry"' in resp.text

    def test_geography_retry_endpoint_exists(self, client):
        """POST /api/estimate/retry exists and returns 200 (not 404)."""
        gemini_patch = patch("app.estimate_routes._call_gemini_date_estimate")
        with ExitStack() as stack:
            for p in _retry_patches():
                stack.enter_context(p)
            mock_gemini = stack.enter_context(gemini_patch)
            mock_gemini.return_value = {
                "best_year_estimate": 1930,
                "estimated_decade": 1930,
                "location": {"primary_location": "Rhodes, Greece"},
            }

            resp = client.post(
                "/api/estimate/retry",
                data={"upload_id": "abc123def456", "location": "Rhodes, Greece"},
            )
            assert resp.status_code == 200

    def test_retry_passes_location_as_constraint(self, client):
        """Retry passes the location via photo_metadata['user_location']."""
        gemini_patch = patch("app.estimate_routes._call_gemini_date_estimate")
        with ExitStack() as stack:
            for p in _retry_patches():
                stack.enter_context(p)
            mock_gemini = stack.enter_context(gemini_patch)
            mock_gemini.return_value = {
                "best_year_estimate": 1930,
                "estimated_decade": 1930,
                "location": {"primary_location": "Rhodes, Greece"},
            }

            resp = client.post(
                "/api/estimate/retry",
                data={"upload_id": "abc123def456", "location": "Rhodes, Greece"},
            )
            assert resp.status_code == 200
            kwargs = mock_gemini.call_args.kwargs
            assert kwargs.get("photo_metadata", {}).get("user_location") == "Rhodes, Greece"

    def test_retry_shows_side_by_side_results(self, client):
        """Retry shows original + revised estimates side by side."""
        gemini_patch = patch("app.estimate_routes._call_gemini_date_estimate")
        with ExitStack() as stack:
            for p in _retry_patches():
                stack.enter_context(p)
            mock_gemini = stack.enter_context(gemini_patch)
            mock_gemini.return_value = {
                "best_year_estimate": 1930,
                "estimated_decade": 1930,
                "location": {"primary_location": "Rhodes, Greece"},
            }

            resp = client.post(
                "/api/estimate/retry",
                data={
                    "upload_id": "abc123def456",
                    "location": "Rhodes, Greece",
                    "orig_year": "1935",
                    "orig_location": "New York, USA",
                },
            )
            assert resp.status_code == 200
            html = resp.text
            assert "Original estimate" in html
            assert "Revised estimate" in html
            assert "Rhodes, Greece" in html
            assert "New York, USA" in html

    def test_retry_logged_with_trigger_geography_retry(self, client):
        """Retry Gemini call uses trigger='geography_retry'."""
        gemini_patch = patch("app.estimate_routes._call_gemini_date_estimate")
        with ExitStack() as stack:
            for p in _retry_patches():
                stack.enter_context(p)
            mock_gemini = stack.enter_context(gemini_patch)
            mock_gemini.return_value = {
                "best_year_estimate": 1930,
                "estimated_decade": 1930,
                "location": {"primary_location": "Rhodes, Greece"},
            }

            resp = client.post(
                "/api/estimate/retry",
                data={"upload_id": "abc123def456", "location": "Rhodes, Greece"},
            )
            assert resp.status_code == 200
            assert mock_gemini.call_args.kwargs.get("trigger") == "geography_retry"

    def test_retry_respects_rate_limit(self, client):
        """Retries count toward the same IP rate limit (429 when exceeded)."""
        patches = [
            patch("app.main.is_auth_enabled", return_value=False),
            patch("app.estimate_routes.check_rate_limit", return_value=False),
        ]
        with ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            resp = client.post(
                "/api/estimate/retry",
                data={"upload_id": "abc123def456", "location": "Rhodes, Greece"},
            )
            assert resp.status_code == 429

    def test_retry_missing_location_prompts_user(self, client):
        """Empty location returns a prompt and does NOT call Gemini."""
        gemini_patch = patch("app.estimate_routes._call_gemini_date_estimate")
        with ExitStack() as stack:
            for p in _retry_patches():
                stack.enter_context(p)
            mock_gemini = stack.enter_context(gemini_patch)
            resp = client.post(
                "/api/estimate/retry",
                data={"upload_id": "abc123def456", "location": "  "},
            )
            assert resp.status_code == 200
            assert "Please enter a location" in resp.text
            mock_gemini.assert_not_called()

    def test_retry_missing_upload_is_handled(self, client):
        """When the stored image is gone, retry returns a friendly message."""
        gemini_patch = patch("app.estimate_routes._call_gemini_date_estimate")
        patches = [
            patch("app.main.is_auth_enabled", return_value=False),
            patch("app.estimate_routes.check_rate_limit", return_value=True),
            patch("app.estimate_routes._load_estimate_upload_bytes", return_value=(None, "")),
            patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}),
        ]
        with ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            mock_gemini = stack.enter_context(gemini_patch)
            resp = client.post(
                "/api/estimate/retry",
                data={"upload_id": "abc123def456", "location": "Rhodes, Greece"},
            )
            assert resp.status_code == 200
            assert "no longer available" in resp.text
            mock_gemini.assert_not_called()
