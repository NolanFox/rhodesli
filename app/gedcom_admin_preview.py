"""Adapter: atomic-importer dry-run result -> admin GEDCOM diff-preview shape.

Session 164 (PRD-064). The new ``scripts.import_gedcom_version.run_import``
returns a compact result for the dry-run::

    {
      "execute": False,
      "source_hash": "...",
      "counts": {"individuals": N, "families": N, ...},
      "diff_summary": {
        "individuals": {"added": N, "modified": N, "removed": N,
                        "ids": {"added": [...], "modified": [...], "removed": [...]}},
        "families": {...}, "relationships": {...}, "sources": {...},
        "media_objects": {...},
      },
    }

The admin GEDCOM upload UI (``app/admin_routes.py``) was written against the old
``import_versioned`` shape (top-level added/modified/removed counts +
``entity_summaries`` + ``sample_changes`` + ``schema_ready``). This adapter maps
the new diff_summary into that shape so the existing rendering keeps working
without a UI rewrite.

NOTE: the dry-run diffs against the CURRENT canonical state, so ``modified``/
``removed`` are meaningful. ``sample_changes`` is best-effort (IDs only — the
new diff_summary intentionally keeps payloads out of the summary; they live in
R2), so we surface changed entity IDs rather than field-level diffs.
"""

from __future__ import annotations

from typing import Any

# UI entity keys -> diff_summary keys. The UI also shows events/records which the
# canonical importer does not diff into the DB; those show 0 and are harmless.
_ENTITY_KEYS = (
    "individuals",
    "families",
    "relationships",
    "sources",
    "media_objects",
)


def build_diff_preview_result(preview: dict[str, Any]) -> dict[str, Any]:
    """Map a run_import dry-run result to the legacy diff-preview dict."""
    diff_summary = preview.get("diff_summary") or {}

    total_added = 0
    total_modified = 0
    total_removed = 0
    entity_summaries: dict[str, dict[str, int]] = {}
    sample_changes: list[dict[str, Any]] = []

    for key in _ENTITY_KEYS:
        per = diff_summary.get(key) or {}
        added = int(per.get("added", 0) or 0)
        modified = int(per.get("modified", 0) or 0)
        removed = int(per.get("removed", 0) or 0)
        entity_summaries[key] = {"added": added, "modified": modified, "removed": removed}
        total_added += added
        total_modified += modified
        total_removed += removed

        # Best-effort sample (IDs only) — prefer modified, then added, then removed.
        ids = per.get("ids") or {}
        for change_type in ("modified", "added", "removed"):
            for entity_id in (ids.get(change_type) or [])[:3]:
                if len(sample_changes) >= 5:
                    break
                sample_changes.append(
                    {
                        "entity_type": key,
                        "entity_id": entity_id,
                        "changes": [{"path": change_type, "old_value": None, "new_value": change_type}],
                    }
                )

    return {
        "skipped": False,
        "schema_ready": True,
        "missing_tables": [],
        "added": total_added,
        "modified": total_modified,
        "removed": total_removed,
        # The atomic importer doesn't compute an "unchanged" count in the summary;
        # it's not load-bearing for the preview badges.
        "unchanged": 0,
        "entity_summaries": entity_summaries,
        "sample_changes": sample_changes,
        "redirects": {},
        "source_hash": preview.get("source_hash"),
        # Pass through for the apply step.
        "_run_import_preview": preview,
    }
