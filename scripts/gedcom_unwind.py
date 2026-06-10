#!/usr/bin/env python3
"""Conservative GEDCOM version unwind (PRD-064 Option B-plus, Session 164).

Reverts a GEDCOM version by applying its INVERSE as a NEW compensating
``applied`` version through the same atomic transaction path as the importer.
It NEVER reverse-replays and NEVER destroys a later change: any unsafe state is
reported as a CONFLICT and the whole unwind aborts (no `--force`, plan R5 /
Codex P0-6).

Safety rules (per entity in the target version's diff):
  * added    -> delete iff current_hash == after_hash AND no current family /
                relationship references the entity (referential integrity).
                Already-absent = no-op.
  * removed  -> re-add the `before` payload iff the entity is currently absent.
                Already-present-with-before = no-op.
  * modified -> restore `before` iff current_hash == after_hash.
                Already-restored (current_hash == before_hash) = no-op.
  * anything else -> CONFLICT (a later version changed it) -> abort + report.

The compensating change is itself a fully-auditable new version with its own R2
artifacts (raw=NULL) and is itself unwindable.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import scripts.import_gedcom_version as imp  # noqa: E402
from rhodesli_ml.importers import gedcom_history as gh  # noqa: E402

logger = logging.getLogger(__name__)

# Entity types whose deletion needs a referential-integrity check.
REFERENCEABLE_TYPES = ("individuals", "families")


# --------------------------------------------------------------------------- #
# Reconstruct
# --------------------------------------------------------------------------- #
def reconstruct_version(
    r2_client, bucket: str, community: str, version_row: dict[str, Any]
) -> dict[str, dict[str, dict[str, Any]]]:
    """Reconstruct the full current-state at a version from its R2 snapshot.

    `version_row` must carry `artifact_prefix`. Returns
    ``{entity_type -> {entity_id -> payload}}``.
    """
    prefix = version_row["artifact_prefix"]
    snapshot_bytes = gh.download_snapshot(r2_client, bucket, prefix)
    return gh.reconstruct_version_from_snapshot(snapshot_bytes)


# --------------------------------------------------------------------------- #
# Plan computation (pure)
# --------------------------------------------------------------------------- #
def compute_unwind_plan(
    target_diff: dict[str, Any],
    current_state_hashes: dict[str, dict[str, str]],
    current_refs: dict[str, set[str]],
) -> dict[str, Any]:
    """Compute the conservative inverse of a version's diff.

    Args:
      target_diff: the parsed diff.json doc (``{entities:{<type>:{added,
        modified,removed}}}``) of the version being reverted.
      current_state_hashes: ``{entity_type -> {entity_id -> current payload_hash}}``
        for the live current state. Absence of an id means the entity is gone.
      current_refs: ``{entity_type -> set(entity_id)}`` — ids of `individuals` /
        `families` still referenced by any current family/relationship. Used for
        the deletion referential-integrity check.

    Returns ``{"safe": {<type>:{added:[],modified:[],removed:[]}}, "conflicts":
    [...], "noops": [...]}``. The `safe` structure is shaped for
    `inverse_diffs_to_apply` -> `apply_entity_diffs`.
    """
    safe: dict[str, dict[str, list[dict[str, Any]]]] = {}
    conflicts: list[dict[str, Any]] = []
    noops: list[dict[str, Any]] = []

    entities = target_diff.get("entities", {})
    for entity_type, type_diff in entities.items():
        type_hashes = current_state_hashes.get(entity_type, {})
        refs = current_refs.get(entity_type, set())

        for item in type_diff.get("added", []):
            entity_id = item["entity_id"]
            after_hash = item.get("after_hash")
            current_hash = type_hashes.get(entity_id)
            if current_hash is None:
                # already deleted by something else -> nothing to undo
                noops.append({"entity_type": entity_type, "entity_id": entity_id, "reason": "added-absent"})
            elif current_hash != after_hash:
                conflicts.append(
                    {
                        "entity_type": entity_type,
                        "entity_id": entity_id,
                        "change_type": "added",
                        "reason": "current_hash != after_hash (later version modified it)",
                    }
                )
            elif entity_type in REFERENCEABLE_TYPES and entity_id in refs:
                conflicts.append(
                    {
                        "entity_type": entity_type,
                        "entity_id": entity_id,
                        "change_type": "added",
                        "reason": "still referenced by a current family/relationship",
                    }
                )
            else:
                # safe to delete -> inverse op = "removed"
                _add_inverse(safe, entity_type, "removed", entity_id, item.get("after"))

        for item in type_diff.get("removed", []):
            entity_id = item["entity_id"]
            before = item.get("before")
            current_hash = type_hashes.get(entity_id)
            if current_hash is None:
                # currently absent -> safe to re-add `before`
                _add_inverse(safe, entity_type, "added", entity_id, before, before_payload=before)
            elif current_hash == item.get("before_hash"):
                noops.append({"entity_type": entity_type, "entity_id": entity_id, "reason": "removed-but-present-as-before"})
            else:
                conflicts.append(
                    {
                        "entity_type": entity_type,
                        "entity_id": entity_id,
                        "change_type": "removed",
                        "reason": "entity present with a different state (later version re-added/changed it)",
                    }
                )

        for item in type_diff.get("modified", []):
            entity_id = item["entity_id"]
            after_hash = item.get("after_hash")
            before_hash = item.get("before_hash")
            before = item.get("before")
            current_hash = type_hashes.get(entity_id)
            if current_hash is None:
                conflicts.append(
                    {
                        "entity_type": entity_type,
                        "entity_id": entity_id,
                        "change_type": "modified",
                        "reason": "entity deleted by a later version",
                    }
                )
            elif current_hash == before_hash:
                noops.append({"entity_type": entity_type, "entity_id": entity_id, "reason": "modified-already-restored"})
            elif current_hash == after_hash:
                # safe to restore `before` -> inverse op = "modified" back to before
                _add_inverse(safe, entity_type, "modified", entity_id, before, before_payload=before)
            else:
                conflicts.append(
                    {
                        "entity_type": entity_type,
                        "entity_id": entity_id,
                        "change_type": "modified",
                        "reason": "current_hash matches neither before nor after (later version changed it)",
                    }
                )

    return {"safe": safe, "conflicts": conflicts, "noops": noops}


def _add_inverse(
    safe: dict[str, dict[str, list[dict[str, Any]]]],
    entity_type: str,
    inverse_change: str,
    entity_id: str,
    payload: Any,
    before_payload: Any = None,
):
    bucket = safe.setdefault(entity_type, {"added": [], "modified": [], "removed": []})
    if inverse_change == "removed":
        bucket["removed"].append({"entity_id": entity_id})
    elif inverse_change == "added":
        bucket["added"].append({"entity_id": entity_id, "new_payload": payload})
    elif inverse_change == "modified":
        bucket["modified"].append({"entity_id": entity_id, "new_payload": payload})


def safe_plan_to_diffs(safe: dict[str, dict[str, list[dict[str, Any]]]]) -> dict[str, dict[str, Any]]:
    """Shape the `safe` plan into the diff dict apply_entity_diffs consumes."""
    diffs: dict[str, dict[str, Any]] = {}
    for entity_type, ops in safe.items():
        diffs[entity_type] = {
            "entity_type": entity_type,
            "added": ops.get("added", []),
            "modified": ops.get("modified", []),
            "removed": ops.get("removed", []),
        }
    return diffs


def plan_is_empty(plan: dict[str, Any]) -> bool:
    for ops in plan.get("safe", {}).values():
        if ops.get("added") or ops.get("modified") or ops.get("removed"):
            return False
    return True


# --------------------------------------------------------------------------- #
# Live unwind (default target = latest applied version)
# --------------------------------------------------------------------------- #
def _fetch_version_row(cur, community: str, version_number: int | None) -> dict[str, Any] | None:
    if version_number is None:
        cur.execute(
            "SELECT version_number, source_hash, artifact_prefix FROM gedcom_versions "
            "WHERE community_id = %s AND status = 'applied' "
            "ORDER BY version_number DESC LIMIT 1",
            (community,),
        )
    else:
        cur.execute(
            "SELECT version_number, source_hash, artifact_prefix FROM gedcom_versions "
            "WHERE community_id = %s AND status = 'applied' AND version_number = %s",
            (community, version_number),
        )
    row = cur.fetchone()
    if not row:
        return None
    return {"version_number": row[0], "source_hash": row[1], "artifact_prefix": row[2]}


def _load_current_hashes_and_refs(conn, community: str):
    """Read current payload_hash maps + referenced-id sets for ref-integrity."""
    maps = imp.load_current_maps(conn, community)
    hashes: dict[str, dict[str, str]] = {}
    for entity_type, entity_map in maps.items():
        hashes[entity_type] = {eid: p.get("payload_hash") for eid, p in entity_map.items()}

    # An individual/family is "referenced" if any current relationship cites it.
    referenced_individuals: set[str] = set()
    referenced_families: set[str] = set()
    for rel in maps.get("relationships", {}).values():
        if rel.get("individual_gedcom_id"):
            referenced_individuals.add(rel["individual_gedcom_id"])
        if rel.get("related_gedcom_id"):
            referenced_individuals.add(rel["related_gedcom_id"])
        if rel.get("family_gedcom_id"):
            referenced_families.add(rel["family_gedcom_id"])
    # A family also references its member individuals via its payload columns.
    for fam in maps.get("families", {}).values():
        for key in ("husband_xref", "wife_xref"):
            if fam.get(key):
                referenced_individuals.add(fam[key])
        for child in fam.get("children_xrefs_json") or []:
            referenced_individuals.add(child)

    refs = {"individuals": referenced_individuals, "families": referenced_families}
    return hashes, refs


def unwind(
    version_number: int | None = None,
    community: str = imp.DEFAULT_COMMUNITY,
    execute: bool = False,
    conn_factory: Callable[[], Any] | None = None,
    r2_factory: Callable[[], Any] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Plan (and optionally apply) a conservative unwind of a version.

    Default target = the latest applied version (true rollback). On ANY conflict,
    abort + report (no DB change). Otherwise apply the inverse as a NEW
    compensating applied version through the same atomic txn path.
    """
    conn_factory = conn_factory or imp.default_conn_factory
    r2_factory = r2_factory or imp.default_r2_factory
    generated_at = generated_at or datetime.now(timezone.utc).isoformat()

    conn = conn_factory()
    r2_client = r2_factory()
    bucket = imp._r2_bucket()
    try:
        cur = conn.cursor()
        cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (imp._community_lock_key(community),))

        version_row = _fetch_version_row(cur, community, version_number)
        if not version_row:
            conn.rollback()
            return {"ok": False, "error": "no matching applied version", "version_number": version_number}
        if not version_row.get("artifact_prefix"):
            conn.rollback()
            return {
                "ok": False,
                "error": "version has no R2 artifacts (legacy) — cannot unwind",
                "version_number": version_row["version_number"],
            }

        target_diff = gh.download_diff(r2_client, bucket, version_row["artifact_prefix"])
        current_hashes, current_refs = _load_current_hashes_and_refs(conn, community)
        plan = compute_unwind_plan(target_diff, current_hashes, current_refs)

        if plan["conflicts"]:
            conn.rollback()
            return {
                "ok": False,
                "aborted": True,
                "reason": "conflicts",
                "target_version": version_row["version_number"],
                "conflicts": plan["conflicts"],
                "noops": plan["noops"],
            }

        if plan_is_empty(plan):
            conn.rollback()
            return {
                "ok": True,
                "noop": True,
                "target_version": version_row["version_number"],
                "noops": plan["noops"],
            }

        if not execute:
            conn.rollback()
            return {
                "ok": True,
                "execute": False,
                "target_version": version_row["version_number"],
                "safe": plan["safe"],
                "noops": plan["noops"],
            }

        # Apply the compensating change as a NEW applied version.
        cur.execute(
            "SELECT COALESCE(MAX(version_number), 0) FROM gedcom_versions WHERE community_id = %s",
            (community,),
        )
        new_version = cur.fetchone()[0] + 1
        inverse_diffs = safe_plan_to_diffs(plan["safe"])
        imp.apply_entity_diffs(conn, community, inverse_diffs, new_version)

        diff_summary = gh.build_diff_summary(inverse_diffs)
        prefix = gh.artifact_prefix(community, new_version, None)
        diff_gz = gh.build_diff_json_gz(
            inverse_diffs,
            version_number=new_version,
            base_version=version_row["version_number"],
            source_hash=None,
            generated_at=generated_at,
        )
        # snapshot of the resulting state is rebuilt from the reconstructed
        # target-before state is non-trivial here; we persist the compensating
        # diff (raw=NULL). A full resulting-state snapshot is produced by the
        # next import; the diff artifact + manifest fully describe the change.
        shas = gh.upload_and_verify_artifacts(
            r2_client, bucket, prefix, {"raw.ged.gz": None, "diff.json.gz": diff_gz}
        )

        cur.execute(
            "INSERT INTO gedcom_versions (version_number, community_id, imported_at, "
            "imported_by, source_file, source_hash, summary, notes, status, "
            "raw_artifact_sha256, diff_artifact_sha256, artifact_prefix, diff_summary, "
            "artifact_format) VALUES (%s, %s, now(), %s, %s, %s, %s::jsonb, %s, 'applied', "
            "NULL, %s, %s, %s::jsonb, 'v1')",
            (
                new_version,
                community,
                "unwind",
                f"compensating-unwind-of-v{version_row['version_number']}",
                None,
                json.dumps(diff_summary),
                f"Conservative unwind of v{version_row['version_number']}",
                shas.get("diff.json.gz"),
                prefix,
                json.dumps(diff_summary),
            ),
        )

        conn.commit()
        return {
            "ok": True,
            "execute": True,
            "target_version": version_row["version_number"],
            "compensating_version": new_version,
            "diff_summary": diff_summary,
            "noops": plan["noops"],
        }
    except Exception:
        conn.rollback()
        logger.exception("Unwind failed — rolled back (ZERO rows changed)")
        raise
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Conservative GEDCOM version unwind (PRD-064)")
    parser.add_argument("--version", type=int, default=None, help="Version to revert (default: latest applied)")
    parser.add_argument("--community", default=imp.DEFAULT_COMMUNITY)
    parser.add_argument("--execute", action="store_true", help="Apply (default: plan only)")
    args = parser.parse_args(argv)

    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:  # pragma: no cover
        pass

    result = unwind(version_number=args.version, community=args.community, execute=args.execute)
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
