#!/usr/bin/env python3
"""
Session 156 — Track B4: Apply the v2 schema migration via Supabase pooler.

Reads scripts/migrations/gedcom_v2_schema.sql and applies via psycopg2 +
us-west-2 pooler (Lesson 175 — direct db.<project>.supabase.co is IPv6-only).

Safety: per Track B prompt, if any v2 table already exists with rows: STOP
and surface to the orchestrator. We do NOT silently overwrite.

Usage:
    python scripts/session156_apply_gedcom_v2_schema.py --dry-run
    python scripts/session156_apply_gedcom_v2_schema.py --execute
"""

from __future__ import annotations

import argparse
import os
import sys
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

MIGRATION_PATH = PROJECT_ROOT / "scripts" / "migrations" / "gedcom_v2_schema.sql"

V2_TABLES = ["gedcom_individuals_v2", "gedcom_families_v2", "gedcom_change_manifest"]


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


def table_exists_with_rows(conn, table: str) -> tuple[bool, int]:
    """Returns (exists, row_count). row_count is -1 if table doesn't exist."""
    cur = conn.cursor()
    cur.execute("SELECT to_regclass(%s)", (f"public.{table}",))
    if cur.fetchone()[0] is None:
        cur.close()
        return False, -1
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    n = cur.fetchone()[0]
    cur.close()
    return True, n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()
    if not args.dry_run and not args.execute:
        ap.error("Pass --dry-run or --execute")

    if not MIGRATION_PATH.exists():
        sys.exit(f"ERROR: migration file not found at {MIGRATION_PATH}")

    sql = MIGRATION_PATH.read_text()
    print(f"Migration file: {MIGRATION_PATH}")
    print(f"  size: {len(sql)} chars, {sql.count(chr(10))} lines")
    print()

    conn = get_conn()
    conn.autocommit = True
    print(f"Connected to {POOLER_HOST}:{POOLER_PORT}")

    # Pre-flight: check v2 tables don't exist with rows
    for t in V2_TABLES:
        exists, n = table_exists_with_rows(conn, t)
        if exists:
            if n > 0:
                conn.close()
                sys.exit(
                    f"ABORT: {t} already exists with {n} rows. Will NOT silently "
                    f"overwrite. Drop manually if this is from a prior failed run "
                    f"and you have verified no data loss."
                )
            print(f"  {t}: EXISTS (empty) — IF NOT EXISTS will be a no-op")
        else:
            print(f"  {t}: does not exist — will be created")
    print()

    if args.dry_run:
        print("DRY-RUN: not applying migration. Pass --execute to run.")
        conn.close()
        return

    print("Applying migration...")
    cur = conn.cursor()
    cur.execute(sql)
    cur.close()
    print("  migration applied (autocommit)")
    print()

    # Verify
    print("Verification:")
    for t in V2_TABLES:
        exists, n = table_exists_with_rows(conn, t)
        status = "EXISTS" if exists else "MISSING"
        print(f"  {t}: {status} (rows={n})")

    # Verify the unique index on payload_hash
    cur = conn.cursor()
    cur.execute(
        """
        SELECT indexname FROM pg_indexes
        WHERE schemaname = 'public'
          AND tablename = 'gedcom_individuals_v2'
          AND indexname = 'uq_gedcom_individuals_v2_payload_hash'
        """
    )
    row = cur.fetchone()
    print(
        f"  uq_gedcom_individuals_v2_payload_hash: {'EXISTS' if row else 'MISSING'}"
    )
    cur.close()

    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
