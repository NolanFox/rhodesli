#!/usr/bin/env python3
"""
Session 158b Phase 158-2 — Historical backfill via REST chunked-write.

REPLACES: session158_historical_backfill_rest.py (which accumulated 951 MB
of rows in memory and stalled). Per Lesson 183 chunked-write template:
read+aggregate+upsert one chunk at a time; never accumulate full dataset.

Pooler is degraded (Session 158b probe: 0/3 PASS, SSL connection closed).
This script uses REST API for BOTH reads and writes — no psycopg2.

Strategy:
  Chunk by version_id. 9 versions + 1 NULL chunk = 10 chunks.
  Each chunk ~22K v1 rows. Per-chunk peak memory ~50 MB.

  For each chunk:
    1. Read rows for this version_id via REST .range() pagination
    2. Aggregate by payload_hash (this chunk only)
    3. Read existing v2 rows with matching payload_hashes
    4. Merge: first_seen_version = LEAST, last_seen_version = GREATEST
    5. REST .upsert() in batches of 500 rows
    6. Clear chunk dict

  Across chunks, the read-merge-write cycle handles cumulative
  first/last_seen_version updates correctly because each chunk reads
  the prior chunk's persisted v2 state.

Usage:
    python scripts/session158b_historical_backfill_chunked.py --dry-run
    python scripts/session158b_historical_backfill_chunked.py --execute
    python scripts/session158b_historical_backfill_chunked.py --execute --skip-individuals
    python scripts/session158b_historical_backfill_chunked.py --execute --skip-families
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
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

INDIV_V2_COLS = [
    "gedcom_id", "name", "given_name", "surname", "gender",
    "birth_date", "birth_place", "death_date", "death_place",
    "names_json", "events_json", "family_as_spouse_json", "family_as_child_json",
    "notes_json", "citations_json",
    "payload_hash", "first_seen_version", "last_seen_version", "community_id",
]
FAM_V2_COLS = [
    "family_gedcom_id", "husband_xref", "wife_xref",
    "children_xrefs_json", "marriage_event_json", "events_json",
    "notes_json", "citations_json",
    "payload_hash", "first_seen_version", "last_seen_version", "community_id",
]

INDIV_JSON_COLS = ["names_json", "events_json", "family_as_spouse_json", "family_as_child_json", "notes_json", "citations_json"]
FAM_LIST_JSON_COLS = ["children_xrefs_json", "events_json", "notes_json", "citations_json"]
FAM_DICT_JSON_COLS = ["marriage_event_json"]

UPSERT_BATCH = 500
READ_PAGE = 1000
RETRY_COUNT = 6           # 158c P0 fix: bumped from 3 (chunk 6 timeout in 158b)
RETRY_SLEEP_BASE_S = 10   # 158c P0 fix: bumped from 3, with backoff


def _canonical_payload_hash(rec: dict, key_fields: list[str]) -> str:
    payload = {k: rec.get(k) for k in key_fields}
    s = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _read_chunk_for_version(sb, table: str, fields: str, version_id: str | None) -> list[dict]:
    """Read all rows for a single version_id via REST pagination. version_id=None → IS NULL.

    158c P0-1 fix: ORDER BY id ASC ensures deterministic pagination across REST calls.
    Without this, PostgREST may return rows in unstable order across pages → silent
    skips/duplicates between offset boundaries.
    """
    rows = []
    offset = 0
    while True:
        for retry in range(RETRY_COUNT):
            try:
                q = sb.table(table).select(fields)
                if version_id is None:
                    q = q.is_("version_id", "null")
                else:
                    q = q.eq("version_id", version_id)
                # 158c P0-1: deterministic order by primary key id
                q = q.order("id", desc=False)
                resp = q.range(offset, offset + READ_PAGE - 1).execute()
                break
            except Exception as exc:
                if retry == RETRY_COUNT - 1:
                    raise
                sleep_s = RETRY_SLEEP_BASE_S * (retry + 1)  # 10s, 20s, 30s, 40s, 50s
                print(f"    [{table}] retry {retry+1}/{RETRY_COUNT}: {exc.__class__.__name__} — sleep {sleep_s}s")
                time.sleep(sleep_s)
        page = resp.data or []
        rows.extend(page)
        if len(page) < READ_PAGE:
            break
        offset += READ_PAGE
    return rows


def _aggregate_chunk(rows: list[dict], key_fields: list[str], v_num: int) -> tuple[dict, int]:
    """Aggregate rows by payload_hash. All rows in this chunk get first/last_seen=v_num.

    158c P0-2 fix: payload_hash is REQUIRED. v1 has 100% payload_hash population today
    (Session 158b carry observed 0 fallback hashes across chunks 1-5). The original
    fallback hashed only key_fields, which would silently collide for two rows with
    identical key fields but different events/citations/notes. Refuse to write rather
    than risk hash collision.
    """
    aggregated: dict[str, dict] = {}
    fallback_count = 0
    for r in rows:
        phash = r.get("payload_hash")
        if not phash:
            # 158c P0-2: refuse to fall back; v1 invariant is payload_hash IS NOT NULL
            raise RuntimeError(
                f"row missing payload_hash — refusing to fallback to narrow hash. "
                f"row keys={list(r.keys())[:5]}, version=v{v_num}"
            )
        if phash in aggregated:
            continue  # within same chunk, dedup by payload_hash
        rec = {**r, "payload_hash": phash, "first_seen_version": v_num, "last_seen_version": v_num}
        rec.pop("version_id", None)
        aggregated[phash] = rec
    return aggregated, fallback_count


def _read_existing_v2(sb, table: str, payload_hashes: list[str]) -> dict:
    """Read first/last_seen_version for the given payload_hashes from v2."""
    existing = {}
    for i in range(0, len(payload_hashes), 100):  # in_() supports many but keep URL short
        batch = payload_hashes[i:i+100]
        for retry in range(RETRY_COUNT):
            try:
                resp = sb.table(table).select("payload_hash,first_seen_version,last_seen_version").in_("payload_hash", batch).execute()
                break
            except Exception as exc:
                if retry == RETRY_COUNT - 1:
                    raise
                sleep_s = RETRY_SLEEP_BASE_S * (retry + 1)
                print(f"      [v2 read] retry {retry+1}/{RETRY_COUNT}: {exc.__class__.__name__} — sleep {sleep_s}s")
                time.sleep(sleep_s)
        for r in resp.data or []:
            existing[r["payload_hash"]] = (r["first_seen_version"], r["last_seen_version"])
    return existing


def _coerce_json_columns(rec: dict, list_cols: list[str], dict_cols: list[str] | None = None) -> None:
    """Ensure JSON columns have correct default types (list or dict, not None)."""
    for k in list_cols:
        if rec.get(k) is None:
            rec[k] = []
    if dict_cols:
        for k in dict_cols:
            if rec.get(k) is None:
                rec[k] = {}


def _upsert_v2(sb, table: str, rows: list[dict]) -> None:
    """REST upsert with on_conflict=payload_hash. Batched for stability."""
    for i in range(0, len(rows), UPSERT_BATCH):
        batch = rows[i:i+UPSERT_BATCH]
        for retry in range(RETRY_COUNT):
            try:
                sb.table(table).upsert(batch, on_conflict="payload_hash").execute()
                break
            except Exception as exc:
                if retry == RETRY_COUNT - 1:
                    raise
                sleep_s = RETRY_SLEEP_BASE_S * (retry + 1)
                print(f"      [{table} upsert] batch {i//UPSERT_BATCH+1} retry {retry+1}/{RETRY_COUNT}: {exc.__class__.__name__}: {exc} — sleep {sleep_s}s")
                time.sleep(sleep_s)


def _process_table(sb, dry_run: bool, table_v1: str, table_v2: str, fields: str, key_fields: list[str], v2_cols: list[str], list_json_cols: list[str], dict_json_cols: list[str] | None, version_map: dict, total_chunks: int, label: str) -> dict:
    """Process one table (individuals or families) chunk by chunk."""
    print(f"\n=== {label} — {total_chunks} chunks ===")
    summary = {
        "v1_scanned_total": 0,
        "unique_payload_hashes_total": 0,
        "fallback_hashes_total": 0,
        "new_inserts_total": 0,
        "updates_total": 0,
        "upserted_total": 0,
        "chunks": [],
    }

    chunk_id = 0
    # Sorted list: actual versions in v_num order, then None
    sorted_versions = sorted(((v_id, v_num) for v_id, v_num in version_map.items()), key=lambda x: x[1])
    for v_id, v_num in sorted_versions + [(None, 0)]:
        chunk_id += 1
        t0 = time.time()
        v_label = f"v{v_num}" if v_id else "NULL"
        print(f"\n  [chunk {chunk_id}/{total_chunks}] {v_label} (version_id={v_id}, v_num={v_num})")

        # Read
        rows = _read_chunk_for_version(sb, table_v1, fields, v_id)
        print(f"    read: {len(rows):,} v1 rows in {time.time()-t0:.1f}s")
        summary["v1_scanned_total"] += len(rows)

        # Aggregate
        agg, fb = _aggregate_chunk(rows, key_fields, v_num)
        del rows  # release memory
        print(f"    aggregated: {len(agg):,} unique hashes, {fb:,} fallback hashes")
        summary["unique_payload_hashes_total"] += len(agg)
        summary["fallback_hashes_total"] += fb

        # Read existing v2 first/last_seen for these hashes
        existing = _read_existing_v2(sb, table_v2, list(agg.keys()))
        print(f"    existing v2 hits: {len(existing):,}")

        # Merge first/last_seen
        new_count = 0
        upd_count = 0
        for phash, rec in agg.items():
            if phash in existing:
                old_first, old_last = existing[phash]
                rec["first_seen_version"] = min(old_first, rec["first_seen_version"])
                rec["last_seen_version"] = max(old_last, rec["last_seen_version"])
                upd_count += 1
            else:
                new_count += 1
            rec["community_id"] = "rhodesli"
            _coerce_json_columns(rec, list_json_cols, dict_json_cols)
        summary["new_inserts_total"] += new_count
        summary["updates_total"] += upd_count
        print(f"    merged: NEW={new_count:,}, UPDATE={upd_count:,}")

        if not dry_run:
            # Build records with only v2 columns
            records = []
            for rec in agg.values():
                row = {c: rec.get(c) for c in v2_cols}
                records.append(row)
            del agg  # release memory
            _upsert_v2(sb, table_v2, records)
            print(f"    upserted: {len(records):,} rows in {time.time()-t0:.1f}s total")
            summary["upserted_total"] += len(records)
            del records
        else:
            del agg

        summary["chunks"].append({
            "chunk_id": chunk_id, "v_label": v_label, "v_num": v_num,
            "v1_rows": summary["v1_scanned_total"],
            "new": new_count, "update": upd_count,
            "elapsed_s": round(time.time() - t0, 1),
        })

    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Actually write to v2. Default is dry-run.")
    parser.add_argument("--skip-individuals", action="store_true")
    parser.add_argument("--skip-families", action="store_true")
    args = parser.parse_args()
    dry_run = not args.execute

    print(f"Session 158b Phase 158-2 — Historical backfill (chunked-write, {'DRY-RUN' if dry_run else 'EXECUTE'})")
    print(f"  Time: {dt.datetime.utcnow().isoformat()}Z")

    sb = get_supabase_client()
    if not sb:
        sys.exit("ERROR: Supabase client unavailable")

    # Build version_map: {version_id_uuid: version_number}
    resp = sb.table("gedcom_versions").select("id,version_number").execute()
    version_map = {str(r["id"]): int(r["version_number"]) for r in (resp.data or [])}
    print(f"  version_map: {len(version_map)} versions")

    total_chunks = len(version_map) + 1  # +1 for NULL chunk

    overall = {}

    if not args.skip_individuals:
        overall["individuals"] = _process_table(
            sb, dry_run,
            "gedcom_individuals", "gedcom_individuals_v2",
            INDIV_REST_FIELDS, INDIVIDUAL_KEY_FIELDS, INDIV_V2_COLS,
            INDIV_JSON_COLS, None,
            version_map, total_chunks, "INDIVIDUALS",
        )

    if not args.skip_families:
        overall["families"] = _process_table(
            sb, dry_run,
            "gedcom_families", "gedcom_families_v2",
            FAM_REST_FIELDS, FAMILY_KEY_FIELDS, FAM_V2_COLS,
            FAM_LIST_JSON_COLS, FAM_DICT_JSON_COLS,
            version_map, total_chunks, "FAMILIES",
        )

    # Final v2 row counts
    if not dry_run:
        for table in ["gedcom_individuals_v2", "gedcom_families_v2"]:
            r = sb.table(table).select("id", count="exact").limit(1).execute()
            print(f"  POST: {table} count = {r.count:,}")

    # Report
    report_path = PROJECT_ROOT / "docs" / "feedback" / "session-158b-historical-backfill-report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    summary_text = f"# Session 158b Phase 158-2 — Historical Backfill (chunked-write) Report\n\n"
    summary_text += f"**Date**: {dt.datetime.utcnow().isoformat()}Z\n"
    summary_text += f"**Mode**: {'DRY-RUN' if dry_run else 'EXECUTE'}\n\n"
    for k, v in overall.items():
        summary_text += f"## {k}\n\n```json\n{json.dumps(v, indent=2)}\n```\n\n"
    report_path.write_text(summary_text)
    print(f"\nReport: {report_path}")

    print("\n=== SUMMARY ===")
    for k, v in overall.items():
        print(f"  {k}: v1_scanned={v['v1_scanned_total']:,}, unique_hashes={v['unique_payload_hashes_total']:,}, NEW={v['new_inserts_total']:,}, UPDATE={v['updates_total']:,}, upserted={v['upserted_total']:,}")


if __name__ == "__main__":
    main()
