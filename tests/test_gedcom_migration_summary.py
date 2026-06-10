"""Unit test for the Session 164 migration's baseline diff_summary builder.

Pure function only — NO live DB, NO network. Validates the 5-type IDs-inclusive
shape (Codex P0-B / P2) and the sources/media-omitted note.
"""

from __future__ import annotations

import json

import scripts.session164_migrate_to_current_state as m
from rhodesli_ml.importers import gedcom_history as gh


def test_baseline_diff_summary_is_five_type_ids_inclusive():
    summary = m.build_baseline_diff_summary(
        {"individuals": 3, "families": 2, "relationships": 5},
        {"individuals": ["@I1@", "@I2@", "@I3@"]},
    )
    # Exactly the 5 DIFF_ENTITY_TYPES (plus the "note" key).
    type_keys = {k for k in summary if k != "note"}
    assert type_keys == set(gh.DIFF_ENTITY_TYPES)

    # Each type has the canonical {added, modified, removed, ids:{...}} shape.
    for et in gh.DIFF_ENTITY_TYPES:
        block = summary[et]
        assert set(block) == {"added", "modified", "removed", "ids"}
        assert set(block["ids"]) == {"added", "modified", "removed"}
        assert block["modified"] == 0
        assert block["removed"] == 0
        assert block["ids"]["modified"] == []
        assert block["ids"]["removed"] == []

    assert summary["individuals"]["added"] == 3
    assert summary["individuals"]["ids"]["added"] == ["@I1@", "@I2@", "@I3@"]
    assert summary["relationships"]["added"] == 5
    # sources/media present but empty (DB doesn't carry them in the baseline).
    assert summary["sources"]["added"] == 0
    assert summary["media_objects"]["added"] == 0


def test_baseline_diff_summary_note_documents_sources_media_omission():
    summary = m.build_baseline_diff_summary({"individuals": 1, "families": 0, "relationships": 0})
    assert "note" in summary
    note = summary["note"].lower()
    assert "sources/media" in note or "sources" in note
    assert "baseline" in note
    # Serializes cleanly (goes into a jsonb column).
    json.dumps(summary)


def test_baseline_diff_summary_counts_default_to_id_lengths():
    summary = m.build_baseline_diff_summary({}, {"families": ["@F1@", "@F2@"]})
    assert summary["families"]["added"] == 2
    assert summary["families"]["ids"]["added"] == ["@F1@", "@F2@"]
