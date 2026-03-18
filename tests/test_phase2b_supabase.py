"""Tests for PRD-051 Phase 2B — annotations, relationships, GEDCOM matches Supabase reads.

Session 114.
"""

import json
import time
from unittest.mock import MagicMock, patch

import pytest


# ============================================================================
# Annotations TTL Cache
# ============================================================================


class TestAnnotationsTTLCache:
    """Annotations load from Supabase with TTL cache."""

    @pytest.fixture(autouse=True)
    def _reset(self):
        import app.engagement_routes as er

        er._annotations_cache = None
        er._annotations_cache_ts = 0.0
        yield
        er._annotations_cache = None
        er._annotations_cache_ts = 0.0

    def test_annotations_from_supabase(self):
        """Annotations load from Supabase when DATA_SOURCE=postgres."""
        import app.engagement_routes as er
        import app.main as main

        mock_result = {"schema_version": 1, "annotations": {"a1": {"text": "hello"}}}

        with (
            patch.object(main, "DATA_SOURCE", "postgres"),
            patch("app.supabase_data.load_annotations_from_supabase", return_value=mock_result),
        ):
            result = er._load_annotations()

        assert result["annotations"]["a1"]["text"] == "hello"

    def test_annotations_ttl_cache(self):
        """Second call within TTL uses cache."""
        import app.engagement_routes as er
        import app.main as main

        mock_result = {"schema_version": 1, "annotations": {"a1": {}}}
        mock_fn = MagicMock(return_value=mock_result)

        with (
            patch.object(main, "DATA_SOURCE", "postgres"),
            patch("app.supabase_data.load_annotations_from_supabase", mock_fn),
        ):
            er._load_annotations()
            er._load_annotations()

        assert mock_fn.call_count == 1

    def test_annotations_invalidation(self):
        """Cache invalidation forces fresh Supabase load."""
        import app.engagement_routes as er
        import app.main as main

        mock_result = {"schema_version": 1, "annotations": {}}
        mock_fn = MagicMock(return_value=mock_result)

        with (
            patch.object(main, "DATA_SOURCE", "postgres"),
            patch("app.supabase_data.load_annotations_from_supabase", mock_fn),
        ):
            er._load_annotations()
            er._invalidate_annotations_cache()
            er._load_annotations()

        assert mock_fn.call_count == 2

    def test_annotations_json_fallback(self, tmp_path):
        """Annotations load from JSON when DATA_SOURCE=json."""
        import app.engagement_routes as er
        import app.main as main

        ann_data = {"schema_version": 1, "annotations": {"a1": {"text": "json"}}}
        (tmp_path / "annotations.json").write_text(json.dumps(ann_data))

        with patch.object(main, "DATA_SOURCE", "json"), patch.object(main, "data_path", tmp_path):
            result = er._load_annotations()

        assert result["annotations"]["a1"]["text"] == "json"


# ============================================================================
# Relationships TTL Cache
# ============================================================================


class TestRelationshipsTTLCache:
    """Relationships load from Supabase with TTL cache."""

    @pytest.fixture(autouse=True)
    def _reset(self):
        import app.relationship_routes as rr

        rr._relationship_graph_cache = None
        rr._relationship_graph_cache_ts = 0.0
        yield
        rr._relationship_graph_cache = None
        rr._relationship_graph_cache_ts = 0.0

    def test_relationships_from_supabase(self):
        """Relationships load from Supabase when DATA_SOURCE=postgres."""
        import app.relationship_routes as rr
        import app.main as main

        mock_sb = MagicMock()
        mock_resp = MagicMock()
        mock_resp.data = [
            {"data": {"person_a": "id1", "person_b": "id2", "type": "parent_child"}},
            {"data": {"person_a": "id3", "person_b": "id4", "type": "spouse"}},
        ]
        mock_sb.table.return_value.select.return_value.execute.return_value = mock_resp

        with (
            patch.object(main, "DATA_SOURCE", "postgres"),
            patch("app.supabase_data.get_supabase_client", return_value=mock_sb),
        ):
            result = rr._load_relationship_graph()

        assert len(result["relationships"]) == 2
        assert result["relationships"][0]["person_a"] == "id1"

    def test_relationships_ttl_cache(self):
        """Second call within TTL uses cache."""
        import app.relationship_routes as rr
        import app.main as main

        mock_sb = MagicMock()
        mock_resp = MagicMock()
        mock_resp.data = []
        mock_sb.table.return_value.select.return_value.execute.return_value = mock_resp

        with (
            patch.object(main, "DATA_SOURCE", "postgres"),
            patch("app.supabase_data.get_supabase_client", return_value=mock_sb),
        ):
            rr._load_relationship_graph()
            rr._load_relationship_graph()

        assert mock_sb.table.call_count == 1

    def test_relationships_invalidation(self):
        """Cache invalidation forces fresh load."""
        import app.relationship_routes as rr
        import app.main as main

        mock_sb = MagicMock()
        mock_resp = MagicMock()
        mock_resp.data = []
        mock_sb.table.return_value.select.return_value.execute.return_value = mock_resp

        with (
            patch.object(main, "DATA_SOURCE", "postgres"),
            patch("app.supabase_data.get_supabase_client", return_value=mock_sb),
        ):
            rr._load_relationship_graph()
            rr.invalidate_relationship_cache()
            rr._load_relationship_graph()

        assert mock_sb.table.call_count == 2

    def test_relationships_json_fallback(self, tmp_path):
        """Relationships load from JSON when DATA_SOURCE=json."""
        import app.relationship_routes as rr
        import app.main as main

        rel_data = {"schema_version": 1, "relationships": [{"person_a": "a", "person_b": "b", "type": "spouse"}]}
        (tmp_path / "relationships.json").write_text(json.dumps(rel_data))

        with patch.object(main, "DATA_SOURCE", "json"), patch.object(main, "data_path", tmp_path):
            result = rr._load_relationship_graph()

        assert len(result["relationships"]) == 1


# ============================================================================
# GEDCOM Matches TTL Cache
# ============================================================================


class TestGedcomMatchesTTLCache:
    """GEDCOM matches load from Supabase with TTL cache."""

    @pytest.fixture(autouse=True)
    def _reset(self):
        import app.relationship_routes as rr

        rr._gedcom_matches_cache = None
        rr._gedcom_matches_cache_ts = 0.0
        yield
        rr._gedcom_matches_cache = None
        rr._gedcom_matches_cache_ts = 0.0

    def test_gedcom_matches_from_supabase(self):
        """GEDCOM matches load from Supabase when DATA_SOURCE=postgres."""
        import app.relationship_routes as rr
        import app.main as main

        mock_sb = MagicMock()
        mock_resp = MagicMock()
        mock_resp.data = [
            {"data": {"gedcom_xref": "@I1@", "identity_id": "uuid-1", "status": "confirmed"}},
        ]
        mock_sb.table.return_value.select.return_value.execute.return_value = mock_resp

        with (
            patch.object(main, "DATA_SOURCE", "postgres"),
            patch("app.supabase_data.get_supabase_client", return_value=mock_sb),
        ):
            result = rr._load_gedcom_matches()

        assert len(result["matches"]) == 1
        assert result["matches"][0]["gedcom_xref"] == "@I1@"

    def test_gedcom_matches_ttl_cache(self):
        """Second call within TTL uses cache."""
        import app.relationship_routes as rr
        import app.main as main

        mock_sb = MagicMock()
        mock_resp = MagicMock()
        mock_resp.data = []
        mock_sb.table.return_value.select.return_value.execute.return_value = mock_resp

        with (
            patch.object(main, "DATA_SOURCE", "postgres"),
            patch("app.supabase_data.get_supabase_client", return_value=mock_sb),
        ):
            rr._load_gedcom_matches()
            rr._load_gedcom_matches()

        assert mock_sb.table.call_count == 1

    def test_gedcom_matches_invalidation(self):
        """Cache invalidation forces fresh load."""
        import app.relationship_routes as rr
        import app.main as main

        mock_sb = MagicMock()
        mock_resp = MagicMock()
        mock_resp.data = []
        mock_sb.table.return_value.select.return_value.execute.return_value = mock_resp

        with (
            patch.object(main, "DATA_SOURCE", "postgres"),
            patch("app.supabase_data.get_supabase_client", return_value=mock_sb),
        ):
            rr._load_gedcom_matches()
            rr.invalidate_gedcom_matches_cache()
            rr._load_gedcom_matches()

        assert mock_sb.table.call_count == 2

    def test_gedcom_matches_json_fallback(self, tmp_path):
        """GEDCOM matches load from JSON when DATA_SOURCE=json."""
        import app.relationship_routes as rr
        import app.main as main

        gm_data = {"schema_version": 1, "matches": [{"gedcom_xref": "@I1@", "identity_id": "uuid-1"}]}
        (tmp_path / "gedcom_matches.json").write_text(json.dumps(gm_data))

        with patch.object(main, "DATA_SOURCE", "json"), patch.object(main, "data_path", tmp_path):
            result = rr._load_gedcom_matches()

        assert len(result["matches"]) == 1
