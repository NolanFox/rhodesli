"""Phase 158-1 — Change-history reality check.

Resolves Albert/Esther/Reva gedcom_ids, demonstrates v1 has multi-state history,
v2 has only current state. Output is the corpus the user reviews when choosing
Option A/B/C.
"""
import json
import os
import sys

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()


def conn():
    # Project ref derived from SUPABASE_URL per Lesson 175 (pooler region us-west-2)
    url = os.environ["SUPABASE_URL"]
    project_ref = url.replace("https://", "").split(".")[0]
    return psycopg2.connect(
        host="aws-0-us-west-2.pooler.supabase.com",
        port=6543,
        database="postgres",
        user=f"postgres.{project_ref}",
        password=os.environ["SUPABASE_DB_PASSWORD"],
    )


def find_gedcom_id(cur, given_name, surname, limit=5):
    """Find gedcom_id(s) for a person, latest is_current row."""
    cur.execute(
        """
        SELECT gedcom_id, name, given_name, surname, birth_date, birth_place,
               death_date, death_place, version_id
        FROM gedcom_individuals
        WHERE LOWER(given_name) LIKE LOWER(%s) AND LOWER(surname) LIKE LOWER(%s)
        AND is_current = TRUE
        ORDER BY version_id DESC
        LIMIT %s
        """,
        (f"%{given_name}%", f"%{surname}%", limit),
    )
    return cur.fetchall()


def history_for_gedcom_id(cur, gedcom_id):
    """All v1 rows for this gedcom_id across versions, ordered by version number."""
    cur.execute(
        """
        SELECT i.version_id, i.payload_hash, i.name, i.given_name, i.surname,
               i.birth_date, i.birth_place, i.death_date, i.death_place,
               i.is_current,
               COALESCE(v.version_number, -1) AS version_number
        FROM gedcom_individuals i
        LEFT JOIN gedcom_versions v ON v.id = i.version_id
        WHERE i.gedcom_id = %s
        ORDER BY COALESCE(v.version_number, -1), i.payload_hash
        """,
        (gedcom_id,),
    )
    return cur.fetchall()


def v2_for_gedcom_id(cur, gedcom_id):
    """All v2 rows for this gedcom_id."""
    cur.execute(
        """
        SELECT first_seen_version, last_seen_version, payload_hash,
               name, given_name, surname,
               birth_date, birth_place, death_date, death_place
        FROM gedcom_individuals_v2
        WHERE gedcom_id = %s
        ORDER BY first_seen_version
        """,
        (gedcom_id,),
    )
    return cur.fetchall()


def main():
    out_lines = []

    def w(s=""):
        print(s)
        out_lines.append(s)

    w("# Session 158 Phase 158-1 — Change-History Reality Check")
    w()
    w(f"**Date**: 2026-05-09")
    w(f"**Source**: scripts/session158_phase1_history_check.py")
    w()
    w("## Purpose")
    w()
    w("Decide whether v2's current `is_current=TRUE` snapshot is sufficient OR")
    w("we need to backfill historical (`is_current=FALSE`) rows from v1 before")
    w("DROPing v1. User asked: 'maintain some sense of GEDCOM change over time.'")
    w()

    with conn() as c, c.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        # Step 1.1 — find candidates
        w("## 1.1 Resolve candidate gedcom_ids")
        w()
        candidates = []
        for gn, sn in [("Albert", "Fox"), ("Esther", "Fox"), ("Esther", "Burd"), ("Reva", "Heft"), ("Harry", "Fox")]:
            rows = find_gedcom_id(cur, gn, sn, limit=3)
            w(f"### {gn} {sn}")
            if not rows:
                w("  (no matches)")
                w()
                continue
            for r in rows:
                w(f"  - gedcom_id=`{r['gedcom_id']}` name={r['name']!r} birth={r['birth_date']!r}/{r['birth_place']!r} death={r['death_date']!r}/{r['death_place']!r} v={r['version_id']}")
                candidates.append((f"{gn} {sn}", r["gedcom_id"]))
            w()

        # Pick top candidate per name
        seen_labels = set()
        chosen = []
        for label, gid in candidates:
            if label not in seen_labels:
                chosen.append((label, gid))
                seen_labels.add(label)

        # Step 1.2 — multi-state history shape
        w("## 1.2 Per-person change-history shape (v1)")
        w()
        w("| Person | gedcom_id | versions | distinct payload_hashes | first→last v |")
        w("|---|---|---|---|---|")
        history_summary = []
        for label, gid in chosen:
            rows = history_for_gedcom_id(cur, gid)
            distinct_hashes = len(set(r["payload_hash"] for r in rows if r["payload_hash"]))
            min_v = min((r["version_number"] for r in rows if r["version_number"] is not None), default=None)
            max_v = max((r["version_number"] for r in rows if r["version_number"] is not None), default=None)
            w(f"| {label} | `{gid}` | {len(rows)} | {distinct_hashes} | v{min_v}→v{max_v} |")
            history_summary.append({
                "label": label,
                "gedcom_id": gid,
                "version_count": len(rows),
                "distinct_states": distinct_hashes,
            })
        w()

        # Pick the person with the most distinct states for the deep dive
        if not history_summary:
            w("**STOP — no history found. Investigate.**")
            sys.exit(1)
        best = max(history_summary, key=lambda h: h["distinct_states"])
        w(f"**Deepest history**: {best['label']} with {best['distinct_states']} distinct states across {best['version_count']} versions.")
        w()

        # Step 1.3 — v2 current state for the same people
        w("## 1.3 v2 current state for same people")
        w()
        w("| Person | gedcom_id | v2 row count | distinct payload_hashes |")
        w("|---|---|---|---|")
        for label, gid in chosen:
            rows = v2_for_gedcom_id(cur, gid)
            distinct = len(set(r["payload_hash"] for r in rows if r["payload_hash"]))
            w(f"| {label} | `{gid}` | {len(rows)} | {distinct} |")
        w()

        # Step 1.5 — demonstrate the deep-dive query on best candidate
        w(f"## 1.5 Change-history deep dive — {best['label']} (`{best['gedcom_id']}`)")
        w()
        rows = history_for_gedcom_id(cur, best["gedcom_id"])
        w("| v# | hash[:8] | name | given | surname | birth_date | birth_place | death_date | death_place | current |")
        w("|---|---|---|---|---|---|---|---|---|---|")
        for r in rows:
            ph = (r["payload_hash"] or "")[:8]
            w(f"| {r['version_number']} | `{ph}` | {r['name']!r} | {r['given_name']!r} | {r['surname']!r} | {r['birth_date']!r} | {r['birth_place']!r} | {r['death_date']!r} | {r['death_place']!r} | {r['is_current']} |")
        w()

        # Compare to v2
        w(f"### v2 current shape for `{best['gedcom_id']}`")
        w()
        v2_rows = v2_for_gedcom_id(cur, best["gedcom_id"])
        w("| first_seen_version | last_seen_version | hash[:8] | name | birth_place | death_place |")
        w("|---|---|---|---|---|---|")
        for r in v2_rows:
            ph = (r["payload_hash"] or "")[:8]
            w(f"| {r['first_seen_version']} | {r['last_seen_version']} | `{ph}` | {r['name']!r} | {r['birth_place']!r} | {r['death_place']!r} |")
        w()

        # Step 1.4 — surface the decision
        w("## 1.4 Strategy decision (USER REQUIRED)")
        w()
        if best["distinct_states"] > 1:
            gap_status = "REAL gap exists — multiple states in v1, only current in v2"
        else:
            gap_status = "No gap — best candidate has only 1 distinct state across all versions"
        w(f"**Gap status**: {gap_status}")
        w()
        w("Options:")
        w("- **A. Full historical backfill** (recommended): backfill is_current=FALSE rows to v2 with payload_hash dedup. v2 grows to ~30-50K rows. Native change-history queries.")
        w("- **B. Keep v1 alive**: only DROP gedcom_change_log; leave individuals + families. ~300 MB savings instead of ~700 MB. History queries hit v1.")
        w("- **C. R2 archive of historical rows**: archive is_current=FALSE to R2; query helper pulls on demand. Full storage win but slow per-id history queries.")
        w()

    # Save report
    report_path = "docs/feedback/session-158-change-history-proof.md"
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w") as f:
        f.write("\n".join(out_lines) + "\n")
    print(f"\nReport saved to {report_path}")


if __name__ == "__main__":
    main()
