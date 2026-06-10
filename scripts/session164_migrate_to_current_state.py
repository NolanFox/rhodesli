#!/usr/bin/env python3
"""Session 164 — migrate GEDCOM storage to canonical current-state tables.

PRD-064 Option B-plus. One-off, reversible, subcommand-driven migration. Each
subcommand does ONE thing; destructive steps require an explicit ``--yes`` flag.
The orchestrator runs the subcommands in order against the LIVE database — this
file is NOT executed automatically and has no unit-test live dependency.

Inherited state (verified live by the orchestrator, plan §0 / R6):
  * DB 423 MB. ``gedcom_individuals_v2`` 267 MB / 43,172 rows (21,998 distinct
    gedcom_id). ``gedcom_families_v2`` 13,158 rows / 6,741 distinct.
  * ``gedcom_relationships`` 140,796 rows — already current-only (Session 163).
  * v1 tables (``gedcom_individuals``/``gedcom_families``) no longer exist (158e).
  * ``gedcom_versions``: 9 rows; only v7 + v9 ``applied``.
  * Site is DOWN (402) → no live readers → DROP-FIRST ordering is safe and
    everything lands in R2 first.

Ordering (headroom-safe, R6):
  1. snapshot              — dump v2 + relationships + versions to R2 (verify)
  2. drop-v2 --yes         — DROP v2 tables + their current_*_v2 views (frees ~294 MB)
  3. create-schema         — apply session164_canonical_schema.sql (idempotent)
  4. populate              — load canonical tables from the R2 current extracts;
                             augment + slim gedcom_relationships
  5. backfill-artifacts --yes — write v9 R2 history artifacts + extend gedcom_versions
  6. verify                — count==distinct, columns gone, complete id->hash equality
  7. measure               — pg_database_size + per-table sizes

Connection: pooler SESSION port 5432 (reuse import_gedcom_version.default_conn_factory).
R2 via boto3.

Run:
  source venv/bin/activate
  python scripts/session164_migrate_to_current_state.py snapshot
  python scripts/session164_migrate_to_current_state.py drop-v2 --yes
  python scripts/session164_migrate_to_current_state.py create-schema
  python scripts/session164_migrate_to_current_state.py populate
  python scripts/session164_migrate_to_current_state.py backfill-artifacts --yes
  python scripts/session164_migrate_to_current_state.py verify
  python scripts/session164_migrate_to_current_state.py measure
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import scripts.import_gedcom_version as imp  # noqa: E402
from rhodesli_ml.importers import gedcom_history as gh  # noqa: E402

# ----------------------------------------------------------------------------- #
# Constants
# ----------------------------------------------------------------------------- #
COMMUNITY = "rhodesli"
SNAP_PREFIX = "gedcom-cleanup-snapshots/2026-06-09-session-164"
SCHEMA_SQL = PROJECT_ROOT / "scripts" / "migrations" / "session164_canonical_schema.sql"

# The v9 source GEDCOM archived in Session 156 (closest-available; the exact
# f778 bytes were never archived — recorded in the manifest note).
V9_RAW_R2_KEY = (
    "gedcom-source-snapshots/2026-05-08-session-156/"
    "Fox_Capeluto_Fogel_Waldorf_Family_Tree-f7832541.ged"
)
V9_VERSION_NUMBER = 9

# Expected current-state counts (R6 acceptance) — used only as advisory bounds.
EXPECTED_INDIVIDUALS = 21998
EXPECTED_FAMILIES = 6741
EXPECTED_RELATIONSHIPS = 140796

# v2 column extracts (current-state) — the typed columns the canonical schema
# keeps, mirroring INDIVIDUAL_COLUMNS / FAMILY_COLUMNS from the importer.
INDIVIDUAL_V2_COLUMNS = imp.INDIVIDUAL_COLUMNS + ["last_seen_version", "first_seen_version"]
FAMILY_V2_COLUMNS = imp.FAMILY_COLUMNS + ["last_seen_version", "first_seen_version"]

CHUNK = 5000


# ----------------------------------------------------------------------------- #
# Connection + R2 helpers
# ----------------------------------------------------------------------------- #
def _conn(autocommit: bool = True):
    """Pooler session-mode connection (port 5432)."""
    conn = imp.default_conn_factory()
    conn.autocommit = autocommit
    return conn


def _r2():
    return imp.default_r2_factory()


def _bucket() -> str:
    return os.environ.get("R2_BUCKET_NAME", "rhodesli-photos")


def _put(r2, key: str, data: bytes) -> str:
    """Upload bytes, re-download, verify sha256 of the stored bytes. Returns sha."""
    sha = hashlib.sha256(data).hexdigest()
    r2.put_object(Bucket=_bucket(), Key=key, Body=data)
    got = gh._get_object_bytes(r2, _bucket(), key)
    got_sha = hashlib.sha256(got).hexdigest()
    if got_sha != sha:
        raise ValueError(f"R2 verify failed for {key}: put {sha} got {got_sha}")
    return sha


def _get(r2, key: str) -> bytes:
    return gh._get_object_bytes(r2, _bucket(), key)


def _head_exists(r2, key: str) -> bool:
    try:
        r2.head_object(Bucket=_bucket(), Key=key)
        return True
    except Exception:
        return False


def _gz_jsonl(rows: list[dict[str, Any]]) -> bytes:
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as gz:
        for row in rows:
            gz.write((json.dumps(row, sort_keys=True, default=str) + "\n").encode("utf-8"))
    return buf.getvalue()


def _read_jsonl_gz(data: bytes) -> list[dict[str, Any]]:
    text = gzip.decompress(data).decode("utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _db_size(cur) -> tuple[str, int]:
    cur.execute(
        "SELECT pg_size_pretty(pg_database_size(current_database())), "
        "pg_database_size(current_database())"
    )
    return cur.fetchone()


def _table_exists(cur, name: str) -> bool:
    cur.execute("SELECT to_regclass(%s)", (f"public.{name}",))
    return cur.fetchone()[0] is not None


def _column_exists(cur, table: str, column: str) -> bool:
    cur.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name=%s AND column_name=%s",
        (table, column),
    )
    return cur.fetchone() is not None


# ----------------------------------------------------------------------------- #
# 1. snapshot
# ----------------------------------------------------------------------------- #
def _stream_table_to_jsonl_gz(conn, sql: str, params=None):
    """Stream a query through a server-side cursor into gzip-compressed JSONL.

    Yields nothing — returns (gz_bytes, row_count). Chunked via fetchmany so the
    full row set is never held in memory beyond a chunk (Lesson 183).
    """
    buf = io.BytesIO()
    n = 0
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as gz:
        cur = conn.cursor(name="s164_snap")  # server-side (named) cursor
        cur.itersize = CHUNK
        cur.execute(sql, params or ())
        colnames = [d[0] for d in cur.description]
        while True:
            rows = cur.fetchmany(CHUNK)
            if not rows:
                break
            for row in rows:
                rec = {c: v for c, v in zip(colnames, row)}
                gz.write((json.dumps(rec, sort_keys=True, default=str) + "\n").encode("utf-8"))
                n += 1
        cur.close()
    return buf.getvalue(), n


def cmd_snapshot(args):
    conn = _conn(autocommit=False)
    conn.set_session(isolation_level="REPEATABLE READ", readonly=True)
    r2 = _r2()
    manifest: dict[str, Any] = {"session": "164", "prefix": SNAP_PREFIX, "community": COMMUNITY, "files": {}}

    def emit(name: str, sql: str, params=None):
        print(f"[snapshot] dumping {name} ...")
        data, n = _stream_table_to_jsonl_gz(conn, sql, params)
        key = f"{SNAP_PREFIX}/{name}"
        sha = _put(r2, key, data)
        manifest["files"][name] = {"rows": n, "size_bytes": len(data), "sha256": sha, "r2_key": key}
        print(f"[snapshot]   {name}: {n} rows, {len(data)} bytes, sha={sha[:16]}")

    # Full backup of v2 individuals (all rows, all columns).
    emit("gedcom_individuals_v2.full.jsonl.gz", "SELECT * FROM gedcom_individuals_v2")

    # Production-faithful current-state extracts (latest row per id).
    ind_cols = ", ".join(INDIVIDUAL_V2_COLUMNS)
    emit(
        "gedcom_individuals_v2.current.jsonl.gz",
        f"SELECT DISTINCT ON (gedcom_id) {ind_cols} FROM gedcom_individuals_v2 "
        "ORDER BY gedcom_id, last_seen_version DESC NULLS LAST, "
        "first_seen_version DESC NULLS LAST, payload_hash",
    )
    fam_cols = ", ".join(FAMILY_V2_COLUMNS)
    emit(
        "gedcom_families_v2.current.jsonl.gz",
        f"SELECT DISTINCT ON (family_gedcom_id) {fam_cols} FROM gedcom_families_v2 "
        "ORDER BY family_gedcom_id, last_seen_version DESC NULLS LAST, "
        "first_seen_version DESC NULLS LAST, payload_hash",
    )

    emit("gedcom_relationships.jsonl.gz", "SELECT * FROM gedcom_relationships")
    emit("gedcom_versions.jsonl.gz", "SELECT * FROM gedcom_versions")

    # Schema DDL text dump (column listing) for the v2 + relationships tables.
    schema_cur = conn.cursor()
    schema_lines = []
    for tbl in ("gedcom_individuals_v2", "gedcom_families_v2", "gedcom_relationships", "gedcom_versions"):
        schema_cur.execute(
            "SELECT column_name, data_type, is_nullable, column_default "
            "FROM information_schema.columns WHERE table_schema='public' AND table_name=%s "
            "ORDER BY ordinal_position",
            (tbl,),
        )
        schema_lines.append(f"-- {tbl}")
        for col, dtype, nullable, default in schema_cur.fetchall():
            schema_lines.append(f"--   {col} {dtype} nullable={nullable} default={default}")
        schema_lines.append("")
    schema_cur.close()
    schema_text = "\n".join(schema_lines).encode("utf-8")
    schema_sha = _put(r2, f"{SNAP_PREFIX}/schema.sql", schema_text)
    manifest["files"]["schema.sql"] = {"size_bytes": len(schema_text), "sha256": schema_sha}

    # Manifest last.
    manifest_bytes = json.dumps(manifest, indent=2, default=str).encode("utf-8")
    _put(r2, f"{SNAP_PREFIX}/manifest.json", manifest_bytes)

    # Re-download verify of one file (current individuals) + sha match.
    verify_key = f"{SNAP_PREFIX}/gedcom_individuals_v2.current.jsonl.gz"
    got = _get(r2, verify_key)
    assert hashlib.sha256(got).hexdigest() == manifest["files"]["gedcom_individuals_v2.current.jsonl.gz"]["sha256"]
    print("[snapshot] re-download verify PASS for current individuals extract")

    conn.rollback()  # readonly txn — release the REPEATABLE READ snapshot
    conn.close()
    print("\n[snapshot] manifest:")
    print(json.dumps(manifest, indent=2, default=str))
    return manifest


# ----------------------------------------------------------------------------- #
# 2. drop-v2
# ----------------------------------------------------------------------------- #
def _snapshot_manifest_exists(r2) -> bool:
    return _head_exists(r2, f"{SNAP_PREFIX}/manifest.json")


def cmd_drop_v2(args):
    if not args.yes:
        print("ABORT: drop-v2 requires --yes")
        sys.exit(1)
    r2 = _r2()
    if not _snapshot_manifest_exists(r2):
        print(f"ABORT: snapshot manifest not found at {SNAP_PREFIX}/manifest.json. Run `snapshot` first.")
        sys.exit(1)
    conn = _conn(autocommit=True)
    cur = conn.cursor()
    before = _db_size(cur)
    print(f"[drop-v2] BEFORE: {before[0]} ({before[1]} bytes)")
    # Explicit view drops (no CASCADE), then tables.
    for view in ("current_gedcom_individuals_v2", "current_gedcom_families_v2"):
        print(f"[drop-v2] DROP VIEW IF EXISTS {view}")
        cur.execute(f"DROP VIEW IF EXISTS {view}")
    for tbl in ("gedcom_individuals_v2", "gedcom_families_v2"):
        print(f"[drop-v2] DROP TABLE IF EXISTS {tbl}")
        cur.execute(f"DROP TABLE IF EXISTS {tbl}")
    after = _db_size(cur)
    print(f"[drop-v2] AFTER:  {after[0]} ({after[1]} bytes)  freed={before[1]-after[1]} bytes")
    conn.close()


# ----------------------------------------------------------------------------- #
# 3. create-schema
# ----------------------------------------------------------------------------- #
def cmd_create_schema(args):
    sql = SCHEMA_SQL.read_text()
    conn = _conn(autocommit=True)
    cur = conn.cursor()
    print(f"[create-schema] applying {SCHEMA_SQL.name}")
    cur.execute(sql)
    for tbl in ("gedcom_individuals", "gedcom_families"):
        print(f"[create-schema]   {tbl} exists: {_table_exists(cur, tbl)}")
    cur.execute(
        "SELECT conname FROM pg_constraint WHERE conrelid = 'gedcom_individuals'::regclass "
        "AND contype = 'p'"
    )
    print(f"[create-schema]   gedcom_individuals PK: {[r[0] for r in cur.fetchall()]}")
    print(
        f"[create-schema]   relationships community_id col: "
        f"{_column_exists(cur, 'gedcom_relationships', 'community_id')}"
    )
    conn.close()


# ----------------------------------------------------------------------------- #
# 4. populate
# ----------------------------------------------------------------------------- #
def _payload_from_extract(row: dict[str, Any], columns: list[str], json_cols: set[str]) -> dict[str, Any]:
    """Map an R2 current-extract row to a typed-column payload for insertion."""
    out: dict[str, Any] = {}
    for col in columns:
        val = row.get(col)
        if col in json_cols and isinstance(val, str):
            # JSONB columns were dumped as text in some COPY paths; re-parse.
            try:
                val = json.loads(val)
            except (TypeError, ValueError):
                pass
        out[col] = val
    return out


def _insert_individuals(cur, rows: list[dict[str, Any]]):
    from psycopg2.extras import execute_values

    cols = ["community_id"] + imp.INDIVIDUAL_COLUMNS + ["version_number"]
    placeholders = ", ".join(cols)
    update_cols = [c for c in imp.INDIVIDUAL_COLUMNS if c != "gedcom_id"] + ["version_number"]
    set_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)
    batch = []
    for row in rows:
        payload = _payload_from_extract(row, imp.INDIVIDUAL_COLUMNS, imp.INDIVIDUAL_JSON_COLUMNS)
        version = row.get("last_seen_version") or V9_VERSION_NUMBER
        batch.append(imp.individual_row_values(COMMUNITY, payload, int(version)))
    for i in range(0, len(batch), CHUNK):
        execute_values(
            cur,
            f"INSERT INTO gedcom_individuals ({placeholders}) VALUES %s "
            f"ON CONFLICT (community_id, gedcom_id) DO UPDATE SET {set_clause}, updated_at = now()",
            batch[i : i + CHUNK],
        )
    return len(batch)


def _insert_families(cur, rows: list[dict[str, Any]]):
    from psycopg2.extras import execute_values

    cols = ["community_id"] + imp.FAMILY_COLUMNS + ["version_number"]
    placeholders = ", ".join(cols)
    update_cols = [c for c in imp.FAMILY_COLUMNS if c != "family_gedcom_id"] + ["version_number"]
    set_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)
    batch = []
    for row in rows:
        payload = _payload_from_extract(row, imp.FAMILY_COLUMNS, imp.FAMILY_JSON_COLUMNS)
        version = row.get("last_seen_version") or V9_VERSION_NUMBER
        batch.append(imp.family_row_values(COMMUNITY, payload, int(version)))
    for i in range(0, len(batch), CHUNK):
        execute_values(
            cur,
            f"INSERT INTO gedcom_families ({placeholders}) VALUES %s "
            f"ON CONFLICT (community_id, family_gedcom_id) DO UPDATE SET {set_clause}, updated_at = now()",
            batch[i : i + CHUNK],
        )
    return len(batch)


def cmd_populate(args):
    r2 = _r2()
    print("[populate] reading R2 current extracts ...")
    ind_rows = _read_jsonl_gz(_get(r2, f"{SNAP_PREFIX}/gedcom_individuals_v2.current.jsonl.gz"))
    fam_rows = _read_jsonl_gz(_get(r2, f"{SNAP_PREFIX}/gedcom_families_v2.current.jsonl.gz"))
    print(f"[populate]   individuals extract: {len(ind_rows)}  families extract: {len(fam_rows)}")

    conn = _conn(autocommit=False)
    cur = conn.cursor()
    try:
        if args.truncate:
            print("[populate] TRUNCATE gedcom_individuals, gedcom_families (--truncate)")
            cur.execute("TRUNCATE gedcom_individuals")
            cur.execute("TRUNCATE gedcom_families")

        n_ind = _insert_individuals(cur, ind_rows)
        n_fam = _insert_families(cur, fam_rows)
        print(f"[populate] inserted individuals={n_ind} families={n_fam}")

        # Relationships: already in-table. Augment community_id + version_number,
        # then drop the legacy versioning columns and the is_current-based view.
        print("[populate] augmenting gedcom_relationships (community_id, version_number) ...")
        cur.execute(
            "UPDATE gedcom_relationships SET community_id = COALESCE(community_id, %s), "
            "version_number = COALESCE(version_number, %s) "
            "WHERE community_id IS NULL OR version_number IS NULL",
            (COMMUNITY, V9_VERSION_NUMBER),
        )
        print(f"[populate]   relationships augmented: {cur.rowcount} rows")
        # The current_gedcom_relationships view filters is_current — it must be
        # dropped before the column, and the app now reads the base table directly.
        cur.execute("DROP VIEW IF EXISTS current_gedcom_relationships")
        for col in ("is_current", "version_id", "superseded_by"):
            if _column_exists(cur, "gedcom_relationships", col):
                print(f"[populate]   DROP COLUMN gedcom_relationships.{col}")
                cur.execute(f"ALTER TABLE gedcom_relationships DROP COLUMN IF EXISTS {col}")

        conn.commit()
        print("[populate] COMMIT")
    except Exception:
        conn.rollback()
        print("[populate] ROLLBACK (error) — no rows changed")
        raise
    finally:
        conn.close()


# ----------------------------------------------------------------------------- #
# 5. backfill-artifacts
# ----------------------------------------------------------------------------- #
def _build_v9_snapshot_jsonl_gz(cur) -> bytes:
    """Build snapshot.jsonl.gz from the freshly-populated canonical tables.

    One line per entity {entity_type, entity_id, payload, payload_hash}. payload
    here is the typed-column projection (lossless full payload predates this
    schema; the R2 v2 full backup retains it). Streamed in chunks.
    """
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as gz:
        # individuals
        cur.execute(
            f"SELECT {', '.join(imp.INDIVIDUAL_COLUMNS)} FROM gedcom_individuals "
            "WHERE community_id = %s ORDER BY gedcom_id",
            (COMMUNITY,),
        )
        for row in cur.fetchall():
            payload = {c: v for c, v in zip(imp.INDIVIDUAL_COLUMNS, row)}
            rec = {
                "entity_type": "individuals",
                "entity_id": payload["gedcom_id"],
                "payload": payload,
                "payload_hash": payload.get("payload_hash"),
            }
            gz.write((json.dumps(rec, sort_keys=True, default=str) + "\n").encode("utf-8"))
        # families
        cur.execute(
            f"SELECT {', '.join(imp.FAMILY_COLUMNS)} FROM gedcom_families "
            "WHERE community_id = %s ORDER BY family_gedcom_id",
            (COMMUNITY,),
        )
        for row in cur.fetchall():
            payload = {c: v for c, v in zip(imp.FAMILY_COLUMNS, row)}
            rec = {
                "entity_type": "families",
                "entity_id": payload["family_gedcom_id"],
                "payload": payload,
                "payload_hash": payload.get("payload_hash"),
            }
            gz.write((json.dumps(rec, sort_keys=True, default=str) + "\n").encode("utf-8"))
    return buf.getvalue()


def _build_v9_diff_baseline_gz(cur, generated_at: str, source_hash: str | None) -> bytes:
    """Baseline diff: every entity as change_type='baseline' with after=payload."""
    entities: dict[str, dict[str, list]] = {"individuals": {"added": [], "modified": [], "removed": []},
                                            "families": {"added": [], "modified": [], "removed": []}}
    cur.execute(
        f"SELECT {', '.join(imp.INDIVIDUAL_COLUMNS)} FROM gedcom_individuals "
        "WHERE community_id = %s ORDER BY gedcom_id",
        (COMMUNITY,),
    )
    for row in cur.fetchall():
        payload = {c: v for c, v in zip(imp.INDIVIDUAL_COLUMNS, row)}
        entities["individuals"]["added"].append(
            {
                "entity_type": "individuals",
                "entity_id": payload["gedcom_id"],
                "change_type": "baseline",
                "before": None,
                "after": payload,
                "before_hash": None,
                "after_hash": payload.get("payload_hash"),
            }
        )
    cur.execute(
        f"SELECT {', '.join(imp.FAMILY_COLUMNS)} FROM gedcom_families "
        "WHERE community_id = %s ORDER BY family_gedcom_id",
        (COMMUNITY,),
    )
    for row in cur.fetchall():
        payload = {c: v for c, v in zip(imp.FAMILY_COLUMNS, row)}
        entities["families"]["added"].append(
            {
                "entity_type": "families",
                "entity_id": payload["family_gedcom_id"],
                "change_type": "baseline",
                "before": None,
                "after": payload,
                "before_hash": None,
                "after_hash": payload.get("payload_hash"),
            }
        )
    doc = {
        "schema_version": gh.SCHEMA_VERSION,
        "version_number": V9_VERSION_NUMBER,
        "base_version": None,
        "source_hash": source_hash,
        "generated_at": generated_at,
        "entities": entities,
    }
    return gzip.compress(json.dumps(doc, sort_keys=True, default=str).encode("utf-8"), mtime=0)


def cmd_backfill_artifacts(args):
    if not args.yes:
        print("ABORT: backfill-artifacts requires --yes")
        sys.exit(1)
    from datetime import datetime, timezone

    r2 = _r2()
    conn = _conn(autocommit=False)
    cur = conn.cursor()
    try:
        # Look up v9's recorded source_hash for the content-addressed prefix.
        cur.execute(
            "SELECT source_hash FROM gedcom_versions WHERE version_number = %s AND community_id = %s",
            (V9_VERSION_NUMBER, COMMUNITY),
        )
        row = cur.fetchone()
        # Fall back to community-agnostic lookup if community_id wasn't set on the row.
        if not row:
            cur.execute(
                "SELECT source_hash FROM gedcom_versions WHERE version_number = %s",
                (V9_VERSION_NUMBER,),
            )
            row = cur.fetchone()
        source_hash = row[0] if row and row[0] else None
        generated_at = datetime.now(timezone.utc).isoformat()
        prefix = gh.artifact_prefix(COMMUNITY, V9_VERSION_NUMBER, source_hash)
        print(f"[backfill-artifacts] prefix={prefix}")

        # raw.ged.gz — fetch archived f783 ged, re-gzip (closest-available).
        print("[backfill-artifacts] fetching archived v9 raw GEDCOM (f783, closest-available) ...")
        raw_bytes = _get(r2, V9_RAW_R2_KEY)
        # Archived file may already be gzipped or raw; normalize to raw then re-gzip.
        try:
            raw_inner = gzip.decompress(raw_bytes)
        except (OSError, gzip.BadGzipFile):
            raw_inner = raw_bytes
        raw_gz = gzip.compress(raw_inner, mtime=0)

        print("[backfill-artifacts] building snapshot.jsonl.gz from canonical tables ...")
        snapshot_gz = _build_v9_snapshot_jsonl_gz(cur)
        print("[backfill-artifacts] building baseline diff.json.gz ...")
        diff_gz = _build_v9_diff_baseline_gz(cur, generated_at, source_hash)

        shas = {
            "raw.ged.gz": _put(r2, prefix + "raw.ged.gz", raw_gz),
            "snapshot.jsonl.gz": _put(r2, prefix + "snapshot.jsonl.gz", snapshot_gz),
            "diff.json.gz": _put(r2, prefix + "diff.json.gz", diff_gz),
        }
        print(f"[backfill-artifacts] uploaded + verified: { {k: v[:12] for k, v in shas.items()} }")

        # diff_summary (counts + ids) for the version row.
        cur.execute("SELECT count(*) FROM gedcom_individuals WHERE community_id = %s", (COMMUNITY,))
        n_ind = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM gedcom_families WHERE community_id = %s", (COMMUNITY,))
        n_fam = cur.fetchone()[0]
        diff_summary = {
            "individuals": {"added": n_ind, "modified": 0, "removed": 0},
            "families": {"added": n_fam, "modified": 0, "removed": 0},
            "note": "baseline (Session 164 migration)",
        }

        cur.execute(
            "UPDATE gedcom_versions SET raw_artifact_sha256 = %s, snapshot_artifact_sha256 = %s, "
            "diff_artifact_sha256 = %s, artifact_prefix = %s, diff_summary = %s::jsonb, "
            "artifact_format = 'v1', "
            "notes = COALESCE(notes, '') || %s "
            "WHERE version_number = %s",
            (
                shas["raw.ged.gz"],
                shas["snapshot.jsonl.gz"],
                shas["diff.json.gz"],
                prefix,
                json.dumps(diff_summary),
                " [S164: raw.ged.gz is archived f783, closest-available; exact f778 bytes not archived]",
                V9_VERSION_NUMBER,
            ),
        )
        print(f"[backfill-artifacts] gedcom_versions v9 updated ({cur.rowcount} row)")

        # All other versions → 'legacy' format (no v1 artifacts).
        cur.execute(
            "UPDATE gedcom_versions SET artifact_format = 'legacy' "
            "WHERE version_number != %s AND (artifact_format IS NULL OR artifact_format = 'v1')",
            (V9_VERSION_NUMBER,),
        )
        print(f"[backfill-artifacts] marked {cur.rowcount} non-v9 versions as 'legacy'")

        conn.commit()
        print("[backfill-artifacts] COMMIT")
    except Exception:
        conn.rollback()
        print("[backfill-artifacts] ROLLBACK (error)")
        raise
    finally:
        conn.close()


# ----------------------------------------------------------------------------- #
# 6. verify
# ----------------------------------------------------------------------------- #
def cmd_verify(args):
    r2 = _r2()
    conn = _conn(autocommit=True)
    cur = conn.cursor()
    ok = True

    def check(label, cond, detail=""):
        nonlocal ok
        status = "PASS" if cond else "FAIL"
        if not cond:
            ok = False
        print(f"[verify] {status}: {label} {detail}")

    # Count == distinct for each canonical table.
    cur.execute("SELECT count(*), count(DISTINCT gedcom_id) FROM gedcom_individuals WHERE community_id = %s", (COMMUNITY,))
    ind_n, ind_d = cur.fetchone()
    check("individuals count==distinct", ind_n == ind_d, f"(count={ind_n} distinct={ind_d})")
    check("individuals count near expected", abs(ind_n - EXPECTED_INDIVIDUALS) <= 50, f"(count={ind_n} expected~{EXPECTED_INDIVIDUALS})")

    cur.execute(
        "SELECT count(*), count(DISTINCT family_gedcom_id) FROM gedcom_families WHERE community_id = %s",
        (COMMUNITY,),
    )
    fam_n, fam_d = cur.fetchone()
    check("families count==distinct", fam_n == fam_d, f"(count={fam_n} distinct={fam_d})")
    check("families count near expected", abs(fam_n - EXPECTED_FAMILIES) <= 50, f"(count={fam_n} expected~{EXPECTED_FAMILIES})")

    # payload_hash non-null on individuals.
    cur.execute("SELECT count(*) FROM gedcom_individuals WHERE community_id = %s AND payload_hash IS NULL", (COMMUNITY,))
    check("individuals payload_hash all non-null", cur.fetchone()[0] == 0)

    # Relationships: community_id + version_number non-null; versioning cols gone.
    cur.execute("SELECT count(*) FROM gedcom_relationships WHERE community_id IS NULL OR version_number IS NULL")
    check("relationships community_id+version_number non-null", cur.fetchone()[0] == 0)
    for col in ("is_current", "version_id", "superseded_by"):
        check(f"relationships column {col} dropped", not _column_exists(cur, "gedcom_relationships", col))

    # COMPLETE id->hash map equality vs the R2 current extract (Codex P2-4).
    print("[verify] comparing complete id->hash map (canonical vs R2 extract) ...")
    extract = _read_jsonl_gz(_get(r2, f"{SNAP_PREFIX}/gedcom_individuals_v2.current.jsonl.gz"))
    extract_map = {r["gedcom_id"]: r["payload_hash"] for r in extract}
    cur.execute("SELECT gedcom_id, payload_hash FROM gedcom_individuals WHERE community_id = %s", (COMMUNITY,))
    db_map = {gid: ph for gid, ph in cur.fetchall()}
    check("individuals id->hash map equals R2 extract", db_map == extract_map,
          f"(db={len(db_map)} extract={len(extract_map)} "
          f"missing_in_db={len(set(extract_map)-set(db_map))} "
          f"extra_in_db={len(set(db_map)-set(extract_map))} "
          f"hash_mismatch={sum(1 for k in db_map if k in extract_map and db_map[k]!=extract_map[k])})")

    fam_extract = _read_jsonl_gz(_get(r2, f"{SNAP_PREFIX}/gedcom_families_v2.current.jsonl.gz"))
    fam_extract_map = {r["family_gedcom_id"]: r["payload_hash"] for r in fam_extract}
    cur.execute("SELECT family_gedcom_id, payload_hash FROM gedcom_families WHERE community_id = %s", (COMMUNITY,))
    fam_db_map = {fid: ph for fid, ph in cur.fetchall()}
    check("families id->hash map equals R2 extract", fam_db_map == fam_extract_map,
          f"(db={len(fam_db_map)} extract={len(fam_extract_map)})")

    size = _db_size(cur)
    print(f"[verify] DB size: {size[0]} ({size[1]} bytes)")
    conn.close()
    print(f"\n[verify] OVERALL: {'PASS' if ok else 'FAIL'}")
    if not ok:
        sys.exit(1)


# ----------------------------------------------------------------------------- #
# 7. measure
# ----------------------------------------------------------------------------- #
def cmd_measure(args):
    conn = _conn(autocommit=True)
    cur = conn.cursor()
    size = _db_size(cur)
    print(f"DB size: {size[0]} ({size[1]} bytes)")
    cur.execute(
        "SELECT c.relname, pg_size_pretty(pg_total_relation_size(c.oid)) "
        "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='public' AND c.relkind='r' "
        "ORDER BY pg_total_relation_size(c.oid) DESC LIMIT 12"
    )
    print("Top tables:")
    for relname, pretty in cur.fetchall():
        print(f"  {relname:36} {pretty:>10}")
    conn.close()


# ----------------------------------------------------------------------------- #
# CLI
# ----------------------------------------------------------------------------- #
COMMANDS: dict[str, Callable[[Any], Any]] = {
    "snapshot": cmd_snapshot,
    "drop-v2": cmd_drop_v2,
    "create-schema": cmd_create_schema,
    "populate": cmd_populate,
    "backfill-artifacts": cmd_backfill_artifacts,
    "verify": cmd_verify,
    "measure": cmd_measure,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Session 164 GEDCOM current-state migration")
    parser.add_argument("command", choices=list(COMMANDS))
    parser.add_argument("--yes", action="store_true", help="confirm destructive step")
    parser.add_argument("--truncate", action="store_true", help="(populate) TRUNCATE canonical tables first")
    args = parser.parse_args(argv)

    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        pass

    COMMANDS[args.command](args)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
