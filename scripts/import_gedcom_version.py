#!/usr/bin/env python3
"""Atomic GEDCOM importer (PRD-064 Option B-plus, Session 164).

Replaces the old non-atomic, per-batch-commit, multi-state versioned importer
(root cause of the Session 163 1.3 GB bloat — Lesson 199). The new importer is
a SINGLE Postgres transaction: a failed import leaves ZERO rows (no partial
state, no `failed` version row).

Flow (plan R3, Codex P0-1/P0-2/P0-A/P1-1):

    raw_bytes = read(file); source_hash = sha256(raw_bytes)
    parsed    = parse_gedcom(file); bundle = build_snapshot_bundle(parsed)
    conn (pooler 5432, autocommit=False)
    BEGIN
      pg_advisory_xact_lock(hashtext('gedcom_import:'||community))   # serialize
      if applied version with source_hash exists: ROLLBACK -> idempotent no-op
      version_number = MAX(version_number)+1  for community
      old = load_diff_base_maps(...)   # PREVIOUS applied version's R2 snapshot
                                       # (full LOSSLESS payloads, ALL diff types
                                       #  incl. sources/media/relationships)
      diffs = diff_entity_maps(et, old[et], new[et])  # full-payload diff
      artifacts = build raw.ged.gz / snapshot.jsonl.gz / diff.json.gz
      upload_and_verify(artifacts)                    # re-download + hash check; fail -> raise
      apply diffs: upsert added/modified, delete removed (individuals/families);
                   relationships: delete removed edges + upsert added/modified
      INSERT gedcom_versions(status='applied', artifact shas, prefix, diff_summary)
    COMMIT
    # any exception anywhere -> conn.rollback() -> ZERO rows changed

The DB stores only typed columns + payload_hash (current-state, one row per
entity); the lossless full payload lives in R2 (gedcom_history).

Codex P0-A — the diff base (the "old" / "before" state) is the PREVIOUS applied
version's R2 snapshot, NOT the lossy typed DB columns. R2 snapshots carry the
full lossless payload for ALL bundle entity types (individuals, families,
relationships, sources, media_objects), so:
  * `before` payloads in the diff artifact are complete (unwind-safe);
  * sources/media diff CORRECTLY (the DB schema doesn't store them, so a DB
    base would always re-add them every import).
The DB current-state == the previous snapshot (they are written atomically in
the same txn), so diffing against R2 is equivalent to diffing against the DB but
lossless. `load_current_maps` is retained as a DB-consistency cross-check.

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
    return os.environ.get("R2_BUCKET_NAME", "rhodesli-photos")


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
# Diff base from R2 (Codex P0-A — lossless)
# --------------------------------------------------------------------------- #
def _empty_old_maps() -> dict[str, dict[str, dict[str, Any]]]:
    return {et: {} for et in DIFF_TYPES}


def _latest_applied_artifact_prefix(cur, community: str) -> str | None:
    """Return the artifact_prefix of the latest applied version with artifacts.

    The diff base must come from the PREVIOUS applied version's R2 snapshot
    (full lossless payloads), not the current bundle's version (not yet written).
    """
    cur.execute(
        "SELECT artifact_prefix FROM gedcom_versions "
        "WHERE community_id = %s AND status = 'applied' AND artifact_prefix IS NOT NULL "
        "ORDER BY version_number DESC LIMIT 1",
        (community,),
    )
    row = cur.fetchone()
    return row[0] if row and row[0] else None


def load_diff_base_maps(
    cur, community: str, r2_client, bucket: str
) -> dict[str, dict[str, dict[str, Any]]]:
    """Load the diff base ("old" state) from the latest applied R2 snapshot.

    Codex P0-A: the diff base is the previous applied version's lossless
    ``snapshot.jsonl.gz`` reconstructed into ``{entity_type -> {id -> payload}}``.
    This carries the FULL payload for every diff entity type (incl. sources /
    media_objects, which the DB schema doesn't persist). If there's no prior
    applied version (first import), returns empty maps for all types.
    """
    prefix = _latest_applied_artifact_prefix(cur, community)
    if not prefix:
        return _empty_old_maps()
    snapshot_bytes = gh.download_snapshot(r2_client, bucket, prefix)
    reconstructed = gh.reconstruct_version_from_snapshot(snapshot_bytes)
    maps = _empty_old_maps()
    for et in DIFF_TYPES:
        maps[et] = dict(reconstructed.get(et, {}))
    return maps


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
        # Dry-run / admin preview (Codex P2): diff against the ACTUAL current
        # state read read-only from the latest applied R2 snapshot, so the
        # preview shows the REAL change set. If no conn/r2 factory is provided
        # (or there's no prior applied version), fall back to an empty base —
        # for a first import the empty base IS the real change set.
        old_maps = _empty_old_maps()
        if conn_factory is not None and r2_factory is not None:
            conn = conn_factory()
            try:
                cur = conn.cursor()
                r2_client = r2_factory()
                old_maps = load_diff_base_maps(cur, community, r2_client, _r2_bucket())
                cur.close()
                conn.rollback()  # read-only — never mutate during a dry-run
            finally:
                conn.close()
        diffs = {et: diff_entity_maps(et, old_maps[et], new_maps[et]) for et in DIFF_TYPES}
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

        # Codex P0-A: the diff base is the PREVIOUS applied version's lossless
        # R2 snapshot (full payloads, all diff types incl. sources/media),
        # NOT the lossy typed DB columns. The R2 client is created here because
        # it's needed both to read the base snapshot and to upload artifacts.
        r2_client = r2_factory()
        bucket = _r2_bucket()
        old_maps = load_diff_base_maps(cur, community, r2_client, bucket)
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
        shas = gh.upload_and_verify_artifacts(r2_client, bucket, prefix, artifacts)

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
