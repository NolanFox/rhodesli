"""Conservative unwind plan tests (Session 164, PRD-064).

Pure logic — NO live DB, NO network. Validates conflict detection, no-op cases,
and referential-integrity refusal in `compute_unwind_plan`.
"""

from __future__ import annotations

import scripts.gedcom_unwind as uw


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
    assert plan["safe"]["individuals"]["removed"] == [{"entity_id": "@I1@"}]


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
    assert plan["safe"]["individuals"]["modified"] == [{"entity_id": "@I1@", "new_payload": before}]


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
    assert plan["safe"]["individuals"]["removed"] == [{"entity_id": "@I_safe@"}]
