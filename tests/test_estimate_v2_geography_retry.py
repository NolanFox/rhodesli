"""
Tests for TOOLS-005: Geography retry logic in /tools/estimate.

Flow 3 from PRD-055: After receiving an initial estimate, the user can
disagree with the location and request a re-estimate with a different
geographic assumption. The system re-runs Gemini with the user-supplied
location as a constraint and shows both results side by side.

All tests are xfail — the feature is not yet implemented.
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
    """Common patches for upload endpoint tests."""
    return [
        patch("app.main.is_auth_enabled", return_value=False),
        patch("app.main._build_caches"),
        patch("app.main._load_date_labels", return_value={}),
        patch("core.storage.can_write_r2", return_value=False),
        patch("core.storage.get_upload_url", return_value="/uploads/test.jpg"),
        patch("app.rate_limit.check_rate_limit", return_value=True),
    ]


class TestEstimateV2GeographyRetry:
    """Tests for geography retry on the estimate results flow."""

    @pytest.mark.xfail(reason="TOOLS-005 not implemented")
    def test_results_have_retry_button(self, client):
        """After an initial estimate, the results HTML should include a
        'Try different location' button.

        Acceptance criterion: 'Try different location' button appears on
        the results page.
        """
        gemini_patch = patch("app.estimate_routes._call_gemini_date_estimate")
        with ExitStack() as stack:
            for p in _upload_patches():
                stack.enter_context(p)
            mock_gemini = stack.enter_context(gemini_patch)
            mock_gemini.return_value = {
                "date_estimation": {"estimated_year": 1935, "confidence_range": [1930, 1940]},
                "location": {"primary_location": "New York, USA"},
            }

            resp = client.post(
                "/api/estimate/upload",
                files={"photo": ("test.jpg", _fake_image_bytes(), "image/jpeg")},
            )
            assert resp.status_code == 200
            assert "Try different location" in resp.text or "try-different-location" in resp.text

    @pytest.mark.xfail(reason="TOOLS-005 not implemented")
    def test_geography_retry_endpoint_exists(self, client):
        """A POST endpoint for geography retry should exist and accept
        an upload_id + location parameter.

        The retry reuses the same uploaded image (no re-upload required).
        """
        gemini_patch = patch("app.estimate_routes._call_gemini_date_estimate")
        with ExitStack() as stack:
            for p in _upload_patches():
                stack.enter_context(p)
            mock_gemini = stack.enter_context(gemini_patch)
            mock_gemini.return_value = {
                "date_estimation": {"estimated_year": 1930, "confidence_range": [1925, 1935]},
                "location": {"primary_location": "Rhodes, Greece"},
            }

            resp = client.post(
                "/api/estimate/retry",
                data={
                    "upload_id": "abc123def456",
                    "location": "Rhodes, Greece",
                },
            )
            # Endpoint should exist and not 404
            assert resp.status_code != 404
            assert resp.status_code == 200

    @pytest.mark.xfail(reason="TOOLS-005 not implemented")
    def test_retry_passes_location_as_constraint(self, client):
        """Geography retry should pass the user-supplied location to
        _call_gemini_date_estimate() via photo_metadata['user_location'].
        """
        gemini_patch = patch("app.estimate_routes._call_gemini_date_estimate")
        with ExitStack() as stack:
            for p in _upload_patches():
                stack.enter_context(p)
            mock_gemini = stack.enter_context(gemini_patch)
            mock_gemini.return_value = {
                "date_estimation": {"estimated_year": 1930, "confidence_range": [1925, 1935]},
                "location": {"primary_location": "Rhodes, Greece"},
            }

            resp = client.post(
                "/api/estimate/retry",
                data={
                    "upload_id": "abc123def456",
                    "location": "Rhodes, Greece",
                },
            )
            assert resp.status_code == 200

            call_args = mock_gemini.call_args
            assert call_args is not None
            kwargs = call_args.kwargs if call_args.kwargs else {}
            photo_metadata = kwargs.get("photo_metadata", {})
            assert photo_metadata.get("user_location") == "Rhodes, Greece"

    @pytest.mark.xfail(reason="TOOLS-005 not implemented")
    def test_retry_shows_side_by_side_results(self, client):
        """Geography retry results should show both the original estimate
        and the revised estimate side by side.

        Acceptance criterion: New result shows alongside original with
        'Original estimate' / 'Revised estimate' labels.
        """
        gemini_patch = patch("app.estimate_routes._call_gemini_date_estimate")
        with ExitStack() as stack:
            for p in _upload_patches():
                stack.enter_context(p)
            mock_gemini = stack.enter_context(gemini_patch)
            mock_gemini.return_value = {
                "date_estimation": {"estimated_year": 1930, "confidence_range": [1925, 1935]},
                "location": {"primary_location": "Rhodes, Greece"},
            }

            resp = client.post(
                "/api/estimate/retry",
                data={
                    "upload_id": "abc123def456",
                    "location": "Rhodes, Greece",
                },
            )
            assert resp.status_code == 200
            html = resp.text
            assert "Original estimate" in html or "original-estimate" in html
            assert "Revised estimate" in html or "revised-estimate" in html

    @pytest.mark.xfail(reason="TOOLS-005 not implemented")
    def test_retry_logged_with_trigger_geography_retry(self, client):
        """Geography retry Gemini call should be logged with
        trigger='geography_retry' in the gemini_api_calls table.
        """
        gemini_patch = patch("app.estimate_routes._call_gemini_date_estimate")
        with ExitStack() as stack:
            for p in _upload_patches():
                stack.enter_context(p)
            mock_gemini = stack.enter_context(gemini_patch)
            mock_gemini.return_value = {
                "date_estimation": {"estimated_year": 1930, "confidence_range": [1925, 1935]},
                "location": {"primary_location": "Rhodes, Greece"},
            }

            resp = client.post(
                "/api/estimate/retry",
                data={
                    "upload_id": "abc123def456",
                    "location": "Rhodes, Greece",
                },
            )
            assert resp.status_code == 200

            call_args = mock_gemini.call_args
            assert call_args is not None
            kwargs = call_args.kwargs if call_args.kwargs else {}
            assert kwargs.get("trigger") == "geography_retry"

    @pytest.mark.xfail(reason="TOOLS-005 not implemented")
    def test_retry_respects_rate_limit(self, client):
        """Geography retries should count toward the same IP rate limit
        as initial uploads.
        """
        patches = [
            patch("app.main.is_auth_enabled", return_value=False),
            patch("app.main._build_caches"),
            patch("app.main._load_date_labels", return_value={}),
            patch("core.storage.can_write_r2", return_value=False),
            patch("core.storage.get_upload_url", return_value="/uploads/test.jpg"),
            patch("app.rate_limit.check_rate_limit", return_value=False),
        ]
        with ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            resp = client.post(
                "/api/estimate/retry",
                data={
                    "upload_id": "abc123def456",
                    "location": "Rhodes, Greece",
                },
            )
            assert resp.status_code == 429
