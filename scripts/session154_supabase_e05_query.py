"""Session 154 Phase E0.5 — GEDCOM bloat root-cause investigation (READ-ONLY).

Connects via Supabase session pooler and runs the 10 diagnostic queries from
the prompt. Writes JSON output suitable for the bloat root-cause markdown.

All queries here are READ-ONLY (SELECT only). No DELETE / TRUNCATE / VACUUM /
UPDATE / INSERT.
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
    if not env_path.exists():
        print(f"FAIL: {env_path} not found", file=sys.stderr)
        sys.exit(1)
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def connect():
    """Connect to Supabase via session pooler (IPv4-friendly).

    Direct host db.<ref>.supabase.co is IPv6-only on local Macs.
    """
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


def run_query(cur, sql: str, name: str) -> list[dict]:
    """Run a SELECT and return list of dict rows. Refuses anything non-SELECT."""
    stripped = sql.strip().upper()
    if not stripped.startswith(("SELECT", "WITH")):
        raise ValueError(f"Refusing non-SELECT in {name!r}: {sql[:80]!r}")
    cur.execute(sql)
    rows = cur.fetchall()
    return [dict(r) for r in rows]


def main() -> int:
    load_env()
    out: dict = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "queries": {},
    }

    with connect() as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        # 1. Distinct individuals
        out["queries"]["q1_distinct_individuals"] = run_query(
            cur,
            "SELECT COUNT(DISTINCT gedcom_id) AS distinct_individuals FROM gedcom_individuals;",
            "q1",
        )

        # 2. Total rows
        out["queries"]["q2_total_rows"] = run_query(
            cur,
            "SELECT COUNT(*) AS total_rows FROM gedcom_individuals;",
            "q2",
        )

        # 3. Version count
        out["queries"]["q3_version_count"] = run_query(
            cur,
            "SELECT COUNT(*) AS version_count FROM gedcom_versions;",
            "q3",
        )

        # 4. Per-version row counts
        out["queries"]["q4_per_version_counts"] = run_query(
            cur,
            """
            SELECT version_id::text AS version_id,
                   is_current,
                   COUNT(*) AS row_count
            FROM gedcom_individuals
            GROUP BY 1, 2
            ORDER BY version_id NULLS FIRST, is_current;
            """,
            "q4",
        )

        # 5. Top-20 duplicated payload_hash groups (proof of dedup status)
        out["queries"]["q5_top20_duplicated_hashes"] = run_query(
            cur,
            """
            SELECT payload_hash,
                   COUNT(*) AS dup_count
            FROM gedcom_individuals
            WHERE payload_hash IS NOT NULL
            GROUP BY payload_hash
            HAVING COUNT(*) > 1
            ORDER BY dup_count DESC
            LIMIT 20;
            """,
            "q5",
        )

        # 5b. payload_hash NULL count (so we know whether dedup column is even populated)
        out["queries"]["q5b_payload_hash_coverage"] = run_query(
            cur,
            """
            SELECT
                COUNT(*) AS total_rows,
                COUNT(payload_hash) AS rows_with_hash,
                COUNT(*) - COUNT(payload_hash) AS rows_without_hash
            FROM gedcom_individuals;
            """,
            "q5b",
        )

        # 6. Per-individual storage breakdown for example
        out["queries"]["q6_example_individual"] = run_query(
            cur,
            """
            SELECT version_id::text AS version_id,
                   is_current,
                   payload_hash,
                   octet_length(raw_record_json::text) AS raw_bytes,
                   octet_length(names_json::text) AS names_bytes,
                   octet_length(events_json::text) AS events_bytes,
                   octet_length(birth_event_json::text) AS birth_bytes,
                   octet_length(death_event_json::text) AS death_bytes,
                   created_at
            FROM gedcom_individuals
            WHERE gedcom_id = '@I132506612777@'
            ORDER BY created_at;
            """,
            "q6",
        )

        # Try one more example if the first returns nothing — pick a real gedcom_id
        if not out["queries"]["q6_example_individual"]:
            out["queries"]["q6b_alt_example"] = run_query(
                cur,
                """
                WITH busiest AS (
                    SELECT gedcom_id
                    FROM gedcom_individuals
                    GROUP BY gedcom_id
                    ORDER BY COUNT(*) DESC
                    LIMIT 1
                )
                SELECT gi.gedcom_id,
                       gi.version_id::text AS version_id,
                       gi.is_current,
                       gi.payload_hash,
                       octet_length(gi.raw_record_json::text) AS raw_bytes,
                       octet_length(gi.names_json::text) AS names_bytes,
                       octet_length(gi.events_json::text) AS events_bytes,
                       gi.created_at
                FROM gedcom_individuals gi
                JOIN busiest b USING (gedcom_id)
                ORDER BY gi.created_at;
                """,
                "q6b",
            )

        # 7. Per-version change_log size
        out["queries"]["q7_change_log_per_version"] = run_query(
            cur,
            """
            SELECT version_id::text AS version_id,
                   COUNT(*) AS row_count
            FROM gedcom_change_log
            GROUP BY version_id
            ORDER BY row_count DESC
            LIMIT 20;
            """,
            "q7",
        )

        # 8. raw_record_json runtime footprint (current rows)
        out["queries"]["q8_raw_record_json_current"] = run_query(
            cur,
            """
            SELECT pg_size_pretty(SUM(octet_length(raw_record_json::text))::bigint) AS pretty,
                   SUM(octet_length(raw_record_json::text))::bigint AS bytes
            FROM gedcom_individuals
            WHERE is_current = TRUE;
            """,
            "q8",
        )

        # 9. raw_record_json total footprint (all versions)
        out["queries"]["q9_raw_record_json_total"] = run_query(
            cur,
            """
            SELECT pg_size_pretty(SUM(octet_length(raw_record_json::text))::bigint) AS pretty,
                   SUM(octet_length(raw_record_json::text))::bigint AS bytes
            FROM gedcom_individuals;
            """,
            "q9",
        )

        # 10. Index usage on gedcom_* tables
        out["queries"]["q10_index_usage"] = run_query(
            cur,
            """
            SELECT relname,
                   indexrelname,
                   idx_scan,
                   pg_relation_size(indexrelid) AS bytes,
                   pg_size_pretty(pg_relation_size(indexrelid)) AS pretty
            FROM pg_stat_user_indexes
            WHERE relname LIKE 'gedcom_%'
            ORDER BY idx_scan ASC, bytes DESC;
            """,
            "q10",
        )

        # Bonus: same dedup audit on change_log + relationships + records
        out["queries"]["q11_change_log_total"] = run_query(
            cur,
            "SELECT COUNT(*) AS rows, pg_size_pretty(pg_total_relation_size('gedcom_change_log')) AS size FROM gedcom_change_log;",
            "q11",
        )

        # Bonus: per-version footprint of gedcom_individuals (rough storage weight per version)
        out["queries"]["q12_per_version_avg_bytes"] = run_query(
            cur,
            """
            SELECT version_id::text AS version_id,
                   COUNT(*) AS rows,
                   pg_size_pretty(SUM(octet_length(raw_record_json::text))::bigint) AS raw_total,
                   ROUND(AVG(octet_length(raw_record_json::text))::numeric, 0) AS avg_raw_bytes_per_row
            FROM gedcom_individuals
            GROUP BY version_id
            ORDER BY rows DESC;
            """,
            "q12",
        )

        # Bonus: change_log dead-weight check — does anything READ from it?
        # We can only check if columns reference it; the actual dead-row check
        # is via pgstattuple but that requires extension. Instead just count
        # rows whose old_value/new_value are populated vs NULL.
        out["queries"]["q13_change_log_payload_audit"] = run_query(
            cur,
            """
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE old_value IS NOT NULL OR new_value IS NOT NULL) AS with_values,
                COUNT(*) FILTER (WHERE old_value IS NULL AND new_value IS NULL) AS without_values,
                COUNT(*) FILTER (WHERE change_type = 'added') AS added,
                COUNT(*) FILTER (WHERE change_type = 'modified') AS modified,
                COUNT(*) FILTER (WHERE change_type = 'removed') AS removed
            FROM gedcom_change_log;
            """,
            "q13",
        )

        # Bonus: Rich JSON column footprint on gedcom_individuals (current only)
        out["queries"]["q14_individuals_json_breakdown"] = run_query(
            cur,
            """
            SELECT
                pg_size_pretty(SUM(octet_length(raw_record_json::text))::bigint) AS raw_record,
                pg_size_pretty(SUM(octet_length(names_json::text))::bigint) AS names,
                pg_size_pretty(SUM(octet_length(events_json::text))::bigint) AS events,
                pg_size_pretty(SUM(octet_length(birth_event_json::text))::bigint) AS birth,
                pg_size_pretty(SUM(octet_length(death_event_json::text))::bigint) AS death,
                pg_size_pretty(SUM(octet_length(family_as_spouse_json::text))::bigint) AS family_as_spouse,
                pg_size_pretty(SUM(octet_length(family_as_child_json::text))::bigint) AS family_as_child,
                pg_size_pretty(SUM(octet_length(notes_json::text))::bigint) AS notes,
                pg_size_pretty(SUM(octet_length(citations_json::text))::bigint) AS citations
            FROM gedcom_individuals;
            """,
            "q14",
        )

        # Bonus: gedcom_versions detail — when imports happened
        out["queries"]["q15_versions_detail"] = run_query(
            cur,
            """
            SELECT id::text,
                   version_number,
                   imported_at,
                   source_file,
                   individual_count,
                   record_count,
                   status
            FROM gedcom_versions
            ORDER BY imported_at;
            """,
            "q15",
        )

    # Write output
    out_path = Path("docs/feedback/session-154-supabase-bloat-root-cause.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Custom serialization for datetime, Decimal etc.
    def _default(o):
        if hasattr(o, "isoformat"):
            return o.isoformat()
        if hasattr(o, "__class__") and o.__class__.__name__ == "Decimal":
            return float(o)
        return str(o)

    out_path.write_text(json.dumps(out, indent=2, default=_default))
    print(f"Wrote {out_path} ({out_path.stat().st_size} bytes)")
    print("Query summary:")
    for name, rows in out["queries"].items():
        print(f"  {name}: {len(rows)} row(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
