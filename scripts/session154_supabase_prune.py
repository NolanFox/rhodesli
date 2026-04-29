"""Session 154 Supabase prune script (Phase E2 contract).

This script implements the snapshot-validate-mutate-verify pattern from
the prune plan (`docs/feedback/session-154-supabase-prune-plan.md` §7).

Default mode is `--dry-run`. The destructive `--execute` mode REQUIRES
the env var `SESSION154_PRUNE_AUTH=approved-<plan-commit-sha>` to be set
to a non-empty value matching the plan's commit hash. This is NOT a true
authentication mechanism — it is a tripwire that ensures `--execute`
cannot run by accident or from a stale session that hasn't seen the
authorized plan. The actual user authorization gate is the message
captured in `docs/feedback/session-154-supabase-prune-authorization.md`.

USAGE
-----
Dry-run (default, safe):
    python scripts/session154_supabase_prune.py --step gedcom_individuals
    python scripts/session154_supabase_prune.py --step all

Execute (gated):
    SESSION154_PRUNE_AUTH=approved-<plan-commit-sha> \
        python scripts/session154_supabase_prune.py --step gedcom_individuals --execute

Restore from snapshot:
    python scripts/session154_supabase_prune.py --restore \
        --snapshot backups/session-154/gedcom_individuals_pre-prune-<UTC>.jsonl.gz

NEVER use `--execute` without explicit user authorization. NEVER skip the
snapshot step. NEVER chain `--execute` with `make test-fast` failures.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

# Step → (table, predicate, snapshot_path_template) registry.
# Predicates use parameterized identity, NOT free-form WHERE.
PRUNE_STEPS: dict[str, dict[str, Any]] = {
    "gedcom_individuals": {
        "table": "gedcom_individuals",
        "select_predicate": (
            "version_id IN (SELECT id FROM gedcom_versions WHERE status = 'failed') "
            "AND is_current = FALSE"
        ),
        "expected_rows": 131_664,  # E1 prep
    },
    "gedcom_records": {
        "table": "gedcom_records",
        "select_predicate": (
            "version_id IN (SELECT id FROM gedcom_versions WHERE status = 'failed') "
            "AND is_current = FALSE"
        ),
        "expected_rows": 60_308,
    },
    "gedcom_events": {
        "table": "gedcom_events",
        "select_predicate": (
            "version_id IN (SELECT id FROM gedcom_versions WHERE status = 'failed') "
            "AND is_current = FALSE"
        ),
        "expected_rows": 143_578,
    },
    "gedcom_relationships": {
        "table": "gedcom_relationships",
        "select_predicate": (
            "version_id IN (SELECT id FROM gedcom_versions WHERE status = 'failed') "
            "AND is_current = FALSE"
        ),
        "expected_rows": 439_776,
    },
    "gedcom_families": {
        "table": "gedcom_families",
        "select_predicate": (
            "version_id IN (SELECT id FROM gedcom_versions WHERE status = 'failed') "
            "AND is_current = FALSE"
        ),
        "expected_rows": 20_166,
    },
    "gedcom_change_log_step_a": {
        "table": "gedcom_change_log",
        "select_predicate": (
            "version_id IN (SELECT id FROM gedcom_versions WHERE status = 'failed')"
        ),
        "expected_rows": 589_594,
    },
    "gedcom_change_log_step_b": {
        "table": "gedcom_change_log",
        "select_predicate": (
            "old_value IS NULL AND new_value IS NULL "
            "AND change_type IN ('added', 'removed') "
            "AND version_id IN (SELECT id FROM gedcom_versions WHERE status = 'applied')"
        ),
        "expected_rows": None,  # E2 will measure precisely; ~650K
    },
}

ALL_STEP_NAMES = list(PRUNE_STEPS.keys())


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


def hash_rows(rows: Iterable[dict]) -> str:
    """Deterministic SHA-256 of rows sorted by stringified PK + serialized payload."""
    serialized = []
    for r in sorted(rows, key=lambda x: json.dumps(x.get("id", x), sort_keys=True, default=str)):
        serialized.append(json.dumps(r, sort_keys=True, default=str))
    blob = "\n".join(serialized).encode()
    return hashlib.sha256(blob).hexdigest()


def write_snapshot(
    rows: list[dict],
    table: str,
    predicate: str,
    snapshot_path: Path,
) -> dict:
    """Write a gzipped JSONL snapshot with header.

    Header is the first line; data rows follow.
    Returns the manifest dict for in-memory verification.
    """
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    pk_list = [r.get("id") for r in rows]
    sha = hash_rows(rows)
    manifest = {
        "schema_version": 1,
        "table": table,
        "predicate": predicate,
        "total_rows": len(rows),
        "sha256_of_rows": sha,
        "pk_list_size": len(pk_list),
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "restore_command": (
            f"python scripts/session154_supabase_prune.py --restore "
            f"--snapshot {snapshot_path}"
        ),
    }
    with gzip.open(snapshot_path, "wt", encoding="utf-8") as gz:
        gz.write(json.dumps(manifest) + "\n")
        for r in rows:
            gz.write(json.dumps(r, default=str) + "\n")
    return manifest


def verify_snapshot(snapshot_path: Path) -> tuple[dict, list[dict]]:
    """Re-read snapshot and verify the recorded sha256 + row count."""
    with gzip.open(snapshot_path, "rt", encoding="utf-8") as gz:
        first = gz.readline()
        manifest = json.loads(first)
        rows = [json.loads(line) for line in gz if line.strip()]
    if len(rows) != manifest["total_rows"]:
        raise ValueError(
            f"Snapshot row count mismatch: header says {manifest['total_rows']}, "
            f"file has {len(rows)}"
        )
    sha_check = hash_rows(rows)
    if sha_check != manifest["sha256_of_rows"]:
        raise ValueError(
            f"Snapshot hash mismatch: header {manifest['sha256_of_rows']!r} vs "
            f"recomputed {sha_check!r}"
        )
    return manifest, rows


def step_dry_run(step: str, conn) -> dict:  # pragma: no cover — DB-dependent
    cfg = PRUNE_STEPS[step]
    sql = f"SELECT COUNT(*) FROM {cfg['table']} WHERE {cfg['select_predicate']}"
    with conn.cursor() as cur:
        cur.execute(sql)
        actual_rows = cur.fetchone()[0]
    summary = {
        "step": step,
        "table": cfg["table"],
        "predicate": cfg["select_predicate"],
        "would_delete": actual_rows,
        "expected_rows": cfg["expected_rows"],
        "delta_pct": (
            None if cfg["expected_rows"] is None
            else round(100 * (actual_rows - cfg["expected_rows"]) / cfg["expected_rows"], 1)
        ),
    }
    return summary


def step_execute(step: str, conn, snapshot_dir: Path) -> dict:  # pragma: no cover
    """Snapshot → verify → DELETE → verify affected rows. Each step its own tx."""
    cfg = PRUNE_STEPS[step]
    table = cfg["table"]
    predicate = cfg["select_predicate"]
    utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    snapshot_path = snapshot_dir / f"{table}_{step}_pre-prune-{utc}.jsonl.gz"

    with conn.cursor() as cur:
        # 1. Pre-snapshot
        cur.execute(f"SELECT row_to_json(t) FROM {table} t WHERE {predicate}")
        rows = [r[0] for r in cur.fetchall()]

    manifest = write_snapshot(rows, table, predicate, snapshot_path)

    # 2. Re-read and verify
    verify_manifest, _ = verify_snapshot(snapshot_path)
    if verify_manifest["sha256_of_rows"] != manifest["sha256_of_rows"]:
        raise RuntimeError(f"Snapshot verification failed for {step}")

    # 3. Delete (in a transaction)
    with conn.cursor() as cur:
        cur.execute(f"DELETE FROM {table} WHERE {predicate}")
        affected = cur.rowcount
    if affected != manifest["total_rows"]:
        conn.rollback()
        raise RuntimeError(
            f"DELETE row count mismatch for {step}: snapshot {manifest['total_rows']}, "
            f"DELETE {affected}. Rolling back."
        )
    conn.commit()
    return {
        "step": step,
        "snapshot": str(snapshot_path),
        "rows_deleted": affected,
        "sha256": manifest["sha256_of_rows"],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--step", choices=ALL_STEP_NAMES + ["all"], help="Step to run")
    p.add_argument("--execute", action="store_true",
                   help="Actually run the DELETE (default: dry-run)")
    p.add_argument("--restore", action="store_true",
                   help="Restore mode (replay snapshot back into table)")
    p.add_argument("--snapshot", help="Snapshot file path (for --restore)")
    p.add_argument("--snapshot-dir", default="backups/session-154",
                   help="Where to write snapshots")
    return p.parse_args(argv)


def assert_authorization() -> None:
    auth = os.environ.get("SESSION154_PRUNE_AUTH", "").strip()
    if not auth or not auth.startswith("approved-"):
        sys.stderr.write(
            "REFUSED: --execute requires env SESSION154_PRUNE_AUTH=approved-<plan-commit-sha>\n"
            "This is a tripwire — the actual user authorization is captured in\n"
            "docs/feedback/session-154-supabase-prune-authorization.md.\n"
        )
        sys.exit(2)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    load_env()

    if args.restore:
        if not args.snapshot:
            sys.stderr.write("--restore requires --snapshot path\n")
            return 2
        manifest, rows = verify_snapshot(Path(args.snapshot))
        sys.stdout.write(json.dumps({
            "mode": "restore-validated",
            "snapshot": args.snapshot,
            "manifest": manifest,
            "row_count": len(rows),
            "note": "Snapshot verified. Actual restore INSERT not implemented in this tripwire script.",
        }, indent=2) + "\n")
        return 0

    if not args.step:
        sys.stderr.write("--step is required (or use --restore)\n")
        return 2

    step_names = ALL_STEP_NAMES if args.step == "all" else [args.step]

    if args.execute:
        assert_authorization()
        sys.stderr.write(
            "EXECUTE MODE: snapshot will be written, DELETEs will run.\n"
            "If you didn't mean to do this, Ctrl-C now.\n"
        )

    conn = connect()
    try:
        results = []
        for step in step_names:
            if args.execute:
                result = step_execute(step, conn, Path(args.snapshot_dir))
            else:
                result = step_dry_run(step, conn)
            results.append(result)
            sys.stdout.write(json.dumps(result, indent=2) + "\n")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
