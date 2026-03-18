"""Tests for core/ml_run_logger.py — ML Run Provenance (AD-227, Session 115).

Verifies that ML pipeline runs are logged with full provenance:
execution environment, model versions, community scope, and fine-grained filters.
"""

import os
import pytest
from unittest.mock import MagicMock, patch


class TestGetExecutionEnvironment:
    """Test environment detection."""

    def test_defaults_to_local_laptop(self):
        from core.ml_run_logger import get_execution_environment

        with patch.dict(os.environ, {}, clear=True):
            # When no EXECUTION_ENVIRONMENT set, default is local_laptop
            env = get_execution_environment()
            assert env == os.getenv("EXECUTION_ENVIRONMENT", "local_laptop")

    def test_reads_env_var(self):
        from core.ml_run_logger import get_execution_environment

        with patch.dict(os.environ, {"EXECUTION_ENVIRONMENT": "railway_ml_service"}):
            assert get_execution_environment() == "railway_ml_service"

    def test_reads_railway_web(self):
        from core.ml_run_logger import get_execution_environment

        with patch.dict(os.environ, {"EXECUTION_ENVIRONMENT": "railway_web"}):
            assert get_execution_environment() == "railway_web"


class TestGetModelVersions:
    """Test model version detection."""

    def test_returns_dict(self):
        from core.ml_run_logger import get_model_versions

        versions = get_model_versions()
        assert isinstance(versions, dict)

    def test_includes_numpy(self):
        """NumPy should always be available in our env."""
        from core.ml_run_logger import get_model_versions

        versions = get_model_versions()
        assert "numpy" in versions

    def test_handles_missing_packages_gracefully(self):
        """Should not raise even if insightface is not installed."""
        from core.ml_run_logger import get_model_versions

        # This should work regardless of whether insightface is installed
        versions = get_model_versions()
        assert isinstance(versions, dict)


class TestLogMlRun:
    """Test ML run creation."""

    def test_creates_run_with_all_fields(self):
        from core.ml_run_logger import log_ml_run

        mock_client = MagicMock()
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"run_id": "test-run-123"}]
        )

        run_id = log_ml_run(
            supabase_client=mock_client,
            pipeline_type="clustering",
            config={"threshold": 1.05},
            triggered_by="upload_webhook",
            community_id="comm-uuid-1",
            scope_filter={"batch_id": "batch-2026-03-18"},
        )

        assert run_id == "test-run-123"

        # Verify the insert was called with correct data
        insert_call = mock_client.table.return_value.insert.call_args
        insert_data = insert_call[0][0]
        assert insert_data["pipeline_type"] == "clustering"
        assert insert_data["config_json"] == {"threshold": 1.05}
        assert insert_data["triggered_by"] == "upload_webhook"
        assert insert_data["status"] == "running"
        assert insert_data["community_id"] == "comm-uuid-1"
        assert insert_data["scope_filter"] == {"batch_id": "batch-2026-03-18"}
        assert "execution_environment" in insert_data
        assert "model_versions" in insert_data

    def test_returns_none_without_client(self):
        from core.ml_run_logger import log_ml_run

        run_id = log_ml_run(
            supabase_client=None,
            pipeline_type="clustering",
        )
        assert run_id is None

    def test_returns_none_on_error(self):
        from core.ml_run_logger import log_ml_run

        mock_client = MagicMock()
        mock_client.table.return_value.insert.return_value.execute.side_effect = Exception("DB error")

        run_id = log_ml_run(
            supabase_client=mock_client,
            pipeline_type="clustering",
        )
        assert run_id is None

    def test_omits_nullable_fields_when_none(self):
        """community_id and scope_filter should not be in insert when None."""
        from core.ml_run_logger import log_ml_run

        mock_client = MagicMock()
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"run_id": "test-run-456"}]
        )

        log_ml_run(
            supabase_client=mock_client,
            pipeline_type="detection",
        )

        insert_data = mock_client.table.return_value.insert.call_args[0][0]
        assert "community_id" not in insert_data
        assert "scope_filter" not in insert_data
        assert "parent_run_id" not in insert_data

    def test_defaults_config_to_empty_dict(self):
        from core.ml_run_logger import log_ml_run

        mock_client = MagicMock()
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"run_id": "test-run-789"}]
        )

        log_ml_run(supabase_client=mock_client, pipeline_type="calibration")

        insert_data = mock_client.table.return_value.insert.call_args[0][0]
        assert insert_data["config_json"] == {}


class TestCompleteMlRun:
    """Test ML run completion."""

    def test_marks_completed(self):
        from core.ml_run_logger import complete_ml_run

        mock_client = MagicMock()
        result = complete_ml_run(
            mock_client,
            run_id="run-123",
            result_summary={"proposals": 42},
            duration_ms=1500,
        )
        assert result is True

        update_data = mock_client.table.return_value.update.call_args[0][0]
        assert update_data["status"] == "completed"
        assert update_data["result_summary"] == {"proposals": 42}
        assert update_data["duration_ms"] == 1500

    def test_returns_false_without_client(self):
        from core.ml_run_logger import complete_ml_run

        assert complete_ml_run(None, "run-123", {}, 0) is False

    def test_returns_false_without_run_id(self):
        from core.ml_run_logger import complete_ml_run

        assert complete_ml_run(MagicMock(), None, {}, 0) is False


class TestFailMlRun:
    """Test ML run failure recording."""

    def test_marks_failed(self):
        from core.ml_run_logger import fail_ml_run

        mock_client = MagicMock()
        result = fail_ml_run(
            mock_client,
            run_id="run-456",
            error="ValueError: bad data",
            duration_ms=500,
        )
        assert result is True

        update_data = mock_client.table.return_value.update.call_args[0][0]
        assert update_data["status"] == "failed"
        assert update_data["result_summary"]["error"] == "ValueError: bad data"


class TestMLRunContext:
    """Test context manager for ML runs."""

    def test_success_path(self):
        from core.ml_run_logger import MLRunContext

        mock_client = MagicMock()
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"run_id": "ctx-run-1"}]
        )

        with MLRunContext(mock_client, "clustering", config={"k": 5}) as run:
            run.set_result({"clusters": 10})

        # Should have called insert (start) and update (complete)
        assert mock_client.table.return_value.insert.called
        assert mock_client.table.return_value.update.called

        update_data = mock_client.table.return_value.update.call_args[0][0]
        assert update_data["status"] == "completed"
        assert update_data["result_summary"] == {"clusters": 10}

    def test_failure_path(self):
        from core.ml_run_logger import MLRunContext

        mock_client = MagicMock()
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"run_id": "ctx-run-2"}]
        )

        with pytest.raises(ValueError):
            with MLRunContext(mock_client, "clustering") as run:
                raise ValueError("bad input")

        update_data = mock_client.table.return_value.update.call_args[0][0]
        assert update_data["status"] == "failed"
        assert "bad input" in update_data["result_summary"]["error"]

    def test_community_scoped_run(self):
        from core.ml_run_logger import MLRunContext

        mock_client = MagicMock()
        mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"run_id": "ctx-run-3"}]
        )

        with MLRunContext(
            mock_client,
            "cross_batch",
            community_id="fox-family-uuid",
            scope_filter={"batch_id": "upload-2026-03-18"},
            triggered_by="upload_webhook",
        ) as run:
            run.set_result({"matches": 5})

        insert_data = mock_client.table.return_value.insert.call_args[0][0]
        assert insert_data["community_id"] == "fox-family-uuid"
        assert insert_data["scope_filter"] == {"batch_id": "upload-2026-03-18"}
        assert insert_data["triggered_by"] == "upload_webhook"
