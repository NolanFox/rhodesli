"""Tests for GEDCOM relationship sync to Supabase.

Tests the sync script that pushes local data/relationships.json
to the Supabase relationships table. All Supabase calls are mocked.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

# Import under test — uses project root path manipulation
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.sync_gedcom_to_supabase import (
    load_local_relationships,
    sync_relationships_to_supabase,
    verify_sync,
    get_supabase_relationship_count,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_relationships():
    """Sample relationships matching the data/relationships.json schema."""
    return [
        {
            "person_a": "ae0b181b-db55-4c3e-853d-0fdc904a1000",
            "person_b": "609d7e34-38a3-4bdd-9879-35560b624bae",
            "type": "spouse",
            "source": "gedcom",
            "gedcom_family_id": "@F427@",
            "created_at": "2026-02-21T05:22:59.938741+00:00",
        },
        {
            "person_a": "@I132127360989@",
            "person_b": "@I132130111756@",
            "type": "parent_child",
            "source": "gedcom",
            "gedcom_family_id": "@F579@",
            "created_at": "2026-02-21T05:22:59.939310+00:00",
        },
        {
            "person_a": "0b9cb708-9b13-4a42-a25d-ad36f3e08547",
            "person_b": "@I132165762036@",
            "type": "parent_child",
            "source": "gedcom",
            "gedcom_family_id": "@F587@",
            "created_at": "2026-02-21T05:22:59.939326+00:00",
        },
    ]


@pytest.fixture
def mock_supabase():
    """Create a mock Supabase client with chainable methods."""
    sb = MagicMock()

    # Mock the table().select().execute() chain for count queries
    count_response = MagicMock()
    count_response.count = 0
    count_response.data = []

    # Mock the table().delete().neq().execute() chain
    delete_response = MagicMock()

    # Mock the table().insert().execute() chain
    insert_response = MagicMock()
    insert_response.data = []

    # Set up chained calls
    table_mock = MagicMock()
    sb.table.return_value = table_mock

    # select chain
    select_mock = MagicMock()
    select_mock.execute.return_value = count_response
    table_mock.select.return_value = select_mock

    # delete chain
    delete_mock = MagicMock()
    neq_mock = MagicMock()
    neq_mock.execute.return_value = delete_response
    delete_mock.neq.return_value = neq_mock
    table_mock.delete.return_value = delete_mock

    # insert chain
    insert_mock = MagicMock()
    insert_mock.execute.return_value = insert_response
    table_mock.insert.return_value = insert_mock

    return sb


# ---------------------------------------------------------------------------
# Tests: load_local_relationships
# ---------------------------------------------------------------------------

class TestLoadLocalRelationships:
    def test_loads_relationships_from_json(self, tmp_path):
        """Load relationships from a valid JSON file."""
        rel_data = {
            "relationships": [
                {"person_a": "uuid1", "person_b": "uuid2", "type": "spouse"},
            ],
            "metadata": {},
        }
        (tmp_path / "relationships.json").write_text(json.dumps(rel_data))

        result = load_local_relationships(tmp_path)
        assert len(result) == 1
        assert result[0]["person_a"] == "uuid1"
        assert result[0]["type"] == "spouse"

    def test_missing_file_raises(self, tmp_path):
        """Missing relationships.json raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_local_relationships(tmp_path)

    def test_empty_relationships(self, tmp_path):
        """Empty relationships list returns empty list."""
        (tmp_path / "relationships.json").write_text(
            json.dumps({"relationships": [], "metadata": {}})
        )
        result = load_local_relationships(tmp_path)
        assert result == []

    def test_mixed_uuid_and_gedcom_ids(self, tmp_path):
        """Relationships can have both UUID and GEDCOM person IDs."""
        rel_data = {
            "relationships": [
                {
                    "person_a": "ae0b181b-db55-4c3e-853d-0fdc904a1000",
                    "person_b": "@I132123770510@",
                    "type": "parent_child",
                    "source": "gedcom",
                },
            ],
        }
        (tmp_path / "relationships.json").write_text(json.dumps(rel_data))

        result = load_local_relationships(tmp_path)
        assert len(result) == 1
        # UUID format
        assert not result[0]["person_a"].startswith("@")
        # GEDCOM format
        assert result[0]["person_b"].startswith("@")


# ---------------------------------------------------------------------------
# Tests: sync_relationships_to_supabase
# ---------------------------------------------------------------------------

class TestSyncRelationships:
    def test_sync_deletes_then_inserts(self, sample_relationships, mock_supabase):
        """Sync deletes existing rows then inserts new ones."""
        stats = sync_relationships_to_supabase(
            mock_supabase, sample_relationships
        )

        assert stats["inserted"] == 3
        assert stats["errors"] == 0
        assert stats["deleted"] is True

        # Verify delete was called
        mock_supabase.table.return_value.delete.assert_called()

        # Verify insert was called
        mock_supabase.table.return_value.insert.assert_called()

    def test_sync_empty_list_only_deletes(self, mock_supabase):
        """Syncing empty list deletes existing but doesn't insert."""
        stats = sync_relationships_to_supabase(mock_supabase, [])

        assert stats["inserted"] == 0
        assert stats["errors"] == 0
        assert stats["deleted"] is True

    def test_sync_builds_correct_rows(self, sample_relationships, mock_supabase):
        """Verify the row format sent to Supabase."""
        sync_relationships_to_supabase(mock_supabase, sample_relationships)

        insert_call = mock_supabase.table.return_value.insert.call_args
        rows = insert_call[0][0]  # First positional arg

        assert len(rows) == 3
        # Check first row
        assert rows[0]["person_a"] == "ae0b181b-db55-4c3e-853d-0fdc904a1000"
        assert rows[0]["person_b"] == "609d7e34-38a3-4bdd-9879-35560b624bae"
        assert rows[0]["relationship_type"] == "spouse"
        assert rows[0]["source"] == "gedcom"
        assert rows[0]["data"] == sample_relationships[0]
        assert rows[0]["updated_at"] == sample_relationships[0]["created_at"]

    def test_sync_batches_large_inserts(self, mock_supabase):
        """Large relationship lists are split into batches."""
        # Create 450 relationships (should be 3 batches with batch_size=200)
        big_list = [
            {
                "person_a": f"uuid-{i}",
                "person_b": f"uuid-{i + 1}",
                "type": "spouse",
                "source": "gedcom",
                "created_at": "2026-01-01T00:00:00+00:00",
            }
            for i in range(450)
        ]

        stats = sync_relationships_to_supabase(
            mock_supabase, big_list, batch_size=200
        )

        assert stats["inserted"] == 450
        assert stats["errors"] == 0

        # Should have been 3 insert calls (200 + 200 + 50)
        insert_calls = mock_supabase.table.return_value.insert.call_args_list
        assert len(insert_calls) == 3
        assert len(insert_calls[0][0][0]) == 200
        assert len(insert_calls[1][0][0]) == 200
        assert len(insert_calls[2][0][0]) == 50

    def test_sync_handles_delete_failure(self, sample_relationships, mock_supabase):
        """If delete fails, sync reports error and skips insert."""
        mock_supabase.table.return_value.delete.return_value.neq.return_value.execute.side_effect = Exception(
            "DB error"
        )

        stats = sync_relationships_to_supabase(
            mock_supabase, sample_relationships
        )

        assert stats["errors"] == 1
        assert stats["inserted"] == 0
        assert "Delete failed" in stats["error_details"][0]

    def test_sync_handles_insert_failure(self, sample_relationships, mock_supabase):
        """If insert fails, sync reports error with partial count."""
        mock_supabase.table.return_value.insert.return_value.execute.side_effect = Exception(
            "Insert error"
        )

        stats = sync_relationships_to_supabase(
            mock_supabase, sample_relationships
        )

        assert stats["errors"] == 1
        assert stats["inserted"] == 0
        assert "Insert batch" in stats["error_details"][0]

    def test_sync_is_idempotent(self, sample_relationships, mock_supabase):
        """Running sync twice produces the same result."""
        stats1 = sync_relationships_to_supabase(
            mock_supabase, sample_relationships
        )
        stats2 = sync_relationships_to_supabase(
            mock_supabase, sample_relationships
        )

        assert stats1["inserted"] == stats2["inserted"]
        assert stats1["errors"] == stats2["errors"]


# ---------------------------------------------------------------------------
# Tests: verify_sync
# ---------------------------------------------------------------------------

class TestVerifySync:
    def test_verify_pass(self, mock_supabase):
        """Verification passes when counts match."""
        mock_supabase.table.return_value.select.return_value.execute.return_value.count = 1019

        result = verify_sync(mock_supabase, 1019)
        assert result["match"] is True
        assert result["expected"] == 1019
        assert result["actual"] == 1019

    def test_verify_fail(self, mock_supabase):
        """Verification fails when counts don't match."""
        mock_supabase.table.return_value.select.return_value.execute.return_value.count = 500

        result = verify_sync(mock_supabase, 1019)
        assert result["match"] is False
        assert result["expected"] == 1019
        assert result["actual"] == 500


# ---------------------------------------------------------------------------
# Tests: get_supabase_relationship_count
# ---------------------------------------------------------------------------

class TestGetCount:
    def test_returns_count(self, mock_supabase):
        """Returns the count from Supabase."""
        mock_supabase.table.return_value.select.return_value.execute.return_value.count = 42

        assert get_supabase_relationship_count(mock_supabase) == 42

    def test_returns_zero_when_none(self, mock_supabase):
        """Returns 0 when count is None."""
        mock_supabase.table.return_value.select.return_value.execute.return_value.count = None

        assert get_supabase_relationship_count(mock_supabase) == 0


# ---------------------------------------------------------------------------
# Tests: Integration with real data file
# ---------------------------------------------------------------------------

class TestWithRealData:
    """Tests that validate against the actual data/relationships.json file."""

    @pytest.fixture
    def real_data_dir(self):
        """Path to the real data directory."""
        data_dir = Path(__file__).resolve().parent.parent / "data"
        if not (data_dir / "relationships.json").exists():
            pytest.skip("data/relationships.json not available")
        return data_dir

    def test_real_data_loads(self, real_data_dir):
        """The actual relationships.json loads successfully."""
        rels = load_local_relationships(real_data_dir)
        assert len(rels) > 0

    def test_real_data_has_expected_structure(self, real_data_dir):
        """Each relationship has required fields."""
        rels = load_local_relationships(real_data_dir)
        for r in rels:
            assert "person_a" in r, f"Missing person_a: {r}"
            assert "person_b" in r, f"Missing person_b: {r}"
            assert "type" in r, f"Missing type: {r}"
            assert r["type"] in ("spouse", "parent_child"), f"Bad type: {r['type']}"

    def test_real_data_has_both_id_formats(self, real_data_dir):
        """Real data contains both UUID and GEDCOM person IDs."""
        rels = load_local_relationships(real_data_dir)
        has_uuid = False
        has_gedcom = False
        for r in rels:
            for key in ("person_a", "person_b"):
                pid = r[key]
                if pid.startswith("@"):
                    has_gedcom = True
                else:
                    has_uuid = True
        assert has_uuid, "Expected some UUID person IDs"
        assert has_gedcom, "Expected some GEDCOM person IDs"

    def test_real_data_count_in_expected_range(self, real_data_dir):
        """Relationship count should be in a reasonable range."""
        rels = load_local_relationships(real_data_dir)
        # As of session 78, we expect ~1019 relationships
        assert 500 <= len(rels) <= 5000, f"Unexpected count: {len(rels)}"

    def test_sync_formats_rows_correctly(self, real_data_dir, mock_supabase):
        """Sync with real data produces valid rows."""
        rels = load_local_relationships(real_data_dir)
        stats = sync_relationships_to_supabase(mock_supabase, rels)

        assert stats["inserted"] == len(rels)
        assert stats["errors"] == 0
