"""Atomic GEDCOM importer tests (Session 164, PRD-064).

Pure fakes — NO live Postgres, NO network. A fake psycopg2-style cursor/conn
proves the rollback + idempotency + advisory-lock-first logic. The real-Postgres
atomicity test (plan R7) runs separately during the session; CI relies on these
fake-cursor logic tests.
"""

from __future__ import annotations

import re
from types import SimpleNamespace

import pytest

import scripts.import_gedcom_version as imp
from rhodesli_ml.importers import gedcom_history as gh
from rhodesli_ml.importers.gedcom_parser import parse_gedcom
from rhodesli_ml.importers.gedcom_snapshot import build_snapshot_bundle


# --------------------------------------------------------------------------- #
# Fake psycopg2 conn / cursor
# --------------------------------------------------------------------------- #
class FakeCursor:
    """Records executed SQL; serves canned answers for the importer's SELECTs.

    `applied_rows` lets a test pre-seed an existing applied version (idempotency).
    """

    def __init__(self, conn):
        self.conn = conn

    def execute(self, sql, params=None):
        self.conn.executed.append((sql, params))
        normalized = re.sub(r"\s+", " ", sql).strip().lower()

        if "pg_advisory_xact_lock" in normalized:
            self.conn.lock_acquired = True
            self._result = [(True,)]
        elif "from gedcom_versions where community_id" in normalized and "source_hash" in normalized:
            # idempotency dup-check
            self._result = self.conn.applied_version_rows
        elif "coalesce(max(version_number)" in normalized:
            self._result = [(self.conn.max_version,)]
        elif normalized.startswith("select") and "from gedcom_individuals" in normalized:
            self._result = list(self.conn.tables.get("gedcom_individuals", []))
        elif normalized.startswith("select") and "from gedcom_families" in normalized:
            self._result = list(self.conn.tables.get("gedcom_families", []))
        elif normalized.startswith("select") and "from gedcom_relationships" in normalized:
            self._result = list(self.conn.tables.get("gedcom_relationships", []))
        elif normalized.startswith("insert into gedcom_individuals"):
            self.conn.applied_ops.append("insert_individuals")
            self._result = []
        elif normalized.startswith("insert into gedcom_families"):
            self.conn.applied_ops.append("insert_families")
            self._result = []
        elif normalized.startswith("insert into gedcom_relationships"):
            self.conn.applied_ops.append("insert_relationships")
            self._result = []
        elif normalized.startswith("delete from"):
            self.conn.applied_ops.append("delete")
            self._result = []
        elif normalized.startswith("insert into gedcom_versions"):
            self.conn.applied_ops.append("insert_version")
            if self.conn.fail_on_version_insert:
                raise RuntimeError("simulated version insert failure")
            self._result = []
        else:
            self._result = []

    def fetchone(self):
        return self._result[0] if self._result else None

    def fetchall(self):
        return list(self._result)

    def close(self):
        pass


class FakeExecuteValues:
    """Patches psycopg2.extras.execute_values to route through FakeCursor.execute."""


class FakeConn:
    def __init__(self, applied_version_rows=None, max_version=0, fail_on_version_insert=False):
        self.executed = []
        self.applied_ops = []
        self.applied_version_rows = applied_version_rows or []
        self.max_version = max_version
        self.fail_on_version_insert = fail_on_version_insert
        self.committed = False
        self.rolled_back = False
        self.closed = False
        self.lock_acquired = False
        self.tables = {}

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class FakeR2:
    def __init__(self):
        self.store = {}

    def put_object(self, Bucket, Key, Body):
        self.store[(Bucket, Key)] = Body

    def get_object(self, Bucket, Key):
        data = self.store[(Bucket, Key)]
        return {"Body": SimpleNamespace(read=lambda: data)}


# --------------------------------------------------------------------------- #
# Fixtures: a tiny real GEDCOM file
# --------------------------------------------------------------------------- #
SAMPLE_GEDCOM = """0 HEAD
1 SOUR test
1 GEDC
2 VERS 5.5.1
0 @I1@ INDI
1 NAME Sol /Capeluto/
1 SEX M
1 BIRT
2 DATE 1905
0 @I2@ INDI
1 NAME Rosa /Capeluto/
1 SEX F
0 @F1@ FAM
1 HUSB @I1@
1 WIFE @I2@
0 TRLR
"""


@pytest.fixture
def gedcom_file(tmp_path):
    path = tmp_path / "sample.ged"
    path.write_text(SAMPLE_GEDCOM)
    return str(path)


@pytest.fixture(autouse=True)
def _patch_execute_values(monkeypatch):
    """execute_values is imported lazily inside apply_entity_diffs; route to fake."""

    def fake_execute_values(cur, sql, argslist, *a, **kw):
        cur.execute(sql, list(argslist))

    import psycopg2.extras

    monkeypatch.setattr(psycopg2.extras, "execute_values", fake_execute_values)


# --------------------------------------------------------------------------- #
# Dry-run
# --------------------------------------------------------------------------- #
def test_dry_run_no_db_no_r2(gedcom_file):
    result = imp.run_import(gedcom_file, execute=False)
    assert result["execute"] is False
    assert result["source_hash"]
    # individuals added in the diff summary (vs empty baseline)
    assert result["diff_summary"]["individuals"]["added"] == 2
    assert result["counts"]["individuals"] == 2


# --------------------------------------------------------------------------- #
# Atomicity: failure mid-import → ROLLBACK, ZERO committed
# --------------------------------------------------------------------------- #
def test_failed_import_rolls_back_zero_rows(gedcom_file):
    conn = FakeConn(fail_on_version_insert=True)
    r2 = FakeR2()
    with pytest.raises(RuntimeError, match="simulated version insert failure"):
        imp.run_import(
            gedcom_file,
            execute=True,
            conn_factory=lambda: conn,
            r2_factory=lambda: r2,
        )
    assert conn.rolled_back is True
    assert conn.committed is False
    # Mutations were attempted but the txn never committed → ZERO persisted.
    assert conn.closed is True


def test_r2_verify_failure_aborts_before_commit(gedcom_file, monkeypatch):
    conn = FakeConn()

    class CorruptR2(FakeR2):
        def get_object(self, Bucket, Key):
            data = self.store[(Bucket, Key)] + b"corrupt"
            return {"Body": SimpleNamespace(read=lambda: data)}

    with pytest.raises(ValueError, match="verification failed"):
        imp.run_import(
            gedcom_file,
            execute=True,
            conn_factory=lambda: conn,
            r2_factory=lambda: CorruptR2(),
        )
    assert conn.rolled_back is True
    assert conn.committed is False
    # No DB mutation ops ran (R2 verify happens before apply_entity_diffs).
    assert "insert_version" not in conn.applied_ops


# --------------------------------------------------------------------------- #
# Lock acquired BEFORE state read (Codex P0-1)
# --------------------------------------------------------------------------- #
def test_advisory_lock_acquired_before_state_read(gedcom_file):
    conn = FakeConn()
    r2 = FakeR2()
    imp.run_import(
        gedcom_file, execute=True, conn_factory=lambda: conn, r2_factory=lambda: r2
    )
    # First executed statement must be the advisory lock.
    first_sql = re.sub(r"\s+", " ", conn.executed[0][0]).lower()
    assert "pg_advisory_xact_lock" in first_sql
    # The state reads (idempotency check, version allocation, diff-base lookup)
    # must all come AFTER the lock.
    lock_index = next(i for i, (s, _) in enumerate(conn.executed) if "pg_advisory_xact_lock" in s.lower())
    # version allocation (MAX) must follow the lock
    max_index = next(
        i for i, (s, _) in enumerate(conn.executed) if "coalesce(max(version_number)" in re.sub(r"\s+", " ", s.lower())
    )
    assert lock_index == 0
    assert lock_index < max_index


# --------------------------------------------------------------------------- #
# Idempotency (Codex P1-1)
# --------------------------------------------------------------------------- #
def test_idempotent_reimport_is_noop(gedcom_file):
    # Pre-seed: an applied version already exists for this source_hash.
    conn = FakeConn(applied_version_rows=[(9,)])
    r2 = FakeR2()
    result = imp.run_import(
        gedcom_file, execute=True, conn_factory=lambda: conn, r2_factory=lambda: r2
    )
    assert result["idempotent"] is True
    assert result["version_number"] == 9
    assert conn.rolled_back is True
    assert conn.committed is False
    # No mutations, no R2 uploads.
    assert conn.applied_ops == []
    assert r2.store == {}


# --------------------------------------------------------------------------- #
# Happy path: applies, allocates next version, commits, uploads R2
# --------------------------------------------------------------------------- #
def test_happy_path_applies_and_commits(gedcom_file):
    conn = FakeConn(max_version=8)
    r2 = FakeR2()
    result = imp.run_import(
        gedcom_file, execute=True, conn_factory=lambda: conn, r2_factory=lambda: r2
    )
    assert result["idempotent"] is False
    assert result["version_number"] == 9
    assert conn.committed is True
    assert conn.rolled_back is False
    assert "insert_individuals" in conn.applied_ops
    assert "insert_families" in conn.applied_ops
    assert "insert_version" in conn.applied_ops
    # R2 artifacts uploaded + verified.
    prefix = result["artifact_prefix"]
    assert (imp._r2_bucket(), prefix + "snapshot.jsonl.gz") in r2.store
    assert (imp._r2_bucket(), prefix + "diff.json.gz") in r2.store
    assert (imp._r2_bucket(), prefix + "raw.ged.gz") in r2.store
    # diff_summary present in result.
    assert result["diff_summary"]["individuals"]["added"] == 2


# --------------------------------------------------------------------------- #
# Bundle payload -> column mapping
# --------------------------------------------------------------------------- #
def test_individual_row_values_maps_columns():
    payload = {
        "gedcom_id": "@I1@",
        "name": "Sol Capeluto",
        "given_name": "Sol",
        "surname": "Capeluto",
        "gender": "M",
        "birth_date": "1905",
        "birth_place": "Rhodes",
        "death_date": None,
        "death_place": None,
        "names_json": [{"full_name": "Sol Capeluto"}],
        "events_json": [],
        "family_as_spouse_json": ["@F1@"],
        "family_as_child_json": [],
        "notes_json": [],
        "citations_json": [],
        "payload_hash": "abc123",
    }
    values = imp.individual_row_values("rhodesli", payload, 9)
    # leading community_id, trailing version_number
    assert values[0] == "rhodesli"
    assert values[-1] == 9
    # gedcom_id is first column after community
    assert values[1] == "@I1@"
    # JSON columns are serialized to strings
    import json as _json

    names_idx = 1 + imp.INDIVIDUAL_COLUMNS.index("names_json")
    assert _json.loads(values[names_idx]) == [{"full_name": "Sol Capeluto"}]
    # payload_hash carried verbatim
    ph_idx = 1 + imp.INDIVIDUAL_COLUMNS.index("payload_hash")
    assert values[ph_idx] == "abc123"


# --------------------------------------------------------------------------- #
# Codex P0-A: diff base loaded from the PREVIOUS applied R2 snapshot
# --------------------------------------------------------------------------- #
class _PriorBaseCursor(FakeCursor):
    """FakeCursor that also answers the latest-applied artifact_prefix lookup."""

    def execute(self, sql, params=None):
        normalized = re.sub(r"\s+", " ", sql).strip().lower()
        # The diff-base lookup: SELECT artifact_prefix ... ORDER BY version_number DESC
        if (
            normalized.startswith("select artifact_prefix from gedcom_versions")
            and "status = 'applied'" in normalized
            and "source_hash" not in normalized
        ):
            self.conn.executed.append((sql, params))
            self._result = [(self.conn.prior_prefix,)] if self.conn.prior_prefix else []
            return
        super().execute(sql, params)


class _PriorBaseConn(FakeConn):
    def __init__(self, prior_prefix=None, **kw):
        super().__init__(**kw)
        self.prior_prefix = prior_prefix

    def cursor(self):
        return _PriorBaseCursor(self)


def test_importer_diff_base_comes_from_prior_r2_snapshot(gedcom_file):
    """A re-import of the SAME bundle (different source bytes so not idempotent)
    must diff against the prior version's R2 snapshot — an unchanged entity is
    NOT re-added (proving the base is the lossless snapshot, not empty/DB)."""
    # Build the prior snapshot from the same GEDCOM the importer will parse.
    bundle = build_snapshot_bundle(parse_gedcom(gedcom_file), source_file="sample.ged")
    prior_prefix = "gedcom-history/rhodesli/v0008-prior000000/"
    snapshot_gz = gh.build_snapshot_jsonl_gz(bundle)

    r2 = FakeR2()
    r2.store[(imp._r2_bucket(), prior_prefix + "snapshot.jsonl.gz")] = snapshot_gz

    conn = _PriorBaseConn(prior_prefix=prior_prefix, max_version=8)
    result = imp.run_import(
        gedcom_file, execute=True, conn_factory=lambda: conn, r2_factory=lambda: r2
    )
    assert result["idempotent"] is False
    # The new bundle == the prior snapshot, so the diff is all-unchanged:
    summary = result["diff_summary"]
    assert summary["individuals"]["added"] == 0
    assert summary["individuals"]["modified"] == 0
    assert summary["families"]["added"] == 0
    # The diff-base prefix lookup actually ran (against gedcom_versions).
    assert any(
        "select artifact_prefix from gedcom_versions" in re.sub(r"\s+", " ", s.lower())
        for s, _ in conn.executed
    )


def test_importer_first_import_diffs_against_empty(gedcom_file):
    """With no prior applied prefix, the base is empty — everything is added."""
    r2 = FakeR2()
    conn = _PriorBaseConn(prior_prefix=None, max_version=0)
    result = imp.run_import(
        gedcom_file, execute=True, conn_factory=lambda: conn, r2_factory=lambda: r2
    )
    assert result["diff_summary"]["individuals"]["added"] == 2
