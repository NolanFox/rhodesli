"""Tests for scripts/session154_supabase_prune.py.

Covers the snapshot/verify/auth-gate pure-function paths. The DB-touching
paths (step_execute, step_dry_run, connect) are not unit-tested — they
require live Supabase access and are excluded from the standard suite.
"""
from __future__ import annotations

import gzip
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add repo root so 'scripts' import works
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts import session154_supabase_prune as prune  # noqa: E402


@pytest.fixture
def sample_rows():
    return [
        {"id": "00000000-0000-0000-0000-000000000001", "value": "row1"},
        {"id": "00000000-0000-0000-0000-000000000002", "value": "row2"},
        {"id": "00000000-0000-0000-0000-000000000003", "value": "row3"},
    ]


def test_hash_rows_is_deterministic(sample_rows):
    h1 = prune.hash_rows(sample_rows)
    h2 = prune.hash_rows(list(reversed(sample_rows)))  # order-independent
    assert h1 == h2
    # Different rows → different hash
    different = sample_rows + [{"id": "extra", "value": "x"}]
    assert prune.hash_rows(different) != h1


def test_write_and_verify_snapshot_roundtrip(tmp_path, sample_rows):
    snapshot = tmp_path / "test_snapshot.jsonl.gz"
    manifest = prune.write_snapshot(
        sample_rows,
        table="test_table",
        predicate="id IS NOT NULL",
        snapshot_path=snapshot,
    )
    assert manifest["total_rows"] == 3
    assert manifest["table"] == "test_table"
    assert "restore_command" in manifest

    re_manifest, re_rows = prune.verify_snapshot(snapshot)
    assert re_manifest["sha256_of_rows"] == manifest["sha256_of_rows"]
    assert len(re_rows) == 3


def test_verify_snapshot_detects_row_count_mismatch(tmp_path, sample_rows):
    snapshot = tmp_path / "tampered.jsonl.gz"
    manifest = prune.write_snapshot(sample_rows, "t", "p", snapshot)
    # Tamper: rewrite with header total_rows=5 but only 3 rows
    bad_manifest = dict(manifest)
    bad_manifest["total_rows"] = 5
    with gzip.open(snapshot, "wt") as gz:
        gz.write(json.dumps(bad_manifest) + "\n")
        for r in sample_rows:
            gz.write(json.dumps(r) + "\n")
    with pytest.raises(ValueError, match="row count mismatch"):
        prune.verify_snapshot(snapshot)


def test_verify_snapshot_detects_hash_tamper(tmp_path, sample_rows):
    snapshot = tmp_path / "hash_tampered.jsonl.gz"
    manifest = prune.write_snapshot(sample_rows, "t", "p", snapshot)
    # Tamper: replace one row but keep same row count + stale hash
    bad_rows = list(sample_rows)
    bad_rows[0] = {"id": bad_rows[0]["id"], "value": "MUTATED"}
    with gzip.open(snapshot, "wt") as gz:
        gz.write(json.dumps(manifest) + "\n")  # stale hash
        for r in bad_rows:
            gz.write(json.dumps(r) + "\n")
    with pytest.raises(ValueError, match="hash mismatch"):
        prune.verify_snapshot(snapshot)


def test_assert_authorization_refuses_when_unset(monkeypatch, capsys):
    monkeypatch.delenv("SESSION154_PRUNE_AUTH", raising=False)
    with pytest.raises(SystemExit) as exc_info:
        prune.assert_authorization()
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "REFUSED" in captured.err


def test_assert_authorization_refuses_when_wrong_format(monkeypatch, capsys):
    monkeypatch.setenv("SESSION154_PRUNE_AUTH", "yes please")
    with pytest.raises(SystemExit) as exc_info:
        prune.assert_authorization()
    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "REFUSED" in captured.err


def test_assert_authorization_passes_with_correct_prefix(monkeypatch):
    monkeypatch.setenv("SESSION154_PRUNE_AUTH", "approved-deadbeef")
    # Should not raise
    prune.assert_authorization()


def test_main_requires_step_or_restore(capsys):
    rc = prune.main([])
    assert rc == 2
    captured = capsys.readouterr()
    assert "--step is required" in captured.err


def test_main_execute_without_auth_refuses(monkeypatch, capsys):
    """Most-important regression: --execute without auth env must NOT touch DB."""
    monkeypatch.delenv("SESSION154_PRUNE_AUTH", raising=False)
    # Patch connect() so we can detect if it's even called
    with patch.object(prune, "connect") as mock_connect:
        with pytest.raises(SystemExit) as exc_info:
            prune.main(["--step", "gedcom_individuals", "--execute"])
        assert exc_info.value.code == 2
        # Must have refused BEFORE attempting to connect
        assert mock_connect.call_count == 0
    captured = capsys.readouterr()
    assert "REFUSED" in captured.err


def test_main_restore_requires_snapshot_path():
    rc = prune.main(["--restore"])
    assert rc == 2


def test_prune_steps_registry_is_locked():
    """Regression: the predicate set is fixed. New steps need explicit
    code review + plan update — they cannot be added by env var."""
    expected = {
        "gedcom_individuals",
        "gedcom_records",
        "gedcom_events",
        "gedcom_relationships",
        "gedcom_families",
        "gedcom_change_log_step_a",
        "gedcom_change_log_step_b",
    }
    assert set(prune.PRUNE_STEPS.keys()) == expected
    # Every predicate must contain a status filter or NULL filter — no free-form WHERE
    for name, cfg in prune.PRUNE_STEPS.items():
        pred = cfg["select_predicate"]
        assert "status =" in pred or "is_current" in pred or "old_value IS NULL" in pred, \
            f"Step {name} has predicate without safety filter: {pred}"


def test_prune_steps_have_expected_row_counts():
    """E1 plan §5 byte-savings depends on row count. Drift detection."""
    expectations = {
        "gedcom_individuals": 131_664,
        "gedcom_records": 60_308,
        "gedcom_events": 143_578,
        "gedcom_relationships": 439_776,
        "gedcom_families": 20_166,
        "gedcom_change_log_step_a": 589_594,
    }
    for step, count in expectations.items():
        assert prune.PRUNE_STEPS[step]["expected_rows"] == count, \
            f"{step} expected_rows drift — update E1 plan first"
