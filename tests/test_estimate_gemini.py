"""Tests for Gemini date estimation integration in estimate_routes.py.

Covers:
- _call_gemini_date_estimate uses build_extraction_prompt (not old _GEMINI_DATE_PROMPT)
- GEDCOM context is passed through to prompt when available
- API call logging via log_gemini_call on every invocation
- Location data extracted from enriched response
- Graceful fallback when GEDCOM is unavailable
- Error handling and logging on API failure
"""

import json
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Mock Gemini response matching enriched prompt output
# ---------------------------------------------------------------------------

_MOCK_GEMINI_RESPONSE = {
    "date_estimation": {
        "evidence": {
            "print_format": [{"cue": "gelatin silver print", "strength": "moderate", "suggested_range": [1920, 1945]}],
            "fashion": [{"cue": "1930s dress style", "strength": "strong", "suggested_range": [1930, 1940]}],
            "environment": [],
            "technology": [],
        },
        "cultural_lag_applied": True,
        "cultural_lag_note": "Sephardic community fashion lag",
        "estimated_decade": 1930,
        "best_year_estimate": 1934,
        "confidence": "high",
        "probable_range": [1930, 1938],
        "decade_probabilities": {"1920": 0.1, "1930": 0.8, "1940": 0.1},
        "reasoning_summary": "1930s dress, children's ages consistent with 1934",
    },
    "location": {
        "place": "Asheville, North Carolina",
        "confidence": "high",
        "visual_evidence": "Brick apartment with sun porches",
        "biographical_evidence": "Family resided at 33 Elizabeth St, Asheville NC",
    },
}


def _make_mock_response(response_dict):
    """Create a mock Gemini API response object."""
    mock_resp = MagicMock()
    mock_resp.text = json.dumps(response_dict)
    return mock_resp


class TestCallGeminiDateEstimate:
    """Tests for _call_gemini_date_estimate function."""

    @patch("app.estimate_routes.log_gemini_call", create=True)
    def test_uses_enriched_prompt(self, mock_log):
        """Verify build_extraction_prompt is used (not old _GEMINI_DATE_PROMPT)."""
        from app.estimate_routes import _call_gemini_date_estimate

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _make_mock_response(_MOCK_GEMINI_RESPONSE)

        with (
            patch("google.genai.Client", return_value=mock_client),
            patch(
                "rhodesli_ml.gemini_extraction.build_extraction_prompt", return_value="enriched prompt"
            ) as mock_build,
            patch("app.supabase_data.log_gemini_call", return_value=True),
        ):
            result = _call_gemini_date_estimate(b"fake_image", ".jpg", "fake_key", photo_id="test123")

        # build_extraction_prompt should be called with quick preset
        mock_build.assert_called_once_with(preset="quick", gedcom_context=None, photo_metadata=None)

        assert result is not None
        assert result["estimated_decade"] == 1930
        assert result["best_year_estimate"] == 1934

    @patch("app.supabase_data.log_gemini_call", return_value=True)
    def test_gedcom_context_passed_to_prompt(self, mock_log):
        """Verify GEDCOM context is forwarded to build_extraction_prompt."""
        from app.estimate_routes import _call_gemini_date_estimate

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _make_mock_response(_MOCK_GEMINI_RESPONSE)

        gedcom_ctx = "Person: Victoria Capuano\n  Born: 1908 in Rhodes"

        with (
            patch("google.genai.Client", return_value=mock_client),
            patch("rhodesli_ml.gemini_extraction.build_extraction_prompt", return_value="prompt") as mock_build,
        ):
            _call_gemini_date_estimate(
                b"fake_image",
                ".jpg",
                "fake_key",
                photo_id="test123",
                gedcom_context=gedcom_ctx,
            )

        mock_build.assert_called_once_with(preset="quick", gedcom_context=gedcom_ctx, photo_metadata=None)

    @patch("app.supabase_data.log_gemini_call", return_value=True)
    def test_api_call_logged_on_success(self, mock_log):
        """Every Gemini call must be logged to Supabase."""
        from app.estimate_routes import _call_gemini_date_estimate

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _make_mock_response(_MOCK_GEMINI_RESPONSE)

        with (
            patch("google.genai.Client", return_value=mock_client),
            patch("rhodesli_ml.gemini_extraction.build_extraction_prompt", return_value="prompt"),
        ):
            _call_gemini_date_estimate(
                b"fake_image",
                ".jpg",
                "fake_key",
                photo_id="photo_abc",
            )

        mock_log.assert_called_once()
        call_kwargs = mock_log.call_args
        assert call_kwargs.kwargs["photo_id"] == "photo_abc"
        assert call_kwargs.kwargs["call_type"] == "date_estimation"
        assert call_kwargs.kwargs["status"] == "success"
        assert "gemini_config" in call_kwargs.kwargs
        config = call_kwargs.kwargs["gemini_config"]
        assert config["enrichment_level"] == "none"
        assert config["prompt_version"] == "v3_enriched"
        assert config["prompt_variant"] == "quick_visual_only"
        assert config["trigger"] == "interactive_upload"
        assert call_kwargs.kwargs["prompt_family"] == "date_estimation"
        assert call_kwargs.kwargs["prompt_version"] == "v3"
        assert call_kwargs.kwargs["prompt_variant"] == "quick_visual_only"
        assert call_kwargs.kwargs["prompt_contract_version"] == "contract2"
        assert call_kwargs.kwargs["request_mode"] == "interactive"
        assert call_kwargs.kwargs["contract_valid"] is True
        assert call_kwargs.kwargs["prompt_manifest_id"].startswith(
            "date_estimation:v3:quick_visual_only:contract2"
        )

    @patch("app.supabase_data.log_gemini_call", return_value=True)
    def test_api_call_logged_on_error(self, mock_log):
        """API call must be logged even on failure."""
        from app.estimate_routes import _call_gemini_date_estimate

        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = RuntimeError("API down")

        with (
            patch("google.genai.Client", return_value=mock_client),
            patch("rhodesli_ml.gemini_extraction.build_extraction_prompt", return_value="prompt"),
        ):
            result = _call_gemini_date_estimate(
                b"fake_image",
                ".jpg",
                "fake_key",
                photo_id="photo_err",
            )

        assert result is None
        mock_log.assert_called_once()
        assert mock_log.call_args.kwargs["status"] == "error"
        assert "API down" in mock_log.call_args.kwargs["error_message"]

    @patch("app.supabase_data.log_gemini_call", return_value=True)
    def test_location_in_result(self, mock_log):
        """Location data from enriched prompt should be in result."""
        from app.estimate_routes import _call_gemini_date_estimate

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _make_mock_response(_MOCK_GEMINI_RESPONSE)

        with (
            patch("google.genai.Client", return_value=mock_client),
            patch("rhodesli_ml.gemini_extraction.build_extraction_prompt", return_value="prompt"),
        ):
            result = _call_gemini_date_estimate(
                b"fake_image",
                ".jpg",
                "fake_key",
                photo_id="photo_loc",
            )

        assert result is not None
        assert "location" in result
        assert result["location"]["place"] == "Asheville, North Carolina"

    @patch("app.supabase_data.log_gemini_call", return_value=True)
    def test_no_logging_without_photo_id(self, mock_log):
        """When photo_id is None, logging is skipped."""
        from app.estimate_routes import _call_gemini_date_estimate

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _make_mock_response(_MOCK_GEMINI_RESPONSE)

        with (
            patch("google.genai.Client", return_value=mock_client),
            patch("rhodesli_ml.gemini_extraction.build_extraction_prompt", return_value="prompt"),
        ):
            result = _call_gemini_date_estimate(
                b"fake_image",
                ".jpg",
                "fake_key",
            )

        assert result is not None
        mock_log.assert_not_called()

    @patch("app.supabase_data.log_gemini_call", return_value=True)
    def test_gedcom_enrichment_level_in_config(self, mock_log):
        """When GEDCOM context is provided, enrichment_level should reflect it."""
        from app.estimate_routes import _call_gemini_date_estimate

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _make_mock_response(_MOCK_GEMINI_RESPONSE)

        with (
            patch("google.genai.Client", return_value=mock_client),
            patch("rhodesli_ml.gemini_extraction.build_extraction_prompt", return_value="prompt"),
        ):
            _call_gemini_date_estimate(
                b"fake_image",
                ".jpg",
                "fake_key",
                photo_id="photo_ged",
                gedcom_context="Person: Victoria",
            )

        config = mock_log.call_args.kwargs["gemini_config"]
        assert config["enrichment_level"] == "gedcom"
        assert config["gedcom_variant"] == "first_order"
        assert config["prompt_variant"] == "quick_gedcom"
        assert mock_log.call_args.kwargs["prompt_variant"] == "quick_gedcom"

    @patch("app.supabase_data.log_gemini_call", return_value=True)
    def test_invalid_decade_returns_none(self, mock_log):
        """Invalid decade in response should return None."""
        from app.estimate_routes import _call_gemini_date_estimate

        bad_response = {
            "date_estimation": {
                "estimated_decade": 999,
                "best_year_estimate": 999,
            }
        }
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _make_mock_response(bad_response)

        with (
            patch("google.genai.Client", return_value=mock_client),
            patch("rhodesli_ml.gemini_extraction.build_extraction_prompt", return_value="prompt"),
        ):
            result = _call_gemini_date_estimate(
                b"fake_image",
                ".jpg",
                "fake_key",
                photo_id="photo_bad",
            )

        assert result is None

    @patch("app.supabase_data.log_gemini_call", return_value=True)
    def test_reanalyze_trigger_and_call_type(self, mock_log):
        """Re-analyze calls should have correct trigger and call_type."""
        from app.estimate_routes import _call_gemini_date_estimate

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _make_mock_response(_MOCK_GEMINI_RESPONSE)

        with (
            patch("google.genai.Client", return_value=mock_client),
            patch("rhodesli_ml.gemini_extraction.build_extraction_prompt", return_value="prompt"),
        ):
            _call_gemini_date_estimate(
                b"fake_image",
                ".jpg",
                "fake_key",
                photo_id="photo_rerun",
                call_type="re_analysis",
                trigger="admin_rerun",
            )

        config = mock_log.call_args.kwargs["gemini_config"]
        assert config["trigger"] == "admin_rerun"
        assert mock_log.call_args.kwargs["call_type"] == "re_analysis"
        assert mock_log.call_args.kwargs["request_mode"] == "admin_tool"


class TestOldPromptRemoved:
    """Verify the old _GEMINI_DATE_PROMPT has been replaced."""

    def test_no_old_prompt_constant(self):
        """The old stripped-down prompt constant should not exist."""
        import app.estimate_routes as er

        assert not hasattr(er, "_GEMINI_DATE_PROMPT"), (
            "_GEMINI_DATE_PROMPT should be removed — replaced by build_extraction_prompt"
        )


class TestOperatorProvenance:
    """Manual-vs-platform provenance tagging on Gemini calls (Session 166).

    Lets the data structurally distinguish a human-directed one-off run
    (operator='claude-code-manual', experiment_id set) from a platform run
    (operator='platform', experiment_id NULL).
    """

    @patch("app.supabase_data.log_gemini_call", return_value=True)
    def test_operator_defaults_to_platform(self, mock_log):
        from app.estimate_routes import _call_gemini_date_estimate

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _make_mock_response(_MOCK_GEMINI_RESPONSE)
        with (
            patch("google.genai.Client", return_value=mock_client),
            patch("rhodesli_ml.gemini_extraction.build_extraction_prompt", return_value="prompt"),
        ):
            _call_gemini_date_estimate(b"img", ".jpg", "key", photo_id="p1")

        config = mock_log.call_args.kwargs["gemini_config"]
        assert config["operator"] == "platform"
        # experiment_id defaults to None -> log_gemini_call drops None values
        assert mock_log.call_args.kwargs.get("experiment_id") is None

    @patch("app.supabase_data.log_gemini_call", return_value=True)
    def test_manual_operator_and_experiment_id_tagged(self, mock_log):
        from app.estimate_routes import _call_gemini_date_estimate

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _make_mock_response(_MOCK_GEMINI_RESPONSE)
        with (
            patch("google.genai.Client", return_value=mock_client),
            patch("rhodesli_ml.gemini_extraction.build_extraction_prompt", return_value="prompt"),
        ):
            _call_gemini_date_estimate(
                b"img",
                ".jpg",
                "key",
                photo_id="p1",
                operator="claude-code-manual",
                experiment_id="manual-multimodel-p1-2026-06-12",
            )

        config = mock_log.call_args.kwargs["gemini_config"]
        assert config["operator"] == "claude-code-manual"
        assert mock_log.call_args.kwargs["experiment_id"] == "manual-multimodel-p1-2026-06-12"
