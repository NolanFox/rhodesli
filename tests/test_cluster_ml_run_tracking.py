"""Tests for ML run tracking in cluster_new_faces.py (PRD-046).

Verifies that clustering creates ml_runs records and writes proposals to ml_proposals.
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest

# Import the functions under test
from scripts.cluster_new_faces import (
    complete_ml_run,
    create_ml_run,
    write_proposals_to_supabase,
)


@pytest.fixture
def mock_sb():
    """Mock Supabase client with insert/update chains."""
    client = MagicMock()
    result = MagicMock()
    result.data = [{"run_id": str(uuid.uuid4())}]
    client.table.return_value.insert.return_value.execute.return_value = result
    client.table.return_value.update.return_value.eq.return_value.execute.return_value = result
    return client


class TestCreateMlRun:
    """Tests for create_ml_run()."""

    def test_creates_run_record(self, mock_sb):
        """create_ml_run inserts a row into ml_runs."""
        run_id = create_ml_run(mock_sb, {"threshold": 1.05, "limit": None, "mode": "dry_run"}, "baseline")
        assert run_id is not None
        mock_sb.table.assert_called_with("ml_runs")
        inserted = mock_sb.table.return_value.insert.call_args[0][0]
        assert inserted["pipeline_type"] == "cluster_new_faces"
        assert inserted["status"] == "running"
        assert inserted["config_json"]["threshold"] == 1.05
        assert inserted["config_json"]["scorer"] == "baseline"

    def test_returns_none_when_sb_is_none(self):
        """Returns None when Supabase client is not available."""
        assert create_ml_run(None, {"threshold": 1.0}, "baseline") is None

    def test_returns_none_on_insert_failure(self, mock_sb):
        """Returns None when Supabase insert fails."""
        mock_sb.table.return_value.insert.return_value.execute.side_effect = Exception("connection error")
        result = create_ml_run(mock_sb, {"threshold": 1.0}, "baseline")
        assert result is None


class TestWriteProposalsToSupabase:
    """Tests for write_proposals_to_supabase()."""

    def test_writes_proposals(self, mock_sb):
        """Writes proposal rows to ml_proposals table."""
        run_id = str(uuid.uuid4())
        suggestions = [
            {
                "source_identity_id": str(uuid.uuid4()),
                "target_identity_id": str(uuid.uuid4()),
                "distance": 0.75,
                "reranker_score": None,
                "face_id": "face1",
            },
            {
                "source_identity_id": str(uuid.uuid4()),
                "target_identity_id": str(uuid.uuid4()),
                "distance": 0.95,
                "reranker_score": None,
                "face_id": "face2",
            },
        ]
        count = write_proposals_to_supabase(mock_sb, run_id, suggestions, "baseline")
        assert count == 2
        mock_sb.table.assert_called_with("ml_proposals")
        inserted = mock_sb.table.return_value.insert.call_args[0][0]
        assert len(inserted) == 2
        # First proposal is tier1 (distance < 0.80)
        assert inserted[0]["tier"] == "tier1"
        assert inserted[0]["status"] == "pending"
        assert inserted[0]["run_id"] == run_id
        # Second proposal is tier2 (0.80 <= distance < 1.05)
        assert inserted[1]["tier"] == "tier2"

    def test_returns_zero_when_sb_none(self):
        """Returns 0 when Supabase client is None."""
        assert write_proposals_to_supabase(None, "run-id", [{"distance": 0.5}], "baseline") == 0

    def test_returns_zero_when_run_id_none(self, mock_sb):
        """Returns 0 when run_id is None."""
        assert write_proposals_to_supabase(mock_sb, None, [{"distance": 0.5}], "baseline") == 0

    def test_returns_zero_on_failure(self, mock_sb):
        """Returns 0 on Supabase insert failure."""
        mock_sb.table.return_value.insert.return_value.execute.side_effect = Exception("fail")
        count = write_proposals_to_supabase(
            mock_sb,
            "run-id",
            [
                {
                    "source_identity_id": "a",
                    "target_identity_id": "b",
                    "distance": 0.5,
                    "reranker_score": None,
                    "face_id": "f1",
                },
            ],
            "baseline",
        )
        assert count == 0

    def test_empty_suggestions(self, mock_sb):
        """Returns 0 for empty suggestion list."""
        assert write_proposals_to_supabase(mock_sb, "run-id", [], "baseline") == 0


class TestCompleteMlRun:
    """Tests for complete_ml_run()."""

    def test_updates_run_with_completion(self, mock_sb):
        """Updates ml_runs with status=completed and result_summary."""
        import time

        run_id = str(uuid.uuid4())
        start = time.time() - 1.5  # 1.5s ago
        summary = {"proposals_created": 10, "tier_breakdown": {"tier1": 3, "tier2": 7}}
        complete_ml_run(mock_sb, run_id, summary, start)
        mock_sb.table.assert_called_with("ml_runs")
        update_call = mock_sb.table.return_value.update
        assert update_call.called
        updated = update_call.call_args[0][0]
        assert updated["status"] == "completed"
        assert updated["result_summary"]["proposals_created"] == 10
        assert updated["duration_ms"] >= 1000  # at least 1 second

    def test_noop_when_sb_none(self):
        """No error when Supabase is None."""
        complete_ml_run(None, "run-id", {}, 0.0)  # should not raise

    def test_noop_when_run_id_none(self, mock_sb):
        """No error when run_id is None."""
        complete_ml_run(mock_sb, None, {}, 0.0)  # should not raise
        mock_sb.table.assert_not_called()
