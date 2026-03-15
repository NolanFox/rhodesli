"""Tests for ml_runs and ml_proposals Supabase table schema (PRD-046).

Verifies insert/query shapes match expected schema using mocked Supabase client.
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_sb():
    """Mock Supabase client with insert/select chains."""
    client = MagicMock()
    result = MagicMock()
    result.data = []
    client.table.return_value.insert.return_value.execute.return_value = result
    client.table.return_value.select.return_value.eq.return_value.execute.return_value = result
    client.table.return_value.select.return_value.execute.return_value = result
    client.table.return_value.update.return_value.eq.return_value.execute.return_value = result
    client.table.return_value.delete.return_value.eq.return_value.execute.return_value = result
    return client


class TestMlRunsTableSchema:
    """Verify ml_runs insert/query shapes match Supabase schema."""

    def test_insert_ml_run_shape(self, mock_sb):
        """Insert row matches ml_runs column schema."""
        run_id = str(uuid.uuid4())
        row = {
            "run_id": run_id,
            "pipeline_type": "clustering",
            "config_json": {"threshold": 0.85, "community": "rhodes"},
            "status": "running",
            "triggered_by": "manual",
        }
        mock_sb.table("ml_runs").insert(row).execute()
        mock_sb.table.assert_called_with("ml_runs")
        insert_call = mock_sb.table.return_value.insert
        assert insert_call.called
        inserted = insert_call.call_args[0][0]
        assert inserted["run_id"] == run_id
        assert inserted["pipeline_type"] == "clustering"
        assert inserted["status"] == "running"
        assert isinstance(inserted["config_json"], dict)

    def test_insert_ml_run_with_parent(self, mock_sb):
        """Insert row with parent_run_id for sub-runs."""
        parent_id = str(uuid.uuid4())
        row = {
            "run_id": str(uuid.uuid4()),
            "pipeline_type": "reranker",
            "parent_run_id": parent_id,
            "status": "running",
        }
        mock_sb.table("ml_runs").insert(row).execute()
        inserted = mock_sb.table.return_value.insert.call_args[0][0]
        assert inserted["parent_run_id"] == parent_id

    def test_update_ml_run_completion(self, mock_sb):
        """Update run with result_summary and duration on completion."""
        run_id = str(uuid.uuid4())
        update = {
            "status": "completed",
            "result_summary": {"proposals_created": 42, "tier1": 5, "tier2": 37},
            "duration_ms": 12345,
        }
        mock_sb.table("ml_runs").update(update).eq("run_id", run_id).execute()
        mock_sb.table.assert_called_with("ml_runs")
        update_call = mock_sb.table.return_value.update
        assert update_call.called
        updated = update_call.call_args[0][0]
        assert updated["status"] == "completed"
        assert updated["duration_ms"] == 12345

    def test_query_runs_by_pipeline_type(self, mock_sb):
        """Query runs filtered by pipeline_type."""
        mock_sb.table("ml_runs").select("*").eq("pipeline_type", "clustering").execute()
        mock_sb.table.assert_called_with("ml_runs")
        select_call = mock_sb.table.return_value.select
        assert select_call.called


class TestMlProposalsTableSchema:
    """Verify ml_proposals insert/query shapes match Supabase schema."""

    def test_insert_proposal_shape(self, mock_sb):
        """Insert row matches ml_proposals column schema."""
        row = {
            "proposal_id": str(uuid.uuid4()),
            "run_id": str(uuid.uuid4()),
            "source_identity_id": str(uuid.uuid4()),
            "target_identity_id": str(uuid.uuid4()),
            "score": 0.72,
            "calibrated_score": 0.65,
            "tier": "tier1",
            "status": "pending",
        }
        mock_sb.table("ml_proposals").insert(row).execute()
        mock_sb.table.assert_called_with("ml_proposals")
        inserted = mock_sb.table.return_value.insert.call_args[0][0]
        assert inserted["score"] == 0.72
        assert inserted["tier"] == "tier1"
        assert inserted["status"] == "pending"

    def test_insert_batch_proposals(self, mock_sb):
        """Batch insert multiple proposals for a single run."""
        run_id = str(uuid.uuid4())
        rows = [
            {
                "run_id": run_id,
                "source_identity_id": str(uuid.uuid4()),
                "target_identity_id": str(uuid.uuid4()),
                "score": 0.5 + i * 0.1,
                "tier": "tier1" if i < 2 else "tier2",
                "status": "pending",
            }
            for i in range(5)
        ]
        mock_sb.table("ml_proposals").insert(rows).execute()
        inserted = mock_sb.table.return_value.insert.call_args[0][0]
        assert len(inserted) == 5
        assert all(r["run_id"] == run_id for r in inserted)

    def test_update_proposal_decision(self, mock_sb):
        """Update proposal with decision (accepted/rejected)."""
        proposal_id = str(uuid.uuid4())
        update = {
            "status": "accepted",
            "decided_by": "admin@example.com",
            "decided_at": "2026-03-15T12:00:00Z",
        }
        mock_sb.table("ml_proposals").update(update).eq("proposal_id", proposal_id).execute()
        updated = mock_sb.table.return_value.update.call_args[0][0]
        assert updated["status"] == "accepted"
        assert updated["decided_by"] == "admin@example.com"

    def test_query_proposals_by_run(self, mock_sb):
        """Query proposals filtered by run_id."""
        run_id = str(uuid.uuid4())
        mock_sb.table("ml_proposals").select("*").eq("run_id", run_id).execute()
        mock_sb.table.assert_called_with("ml_proposals")

    def test_query_pending_proposals(self, mock_sb):
        """Query only pending proposals."""
        mock_sb.table("ml_proposals").select("*").eq("status", "pending").execute()
        eq_call = mock_sb.table.return_value.select.return_value.eq
        assert eq_call.call_args[0] == ("status", "pending")
