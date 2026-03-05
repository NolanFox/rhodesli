"""Tests for re-analyze section refresh (Session 89d).

Verifies that re-analyze response triggers refresh of AI sections,
and that the "Last analyzed" timestamp is visible.
"""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_label_data():
    return {
        "test123": {
            "photo_id": "test123",
            "estimated_decade": 1940,
            "best_year_estimate": 1942,
            "confidence": "medium",
            "model": "gemini-3.1-pro-preview",
            "reanalyzed_at": "2026-03-05T12:00:00+00:00",
            "prompt_version": "v3_enriched",
            "scene_description": "A restaurant interior",
        }
    }


class TestReanalyzeRefreshTrigger:
    """Verify re-analyze response includes HX-Trigger for section refresh."""

    def test_reanalyze_returns_hx_trigger_header(self, client, mock_label_data):
        """After re-analyze, response should include HX-Trigger: refreshAnalysis."""
        mock_result = {
            "estimated_decade": 1940,
            "best_year_estimate": 1942,
            "confidence": "medium",
            "location": {"place": "San Francisco"},
            "probable_range": [1935, 1945],
        }

        with (
            patch("app.estimate_routes._main_mod._check_admin", return_value=None),
            patch(
                "app.estimate_routes.os.getenv", side_effect=lambda k, d="": "fake-key" if k == "GEMINI_API_KEY" else d
            ),
            patch("app.estimate_routes._load_photo_image_bytes", return_value=(b"fake", ".jpg")),
            patch("app.estimate_routes._main_mod._load_date_labels", return_value=mock_label_data),
            patch("app.estimate_routes._main_mod._load_photo_locations", return_value={}),
            patch("app.estimate_routes._build_gedcom_context_for_photo", return_value=None),
            patch("app.estimate_routes._call_gemini_date_estimate", return_value=mock_result),
            patch("app.estimate_routes._main_mod._date_labels_cache", None),
            patch("app.estimate_routes._main_mod._photo_locations_cache", None),
            patch("app.estimate_routes.Path") as mock_path,
            patch("rhodesli_ml.gemini_config.GEMINI_MODEL", "gemini-3.1-pro-preview"),
        ):
            mock_path.return_value.exists.return_value = False
            resp = client.post("/api/photo/test123/reanalyze")

        assert resp.status_code == 200
        assert resp.headers.get("hx-trigger") == "refreshAnalysis"
        assert "Re-analysis complete" in resp.text


class TestAiSectionsEndpoint:
    """Verify /api/photo/{photo_id}/ai-sections returns refreshed content."""

    def test_ai_sections_returns_content(self, client, mock_label_data):
        with (
            patch("app.main._load_date_labels", return_value=mock_label_data),
            patch("app.main._load_search_index", return_value=[]),
            patch("app.main._load_photo_locations", return_value={}),
            patch("app.main._detective_evidence_section", return_value=None),
            patch("app.main._check_admin", return_value=None),
        ):
            resp = client.get("/api/photo/test123/ai-sections")

        assert resp.status_code == 200
        assert "Date Estimate" in resp.text or "1942" in resp.text

    def test_ai_sections_empty_for_unknown_photo(self, client):
        with (
            patch("app.main._load_date_labels", return_value={}),
            patch("app.main._check_admin", return_value=None),
        ):
            resp = client.get("/api/photo/nonexistent/ai-sections")

        assert resp.status_code == 200


class TestLastAnalyzedIndicator:
    """Verify 'Last analyzed' timestamp appears near Re-analyze button."""

    def test_last_analyzed_shown_for_admin(self, client, mock_label_data):
        """Photo page should show 'Last analyzed: Mar 5, 2026' for admin."""
        mock_photo_cache = {
            "test123": {
                "filename": "test.jpg",
                "source": "Test",
                "collection": "Test",
                "faces": [],
            }
        }
        mock_registry = MagicMock()
        mock_registry.list_identities.return_value = []

        with (
            patch("app.main._build_caches"),
            patch("app.main._photo_cache", mock_photo_cache),
            patch("app.main._face_to_photo_cache", {"test123": "test123"}),
            patch("app.main._load_date_labels", return_value=mock_label_data),
            patch("app.main._load_search_index", return_value=[]),
            patch("app.main._load_photo_locations", return_value={}),
            patch("app.main.load_registry", return_value=mock_registry),
            patch("app.main._check_admin", return_value=None),
            patch("app.main._check_login", return_value=None),
            patch("app.main.get_identity_for_face", return_value=None),
        ):
            resp = client.get("/photo/test123")

        assert resp.status_code == 200
        assert "Last analyzed" in resp.text
        assert "Mar 5, 2026" in resp.text
