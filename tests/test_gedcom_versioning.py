"""Tests for GEDCOM temporal versioning (AD-163).

Tests the import_gedcom_version module: version tracking, diff detection,
change logging, duplicate detection, and re-enrichment queue.
"""

import hashlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# We need to be able to import from scripts/
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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
        assert len(individuals_table._update_calls) == 1
        assert individuals_table._update_calls[0]['is_current'] is False

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


class TestCompareFieldsCoverage:
    """Ensure all expected fields are compared."""

    def test_all_important_fields_in_compare_list(self):
        expected = {'name', 'given_name', 'surname', 'gender',
                    'birth_date', 'birth_place', 'death_date', 'death_place'}
        assert set(INDIVIDUAL_COMPARE_FIELDS) == expected
