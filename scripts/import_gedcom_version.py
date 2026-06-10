#!/usr/bin/env python3
"""Atomic GEDCOM importer (PRD-064 Option B-plus, Session 164).

Replaces the old non-atomic, per-batch-commit, multi-state versioned importer
(root cause of the Session 163 1.3 GB bloat — Lesson 199). The new importer is
a SINGLE Postgres transaction: a failed import leaves ZERO rows (no partial
state, no `failed` version row).

Flow (plan R3, Codex P0-1/P0-2/P1-1):

    raw_bytes = read(file); source_hash = sha256(raw_bytes)
    parsed    = parse_gedcom(file); bundle = build_snapshot_bundle(parsed)
    conn (pooler 5432, autocommit=False)
    BEGIN
      pg_advisory_xact_lock(hashtext('gedcom_import:'||community))   # serialize
      if applied version with source_hash exists: ROLLBACK -> idempotent no-op
      version_number = MAX(version_number)+1  for community
      old = load_current_maps(conn, community)        # id -> payload-ish (+payload_hash)
      diffs = diff_entity_maps(et, old[et], new[et])  # canonical payloads only
      artifacts = build raw.ged.gz / snapshot.jsonl.gz / diff.json.gz
      upload_and_verify(artifacts)                    # re-download + hash check; fail -> raise
      apply diffs: upsert added/modified, delete removed (individuals/families);
                   relationships: delete removed edges + upsert added/modified
      INSERT gedcom_versions(status='applied', artifact shas, prefix, diff_summary)
    COMMIT
    # any exception anywhere -> conn.rollback() -> ZERO rows changed

The DB stores only typed columns + payload_hash (current-state, one row per
entity); the lossless full payload lives in R2 (gedcom_history).

This script DOES NOT run against the live DB on import. `run_import` accepts
injectable `conn_factory` and `r2_factory` so tests exercise the full code path
with fakes. Dry-run (`--execute` absent) stops after the diff + prints a
summary (no R2, no DB writes).
"""

from __future__ import annotations

import argparse
import hashlib
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

from rhodesli_ml.importers.gedcom_parser import parse_gedcom  # noqa: E402
from rhodesli_ml.importers.gedcom_snapshot import (  # noqa: E402
    build_snapshot_bundle,
    diff_entity_maps,
)
from rhodesli_ml.importers import gedcom_history as gh  # noqa: E402

logger = logging.getLogger(__name__)

DEFAULT_COMMUNITY = "rhodesli"

# Entity types that map to their own canonical tables (diffed + applied).
DIFF_TYPES = ("individuals", "families", "relationships", "sources", "media_objects")

# Bundle payload fields persisted to each canonical table, in column order.
INDIVIDUAL_COLUMNS = [
    "gedcom_id",
    "name",
    "given_name",
    "surname",
    "gender",
    "birth_date",
    "birth_place",
    "death_date",
    "death_place",
    "names_json",
    "events_json",
    "family_as_spouse_json",
    "family_as_child_json",
    "notes_json",
    "citations_json",
    "payload_hash",
]
INDIVIDUAL_JSON_COLUMNS = {
    "names_json",
    "events_json",
    "family_as_spouse_json",
    "family_as_child_json",
    "notes_json",
    "citations_json",
}

FAMILY_COLUMNS = [
    "family_gedcom_id",
    "husband_xref",
    "wife_xref",
    "children_xrefs_json",
    "marriage_event_json",
    "events_json",
    "notes_json",
    "citations_json",
    "payload_hash",
]
FAMILY_JSON_COLUMNS = {
    "children_xrefs_json",
    "marriage_event_json",
    "events_json",
    "notes_json",
    "citations_json",
}


# --------------------------------------------------------------------------- #
# Connection
# --------------------------------------------------------------------------- #
def default_conn_factory():
    """Open a psycopg2 connection on the Supabase pooler session port (5432).

    Uses SUPABASE_DB_PASSWORD from the environment. autocommit=False so the
    whole import is one transaction.
    """
    import psycopg2

    project_ref = os.environ.get("SUPABASE_PROJECT_REF", "fvynibivlphxwfowzkjl")
    region = os.environ.get("SUPABASE_POOLER_REGION", "us-west-2")
    conn = psycopg2.connect(
        host=os.environ.get(
            "SUPABASE_POOLER_HOST", f"aws-0-{region}.pooler.supabase.com"
        ),
        port=int(os.environ.get("SUPABASE_POOLER_PORT", "5432")),
        user=os.environ.get("SUPABASE_POOLER_USER", f"postgres.{project_ref}"),
        password=os.environ["SUPABASE_DB_PASSWORD"],
        dbname=os.environ.get("SUPABASE_DB_NAME", "postgres"),
    )
    conn.autocommit = False
    return conn


def default_r2_factory():
    import boto3

    account_id = os.environ["R2_ACCOUNT_ID"]
    return boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
    )


def _r2_bucket() -> str:
    return os.environ.get("R2_BUCKET_NAME", "rhodesli-archive")


# --------------------------------------------------------------------------- #
# Current-state readers (inside the open txn)
# --------------------------------------------------------------------------- #
def load_current_maps(conn, community: str) -> dict[str, dict[str, dict[str, Any]]]:
    """Read canonical current-state maps for diffing.

    Returns ``{entity_type -> {entity_id -> {..., 'payload_hash': ...}}}``.
    Only ``payload_hash`` and the natural id matter for diffing (diff_entity_maps
    short-circuits on equal hashes); the typed columns are included so the diff's
    ``before`` payloads are usable for unwind reconstruction context.
    """
    cur = conn.cursor()
    maps: dict[str, dict[str, dict[str, Any]]] = {et: {} for et in DIFF_TYPES}

    # individuals
    cur.execute(
        f"SELECT {', '.join(INDIVIDUAL_COLUMNS)} FROM gedcom_individuals "
        "WHERE community_id = %s",
        (community,),
    )
    for row in cur.fetchall():
        payload = _row_to_payload(INDIVIDUAL_COLUMNS, row)
        maps["individuals"][payload["gedcom_id"]] = payload

    # families
    cur.execute(
        f"SELECT {', '.join(FAMILY_COLUMNS)} FROM gedcom_families "
        "WHERE community_id = %s",
        (community,),
    )
    for row in cur.fetchall():
        payload = _row_to_payload(FAMILY_COLUMNS, row)
        maps["families"][payload["family_gedcom_id"]] = payload

    # relationships
    cur.execute(
        "SELECT edge_key, individual_gedcom_id, related_gedcom_id, "
        "relationship_type, family_gedcom_id, relationship_payload, payload_hash "
        "FROM gedcom_relationships WHERE community_id = %s",
        (community,),
    )
    for row in cur.fetchall():
        edge_key, ind, rel, rtype, fam, payload, payload_hash = row
        maps["relationships"][edge_key] = {
            "edge_key": edge_key,
            "individual_gedcom_id": ind,
            "related_gedcom_id": rel,
            "relationship_type": rtype,
            "family_gedcom_id": fam,
            "relationship_payload": payload,
            "payload_hash": payload_hash,
        }

    # sources / media_objects: canonical tables not part of the current
    # current-state DB schema (Session 164 stores them only in R2 snapshot).
    # They still get diffed (against empty), so the R2 diff records them.
    cur.close()
    return maps


def _row_to_payload(columns: list[str], row: tuple) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for col, value in zip(columns, row):
        payload[col] = value
    return payload


# --------------------------------------------------------------------------- #
# Bundle payload -> canonical table column row
# --------------------------------------------------------------------------- #
def individual_row_values(community: str, payload: dict[str, Any], version_number: int):
    """Map a bundle individual payload to the canonical column tuple."""
    return _typed_row_values(
        community, INDIVIDUAL_COLUMNS, INDIVIDUAL_JSON_COLUMNS, payload, version_number
    )


def family_row_values(community: str, payload: dict[str, Any], version_number: int):
    return _typed_row_values(
        community, FAMILY_COLUMNS, FAMILY_JSON_COLUMNS, payload, version_number
    )


def _typed_row_values(
    community: str,
    columns: list[str],
    json_columns: set[str],
    payload: dict[str, Any],
    version_number: int,
):
    values: list[Any] = [community]
    for col in columns:
        value = payload.get(col)
        if col in json_columns:
            value = json.dumps(value if value is not None else None)
        values.append(value)
    values.append(version_number)
    return tuple(values)


# --------------------------------------------------------------------------- #
# Mutation helpers (shared with gedcom_unwind via apply_entity_diffs)
# --------------------------------------------------------------------------- #
def apply_entity_diffs(conn, community: str, diffs: dict[str, dict[str, Any]], version_number: int):
    """Apply per-type diffs to canonical tables inside the open txn.

    individuals/families: upsert added+modified (ON CONFLICT DO UPDATE), delete
    removed. relationships: delete removed edges, upsert added+modified edges.
    """
    from psycopg2.extras import execute_values

    cur = conn.cursor()

    # ----- individuals -----
    ind_diff = diffs.get("individuals")
    if ind_diff:
        upserts = [
            individual_row_values(community, e["new_payload"], version_number)
            for e in ind_diff["added"] + ind_diff["modified"]
        ]
        if upserts:
            cols = ["community_id"] + INDIVIDUAL_COLUMNS + ["version_number"]
            update_cols = [c for c in INDIVIDUAL_COLUMNS if c != "gedcom_id"] + ["version_number"]
            set_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)
            execute_values(
                cur,
                f"INSERT INTO gedcom_individuals ({', '.join(cols)}) VALUES %s "
                f"ON CONFLICT (community_id, gedcom_id) DO UPDATE SET {set_clause}, updated_at = now()",
                upserts,
            )
        removed_ids = [e["entity_id"] for e in ind_diff["removed"]]
        if removed_ids:
            cur.execute(
                "DELETE FROM gedcom_individuals WHERE community_id = %s AND gedcom_id = ANY(%s)",
                (community, removed_ids),
            )

    # ----- families -----
    fam_diff = diffs.get("families")
    if fam_diff:
        upserts = [
            family_row_values(community, e["new_payload"], version_number)
            for e in fam_diff["added"] + fam_diff["modified"]
        ]
        if upserts:
            cols = ["community_id"] + FAMILY_COLUMNS + ["version_number"]
            update_cols = [c for c in FAMILY_COLUMNS if c != "family_gedcom_id"] + ["version_number"]
            set_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)
            execute_values(
                cur,
                f"INSERT INTO gedcom_families ({', '.join(cols)}) VALUES %s "
                f"ON CONFLICT (community_id, family_gedcom_id) DO UPDATE SET {set_clause}, updated_at = now()",
                upserts,
            )
        removed_ids = [e["entity_id"] for e in fam_diff["removed"]]
        if removed_ids:
            cur.execute(
                "DELETE FROM gedcom_families WHERE community_id = %s AND family_gedcom_id = ANY(%s)",
                (community, removed_ids),
            )

    # ----- relationships -----
    rel_diff = diffs.get("relationships")
    if rel_diff:
        removed_edges = [e["entity_id"] for e in rel_diff["removed"]]
        if removed_edges:
            cur.execute(
                "DELETE FROM gedcom_relationships WHERE community_id = %s AND edge_key = ANY(%s)",
                (community, removed_edges),
            )
        rel_upserts = []
        for e in rel_diff["added"] + rel_diff["modified"]:
            p = e["new_payload"]
            rel_upserts.append(
                (
                    community,
                    p["edge_key"],
                    p["individual_gedcom_id"],
                    p["related_gedcom_id"],
                    p["relationship_type"],
                    p["family_gedcom_id"],
                    json.dumps(p.get("relationship_payload") or {}),
                    p["payload_hash"],
                    version_number,
                )
            )
        if rel_upserts:
            execute_values(
                cur,
                "INSERT INTO gedcom_relationships (community_id, edge_key, "
                "individual_gedcom_id, related_gedcom_id, relationship_type, "
                "family_gedcom_id, relationship_payload, payload_hash, version_number) "
                "VALUES %s ON CONFLICT (community_id, edge_key) DO UPDATE SET "
                "individual_gedcom_id = EXCLUDED.individual_gedcom_id, "
                "related_gedcom_id = EXCLUDED.related_gedcom_id, "
                "relationship_type = EXCLUDED.relationship_type, "
                "family_gedcom_id = EXCLUDED.family_gedcom_id, "
                "relationship_payload = EXCLUDED.relationship_payload, "
                "payload_hash = EXCLUDED.payload_hash, "
                "version_number = EXCLUDED.version_number",
                rel_upserts,
            )

    cur.close()


# --------------------------------------------------------------------------- #
# The atomic import
# --------------------------------------------------------------------------- #
def _community_lock_key(community: str) -> str:
    return f"gedcom_import:{community}"


def run_import(
    file: str,
    community: str = DEFAULT_COMMUNITY,
    notes: str | None = None,
    imported_by: str = "admin",
    execute: bool = False,
    conn_factory: Callable[[], Any] | None = None,
    r2_factory: Callable[[], Any] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Import a GEDCOM file as one atomic version.

    Dry-run (execute=False): parse + diff against current state + print summary;
    no R2 or DB writes. Returns the diff summary.

    execute=True: the full atomic transaction described in the module docstring.
    Any exception rolls back -> ZERO rows changed.
    """
    file = str(file)
    raw_bytes = Path(file).read_bytes()
    source_hash = hashlib.sha256(raw_bytes).hexdigest()
    generated_at = generated_at or datetime.now(timezone.utc).isoformat()

    parsed = parse_gedcom(file)
    bundle = build_snapshot_bundle(parsed, source_file=Path(file).name)
    new_maps = {
        "individuals": bundle.individuals,
        "families": bundle.families,
        "relationships": bundle.relationships,
        "sources": bundle.sources,
        "media_objects": bundle.media_objects,
    }

    if not execute:
        # Dry-run: diff against EMPTY current state (no DB connection) and report
        # the full bundle as the change set. This is a "what would import" view.
        diffs = {et: diff_entity_maps(et, {}, new_maps[et]) for et in DIFF_TYPES}
        summary = gh.build_diff_summary(diffs)
        result = {
            "execute": False,
            "source_hash": source_hash,
            "counts": bundle.counts,
            "diff_summary": summary,
        }
        logger.info("DRY-RUN import of %s (source_hash=%s): %s", file, source_hash[:12], bundle.counts)
        return result

    conn_factory = conn_factory or default_conn_factory
    r2_factory = r2_factory or default_r2_factory
    conn = conn_factory()
    try:
        cur = conn.cursor()
        # Serialize concurrent imports for this community BEFORE any state read.
        cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (_community_lock_key(community),))

        # Idempotency guard UNDER the lock, BEFORE any R2/DB mutation.
        cur.execute(
            "SELECT version_number FROM gedcom_versions "
            "WHERE community_id = %s AND source_hash = %s AND status = 'applied' LIMIT 1",
            (community, source_hash),
        )
        existing = cur.fetchone()
        if existing:
            conn.rollback()
            logger.info("Idempotent no-op: source_hash %s already applied as v%s", source_hash[:12], existing[0])
            return {
                "execute": True,
                "idempotent": True,
                "version_number": existing[0],
                "source_hash": source_hash,
            }

        # Allocate the next version number for this community.
        cur.execute(
            "SELECT COALESCE(MAX(version_number), 0) FROM gedcom_versions WHERE community_id = %s",
            (community,),
        )
        base_version = cur.fetchone()[0]
        version_number = base_version + 1

        # Load current state + diff against the new bundle.
        old_maps = load_current_maps(conn, community)
        diffs = {et: diff_entity_maps(et, old_maps[et], new_maps[et]) for et in DIFF_TYPES}
        diff_summary = gh.build_diff_summary(diffs)

        # Build + upload + verify R2 artifacts (version is now known).
        prefix = gh.artifact_prefix(community, version_number, source_hash)
        snapshot_gz = gh.build_snapshot_jsonl_gz(bundle)
        diff_gz = gh.build_diff_json_gz(
            diffs,
            version_number=version_number,
            base_version=base_version or None,
            source_hash=source_hash,
            generated_at=generated_at,
        )
        import gzip as _gzip

        artifacts = {
            "raw.ged.gz": _gzip.compress(raw_bytes, mtime=0),
            "snapshot.jsonl.gz": snapshot_gz,
            "diff.json.gz": diff_gz,
        }
        r2_client = r2_factory()
        shas = gh.upload_and_verify_artifacts(r2_client, _r2_bucket(), prefix, artifacts)

        # Apply mutations to canonical tables (still inside the txn).
        apply_entity_diffs(conn, community, diffs, version_number)

        # Insert the manifest row.
        cur.execute(
            "INSERT INTO gedcom_versions (version_number, community_id, imported_at, "
            "imported_by, source_file, source_hash, individual_count, family_count, "
            "summary, notes, status, raw_artifact_sha256, snapshot_artifact_sha256, "
            "diff_artifact_sha256, artifact_prefix, diff_summary, artifact_format) "
            "VALUES (%s, %s, now(), %s, %s, %s, %s, %s, %s::jsonb, %s, 'applied', "
            "%s, %s, %s, %s, %s::jsonb, 'v1')",
            (
                version_number,
                community,
                imported_by,
                Path(file).name,
                source_hash,
                len(bundle.individuals),
                len(bundle.families),
                json.dumps(diff_summary),
                notes,
                shas.get("raw.ged.gz"),
                shas.get("snapshot.jsonl.gz"),
                shas.get("diff.json.gz"),
                prefix,
                json.dumps(diff_summary),
            ),
        )

        conn.commit()
        cur.close()
        logger.info("Applied GEDCOM v%s (source_hash=%s) to %s", version_number, source_hash[:12], community)
        return {
            "execute": True,
            "idempotent": False,
            "version_number": version_number,
            "source_hash": source_hash,
            "artifact_prefix": prefix,
            "artifact_sha256": shas,
            "diff_summary": diff_summary,
        }
    except Exception:
        conn.rollback()
        logger.exception("GEDCOM import failed — rolled back (ZERO rows changed)")
        raise
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Atomic GEDCOM importer (PRD-064)")
    parser.add_argument("--file", required=True, help="Path to the .ged file")
    parser.add_argument("--execute", action="store_true", help="Apply (default: dry-run)")
    parser.add_argument("--community", default=DEFAULT_COMMUNITY)
    parser.add_argument("--notes", default=None)
    parser.add_argument("--imported-by", default="admin")
    args = parser.parse_args(argv)

    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:  # pragma: no cover - dotenv optional
        pass

    result = run_import(
        file=args.file,
        community=args.community,
        notes=args.notes,
        imported_by=args.imported_by,
        execute=args.execute,
    )
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
