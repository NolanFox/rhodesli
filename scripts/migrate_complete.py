#!/usr/bin/env python3
"""Migrate ALL JSON data files to Supabase Postgres tables.

Migrates 8 JSON files:
  1. date_labels.json     -> date_labels
  2. photo_locations.json -> photo_locations
  3. person_comments.json -> person_comments
  4. discovery_log.json   -> discovery_log
  5. audit_log.json       -> audit_log
  6. comparison_results.json -> comparison_results
  7. birth_year_estimates.json -> birth_year_estimates
  8. corrections_log.json -> corrections_log

Usage:
  python scripts/migrate_complete.py --dry-run          # preview counts
  python scripts/migrate_complete.py                    # run migration
  python scripts/migrate_complete.py --verbose          # detailed logging
  python scripts/migrate_complete.py --dry-run --verbose
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Load .env
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())

DATA_DIR = Path(__file__).parent.parent / "data"
PROJECT_REF = "fvynibivlphxwfowzkjl"


def get_connection():
    """Connect to Supabase Postgres using individual params (password may contain @)."""
    import psycopg2

    db_password = os.environ.get("SUPABASE_DB_PASSWORD")
    if not db_password:
        print("ERROR: SUPABASE_DB_PASSWORD not set")
        sys.exit(1)

    return psycopg2.connect(
        host=f"db.{PROJECT_REF}.supabase.co",
        port=5432,
        dbname="postgres",
        user="postgres",
        password=db_password,
    )


def load_json(filename: str) -> dict | list | None:
    """Load a JSON file from data/, returning None if missing."""
    path = DATA_DIR / filename
    if not path.exists():
        print(f"  WARNING: {path} not found, skipping")
        return None
    with open(path) as f:
        return json.load(f)


# ============================================================
# Migration functions — one per table
# ============================================================


def migrate_date_labels(conn, dry_run: bool, verbose: bool) -> int:
    """date_labels.json -> date_labels table.

    JSON structure: {"schema_version": 2, "labels": [{photo_id, ...}, ...]}
    Each entry has many fields; we extract known columns and store the
    full entry as full_data JSONB for anything we don't have a column for.
    """
    data = load_json("date_labels.json")
    if data is None:
        return 0

    labels = data.get("labels", [])
    if not labels:
        print("  No labels found in date_labels.json")
        return 0

    if dry_run:
        print(f"  Would insert/upsert {len(labels)} rows into date_labels")
        return len(labels)

    cur = conn.cursor()
    count = 0
    for entry in labels:
        photo_id = entry.get("photo_id")
        if not photo_id:
            continue

        # Extract probable_range -> year_range_start/end
        prob_range = entry.get("probable_range", [])
        year_start = prob_range[0] if len(prob_range) >= 1 else None
        year_end = prob_range[1] if len(prob_range) >= 2 else None

        # controlled_tags or keywords -> tags array
        tags = entry.get("controlled_tags") or entry.get("keywords") or []

        cur.execute(
            """
            INSERT INTO date_labels (
                photo_id, estimated_decade, best_year_estimate, confidence,
                year_range_start, year_range_end, scene_description, tags,
                evidence, model, prompt_version, reanalyzed_at,
                location_evidence, visible_text, gemini_raw_location,
                full_data, created_at
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s
            )
            ON CONFLICT (photo_id) DO UPDATE SET
                estimated_decade = EXCLUDED.estimated_decade,
                best_year_estimate = EXCLUDED.best_year_estimate,
                confidence = EXCLUDED.confidence,
                year_range_start = EXCLUDED.year_range_start,
                year_range_end = EXCLUDED.year_range_end,
                scene_description = EXCLUDED.scene_description,
                tags = EXCLUDED.tags,
                evidence = EXCLUDED.evidence,
                model = EXCLUDED.model,
                prompt_version = EXCLUDED.prompt_version,
                reanalyzed_at = EXCLUDED.reanalyzed_at,
                location_evidence = EXCLUDED.location_evidence,
                visible_text = EXCLUDED.visible_text,
                gemini_raw_location = EXCLUDED.gemini_raw_location,
                full_data = EXCLUDED.full_data,
                updated_at = NOW()
            """,
            (
                photo_id,
                entry.get("estimated_decade"),
                entry.get("best_year_estimate"),
                entry.get("confidence"),
                year_start,
                year_end,
                entry.get("scene_description"),
                tags if tags else None,
                json.dumps(entry.get("evidence", {})),
                entry.get("model"),
                entry.get("prompt_version"),
                entry.get("reanalyzed_at"),
                json.dumps(entry.get("location_evidence", {})),
                entry.get("visible_text"),
                entry.get("location_estimate"),  # gemini_raw_location
                json.dumps(entry),  # full_data — entire entry
                entry.get("created_at"),
            ),
        )
        count += 1
        if verbose:
            print(f"    date_labels: {photo_id}")

    conn.commit()
    return count


def migrate_photo_locations(conn, dry_run: bool, verbose: bool) -> int:
    """photo_locations.json -> photo_locations table.

    JSON structure: {"version": 1, "photos": {"photo_id": {...}, ...}}
    Each entry is keyed by photo_id with lat/lng/location_name etc.
    """
    data = load_json("photo_locations.json")
    if data is None:
        return 0

    photos = data.get("photos", {})
    if not photos:
        print("  No photos found in photo_locations.json")
        return 0

    if dry_run:
        print(f"  Would insert/upsert {len(photos)} rows into photo_locations")
        return len(photos)

    cur = conn.cursor()
    count = 0
    for photo_id, entry in photos.items():
        cur.execute(
            """
            INSERT INTO photo_locations (
                photo_id, lat, lng, location_name, location_estimate,
                confidence, region, biographical_evidence,
                missing_child_analysis, visual_evidence,
                gemini_raw_location, full_data, created_at
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s, NOW()
            )
            ON CONFLICT (photo_id) DO UPDATE SET
                lat = EXCLUDED.lat,
                lng = EXCLUDED.lng,
                location_name = EXCLUDED.location_name,
                location_estimate = EXCLUDED.location_estimate,
                confidence = EXCLUDED.confidence,
                region = EXCLUDED.region,
                biographical_evidence = EXCLUDED.biographical_evidence,
                missing_child_analysis = EXCLUDED.missing_child_analysis,
                visual_evidence = EXCLUDED.visual_evidence,
                gemini_raw_location = EXCLUDED.gemini_raw_location,
                full_data = EXCLUDED.full_data,
                updated_at = NOW()
            """,
            (
                entry.get("photo_id", photo_id),
                entry.get("lat"),
                entry.get("lng"),
                entry.get("location_name"),
                entry.get("location_estimate"),
                entry.get("confidence"),
                entry.get("region"),
                entry.get("biographical_evidence"),
                entry.get("missing_child_analysis"),
                entry.get("visual_evidence"),
                entry.get("gemini_raw_location"),
                json.dumps(entry),  # full entry as JSONB
            ),
        )
        count += 1
        if verbose:
            print(f"    photo_locations: {photo_id}")

    conn.commit()
    return count


def migrate_person_comments(conn, dry_run: bool, verbose: bool) -> int:
    """person_comments.json -> person_comments table.

    JSON structure: {"schema_version": 1, "comments": {"identity_id": [comments...]}}
    Each comment has: id, author, text, timestamp, status.
    """
    data = load_json("person_comments.json")
    if data is None:
        return 0

    comments = data.get("comments", {})
    if not comments:
        print("  No comments found in person_comments.json")
        return 0

    total = sum(len(v) for v in comments.values())

    if dry_run:
        print(f"  Would insert {total} rows into person_comments ({len(comments)} identities)")
        return total

    cur = conn.cursor()
    count = 0
    for identity_id, comment_list in comments.items():
        for comment in comment_list:
            cur.execute(
                """
                INSERT INTO person_comments (
                    identity_id, user_id, user_email, comment_text,
                    comment_type, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    identity_id,
                    comment.get("id"),  # use comment id as user_id placeholder
                    comment.get("author"),
                    comment.get("text", ""),
                    comment.get("status", "general"),
                    comment.get("timestamp"),
                ),
            )
            count += 1
            if verbose:
                print(f"    person_comments: {identity_id} -> {comment.get('id')}")

    conn.commit()
    return count


def migrate_discovery_log(conn, dry_run: bool, verbose: bool) -> int:
    """discovery_log.json -> discovery_log table.

    JSON structure: {"schema_version": 1, "entries": [{...}, ...]}
    Each entry has: source_identity_id, target_identity_id, action, distance, etc.
    """
    data = load_json("discovery_log.json")
    if data is None:
        return 0

    entries = data.get("entries", [])
    if not entries:
        print("  No entries found in discovery_log.json")
        return 0

    if dry_run:
        print(f"  Would insert {len(entries)} rows into discovery_log")
        return len(entries)

    cur = conn.cursor()
    count = 0
    for entry in entries:
        cur.execute(
            """
            INSERT INTO discovery_log (
                source_identity_id, target_identity_id, action,
                distance, admin_user, notes, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                entry.get("source_identity_id", ""),
                entry.get("target_identity_id", ""),
                entry.get("action", ""),
                entry.get("distance"),
                entry.get("admin_user"),
                entry.get("notes"),
                entry.get("timestamp"),
            ),
        )
        count += 1
        if verbose and count <= 5:
            print(
                f"    discovery_log: {entry.get('source_identity_id')} "
                f"-> {entry.get('target_identity_id')} ({entry.get('action')})"
            )

    conn.commit()
    return count


def migrate_audit_log(conn, dry_run: bool, verbose: bool) -> int:
    """audit_log.json -> audit_log table.

    JSON structure: {"entries": [{action, annotation_id, admin, timestamp, details}, ...]}
    All entries have action="approved". Map annotation_id -> entity_id.
    """
    data = load_json("audit_log.json")
    if data is None:
        return 0

    entries = data.get("entries", [])
    if not entries:
        print("  No entries found in audit_log.json")
        return 0

    if dry_run:
        print(f"  Would insert {len(entries)} rows into audit_log")
        return len(entries)

    cur = conn.cursor()
    count = 0
    for entry in entries:
        cur.execute(
            """
            INSERT INTO audit_log (
                action, entity_type, entity_id, user_id, user_email,
                old_value, new_value, metadata, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                entry.get("action", "unknown"),
                "annotation",  # all current entries are annotation approvals
                entry.get("annotation_id", ""),
                None,
                entry.get("admin"),
                None,
                None,
                json.dumps({"details": entry.get("details", "")}),
                entry.get("timestamp"),
            ),
        )
        count += 1
        if verbose and count <= 5:
            print(f"    audit_log: {entry.get('action')} {entry.get('annotation_id')}")

    conn.commit()
    return count


def migrate_comparison_results(conn, dry_run: bool, verbose: bool) -> int:
    """comparison_results.json -> comparison_results table.

    JSON structure: {"schema_version": 1, "results": {"result_id": {...}, ...}}
    Each result has: result_id, query_type, photo_id, matches, etc.
    We store one row per result with result_data JSONB for full context.
    """
    data = load_json("comparison_results.json")
    if data is None:
        return 0

    results = data.get("results", {})
    if not results:
        print("  No results found in comparison_results.json")
        return 0

    if dry_run:
        print(f"  Would insert {len(results)} rows into comparison_results")
        return len(results)

    cur = conn.cursor()
    count = 0
    for result_id, entry in results.items():
        # Extract first match distance if available
        matches = entry.get("matches", [])
        first_distance = matches[0].get("distance") if matches else None
        first_calibrated = matches[0].get("confidence_pct") if matches else None

        # Extract face IDs from first match
        face_id_1 = entry.get("query_face_id")
        face_id_2 = matches[0].get("face_id") if matches else None

        cur.execute(
            """
            INSERT INTO comparison_results (
                photo_id_1, photo_id_2, face_id_1, face_id_2,
                distance, calibrated_score, comparison_type,
                user_id, result_data, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                entry.get("photo_id"),
                None,  # second photo not always present
                face_id_1,
                face_id_2,
                first_distance,
                first_calibrated,
                entry.get("query_type"),
                entry.get("user_id"),
                json.dumps(entry),  # full result as JSONB
                entry.get("created_at"),
            ),
        )
        count += 1
        if verbose and count <= 5:
            print(f"    comparison_results: {result_id}")

    conn.commit()
    return count


def migrate_birth_year_estimates(conn, dry_run: bool, verbose: bool) -> int:
    """birth_year_estimates.json -> birth_year_estimates table.

    JSON structure: {"schema_version": 1, "estimates": [{identity_id, evidence: [{...}]}, ...]}
    Each estimate has identity-level data with per-photo evidence array.
    We create one row per (identity_id, photo_id) from the evidence array.
    """
    data = load_json("birth_year_estimates.json")
    if data is None:
        return 0

    estimates = data.get("estimates", [])
    if not estimates:
        print("  No estimates found in birth_year_estimates.json")
        return 0

    # Count total rows (one per evidence entry)
    total_rows = 0
    for est in estimates:
        evidence = est.get("evidence", [])
        if evidence:
            total_rows += len(evidence)
        else:
            # Still insert one row for the identity-level estimate
            total_rows += 1

    if dry_run:
        print(f"  Would insert {total_rows} rows into birth_year_estimates ({len(estimates)} identities)")
        return total_rows

    cur = conn.cursor()
    count = 0
    for est in estimates:
        identity_id = est.get("identity_id", "")
        evidence = est.get("evidence", [])

        if evidence:
            for ev in evidence:
                cur.execute(
                    """
                    INSERT INTO birth_year_estimates (
                        identity_id, photo_id, estimated_age, photo_year,
                        estimated_birth_year, source, confidence, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                    """,
                    (
                        identity_id,
                        ev.get("photo_id", ""),
                        ev.get("estimated_age"),
                        ev.get("photo_year"),
                        ev.get("implied_birth"),
                        ev.get("matching_method", "gemini"),
                        est.get("birth_year_confidence"),
                    ),
                )
                count += 1
        else:
            # Identity-level only (no per-photo evidence)
            cur.execute(
                """
                INSERT INTO birth_year_estimates (
                    identity_id, photo_id, estimated_age, photo_year,
                    estimated_birth_year, source, confidence, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                """,
                (
                    identity_id,
                    "",
                    None,
                    None,
                    est.get("birth_year_estimate"),
                    "gemini",
                    est.get("birth_year_confidence"),
                ),
            )
            count += 1

        if verbose and count <= 10:
            print(f"    birth_year_estimates: {identity_id} ({len(evidence)} evidence)")

    conn.commit()
    return count


def migrate_corrections_log(conn, dry_run: bool, verbose: bool) -> int:
    """corrections_log.json -> corrections_log table.

    JSON structure: {"schema_version": 1, "corrections": [{id, photo_id, field, ...}, ...]}
    Each correction has: id, photo_id, field, old_value, new_value, timestamps.
    """
    data = load_json("corrections_log.json")
    if data is None:
        return 0

    corrections = data.get("corrections", [])
    if not corrections:
        print("  No corrections found in corrections_log.json")
        return 0

    if dry_run:
        print(f"  Would insert {len(corrections)} rows into corrections_log")
        return len(corrections)

    cur = conn.cursor()
    count = 0
    for entry in corrections:
        # old_value and new_value can be dicts — serialize to text
        old_val = entry.get("old_value")
        new_val = entry.get("new_value")
        old_text = (
            json.dumps(old_val) if isinstance(old_val, (dict, list)) else str(old_val) if old_val is not None else None
        )
        new_text = (
            json.dumps(new_val) if isinstance(new_val, (dict, list)) else str(new_val) if new_val is not None else None
        )

        cur.execute(
            """
            INSERT INTO corrections_log (
                photo_id, field, old_value, new_value,
                corrected_by, correction_type, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                entry.get("photo_id", ""),
                entry.get("field", ""),
                old_text,
                new_text,
                entry.get("contributor_email"),
                entry.get("new_source", "manual"),
                entry.get("timestamp"),
            ),
        )
        count += 1
        if verbose and count <= 5:
            print(f"    corrections_log: {entry.get('photo_id')} {entry.get('field')}")

    conn.commit()
    return count


# ============================================================
# Main
# ============================================================

MIGRATIONS = [
    ("date_labels", migrate_date_labels),
    ("photo_locations", migrate_photo_locations),
    ("person_comments", migrate_person_comments),
    ("discovery_log", migrate_discovery_log),
    ("audit_log", migrate_audit_log),
    ("comparison_results", migrate_comparison_results),
    ("birth_year_estimates", migrate_birth_year_estimates),
    ("corrections_log", migrate_corrections_log),
]


def main():
    parser = argparse.ArgumentParser(description="Migrate JSON data to Supabase Postgres")
    parser.add_argument("--dry-run", action="store_true", help="Print counts without inserting")
    parser.add_argument("--verbose", action="store_true", help="Detailed per-row logging")
    args = parser.parse_args()

    print(f"{'DRY RUN — ' if args.dry_run else ''}Rhodesli JSON -> Supabase Migration")
    print(f"Data directory: {DATA_DIR}")
    print("=" * 60)

    conn = None
    if not args.dry_run:
        conn = get_connection()
        print("Connected to Supabase Postgres")

    summary = {}
    total = 0

    for table_name, migrate_fn in MIGRATIONS:
        print(f"\n[{table_name}]")
        try:
            count = migrate_fn(conn, args.dry_run, args.verbose)
            summary[table_name] = count
            total += count
            print(f"  -> {count} rows {'would be migrated' if args.dry_run else 'migrated'}")
        except Exception as e:
            summary[table_name] = f"ERROR: {e}"
            print(f"  -> ERROR: {e}")
            if conn:
                conn.rollback()

    if conn:
        conn.close()

    # Print summary
    print("\n" + "=" * 60)
    print("MIGRATION SUMMARY")
    print("=" * 60)
    for table_name, result in summary.items():
        status = f"{result} rows" if isinstance(result, int) else result
        print(f"  {table_name:30s} {status}")
    print(f"  {'TOTAL':30s} {total} rows")
    print("=" * 60)

    if args.dry_run:
        print("\nThis was a DRY RUN. No data was inserted.")
        print("Run without --dry-run to execute the migration.")


if __name__ == "__main__":
    main()
