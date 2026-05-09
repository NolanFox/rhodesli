#!/usr/bin/env python3
"""
Session 158 Phase 158-2 — Historical backfill via Supabase REST.

Replaces the psycopg2 streaming variant after the pooler proved unreliable
for long-running server-side cursors against the 196K-row gedcom_individuals
table (Session 158: 9/10 chunks succeeded, 10th repeatedly failed; on retry,
even the version_map query failed). The REST API has a 1000-row default
limit per call, so we paginate via .range(offset, offset+999).

Mirrors scripts/session156_backfill_gedcom_v2.py output schema. Uses the
same payload_hash strategy + the same ON CONFLICT DO UPDATE for first/last
seen version merging.

Usage:
    python scripts/session158_historical_backfill_rest.py --dry-run
    python scripts/session158_historical_backfill_rest.py --execute
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except Exception:
    pass

from app.supabase_data import get_supabase_client

INDIVIDUAL_KEY_FIELDS = [
    "gedcom_id", "name", "given_name", "surname", "gender",
    "birth_date", "birth_place", "death_date", "death_place",
]
FAMILY_KEY_FIELDS = ["family_gedcom_id", "husband_xref", "wife_xref"]

INDIV_REST_FIELDS = (
    "gedcom_id,name,given_name,surname,gender,"
    "birth_date,birth_place,death_date,death_place,"
    "names_json,events_json,family_as_spouse_json,family_as_child_json,"
    "notes_json,citations_json,"
    "payload_hash,version_id"
)
FAM_REST_FIELDS = (
    "family_gedcom_id,husband_xref,wife_xref,"
    "children_xrefs_json,marriage_event_json,events_json,"
    "notes_json,citations_json,"
    "payload_hash,version_id"
)


def _canonical_payload_hash(rec: dict, key_fields: list[str]) -> str:
    payload = {k: rec.get(k) for k in key_fields}
    s = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _read_all_rest(sb, table: str, fields: str, page_size: int = 1000) -> list[dict]:
    """Paginate via .range() — Lesson 173. Returns all rows."""
    rows = []
    offset = 0
    while True:
        # Retry once on transient errors
        for retry in range(3):
            try:
                resp = sb.table(table).select(fields).range(offset, offset + page_size - 1).execute()
                break
            except Exception as exc:
                if retry == 2:
                    raise
                print(f"    [{table}] range {offset}-{offset+page_size-1} retry {retry+1}: {exc.__class__.__name__}")
                time.sleep(2)
        page = resp.data or []
        rows.extend(page)
        if len(page) < page_size:
            break
        offset += page_size
        if offset % 10000 == 0:
            print(f"    [{table}] read {offset:,} rows...")
    return rows


def _get_version_map_rest(sb) -> dict:
    resp = sb.table("gedcom_versions").select("id,version_number").execute()
    return {str(r["id"]): int(r["version_number"]) for r in (resp.data or [])}


def aggregate(rows: list[dict], key_fields: list[str], version_map: dict) -> tuple[dict, int, int]:
    """Aggregate rows by payload_hash, returning (agg, fallback_hash_count, null_version_count)."""
    aggregated: dict[str, dict] = {}
    fallback_hash_count = 0
    null_version_count = 0
    for r in rows:
        phash = r.get("payload_hash")
        if not phash:
            phash = _canonical_payload_hash(r, key_fields)
            fallback_hash_count += 1
        v_uuid = str(r.get("version_id")) if r.get("version_id") else None
        v_num = version_map.get(v_uuid)
        if v_num is None:
            v_num = 0
            null_version_count += 1
        existing = aggregated.get(phash)
        if existing is None:
            aggregated[phash] = {**r, "payload_hash": phash, "first_seen_version": v_num, "last_seen_version": v_num}
        else:
            if v_num < existing["first_seen_version"]:
                existing["first_seen_version"] = v_num
            if v_num > existing["last_seen_version"]:
                existing["last_seen_version"] = v_num
    return aggregated, fallback_hash_count, null_version_count


def _bulk_upsert_psycopg2(table: str, rows: list[dict], schema_cols: list[str]) -> dict:
    """Use psycopg2 for the single bulk INSERT (REST upsert too slow for 60K rows).

    schema_cols: ordered list of columns to insert. Each row dict must have these keys.
    """
    import psycopg2
    import psycopg2.extras

    pw = os.environ["SUPABASE_DB_PASSWORD"]
    conn = psycopg2.connect(
        host="aws-0-us-west-2.pooler.supabase.com",
        port=6543,
        user="postgres.fvynibivlphxwfowzkjl",
        password=pw,
        database="postgres",
        connect_timeout=30,
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=5,
    )
    try:
        col_list = ", ".join(schema_cols)
        sql = f"""
            INSERT INTO {table} ({col_list}) VALUES %s
            ON CONFLICT (payload_hash) DO UPDATE SET
                first_seen_version = LEAST({table}.first_seen_version, EXCLUDED.first_seen_version),
                last_seen_version = GREATEST({table}.last_seen_version, EXCLUDED.last_seen_version)
        """
        # Convert each row dict to ordered tuple, JSON-encoding list/dict columns
        tuples = []
        for r in rows:
            t = []
            for c in schema_cols:
                v = r.get(c)
                if isinstance(v, (list, dict)):
                    t.append(json.dumps(v))
                else:
                    t.append(v)
            tuples.append(tuple(t))

        cur = conn.cursor()
        t0 = time.time()
        psycopg2.extras.execute_values(cur, sql, tuples, page_size=500)
        conn.commit()
        elapsed = time.time() - t0

        cur.execute(f"SELECT COUNT(*) FROM {table}")
        v2_count = cur.fetchone()[0]
        cur.execute(f"SELECT pg_size_pretty(pg_total_relation_size('{table}'))")
        size = cur.fetchone()[0]
        cur.close()
        return {"v2_count": v2_count, "size": size, "upsert_seconds": round(elapsed, 2)}
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    dry_run = not args.execute

    print(f"Session 158 Phase 158-2 — Historical backfill via REST (Mode: {'DRY-RUN' if dry_run else 'EXECUTE'})")
    print(f"  Time: {dt.datetime.utcnow().isoformat()}Z")

    sb = get_supabase_client()
    if not sb:
        sys.exit("ERROR: Supabase client unavailable")

    version_map = _get_version_map_rest(sb)
    print(f"  version_map: {len(version_map)} versions")

    summary = {}

    # Individuals
    print("\n=== Reading gedcom_individuals (ALL rows via REST) ===")
    t0 = time.time()
    indiv_rows = _read_all_rest(sb, "gedcom_individuals", INDIV_REST_FIELDS)
    print(f"  v1 rows scanned: {len(indiv_rows):,} in {time.time()-t0:.1f}s")

    indiv_agg, fb, nv = aggregate(indiv_rows, INDIVIDUAL_KEY_FIELDS, version_map)
    print(f"  unique payload_hashes: {len(indiv_agg):,}")
    print(f"  fallback hashes: {fb:,}, null version: {nv:,}")

    # Pre-count vs existing v2
    existing_resp = _read_all_rest(sb, "gedcom_individuals_v2", "payload_hash")
    existing_hashes = {r["payload_hash"] for r in existing_resp}
    new_inserts = sum(1 for h in indiv_agg if h not in existing_hashes)
    will_update = sum(1 for h in indiv_agg if h in existing_hashes)
    print(f"  NEW: {new_inserts:,}  UPDATE: {will_update:,}  estimate v2: {len(existing_hashes) + new_inserts:,}")

    summary["individuals"] = {
        "v1_scanned": len(indiv_rows),
        "unique_payload_hashes": len(indiv_agg),
        "fallback_hashes": fb,
        "null_version_rows": nv,
        "new_inserts": new_inserts,
        "will_update": will_update,
    }

    if not dry_run:
        # Add community_id to each row
        for d in indiv_agg.values():
            d["community_id"] = "rhodesli"
        cols = [
            "gedcom_id", "name", "given_name", "surname", "gender",
            "birth_date", "birth_place", "death_date", "death_place",
            "names_json", "events_json", "family_as_spouse_json", "family_as_child_json",
            "notes_json", "citations_json",
            "payload_hash", "first_seen_version", "last_seen_version", "community_id",
        ]
        # Coerce missing JSON to []
        for d in indiv_agg.values():
            for k in ["names_json", "events_json", "family_as_spouse_json", "family_as_child_json", "notes_json", "citations_json"]:
                if d.get(k) is None:
                    d[k] = []
        print("  upserting individuals via psycopg2 (single bulk INSERT)...")
        result = _bulk_upsert_psycopg2("gedcom_individuals_v2", list(indiv_agg.values()), cols)
        print(f"  done: v2 count={result['v2_count']:,}, size={result['size']}, time={result['upsert_seconds']}s")
        summary["individuals"].update(result)

    # Families
    print("\n=== Reading gedcom_families (ALL rows via REST) ===")
    t0 = time.time()
    fam_rows = _read_all_rest(sb, "gedcom_families", FAM_REST_FIELDS)
    print(f"  v1 rows scanned: {len(fam_rows):,} in {time.time()-t0:.1f}s")

    fam_agg, fb, nv = aggregate(fam_rows, FAMILY_KEY_FIELDS, version_map)
    print(f"  unique payload_hashes: {len(fam_agg):,}")

    existing_fam = _read_all_rest(sb, "gedcom_families_v2", "payload_hash")
    existing_fam_hashes = {r["payload_hash"] for r in existing_fam}
    new_fam = sum(1 for h in fam_agg if h not in existing_fam_hashes)
    upd_fam = sum(1 for h in fam_agg if h in existing_fam_hashes)
    print(f"  NEW: {new_fam:,}  UPDATE: {upd_fam:,}  estimate v2: {len(existing_fam_hashes) + new_fam:,}")

    summary["families"] = {
        "v1_scanned": len(fam_rows),
        "unique_payload_hashes": len(fam_agg),
        "fallback_hashes": fb,
        "null_version_rows": nv,
        "new_inserts": new_fam,
        "will_update": upd_fam,
    }

    if not dry_run:
        for d in fam_agg.values():
            d["community_id"] = "rhodesli"
            for k in ["children_xrefs_json", "events_json", "notes_json", "citations_json"]:
                if d.get(k) is None:
                    d[k] = []
            if d.get("marriage_event_json") is None:
                d["marriage_event_json"] = {}
        cols = [
            "family_gedcom_id", "husband_xref", "wife_xref",
            "children_xrefs_json", "marriage_event_json", "events_json",
            "notes_json", "citations_json",
            "payload_hash", "first_seen_version", "last_seen_version", "community_id",
        ]
        print("  upserting families via psycopg2 (single bulk INSERT)...")
        result = _bulk_upsert_psycopg2("gedcom_families_v2", list(fam_agg.values()), cols)
        print(f"  done: v2 count={result['v2_count']:,}, size={result['size']}, time={result['upsert_seconds']}s")
        summary["families"].update(result)

    # Report
    report_path = PROJECT_ROOT / "docs" / "feedback" / "session-158-historical-backfill-rest-report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        f"# Session 158 Phase 158-2 — Historical Backfill (REST) Report\n\n"
        f"**Date**: {dt.datetime.utcnow().isoformat()}Z\n"
        f"**Mode**: {'DRY-RUN' if dry_run else 'EXECUTE'}\n\n"
        f"## Individuals\n\n```json\n{json.dumps(summary['individuals'], indent=2)}\n```\n\n"
        f"## Families\n\n```json\n{json.dumps(summary['families'], indent=2)}\n```\n"
    )
    print(f"\nReport: {report_path}")

    print("\n=== SUMMARY ===")
    for k, v in summary.items():
        if dry_run:
            print(f"  {k}: NEW={v['new_inserts']:,}, UPDATE={v['will_update']:,}")
        else:
            print(f"  {k}: NEW={v['new_inserts']:,}, UPDATE={v['will_update']:,}, v2_count={v.get('v2_count'):,}")


if __name__ == "__main__":
    main()
