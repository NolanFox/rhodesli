#!/usr/bin/env python3
"""
Session 158 Phase 158-2 — Historical backfill from v1 to v2 GEDCOM tables.

Mirrors scripts/session156_backfill_gedcom_v2.py but reads ALL rows (not
filtered by is_current=TRUE). Existing v2 rows from 156's backfill stay
intact. New historical states (different payload_hashes for same gedcom_id)
INSERT alongside. For payload_hashes that already exist in v2, UPDATE
first_seen_version = MIN(existing, computed) and last_seen_version =
MAX(existing, computed).

Per concurrency rule R3: READ-ONLY on v1, INSERT-ONLY (or UPDATE-ONLY for
first/last_seen) on v2.

Per Lesson 173: paginate via psycopg2 server-side cursors.

Usage:
    python scripts/session158_historical_backfill_gedcom_v2.py --dry-run
    python scripts/session158_historical_backfill_gedcom_v2.py --execute
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

# These match scripts/session156_backfill_gedcom_v2.py
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


def get_conn():
    import psycopg2

    pw = os.environ.get("SUPABASE_DB_PASSWORD")
    if not pw:
        sys.exit("ERROR: SUPABASE_DB_PASSWORD not set")
    # keepalives prevent the pooler from dropping idle connections during
    # long server-side cursor reads (Session 158 hit this on the 196K-row
    # historical backfill — first attempt failed with "server closed the
    # connection unexpectedly")
    return psycopg2.connect(
        host=POOLER_HOST,
        port=POOLER_PORT,
        user=POOLER_USER,
        password=pw,
        database="postgres",
        connect_timeout=30,
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=5,
    )


def _canonical_payload_hash(rec: dict, key_fields: list[str]) -> str:
    payload = {k: rec.get(k) for k in key_fields}
    s = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _get_version_number_map(conn) -> dict[str, int]:
    cur = conn.cursor()
    cur.execute("SELECT id, version_number FROM gedcom_versions")
    m = {str(r[0]): int(r[1]) for r in cur.fetchall()}
    cur.close()
    return m


def backfill_table(
    conn,
    *,
    src_table: str,
    dst_table: str,
    dry_run: bool,
    key_fields: list[str],
    record_builder,
    insert_sql: str,
    update_sql: str,
    binder,
    get_conn_fn=None,
):
    """Generic backfill — handles individuals or families.

    Chunks reads by version_id to avoid pooler-killing long server-side
    cursors (Session 158 first-execute attempt failed with "SSL SYSCALL
    error: EOF detected" on a 196K-row stream).

    record_builder(obj, payload_hash, v_num) -> dict (the v2 row)
    binder(record_dict) -> tuple (positional args for insert)
    get_conn_fn: callable that returns a fresh psycopg2 connection (used
                 to reconnect between chunks if the pooler drops us).
    """
    import psycopg2
    import psycopg2.extras

    print(f"\n=== Backfilling {dst_table} from ALL rows of {src_table} ===")

    version_map = _get_version_number_map(conn)
    print(f"  version_map: {len(version_map)} versions")

    col_cur = conn.cursor()
    col_cur.execute(f"SELECT * FROM {src_table} LIMIT 0")
    cols = [d[0] for d in col_cur.description]
    col_cur.close()

    # Build chunk plan: one chunk per version_id + one for NULL
    version_ids = list(version_map.keys())
    chunks = [(v, "id") for v in version_ids] + [(None, "null")]
    print(f"  chunks: {len(chunks)} ({len(version_ids)} versions + 1 NULL chunk)")

    aggregated: dict[str, dict] = {}
    seen_count = 0
    fallback_hash_count = 0
    null_version_count = 0

    def _read_with_retry(query_sql, query_args, label):
        """Open fresh connection, execute, fetchall, close. Retry up to 5×."""
        nonlocal conn
        last_exc = None
        for retry in range(5):
            try:
                conn.close()
            except Exception:
                pass
            conn = get_conn_fn() if get_conn_fn else get_conn()
            cur = conn.cursor()
            try:
                cur.execute(query_sql, query_args)
                batch = cur.fetchall()
                cur.close()
                return batch, conn
            except (psycopg2.OperationalError, psycopg2.InterfaceError) as exc:
                last_exc = exc
                print(f"  [{label}] retry {retry+1}/5: {exc.__class__.__name__}")
                try:
                    conn.close()
                except Exception:
                    pass
                if retry < 4:
                    import time as _t
                    _t.sleep(2 + retry)
        raise last_exc

    for ci, (v_id, kind) in enumerate(chunks):
        if kind == "id":
            batch, conn = _read_with_retry(
                f"SELECT * FROM {src_table} WHERE version_id = %s",
                (v_id,),
                f"chunk {ci+1}/{len(chunks)}",
            )
        else:
            # NULL chunk — paginate by primary key id to avoid "WHERE IS NULL"
            # being expensive. PRIMARY KEY 'id' is indexed.
            batch = []
            page = 0
            page_size = 2000
            while True:
                page_batch, conn = _read_with_retry(
                    f"SELECT * FROM {src_table} WHERE version_id IS NULL "
                    f"ORDER BY id LIMIT {page_size} OFFSET {page * page_size}",
                    None,
                    f"chunk {ci+1}/{len(chunks)} NULL page {page+1}",
                )
                if not page_batch:
                    break
                batch.extend(page_batch)
                if len(page_batch) < page_size:
                    break
                page += 1

        chunk_count = len(batch)
        print(f"  [chunk {ci+1}/{len(chunks)}] v_id={v_id or 'NULL'}: {chunk_count:,} rows")

        for r in batch:
            obj = dict(zip(cols, r))
            seen_count += 1

            phash = obj.get("payload_hash")
            if not phash:
                phash = _canonical_payload_hash(obj, key_fields)
                fallback_hash_count += 1

            v_uuid = str(obj.get("version_id")) if obj.get("version_id") else None
            v_num = version_map.get(v_uuid)
            if v_num is None:
                v_num = 0
                null_version_count += 1

            existing = aggregated.get(phash)
            if existing is None:
                aggregated[phash] = record_builder(obj, phash, v_num)
            else:
                if v_num < existing["first_seen_version"]:
                    existing["first_seen_version"] = v_num
                if v_num > existing["last_seen_version"]:
                    existing["last_seen_version"] = v_num

    print(f"  v1 ALL rows scanned: {seen_count:,}")
    print(f"  unique payload_hashes: {len(aggregated):,}")
    print(f"  fallback hashes computed (NULL v1 payload_hash): {fallback_hash_count:,}")
    print(f"  NULL/unmapped version_id rows: {null_version_count:,}")
    print(f"  dedup factor: {seen_count / max(len(aggregated), 1):.2f}×")

    # Reconnect if previous connection died during chunked reads
    if conn.closed:
        print("  reconnecting for write phase...")
        conn = get_conn_fn() if get_conn_fn else get_conn()

    # Pre-count: how many will be NEW vs UPDATE on existing v2 row?
    write_cur = conn.cursor()
    write_cur.execute(f"SELECT payload_hash FROM {dst_table}")
    existing_v2_hashes = {r[0] for r in write_cur.fetchall()}
    new_inserts = sum(1 for h in aggregated if h not in existing_v2_hashes)
    will_update = sum(1 for h in aggregated if h in existing_v2_hashes)
    print(f"  NEW INSERTs: {new_inserts:,}")
    print(f"  Will UPDATE existing v2 rows: {will_update:,}")
    print(f"  v2 row count after backfill: ~{len(existing_v2_hashes) + new_inserts:,}")

    if dry_run:
        print("  [DRY-RUN] not writing")
        return {
            "phase": dst_table,
            "dry_run": True,
            "v1_scanned": seen_count,
            "unique_payload_hashes": len(aggregated),
            "fallback_hashes": fallback_hash_count,
            "null_version_rows": null_version_count,
            "new_inserts": new_inserts,
            "will_update": will_update,
            "v2_row_count_estimate": len(existing_v2_hashes) + new_inserts,
        }

    print(f"  upserting into {dst_table} (ON CONFLICT (payload_hash) DO UPDATE)...")
    rows = [binder(d) for d in aggregated.values()]

    t0 = time.time()
    psycopg2.extras.execute_values(write_cur, insert_sql, rows, page_size=1000)
    conn.commit()
    elapsed = time.time() - t0

    write_cur.execute(f"SELECT COUNT(*) FROM {dst_table}")
    v2_count = write_cur.fetchone()[0]
    write_cur.execute(f"SELECT pg_size_pretty(pg_total_relation_size('{dst_table}'))")
    size_pretty = write_cur.fetchone()[0]
    write_cur.close()

    print(f"  upserted in {elapsed:.1f}s")
    print(f"  {dst_table} row count: {v2_count:,}")
    print(f"  table size: {size_pretty}")

    return {
        "phase": dst_table,
        "v1_scanned": seen_count,
        "unique_payload_hashes": len(aggregated),
        "fallback_hashes": fallback_hash_count,
        "null_version_rows": null_version_count,
        "new_inserts": new_inserts,
        "updated_existing": will_update,
        "v2_row_count": v2_count,
        "v2_size": size_pretty,
        "upsert_seconds": round(elapsed, 2),
    }


# --- Individuals ---

INDIV_INSERT_SQL = """
    INSERT INTO gedcom_individuals_v2 (
        gedcom_id, name, given_name, surname, gender,
        birth_date, birth_place, death_date, death_place,
        names_json, events_json, family_as_spouse_json, family_as_child_json,
        notes_json, citations_json,
        payload_hash, first_seen_version, last_seen_version, community_id
    ) VALUES %s
    ON CONFLICT (payload_hash) DO UPDATE SET
        first_seen_version = LEAST(gedcom_individuals_v2.first_seen_version, EXCLUDED.first_seen_version),
        last_seen_version = GREATEST(gedcom_individuals_v2.last_seen_version, EXCLUDED.last_seen_version)
"""


def _indiv_record(obj, phash, v_num):
    return {
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


def _indiv_bind(d):
    return (
        d["gedcom_id"], d["name"], d["given_name"], d["surname"], d["gender"],
        d["birth_date"], d["birth_place"], d["death_date"], d["death_place"],
        json.dumps(d["names_json"]),
        json.dumps(d["events_json"]),
        json.dumps(d["family_as_spouse_json"]),
        json.dumps(d["family_as_child_json"]),
        json.dumps(d["notes_json"]),
        json.dumps(d["citations_json"]),
        d["payload_hash"], d["first_seen_version"], d["last_seen_version"], d["community_id"],
    )


# --- Families ---

FAM_INSERT_SQL = """
    INSERT INTO gedcom_families_v2 (
        family_gedcom_id, husband_xref, wife_xref,
        children_xrefs_json, marriage_event_json, events_json,
        notes_json, citations_json,
        payload_hash, first_seen_version, last_seen_version, community_id
    ) VALUES %s
    ON CONFLICT (payload_hash) DO UPDATE SET
        first_seen_version = LEAST(gedcom_families_v2.first_seen_version, EXCLUDED.first_seen_version),
        last_seen_version = GREATEST(gedcom_families_v2.last_seen_version, EXCLUDED.last_seen_version)
"""


def _fam_record(obj, phash, v_num):
    return {
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


def _fam_bind(d):
    return (
        d["family_gedcom_id"], d["husband_xref"], d["wife_xref"],
        json.dumps(d["children_xrefs_json"]),
        json.dumps(d["marriage_event_json"]),
        json.dumps(d["events_json"]),
        json.dumps(d["notes_json"]),
        json.dumps(d["citations_json"]),
        d["payload_hash"], d["first_seen_version"], d["last_seen_version"], d["community_id"],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    dry_run = not args.execute
    print(f"Session 158 Phase 158-2 — Historical backfill (Mode: {'DRY-RUN' if dry_run else 'EXECUTE'})")
    print(f"  Time: {dt.datetime.utcnow().isoformat()}Z")

    summary = {}
    conn = get_conn()
    try:
        summary["individuals"] = backfill_table(
            conn,
            src_table="gedcom_individuals",
            dst_table="gedcom_individuals_v2",
            dry_run=dry_run,
            key_fields=INDIVIDUAL_KEY_FIELDS,
            record_builder=_indiv_record,
            insert_sql=INDIV_INSERT_SQL,
            update_sql=None,
            binder=_indiv_bind,
            get_conn_fn=get_conn,
        )
    finally:
        if conn and not conn.closed:
            try:
                conn.close()
            except Exception:
                pass

    conn = get_conn()
    try:
        summary["families"] = backfill_table(
            conn,
            src_table="gedcom_families",
            dst_table="gedcom_families_v2",
            dry_run=dry_run,
            key_fields=FAMILY_KEY_FIELDS,
            record_builder=_fam_record,
            insert_sql=FAM_INSERT_SQL,
            update_sql=None,
            binder=_fam_bind,
            get_conn_fn=get_conn,
        )
    finally:
        if conn and not conn.closed:
            try:
                conn.close()
            except Exception:
                pass

    # Write report
    report_path = PROJECT_ROOT / "docs" / "feedback" / "session-158-historical-backfill-report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Session 158 Phase 158-2 — Historical Backfill Report",
        "",
        f"**Date**: {dt.datetime.utcnow().isoformat()}Z",
        f"**Mode**: {'DRY-RUN' if dry_run else 'EXECUTE'}",
        "",
        "## Individuals",
        "",
        "```json",
        json.dumps(summary["individuals"], indent=2),
        "```",
        "",
        "## Families",
        "",
        "```json",
        json.dumps(summary["families"], indent=2),
        "```",
        "",
    ]
    report_path.write_text("\n".join(lines))
    print(f"\nReport written to {report_path}")

    print("\n=== SUMMARY ===")
    for phase, s in summary.items():
        if s.get("dry_run"):
            print(f"  {phase}: NEW={s.get('new_inserts')}, UPDATE={s.get('will_update')}, v2 estimate={s.get('v2_row_count_estimate')}")
        else:
            print(f"  {phase}: NEW={s.get('new_inserts')}, UPDATE={s.get('updated_existing')}, v2 row count={s.get('v2_row_count')}, size={s.get('v2_size')}")


if __name__ == "__main__":
    main()
