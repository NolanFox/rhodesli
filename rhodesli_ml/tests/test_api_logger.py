"""Tests for Gemini API logging infrastructure."""

import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch


class TestApiLogger:
    """Test API call logging."""

    @pytest.fixture(autouse=True)
    def setup_log_dir(self, tmp_path):
        """Redirect log directory to tmp_path for test isolation."""
        self.log_dir = tmp_path / "api_logs"
        self.log_dir.mkdir()
        with patch("rhodesli_ml.utils.api_logger.LOG_DIR", self.log_dir):
            yield

    def test_log_api_call_creates_file(self):
        """Logging an API call writes a JSON file."""
        from rhodesli_ml.utils.api_logger import log_api_call

        with patch("rhodesli_ml.utils.api_logger.LOG_DIR", self.log_dir):
            entry = log_api_call(
                photo_id="test_photo_001",
                model="gemini-2.5-pro-preview-05-06",
                prompt="Analyze this photo",
                response_text='{"estimated_decade": 1940}',
                input_tokens=1000,
                output_tokens=500,
            )

        assert entry["photo_id"] == "test_photo_001"
        assert entry["model"] == "gemini-2.5-pro-preview-05-06"
        assert entry["input_tokens"] == 1000
        assert entry["output_tokens"] == 500
        assert entry["estimated_cost_usd"] > 0

        # Verify file was written
        files = list(self.log_dir.glob("*.json"))
        assert len(files) == 1

        with open(files[0]) as f:
            saved = json.load(f)
        assert saved["photo_id"] == "test_photo_001"

    def test_log_api_call_with_verified_facts(self):
        """Verified facts are stored in the log entry."""
        from rhodesli_ml.utils.api_logger import log_api_call

        facts = {
            "confirmed_identities": ["Albert Cohen", "Eleanore Cohen"],
            "birth_years": {"Albert Cohen": 1905},
        }

        with patch("rhodesli_ml.utils.api_logger.LOG_DIR", self.log_dir):
            entry = log_api_call(
                photo_id="p001",
                model="gemini-2.5-pro-preview-05-06",
                prompt="test",
                response_text="{}",
                verified_facts=facts,
            )

        assert entry["verified_facts"]["confirmed_identities"] == ["Albert Cohen", "Eleanore Cohen"]

    def test_log_api_call_with_previous_result_comparison(self):
        """When previous result provided, comparison is generated."""
        from rhodesli_ml.utils.api_logger import log_api_call

        previous = {"estimated_decade": 1930, "confidence": "medium"}
        new_response = json.dumps({"estimated_decade": 1940, "confidence": "high"})

        with patch("rhodesli_ml.utils.api_logger.LOG_DIR", self.log_dir):
            entry = log_api_call(
                photo_id="p001",
                model="gemini-2.5-pro-preview-05-06",
                prompt="test",
                response_text=new_response,
                previous_result=previous,
            )

        assert entry["comparison"]["has_changes"] is True
        assert entry["comparison"]["decade_changed"]["from"] == 1930
        assert entry["comparison"]["decade_changed"]["to"] == 1940

    def test_cost_calculation(self):
        """Cost is calculated from token counts and model pricing."""
        from rhodesli_ml.utils.api_logger import log_api_call

        with patch("rhodesli_ml.utils.api_logger.LOG_DIR", self.log_dir):
            entry = log_api_call(
                photo_id="p001",
                model="gemini-2.5-pro-preview-05-06",
                prompt="test",
                response_text="{}",
                input_tokens=1_000_000,  # exactly 1M tokens
                output_tokens=0,
            )

        # gemini-2.5-pro-preview-05-06 input = $1.25/1M
        assert entry["estimated_cost_usd"] == pytest.approx(1.25, abs=0.01)

    def test_long_prompt_is_hashed(self):
        """Prompts >5000 chars are truncated with hash prefix."""
        from rhodesli_ml.utils.api_logger import log_api_call

        long_prompt = "x" * 10000

        with patch("rhodesli_ml.utils.api_logger.LOG_DIR", self.log_dir):
            entry = log_api_call(
                photo_id="p001",
                model="gemini-2.5-pro-preview-05-06",
                prompt=long_prompt,
                response_text="{}",
            )

        assert entry["prompt"].startswith("[hash:")
        assert len(entry["prompt"]) < 600  # truncated
        assert entry["prompt_hash"]  # hash always present


class TestLoadLogs:
    """Test log loading and filtering."""

    @pytest.fixture(autouse=True)
    def setup_log_dir(self, tmp_path):
        self.log_dir = tmp_path / "api_logs"
        self.log_dir.mkdir()

    def _write_log(self, photo_id, model, timestamp="2026-01-01T00:00:00"):
        entry = {
            "timestamp": timestamp,
            "photo_id": photo_id,
            "model": model,
            "estimated_cost_usd": 0.01,
            "input_tokens": 100,
            "output_tokens": 50,
        }
        safe_ts = timestamp.replace(":", "-")[:19]
        filepath = self.log_dir / f"{safe_ts}_{photo_id}_{model}.json"
        with open(filepath, "w") as f:
            json.dump(entry, f)

    def test_load_logs_empty_dir(self):
        from rhodesli_ml.utils.api_logger import load_logs
        with patch("rhodesli_ml.utils.api_logger.LOG_DIR", self.log_dir):
            logs = load_logs()
        assert logs == []

    def test_load_logs_returns_entries(self):
        from rhodesli_ml.utils.api_logger import load_logs
        self._write_log("p001", "gemini-pro")
        self._write_log("p002", "gemini-pro")
        with patch("rhodesli_ml.utils.api_logger.LOG_DIR", self.log_dir):
            logs = load_logs()
        assert len(logs) == 2

    def test_load_logs_filter_by_photo(self):
        from rhodesli_ml.utils.api_logger import load_logs
        self._write_log("p001", "gemini-pro", "2026-01-01T00:00:01")
        self._write_log("p002", "gemini-pro", "2026-01-01T00:00:02")
        with patch("rhodesli_ml.utils.api_logger.LOG_DIR", self.log_dir):
            logs = load_logs(photo_id="p001")
        assert len(logs) == 1
        assert logs[0]["photo_id"] == "p001"

    def test_load_logs_filter_by_model(self):
        from rhodesli_ml.utils.api_logger import load_logs
        self._write_log("p001", "model-a", "2026-01-01T00:00:01")
        self._write_log("p001", "model-b", "2026-01-01T00:00:02")
        with patch("rhodesli_ml.utils.api_logger.LOG_DIR", self.log_dir):
            logs = load_logs(model="model-a")
        assert len(logs) == 1
        assert logs[0]["model"] == "model-a"

    def test_load_logs_respects_limit(self):
        from rhodesli_ml.utils.api_logger import load_logs
        for i in range(5):
            self._write_log(f"p{i:03d}", "gemini-pro", f"2026-01-01T00:00:{i:02d}")
        with patch("rhodesli_ml.utils.api_logger.LOG_DIR", self.log_dir):
            logs = load_logs(limit=3)
        assert len(logs) == 3


class TestCostSummary:
    """Test cost summary aggregation."""

    @pytest.fixture(autouse=True)
    def setup_log_dir(self, tmp_path):
        self.log_dir = tmp_path / "api_logs"
        self.log_dir.mkdir()

    def _write_log(self, photo_id, model, cost, timestamp="2026-01-01T00:00:00"):
        entry = {
            "timestamp": timestamp,
            "photo_id": photo_id,
            "model": model,
            "estimated_cost_usd": cost,
            "input_tokens": 100,
            "output_tokens": 50,
        }
        safe_ts = timestamp.replace(":", "-")[:19]
        filepath = self.log_dir / f"{safe_ts}_{photo_id}_{model}.json"
        with open(filepath, "w") as f:
            json.dump(entry, f)

    def test_cost_summary_empty(self):
        from rhodesli_ml.utils.api_logger import get_cost_summary
        with patch("rhodesli_ml.utils.api_logger.LOG_DIR", self.log_dir):
            summary = get_cost_summary()
        assert summary["total_calls"] == 0
        assert summary["total_cost_usd"] == 0

    def test_cost_summary_with_entries(self):
        from rhodesli_ml.utils.api_logger import get_cost_summary
        self._write_log("p001", "model-a", 0.05, "2026-01-01T00:00:01")
        self._write_log("p002", "model-b", 0.10, "2026-01-01T00:00:02")
        with patch("rhodesli_ml.utils.api_logger.LOG_DIR", self.log_dir):
            summary = get_cost_summary()
        assert summary["total_calls"] == 2
        assert summary["total_cost_usd"] == pytest.approx(0.15, abs=0.001)
        assert "model-a" in summary["by_model"]
        assert "model-b" in summary["by_model"]


class TestCompareResults:
    """Test result comparison engine."""

    def test_compare_no_changes(self):
        from rhodesli_ml.utils.api_logger import _compare_results
        prev = {"estimated_decade": 1940, "confidence": "high"}
        new = json.dumps({"estimated_decade": 1940, "confidence": "high"})
        result = _compare_results(prev, new)
        assert result["has_changes"] is False
        assert result["change_count"] == 0

    def test_compare_decade_changed(self):
        from rhodesli_ml.utils.api_logger import _compare_results
        prev = {"estimated_decade": 1930}
        new = json.dumps({"estimated_decade": 1940})
        result = _compare_results(prev, new)
        assert result["has_changes"] is True
        assert result["decade_changed"]["from"] == 1930
        assert result["decade_changed"]["to"] == 1940

    def test_compare_invalid_json(self):
        from rhodesli_ml.utils.api_logger import _compare_results
        result = _compare_results({}, "not json")
        assert "error" in result


class TestGetPreviousResult:
    """Test retrieving previous analysis results."""

    @pytest.fixture(autouse=True)
    def setup_log_dir(self, tmp_path):
        self.log_dir = tmp_path / "api_logs"
        self.log_dir.mkdir()

    def test_no_previous_result(self):
        from rhodesli_ml.utils.api_logger import get_previous_result
        with patch("rhodesli_ml.utils.api_logger.LOG_DIR", self.log_dir):
            result = get_previous_result("nonexistent")
        assert result is None

    def test_previous_result_returned(self):
        from rhodesli_ml.utils.api_logger import get_previous_result
        entry = {
            "timestamp": "2026-01-01T00:00:00",
            "photo_id": "p001",
            "model": "gemini-pro",
            "response": json.dumps({"estimated_decade": 1940}),
        }
        filepath = self.log_dir / "2026-01-01T00-00-00_p001_gemini-pro.json"
        with open(filepath, "w") as f:
            json.dump(entry, f)

        with patch("rhodesli_ml.utils.api_logger.LOG_DIR", self.log_dir):
            result = get_previous_result("p001")
        assert result["estimated_decade"] == 1940
