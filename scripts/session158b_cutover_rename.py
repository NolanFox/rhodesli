#!/usr/bin/env python3
"""
Session 158b Phase 158-4.2 — Reversible cutover via RENAME.

RENAMEs v1 GEDCOM tables to _dropped_*_session158 prefix. Reversible — to
roll back, rerun with --rollback. Tables stay on disk; storage doesn't drop
until Phase 158-6 (DROP + VACUUM FULL).

Also drops the legacy `current_gedcom_individuals` view (sourced from v1's
is_current=TRUE rows). Must be dropped BEFORE the rename so the rename
doesn't break dependent objects.

Usage:
    python scripts/session158b_cutover_rename.py --dry-run     # default
    python scripts/session158b_cutover_rename.py --execute
    python scripts/session158b_cutover_rename.py --rollback    # reverse the rename
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
# 158c port change: 6543 (transaction-mode) is dead from 158b through 158c.
# Session-mode 5432 verified 5/5 PASS on 2026-05-09 22:50 UTC. AD-245.
POOLER_PORT = 5432


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
        connect_timeout=60,  # 158c bumped 30→60 to absorb cold-start latency (25s observed)
    )


RENAME_PAIRS = [
    ("gedcom_individuals", "_dropped_gedcom_individuals_session158"),
    ("gedcom_families", "_dropped_gedcom_families_session158"),
    ("gedcom_change_log", "_dropped_gedcom_change_log_session158"),
]


def cutover_forward(conn) -> None:
    cur = conn.cursor()
    # 158d (Codex 158c P1 form): production app holds AccessShareLock on
    # gedcom_individuals via TTL cache refresh queries (every ~120s). Default
    # statement_timeout (2min) was too tight for RENAME's required
    # AccessExclusiveLock to acquire (158c observed timeout). Two-step fix:
    #   1. lock_timeout=30s — fail FAST if lock is held; retry the script.
    #   2. statement_timeout=0 — once we have the lock, RENAME is metadata-only
    #      and instantaneous; allow unlimited time inside the transaction.
    # SET LOCAL scopes the override to this transaction only (auto-revert on
    # COMMIT/ROLLBACK — cleaner for connection pooling).
    cur.execute("BEGIN")
    cur.execute("SET LOCAL lock_timeout = '30s'")
    cur.execute("SET LOCAL statement_timeout = '0'")
    cur.execute("DROP VIEW IF EXISTS current_gedcom_individuals")
    for src, dst in RENAME_PAIRS:
        cur.execute(f"ALTER TABLE {src} RENAME TO {dst}")
    cur.execute("COMMIT")
    cur.close()


def cutover_rollback(conn) -> None:
    cur = conn.cursor()
    # 158d: same lock_timeout/statement_timeout treatment as cutover_forward.
    # Rollback also takes AccessExclusiveLock and faces the same contention.
    cur.execute("BEGIN")
    cur.execute("SET LOCAL lock_timeout = '30s'")
    cur.execute("SET LOCAL statement_timeout = '0'")
    for src, dst in RENAME_PAIRS:
        # Reverse: rename _dropped_* back to original
        cur.execute(f"ALTER TABLE {dst} RENAME TO {src}")
    # Recreate current_gedcom_individuals view (matches pre-cutover form)
    cur.execute(
        """
        CREATE OR REPLACE VIEW current_gedcom_individuals AS
        SELECT * FROM gedcom_individuals WHERE is_current = TRUE
        """
    )
    cur.execute("COMMIT")
    cur.close()


def verify_state(conn, expected_renamed: bool) -> dict:
    """Return current state of the relevant tables."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND (table_name LIKE 'gedcom_%' OR table_name LIKE '_dropped_gedcom_%')
        ORDER BY table_name
        """
    )
    tables = [r[0] for r in cur.fetchall()]
    cur.close()
    return {
        "tables": tables,
        "v1_alive": [t for t in ["gedcom_individuals", "gedcom_families", "gedcom_change_log"] if t in tables],
        "renamed_alive": [t for t in [d for _, d in RENAME_PAIRS] if t in tables],
        "v2_alive": [t for t in ["gedcom_individuals_v2", "gedcom_families_v2", "gedcom_change_manifest"] if t in tables],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--rollback", action="store_true")
    args = parser.parse_args()
    dry_run = not (args.execute or args.rollback)

    print(f"Session 158b Phase 158-4.2 — Cutover RENAME (Mode: {'DRY-RUN' if dry_run else ('ROLLBACK' if args.rollback else 'EXECUTE')})")
    print(f"  Time: {dt.datetime.utcnow().isoformat()}Z")

    conn = get_conn()
    try:
        before = verify_state(conn, expected_renamed=False)
        print(f"\nBefore state:")
        print(f"  v1 alive: {before['v1_alive']}")
        print(f"  _dropped_*_session158 alive: {before['renamed_alive']}")
        print(f"  v2 alive: {before['v2_alive']}")

        if dry_run:
            print("\nWould execute (forward):")
            print("  DROP VIEW IF EXISTS current_gedcom_individuals;")
            for src, dst in RENAME_PAIRS:
                print(f"  ALTER TABLE {src} RENAME TO {dst};")
            print("\nNo changes made.")
            return

        if args.rollback:
            # 158c P1-2 fix: assert ALL 3 _dropped_*_session158 tables exist before rollback.
            # Partial rollback would leave orphaned dual-state (some renamed, some not).
            if len(before["renamed_alive"]) != 3:
                sys.exit(
                    f"ERROR: rollback requires all 3 _dropped_*_session158 tables present. "
                    f"Found: {before['renamed_alive']}. Manual investigation required."
                )
            if before["v1_alive"]:
                sys.exit(
                    f"ERROR: v1 tables {before['v1_alive']} are alive — rollback would conflict. "
                    f"Manual investigation required."
                )
            cutover_rollback(conn)
            print("\nROLLBACK complete.")
        else:
            # 158c P1-1 fix: assert ALL 3 v1 originals AND all 3 v2 alive before forward cutover.
            # Forward cutover requires complete v1 set (3 tables to rename) AND complete v2 set
            # (3 tables to read from after rename). Partial state is unsafe.
            if len(before["v1_alive"]) != 3:
                sys.exit(
                    f"ERROR: forward cutover requires all 3 v1 GEDCOM tables. "
                    f"Found: {before['v1_alive']}. Expected: gedcom_individuals, gedcom_families, gedcom_change_log."
                )
            if len(before["v2_alive"]) != 3:
                sys.exit(
                    f"ERROR: forward cutover requires all 3 v2 GEDCOM tables. "
                    f"Found: {before['v2_alive']}. Expected: gedcom_individuals_v2, gedcom_families_v2, gedcom_change_manifest."
                )
            if before["renamed_alive"]:
                sys.exit(f"ERROR: _dropped_*_session158 already exist: {before['renamed_alive']}. Investigate before re-running.")
            cutover_forward(conn)
            print("\nFORWARD cutover complete.")

        after = verify_state(conn, expected_renamed=True)
        print(f"\nAfter state:")
        print(f"  v1 alive: {after['v1_alive']}")
        print(f"  _dropped_*_session158 alive: {after['renamed_alive']}")
        print(f"  v2 alive: {after['v2_alive']}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
