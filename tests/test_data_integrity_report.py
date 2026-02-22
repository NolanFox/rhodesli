"""Tests for data_integrity_report.py script (Session 61, ACT 4)."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch


class TestDataIntegrityReport:
    """Tests for scripts/data_integrity_report.py."""

    def test_count_json_entries_runs(self, tmp_path):
        """count_json_entries() counts correctly from test data."""
        import scripts.data_integrity_report as dir_mod

        (tmp_path / "identities.json").write_text(json.dumps({
            "identities": {
                "id1": {"state": "CONFIRMED", "name": "Test Person"},
                "id2": {"state": "PROPOSED", "name": "Proposed"},
                "id3": {"state": "INBOX", "name": "Inbox Person"},
                "id4": {"state": "CONFIRMED", "name": "Merged", "merged_into": "id1"},
            }
        }))
        (tmp_path / "photo_index.json").write_text(json.dumps({
            "photos": {"p1": {}, "p2": {}},
            "face_to_photo": {"f1": "p1", "f2": "p2"},
        }))
        (tmp_path / "annotations.json").write_text(json.dumps({
            "annotations": [{"id": 1}, {"id": 2}],
        }))
        (tmp_path / "date_labels.json").write_text(json.dumps({
            "photo1": {"estimated_decade": 1940},
        }))

        with patch.object(dir_mod, "DATA_DIR", tmp_path):
            result = dir_mod.count_json_entries()
            assert result["identities.json"]["total"] == 4
            assert result["identities.json"]["confirmed"] == 2
            assert result["identities.json"]["merged"] == 1
            assert result["photo_index.json"]["total_photos"] == 2
            assert result["annotations.json"]["total"] == 2
            assert result["date_labels.json"]["total"] == 1

    def test_check_gemini_logs_empty(self, tmp_path):
        """check_gemini_logs() handles missing directory."""
        import scripts.data_integrity_report as dir_mod

        with patch.object(dir_mod, "ML_DATA_DIR", tmp_path):
            result = dir_mod.check_gemini_logs()
            assert result["count"] == 0

    def test_check_gemini_logs_with_data(self, tmp_path):
        """check_gemini_logs() counts log files."""
        import scripts.data_integrity_report as dir_mod

        log_dir = tmp_path / "api_logs"
        log_dir.mkdir()
        (log_dir / "test_log.json").write_text(json.dumps({
            "model": "gemini-3.1-pro-preview",
            "estimated_cost_usd": 0.01,
        }))

        with patch.object(dir_mod, "ML_DATA_DIR", tmp_path):
            result = dir_mod.check_gemini_logs()
            assert result["count"] == 1
            assert "gemini-3.1-pro-preview" in result["models_used"]

    def test_check_upload_records_no_file(self, tmp_path):
        """check_upload_records() handles missing file."""
        import scripts.data_integrity_report as dir_mod

        with patch.object(dir_mod, "DATA_DIR", tmp_path):
            result = dir_mod.check_upload_records()
            assert result["count"] == 0

    def test_cross_check_json_only(self, tmp_path):
        """cross_check_identities() works without Supabase."""
        import scripts.data_integrity_report as dir_mod

        (tmp_path / "identities.json").write_text(json.dumps({
            "identities": {
                "id1": {"state": "CONFIRMED", "name": "Test"},
                "id2": {"state": "INBOX", "name": "Inbox"},
            }
        }))

        with patch.object(dir_mod, "DATA_DIR", tmp_path):
            result = dir_mod.cross_check_identities()
            assert result["json_confirmed_count"] == 1
