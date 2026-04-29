"""Tests for scripts/retention_sweep.py.

Covers the auth-gate, registry-locking, and dry-run-default contracts.
DB-touching paths are not unit-tested.
"""
from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts import retention_sweep as rs  # noqa: E402


def test_retention_rules_registry_is_locked():
    """Regression: retention rule set is fixed. New rules need code review +
    OD-013 amendment — not env-var injection."""
    expected = {
        "gemini_api_calls",
        "audit_log",
        "ml_proposals_resolved",
        "gedcom_change_log_keep_3",
    }
    assert set(rs.RETENTION_RULES.keys()) == expected
    # Every rule must have a non-empty predicate
    for name, rule in rs.RETENTION_RULES.items():
        assert rule["predicate"], f"Rule {name} has empty predicate"
        assert rule["table"], f"Rule {name} has empty table"


def test_retention_predicates_have_temporal_or_window_filter():
    """Drift-detection: a retention predicate without a time/version filter
    would prune ALL rows. Reject any such rule."""
    for name, rule in rs.RETENTION_RULES.items():
        pred = rule["predicate"]
        has_time = "INTERVAL" in pred or "NOW()" in pred
        has_version = "ORDER BY" in pred and "LIMIT" in pred
        has_status = "status IN" in pred or "status =" in pred
        assert has_time or has_version or has_status, (
            f"Rule {name!r} has no temporal or version filter — would prune ALL rows"
        )


def test_assert_authorization_refuses_when_unset(monkeypatch, capsys):
    monkeypatch.delenv("RETENTION_AUTH", raising=False)
    with pytest.raises(SystemExit) as exc_info:
        rs.assert_authorization()
    assert exc_info.value.code == 2
    assert "REFUSED" in capsys.readouterr().err


def test_assert_authorization_refuses_wrong_format(monkeypatch, capsys):
    monkeypatch.setenv("RETENTION_AUTH", "yes")
    with pytest.raises(SystemExit) as exc_info:
        rs.assert_authorization()
    assert exc_info.value.code == 2
    assert "REFUSED" in capsys.readouterr().err


def test_assert_authorization_passes_with_approved_prefix(monkeypatch):
    monkeypatch.setenv("RETENTION_AUTH", "approved-od013")
    rs.assert_authorization()  # no raise


def test_main_execute_without_auth_never_connects(monkeypatch, capsys):
    """The most-important regression: --execute without RETENTION_AUTH
    must NOT touch the DB even if the DB is reachable."""
    monkeypatch.delenv("RETENTION_AUTH", raising=False)
    with patch.object(rs, "connect") as mock_connect:
        with pytest.raises(SystemExit) as exc_info:
            rs.main(["--table", "gemini_api_calls", "--execute"])
        assert exc_info.value.code == 2
        assert mock_connect.call_count == 0  # never called
    assert "REFUSED" in capsys.readouterr().err


def test_snapshot_roundtrip(tmp_path):
    rows = [{"id": "a", "v": 1}, {"id": "b", "v": 2}]
    snapshot_path = tmp_path / "test.jsonl.gz"
    manifest = rs.write_snapshot(rows, "test_table", "v IS NOT NULL", snapshot_path)
    assert manifest["total_rows"] == 2
    assert manifest["table"] == "test_table"
    # Read back
    with gzip.open(snapshot_path, "rt") as gz:
        first = json.loads(gz.readline())
        recovered = [json.loads(line) for line in gz if line.strip()]
    assert first["sha256_of_rows"] == manifest["sha256_of_rows"]
    assert len(recovered) == 2


def test_hash_rows_deterministic():
    rows = [{"id": "a"}, {"id": "b"}]
    assert rs.hash_rows(rows) == rs.hash_rows(list(reversed(rows)))


def test_no_rule_targets_a_table_outside_known_set():
    """Sanity check: every retention rule targets a known Supabase table.
    If a future commit adds 'users' or 'auth.users' to retention, fail loudly."""
    allowed_tables = {
        "gemini_api_calls", "audit_log", "ml_proposals", "gedcom_change_log",
    }
    for name, rule in rs.RETENTION_RULES.items():
        assert rule["table"] in allowed_tables, (
            f"Rule {name!r} targets table {rule['table']!r} not in allowlist"
        )
