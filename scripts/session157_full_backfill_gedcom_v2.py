#!/usr/bin/env python3
"""
Session 157b — Track B1: Full backfill catching post-cutover v1 rows.

PRD-063 Day 2: After Session 156 cut over to v2 at 2026-05-08T04:56:15Z, any
new is_current=TRUE rows added to v1 by concurrent genealogy sessions must
land in v2 too — the dual-read window relies on v2 being a complete superset
of v1 for canonical fields.

This script reads gedcom_individuals + gedcom_families rows where
is_current=TRUE AND created_at > cutover_ts, computes payload_hash (or
re-uses v1's column), and INSERTs into v2 with ON CONFLICT (payload_hash)
DO NOTHING. Updates last_seen_version when a higher version_number row
arrives for an already-known payload.

If post-cutover delta is 0 (no concurrent imports): script logs "no-op
confirmed" and exits clean. The 0-delta path is the EXPECTED outcome based
on Phase 157b-0 carry verification.

Per concurrency rule R1: hold .claude/parallel_session_active during
--execute. Per Lesson 173: paginate via psycopg2 server-side cursor.

Usage:
    python scripts/session157_full_backfill_gedcom_v2.py --dry-run
    python scripts/session157_full_backfill_gedcom_v2.py --execute
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

# Cutover timestamp from Session 156 Track B5 (PRD-063 Day 1 backfill).
# AD-244 cites this as the boundary between "captured by Day 1 backfill" and
# "must be caught by Day 2 catch-up backfill".
CUTOVER_TS = "2026-05-08T04:56:15Z"

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
    return psycopg2.connect(
        host=POOLER_HOST,
        port=POOLER_PORT,
        user=POOLER_USER,
        password=pw,
        database="postgres",
        connect_timeout=30,
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


def _backfill_table(
    conn,
    *,
    v1_table: str,
    v2_table: str,
    key_fields: list[str],
    insert_columns: list[str],
    cutover_ts: str,
    dry_run: bool,
) -> dict:
    """Generic backfill driver shared by individuals + families.

    Reads v1 rows is_current=TRUE AND created_at > cutover_ts. INSERTs into
    v2 with ON CONFLICT (payload_hash) DO NOTHING. Tracks last_seen_version
    via post-insert UPDATE for hashes that already exist in v2.
    """
    import psycopg2.extras

    print(f"\n=== Backfilling {v2_table} (post-cutover) ===")
    print(f"  source: {v1_table} WHERE is_current=TRUE AND created_at > '{cutover_ts}'")

    version_map = _get_version_number_map(conn)

    col_cur = conn.cursor()
    col_cur.execute(f"SELECT * FROM {v1_table} LIMIT 0")
    cols = [d[0] for d in col_cur.description]
    col_cur.close()

    cur_name = f"backfill_{v2_table}_{uuid.uuid4().hex[:8]}"
    cur = conn.cursor(name=cur_name)
    cur.itersize = 5000
    cur.execute(
        f"SELECT * FROM {v1_table} WHERE is_current = TRUE AND created_at > %s",
        (cutover_ts,),
    )

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
                phash = _canonical_payload_hash(obj, key_fields)
                fallback_hash_count += 1

            v_uuid = str(obj.get("version_id")) if obj.get("version_id") else None
            v_num = version_map.get(v_uuid, 0)

            existing = aggregated.get(phash)
            if existing is None:
                row_record = {col: obj.get(col) for col in insert_columns}
                row_record["payload_hash"] = phash
                row_record["first_seen_version"] = v_num
                row_record["last_seen_version"] = v_num
                row_record.setdefault("community_id", obj.get("community_id") or "rhodesli")
                aggregated[phash] = row_record
            else:
                if v_num < existing["first_seen_version"]:
                    existing["first_seen_version"] = v_num
                if v_num > existing["last_seen_version"]:
                    existing["last_seen_version"] = v_num

    cur.close()

    print(f"  v1 post-cutover rows scanned: {seen_count}")
    print(f"  unique payload_hashes: {len(aggregated)}")
    print(f"  fallback hashes computed (NULL v1 payload_hash): {fallback_hash_count}")

    if seen_count == 0:
        print(f"  [NO-OP] no post-cutover rows in {v1_table} — nothing to backfill")
        return {
            "phase": v2_table,
            "v1_post_cutover_rows": 0,
            "unique_payload_hashes": 0,
            "fallback_hashes_computed": 0,
            "no_op": True,
            "dry_run": dry_run,
        }

    if dry_run:
        print("  [DRY-RUN] not inserting")
        return {
            "phase": v2_table,
            "v1_post_cutover_rows": seen_count,
            "unique_payload_hashes": len(aggregated),
            "fallback_hashes_computed": fallback_hash_count,
            "no_op": False,
            "dry_run": True,
        }

    # Build INSERT
    write_cur = conn.cursor()
    json_columns = {
        "names_json", "events_json", "family_as_spouse_json", "family_as_child_json",
        "notes_json", "citations_json", "children_xrefs_json", "events_family_json",
    }
    full_columns = list(insert_columns) + ["payload_hash", "first_seen_version", "last_seen_version", "community_id"]
    placeholders = "%s"
    column_list = ", ".join(full_columns)
    insert_sql = (
        f"INSERT INTO {v2_table} ({column_list}) VALUES %s "
        f"ON CONFLICT (payload_hash) DO NOTHING"
    )

    rows = []
    for h, d in aggregated.items():
        row_tuple = []
        for col in full_columns:
            v = d.get(col)
            if col in json_columns:
                row_tuple.append(json.dumps(v) if v is not None else "[]")
            else:
                row_tuple.append(v)
        rows.append(tuple(row_tuple))

    t0 = time.time()
    psycopg2.extras.execute_values(write_cur, insert_sql, rows, page_size=1000)
    conn.commit()
    elapsed = time.time() - t0

    # Update last_seen_version for already-existing hashes whose v_num is higher
    update_count = 0
    for h, d in aggregated.items():
        write_cur.execute(
            f"UPDATE {v2_table} SET last_seen_version = GREATEST(last_seen_version, %s) "
            f"WHERE payload_hash = %s AND last_seen_version < %s",
            (d["last_seen_version"], h, d["last_seen_version"]),
        )
        update_count += write_cur.rowcount
    conn.commit()

    write_cur.execute(f"SELECT COUNT(*) FROM {v2_table}")
    v2_count = write_cur.fetchone()[0]
    write_cur.close()

    print(f"  inserted in {elapsed:.1f}s")
    print(f"  {v2_table} total row count after backfill: {v2_count}")
    print(f"  last_seen_version updates: {update_count}")

    return {
        "phase": v2_table,
        "v1_post_cutover_rows": seen_count,
        "unique_payload_hashes": len(aggregated),
        "fallback_hashes_computed": fallback_hash_count,
        "v2_row_count_after": v2_count,
        "last_seen_version_updates": update_count,
        "insert_seconds": round(elapsed, 2),
        "no_op": False,
        "dry_run": False,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true", help="Apply changes (default is dry-run)")
    ap.add_argument("--dry-run", action="store_true", default=True, help="Show what would change")
    args = ap.parse_args()

    dry_run = not args.execute
    print(f"Session 157b — PRD-063 Day 2 catch-up backfill (cutover_ts={CUTOVER_TS})")
    print(f"Mode: {'DRY-RUN' if dry_run else 'EXECUTE'}")

    conn = get_conn()
    results = {
        "session": "157b",
        "track": "B1",
        "cutover_ts": CUTOVER_TS,
        "started_at": dt.datetime.utcnow().isoformat() + "Z",
        "dry_run": dry_run,
        "phases": [],
    }

    individual_columns = [
        "gedcom_id", "name", "given_name", "surname", "gender",
        "birth_date", "birth_place", "death_date", "death_place",
        "names_json", "events_json", "family_as_spouse_json", "family_as_child_json",
        "notes_json", "citations_json",
    ]
    results["phases"].append(
        _backfill_table(
            conn,
            v1_table="gedcom_individuals",
            v2_table="gedcom_individuals_v2",
            key_fields=INDIVIDUAL_KEY_FIELDS,
            insert_columns=individual_columns,
            cutover_ts=CUTOVER_TS,
            dry_run=dry_run,
        )
    )

    family_columns = [
        "family_gedcom_id", "husband_xref", "wife_xref",
        "children_xrefs_json", "events_family_json",
    ]
    # gedcom_families may have different columns; introspect via _family_has_is_current path
    fam_col_cur = conn.cursor()
    fam_col_cur.execute("SELECT * FROM gedcom_families LIMIT 0")
    fam_cols = {d[0] for d in fam_col_cur.description}
    fam_col_cur.close()
    family_columns = [c for c in family_columns if c in fam_cols]
    if "family_gedcom_id" not in family_columns:
        # fall back to whatever the v1 table actually has
        family_columns = sorted(fam_cols & {
            "family_gedcom_id", "husband_xref", "wife_xref",
            "children_xrefs_json", "events_family_json",
            "name", "marriage_date", "marriage_place",
        })

    results["phases"].append(
        _backfill_table(
            conn,
            v1_table="gedcom_families",
            v2_table="gedcom_families_v2",
            key_fields=FAMILY_KEY_FIELDS,
            insert_columns=family_columns,
            cutover_ts=CUTOVER_TS,
            dry_run=dry_run,
        )
    )

    results["completed_at"] = dt.datetime.utcnow().isoformat() + "Z"
    conn.close()

    out_path = PROJECT_ROOT / "docs" / "feedback" / "session-157b-day-2-backfill-report.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Session 157b — PRD-063 Day 2 Catch-Up Backfill Report\n"]
    lines.append(f"**Mode**: {'DRY-RUN' if dry_run else 'EXECUTE'}\n")
    lines.append(f"**Cutover timestamp**: `{CUTOVER_TS}`\n")
    lines.append(f"**Started**: {results['started_at']}\n")
    lines.append(f"**Completed**: {results['completed_at']}\n\n")
    lines.append("## Phases\n\n")
    for p in results["phases"]:
        lines.append(f"### {p['phase']}\n")
        for k, v in p.items():
            if k == "phase":
                continue
            lines.append(f"- `{k}`: `{v}`\n")
        lines.append("\n")
    out_path.write_text("".join(lines))
    print(f"\nReport written to {out_path}")

    print("\n=== SUMMARY ===")
    for p in results["phases"]:
        if p.get("no_op"):
            print(f"  {p['phase']}: NO-OP (0 post-cutover rows)")
        elif p.get("dry_run"):
            print(f"  {p['phase']}: DRY-RUN — {p['unique_payload_hashes']} unique hashes from {p['v1_post_cutover_rows']} rows")
        else:
            print(f"  {p['phase']}: EXECUTED — {p['v1_post_cutover_rows']} rows, {p.get('insert_seconds', 0)}s")


if __name__ == "__main__":
    main()
