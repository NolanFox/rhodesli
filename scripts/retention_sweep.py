"""Retention sweep — Supabase storage steady-state guard.

Prevents recurrence of the Session 154 storage crisis (OD-013) by trimming
old rows in tables prone to unbounded growth. Mirrors the snapshot-validate-
mutate-verify pattern from `scripts/session154_supabase_prune.py`.

DEFAULT: --dry-run. Returns JSON summary of would-prune row counts; does NOT
mutate the DB.

DESTRUCTIVE: --execute requires `RETENTION_AUTH=approved-*` env var. The
tripwire prevents accidental scheduled runs. The actual user authorization is
captured in writing; enabling a scheduler (cron / Railway cron / GitHub
Action) requires a separate OD-013 amendment.

USAGE
-----
Dry-run all retention rules (safe):
    python scripts/retention_sweep.py
    python scripts/retention_sweep.py --table gemini_api_calls

Execute (gated):
    RETENTION_AUTH=approved-<auth-id> \
        python scripts/retention_sweep.py --table gemini_api_calls --execute
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Retention rules registry. Each rule:
#   - table: target Supabase table
#   - predicate: SELECT predicate identifying rows to prune
#   - description: human-readable purpose
RETENTION_RULES: dict[str, dict[str, Any]] = {
    "gemini_api_calls": {
        "table": "gemini_api_calls",
        "predicate": "created_at < NOW() - INTERVAL '90 days'",
        "description": "Drop Gemini API call records older than 90 days.",
        "ttl_days": 90,
    },
    "audit_log": {
        "table": "audit_log",
        "predicate": "created_at < NOW() - INTERVAL '365 days'",
        "description": "Drop audit_log entries older than 365 days. User may want longer — flag.",
        "ttl_days": 365,
    },
    "ml_proposals_resolved": {
        "table": "ml_proposals",
        "predicate": (
            "status IN ('REJECTED', 'ACCEPTED') "
            "AND updated_at < NOW() - INTERVAL '30 days'"
        ),
        "description": "Drop ml_proposals in REJECTED/ACCEPTED state older than 30 days. PENDING is KEEP_ALL.",
        "ttl_days": 30,
    },
    "gedcom_change_log_keep_3": {
        "table": "gedcom_change_log",
        # Per OD-013 Phase E3 spec: keep latest 3 versions per entity.
        # Drop change_log rows where the version_id is NOT in the latest 3
        # gedcom_versions rows (ordered by imported_at DESC).
        "predicate": (
            "version_id NOT IN ("
            "  SELECT id FROM gedcom_versions "
            "  ORDER BY imported_at DESC NULLS LAST "
            "  LIMIT 3"
            ")"
        ),
        "description": "Keep change_log only for the 3 most-recent gedcom_versions imports.",
        "ttl_days": None,  # version-window, not time-window
    },
}

ALL_RULE_NAMES = list(RETENTION_RULES.keys())


def load_env() -> None:
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def connect():  # pragma: no cover — exercised in integration tests, not unit
    import psycopg2
    project_ref = "fvynibivlphxwfowzkjl"
    return psycopg2.connect(
        host="aws-0-us-west-2.pooler.supabase.com",
        port=5432,
        user=f"postgres.{project_ref}",
        password=os.environ["SUPABASE_DB_PASSWORD"],
        dbname="postgres",
        connect_timeout=15,
        sslmode="require",
    )


def hash_rows(rows) -> str:
    serialized = []
    for r in sorted(rows, key=lambda x: json.dumps(x.get("id", x), sort_keys=True, default=str)):
        serialized.append(json.dumps(r, sort_keys=True, default=str))
    return hashlib.sha256("\n".join(serialized).encode()).hexdigest()


def write_snapshot(rows, table: str, predicate: str, snapshot_path: Path) -> dict:
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    sha = hash_rows(rows)
    manifest = {
        "schema_version": 1,
        "table": table,
        "predicate": predicate,
        "total_rows": len(rows),
        "sha256_of_rows": sha,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "restore_command": (
            f"# Snapshot validation only — actual restore is a separate manual step.\n"
            f"# python scripts/retention_sweep.py --validate-snapshot {snapshot_path}"
        ),
    }
    with gzip.open(snapshot_path, "wt", encoding="utf-8") as gz:
        gz.write(json.dumps(manifest) + "\n")
        for r in rows:
            gz.write(json.dumps(r, default=str) + "\n")
    return manifest


def assert_authorization() -> None:
    auth = os.environ.get("RETENTION_AUTH", "").strip()
    if not auth or not auth.startswith("approved-"):
        sys.stderr.write(
            "REFUSED: --execute requires env RETENTION_AUTH=approved-<auth-id>\n"
            "This is a tripwire — actual authorization is the OD-013 amendment\n"
            "that enables retention. NO scheduler enablement until then.\n"
        )
        sys.exit(2)


def rule_dry_run(name: str, conn) -> dict:  # pragma: no cover — DB-dependent
    rule = RETENTION_RULES[name]
    sql = f"SELECT COUNT(*) FROM {rule['table']} WHERE {rule['predicate']}"
    with conn.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchone()[0]
    return {
        "rule": name,
        "table": rule["table"],
        "predicate": rule["predicate"],
        "would_prune": rows,
        "ttl_days": rule["ttl_days"],
        "snapshot_path": (
            f"backups/retention/{rule['table']}_{name}_pre-prune-<UTC>.jsonl.gz"
        ),
    }


def rule_execute(name: str, conn, snapshot_dir: Path) -> dict:  # pragma: no cover
    rule = RETENTION_RULES[name]
    table = rule["table"]
    predicate = rule["predicate"]
    utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    snapshot_path = snapshot_dir / f"{table}_{name}_pre-prune-{utc}.jsonl.gz"

    with conn.cursor() as cur:
        cur.execute(f"SELECT row_to_json(t) FROM {table} t WHERE {predicate}")
        rows = [r[0] for r in cur.fetchall()]
    manifest = write_snapshot(rows, table, predicate, snapshot_path)

    with conn.cursor() as cur:
        cur.execute(f"DELETE FROM {table} WHERE {predicate}")
        affected = cur.rowcount
    if affected != manifest["total_rows"]:
        conn.rollback()
        raise RuntimeError(
            f"DELETE row mismatch for {name}: snapshot {manifest['total_rows']}, "
            f"DELETE {affected}. Rolled back."
        )
    conn.commit()
    return {
        "rule": name,
        "table": table,
        "snapshot": str(snapshot_path),
        "rows_deleted": affected,
    }


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--table", choices=ALL_RULE_NAMES + ["all"], default="all")
    p.add_argument("--execute", action="store_true",
                   help="Actually run the DELETE (default: dry-run)")
    p.add_argument("--snapshot-dir", default="backups/retention")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    load_env()

    rule_names = ALL_RULE_NAMES if args.table == "all" else [args.table]

    if args.execute:
        assert_authorization()
        sys.stderr.write("EXECUTE MODE: DELETEs will run. Ctrl-C now if unintended.\n")

    conn = connect()
    try:
        results = []
        for name in rule_names:
            if args.execute:
                result = rule_execute(name, conn, Path(args.snapshot_dir))
            else:
                result = rule_dry_run(name, conn)
            results.append(result)
            sys.stdout.write(json.dumps(result, indent=2) + "\n")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
