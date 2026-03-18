"""Tests for proposals Supabase read path (PRD-051 Phase 2A, Session 114).

Verifies:
- _load_proposals() reads from Supabase when DATA_SOURCE=postgres
- TTL cache works (second call within 120s doesn't hit Supabase)
- Cache invalidation works (after recluster, cache is cleared)
- Fallback to JSON works when DATA_SOURCE=json
- invalidate_proposals_cache() clears all caches
"""

import json
import time
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _reset_proposals_cache():
    """Reset proposals cache before each test."""
    import app.main as main

    main._proposals_cache = None
    main._proposals_cache_ts = 0.0
    main._proposal_target_counts_cache = None
    yield
    main._proposals_cache = None
    main._proposals_cache_ts = 0.0
    main._proposal_target_counts_cache = None


class TestProposalsSupabaseRead:
    """Proposals read from Supabase when DATA_SOURCE=postgres."""

    def test_load_proposals_from_supabase(self):
        """_load_proposals reads from ml_proposals table."""
        import app.main as main

        mock_sb = MagicMock()
        mock_resp = MagicMock()
        mock_resp.data = [
            {
                "source_identity_id": "id-aaa",
                "target_identity_id": "id-bbb",
                "score": 0.85,
                "tier": "tier1",
                "status": "pending",
                "run_id": "run-1",
                "created_at": "2026-03-17T00:00:00Z",
            }
        ]
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_resp

        with (
            patch.object(main, "DATA_SOURCE", "postgres"),
            patch("app.supabase_data.get_supabase_client", return_value=mock_sb),
        ):
            result = main._load_proposals()

        assert len(result["proposals"]) == 1
        p = result["proposals"][0]
        assert p["source_identity_id"] == "id-aaa"
        assert p["target_identity_id"] == "id-bbb"
        assert p["distance"] == 0.85
        assert p["confidence_tier"] == "tier1"
        assert p["match_type"] == "clustering"
        assert result["generated_at"] == "2026-03-17T00:00:00Z"

    def test_load_proposals_empty_supabase(self):
        """Empty ml_proposals returns empty structure."""
        import app.main as main

        mock_sb = MagicMock()
        mock_resp = MagicMock()
        mock_resp.data = []
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_resp

        with (
            patch.object(main, "DATA_SOURCE", "postgres"),
            patch("app.supabase_data.get_supabase_client", return_value=mock_sb),
        ):
            result = main._load_proposals()

        assert result["proposals"] == []
        assert result["generated_at"] == ""

    def test_load_proposals_supabase_unavailable(self):
        """When Supabase client is None, returns empty proposals."""
        import app.main as main

        with (
            patch.object(main, "DATA_SOURCE", "postgres"),
            patch("app.supabase_data.get_supabase_client", return_value=None),
        ):
            result = main._load_proposals()

        assert result["proposals"] == []

    def test_load_proposals_supabase_error_falls_through_to_json(self, tmp_path):
        """When Supabase throws, falls back to JSON."""
        import app.main as main

        proposals_json = {
            "proposals": [{"source_identity_id": "json-id", "target_identity_id": "json-tgt", "distance": 0.9}],
            "generated_at": "2026-01-01",
        }
        json_path = tmp_path / "proposals.json"
        json_path.write_text(json.dumps(proposals_json))

        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.side_effect = Exception("timeout")

        with (
            patch.object(main, "DATA_SOURCE", "postgres"),
            patch.object(main, "data_path", tmp_path),
            patch("app.supabase_data.get_supabase_client", return_value=mock_sb),
        ):
            result = main._load_proposals()

        assert len(result["proposals"]) == 1
        assert result["proposals"][0]["source_identity_id"] == "json-id"


class TestProposalsTTLCache:
    """TTL cache prevents repeated Supabase hits."""

    def test_second_call_uses_cache(self):
        """Second call within TTL returns cached data without hitting Supabase."""
        import app.main as main

        mock_sb = MagicMock()
        mock_resp = MagicMock()
        mock_resp.data = [
            {
                "source_identity_id": "id-1",
                "target_identity_id": "id-2",
                "score": 0.5,
                "tier": "tier1",
                "status": "pending",
                "run_id": "r1",
                "created_at": "2026-03-17T00:00:00Z",
            }
        ]
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_resp

        with (
            patch.object(main, "DATA_SOURCE", "postgres"),
            patch("app.supabase_data.get_supabase_client", return_value=mock_sb),
        ):
            result1 = main._load_proposals()
            result2 = main._load_proposals()

        # Should only call Supabase once
        assert mock_sb.table.call_count == 1
        assert result1 is result2

    def test_cache_expires_after_ttl(self):
        """After TTL expires, Supabase is queried again."""
        import app.main as main

        mock_sb = MagicMock()
        mock_resp = MagicMock()
        mock_resp.data = []
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_resp

        with (
            patch.object(main, "DATA_SOURCE", "postgres"),
            patch.object(main, "_PROPOSALS_CACHE_TTL", 0.01),
            patch("app.supabase_data.get_supabase_client", return_value=mock_sb),
        ):
            main._load_proposals()
            time.sleep(0.02)
            main._load_proposals()

        assert mock_sb.table.call_count == 2


class TestProposalsCacheInvalidation:
    """invalidate_proposals_cache() clears the cache."""

    def test_invalidate_clears_cache(self):
        """After invalidation, next call hits Supabase again."""
        import app.main as main

        mock_sb = MagicMock()
        mock_resp = MagicMock()
        mock_resp.data = []
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_resp

        with (
            patch.object(main, "DATA_SOURCE", "postgres"),
            patch("app.supabase_data.get_supabase_client", return_value=mock_sb),
        ):
            main._load_proposals()
            assert mock_sb.table.call_count == 1

            main.invalidate_proposals_cache()
            main._load_proposals()
            assert mock_sb.table.call_count == 2


class TestProposalsJSONFallback:
    """JSON mode works when DATA_SOURCE=json."""

    def test_load_from_json(self, tmp_path):
        """_load_proposals reads from JSON when DATA_SOURCE=json."""
        import app.main as main

        proposals_json = {
            "proposals": [{"source_identity_id": "s1", "target_identity_id": "t1", "distance": 0.7}],
            "generated_at": "2026-03-01",
        }
        json_path = tmp_path / "proposals.json"
        json_path.write_text(json.dumps(proposals_json))

        with patch.object(main, "DATA_SOURCE", "json"), patch.object(main, "data_path", tmp_path):
            result = main._load_proposals()

        assert len(result["proposals"]) == 1
        assert result["proposals"][0]["distance"] == 0.7

    def test_load_json_missing_file(self, tmp_path):
        """Missing proposals.json returns empty structure."""
        import app.main as main

        with patch.object(main, "DATA_SOURCE", "json"), patch.object(main, "data_path", tmp_path):
            result = main._load_proposals()

        assert result["proposals"] == []
        assert result["generated_at"] == ""


class TestClusterReviewUsesUnifiedReader:
    """cluster_review_routes._load_proposals() delegates to main."""

    def test_delegates_to_main(self):
        """cluster_review_routes._load_proposals() calls main._load_proposals()."""
        import app.cluster_review_routes as cr
        import app.main as main

        test_data = {"proposals": [{"source_identity_id": "x"}], "generated_at": "now"}
        with patch.object(main, "_load_proposals", return_value=test_data) as mock_load:
            result = cr._load_proposals()

        mock_load.assert_called_once()
        assert result == [{"source_identity_id": "x"}]
