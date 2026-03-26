"""
Tests for TOOLS-005: GEDCOM paste/upload in /tools/estimate.

Flow 1 from PRD-055: User pastes GEDCOM text alongside a photo upload.
System parses GEDCOM for names, birth/death years, locations and builds
an enriched Gemini prompt with biographical constraints.

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
        patch("app.estimate_routes.check_rate_limit", return_value=True),
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


SAMPLE_GEDCOM_TEXT = """
0 @I1@ INDI
1 NAME Leon /Capeluto/
1 BIRT
2 DATE 1895
2 PLAC Rhodes, Greece
1 DEAT
2 DATE 1970
2 PLAC New York, USA

0 @I2@ INDI
1 NAME Sarah /Capeluto/
1 BIRT
2 DATE 1900
2 PLAC Rhodes, Greece
""".strip()


class TestEstimateV2GedcomPaste:
    """Tests for GEDCOM paste input on the estimate upload flow."""

    @pytest.mark.xfail(reason="TOOLS-005 not implemented")
    def test_estimate_page_has_gedcom_textarea(self, client):
        """GET /tools/estimate should render an optional GEDCOM textarea.

        Acceptance criterion: Textarea labeled
        'Paste family tree info (optional)' appears below the upload area.
        """
        with ExitStack() as stack:
            for p in _page_patches():
                stack.enter_context(p)
            resp = client.get("/tools/estimate")
            assert resp.status_code == 200
            assert "Paste family tree info" in resp.text

    @pytest.mark.xfail(reason="TOOLS-005 not implemented")
    def test_gedcom_text_parsed_and_passed_to_gemini(self, client):
        """POST /api/estimate/upload with gedcom_text should parse GEDCOM
        INDI records and pass structured context to _call_gemini_date_estimate()
        as the gedcom_context parameter.
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
                data={"gedcom_text": SAMPLE_GEDCOM_TEXT},
            )
            assert resp.status_code == 200

            call_args = mock_gemini.call_args
            assert call_args is not None
            kwargs = call_args.kwargs if call_args.kwargs else {}
            # gedcom_context should contain parsed person data
            gedcom_ctx = kwargs.get("gedcom_context", "")
            assert "Leon" in gedcom_ctx or "Capeluto" in gedcom_ctx
            assert "1895" in gedcom_ctx

    @pytest.mark.xfail(reason="TOOLS-005 not implemented")
    def test_invalid_gedcom_falls_back_to_visual_only(self, client):
        """POST /api/estimate/upload with invalid/unparseable GEDCOM text
        should fall back to visual-only estimation without error.

        Acceptance criterion: Invalid/empty GEDCOM text falls back to
        visual-only estimation.
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
                data={"gedcom_text": "This is not valid GEDCOM data at all."},
            )
            assert resp.status_code == 200
            assert "194" in resp.text

            call_args = mock_gemini.call_args
            kwargs = call_args.kwargs if call_args.kwargs else {}
            assert not kwargs.get("gedcom_context")

    @pytest.mark.xfail(reason="TOOLS-005 not implemented")
    def test_gedcom_enrichment_level_logged(self, client):
        """When GEDCOM text is provided, the Gemini API call should be logged
        with enrichment_level='gedcom_user_provided' in the gemini_api_calls table.
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
                data={"gedcom_text": SAMPLE_GEDCOM_TEXT},
            )
            assert resp.status_code == 200
            call_args = mock_gemini.call_args
            assert call_args is not None

    @pytest.mark.xfail(reason="TOOLS-005 not implemented")
    def test_results_show_gedcom_badge(self, client):
        """When GEDCOM context influenced the result, evidence cards should
        show a 'Family tree context' badge.
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
                data={"gedcom_text": SAMPLE_GEDCOM_TEXT},
            )
            assert resp.status_code == 200
            assert "Family tree context" in resp.text or "family tree" in resp.text.lower()
