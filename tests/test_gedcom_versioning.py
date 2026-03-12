"""Tests for GEDCOM temporal versioning (AD-163).

Tests the import_gedcom_version module: version tracking, diff detection,
change logging, duplicate detection, and re-enrichment queue.
"""

import hashlib
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# We need to be able to import from scripts/
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import scripts.import_gedcom_version as import_mod
from rhodesli_ml.importers.gedcom_snapshot import build_snapshot_bundle
from scripts.import_gedcom_version import (
    INDIVIDUAL_COMPARE_FIELDS,
    build_individual_row,
    check_duplicate_hash,
    diff_individual,
    get_next_version_number,
    hash_file,
    import_versioned,
)


# --- Fixtures ---

def make_individual(full_name="John Doe", given_name="John", surname="Doe",
                    gender="M", birth_raw=None, birth_place=None,
                    death_raw=None, death_place=None, events=None):
    """Create a mock parsed GEDCOM individual."""
    birth = SimpleNamespace(raw_date=birth_raw, date=None, place=birth_place) if birth_raw else None
    death = SimpleNamespace(raw_date=death_raw, date=None, place=death_place) if death_raw else None
    return SimpleNamespace(
        full_name=full_name,
        given_name=given_name,
        surname=surname,
        gender=gender,
        birth=birth,
        birth_place=birth_place,
        death=death,
        death_place=death_place,
        events=events or [],
    )


def make_parsed(*individuals_dict):
    """Create a mock ParsedGedcom with individuals.

    Args:
        individuals_dict: list of (xref_id, individual) tuples
    """
    indis = dict(individuals_dict)
    return SimpleNamespace(
        individuals=indis,
        families={},
        individual_count=len(indis),
        family_count=0,
    )


class MockSupabaseQuery:
    """A chainable query builder that records operations and returns data on execute()."""

    def __init__(self, table, data=None, pending_result=None):
        self._table = table
        self._data = data if data is not None else table._data
        self._filters = []
        self._order_col = None
        self._order_desc = False
        self._limit_val = None
        self._range_start = None
        self._range_end = None
        self._pending_result = pending_result  # For insert/update that have pre-set results

    def select(self, cols):
        return self

    def eq(self, col, val):
        self._filters.append(('eq', col, val))
        return self

    def neq(self, col, val):
        return self

    def in_(self, col, values):
        self._filters.append(('in', col, tuple(values)))
        return self

    def or_(self, expr):
        return self

    def order(self, col, desc=False):
        self._order_col = col
        self._order_desc = desc
        return self

    def limit(self, n):
        self._limit_val = n
        return self

    def range(self, start, end):
        self._range_start = start
        self._range_end = end
        return self

    def execute(self):
        if self._pending_result is not None:
            return SimpleNamespace(data=self._pending_result)
        data = list(self._data)
        for op, col, val in self._filters:
            if op == 'eq':
                data = [r for r in data if r.get(col) == val]
            elif op == 'in':
                data = [r for r in data if r.get(col) in val]
        if self._order_col:
            data = sorted(data, key=lambda r: r.get(self._order_col, 0),
                          reverse=self._order_desc)
        if self._limit_val:
            data = data[:self._limit_val]
        if self._range_start is not None:
            data = data[self._range_start:self._range_end + 1]
        return SimpleNamespace(data=data)


class MockSupabaseTable:
    """Mock Supabase table operations for testing."""

    def __init__(self, data=None):
        self._data = data or []
        self._insert_calls = []
        self._update_calls = []
        self._uuid_counter = 0

    def select(self, cols):
        return MockSupabaseQuery(self)

    def insert(self, rows):
        rows_list = rows if isinstance(rows, list) else [rows]
        result_data = []
        for row in rows_list:
            self._uuid_counter += 1
            enriched = {**row, 'id': f'mock-uuid-{self._uuid_counter}'}
            result_data.append(enriched)
            self._insert_calls.append(enriched)
        return MockSupabaseQuery(self, pending_result=result_data)

    def update(self, data):
        self._update_calls.append(data)
        return MockSupabaseQuery(self)

    def delete(self):
        return MockSupabaseQuery(self)

    def upsert(self, rows, on_conflict=None):
        return self.insert(rows)


class MockSupabase:
    """Mock Supabase client with configurable table data."""

    def __init__(self, tables=None):
        self._tables = tables or {}

    def table(self, name):
        if name not in self._tables:
            self._tables[name] = MockSupabaseTable()
        return self._tables[name]


# --- Tests ---

class TestDiffIndividual:
    """Test field-level diff detection between GEDCOM individuals."""

    def test_no_changes(self):
        old = {'name': 'John Doe', 'given_name': 'John', 'surname': 'Doe',
               'gender': 'M', 'birth_date': '1920', 'birth_place': 'Rhodes',
               'death_date': '1990', 'death_place': 'New York'}
        new = dict(old)
        assert diff_individual(old, new) == []

    def test_name_changed(self):
        old = {'name': 'John Doe', 'given_name': 'John', 'surname': 'Doe',
               'gender': 'M', 'birth_date': None, 'birth_place': None,
               'death_date': None, 'death_place': None}
        new = dict(old, name='Jonathan Doe', given_name='Jonathan')
        changes = diff_individual(old, new)
        assert len(changes) == 2
        fields_changed = {c['field_name'] for c in changes}
        assert fields_changed == {'name', 'given_name'}

    def test_birth_date_added(self):
        old = {'name': 'John', 'given_name': 'John', 'surname': 'Doe',
               'gender': 'M', 'birth_date': None, 'birth_place': None,
               'death_date': None, 'death_place': None}
        new = dict(old, birth_date='ABT 1920')
        changes = diff_individual(old, new)
        assert len(changes) == 1
        assert changes[0]['field_name'] == 'birth_date'
        assert changes[0]['old_value'] is None
        assert changes[0]['new_value'] == 'ABT 1920'

    def test_whitespace_ignored(self):
        old = {'name': 'John Doe ', 'given_name': 'John', 'surname': 'Doe',
               'gender': 'M', 'birth_date': None, 'birth_place': None,
               'death_date': None, 'death_place': None}
        new = dict(old, name='John Doe')
        assert diff_individual(old, new) == []


class TestBuildIndividualRow:
    """Test building a database row from a parsed individual."""

    def test_basic(self):
        indi = make_individual("Sol Capeluto", "Sol", "Capeluto", "M",
                               birth_raw="1905", birth_place="Rhodes")
        row = build_individual_row("I001", indi, "Family.ged")
        assert row['gedcom_id'] == 'I001'
        assert row['name'] == 'Sol Capeluto'
        assert row['birth_date'] == '1905'
        assert row['source_file'] == 'Family.ged'

    def test_no_dates(self):
        indi = make_individual("Unknown Person")
        row = build_individual_row("I999", indi, "test.ged")
        assert row['birth_date'] is None
        assert row['death_date'] is None


class TestGetNextVersionNumber:
    """Test version number auto-increment."""

    def test_first_version(self):
        sb = MockSupabase({'gedcom_versions': MockSupabaseTable([])})
        assert get_next_version_number(sb, 'rhodesli') == 1

    def test_increment(self):
        sb = MockSupabase({'gedcom_versions': MockSupabaseTable([
            {'version_number': 1, 'community_id': 'rhodesli'},
            {'version_number': 2, 'community_id': 'rhodesli'},
        ])})
        assert get_next_version_number(sb, 'rhodesli') == 3


class TestCheckDuplicateHash:
    """Test duplicate file detection."""

    def test_no_duplicate(self):
        sb = MockSupabase({'gedcom_versions': MockSupabaseTable([])})
        assert check_duplicate_hash(sb, 'abc123', 'rhodesli') is None

    def test_duplicate_found(self):
        sb = MockSupabase({'gedcom_versions': MockSupabaseTable([
            {'source_hash': 'abc123', 'community_id': 'rhodesli',
             'version_number': 1, 'imported_at': '2026-01-01'},
        ])})
        result = check_duplicate_hash(sb, 'abc123', 'rhodesli')
        assert result is not None
        assert result['version_number'] == 1

    def test_failed_duplicate_does_not_block_retry(self):
        sb = MockSupabase({'gedcom_versions': MockSupabaseTable([
            {
                'source_hash': 'abc123',
                'community_id': 'rhodesli',
                'version_number': 1,
                'imported_at': '2026-01-01',
                'status': 'failed',
            },
        ])})
        assert check_duplicate_hash(sb, 'abc123', 'rhodesli') is None

    def test_failed_versions_do_not_count_as_existing_history(self):
        sb = MockSupabase({'gedcom_versions': MockSupabaseTable([
            {
                'id': 'failed-version',
                'community_id': 'rhodesli',
                'status': 'failed',
            },
        ])})
        assert import_mod._versions_exist(sb, 'rhodesli') is False


class TestHashFile:
    """Test file hashing."""

    def test_hash_consistency(self, tmp_path):
        f = tmp_path / "test.ged"
        f.write_text("0 HEAD\n1 SOUR Test\n0 TRLR\n")
        h1 = hash_file(f)
        h2 = hash_file(f)
        assert h1 == h2
        assert len(h1) == 64  # SHA256 hex

    def test_different_files_different_hash(self, tmp_path):
        f1 = tmp_path / "a.ged"
        f2 = tmp_path / "b.ged"
        f1.write_text("file A content")
        f2.write_text("file B content")
        assert hash_file(f1) != hash_file(f2)


class TestImportVersioned:
    """Test the full versioned import flow."""

    def test_dry_run_all_new(self):
        """Importing into empty database = all added."""
        sb = MockSupabase({
            'gedcom_versions': MockSupabaseTable([]),
            'gedcom_individuals': MockSupabaseTable([]),
        })
        parsed = make_parsed(
            ('I001', make_individual("Sol Capeluto", "Sol", "Capeluto")),
            ('I002', make_individual("Rachel Capeluto", "Rachel", "Capeluto")),
        )
        result = import_versioned(sb, parsed, 'test.ged', 'hash123', dry_run=True)
        assert result['dry_run'] is True
        assert result['added'] == 2
        assert result['modified'] == 0
        assert result['removed'] == 0

    def test_dry_run_with_modifications(self):
        """Detect modifications when re-importing."""
        sb = MockSupabase({
            'gedcom_versions': MockSupabaseTable([]),
            'gedcom_individuals': MockSupabaseTable([
                {'id': 'uuid-1', 'gedcom_id': 'I001', 'name': 'Sol Capeluto',
                 'given_name': 'Sol', 'surname': 'Capeluto', 'gender': 'M',
                 'birth_date': None, 'birth_place': None,
                 'death_date': None, 'death_place': None,
                 'is_current': True},
            ]),
        })
        # Same person but with a birth date added
        parsed = make_parsed(
            ('I001', make_individual("Sol Capeluto", "Sol", "Capeluto", "M",
                                     birth_raw="1905", birth_place="Rhodes")),
        )
        result = import_versioned(sb, parsed, 'test.ged', 'hash456', dry_run=True)
        assert result['modified'] == 1
        assert result['added'] == 0
        assert result['unchanged'] == 0

    def test_dry_run_with_removal(self):
        """Detect removed individuals."""
        sb = MockSupabase({
            'gedcom_versions': MockSupabaseTable([]),
            'gedcom_individuals': MockSupabaseTable([
                {'id': 'uuid-1', 'gedcom_id': 'I001', 'name': 'Sol',
                 'given_name': 'Sol', 'surname': 'Capeluto', 'gender': 'M',
                 'birth_date': None, 'birth_place': None,
                 'death_date': None, 'death_place': None,
                 'is_current': True},
                {'id': 'uuid-2', 'gedcom_id': 'I002', 'name': 'Rachel',
                 'given_name': 'Rachel', 'surname': 'Capeluto', 'gender': 'F',
                 'birth_date': None, 'birth_place': None,
                 'death_date': None, 'death_place': None,
                 'is_current': True},
            ]),
        })
        # Only I001 in new file — I002 removed
        parsed = make_parsed(
            ('I001', make_individual("Sol", "Sol", "Capeluto")),
        )
        result = import_versioned(sb, parsed, 'test.ged', 'hash789', dry_run=True)
        assert result['removed'] == 1
        assert result['unchanged'] == 1
        assert result['added'] == 0

    def test_duplicate_hash_skipped(self):
        """Re-importing same file (same hash) is a no-op."""
        sb = MockSupabase({
            'gedcom_versions': MockSupabaseTable([
                {'source_hash': 'same_hash', 'community_id': 'rhodesli',
                 'version_number': 1, 'imported_at': '2026-01-01'},
            ]),
            'gedcom_individuals': MockSupabaseTable([]),
        })
        parsed = make_parsed(
            ('I001', make_individual("Sol Capeluto")),
        )
        result = import_versioned(sb, parsed, 'test.ged', 'same_hash', dry_run=False)
        assert result['skipped'] is True
        assert result['reason'] == 'duplicate_hash'

    def test_execute_creates_version_and_inserts(self):
        """Full execute mode: creates version, inserts individuals, writes change log."""
        versions_table = MockSupabaseTable([])
        individuals_table = MockSupabaseTable([])
        change_log_table = MockSupabaseTable([])
        face_links_table = MockSupabaseTable([])
        enrichment_table = MockSupabaseTable([])

        sb = MockSupabase({
            'gedcom_versions': versions_table,
            'gedcom_individuals': individuals_table,
            'gedcom_change_log': change_log_table,
            'gedcom_face_links': face_links_table,
            'gedcom_enrichment_queue': enrichment_table,
        })

        parsed = make_parsed(
            ('I001', make_individual("Sol Capeluto", "Sol", "Capeluto")),
            ('I002', make_individual("Rachel Capeluto", "Rachel", "Capeluto")),
        )

        result = import_versioned(sb, parsed, 'test.ged', 'new_hash', dry_run=False)
        assert result.get('skipped') is None
        assert result['added'] == 2
        assert result['version_number'] == 1

        # Version was created
        assert len(versions_table._insert_calls) == 1
        assert versions_table._insert_calls[0]['version_number'] == 1

        # Individuals were inserted
        assert len(individuals_table._insert_calls) == 2

        # Change log was written
        assert len(change_log_table._insert_calls) == 2  # 2 'added' entries

    def test_execute_marks_modified_as_superseded(self):
        """Modified individuals: old row marked superseded, new row inserted."""
        individuals_table = MockSupabaseTable([
            {'id': 'old-uuid', 'gedcom_id': 'I001', 'name': 'Sol',
             'given_name': 'Sol', 'surname': 'Capeluto', 'gender': 'M',
             'birth_date': None, 'birth_place': None,
             'death_date': None, 'death_place': None,
             'is_current': True},
        ])
        versions_table = MockSupabaseTable([])
        change_log_table = MockSupabaseTable([])
        face_links_table = MockSupabaseTable([])
        enrichment_table = MockSupabaseTable([])

        sb = MockSupabase({
            'gedcom_versions': versions_table,
            'gedcom_individuals': individuals_table,
            'gedcom_change_log': change_log_table,
            'gedcom_face_links': face_links_table,
            'gedcom_enrichment_queue': enrichment_table,
        })

        parsed = make_parsed(
            ('I001', make_individual("Sol Capeluto", "Sol", "Capeluto", "M",
                                     birth_raw="1905")),
        )

        result = import_versioned(sb, parsed, 'v2.ged', 'hash_v2', dry_run=False)
        assert result['modified'] == 1
        assert result['added'] == 0

        # Old row was marked as superseded
        assert any(call.get('is_current') is False for call in individuals_table._update_calls)
        assert any(call.get('is_current') is True for call in individuals_table._update_calls)

    def test_execute_marks_version_failed_when_apply_step_raises(self):
        versions_table = MockSupabaseTable([])
        sb = MockSupabase({
            'gedcom_versions': versions_table,
            'gedcom_individuals': MockSupabaseTable([]),
            'gedcom_change_log': MockSupabaseTable([]),
            'gedcom_face_links': MockSupabaseTable([]),
            'gedcom_enrichment_queue': MockSupabaseTable([]),
        })

        parsed = make_parsed(
            ('I001', make_individual("Sol Capeluto", "Sol", "Capeluto")),
        )

        with (
            patch("scripts.import_gedcom_version._apply_entity_diff", side_effect=RuntimeError("boom")),
            pytest.raises(RuntimeError, match="boom"),
        ):
            import_versioned(sb, parsed, 'broken.ged', 'broken-hash', dry_run=False)

        assert versions_table._insert_calls[0]['status'] == 'applying'
        assert any(call.get('status') == 'failed' for call in versions_table._update_calls)

    def test_execute_defers_current_swap_until_all_writes_succeed(self):
        individuals_table = MockSupabaseTable([
            {
                'id': 'legacy-uuid',
                'gedcom_id': 'I001',
                'name': 'Sol Capeluto',
                'given_name': 'Sol',
                'surname': 'Capeluto',
                'gender': 'M',
                'birth_date': None,
                'birth_place': None,
                'death_date': None,
                'death_place': None,
                'is_current': True,
            },
        ])
        versions_table = MockSupabaseTable([])
        change_log_table = MockSupabaseTable([])

        sb = MockSupabase({
            'gedcom_versions': versions_table,
            'gedcom_individuals': individuals_table,
            'gedcom_events': MockSupabaseTable([]),
            'gedcom_relationships': MockSupabaseTable([]),
            'gedcom_families': MockSupabaseTable([]),
            'gedcom_sources': MockSupabaseTable([]),
            'gedcom_media_objects': MockSupabaseTable([]),
            'gedcom_records': MockSupabaseTable([]),
            'gedcom_change_log': change_log_table,
            'gedcom_face_links': MockSupabaseTable([]),
            'gedcom_enrichment_queue': MockSupabaseTable([]),
        })

        parsed = make_parsed(
            ('I001', make_individual("Sol Capeluto", "Sol", "Capeluto", "M", birth_raw="1905")),
        )

        with (
            patch("scripts.import_gedcom_version._queue_enrichments", side_effect=RuntimeError("queue boom")),
            pytest.raises(RuntimeError, match="queue boom"),
        ):
            import_versioned(sb, parsed, 'broken-after-stage.ged', 'hash-stage-fail', dry_run=False)

        assert len(individuals_table._insert_calls) == 1
        assert individuals_table._update_calls == []
        assert len(change_log_table._insert_calls) >= 1
        assert any(call.get('status') == 'failed' for call in versions_table._update_calls)

    def test_baseline_execute_supersedes_unchanged_legacy_rows(self):
        """First versioned import must retire all legacy current rows, even unchanged ones."""
        individuals_table = MockSupabaseTable([
            {
                'id': 'legacy-uuid',
                'gedcom_id': 'I001',
                'name': 'Sol Capeluto',
                'given_name': 'Sol',
                'surname': 'Capeluto',
                'gender': 'M',
                'birth_date': '1905',
                'birth_place': 'Rhodes',
                'death_date': None,
                'death_place': None,
                'is_current': True,
            },
        ])

        sb = MockSupabase({
            'gedcom_versions': MockSupabaseTable([]),
            'gedcom_individuals': individuals_table,
            'gedcom_events': MockSupabaseTable([]),
            'gedcom_relationships': MockSupabaseTable([]),
            'gedcom_change_log': MockSupabaseTable([]),
            'gedcom_face_links': MockSupabaseTable([]),
            'gedcom_enrichment_queue': MockSupabaseTable([]),
        })

        parsed = make_parsed(
            ('I001', make_individual('Sol Capeluto', 'Sol', 'Capeluto', 'M', birth_raw='1905', birth_place='Rhodes')),
        )

        result = import_versioned(sb, parsed, 'baseline.ged', 'baseline-hash', dry_run=False)

        assert result['version_number'] == 1
        assert len(individuals_table._insert_calls) == 1
        assert any(call.get('is_current') is False for call in individuals_table._update_calls)
        assert any(call.get('is_current') is True for call in individuals_table._update_calls)

    def test_enrichment_queue_for_linked_modified(self):
        """Modified individuals with face links trigger enrichment queue."""
        individuals_table = MockSupabaseTable([
            {'id': 'old-uuid', 'gedcom_id': 'I001', 'name': 'Sol',
             'given_name': 'Sol', 'surname': 'Capeluto', 'gender': 'M',
             'birth_date': None, 'birth_place': None,
             'death_date': None, 'death_place': None,
             'is_current': True},
        ])
        face_links_table = MockSupabaseTable([
            {'gedcom_id': 'I001', 'identity_id': 'identity-abc', 'confidence': 0.9},
        ])
        enrichment_table = MockSupabaseTable([])

        sb = MockSupabase({
            'gedcom_versions': MockSupabaseTable([]),
            'gedcom_individuals': individuals_table,
            'gedcom_change_log': MockSupabaseTable([]),
            'gedcom_face_links': face_links_table,
            'gedcom_enrichment_queue': enrichment_table,
        })

        parsed = make_parsed(
            ('I001', make_individual("Sol Capeluto", "Sol", "Capeluto", "M",
                                     birth_raw="1905")),
        )

        result = import_versioned(sb, parsed, 'v2.ged', 'hash_v2b', dry_run=False)
        assert result['modified'] == 1

        # Enrichment was queued
        assert len(enrichment_table._insert_calls) >= 1
        queued = enrichment_table._insert_calls[0]
        assert queued['identity_id'] == 'identity-abc'
        assert queued['trigger'] == 'gedcom_update'
        assert queued['status'] == 'pending'

    def test_dry_run_detects_redirect_for_rekeyed_individual(self):
        """Removed old GEDCOM ids should surface as redirect candidates."""
        versions_table = MockSupabaseTable([
            {'id': 'version-1', 'version_number': 1, 'community_id': 'rhodesli'},
        ])
        individuals_table = MockSupabaseTable([
            {
                'id': 'old-uuid',
                'gedcom_id': 'I001',
                'name': 'Nolan Fox',
                'given_name': 'Nolan',
                'surname': 'Fox',
                'gender': 'M',
                'birth_date': '1985',
                'birth_place': 'Clearwater, Florida, USA',
                'death_date': None,
                'death_place': None,
                'is_current': True,
            },
        ])

        sb = MockSupabase({
            'gedcom_versions': versions_table,
            'gedcom_individuals': individuals_table,
            'gedcom_events': MockSupabaseTable([]),
            'gedcom_relationships': MockSupabaseTable([]),
            'gedcom_families': MockSupabaseTable([]),
            'gedcom_sources': MockSupabaseTable([]),
            'gedcom_media_objects': MockSupabaseTable([]),
            'gedcom_records': MockSupabaseTable([]),
            'gedcom_face_links': MockSupabaseTable([]),
            'gedcom_change_log': MockSupabaseTable([]),
            'gedcom_enrichment_queue': MockSupabaseTable([]),
            'gedcom_entity_redirects': MockSupabaseTable([]),
        })

        parsed = make_parsed(
            ('I999', make_individual('Nolan Fox', 'Nolan', 'Fox', 'M', birth_raw='1985', birth_place='Clearwater, Pinellas, Florida, USA')),
        )

        result = import_versioned(sb, parsed, 'rekey.ged', 'hash-rekey', dry_run=True)

        assert result['redirects']['detected'] == 1
        redirect = result['redirects']['sample'][0]
        assert redirect['old_key'] == 'I001'
        assert redirect['new_key'] == 'I999'

    def test_execute_writes_redirect_rows_for_rekeyed_individual(self):
        """Execute mode should persist redirect metadata for removed -> current matches."""
        versions_table = MockSupabaseTable([
            {'id': 'version-1', 'version_number': 1, 'community_id': 'rhodesli'},
        ])
        individuals_table = MockSupabaseTable([
            {
                'id': 'old-uuid',
                'gedcom_id': 'I001',
                'name': 'Nolan Fox',
                'given_name': 'Nolan',
                'surname': 'Fox',
                'gender': 'M',
                'birth_date': '1985',
                'birth_place': 'Clearwater, Florida, USA',
                'death_date': None,
                'death_place': None,
                'is_current': True,
            },
        ])
        redirect_table = MockSupabaseTable([])
        change_log_table = MockSupabaseTable([])

        sb = MockSupabase({
            'gedcom_versions': versions_table,
            'gedcom_individuals': individuals_table,
            'gedcom_events': MockSupabaseTable([]),
            'gedcom_relationships': MockSupabaseTable([]),
            'gedcom_families': MockSupabaseTable([]),
            'gedcom_sources': MockSupabaseTable([]),
            'gedcom_media_objects': MockSupabaseTable([]),
            'gedcom_records': MockSupabaseTable([]),
            'gedcom_face_links': MockSupabaseTable([]),
            'gedcom_change_log': change_log_table,
            'gedcom_enrichment_queue': MockSupabaseTable([]),
            'gedcom_entity_redirects': redirect_table,
        })

        parsed = make_parsed(
            ('I999', make_individual('Nolan Fox', 'Nolan', 'Fox', 'M', birth_raw='1985', birth_place='Clearwater, Pinellas, Florida, USA')),
        )

        result = import_versioned(sb, parsed, 'rekey.ged', 'hash-rekey-2', dry_run=False)

        assert result['redirects']['detected'] == 1
        assert len(redirect_table._insert_calls) == 1
        assert redirect_table._insert_calls[0]['old_key'] == 'I001'
        assert redirect_table._insert_calls[0]['new_key'] == 'I999'
        assert any(entry['change_type'] == 'redirected' for entry in change_log_table._insert_calls)

    def test_bootstrap_execute_writes_redirect_rows_for_rekeyed_individual(self):
        """First versioned import should still persist redirect metadata for legacy rekeys."""
        versions_table = MockSupabaseTable([])
        individuals_table = MockSupabaseTable([
            {
                'id': 'old-uuid',
                'gedcom_id': 'I001',
                'name': 'Nolan Fox',
                'given_name': 'Nolan',
                'surname': 'Fox',
                'gender': 'M',
                'birth_date': '1985',
                'birth_place': 'Clearwater, Florida, USA',
                'death_date': None,
                'death_place': None,
                'is_current': True,
            },
        ])
        redirect_table = MockSupabaseTable([])
        change_log_table = MockSupabaseTable([])

        sb = MockSupabase({
            'gedcom_versions': versions_table,
            'gedcom_individuals': individuals_table,
            'gedcom_events': MockSupabaseTable([]),
            'gedcom_relationships': MockSupabaseTable([]),
            'gedcom_families': MockSupabaseTable([]),
            'gedcom_sources': MockSupabaseTable([]),
            'gedcom_media_objects': MockSupabaseTable([]),
            'gedcom_records': MockSupabaseTable([]),
            'gedcom_face_links': MockSupabaseTable([]),
            'gedcom_change_log': change_log_table,
            'gedcom_enrichment_queue': MockSupabaseTable([]),
            'gedcom_entity_redirects': redirect_table,
        })

        parsed = make_parsed(
            ('I999', make_individual('Nolan Fox', 'Nolan', 'Fox', 'M', birth_raw='1985', birth_place='Clearwater, Pinellas, Florida, USA')),
        )

        result = import_versioned(sb, parsed, 'rekey-bootstrap.ged', 'hash-rekey-bootstrap', dry_run=False)

        assert result['redirects']['detected'] == 1
        assert len(redirect_table._insert_calls) == 1
        assert redirect_table._insert_calls[0]['old_key'] == 'I001'
        assert redirect_table._insert_calls[0]['new_key'] == 'I999'
        assert any(entry['change_type'] == 'redirected' for entry in change_log_table._insert_calls)


class TestRichSchemaChecks:
    """Guard bootstrap-mode schema checks for rich GEDCOM tables."""

    def test_bootstrap_marks_rich_table_present_when_visibility_check_passes(self):
        with patch("scripts.import_gedcom_version._table_exists", return_value=True):
            result = import_mod._load_current_entity_map(MockSupabase({}), "families", baseline_mode=True)

        assert result == {"rows": {}, "missing_table": False}

    def test_required_schema_tables_only_reports_actual_missing_tables(self):
        diff_by_entity = {
            "families": {"summary": {"added": 10, "modified": 0, "removed": 0, "unchanged": 0}},
            "sources": {"summary": {"added": 3, "modified": 0, "removed": 0, "unchanged": 0}},
            "media_objects": {"summary": {"added": 1, "modified": 0, "removed": 0, "unchanged": 0}},
            "records": {"summary": {"added": 20, "modified": 0, "removed": 0, "unchanged": 0}},
        }

        result = import_mod._required_schema_tables(diff_by_entity, ["gedcom_sources"])

        assert result == ["gedcom_sources"]


class TestDirectDbFinalization:
    """Ensure direct-DB current swaps handle UUID-like ids safely."""

    def test_insert_rows_uses_direct_db_returned_rows_when_available(self):
        with patch(
            "scripts.import_gedcom_version._insert_rows_direct_db",
            return_value=[{"id": "row-1", "gedcom_id": "I001"}],
        ):
            result = import_mod._insert_rows(MockSupabase({}), "gedcom_individuals", [{"gedcom_id": "I001"}])

        assert result == {"I001": {"id": "row-1", "gedcom_id": "I001"}}

    def test_swap_current_rows_direct_db_stringifies_ids(self):
        executed = []

        class FakeCursor:
            def execute(self, query, params):
                executed.append((query, params))

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        class FakeConnection:
            def cursor(self):
                return FakeCursor()

            def close(self):
                return None

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("scripts.import_gedcom_version._get_direct_db_swap_connection", return_value=FakeConnection()):
            ok = import_mod._swap_current_rows_direct_db(
                "gedcom_individuals",
                [{"id": uuid.UUID("11111111-1111-1111-1111-111111111111")}],
                [{"id": uuid.UUID("22222222-2222-2222-2222-222222222222")}],
            )

        assert ok is True
        assert executed[0][1] == (["11111111-1111-1111-1111-111111111111"],)
        assert executed[1][1] == (["22222222-2222-2222-2222-222222222222"],)


class TestChangeLogStreaming:
    """Ensure large change logs can flush incrementally instead of accumulating in memory."""

    def test_write_change_log_flushes_in_batches(self):
        flushed_batches = []

        def fake_write_rows(sb, table_name, rows, batch_size=500):
            del sb
            flushed_batches.append((table_name, [row.copy() for row in rows], batch_size))

        diff_by_entity = {
            "individuals": {
                "added": [{"entity_id": "I001"}, {"entity_id": "I002"}],
                "removed": [{"entity_id": "I003"}],
                "modified": [
                    {
                        "entity_id": "I004",
                        "changes": [
                            {"path": "birth_date", "old_value": None, "new_value": "1901"},
                            {"path": "birth_place", "old_value": None, "new_value": "Rhodes"},
                        ],
                    }
                ],
            }
        }
        redirects = [
            {"entity_type": "individual", "old_key": "I003", "new_key": "I004"},
        ]

        with patch("scripts.import_gedcom_version._write_rows", side_effect=fake_write_rows):
            import_mod._write_change_log(
                MockSupabase({}),
                "version-123",
                diff_by_entity,
                redirects,
                batch_size=2,
            )

        assert [len(rows) for _, rows, _ in flushed_batches] == [2, 2, 2]
        flattened = [row for _, rows, _ in flushed_batches for row in rows]
        assert [row["change_type"] for row in flattened] == [
            "added",
            "added",
            "removed",
            "modified",
            "modified",
            "redirected",
        ]
        assert all(table_name == "gedcom_change_log" for table_name, _, _ in flushed_batches)


class TestSnapshotBundle:
    """Guard schema field naming for rich record snapshots."""

    def test_record_snapshots_use_root_json_column_name(self):
        root = SimpleNamespace(level=0, tag='INDI', xref_id='I001', value=None, children=[])
        record = SimpleNamespace(
            record_key='INDI:I001',
            record_type='INDI',
            xref_id='I001',
            record_hash='hash-1',
            raw_text='0 @I001@ INDI',
            root=root,
        )
        parsed = SimpleNamespace(
            individuals={},
            families={},
            sources={},
            media_objects={},
            records={'INDI:I001': record},
            source_file='test.ged',
        )

        bundle = build_snapshot_bundle(parsed, source_file='test.ged')

        row = bundle.records['INDI:I001']
        assert 'root_json' in row
        assert 'root' not in row


class TestCompareFieldsCoverage:
    """Ensure all expected fields are compared."""

    def test_all_important_fields_in_compare_list(self):
        expected = {'name', 'given_name', 'surname', 'gender',
                    'birth_date', 'birth_place', 'death_date', 'death_place'}
        assert set(INDIVIDUAL_COMPARE_FIELDS) == expected
