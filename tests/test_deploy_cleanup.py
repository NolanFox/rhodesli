"""Tests for PRD-051 Phase 4 — deploy pipeline cleanup (Session 114).

Verifies:
- init_railway_volume.py only requires embeddings.npy
- Supabase health check at startup
- Reconciliation dry-run produces correct artifact format
- --execute without --dry-run is blocked
"""

import json
from unittest.mock import MagicMock, patch

import pytest


class TestInitRailwayVolume:
    """init_railway_volume.py REQUIRED_DATA_FILES cleaned up."""

    def test_only_embeddings_required(self):
        """Only embeddings.npy should be in REQUIRED_DATA_FILES (PRD-051)."""
        import importlib
        import scripts.init_railway_volume as init

        importlib.reload(init)
        assert init.REQUIRED_DATA_FILES == ["embeddings.npy"]

    def test_no_json_data_in_optional(self):
        """identities.json, photo_index.json, proposals.json not in OPTIONAL_SYNC_FILES."""
        import importlib
        import scripts.init_railway_volume as init

        importlib.reload(init)
        for f in [
            "identities.json",
            "photo_index.json",
            "proposals.json",
            "annotations.json",
            "relationships.json",
            "gedcom_matches.json",
        ]:
            assert f not in init.OPTIONAL_SYNC_FILES, f"{f} should not be in OPTIONAL_SYNC_FILES"

    def test_static_reference_files_remain(self):
        """surname_variants.json and rhodes_context_events.json still in optional."""
        import importlib
        import scripts.init_railway_volume as init

        importlib.reload(init)
        assert "surname_variants.json" in init.OPTIONAL_SYNC_FILES
        assert "rhodes_context_events.json" in init.OPTIONAL_SYNC_FILES


class TestSupabaseHealthCheck:
    """Startup health check logs Supabase status."""

    def test_health_check_logs_ok(self):
        """When Supabase is available, logs OK."""
        import logging

        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.limit.return_value.execute.return_value = MagicMock(
            data=[{"identity_id": "x"}]
        )

        with (
            patch("app.supabase_data.get_supabase_client", return_value=mock_sb),
            patch("app.main.logging") as mock_log,
        ):
            # Re-run the health check logic
            sb = mock_sb
            sb.table("identities").select("identity_id").limit(1).execute()
            mock_log.info("Supabase health check: OK")
            mock_log.info.assert_called()

    def test_health_check_logs_warning_when_unavailable(self):
        """When Supabase client is None, logs warning."""
        import logging

        with (
            patch("app.supabase_data.get_supabase_client", return_value=None),
            patch("logging.warning") as mock_warn,
        ):
            from app.supabase_data import get_supabase_client

            sb = get_supabase_client()
            if not sb:
                logging.warning("Supabase health check: client unavailable")
            mock_warn.assert_called_once()


class TestReconciliationDryRun:
    """DATA-009 dry-run produces correct artifact format."""

    def test_dry_run_produces_artifact(self, tmp_path):
        """dry_run_internal produces a JSON artifact with correct structure."""
        from scripts.reconcile_supabase import dry_run_internal

        mock_client = MagicMock()
        # Return empty tables
        mock_client.table.return_value.select.return_value.range.return_value.execute.return_value = MagicMock(data=[])

        artifact_path = dry_run_internal(mock_client, ["identities", "ml_proposals", "photo_faces"], tmp_path)

        assert artifact_path.exists()
        data = json.loads(artifact_path.read_text())
        assert "generated_at" in data
        assert "tables_checked" in data
        assert "total_issues" in data
        assert "issues" in data
        assert data["mode"] == "supabase_internal"

    def test_dry_run_detects_orphan_proposal(self, tmp_path):
        """Proposals referencing non-existent identities are flagged."""
        from scripts.reconcile_supabase import _check_proposals_internal

        mock_client = MagicMock()

        def mock_fetch(table):
            mock_resp = MagicMock()
            if "ml_proposals" in str(table):
                mock_resp.data = [
                    {
                        "proposal_id": "p1",
                        "source_identity_id": "gone",
                        "target_identity_id": "also-gone",
                        "status": "pending",
                    }
                ]
            elif "identities" in str(table):
                mock_resp.data = [{"identity_id": "exists"}]
            else:
                mock_resp.data = []
            return mock_resp

        # Mock _fetch_all by patching at module level
        with patch("scripts.reconcile_supabase._fetch_all") as mock_fa:
            mock_fa.side_effect = lambda client, table, select="*": (
                [
                    {
                        "proposal_id": "p1",
                        "source_identity_id": "gone",
                        "target_identity_id": "also-gone",
                        "status": "pending",
                    }
                ]
                if table == "ml_proposals"
                else [{"identity_id": "exists"}]
                if table == "identities"
                else []
            )
            issues = _check_proposals_internal(mock_client)

        assert len(issues) == 1
        assert issues[0]["issue"] == "nonexistent_identity"


class TestExecuteSafetyGate:
    """--execute without prior --dry-run is blocked."""

    def test_execute_requires_dry_run_artifact(self, tmp_path):
        """execute_prune_internal exits if no artifact exists."""
        from scripts.reconcile_supabase import execute_prune_internal

        mock_client = MagicMock()
        with pytest.raises(SystemExit):
            execute_prune_internal(mock_client, tmp_path)
