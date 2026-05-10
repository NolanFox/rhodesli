#!/usr/bin/env python3
"""
Session 158c Phase 158c-4.1 — Apply current_gedcom_*_v2 views.

Reads scripts/migrations/session158b_current_v2_views.sql and applies it via
the SESSION-MODE pooler (port 5432) — transaction-mode (6543) is dead since 158.
See AD-246.

Idempotent (CREATE OR REPLACE VIEW). Sanity check after creation: row count of
each view MUST equal COUNT(DISTINCT gedcom_id) / COUNT(DISTINCT family_gedcom_id)
in the underlying table.

Usage:
    python scripts/session158c_apply_v2_views.py --dry-run    # default — print sql, exit
    python scripts/session158c_apply_v2_views.py --execute
"""
from __future__ import annotations

import argparse
import datetime as dt
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
POOLER_PORT = 5432  # AD-246: session-mode (6543 dead since 158)
SQL_FILE = PROJECT_ROOT / "scripts" / "migrations" / "session158b_current_v2_views.sql"


def get_conn():
    import psycopg2
    pw = os.environ.get("SUPABASE_DB_PASSWORD")
    if not pw:
        sys.exit("ERROR: SUPABASE_DB_PASSWORD not set")
    url = os.environ["SUPABASE_URL"]
    project_ref = url.replace("https://", "").split(".")[0]
    return psycopg2.connect(
        host=POOLER_HOST,
        port=POOLER_PORT,
        user=f"postgres.{project_ref}",
        password=pw,
        database="postgres",
        connect_timeout=60,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    dry_run = not args.execute

    print(f"Session 158c Phase 158c-4.1 — Apply v2 views (Mode: {'DRY-RUN' if dry_run else 'EXECUTE'})")
    print(f"  Time: {dt.datetime.utcnow().isoformat()}Z")
    print(f"  SQL file: {SQL_FILE}")

    if not SQL_FILE.exists():
        sys.exit(f"ERROR: SQL file not found: {SQL_FILE}")

    sql = SQL_FILE.read_text()
    print(f"  SQL size: {len(sql):,} chars, {sql.count(chr(10))+1} lines")

    if dry_run:
        print("\n--- SQL to apply ---")
        print(sql)
        print("--- (dry-run, no execution) ---")
        return

    conn = get_conn()
    try:
        cur = conn.cursor()
        print("\n=== Applying views ===")
        cur.execute(sql)
        conn.commit()
        print("  Views applied (CREATE OR REPLACE).")

        print("\n=== Sanity checks ===")
        cur.execute("SELECT COUNT(*) FROM current_gedcom_individuals_v2")
        view_indiv = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT gedcom_id) FROM gedcom_individuals_v2")
        distinct_indiv = cur.fetchone()[0]
        print(f"  current_gedcom_individuals_v2 rows: {view_indiv:,}")
        print(f"  distinct gedcom_id in v2 individuals: {distinct_indiv:,}")
        if view_indiv != distinct_indiv:
            sys.exit(
                f"FAIL: view rows ({view_indiv:,}) != distinct gedcom_id ({distinct_indiv:,}). "
                f"Tiebreaker not deterministic — investigate."
            )
        print(f"  [OK] individuals view passes 1:1 distinct check")

        cur.execute("SELECT COUNT(*) FROM current_gedcom_families_v2")
        view_fam = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT family_gedcom_id) FROM gedcom_families_v2")
        distinct_fam = cur.fetchone()[0]
        print(f"  current_gedcom_families_v2 rows: {view_fam:,}")
        print(f"  distinct family_gedcom_id in v2 families: {distinct_fam:,}")
        if view_fam != distinct_fam:
            sys.exit(
                f"FAIL: view rows ({view_fam:,}) != distinct family_gedcom_id ({distinct_fam:,}). "
                f"Tiebreaker not deterministic — investigate."
            )
        print(f"  [OK] families view passes 1:1 distinct check")

        cur.close()
    finally:
        conn.close()
    print("\nDONE — both views created and validated.")


if __name__ == "__main__":
    main()
