#!/usr/bin/env python3
"""
Session 156 — Track B5: Initial backfill from v1 to v2 GEDCOM tables.

PRD-063 §6 Step 3: Backfill v2 from is_current=TRUE rows of v1 tables.
ON CONFLICT (payload_hash) DO NOTHING to skip dedup.

Per concurrency rule R3: this is READ-ONLY on v1, INSERT-ONLY on v2.
Genealogy session writes to v1 during our backfill won't appear in v2 yet
(Session 157's "full backfill + dual-read confidence check" picks them up).

Per Lesson 173: paginate via psycopg2 server-side cursors (NOT Supabase REST).

What gets backfilled:
  - gedcom_individuals_v2 from gedcom_individuals WHERE is_current=TRUE
  - gedcom_families_v2 from gedcom_families WHERE is_current=TRUE
  - gedcom_change_manifest with one summary row per gedcom_versions row

payload_hash strategy:
  v1 rows already have a payload_hash column populated by the v1 importer.
  We re-use it. If a row's payload_hash is NULL (legacy), we compute SHA256
  of canonical JSON of identifying fields.

Usage:
    python scripts/session156_backfill_gedcom_v2.py --dry-run
    python scripts/session156_backfill_gedcom_v2.py --execute
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
import time
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
except Exception:
    pass

POOLER_HOST = "aws-0-us-west-2.pooler.supabase.com"
POOLER_PORT = 6543
POOLER_USER = "postgres.fvynibivlphxwfowzkjl"


def get_conn():
    import psycopg2

    pw = os.environ.get("SUPABASE_DB_PASSWORD")
    if not pw:
        sys.exit("ERROR: SUPABASE_DB_PASSWORD not set")
    return psycopg2.connect(
        host=POOLER_HOST,
        port=POOLER_PORT,
        user=POOLER_USER,
        password=pw,
        database="postgres",
        connect_timeout=30,
    )


def _canonical_payload_hash(rec: dict, key_fields: list[str]) -> str:
    """Compute SHA256 over canonical JSON of selected fields. Stable on
    insertion order via sorted keys + ensure_ascii=False + separators."""
    payload = {k: rec.get(k) for k in key_fields}
    s = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


# Identifying fields used to fall back when payload_hash is NULL on v1 rows
INDIVIDUAL_KEY_FIELDS = [
    "gedcom_id",
    "name",
    "given_name",
    "surname",
    "gender",
    "birth_date",
    "birth_place",
    "death_date",
    "death_place",
]

FAMILY_KEY_FIELDS = [
    "family_gedcom_id",
    "husband_xref",
    "wife_xref",
]


def _get_version_number_map(conn) -> dict[str, int]:
    """Return mapping from version_id (UUID str) -> version_number (int)."""
    cur = conn.cursor()
    cur.execute("SELECT id, version_number FROM gedcom_versions")
    m = {str(r[0]): int(r[1]) for r in cur.fetchall()}
    cur.close()
    return m


def backfill_individuals(conn, dry_run: bool, cutover_ts: str) -> dict:
    """Backfill gedcom_individuals_v2."""
    import psycopg2.extras

    print("\n=== Backfilling gedcom_individuals_v2 ===")

    version_map = _get_version_number_map(conn)
    print(f"  version_map: {len(version_map)} versions")

    # Use server-side cursor to stream
    col_cur = conn.cursor()
    col_cur.execute("SELECT * FROM gedcom_individuals LIMIT 0")
    cols = [d[0] for d in col_cur.description]
    col_cur.close()
    print(f"  v1 columns ({len(cols)}): {', '.join(cols[:8])}...")

    cur_name = f"backfill_indiv_{uuid.uuid4().hex[:8]}"
    cur = conn.cursor(name=cur_name)
    cur.itersize = 5000
    cur.execute("SELECT * FROM gedcom_individuals WHERE is_current = TRUE")

    # Aggregate per-payload-hash: track first/last seen versions
    # We'll INSERT all unique payload_hashes, then UPDATE first/last_seen.
    # But ON CONFLICT DO NOTHING means we INSERT only the first occurrence —
    # so we need to compute first/last_seen across the WHOLE result set first,
    # then INSERT.
    #
    # Strategy: stream once into an in-memory dict keyed by payload_hash.
    # 22K rows is small enough for a single dict.

    aggregated: dict[str, dict] = {}
    seen_count = 0
    fallback_hash_count = 0

    while True:
        batch = cur.fetchmany(5000)
        if not batch:
            break
        for r in batch:
            obj = dict(zip(cols, r))
            seen_count += 1

            phash = obj.get("payload_hash")
            if not phash:
                phash = _canonical_payload_hash(obj, INDIVIDUAL_KEY_FIELDS)
                fallback_hash_count += 1

            v_uuid = str(obj.get("version_id")) if obj.get("version_id") else None
            v_num = version_map.get(v_uuid)
            if v_num is None:
                # Legacy unversioned row (Capeluto Rhodes pre-Migration-002 per E0.5)
                v_num = 0  # represent as v0-equivalent

            existing = aggregated.get(phash)
            if existing is None:
                aggregated[phash] = {
                    "gedcom_id": obj.get("gedcom_id"),
                    "name": obj.get("name"),
                    "given_name": obj.get("given_name"),
                    "surname": obj.get("surname"),
                    "gender": obj.get("gender"),
                    "birth_date": obj.get("birth_date"),
                    "birth_place": obj.get("birth_place"),
                    "death_date": obj.get("death_date"),
                    "death_place": obj.get("death_place"),
                    "names_json": obj.get("names_json") or [],
                    "events_json": obj.get("events_json") or [],
                    "family_as_spouse_json": obj.get("family_as_spouse_json") or [],
                    "family_as_child_json": obj.get("family_as_child_json") or [],
                    "notes_json": obj.get("notes_json") or [],
                    "citations_json": obj.get("citations_json") or [],
                    "payload_hash": phash,
                    "first_seen_version": v_num,
                    "last_seen_version": v_num,
                    "community_id": "rhodesli",
                }
            else:
                if v_num < existing["first_seen_version"]:
                    existing["first_seen_version"] = v_num
                if v_num > existing["last_seen_version"]:
                    existing["last_seen_version"] = v_num

    cur.close()

    print(f"  v1 is_current=TRUE rows scanned: {seen_count}")
    print(f"  unique payload_hashes: {len(aggregated)}")
    print(
        f"  fallback hashes computed (NULL v1 payload_hash): {fallback_hash_count}"
    )
    print(f"  dedup factor: {seen_count / max(len(aggregated), 1):.2f}×")

    if dry_run:
        print("  [DRY-RUN] not inserting")
        return {
            "phase": "individuals",
            "dry_run": True,
            "v1_scanned": seen_count,
            "unique_payload_hashes": len(aggregated),
            "fallback_hashes_computed": fallback_hash_count,
        }

    # INSERT in batches with ON CONFLICT DO NOTHING
    print("  inserting into gedcom_individuals_v2 (ON CONFLICT DO NOTHING)...")
    write_cur = conn.cursor()
    insert_sql = """
        INSERT INTO gedcom_individuals_v2 (
            gedcom_id, name, given_name, surname, gender,
            birth_date, birth_place, death_date, death_place,
            names_json, events_json, family_as_spouse_json, family_as_child_json,
            notes_json, citations_json,
            payload_hash, first_seen_version, last_seen_version, community_id
        ) VALUES %s
        ON CONFLICT (payload_hash) DO NOTHING
    """

    rows = []
    for h, d in aggregated.items():
        rows.append(
            (
                d["gedcom_id"],
                d["name"],
                d["given_name"],
                d["surname"],
                d["gender"],
                d["birth_date"],
                d["birth_place"],
                d["death_date"],
                d["death_place"],
                json.dumps(d["names_json"]) if d["names_json"] is not None else "[]",
                json.dumps(d["events_json"]) if d["events_json"] is not None else "[]",
                json.dumps(d["family_as_spouse_json"]) if d["family_as_spouse_json"] is not None else "[]",
                json.dumps(d["family_as_child_json"]) if d["family_as_child_json"] is not None else "[]",
                json.dumps(d["notes_json"]) if d["notes_json"] is not None else "[]",
                json.dumps(d["citations_json"]) if d["citations_json"] is not None else "[]",
                d["payload_hash"],
                d["first_seen_version"],
                d["last_seen_version"],
                d["community_id"],
            )
        )

    t0 = time.time()
    psycopg2.extras.execute_values(write_cur, insert_sql, rows, page_size=1000)
    conn.commit()
    elapsed = time.time() - t0

    # Verify
    write_cur.execute("SELECT COUNT(*) FROM gedcom_individuals_v2")
    v2_count = write_cur.fetchone()[0]
    write_cur.execute("SELECT COUNT(DISTINCT gedcom_id) FROM gedcom_individuals_v2")
    distinct_gedcom_id = write_cur.fetchone()[0]
    write_cur.execute(
        "SELECT pg_size_pretty(pg_total_relation_size('gedcom_individuals_v2'))"
    )
    size_pretty = write_cur.fetchone()[0]
    write_cur.close()

    print(f"  inserted in {elapsed:.1f}s")
    print(f"  gedcom_individuals_v2 row count: {v2_count}")
    print(f"  distinct gedcom_id in v2: {distinct_gedcom_id}")
    print(f"  table size: {size_pretty}")

    return {
        "phase": "individuals",
        "v1_scanned": seen_count,
        "unique_payload_hashes": len(aggregated),
        "fallback_hashes_computed": fallback_hash_count,
        "v2_row_count": v2_count,
        "v2_distinct_gedcom_id": distinct_gedcom_id,
        "v2_size": size_pretty,
        "insert_seconds": round(elapsed, 2),
    }


def _family_has_is_current(conn) -> bool:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='public'
          AND table_name='gedcom_families'
          AND column_name='is_current'
        """
    )
    r = cur.fetchone()
    cur.close()
    return r is not None


def backfill_families(conn, dry_run: bool) -> dict:
    """Backfill gedcom_families_v2."""
    import psycopg2.extras

    print("\n=== Backfilling gedcom_families_v2 ===")
    version_map = _get_version_number_map(conn)

    has_is_current = _family_has_is_current(conn)
    where_clause = "WHERE is_current = TRUE" if has_is_current else ""
    print(f"  gedcom_families.is_current: {'YES' if has_is_current else 'NO (using all rows)'}")

    col_cur = conn.cursor()
    col_cur.execute("SELECT * FROM gedcom_families LIMIT 0")
    cols = [d[0] for d in col_cur.description]
    col_cur.close()

    cur_name = f"backfill_fam_{uuid.uuid4().hex[:8]}"
    cur = conn.cursor(name=cur_name)
    cur.itersize = 5000
    cur.execute(f"SELECT * FROM gedcom_families {where_clause}")

    aggregated: dict[str, dict] = {}
    seen_count = 0
    fallback_hash_count = 0

    while True:
        batch = cur.fetchmany(5000)
        if not batch:
            break
        for r in batch:
            obj = dict(zip(cols, r))
            seen_count += 1

            phash = obj.get("payload_hash")
            if not phash:
                phash = _canonical_payload_hash(obj, FAMILY_KEY_FIELDS)
                fallback_hash_count += 1

            v_uuid = str(obj.get("version_id")) if obj.get("version_id") else None
            v_num = version_map.get(v_uuid, 0)

            existing = aggregated.get(phash)
            if existing is None:
                aggregated[phash] = {
                    "family_gedcom_id": obj.get("family_gedcom_id"),
                    "husband_xref": obj.get("husband_xref"),
                    "wife_xref": obj.get("wife_xref"),
                    "children_xrefs_json": obj.get("children_xrefs_json") or [],
                    "marriage_event_json": obj.get("marriage_event_json") or {},
                    "events_json": obj.get("events_json") or [],
                    "notes_json": obj.get("notes_json") or [],
                    "citations_json": obj.get("citations_json") or [],
                    "payload_hash": phash,
                    "first_seen_version": v_num,
                    "last_seen_version": v_num,
                    "community_id": "rhodesli",
                }
            else:
                if v_num < existing["first_seen_version"]:
                    existing["first_seen_version"] = v_num
                if v_num > existing["last_seen_version"]:
                    existing["last_seen_version"] = v_num
    cur.close()

    print(f"  v1 rows scanned: {seen_count}")
    print(f"  unique payload_hashes: {len(aggregated)}")
    print(f"  fallback hashes computed: {fallback_hash_count}")

    if dry_run:
        print("  [DRY-RUN] not inserting")
        return {
            "phase": "families",
            "dry_run": True,
            "v1_scanned": seen_count,
            "unique_payload_hashes": len(aggregated),
        }

    write_cur = conn.cursor()
    insert_sql = """
        INSERT INTO gedcom_families_v2 (
            family_gedcom_id, husband_xref, wife_xref,
            children_xrefs_json, marriage_event_json, events_json,
            notes_json, citations_json,
            payload_hash, first_seen_version, last_seen_version, community_id
        ) VALUES %s
        ON CONFLICT (payload_hash) DO NOTHING
    """
    rows = []
    for h, d in aggregated.items():
        rows.append(
            (
                d["family_gedcom_id"],
                d["husband_xref"],
                d["wife_xref"],
                json.dumps(d["children_xrefs_json"]) if d["children_xrefs_json"] is not None else "[]",
                json.dumps(d["marriage_event_json"]) if d["marriage_event_json"] is not None else "{}",
                json.dumps(d["events_json"]) if d["events_json"] is not None else "[]",
                json.dumps(d["notes_json"]) if d["notes_json"] is not None else "[]",
                json.dumps(d["citations_json"]) if d["citations_json"] is not None else "[]",
                d["payload_hash"],
                d["first_seen_version"],
                d["last_seen_version"],
                d["community_id"],
            )
        )

    t0 = time.time()
    psycopg2.extras.execute_values(write_cur, insert_sql, rows, page_size=1000)
    conn.commit()
    elapsed = time.time() - t0

    write_cur.execute("SELECT COUNT(*) FROM gedcom_families_v2")
    v2_count = write_cur.fetchone()[0]
    write_cur.execute(
        "SELECT pg_size_pretty(pg_total_relation_size('gedcom_families_v2'))"
    )
    size_pretty = write_cur.fetchone()[0]
    write_cur.close()

    print(f"  inserted in {elapsed:.1f}s")
    print(f"  gedcom_families_v2 row count: {v2_count}")
    print(f"  table size: {size_pretty}")

    return {
        "phase": "families",
        "v1_scanned": seen_count,
        "unique_payload_hashes": len(aggregated),
        "fallback_hashes_computed": fallback_hash_count,
        "v2_row_count": v2_count,
        "v2_size": size_pretty,
        "insert_seconds": round(elapsed, 2),
    }


def backfill_change_manifest(conn, dry_run: bool) -> dict:
    """One row per existing gedcom_versions row. Summary populated from
    existing summary JSONB on gedcom_versions; full per-version diff
    manifests deferred to Session 157."""
    import psycopg2.extras

    print("\n=== Backfilling gedcom_change_manifest ===")
    cur = conn.cursor()
    cur.execute(
        """
        SELECT version_number, community_id, imported_at, summary,
               source_file, source_hash
        FROM gedcom_versions
        ORDER BY version_number ASC
        """
    )
    rows_v = cur.fetchall()
    cur.close()
    print(f"  gedcom_versions rows: {len(rows_v)}")

    if dry_run:
        print("  [DRY-RUN] not inserting")
        return {"phase": "change_manifest", "dry_run": True, "rows": len(rows_v)}

    write_cur = conn.cursor()
    insert_sql = """
        INSERT INTO gedcom_change_manifest (
            version_number, community_id, imported_at, summary_jsonb,
            source_file, source_hash
        ) VALUES %s
        ON CONFLICT (community_id, version_number) DO NOTHING
    """
    payload = []
    for r in rows_v:
        v_num, comm, imported_at, summary, source_file, source_hash = r
        payload.append(
            (
                v_num,
                comm,
                imported_at,
                json.dumps(summary) if summary is not None else "{}",
                source_file,
                source_hash,
            )
        )
    psycopg2.extras.execute_values(write_cur, insert_sql, payload, page_size=100)
    conn.commit()

    write_cur.execute("SELECT COUNT(*) FROM gedcom_change_manifest")
    n = write_cur.fetchone()[0]
    write_cur.close()
    print(f"  gedcom_change_manifest row count: {n}")
    return {"phase": "change_manifest", "rows_inserted": n, "v1_versions": len(rows_v)}


def measure_v1_baseline(conn) -> dict:
    cur = conn.cursor()
    out = {}
    for table in [
        "gedcom_individuals",
        "gedcom_families",
        "gedcom_change_log",
        "gedcom_records",
        "gedcom_events",
        "gedcom_relationships",
    ]:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        n = cur.fetchone()[0]
        cur.execute(f"SELECT pg_size_pretty(pg_total_relation_size('{table}'))")
        sz = cur.fetchone()[0]
        out[table] = {"row_count": n, "size": sz}
    cur.close()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()
    if not args.dry_run and not args.execute:
        ap.error("Pass --dry-run or --execute")

    conn = get_conn()
    print(f"Connected to {POOLER_HOST}:{POOLER_PORT}")

    cutover_ts = dt.datetime.utcnow().isoformat() + "Z"
    print(f"Cutover timestamp (start of v1 SELECT): {cutover_ts}")
    print("Genealogy session writes to v1 AFTER this timestamp will not be in v2.")
    print("They will be picked up in Session 157's full backfill.")
    print()

    # Pre-flight: confirm v2 tables exist (B4 must have run first)
    cur = conn.cursor()
    for t in ["gedcom_individuals_v2", "gedcom_families_v2", "gedcom_change_manifest"]:
        cur.execute("SELECT to_regclass(%s)", (f"public.{t}",))
        if cur.fetchone()[0] is None:
            sys.exit(f"ABORT: {t} does not exist. Run B4 (apply v2 schema) first.")
    cur.close()
    print("v2 tables: all exist")

    baseline_v1 = measure_v1_baseline(conn)
    print("\nv1 baseline (read-only):")
    for t, info in baseline_v1.items():
        print(f"  {t:<28} rows={info['row_count']:>10}  size={info['size']}")

    out = {
        "cutover_ts": cutover_ts,
        "v1_baseline": baseline_v1,
        "phases": [],
    }

    out["phases"].append(backfill_individuals(conn, args.dry_run, cutover_ts))
    out["phases"].append(backfill_families(conn, args.dry_run))
    out["phases"].append(backfill_change_manifest(conn, args.dry_run))

    # Final size measurements
    if not args.dry_run:
        print("\n=== Final v2 sizes ===")
        cur = conn.cursor()
        for t in ["gedcom_individuals_v2", "gedcom_families_v2", "gedcom_change_manifest"]:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            n = cur.fetchone()[0]
            cur.execute(f"SELECT pg_size_pretty(pg_total_relation_size('{t}'))")
            sz = cur.fetchone()[0]
            print(f"  {t:<32} rows={n:>8}  size={sz}")
        cur.close()

    # Persist results to local artifact
    out_path = (
        PROJECT_ROOT
        / "backups"
        / "session-156"
        / f"backfill_results_{'execute' if args.execute else 'dryrun'}.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, default=str))
    print(f"\nResults: {out_path}")

    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
