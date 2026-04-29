"""Session 154 Phase E1 prep — per-version row counts for sibling tables.

READ-ONLY. Gathers data E0.5 didn't have to refine E1 prune predicates.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
import psycopg2.extras


def load_env() -> None:
    env_path = Path(__file__).parent.parent / ".env"
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def connect():
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


def run(cur, sql, name):
    stripped = sql.strip().upper()
    if not stripped.startswith(("SELECT", "WITH")):
        raise ValueError(f"Refusing non-SELECT in {name!r}")
    cur.execute(sql)
    return [dict(r) for r in cur.fetchall()]


def main() -> int:
    load_env()
    out: dict = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "queries": {},
    }

    with connect() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        # Per-version footprint for gedcom_records
        out["queries"]["records_per_version"] = run(
            cur,
            """
            SELECT version_id::text AS version_id,
                   COUNT(*) AS rows,
                   pg_size_pretty(SUM(octet_length(raw_text))::bigint) AS raw_text_total,
                   pg_size_pretty(SUM(octet_length(root_json::text))::bigint) AS root_json_total
            FROM gedcom_records
            GROUP BY version_id
            ORDER BY rows DESC;
            """,
            "records_per_version",
        )

        # Per-version footprint for gedcom_relationships
        out["queries"]["relationships_per_version"] = run(
            cur,
            """
            SELECT version_id::text AS version_id,
                   COUNT(*) AS rows,
                   pg_size_pretty(SUM(octet_length(relationship_payload::text))::bigint) AS payload_total
            FROM gedcom_relationships
            GROUP BY version_id
            ORDER BY rows DESC;
            """,
            "relationships_per_version",
        )

        # Per-version footprint for gedcom_events
        out["queries"]["events_per_version"] = run(
            cur,
            """
            SELECT version_id::text AS version_id,
                   COUNT(*) AS rows,
                   pg_size_pretty(SUM(octet_length(raw_node_json::text))::bigint) AS raw_node_total
            FROM gedcom_events
            GROUP BY version_id
            ORDER BY rows DESC;
            """,
            "events_per_version",
        )

        # Per-version footprint for gedcom_families
        out["queries"]["families_per_version"] = run(
            cur,
            """
            SELECT version_id::text AS version_id,
                   COUNT(*) AS rows,
                   pg_size_pretty(SUM(octet_length(raw_record_json::text))::bigint) AS raw_total
            FROM gedcom_families
            GROUP BY version_id
            ORDER BY rows DESC;
            """,
            "families_per_version",
        )

        # Confirmed-good rows (current+applied versions only)
        out["queries"]["safe_rows_individuals"] = run(
            cur,
            """
            SELECT COUNT(*) AS rows
            FROM gedcom_individuals gi
            JOIN gedcom_versions gv ON gv.id = gi.version_id
            WHERE gv.status = 'applied' OR gi.is_current = TRUE;
            """,
            "safe_individuals",
        )

        out["queries"]["safe_rows_records"] = run(
            cur,
            """
            SELECT COUNT(*) AS rows
            FROM gedcom_records gr
            JOIN gedcom_versions gv ON gv.id = gr.version_id
            WHERE gv.status = 'applied' OR gr.is_current = TRUE;
            """,
            "safe_records",
        )

        # Failed-version row counts (rows we can drop in E2)
        out["queries"]["failed_version_rows"] = run(
            cur,
            """
            WITH failed_versions AS (
                SELECT id FROM gedcom_versions WHERE status = 'failed'
            )
            SELECT 'gedcom_individuals' AS tbl, COUNT(*) AS rows
            FROM gedcom_individuals WHERE version_id IN (SELECT id FROM failed_versions)
            UNION ALL
            SELECT 'gedcom_records', COUNT(*) FROM gedcom_records
            WHERE version_id IN (SELECT id FROM failed_versions)
            UNION ALL
            SELECT 'gedcom_events', COUNT(*) FROM gedcom_events
            WHERE version_id IN (SELECT id FROM failed_versions)
            UNION ALL
            SELECT 'gedcom_relationships', COUNT(*) FROM gedcom_relationships
            WHERE version_id IN (SELECT id FROM failed_versions)
            UNION ALL
            SELECT 'gedcom_families', COUNT(*) FROM gedcom_families
            WHERE version_id IN (SELECT id FROM failed_versions)
            UNION ALL
            SELECT 'gedcom_change_log', COUNT(*) FROM gedcom_change_log
            WHERE version_id IN (SELECT id FROM failed_versions);
            """,
            "failed_rows",
        )

        # Identify the legacy NULL bucket — what's its current/non-current ratio
        out["queries"]["null_version_audit"] = run(
            cur,
            """
            SELECT 'gedcom_individuals' AS tbl,
                   COUNT(*) FILTER (WHERE version_id IS NULL) AS null_rows,
                   COUNT(*) FILTER (WHERE version_id IS NULL AND is_current = TRUE) AS null_current,
                   COUNT(*) FILTER (WHERE version_id IS NULL AND is_current = FALSE) AS null_legacy
            FROM gedcom_individuals
            UNION ALL
            SELECT 'gedcom_records',
                   COUNT(*) FILTER (WHERE version_id IS NULL),
                   COUNT(*) FILTER (WHERE version_id IS NULL AND is_current = TRUE),
                   COUNT(*) FILTER (WHERE version_id IS NULL AND is_current = FALSE)
            FROM gedcom_records
            UNION ALL
            SELECT 'gedcom_events',
                   COUNT(*) FILTER (WHERE version_id IS NULL),
                   COUNT(*) FILTER (WHERE version_id IS NULL AND is_current = TRUE),
                   COUNT(*) FILTER (WHERE version_id IS NULL AND is_current = FALSE)
            FROM gedcom_events
            UNION ALL
            SELECT 'gedcom_relationships',
                   COUNT(*) FILTER (WHERE version_id IS NULL),
                   COUNT(*) FILTER (WHERE version_id IS NULL AND is_current = TRUE),
                   COUNT(*) FILTER (WHERE version_id IS NULL AND is_current = FALSE)
            FROM gedcom_relationships;
            """,
            "null_version",
        )

        # change_log NULL/NULL phantom row count
        out["queries"]["change_log_phantom"] = run(
            cur,
            """
            WITH failed_versions AS (
                SELECT id FROM gedcom_versions WHERE status = 'failed'
            )
            SELECT
                COUNT(*) FILTER (WHERE version_id IN (SELECT id FROM failed_versions)) AS failed_version_rows,
                COUNT(*) FILTER (WHERE old_value IS NULL AND new_value IS NULL) AS null_payload_rows,
                COUNT(*) FILTER (WHERE version_id IN (SELECT id FROM failed_versions) OR (old_value IS NULL AND new_value IS NULL)) AS combined_droppable
            FROM gedcom_change_log;
            """,
            "phantom",
        )

        # gemini_api_calls retention candidates (E3 prep)
        out["queries"]["gemini_api_age_distribution"] = run(
            cur,
            """
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE created_at < NOW() - INTERVAL '90 days') AS over_90d,
                COUNT(*) FILTER (WHERE created_at < NOW() - INTERVAL '180 days') AS over_180d,
                MIN(created_at) AS oldest,
                MAX(created_at) AS newest,
                pg_size_pretty(SUM(
                    COALESCE(octet_length(prompt_text), 0)
                    + COALESCE(octet_length(full_response::text), 0)
                    + COALESCE(octet_length(gedcom_context), 0)
                )::bigint) AS payload_total
            FROM gemini_api_calls;
            """,
            "gemini_age",
        )

    out_path = Path("docs/feedback/session-154-supabase-e1-prep.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    def _default(o):
        if hasattr(o, "isoformat"):
            return o.isoformat()
        if hasattr(o, "__class__") and o.__class__.__name__ == "Decimal":
            return float(o)
        return str(o)

    out_path.write_text(json.dumps(out, indent=2, default=_default))
    print(f"Wrote {out_path}")
    for name, rows in out["queries"].items():
        print(f"  {name}: {len(rows)} row(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
