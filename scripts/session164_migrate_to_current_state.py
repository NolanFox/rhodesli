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

ASSUMPTION (Codex P1-A): this migration is SINGLE-COMMUNITY (rhodesli). cmd_snapshot
asserts every v2/relationships row is community_id NULL or 'rhodesli' and aborts
otherwise. Multi-community would need per-community extracts + version numbering.

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

# Codex P0-C / P1-C: DB-size gates. Post-migration target is ~129 MB.
DB_SIZE_HARD_LIMIT_BYTES = 300 * 1024 * 1024   # verify FAILs above this
DB_SIZE_POPULATE_GUARD_BYTES = 350 * 1024 * 1024  # populate ABORTs if already above this

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


def _column_type_sql(data_type: str, char_max_len, num_precision, num_scale) -> str:
    """Best-effort SQL type from information_schema metadata (Codex P0-E)."""
    dt = (data_type or "text").lower()
    if dt == "character varying":
        return f"varchar({char_max_len})" if char_max_len else "varchar"
    if dt == "character":
        return f"char({char_max_len})" if char_max_len else "char"
    if dt == "numeric" and num_precision:
        return f"numeric({num_precision},{num_scale or 0})"
    if dt == "timestamp without time zone":
        return "timestamp"
    if dt == "timestamp with time zone":
        return "timestamptz"
    if dt == "double precision":
        return "double precision"
    # text, integer, bigint, boolean, jsonb, uuid, etc. map 1:1
    return dt


def _build_restorable_ddl(cur, tables: tuple[str, ...]) -> str:
    """Build real CREATE TABLE DDL from information_schema (Codex P0-E).

    Good enough to recreate the tables (column name, type, nullability, default).
    Indexes / constraints are NOT reproduced — this is a restorability backstop,
    not a pg_dump replacement. A header documents the limitation.
    """
    lines: list[str] = [
        "-- Session 164 snapshot — restorable CREATE TABLE DDL (Codex P0-E).",
        "-- NOTE: indexes, PKs, FKs and triggers are NOT reproduced here; the",
        "--       canonical schema SQL (session164_canonical_schema.sql) and the",
        "--       v2 originals carry those. This is a column-level restore backstop.",
        "",
    ]
    for tbl in tables:
        cur.execute(
            "SELECT column_name, data_type, is_nullable, column_default, "
            "character_maximum_length, numeric_precision, numeric_scale "
            "FROM information_schema.columns WHERE table_schema='public' AND table_name=%s "
            "ORDER BY ordinal_position",
            (tbl,),
        )
        col_defs: list[str] = []
        for col, dtype, nullable, default, char_len, num_prec, num_scale in cur.fetchall():
            type_sql = _column_type_sql(dtype, char_len, num_prec, num_scale)
            piece = f"    {col} {type_sql}"
            if default is not None:
                piece += f" DEFAULT {default}"
            if (nullable or "YES").upper() == "NO":
                piece += " NOT NULL"
            col_defs.append(piece)
        if not col_defs:
            lines.append(f"-- (table {tbl} not found / no columns)")
            lines.append("")
            continue
        lines.append(f"CREATE TABLE IF NOT EXISTS {tbl} (")
        lines.append(",\n".join(col_defs))
        lines.append(");")
        lines.append("")
    return "\n".join(lines)


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
        colnames = None
        while True:
            rows = cur.fetchmany(CHUNK)
            if not rows:
                break
            if colnames is None:
                # Named cursors only populate .description after the first fetch.
                colnames = [d[0] for d in cur.description]
            for row in rows:
                rec = {c: v for c, v in zip(colnames, row)}
                gz.write((json.dumps(rec, sort_keys=True, default=str) + "\n").encode("utf-8"))
                n += 1
        cur.close()
    return buf.getvalue(), n


def _assert_single_community(cur, table: str):
    """Codex P1-A: the migration assumes ONE community (rhodesli). Abort if the
    table carries rows for more than one community_id (or any non-rhodesli)."""
    if not _column_exists(cur, table, "community_id"):
        return  # v2 tables may predate community_id; treated as single-community
    cur.execute(f"SELECT DISTINCT community_id FROM {table}")
    distinct = [r[0] for r in cur.fetchall()]
    non_null = [c for c in distinct if c is not None]
    if len(non_null) > 1 or (non_null and non_null != [COMMUNITY]):
        print(
            f"ABORT: {table} has community_id values {distinct} — the Session 164 "
            f"migration assumes a single community ({COMMUNITY!r}). Aborting."
        )
        sys.exit(1)


def cmd_snapshot(args):
    conn = _conn(autocommit=False)
    conn.set_session(isolation_level="REPEATABLE READ", readonly=True)
    r2 = _r2()
    manifest: dict[str, Any] = {"session": "164", "prefix": SNAP_PREFIX, "community": COMMUNITY, "files": {}}

    # Codex P1-A: single-community assumption guard (documented in module header).
    guard_cur = conn.cursor()
    for tbl in ("gedcom_individuals_v2", "gedcom_families_v2", "gedcom_relationships"):
        if _table_exists(guard_cur, tbl):
            _assert_single_community(guard_cur, tbl)
    guard_cur.close()

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

    # Codex P0-E: REAL CREATE TABLE DDL (not just column comments) so the snapshot
    # is restorable. Built from information_schema columns; indexes are NOT
    # reproduced (noted in the header) — the canonical schema SQL recreates those.
    schema_cur = conn.cursor()
    schema_text = _build_restorable_ddl(
        schema_cur,
        (
            "gedcom_individuals_v2",
            "gedcom_families_v2",
            "gedcom_relationships",
            "gedcom_versions",
        ),
    ).encode("utf-8")
    schema_cur.close()
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
def _verify_snapshot_manifest_complete(r2) -> dict[str, Any]:
    """Codex P0-E: every file the manifest records must actually exist in R2
    (head_object each), AND the current individuals extract must have the
    expected row count, BEFORE any irreversible DROP. Returns the manifest.
    Aborts (sys.exit(1)) on any missing file or count mismatch.
    """
    manifest_key = f"{SNAP_PREFIX}/manifest.json"
    if not _head_exists(r2, manifest_key):
        print(f"ABORT: snapshot manifest not found at {manifest_key}. Run `snapshot` first.")
        sys.exit(1)
    manifest = json.loads(_get(r2, manifest_key).decode("utf-8"))
    files = manifest.get("files", {})
    missing = []
    for name, meta in files.items():
        key = meta.get("r2_key") or f"{SNAP_PREFIX}/{name}"
        if not _head_exists(r2, key):
            missing.append(key)
    if missing:
        print(f"ABORT: snapshot manifest references {len(missing)} missing R2 file(s): {missing}")
        sys.exit(1)
    # Sanity: current individuals extract row count == expected (21998).
    cur_ind = files.get("gedcom_individuals_v2.current.jsonl.gz", {})
    rows = cur_ind.get("rows")
    if rows != EXPECTED_INDIVIDUALS:
        print(
            f"ABORT: snapshot current-individuals row count {rows} != expected "
            f"{EXPECTED_INDIVIDUALS}. Refusing to DROP."
        )
        sys.exit(1)
    print(f"[drop-v2] manifest verified: {len(files)} files present in R2; current individuals={rows}")
    return manifest


def cmd_drop_v2(args):
    if not args.yes:
        print("ABORT: drop-v2 requires --yes")
        sys.exit(1)
    r2 = _r2()
    _verify_snapshot_manifest_complete(r2)
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
    freed = before[1] - after[1]
    print(f"[drop-v2] AFTER:  {after[0]} ({after[1]} bytes)  freed={freed} bytes")
    # Codex P1-C: idempotent re-run is OK (tables already gone -> freed <= 0).
    if freed <= 0:
        print("[drop-v2] WARNING: freed <= 0 bytes — tables may already be dropped (idempotent re-run).")
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
        # Codex P1-C: headroom guard — the drop-v2 step should have brought the
        # DB to ~129 MB. If it's still bloated, refuse to insert more.
        size = _db_size(cur)
        if size[1] > DB_SIZE_POPULATE_GUARD_BYTES:
            print(
                f"[populate] ABORT: DB size {size[0]} ({size[1]} bytes) exceeds "
                f"{DB_SIZE_POPULATE_GUARD_BYTES} bytes — run drop-v2 first."
            )
            conn.rollback()
            conn.close()
            sys.exit(1)

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

        # Codex P1-B: enforce NOT NULL on the relationship key columns so the
        # composite unique index (community_id, edge_key) can't be bypassed by
        # NULLs. Verify no NULLs remain before SET NOT NULL (fail-loud otherwise).
        cur.execute(
            "SELECT count(*) FROM gedcom_relationships "
            "WHERE community_id IS NULL OR version_number IS NULL "
            "OR edge_key IS NULL OR payload_hash IS NULL"
        )
        n_null = cur.fetchone()[0]
        if n_null:
            raise RuntimeError(
                f"{n_null} gedcom_relationships rows have NULL key columns — "
                "cannot SET NOT NULL. Aborting (rollback)."
            )
        print("[populate]   SET NOT NULL on community_id, version_number, edge_key, payload_hash")
        cur.execute(
            "ALTER TABLE gedcom_relationships "
            "ALTER COLUMN community_id SET NOT NULL, "
            "ALTER COLUMN version_number SET NOT NULL, "
            "ALTER COLUMN edge_key SET NOT NULL, "
            "ALTER COLUMN payload_hash SET NOT NULL"
        )

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
# Relationship columns persisted to the canonical table (for snapshot/baseline).
RELATIONSHIP_COLUMNS = [
    "edge_key",
    "individual_gedcom_id",
    "related_gedcom_id",
    "relationship_type",
    "family_gedcom_id",
    "relationship_payload",
    "payload_hash",
]

# Codex P0-B: the canonical DB holds individuals + families + relationships, so
# the v9 baseline snapshot/diff covers ALL THREE. sources/media are NOT in the
# canonical DB and are intentionally omitted from the baseline (see the note
# written into gedcom_versions.notes — they remain preserved in the f783
# raw.ged.gz + the Session-156 archives + the Session-164 v2 full backup).
BASELINE_ENTITY_TYPES = ("individuals", "families", "relationships")


def _baseline_entity_iter(cur):
    """Yield (entity_type, entity_id, payload) for individuals, families,
    relationships streamed from the canonical tables in chunks (P0-B, P0-stream)."""
    # individuals
    cur.execute(
        f"SELECT {', '.join(imp.INDIVIDUAL_COLUMNS)} FROM gedcom_individuals "
        "WHERE community_id = %s ORDER BY gedcom_id",
        (COMMUNITY,),
    )
    while True:
        rows = cur.fetchmany(CHUNK)
        if not rows:
            break
        for row in rows:
            payload = {c: v for c, v in zip(imp.INDIVIDUAL_COLUMNS, row)}
            yield "individuals", payload["gedcom_id"], payload
    # families
    cur.execute(
        f"SELECT {', '.join(imp.FAMILY_COLUMNS)} FROM gedcom_families "
        "WHERE community_id = %s ORDER BY family_gedcom_id",
        (COMMUNITY,),
    )
    while True:
        rows = cur.fetchmany(CHUNK)
        if not rows:
            break
        for row in rows:
            payload = {c: v for c, v in zip(imp.FAMILY_COLUMNS, row)}
            yield "families", payload["family_gedcom_id"], payload
    # relationships (140,796 rows — chunked, never loaded all at once)
    cur.execute(
        f"SELECT {', '.join(RELATIONSHIP_COLUMNS)} FROM gedcom_relationships "
        "WHERE community_id = %s ORDER BY edge_key",
        (COMMUNITY,),
    )
    while True:
        rows = cur.fetchmany(CHUNK)
        if not rows:
            break
        for row in rows:
            payload = {c: v for c, v in zip(RELATIONSHIP_COLUMNS, row)}
            yield "relationships", payload["edge_key"], payload


def _build_v9_snapshot_jsonl_gz(cur) -> bytes:
    """Build snapshot.jsonl.gz from the freshly-populated canonical tables.

    One line per entity {entity_type, entity_id, payload, payload_hash} for
    individuals + families + relationships (Codex P0-B). payload here is the
    typed-column projection (the lossless full pre-Session-164 payload is
    retained in the R2 v2 full backup). Streamed in chunks (never all in memory).
    """
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as gz:
        for entity_type, entity_id, payload in _baseline_entity_iter(cur):
            rec = {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "payload": payload,
                "payload_hash": payload.get("payload_hash"),
            }
            gz.write((json.dumps(rec, sort_keys=True, default=str) + "\n").encode("utf-8"))
    return buf.getvalue()


def _build_v9_diff_baseline_gz(cur, generated_at: str, source_hash: str | None) -> bytes:
    """Baseline diff: every entity as an `added` baseline with after=payload.

    Codex P0-B: covers individuals + families + relationships. Streamed (the
    `entities` dict accumulates IDs, but each baseline item is small). Codex P2:
    the diff_summary built from this is the 5-type IDs-inclusive shape.
    """
    entities: dict[str, dict[str, list]] = {
        et: {"added": [], "modified": [], "removed": []} for et in BASELINE_ENTITY_TYPES
    }
    for entity_type, entity_id, payload in _baseline_entity_iter(cur):
        entities[entity_type]["added"].append(
            {
                "entity_type": entity_type,
                "entity_id": entity_id,
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


def build_baseline_diff_summary(
    counts: dict[str, int], ids: dict[str, list[str]] | None = None
) -> dict[str, Any]:
    """Pure builder for the baseline diff_summary (Codex P2).

    Produces the 5-type IDs-inclusive shape that the importer's
    ``gedcom_history.build_diff_summary`` emits:
    ``{<type>: {added, modified, removed, ids: {added, modified, removed}}}`` for
    each of the 5 DIFF_ENTITY_TYPES. The baseline only has `added` entities;
    modified/removed are always empty/zero. ``counts`` maps type -> added count;
    ``ids`` (optional) maps type -> list of added entity ids.
    """
    ids = ids or {}
    summary: dict[str, Any] = {}
    for et in gh.DIFF_ENTITY_TYPES:
        added_ids = list(ids.get(et, []))
        added_count = counts.get(et, len(added_ids))
        summary[et] = {
            "added": added_count,
            "modified": 0,
            "removed": 0,
            "ids": {"added": added_ids, "modified": [], "removed": []},
        }
    summary["note"] = (
        "baseline (Session 164 migration); covers individuals/families/"
        "relationships only — sources/media preserved in raw.ged.gz + "
        "Session-156 archives + Session-164 v2 full backup"
    )
    return summary


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

        # diff_summary (counts + ids) for the version row — Codex P0-B/P2:
        # 5-type IDs-inclusive shape covering individuals/families/relationships.
        cur.execute("SELECT count(*) FROM gedcom_individuals WHERE community_id = %s", (COMMUNITY,))
        n_ind = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM gedcom_families WHERE community_id = %s", (COMMUNITY,))
        n_fam = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM gedcom_relationships WHERE community_id = %s", (COMMUNITY,))
        n_rel = cur.fetchone()[0]
        diff_summary = build_baseline_diff_summary(
            {"individuals": n_ind, "families": n_fam, "relationships": n_rel}
        )

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
                " [S164: raw.ged.gz is archived f783, closest-available; exact f778 bytes not archived. "
                "Baseline snapshot covers individuals/families/relationships only; "
                "sources/media preserved in f783 raw.ged.gz + Session-156 archives + Session-164 v2 full backup]",
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

    # Codex P0-C: relationships count > 0 AND near expected; edge-set non-empty.
    cur.execute("SELECT count(*), count(DISTINCT edge_key) FROM gedcom_relationships WHERE community_id = %s", (COMMUNITY,))
    rel_n, rel_d = cur.fetchone()
    check("relationships count > 0", rel_n > 0, f"(count={rel_n})")
    check("relationships count near expected", abs(rel_n - EXPECTED_RELATIONSHIPS) <= 100, f"(count={rel_n} expected~{EXPECTED_RELATIONSHIPS})")
    check("relationships edge-set non-empty (count==distinct edge_key)", rel_n == rel_d and rel_d > 0, f"(count={rel_n} distinct_edge={rel_d})")

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

    # Codex P0-C: HARD DB-size gate — FAIL if the database exceeds 300 MB.
    size = _db_size(cur)
    check(
        "DB size under 300 MB",
        size[1] <= DB_SIZE_HARD_LIMIT_BYTES,
        f"({size[0]} = {size[1]} bytes; limit {DB_SIZE_HARD_LIMIT_BYTES})",
    )
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
