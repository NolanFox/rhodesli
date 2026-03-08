#!/usr/bin/env python3
"""Migrate local JSON data files to Supabase Postgres via psycopg2.

Reads from data/*.json and upserts into corresponding Supabase tables.
Uses INSERT ... ON CONFLICT for idempotent operation.

Connection: db.fvynibivlphxwfowzkjl.supabase.co:5432/postgres
Password: from SUPABASE_DB_PASSWORD env var (loaded from .env)

Usage:
    source venv/bin/activate && python scripts/migrate_data_psycopg2.py
"""

import json
import os
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path(__file__).parent.parent / "data"

DB_CONFIG = {
    "host": "db.fvynibivlphxwfowzkjl.supabase.co",
    "port": 5432,
    "dbname": "postgres",
    "user": "postgres",
    "password": os.environ.get("SUPABASE_DB_PASSWORD", ""),
    "connect_timeout": 10,
}


def load_json(filename):
    """Load a JSON file from the data directory. Returns None if not found."""
    path = DATA_DIR / filename
    if not path.exists():
        print(f"  SKIP: {filename} not found")
        return None
    with open(path) as f:
        return json.load(f)


def migrate_date_labels(cur):
    """date_labels.json -> date_labels table.

    JSON structure: {"labels": [{photo_id, estimated_decade, best_year_estimate,
    confidence, probable_range, evidence, model, prompt_version, scene_description,
    visible_text, keywords/controlled_tags, ...}, ...]}

    Table: photo_id (UNIQUE), estimated_decade, best_year_estimate, confidence,
    year_range_start, year_range_end, scene_description, tags (TEXT[]),
    evidence (JSONB), model, prompt_version, visible_text,
    gemini_raw_location, full_data (JSONB)
    """
    data = load_json("date_labels.json")
    if not data:
        return 0
    labels = data.get("labels", [])
    if not labels:
        print("  No labels found")
        return 0

    sql = """
        INSERT INTO date_labels (
            photo_id, estimated_decade, best_year_estimate, confidence,
            year_range_start, year_range_end, scene_description, tags,
            evidence, model, prompt_version, visible_text,
            gemini_raw_location, full_data
        ) VALUES (
            %(photo_id)s, %(estimated_decade)s, %(best_year_estimate)s, %(confidence)s,
            %(year_range_start)s, %(year_range_end)s, %(scene_description)s, %(tags)s,
            %(evidence)s, %(model)s, %(prompt_version)s, %(visible_text)s,
            %(gemini_raw_location)s, %(full_data)s
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
            visible_text = EXCLUDED.visible_text,
            gemini_raw_location = EXCLUDED.gemini_raw_location,
            full_data = EXCLUDED.full_data,
            updated_at = NOW()
    """

    success = 0
    errors = 0
    for label in labels:
        probable_range = label.get("probable_range", [None, None])
        # Combine keywords + controlled_tags for the tags array
        tags = label.get("controlled_tags", []) or []
        keywords = label.get("keywords", []) or []
        all_tags = list(set(tags + keywords))

        params = {
            "photo_id": label["photo_id"],
            "estimated_decade": label.get("estimated_decade"),
            "best_year_estimate": label.get("best_year_estimate"),
            "confidence": label.get("confidence"),
            "year_range_start": probable_range[0] if len(probable_range) > 0 else None,
            "year_range_end": probable_range[1] if len(probable_range) > 1 else None,
            "scene_description": label.get("scene_description"),
            "tags": all_tags if all_tags else None,
            "evidence": json.dumps(label.get("evidence", {})),
            "model": label.get("model"),
            "prompt_version": label.get("prompt_version"),
            "visible_text": label.get("visible_text"),
            "gemini_raw_location": label.get("location_estimate"),
            "full_data": json.dumps(label),
        }
        try:
            cur.execute(sql, params)
            success += 1
        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f"  ERROR on {label['photo_id']}: {e}")
    if errors > 3:
        print(f"  ... and {errors - 3} more errors")
    return success


def migrate_photo_locations(cur):
    """photo_locations.json -> photo_locations table.

    JSON structure: {"photos": {"photo_id": {photo_id, lat, lng, location_name,
    location_estimate, confidence, region, ...}, ...}}

    Table: photo_id (UNIQUE), lat, lng, location_name, location_estimate,
    confidence, region, full_data (JSONB)
    """
    data = load_json("photo_locations.json")
    if not data:
        return 0
    photos = data.get("photos", {})
    if not photos:
        print("  No photo locations found")
        return 0

    sql = """
        INSERT INTO photo_locations (
            photo_id, lat, lng, location_name, location_estimate,
            confidence, region, full_data
        ) VALUES (
            %(photo_id)s, %(lat)s, %(lng)s, %(location_name)s, %(location_estimate)s,
            %(confidence)s, %(region)s, %(full_data)s
        )
        ON CONFLICT (photo_id) DO UPDATE SET
            lat = EXCLUDED.lat,
            lng = EXCLUDED.lng,
            location_name = EXCLUDED.location_name,
            location_estimate = EXCLUDED.location_estimate,
            confidence = EXCLUDED.confidence,
            region = EXCLUDED.region,
            full_data = EXCLUDED.full_data,
            updated_at = NOW()
    """

    success = 0
    errors = 0
    for photo_id, loc in photos.items():
        params = {
            "photo_id": loc.get("photo_id", photo_id),
            "lat": loc.get("lat"),
            "lng": loc.get("lng"),
            "location_name": loc.get("location_name"),
            "location_estimate": loc.get("location_estimate"),
            "confidence": loc.get("confidence"),
            "region": loc.get("region"),
            "full_data": json.dumps(loc),
        }
        try:
            cur.execute(sql, params)
            success += 1
        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f"  ERROR on {photo_id}: {e}")
    if errors > 3:
        print(f"  ... and {errors - 3} more errors")
    return success


def migrate_person_comments(cur):
    """person_comments.json -> person_comments table.

    JSON structure: {"comments": {"identity_id": [{id, author, text, timestamp, status}, ...]}}

    Table: identity_id, user_email, comment_text, comment_type
    No unique constraint on content, so we use a check to avoid duplicates.
    """
    data = load_json("person_comments.json")
    if not data:
        return 0
    comments = data.get("comments", {})
    if not comments:
        print("  No person comments found")
        return 0

    sql = """
        INSERT INTO person_comments (identity_id, user_id, user_email, comment_text, comment_type, created_at)
        VALUES (%(identity_id)s, %(user_id)s, %(user_email)s, %(comment_text)s, %(comment_type)s, %(created_at)s)
    """

    # First, check how many rows already exist to avoid re-inserting
    cur.execute("SELECT COUNT(*) FROM person_comments")
    existing = cur.fetchone()[0]
    if existing > 0:
        print(f"  person_comments already has {existing} rows, clearing first")
        cur.execute("DELETE FROM person_comments")

    success = 0
    errors = 0
    for identity_id, comment_list in comments.items():
        for comment in comment_list:
            params = {
                "identity_id": identity_id,
                "user_id": comment.get("id"),
                "user_email": comment.get("author"),
                "comment_text": comment.get("text", ""),
                "comment_type": comment.get("status", "general"),
                "created_at": comment.get("timestamp"),
            }
            try:
                cur.execute(sql, params)
                success += 1
            except Exception as e:
                errors += 1
                if errors <= 3:
                    print(f"  ERROR: {e}")
    if errors > 3:
        print(f"  ... and {errors - 3} more errors")
    return success


def migrate_discovery_log(cur):
    """discovery_log.json -> discovery_log table.

    JSON structure: {"entries": [{source_identity_id, target_identity_id, action,
    distance, timestamp, face_id, tier, ...}, ...]}

    Table: source_identity_id, target_identity_id, action, distance, admin_user, notes
    """
    data = load_json("discovery_log.json")
    if not data:
        return 0
    entries = data.get("entries", [])
    if not entries:
        print("  No discovery log entries found")
        return 0

    # Clear and re-insert (no natural unique key)
    cur.execute("SELECT COUNT(*) FROM discovery_log")
    existing = cur.fetchone()[0]
    if existing > 0:
        print(f"  discovery_log already has {existing} rows, clearing first")
        cur.execute("DELETE FROM discovery_log")

    sql = """
        INSERT INTO discovery_log (
            source_identity_id, target_identity_id, action, distance, admin_user, notes, created_at
        ) VALUES (
            %(source_identity_id)s, %(target_identity_id)s, %(action)s, %(distance)s,
            %(admin_user)s, %(notes)s, %(created_at)s
        )
    """

    success = 0
    errors = 0
    for entry in entries:
        # Build notes from extra fields
        notes_parts = []
        if entry.get("face_id"):
            notes_parts.append(f"face_id={entry['face_id']}")
        if entry.get("tier"):
            notes_parts.append(f"tier={entry['tier']}")
        if entry.get("source_identity_name"):
            notes_parts.append(f"source={entry['source_identity_name']}")
        if entry.get("target_identity_name"):
            notes_parts.append(f"target={entry['target_identity_name']}")
        if entry.get("user_decision"):
            notes_parts.append(f"decision={entry['user_decision']}")

        params = {
            "source_identity_id": entry["source_identity_id"],
            "target_identity_id": entry["target_identity_id"],
            "action": entry.get("action", "unknown"),
            "distance": entry.get("distance"),
            "admin_user": None,
            "notes": "; ".join(notes_parts) if notes_parts else None,
            "created_at": entry.get("timestamp"),
        }
        try:
            cur.execute(sql, params)
            success += 1
        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f"  ERROR: {e}")
    if errors > 3:
        print(f"  ... and {errors - 3} more errors")
    return success


def migrate_audit_log(cur):
    """audit_log.json -> audit_log table.

    JSON structure: {"entries": [{action, annotation_id, admin, timestamp, details}, ...]}

    Table: action, entity_type, entity_id, user_id, user_email, old_value (JSONB),
    new_value (JSONB), metadata (JSONB)
    """
    data = load_json("audit_log.json")
    if not data:
        return 0
    entries = data.get("entries", [])
    if not entries:
        print("  No audit log entries found")
        return 0

    # Clear and re-insert
    cur.execute("SELECT COUNT(*) FROM audit_log")
    existing = cur.fetchone()[0]
    if existing > 0:
        print(f"  audit_log already has {existing} rows, clearing first")
        cur.execute("DELETE FROM audit_log")

    sql = """
        INSERT INTO audit_log (
            action, entity_type, entity_id, user_id, user_email, metadata, created_at
        ) VALUES (
            %(action)s, %(entity_type)s, %(entity_id)s, %(user_id)s,
            %(user_email)s, %(metadata)s, %(created_at)s
        )
    """

    success = 0
    errors = 0
    for entry in entries:
        metadata = {}
        if entry.get("details"):
            metadata["details"] = entry["details"]

        params = {
            "action": entry.get("action", "unknown"),
            "entity_type": "annotation",
            "entity_id": entry.get("annotation_id", "unknown"),
            "user_id": entry.get("admin"),
            "user_email": entry.get("admin"),
            "metadata": json.dumps(metadata) if metadata else "{}",
            "created_at": entry.get("timestamp"),
        }
        try:
            cur.execute(sql, params)
            success += 1
        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f"  ERROR: {e}")
    if errors > 3:
        print(f"  ... and {errors - 3} more errors")
    return success


def migrate_comparison_results(cur):
    """comparison_results.json -> comparison_results table.

    JSON structure: {"results": {"result_id": {result_id, query_type, query_name,
    photo_id, reference_person, matches: [{face_id, identity_id, distance,
    confidence_pct, tier}], responses}, ...}}

    Table: photo_id_1, photo_id_2, face_id_1, face_id_2, distance, calibrated_score,
    comparison_type, user_id, result_data (JSONB)

    Each result may have multiple matches; we flatten to one row per match.
    """
    data = load_json("comparison_results.json")
    if not data:
        return 0
    results = data.get("results", {})
    if not results:
        print("  No comparison results found")
        return 0

    # Clear and re-insert
    cur.execute("SELECT COUNT(*) FROM comparison_results")
    existing = cur.fetchone()[0]
    if existing > 0:
        print(f"  comparison_results already has {existing} rows, clearing first")
        cur.execute("DELETE FROM comparison_results")

    sql = """
        INSERT INTO comparison_results (
            photo_id_1, photo_id_2, face_id_1, face_id_2, distance,
            calibrated_score, comparison_type, user_id, result_data
        ) VALUES (
            %(photo_id_1)s, %(photo_id_2)s, %(face_id_1)s, %(face_id_2)s, %(distance)s,
            %(calibrated_score)s, %(comparison_type)s, %(user_id)s, %(result_data)s
        )
    """

    success = 0
    errors = 0
    for result_id, result in results.items():
        matches = result.get("matches", [])
        photo_id_1 = result.get("photo_id")
        comparison_type = result.get("query_type")

        if not matches:
            # Store as a single row with the full result as result_data
            params = {
                "photo_id_1": photo_id_1,
                "photo_id_2": None,
                "face_id_1": None,
                "face_id_2": None,
                "distance": None,
                "calibrated_score": None,
                "comparison_type": comparison_type,
                "user_id": None,
                "result_data": json.dumps(result),
            }
            try:
                cur.execute(sql, params)
                success += 1
            except Exception as e:
                errors += 1
                if errors <= 3:
                    print(f"  ERROR on {result_id}: {e}")
        else:
            for match in matches:
                params = {
                    "photo_id_1": photo_id_1,
                    "photo_id_2": None,
                    "face_id_1": match.get("face_id"),
                    "face_id_2": None,
                    "distance": match.get("distance"),
                    "calibrated_score": match.get("confidence_pct"),
                    "comparison_type": comparison_type,
                    "user_id": None,
                    "result_data": json.dumps(result),
                }
                try:
                    cur.execute(sql, params)
                    success += 1
                except Exception as e:
                    errors += 1
                    if errors <= 3:
                        print(f"  ERROR on {result_id}: {e}")
    if errors > 3:
        print(f"  ... and {errors - 3} more errors")
    return success


def migrate_birth_year_estimates(cur):
    """birth_year_estimates.json -> birth_year_estimates table.

    JSON structure: {"estimates": [{identity_id, name, birth_year_estimate,
    birth_year_confidence, birth_year_range, evidence: [{photo_id, photo_year,
    estimated_age, implied_birth, ...}], ...}, ...]}

    Table: identity_id, photo_id, estimated_age, photo_year, estimated_birth_year,
    source, confidence

    One row per (identity, photo evidence item).
    """
    data = load_json("birth_year_estimates.json")
    if not data:
        return 0
    estimates = data.get("estimates", [])
    if not estimates:
        print("  No birth year estimates found")
        return 0

    # Clear and re-insert
    cur.execute("SELECT COUNT(*) FROM birth_year_estimates")
    existing = cur.fetchone()[0]
    if existing > 0:
        print(f"  birth_year_estimates already has {existing} rows, clearing first")
        cur.execute("DELETE FROM birth_year_estimates")

    sql = """
        INSERT INTO birth_year_estimates (
            identity_id, photo_id, estimated_age, photo_year,
            estimated_birth_year, source, confidence
        ) VALUES (
            %(identity_id)s, %(photo_id)s, %(estimated_age)s, %(photo_year)s,
            %(estimated_birth_year)s, %(source)s, %(confidence)s
        )
    """

    success = 0
    errors = 0
    for estimate in estimates:
        identity_id = estimate["identity_id"]
        source = estimate.get("source", "gemini")
        confidence = estimate.get("birth_year_confidence")
        evidence_items = estimate.get("evidence", [])

        if not evidence_items:
            # Store one summary row if no per-photo evidence
            params = {
                "identity_id": identity_id,
                "photo_id": "summary",
                "estimated_age": None,
                "photo_year": None,
                "estimated_birth_year": estimate.get("birth_year_estimate"),
                "source": source,
                "confidence": confidence,
            }
            try:
                cur.execute(sql, params)
                success += 1
            except Exception as e:
                errors += 1
                if errors <= 3:
                    print(f"  ERROR on {identity_id}: {e}")
        else:
            for ev in evidence_items:
                params = {
                    "identity_id": identity_id,
                    "photo_id": ev.get("photo_id", "unknown"),
                    "estimated_age": ev.get("estimated_age"),
                    "photo_year": ev.get("photo_year"),
                    "estimated_birth_year": ev.get("implied_birth"),
                    "source": ev.get("matching_method", source),
                    "confidence": confidence,
                }
                try:
                    cur.execute(sql, params)
                    success += 1
                except Exception as e:
                    errors += 1
                    if errors <= 3:
                        print(f"  ERROR on {identity_id}/{ev.get('photo_id')}: {e}")
    if errors > 3:
        print(f"  ... and {errors - 3} more errors")
    return success


def migrate_corrections_log(cur):
    """corrections_log.json -> corrections_log table.

    JSON structure: {"corrections": [{id, photo_id, field, old_value, new_value,
    old_source, new_source, contributor_email, contributor_type, status, timestamp}, ...]}

    Table: photo_id, field, old_value, new_value, corrected_by, correction_type
    """
    data = load_json("corrections_log.json")
    if not data:
        return 0
    corrections = data.get("corrections", [])
    if not corrections:
        print("  No corrections found")
        return 0

    # Clear and re-insert
    cur.execute("SELECT COUNT(*) FROM corrections_log")
    existing = cur.fetchone()[0]
    if existing > 0:
        print(f"  corrections_log already has {existing} rows, clearing first")
        cur.execute("DELETE FROM corrections_log")

    sql = """
        INSERT INTO corrections_log (
            photo_id, field, old_value, new_value, corrected_by, correction_type, created_at
        ) VALUES (
            %(photo_id)s, %(field)s, %(old_value)s, %(new_value)s,
            %(corrected_by)s, %(correction_type)s, %(created_at)s
        )
    """

    success = 0
    errors = 0
    for corr in corrections:
        # Convert dict values to JSON strings for text columns
        old_val = corr.get("old_value")
        new_val = corr.get("new_value")
        if isinstance(old_val, dict):
            old_val = json.dumps(old_val)
        elif old_val is not None:
            old_val = str(old_val)
        if isinstance(new_val, dict):
            new_val = json.dumps(new_val)
        elif new_val is not None:
            new_val = str(new_val)

        params = {
            "photo_id": corr["photo_id"],
            "field": corr.get("field", "unknown"),
            "old_value": old_val,
            "new_value": new_val,
            "corrected_by": corr.get("contributor_email"),
            "correction_type": corr.get("contributor_type", "manual"),
            "created_at": corr.get("timestamp"),
        }
        try:
            cur.execute(sql, params)
            success += 1
        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f"  ERROR on {corr.get('id')}: {e}")
    if errors > 3:
        print(f"  ... and {errors - 3} more errors")
    return success


def main():
    if not DB_CONFIG["password"]:
        print("ERROR: SUPABASE_DB_PASSWORD not set. Add it to .env file.")
        sys.exit(1)

    # Force unbuffered output
    sys.stdout.reconfigure(line_buffering=True)

    print("Connecting to Supabase Postgres...")
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False
    cur = conn.cursor()

    migrations = [
        ("date_labels", migrate_date_labels),
        ("photo_locations", migrate_photo_locations),
        ("person_comments", migrate_person_comments),
        ("discovery_log", migrate_discovery_log),
        ("audit_log", migrate_audit_log),
        ("comparison_results", migrate_comparison_results),
        ("birth_year_estimates", migrate_birth_year_estimates),
        ("corrections_log", migrate_corrections_log),
    ]

    results = {}
    all_ok = True

    for table_name, migrate_fn in migrations:
        print(f"\n--- Migrating {table_name} ---")
        try:
            count = migrate_fn(cur)
            results[table_name] = count
            print(f"  OK: {count} rows inserted/updated")
        except Exception as e:
            results[table_name] = f"FAILED: {e}"
            all_ok = False
            print(f"  FAILED: {e}")
            conn.rollback()
            # Reconnect for next table
            conn = psycopg2.connect(**DB_CONFIG)
            conn.autocommit = False
            cur = conn.cursor()

    if all_ok:
        conn.commit()
        print("\n=== All migrations committed ===")
    else:
        print("\n=== Some migrations failed, rolling back remaining ===")
        conn.rollback()

    # Verify final counts
    print("\n=== Final Row Counts ===")
    verify_conn = psycopg2.connect(**DB_CONFIG)
    verify_cur = verify_conn.cursor()
    for table_name, _ in migrations:
        try:
            verify_cur.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = verify_cur.fetchone()[0]
            print(f"  {table_name}: {count} rows")
        except Exception as e:
            print(f"  {table_name}: ERROR - {e}")
    verify_conn.close()

    print("\n=== Migration Summary ===")
    for table_name, result in results.items():
        print(f"  {table_name}: {result}")

    conn.close()


if __name__ == "__main__":
    main()
