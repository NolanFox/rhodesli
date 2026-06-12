"""Tests for Gemini API call logging to Supabase (AD-152)."""

from unittest.mock import MagicMock, patch


class TestLogGeminiCall:
    """Tests for log_gemini_call."""

    def test_logs_successful_call(self):
        """Creates record with all required fields."""
        mock_sb = MagicMock()
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock()

        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
            from app.supabase_data import log_gemini_call
            result = log_gemini_call(
                photo_id="test123",
                model_used="gemini-3.1-pro-preview",
                call_type="alignment",
                prompt_tokens=1000,
                completion_tokens=500,
                cost_usd=0.028,
                latency_ms=2500,
                status="success",
            )

        assert result is True
        mock_sb.table.assert_called_with("gemini_api_calls")
        call_row = mock_sb.table.return_value.insert.call_args[0][0]
        assert call_row["photo_id"] == "test123"
        assert call_row["model_used"] == "gemini-3.1-pro-preview"
        assert call_row["status"] == "success"

    def test_logs_rate_limited_call(self):
        """Rate-limited calls include rate_limit_type."""
        mock_sb = MagicMock()
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock()

        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
            from app.supabase_data import log_gemini_call
            log_gemini_call(
                photo_id="test456",
                model_used="gemini-3.1-pro-preview",
                call_type="combined",
                status="rate_limited",
                rate_limit_type="rpd",
                error_message="429 Too Many Requests",
            )

        call_row = mock_sb.table.return_value.insert.call_args[0][0]
        assert call_row["status"] == "rate_limited"
        assert call_row["rate_limit_type"] == "rpd"

    def test_returns_false_when_supabase_unavailable(self):
        """Returns False when no Supabase client."""
        with patch("app.supabase_data.get_supabase_client", return_value=None):
            from app.supabase_data import log_gemini_call
            result = log_gemini_call("p1", "model", "type")

        assert result is False

    def test_handles_supabase_error(self):
        """Returns False on Supabase network exception."""
        mock_sb = MagicMock()
        mock_sb.table.return_value.insert.return_value.execute.side_effect = ConnectionError("fail")

        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
            from app.supabase_data import log_gemini_call
            result = log_gemini_call("p1", "model", "type")

        assert result is False

    def test_defaults_status_to_success(self):
        """Status defaults to 'success' when not specified."""
        mock_sb = MagicMock()
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock()

        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
            from app.supabase_data import log_gemini_call
            log_gemini_call("p1", "model", "alignment")

        call_row = mock_sb.table.return_value.insert.call_args[0][0]
        assert call_row["status"] == "success"

    def test_includes_batch_id(self):
        """batch_id groups calls from same batch run."""
        mock_sb = MagicMock()
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock()

        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
            from app.supabase_data import log_gemini_call
            log_gemini_call("p1", "model", "combined", batch_id="batch_20260223")

        call_row = mock_sb.table.return_value.insert.call_args[0][0]
        assert call_row["batch_id"] == "batch_20260223"

    def test_includes_prompt_manifest_fields(self):
        """Prompt-manifest lineage fields are logged as first-class columns."""
        mock_sb = MagicMock()
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock()

        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
            from app.supabase_data import log_gemini_call

            log_gemini_call(
                "p1",
                "model",
                "date_estimation",
                prompt_manifest_id="date_estimation:v3:quick_visual_only:contract2",
                prompt_family="date_estimation",
                prompt_version="v3",
                prompt_variant="quick_visual_only",
                prompt_contract_version="contract2",
                prompt_hash="abc123",
                full_response_hash="def456",
                request_surface="app.estimate_routes._call_gemini_date_estimate",
                request_mode="interactive",
                contract_valid=True,
            )

        call_row = mock_sb.table.return_value.insert.call_args[0][0]
        assert call_row["prompt_manifest_id"] == "date_estimation:v3:quick_visual_only:contract2"
        assert call_row["prompt_family"] == "date_estimation"
        assert call_row["prompt_variant"] == "quick_visual_only"
        assert call_row["contract_valid"] is True


class TestGetGeminiCallSummary:
    """Tests for get_gemini_call_summary."""

    def test_returns_summary(self):
        """Returns aggregated call statistics."""
        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.execute.return_value = MagicMock(
            data=[
                {"cost_usd": 0.028, "status": "success"},
                {"cost_usd": 0.028, "status": "success"},
                {"cost_usd": None, "status": "rate_limited"},
            ]
        )

        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
            from app.supabase_data import get_gemini_call_summary
            result = get_gemini_call_summary()

        assert result["total_calls"] == 3
        assert result["total_cost_usd"] == 0.056
        assert result["by_status"]["success"] == 2
        assert result["by_status"]["rate_limited"] == 1

    def test_returns_none_when_unavailable(self):
        """Returns None when Supabase not configured."""
        with patch("app.supabase_data.get_supabase_client", return_value=None):
            from app.supabase_data import get_gemini_call_summary
            assert get_gemini_call_summary() is None


class TestSchemaDriftFilter:
    """log_gemini_call must not drop the whole insert when the code passes a
    column the live gemini_api_calls table lacks (Lesson 105/152, Session 166).

    Before this fix, build_prompt_lineage_fields() passed contract_valid +
    prompt_manifest_id etc., and PostgREST rejected the ENTIRE insert
    (PGRST204), so every interactive/admin estimate silently failed to log.
    """

    def _reset_cache(self):
        import app.supabase_data as sd

        sd._GEMINI_API_CALLS_COLUMNS = None

    def test_unknown_columns_dropped_and_preserved_in_lineage(self):
        self._reset_cache()
        # Live table exposes this column set (no contract_valid / lineage cols)
        live_cols = {
            "id", "photo_id", "model_used", "call_type", "status",
            "gemini_config", "experiment_id", "cost_usd",
        }
        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[{c: None for c in live_cols}]
        )
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock()

        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
            from app.supabase_data import log_gemini_call

            result = log_gemini_call(
                photo_id="p1",
                model_used="gemini-3.1-pro-preview",
                call_type="re_analysis",
                gemini_config={"operator": "claude-code-manual"},
                contract_valid=True,
                prompt_manifest_id="date_estimation:v3",
                request_surface="app.estimate_routes._call_gemini_date_estimate",
            )

        assert result is True
        row = mock_sb.table.return_value.insert.call_args[0][0]
        # Drifted columns are NOT in the inserted row
        assert "contract_valid" not in row
        assert "prompt_manifest_id" not in row
        assert "request_surface" not in row
        # ...but they are preserved inside gemini_config._lineage (nothing lost)
        lineage = row["gemini_config"]["_lineage"]
        assert lineage["contract_valid"] is True
        assert lineage["prompt_manifest_id"] == "date_estimation:v3"
        assert lineage["request_surface"].endswith("_call_gemini_date_estimate")
        # Known columns survive
        assert row["photo_id"] == "p1"
        assert row["gemini_config"]["operator"] == "claude-code-manual"
        self._reset_cache()

    def test_full_insert_when_column_discovery_fails(self):
        """If column discovery fails (probe errors), insert the full row
        (best-effort, original behavior) rather than dropping data."""
        self._reset_cache()
        mock_sb = MagicMock()
        # Probe raises -> discovery returns None -> no filtering
        mock_sb.table.return_value.select.return_value.limit.return_value.execute.side_effect = RuntimeError(
            "probe failed"
        )
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock()

        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
            from app.supabase_data import log_gemini_call

            result = log_gemini_call(
                photo_id="p2",
                model_used="m",
                call_type="t",
                contract_valid=True,
            )

        assert result is True
        row = mock_sb.table.return_value.insert.call_args[0][0]
        # No filtering applied -> unknown column passes through unchanged
        assert row["contract_valid"] is True
        self._reset_cache()
