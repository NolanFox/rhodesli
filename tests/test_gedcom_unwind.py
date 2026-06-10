"""Conservative unwind plan tests (Session 164, PRD-064).

Pure logic — NO live DB, NO network. Validates conflict detection, no-op cases,
and referential-integrity refusal in `compute_unwind_plan`.
"""

from __future__ import annotations

import gzip
import json
import re
from types import SimpleNamespace

import scripts.gedcom_unwind as uw
import scripts.import_gedcom_version as imp
from rhodesli_ml.importers import gedcom_history as gh


def _diff(entities):
    return {"entities": entities}


# --------------------------------------------------------------------------- #
# added -> delete
# --------------------------------------------------------------------------- #
def test_added_safe_delete_when_hash_matches_and_unreferenced():
    target = _diff(
        {
            "individuals": {
                "added": [{"entity_id": "@I1@", "after_hash": "h1", "after": {"x": 1}}],
                "modified": [],
                "removed": [],
            }
        }
    )
    plan = uw.compute_unwind_plan(
        target,
        current_state_hashes={"individuals": {"@I1@": "h1"}},
        current_refs={"individuals": set(), "families": set()},
    )
    assert plan["conflicts"] == []
    # Codex P0-D: removed inverse carries old_payload (= original add's `after`).
    assert plan["safe"]["individuals"]["removed"] == [{"entity_id": "@I1@", "old_payload": {"x": 1}}]


def test_added_conflict_when_current_hash_differs():
    target = _diff(
        {"individuals": {"added": [{"entity_id": "@I1@", "after_hash": "h1", "after": {}}], "modified": [], "removed": []}}
    )
    plan = uw.compute_unwind_plan(
        target,
        current_state_hashes={"individuals": {"@I1@": "DIFFERENT"}},
        current_refs={"individuals": set(), "families": set()},
    )
    assert len(plan["conflicts"]) == 1
    assert plan["conflicts"][0]["reason"].startswith("current_hash != after_hash")
    assert plan["safe"] == {}


def test_added_conflict_when_still_referenced():
    target = _diff(
        {"individuals": {"added": [{"entity_id": "@I1@", "after_hash": "h1", "after": {}}], "modified": [], "removed": []}}
    )
    plan = uw.compute_unwind_plan(
        target,
        current_state_hashes={"individuals": {"@I1@": "h1"}},
        current_refs={"individuals": {"@I1@"}, "families": set()},  # referenced!
    )
    assert len(plan["conflicts"]) == 1
    assert "still referenced" in plan["conflicts"][0]["reason"]
    assert plan["safe"] == {}


def test_added_noop_when_already_absent():
    target = _diff(
        {"individuals": {"added": [{"entity_id": "@I1@", "after_hash": "h1", "after": {}}], "modified": [], "removed": []}}
    )
    plan = uw.compute_unwind_plan(
        target,
        current_state_hashes={"individuals": {}},  # already deleted
        current_refs={"individuals": set(), "families": set()},
    )
    assert plan["conflicts"] == []
    assert plan["safe"] == {}
    assert plan["noops"][0]["reason"] == "added-absent"


# --------------------------------------------------------------------------- #
# removed -> re-add
# --------------------------------------------------------------------------- #
def test_removed_safe_readd_when_absent():
    before = {"gedcom_id": "@I1@", "payload_hash": "hbefore"}
    target = _diff(
        {
            "individuals": {
                "added": [],
                "modified": [],
                "removed": [{"entity_id": "@I1@", "before": before, "before_hash": "hbefore"}],
            }
        }
    )
    plan = uw.compute_unwind_plan(
        target,
        current_state_hashes={"individuals": {}},  # currently absent
        current_refs={"individuals": set(), "families": set()},
    )
    assert plan["conflicts"] == []
    assert plan["safe"]["individuals"]["added"] == [{"entity_id": "@I1@", "new_payload": before}]


def test_removed_noop_when_present_as_before():
    target = _diff(
        {"individuals": {"added": [], "modified": [], "removed": [{"entity_id": "@I1@", "before": {}, "before_hash": "hbefore"}]}}
    )
    plan = uw.compute_unwind_plan(
        target,
        current_state_hashes={"individuals": {"@I1@": "hbefore"}},  # already back as before
        current_refs={"individuals": set(), "families": set()},
    )
    assert plan["conflicts"] == []
    assert plan["safe"] == {}
    assert plan["noops"][0]["reason"] == "removed-but-present-as-before"


def test_removed_conflict_when_present_with_different_state():
    target = _diff(
        {"individuals": {"added": [], "modified": [], "removed": [{"entity_id": "@I1@", "before": {}, "before_hash": "hbefore"}]}}
    )
    plan = uw.compute_unwind_plan(
        target,
        current_state_hashes={"individuals": {"@I1@": "SOMETHING_ELSE"}},
        current_refs={"individuals": set(), "families": set()},
    )
    assert len(plan["conflicts"]) == 1
    assert plan["safe"] == {}


# --------------------------------------------------------------------------- #
# modified -> restore before
# --------------------------------------------------------------------------- #
def test_modified_safe_restore_when_current_is_after():
    before = {"gedcom_id": "@I1@", "payload_hash": "hbefore"}
    target = _diff(
        {
            "individuals": {
                "added": [],
                "modified": [
                    {"entity_id": "@I1@", "before": before, "after": {"y": 2}, "before_hash": "hbefore", "after_hash": "hafter"}
                ],
                "removed": [],
            }
        }
    )
    plan = uw.compute_unwind_plan(
        target,
        current_state_hashes={"individuals": {"@I1@": "hafter"}},  # current == after -> safe restore
        current_refs={"individuals": set(), "families": set()},
    )
    assert plan["conflicts"] == []
    # Codex P0-D: modified inverse carries both old_payload (current=after) and
    # new_payload (restore target=before).
    assert plan["safe"]["individuals"]["modified"] == [
        {"entity_id": "@I1@", "old_payload": {"y": 2}, "new_payload": before}
    ]


def test_modified_noop_when_already_restored():
    target = _diff(
        {
            "individuals": {
                "added": [],
                "modified": [{"entity_id": "@I1@", "before": {}, "after": {}, "before_hash": "hbefore", "after_hash": "hafter"}],
                "removed": [],
            }
        }
    )
    plan = uw.compute_unwind_plan(
        target,
        current_state_hashes={"individuals": {"@I1@": "hbefore"}},  # already at before
        current_refs={"individuals": set(), "families": set()},
    )
    assert plan["conflicts"] == []
    assert plan["safe"] == {}
    assert plan["noops"][0]["reason"] == "modified-already-restored"


def test_modified_conflict_when_current_matches_neither():
    target = _diff(
        {
            "individuals": {
                "added": [],
                "modified": [{"entity_id": "@I1@", "before": {}, "after": {}, "before_hash": "hbefore", "after_hash": "hafter"}],
                "removed": [],
            }
        }
    )
    plan = uw.compute_unwind_plan(
        target,
        current_state_hashes={"individuals": {"@I1@": "DRIFTED"}},
        current_refs={"individuals": set(), "families": set()},
    )
    assert len(plan["conflicts"]) == 1
    assert "matches neither" in plan["conflicts"][0]["reason"]


def test_modified_conflict_when_entity_deleted():
    target = _diff(
        {
            "individuals": {
                "added": [],
                "modified": [{"entity_id": "@I1@", "before": {}, "after": {}, "before_hash": "hbefore", "after_hash": "hafter"}],
                "removed": [],
            }
        }
    )
    plan = uw.compute_unwind_plan(
        target,
        current_state_hashes={"individuals": {}},  # deleted later
        current_refs={"individuals": set(), "families": set()},
    )
    assert len(plan["conflicts"]) == 1
    assert "deleted by a later version" in plan["conflicts"][0]["reason"]


# --------------------------------------------------------------------------- #
# plan -> apply shape + helpers
# --------------------------------------------------------------------------- #
def test_safe_plan_to_diffs_shape():
    safe = {"individuals": {"added": [{"entity_id": "@I1@", "new_payload": {}}], "modified": [], "removed": []}}
    diffs = uw.safe_plan_to_diffs(safe)
    assert diffs["individuals"]["added"] == [{"entity_id": "@I1@", "new_payload": {}}]
    assert diffs["individuals"]["removed"] == []
    assert diffs["individuals"]["entity_type"] == "individuals"


def test_plan_is_empty():
    assert uw.plan_is_empty({"safe": {}}) is True
    assert uw.plan_is_empty({"safe": {"individuals": {"added": [], "modified": [], "removed": []}}}) is True
    assert uw.plan_is_empty({"safe": {"individuals": {"added": [{"x": 1}], "modified": [], "removed": []}}}) is False


def test_mixed_conflict_blocks_whole_plan():
    """Any conflict means the whole unwind aborts (caller checks plan['conflicts'])."""
    target = _diff(
        {
            "individuals": {
                "added": [{"entity_id": "@I_safe@", "after_hash": "h1", "after": {}}],
                "modified": [{"entity_id": "@I_conflict@", "before": {}, "after": {}, "before_hash": "hb", "after_hash": "ha"}],
                "removed": [],
            }
        }
    )
    plan = uw.compute_unwind_plan(
        target,
        current_state_hashes={"individuals": {"@I_safe@": "h1", "@I_conflict@": "DRIFTED"}},
        current_refs={"individuals": set(), "families": set()},
    )
    # one safe op + one conflict; the caller must abort on any conflict
    assert len(plan["conflicts"]) == 1
    assert plan["safe"]["individuals"]["removed"] == [{"entity_id": "@I_safe@", "old_payload": {}}]


def test_removal_set_derived_from_added():
    target = _diff(
        {
            "individuals": {"added": [{"entity_id": "@I1@", "after_hash": "h", "after": {}}], "modified": [], "removed": []},
            "families": {"added": [{"entity_id": "@F1@", "after_hash": "h", "after": {}}], "modified": [], "removed": []},
        }
    )
    rs = uw._removal_set(target)
    assert rs == {"individuals": {"@I1@"}, "families": {"@F1@"}}


def test_added_family_graph_rolls_back_despite_internal_refs():
    """Codex P1-D: a self-contained added subgraph (family + its members +
    relationships, all added in the SAME version) must NOT block rollback even
    though the family/relationship reference the individuals — because those
    referencing entities are removed in the same unwind."""
    # Build current state where @F1@ references @I1@/@I2@ and a rel cites them.
    state = {
        "individuals": {
            "@I1@": {"gedcom_id": "@I1@", "payload_hash": "hi1"},
            "@I2@": {"gedcom_id": "@I2@", "payload_hash": "hi2"},
        },
        "families": {
            "@F1@": {
                "family_gedcom_id": "@F1@",
                "husband_xref": "@I1@",
                "wife_xref": "@I2@",
                "children_xrefs_json": [],
                "payload_hash": "hf1",
            }
        },
        "relationships": {
            "spouse|@F1@|@I1@|@I2@": {
                "edge_key": "spouse|@F1@|@I1@|@I2@",
                "individual_gedcom_id": "@I1@",
                "related_gedcom_id": "@I2@",
                "family_gedcom_id": "@F1@",
                "payload_hash": "hr1",
            }
        },
    }
    target_diff = {
        "entities": {
            "individuals": {
                "added": [
                    {"entity_id": "@I1@", "after_hash": "hi1", "after": state["individuals"]["@I1@"]},
                    {"entity_id": "@I2@", "after_hash": "hi2", "after": state["individuals"]["@I2@"]},
                ],
                "modified": [],
                "removed": [],
            },
            "families": {
                "added": [{"entity_id": "@F1@", "after_hash": "hf1", "after": state["families"]["@F1@"]}],
                "modified": [],
                "removed": [],
            },
            "relationships": {
                "added": [
                    {"entity_id": "spouse|@F1@|@I1@|@I2@", "after_hash": "hr1",
                     "after": state["relationships"]["spouse|@F1@|@I1@|@I2@"]}
                ],
                "modified": [],
                "removed": [],
            },
        }
    }

    removal_set = uw._removal_set(target_diff)
    hashes, refs = uw._hashes_and_refs_from_state(state, removal_set)
    plan = uw.compute_unwind_plan(target_diff, hashes, refs, removal_set)

    # No conflicts despite @I1@/@I2@ being referenced — refs come from entities
    # also being removed, so they're ignored.
    assert plan["conflicts"] == []
    assert {e["entity_id"] for e in plan["safe"]["individuals"]["removed"]} == {"@I1@", "@I2@"}
    assert plan["safe"]["families"]["removed"][0]["entity_id"] == "@F1@"

    # And the compensating diff serializes without KeyError (P0-D) — removed
    # entries carry old_payload.
    inverse = uw.safe_plan_to_diffs(plan["safe"])
    diff_gz = gh.build_diff_json_gz(inverse, version_number=11, base_version=10, source_hash=None,
                                    generated_at="2026-06-10T00:00:00Z")
    doc = gh.parse_diff_json_gz(diff_gz)
    assert len(doc["entities"]["individuals"]["removed"]) == 2


# --------------------------------------------------------------------------- #
# Executed unwind (fake conn + fake R2) — Codex P0-D
# --------------------------------------------------------------------------- #
class _UnwindCursor:
    """Fake cursor for the executed-unwind path."""

    def __init__(self, conn):
        self.conn = conn
        self._result = []

    def execute(self, sql, params=None):
        self.conn.executed.append((sql, params))
        n = re.sub(r"\s+", " ", sql).strip().lower()
        if "pg_advisory_xact_lock" in n:
            self._result = [(True,)]
        elif n.startswith("select version_number, source_hash, artifact_prefix from gedcom_versions") and "order by version_number desc" in n:
            # latest applied (and also _fetch_version_row default target)
            self._result = [self.conn.latest_row]
        elif n.startswith("select version_number, source_hash, artifact_prefix from gedcom_versions"):
            self._result = [self.conn.latest_row]
        elif "coalesce(max(version_number)" in n:
            self._result = [(self.conn.max_version,)]
        elif n.startswith("insert into gedcom_versions"):
            self.conn.version_insert_params = params
            self._result = []
        elif n.startswith("insert into") or n.startswith("delete from"):
            self.conn.applied_ops.append(n.split()[0] + ":" + (n.split("into ")[-1].split()[0] if "into" in n else n.split("from ")[-1].split()[0]))
            self._result = []
        else:
            self._result = []

    def fetchone(self):
        return self._result[0] if self._result else None

    def fetchall(self):
        return list(self._result)

    def close(self):
        pass


class _UnwindConn:
    def __init__(self, latest_row, max_version):
        self.latest_row = latest_row
        self.max_version = max_version
        self.executed = []
        self.applied_ops = []
        self.committed = False
        self.rolled_back = False
        self.closed = False
        self.version_insert_params = None

    def cursor(self):
        return _UnwindCursor(self)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class _UnwindR2:
    def __init__(self):
        self.store = {}

    def put_object(self, Bucket, Key, Body):
        self.store[(Bucket, Key)] = Body

    def get_object(self, Bucket, Key):
        data = self.store[(Bucket, Key)]
        return {"Body": SimpleNamespace(read=lambda: data)}


def _gz_diff(entities):
    doc = {"schema_version": 1, "version_number": 10, "base_version": 9,
           "source_hash": None, "generated_at": "2026-06-10T00:00:00Z", "entities": entities}
    return gzip.compress(json.dumps(doc, sort_keys=True).encode("utf-8"), mtime=0)


def test_executed_unwind_uploads_snapshot_and_compensating_diff(monkeypatch):
    """Codex P0-D: executed unwind serializes the compensating diff (no KeyError),
    uploads a resulting-state snapshot, and inserts a v1 version with a snapshot
    sha."""
    # execute_values routes through the cursor for apply_entity_diffs.
    import psycopg2.extras

    def fake_execute_values(cur, sql, argslist, *a, **kw):
        cur.execute(sql, list(argslist))

    monkeypatch.setattr(psycopg2.extras, "execute_values", fake_execute_values)

    bucket = imp._r2_bucket()
    target_prefix = "gedcom-history/rhodesli/v0010-aaa/"

    # Current state (latest snapshot) has one added individual @I1@.
    indiv = {"gedcom_id": "@I1@", "payload_hash": "h1"}
    snapshot_lines = json.dumps(
        {"entity_type": "individuals", "entity_id": "@I1@", "payload": indiv, "payload_hash": "h1"},
        sort_keys=True,
    ) + "\n"
    snapshot_gz = gzip.compress(snapshot_lines.encode("utf-8"), mtime=0)

    target_diff_entities = {
        "individuals": {"added": [{"entity_id": "@I1@", "after_hash": "h1", "after": indiv}],
                        "modified": [], "removed": []}
    }

    r2 = _UnwindR2()
    r2.store[(bucket, target_prefix + "diff.json.gz")] = _gz_diff(target_diff_entities)
    r2.store[(bucket, target_prefix + "snapshot.jsonl.gz")] = snapshot_gz

    latest_row = (10, None, target_prefix)
    conn = _UnwindConn(latest_row=latest_row, max_version=10)

    result = uw.unwind(
        version_number=None,
        execute=True,
        conn_factory=lambda: conn,
        r2_factory=lambda: r2,
        generated_at="2026-06-10T00:00:00Z",
    )

    assert result["ok"] is True
    assert result["execute"] is True
    assert result["compensating_version"] == 11
    assert conn.committed is True
    new_prefix = gh.artifact_prefix("rhodesli", 11, None)
    # Both the compensating diff AND a resulting-state snapshot were uploaded.
    assert (bucket, new_prefix + "diff.json.gz") in r2.store
    assert (bucket, new_prefix + "snapshot.jsonl.gz") in r2.store
    # The resulting snapshot is EMPTY (the only individual was removed).
    result_snap = gh.reconstruct_version_from_snapshot(r2.store[(bucket, new_prefix + "snapshot.jsonl.gz")])
    assert result_snap == {}
    # The version INSERT carried a non-null snapshot sha (never v1 without snapshot).
    assert conn.version_insert_params is not None
    assert any(isinstance(p, str) and len(p) == 64 for p in conn.version_insert_params)
