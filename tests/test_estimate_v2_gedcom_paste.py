"""
Tests for TOOLS-005 / PRD-055 Flow 1: GEDCOM paste in /tools/estimate.

User pastes GEDCOM text alongside a photo. The system parses INDI records
(name, birth/death year, place) into a context block that is injected into the
Gemini prompt as user-provided genealogical context. (File upload is out of
scope per PRD-055 — paste only.)
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
    """Tests for GEDCOM paste/upload input on the estimate flow."""

    def test_estimate_page_has_gedcom_input(self, client):
        """GET /tools/estimate renders an optional family-tree paste area."""
        with ExitStack() as stack:
            for p in _page_patches():
                stack.enter_context(p)
            resp = client.get("/tools/estimate")
            assert resp.status_code == 200
            assert "Paste family tree info" in resp.text
            assert 'name="gedcom_text"' in resp.text

    def test_gedcom_text_parsed_and_passed_to_gemini(self, client):
        """Pasted GEDCOM is parsed and passed as gedcom_context to Gemini."""
        gemini_patch = patch("app.estimate_routes._call_gemini_date_estimate")
        with ExitStack() as stack:
            for p in _upload_patches():
                stack.enter_context(p)
            mock_gemini = stack.enter_context(gemini_patch)
            mock_gemini.return_value = {
                "best_year_estimate": 1935,
                "estimated_decade": 1930,
                "probable_range": [1930, 1940],
            }

            resp = client.post(
                "/api/estimate/upload",
                files={"photo": ("test.jpg", _fake_image_bytes(), "image/jpeg")},
                data={"gedcom_text": SAMPLE_GEDCOM_TEXT},
            )
            assert resp.status_code == 200

            kwargs = mock_gemini.call_args.kwargs
            gedcom_ctx = kwargs.get("gedcom_context", "") or ""
            assert "Leon" in gedcom_ctx and "Capeluto" in gedcom_ctx
            assert "1895" in gedcom_ctx
            assert "Rhodes, Greece" in gedcom_ctx
            assert kwargs.get("enrichment_level") == "gedcom_user_provided"

    def test_invalid_gedcom_falls_back_to_visual_only(self, client):
        """Unparseable GEDCOM text falls back to visual-only estimation."""
        gemini_patch = patch("app.estimate_routes._call_gemini_date_estimate")
        with ExitStack() as stack:
            for p in _upload_patches():
                stack.enter_context(p)
            mock_gemini = stack.enter_context(gemini_patch)
            mock_gemini.return_value = {"best_year_estimate": 1940, "estimated_decade": 1940}

            resp = client.post(
                "/api/estimate/upload",
                files={"photo": ("test.jpg", _fake_image_bytes(), "image/jpeg")},
                data={"gedcom_text": "This is not valid GEDCOM data at all."},
            )
            assert resp.status_code == 200
            assert "1940" in resp.text

            kwargs = mock_gemini.call_args.kwargs
            assert not kwargs.get("gedcom_context")
            assert kwargs.get("enrichment_level") is None

    def test_results_show_gedcom_badge(self, client):
        """When GEDCOM context is used, results show a 'Family tree context' badge."""
        gemini_patch = patch("app.estimate_routes._call_gemini_date_estimate")
        with ExitStack() as stack:
            for p in _upload_patches():
                stack.enter_context(p)
            mock_gemini = stack.enter_context(gemini_patch)
            mock_gemini.return_value = {
                "best_year_estimate": 1935,
                "estimated_decade": 1930,
                "location": {"place": "Rhodes, Greece"},
            }

            resp = client.post(
                "/api/estimate/upload",
                files={"photo": ("test.jpg", _fake_image_bytes(), "image/jpeg")},
                data={"gedcom_text": SAMPLE_GEDCOM_TEXT},
            )
            assert resp.status_code == 200
            assert "Family tree context" in resp.text

    def test_no_gedcom_no_badge_regression(self, client):
        """Visual-only upload (no GEDCOM) must NOT show the family-tree badge."""
        gemini_patch = patch("app.estimate_routes._call_gemini_date_estimate")
        with ExitStack() as stack:
            for p in _upload_patches():
                stack.enter_context(p)
            mock_gemini = stack.enter_context(gemini_patch)
            mock_gemini.return_value = {
                "best_year_estimate": 1935,
                "estimated_decade": 1930,
                "location": {"place": "Rhodes, Greece"},
            }

            resp = client.post(
                "/api/estimate/upload",
                files={"photo": ("test.jpg", _fake_image_bytes(), "image/jpeg")},
            )
            assert resp.status_code == 200
            assert "Family tree context" not in resp.text
            assert not mock_gemini.call_args.kwargs.get("gedcom_context")
