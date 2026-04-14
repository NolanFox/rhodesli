"""
Tests for TOOLS-005: Text hint support in /tools/estimate.

Flow 2 from PRD-055: User provides free-text hints alongside a photo upload.
Hints are appended to the Gemini prompt in a structured "User context" section.
Results indicate which hints were used.

Tests cover the text hints textarea, Gemini prompt integration, and results display.
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


def _fake_image_bytes(suffix=".jpg"):
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
        patch("app.estimate_routes.check_rate_limit", return_value=True),
        patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}),
    ]


def _page_patches():
    """Patches needed for GET /tools/estimate page rendering."""
    return _upload_patches() + [
        patch("app.main._photo_cache", {}),
        patch("app.main.load_registry", return_value=MagicMock()),
        patch("app.main.load_photo_registry", return_value=MagicMock(list_photos=MagicMock(return_value=[]))),
        patch("app.main.get_crop_files", return_value={}),
        patch(
            "app.main._load_relationship_graph",
            return_value={"schema_version": 1, "relationships": [], "gedcom_imports": []},
        ),
        patch("app.main._load_photo_locations", return_value={}),
    ]


class TestEstimateV2TextHints:
    """Tests for text hint input on the estimate upload flow."""

    def test_estimate_page_has_text_hints_field(self, client):
        """GET /tools/estimate should render an optional text hints input field.

        Acceptance criterion: Input field labeled
        'What do you know about this photo? (optional)' appears on the page.
        """
        with ExitStack() as stack:
            for p in _page_patches():
                stack.enter_context(p)
            resp = client.get("/tools/estimate")
            assert resp.status_code == 200
            assert "What do you know about this photo?" in resp.text

    def test_text_hints_passed_to_gemini_prompt(self, client):
        """POST /api/estimate/upload with text_hints should include hints in the
        Gemini prompt as a 'User context' section.

        The hints string should appear in the prompt_text passed to
        build_extraction_prompt() or appended as a separate section.
        """
        gemini_patch = patch("app.estimate_routes._call_gemini_date_estimate")
        with ExitStack() as stack:
            for p in _upload_patches():
                stack.enter_context(p)
            mock_gemini = stack.enter_context(gemini_patch)
            mock_gemini.return_value = {
                "date_estimation": {"estimated_year": 1935, "confidence_range": [1930, 1940]},
            }

            resp = client.post(
                "/api/estimate/upload",
                files={"photo": ("test.jpg", _fake_image_bytes(), "image/jpeg")},
                data={"text_hints": "Wedding in Rhodes, probably 1930s"},
            )
            assert resp.status_code == 200
            # Verify the hints were passed through (exact mechanism TBD)
            call_args = mock_gemini.call_args
            assert call_args is not None
            # Either as a dedicated parameter or in photo_metadata
            kwargs = call_args.kwargs if call_args.kwargs else {}
            assert (
                "text_hints" in kwargs
                or "user_context" in kwargs
                or (kwargs.get("photo_metadata", {}).get("text_hints"))
            )

    def test_empty_text_hints_falls_back_to_visual_only(self, client):
        """POST /api/estimate/upload with empty text_hints should behave
        identically to a photo-only upload — no regression.

        An empty string or whitespace-only hints field should not alter
        the Gemini prompt.
        """
        gemini_patch = patch("app.estimate_routes._call_gemini_date_estimate")
        with ExitStack() as stack:
            for p in _upload_patches():
                stack.enter_context(p)
            mock_gemini = stack.enter_context(gemini_patch)
            mock_gemini.return_value = {
                "date_estimation": {"estimated_year": 1940, "confidence_range": [1935, 1945]},
            }

            resp = client.post(
                "/api/estimate/upload",
                files={"photo": ("test.jpg", _fake_image_bytes(), "image/jpeg")},
                data={"text_hints": "   "},
            )
            assert resp.status_code == 200
            call_args = mock_gemini.call_args
            kwargs = call_args.kwargs if call_args.kwargs else {}
            # gedcom_context should be None (visual-only)
            assert kwargs.get("gedcom_context") is None

    def test_results_show_which_hints_were_used(self, client):
        """When text hints are provided, the results HTML should indicate
        which hints influenced the estimate (e.g., 'You mentioned: wedding in Rhodes').

        PRD acceptance criterion: Results indicate which hints were used.
        """
        gemini_patch = patch("app.estimate_routes._call_gemini_date_estimate")
        with ExitStack() as stack:
            for p in _upload_patches():
                stack.enter_context(p)
            mock_gemini = stack.enter_context(gemini_patch)
            mock_gemini.return_value = {
                "date_estimation": {"estimated_year": 1935, "confidence_range": [1930, 1940]},
                "location": {"primary_location": "Rhodes, Greece"},
            }

            resp = client.post(
                "/api/estimate/upload",
                files={"photo": ("test.jpg", _fake_image_bytes(), "image/jpeg")},
                data={"text_hints": "Wedding in Rhodes"},
            )
            assert resp.status_code == 200
            assert "You mentioned" in resp.text or "wedding" in resp.text.lower()
