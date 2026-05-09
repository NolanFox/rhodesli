"""Phase 158-1b — Find the person with the MOST distinct payload_hash states.

Gives the user a more dramatic example of what would be lost if we DROP v1
without backfilling historical rows.
"""
import os
import sys

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()


def conn():
    url = os.environ["SUPABASE_URL"]
    project_ref = url.replace("https://", "").split(".")[0]
    return psycopg2.connect(
        host="aws-0-us-west-2.pooler.supabase.com",
        port=6543,
        database="postgres",
        user=f"postgres.{project_ref}",
        password=os.environ["SUPABASE_DB_PASSWORD"],
    )


def main():
    out_lines = []

    def w(s=""):
        print(s)
        out_lines.append(s)

    w("# Session 158 Phase 158-1b — Maximum-Change Person")
    w()
    w("Find the gedcom_id with the most distinct payload_hash states in v1, to")
    w("show user the worst-case data loss if v1 is DROPed without backfill.")
    w()

    with conn() as c, c.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        # Aggregate distinct payload_hashes per gedcom_id
        # NULL payload_hashes count as 1 each (legacy rows pre-payload_hash)
        cur.execute(
            """
            SELECT gedcom_id,
                   COUNT(DISTINCT payload_hash) AS distinct_hashes,
                   COUNT(*) FILTER (WHERE payload_hash IS NULL) AS null_hash_rows,
                   COUNT(*) AS total_rows,
                   MAX(name) AS sample_name,
                   MAX(surname) AS sample_surname
            FROM gedcom_individuals
            GROUP BY gedcom_id
            ORDER BY distinct_hashes DESC, total_rows DESC
            LIMIT 20
            """
        )
        rows = cur.fetchall()

        w("## Top 20 individuals by distinct payload_hash count")
        w()
        w("| gedcom_id | name | distinct hashes | null rows | total rows |")
        w("|---|---|---|---|---|")
        for r in rows:
            w(f"| `{r['gedcom_id']}` | {r['sample_name']!r} | {r['distinct_hashes']} | {r['null_hash_rows']} | {r['total_rows']} |")
        w()

        # Same for families
        cur.execute(
            """
            SELECT family_gedcom_id,
                   COUNT(DISTINCT payload_hash) AS distinct_hashes,
                   COUNT(*) FILTER (WHERE payload_hash IS NULL) AS null_hash_rows,
                   COUNT(*) AS total_rows
            FROM gedcom_families
            GROUP BY family_gedcom_id
            ORDER BY distinct_hashes DESC, total_rows DESC
            LIMIT 10
            """
        )
        frows = cur.fetchall()

        w("## Top 10 families by distinct payload_hash count")
        w()
        w("| family_gedcom_id | distinct hashes | null rows | total rows |")
        w("|---|---|---|---|")
        for r in frows:
            w(f"| `{r['family_gedcom_id']}` | {r['distinct_hashes']} | {r['null_hash_rows']} | {r['total_rows']} |")
        w()

        # Aggregated stats
        cur.execute(
            """
            SELECT
                COUNT(DISTINCT gedcom_id) AS total_individuals,
                SUM(CASE WHEN distinct_hashes > 1 THEN 1 ELSE 0 END) AS individuals_with_changes,
                SUM(CASE WHEN distinct_hashes >= 3 THEN 1 ELSE 0 END) AS individuals_3plus_states,
                SUM(distinct_hashes) AS sum_distinct_states
            FROM (
                SELECT gedcom_id, COUNT(DISTINCT payload_hash) AS distinct_hashes
                FROM gedcom_individuals
                WHERE payload_hash IS NOT NULL
                GROUP BY gedcom_id
            ) AS sub
            """
        )
        agg = cur.fetchone()
        w("## Aggregate stats — INDIVIDUALS (excl. NULL payload_hash)")
        w()
        w(f"- Total distinct gedcom_ids: {agg['total_individuals']:,}")
        w(f"- Individuals with >1 distinct payload_hash state: {agg['individuals_with_changes']:,} ({100*agg['individuals_with_changes']/max(1,agg['total_individuals']):.1f}%)")
        w(f"- Individuals with >=3 distinct states: {agg['individuals_3plus_states']:,}")
        w(f"- Total distinct (gedcom_id, payload_hash) pairs (= post-backfill v2 row estimate): **{agg['sum_distinct_states']:,}**")
        w()

        # Same for families
        cur.execute(
            """
            SELECT
                COUNT(DISTINCT family_gedcom_id) AS total_families,
                SUM(CASE WHEN distinct_hashes > 1 THEN 1 ELSE 0 END) AS families_with_changes,
                SUM(distinct_hashes) AS sum_distinct_states
            FROM (
                SELECT family_gedcom_id, COUNT(DISTINCT payload_hash) AS distinct_hashes
                FROM gedcom_families
                WHERE payload_hash IS NOT NULL
                GROUP BY family_gedcom_id
            ) AS sub
            """
        )
        fagg = cur.fetchone()
        w("## Aggregate stats — FAMILIES (excl. NULL payload_hash)")
        w()
        w(f"- Total distinct family_gedcom_ids: {fagg['total_families']:,}")
        w(f"- Families with >1 distinct payload_hash state: {fagg['families_with_changes']:,} ({100*fagg['families_with_changes']/max(1,fagg['total_families']):.1f}%)")
        w(f"- Total distinct (family_gedcom_id, payload_hash) pairs (= post-backfill v2 row estimate): **{fagg['sum_distinct_states']:,}**")
        w()

        # Show null-hash row counts
        cur.execute("SELECT COUNT(*) FILTER (WHERE payload_hash IS NULL) AS null_rows, COUNT(*) AS total FROM gedcom_individuals")
        nh = cur.fetchone()
        w(f"## NULL payload_hash rows (legacy pre-hash data)")
        w()
        w(f"- gedcom_individuals: {nh['null_rows']:,} of {nh['total']:,} ({100*nh['null_rows']/nh['total']:.1f}%)")
        cur.execute("SELECT COUNT(*) FILTER (WHERE payload_hash IS NULL) AS null_rows, COUNT(*) AS total FROM gedcom_families")
        fnh = cur.fetchone()
        w(f"- gedcom_families: {fnh['null_rows']:,} of {fnh['total']:,} ({100*fnh['null_rows']/fnh['total']:.1f}%)")
        w()

        # Implication
        w("## Implication for cutover strategy")
        w()
        w(f"If Option A (full historical backfill) is chosen:")
        w(f"- v2 individuals: ~{agg['sum_distinct_states']:,} rows (vs current 21,998 — adds ~{agg['sum_distinct_states']-21998:,})")
        w(f"- v2 families: ~{fagg['sum_distinct_states']:,} rows (vs current 6,741 — adds ~{fagg['sum_distinct_states']-6741:,})")
        w(f"- Plus need to handle {nh['null_rows']:,} NULL-hash individual rows (compute canonical hash)")
        w(f"- Total v2 rows: ~{agg['sum_distinct_states'] + fagg['sum_distinct_states']:,} vs v1's 196,645+33,324 = 229,969 → still **~{229969 / max(1, agg['sum_distinct_states'] + fagg['sum_distinct_states']):.1f}x reduction**")
        w()
        w("If Option B (keep v1 individuals + families):")
        w("- Save only what change_log saves (~30 MB compressed in R2 — 1.65M rows)")
        w("- v1 individuals + families stay (~150 MB on disk after VACUUM)")
        w("- Still need to keep dual-read helper or re-point app reads back to v1")
        w()

    report_path = "docs/feedback/session-158-max-changes.md"
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w") as f:
        f.write("\n".join(out_lines) + "\n")
    print(f"\nReport saved to {report_path}")


if __name__ == "__main__":
    main()
