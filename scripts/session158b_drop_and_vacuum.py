#!/usr/bin/env python3
"""
Session 158b Phase 158-6 — DROP renamed v1 GEDCOM tables + VACUUM FULL.

IRREVERSIBLE except via R2 archive (1h restore) or local pg_dump (30min).
Only run after ALL pre-DROP gates have passed and user has authorized via
AskUserQuestion in the orchestrator.

This script:
  1. Captures pre-DROP DB size for the report
  2. DROP TABLE for the three renamed _dropped_*_session158 tables
  3. VACUUM FULL on v2 tables (and v1 events/relationships/records which
     remain alive because they're independent of the cutover)
  4. Captures post-VACUUM DB size
  5. Writes report to docs/feedback/session-158b-drop-vacuum-report.md

VACUUM FULL takes an AccessExclusiveLock and rewrites the relation. Brief
downtime per-table expected. Per Postgres docs: VACUUM FULL on a 22K-row
table is fast (<10s). The bulk of the time will be on `gedcom_records` if
it has churned heavily.

Usage:
    python scripts/session158b_drop_and_vacuum.py --dry-run    # default
    python scripts/session158b_drop_and_vacuum.py --execute
"""

from __future__ import annotations

import argparse
import datetime as dt
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

POOLER_HOST = "aws-0-us-west-2.pooler.supabase.com"
# 158c port change: 6543 (transaction-mode) is dead from 158b through 158c.
# Session-mode 5432 verified 5/5 PASS on 2026-05-09 22:50 UTC. AD-245.
POOLER_PORT = 5432

DROP_TABLES = [
    "_dropped_gedcom_individuals_session158",
    "_dropped_gedcom_families_session158",
    "_dropped_gedcom_change_log_session158",
]
V1_ORIGINAL_TABLES = [
    "gedcom_individuals",
    "gedcom_families",
    "gedcom_change_log",
]

VACUUM_TABLES = [
    # v2 tables (will benefit from VACUUM FULL after the heavy upsert in 158b-2)
    "gedcom_individuals_v2",
    "gedcom_families_v2",
    "gedcom_change_manifest",
    # v1 tables that stayed alive — VACUUM FULL them while we hold a write window
    "gedcom_records",
    "gedcom_events",
    "gedcom_relationships",
    "gedcom_versions",
]


def get_conn(autocommit: bool = False):
    import psycopg2
    pw = os.environ.get("SUPABASE_DB_PASSWORD")
    if not pw:
        sys.exit("ERROR: SUPABASE_DB_PASSWORD not set")
    url = os.environ["SUPABASE_URL"]
    project_ref = url.replace("https://", "").split(".")[0]
    conn = psycopg2.connect(
        host=POOLER_HOST,
        port=POOLER_PORT,
        user=f"postgres.{project_ref}",
        password=pw,
        database="postgres",
        connect_timeout=60,  # 158c bumped 30→60 to absorb session-mode cold-start latency
    )
    if autocommit:
        conn.autocommit = True
    return conn


def pooler_health_probe() -> bool:
    """158c P1-3: probe pooler before any IRREVERSIBLE work. Returns True if healthy.

    Runs 3 trials. ALL must succeed (this is the gate before DROP, so we want zero tolerance).
    """
    import psycopg2
    pw = os.environ.get("SUPABASE_DB_PASSWORD")
    if not pw:
        return False
    url = os.environ["SUPABASE_URL"]
    project_ref = url.replace("https://", "").split(".")[0]
    print("\n=== Pre-DROP pooler health probe (3 trials) ===")
    for trial in range(3):
        t0 = time.time()
        try:
            c = psycopg2.connect(
                host=POOLER_HOST, port=POOLER_PORT,
                user=f"postgres.{project_ref}", password=pw,
                database="postgres", connect_timeout=60,
            )
            cur = c.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
            cur.close()
            c.close()
            ms = (time.time() - t0) * 1000
            print(f"  Trial {trial+1}: PASS in {ms:.0f}ms")
        except Exception as exc:
            print(f"  Trial {trial+1}: FAIL — {exc.__class__.__name__}: {exc}")
            return False
    return True


def assert_drop_gate_safe(conn) -> None:
    """158c P0-3: all-or-nothing gate. ALL 3 _dropped_*_session158 must exist
    AND ALL 3 v1 originals must NOT exist. Otherwise abort.

    This prevents a partial DROP that would silently skip missing tables (the prior
    behavior just printed `[skip]` and moved on, which would not preserve the
    irreversibility/atomicity contract).
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT tablename FROM pg_tables WHERE schemaname = 'public'
          AND (tablename = ANY(%s) OR tablename = ANY(%s))
        """,
        (DROP_TABLES, V1_ORIGINAL_TABLES),
    )
    found = {r[0] for r in cur.fetchall()}
    cur.close()

    missing_renamed = [t for t in DROP_TABLES if t not in found]
    surviving_v1 = [t for t in V1_ORIGINAL_TABLES if t in found]

    if missing_renamed:
        sys.exit(
            f"ERROR: pre-DROP gate failed — these renamed tables are MISSING: {missing_renamed}. "
            f"Cutover RENAME (Phase 158-4.2) must run first."
        )
    if surviving_v1:
        sys.exit(
            f"ERROR: pre-DROP gate failed — these v1 originals are ALIVE: {surviving_v1}. "
            f"Cutover RENAME must complete cleanly before DROP. Was the rename rolled back?"
        )
    print(f"  pre-DROP gate PASS — all 3 renamed tables present, all 3 v1 originals absent")


def db_size(conn) -> dict:
    cur = conn.cursor()
    cur.execute("SELECT pg_size_pretty(pg_database_size('postgres')), pg_database_size('postgres')")
    pretty, raw_bytes = cur.fetchone()
    cur.execute(
        """
        SELECT relname, pg_size_pretty(pg_total_relation_size(c.oid)) AS size,
               pg_total_relation_size(c.oid) AS raw_bytes
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
        ORDER BY pg_total_relation_size(c.oid) DESC
        LIMIT 25
        """
    )
    tables = [{"name": r[0], "size": r[1], "raw_bytes": r[2]} for r in cur.fetchall()]
    cur.close()
    return {"db_size_pretty": pretty, "db_size_bytes": raw_bytes, "top_25_tables": tables}


def drop_renamed_tables(conn) -> None:
    """DROP all 3 _dropped_*_session158 tables.

    158c P0-3: pre-flight gate (assert_drop_gate_safe) MUST be called by caller
    before this. The legacy [skip] branch was removed — if a table is missing
    here, something has gone wrong and we should NOT DROP only the others.
    """
    cur = conn.cursor()
    cur.execute("BEGIN")
    for tbl in DROP_TABLES:
        # Defensive double-check (gate already passed — this is belt-and-suspenders)
        cur.execute("SELECT EXISTS (SELECT 1 FROM pg_tables WHERE tablename = %s)", (tbl,))
        exists = cur.fetchone()[0]
        if not exists:
            cur.execute("ROLLBACK")
            cur.close()
            sys.exit(
                f"ERROR: {tbl} disappeared between gate check and DROP — concurrent DDL? "
                f"Aborting transaction; no tables dropped."
            )
        print(f"  DROP TABLE {tbl}")
        cur.execute(f"DROP TABLE {tbl}")
    cur.execute("COMMIT")
    cur.close()


def vacuum_full(conn, tables: list[str]) -> dict:
    """VACUUM FULL each table; capture timing per table."""
    timings = {}
    cur = conn.cursor()
    for tbl in tables:
        cur.execute("SELECT EXISTS (SELECT 1 FROM pg_tables WHERE tablename = %s)", (tbl,))
        if not cur.fetchone()[0]:
            timings[tbl] = {"status": "skipped — does not exist"}
            print(f"  [skip] {tbl} does not exist")
            continue
        t0 = time.time()
        try:
            cur.execute(f"VACUUM FULL {tbl}")
            elapsed = time.time() - t0
            timings[tbl] = {"status": "ok", "elapsed_s": round(elapsed, 1)}
            print(f"  VACUUM FULL {tbl}: {elapsed:.1f}s")
        except Exception as exc:
            timings[tbl] = {"status": f"ERROR: {exc}", "elapsed_s": round(time.time() - t0, 1)}
            print(f"  VACUUM FULL {tbl} FAILED: {exc}")
    cur.close()
    return timings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    dry_run = not args.execute

    print(f"Session 158b Phase 158-6 — DROP + VACUUM FULL (Mode: {'DRY-RUN' if dry_run else 'EXECUTE'})")
    print(f"  Time: {dt.datetime.utcnow().isoformat()}Z")

    if dry_run:
        print("\nWould DROP:")
        for t in DROP_TABLES:
            print(f"  DROP TABLE {t};")
        print("\nWould VACUUM FULL:")
        for t in VACUUM_TABLES:
            print(f"  VACUUM FULL {t};")
        return

    # 158c P1-3: pre-DROP pooler health probe. If pooler is degraded, halt before
    # the IRREVERSIBLE step. (P1-1/P1-2 are on cutover_rename.py.)
    if not pooler_health_probe():
        sys.exit("ERROR: pooler health probe failed before DROP. Aborting irreversible step.")

    conn = get_conn()
    try:
        # 158c P0-3: gate check before DROP — must have all 3 renamed AND no v1 alive
        print(f"\n=== Pre-DROP gate ===")
        assert_drop_gate_safe(conn)

        pre = db_size(conn)
        print(f"\nPRE: db_size = {pre['db_size_pretty']} ({pre['db_size_bytes']:,} bytes)")
        print(f"\n=== DROP step ===")
        drop_renamed_tables(conn)
    finally:
        conn.close()

    # VACUUM FULL needs autocommit (cannot run in a transaction block)
    conn2 = get_conn(autocommit=True)
    try:
        print(f"\n=== VACUUM FULL step ===")
        timings = vacuum_full(conn2, VACUUM_TABLES)
    finally:
        conn2.close()

    conn3 = get_conn()
    try:
        post = db_size(conn3)
        print(f"\nPOST: db_size = {post['db_size_pretty']} ({post['db_size_bytes']:,} bytes)")
        delta = pre["db_size_bytes"] - post["db_size_bytes"]
        print(f"DELTA: {delta:,} bytes saved ({delta / pre['db_size_bytes']:.1%})")
    finally:
        conn3.close()

    # Report
    report_path = PROJECT_ROOT / "docs" / "feedback" / "session-158b-drop-vacuum-report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        f"# Session 158b Phase 158-6 — DROP + VACUUM FULL Report\n\n"
        f"**Date**: {dt.datetime.utcnow().isoformat()}Z\n"
        f"**Mode**: EXECUTE (irreversible)\n\n"
        f"## Pre-DROP DB size\n```\n{pre['db_size_pretty']} ({pre['db_size_bytes']:,} bytes)\n```\n\n"
        f"## Post-VACUUM DB size\n```\n{post['db_size_pretty']} ({post['db_size_bytes']:,} bytes)\n```\n\n"
        f"## Delta\n```\n{delta:,} bytes ({delta / pre['db_size_bytes']:.1%})\n```\n\n"
        f"## DROPped tables\n```\n{json.dumps(DROP_TABLES, indent=2)}\n```\n\n"
        f"## VACUUM FULL timings\n```json\n{json.dumps(timings, indent=2)}\n```\n\n"
        f"## Pre-DROP top 25 tables\n```json\n{json.dumps(pre['top_25_tables'][:25], indent=2)}\n```\n\n"
        f"## Post-VACUUM top 25 tables\n```json\n{json.dumps(post['top_25_tables'][:25], indent=2)}\n```\n"
    )
    print(f"\nReport: {report_path}")


if __name__ == "__main__":
    main()
