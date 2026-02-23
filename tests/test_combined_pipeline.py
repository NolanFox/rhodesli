"""Tests for combined Gemini pipeline and model config centralization (AD-152)."""

from unittest.mock import MagicMock, patch

import pytest


class TestModelConfigCentralization:
    """Verify hardcoded model strings are replaced with config references."""

    def test_call_gemini_alignment_uses_config_default(self):
        """When model=None, uses GEMINI_MODEL from gemini_config."""
        from rhodesli_ml.gemini_config import GEMINI_MODEL

        # Verify the config has a value
        assert GEMINI_MODEL
        assert "gemini" in GEMINI_MODEL

    def test_run_face_alignment_model_default_is_none(self):
        """run_face_alignment model parameter defaults to None (uses config)."""
        import inspect
        from app.face_alignment import run_face_alignment

        sig = inspect.signature(run_face_alignment)
        assert sig.parameters["model"].default is None

    def test_call_gemini_alignment_model_default_is_none(self):
        """call_gemini_alignment model parameter defaults to None (uses config)."""
        import inspect
        from app.face_alignment import call_gemini_alignment

        sig = inspect.signature(call_gemini_alignment)
        assert sig.parameters["model"].default is None

    def test_batch_script_imports_config(self):
        """Batch script imports GEMINI_MODEL, not hardcoded string."""
        from pathlib import Path

        script_path = Path(__file__).resolve().parent.parent / "scripts" / "run_batch_alignment.py"
        content = script_path.read_text()
        assert "from rhodesli_ml.gemini_config import GEMINI_MODEL" in content
        assert "default=GEMINI_MODEL" in content


class TestApiCallLogging:
    """Verify Gemini API calls are logged via log_gemini_call."""

    def test_log_call_helper_exists(self):
        """_log_call helper function exists in face_alignment."""
        from app.face_alignment import _log_call
        assert callable(_log_call)

    def test_log_call_calls_supabase(self):
        """_log_call invokes log_gemini_call with correct params."""
        mock_log = MagicMock()
        with patch("app.supabase_data.log_gemini_call", mock_log):
            from app.face_alignment import _log_call
            _log_call(
                photo_id="test123",
                model="gemini-3.1-pro-preview",
                call_type="alignment",
                prompt_tokens=1000,
                completion_tokens=500,
                cost_usd=0.028,
                start_ms=1000000,
                status="success",
                batch_id="batch_test",
            )
        mock_log.assert_called_once()
        kwargs = mock_log.call_args[1]
        assert kwargs["photo_id"] == "test123"
        assert kwargs["status"] == "success"
        assert kwargs["batch_id"] == "batch_test"

    def test_log_call_skips_when_no_photo_id(self):
        """_log_call returns without logging when photo_id is None."""
        mock_log = MagicMock()
        with patch("app.supabase_data.log_gemini_call", mock_log):
            from app.face_alignment import _log_call
            _log_call(
                photo_id=None,
                model="model",
                call_type="alignment",
                prompt_tokens=0,
                completion_tokens=0,
                cost_usd=0,
                start_ms=1000,
                status="success",
            )
        mock_log.assert_not_called()

    def test_log_call_handles_exception(self):
        """_log_call never raises, even on logging failure."""
        with patch("app.supabase_data.log_gemini_call", side_effect=RuntimeError("db down")):
            from app.face_alignment import _log_call
            # Should not raise
            _log_call("p1", "model", "alignment", 0, 0, 0, 1000, "success")


class TestCombinedPipelineScript:
    """Tests for the combined pipeline script structure."""

    def test_script_exists(self):
        """Combined pipeline script exists."""
        from pathlib import Path
        script = Path(__file__).resolve().parent.parent / "scripts" / "run_combined_pipeline.py"
        assert script.exists()

    def test_script_imports_config(self):
        """Script uses centralized model config."""
        from pathlib import Path
        script = Path(__file__).resolve().parent.parent / "scripts" / "run_combined_pipeline.py"
        content = script.read_text()
        assert "from rhodesli_ml.gemini_config import GEMINI_MODEL" in content
        assert "save_alignment" in content
        assert "batch_id" in content

    def test_script_has_retry_failed_option(self):
        """Script supports --retry-failed for re-processing failed photos."""
        from pathlib import Path
        script = Path(__file__).resolve().parent.parent / "scripts" / "run_combined_pipeline.py"
        content = script.read_text()
        assert "--retry-failed" in content

    def test_script_has_gedcom_option(self):
        """Script supports GEDCOM context toggle."""
        from pathlib import Path
        script = Path(__file__).resolve().parent.parent / "scripts" / "run_combined_pipeline.py"
        content = script.read_text()
        assert "--no-gedcom" in content

    def test_get_failed_photo_ids(self, tmp_path):
        """get_failed_photo_ids extracts failed IDs from result file."""
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

        results = {
            "results": [
                {"photo_id": "p1", "status": "success"},
                {"photo_id": "p2", "status": "error", "reason": "429"},
                {"photo_id": "p3", "status": "error", "reason": "timeout"},
                {"photo_id": "p4", "status": "skipped"},
            ]
        }
        result_file = tmp_path / "batch_result.json"
        import json
        result_file.write_text(json.dumps(results))

        from run_combined_pipeline import get_failed_photo_ids
        failed = get_failed_photo_ids(result_file)
        assert failed == ["p2", "p3"]

    def test_get_failed_photo_ids_missing_file(self, tmp_path):
        """get_failed_photo_ids returns empty list for missing file."""
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

        from run_combined_pipeline import get_failed_photo_ids
        failed = get_failed_photo_ids(tmp_path / "nonexistent.json")
        assert failed == []


class TestRateLimitDetection:
    """Verify rate limit detection in call_gemini_alignment."""

    def test_call_gemini_alignment_has_photo_id_param(self):
        """call_gemini_alignment accepts photo_id for logging."""
        import inspect
        from app.face_alignment import call_gemini_alignment
        sig = inspect.signature(call_gemini_alignment)
        assert "photo_id" in sig.parameters
        assert "batch_id" in sig.parameters
        assert "call_type" in sig.parameters

    def test_run_face_alignment_has_batch_id_param(self):
        """run_face_alignment accepts batch_id for logging."""
        import inspect
        from app.face_alignment import run_face_alignment
        sig = inspect.signature(run_face_alignment)
        assert "batch_id" in sig.parameters
        assert "call_type" in sig.parameters
