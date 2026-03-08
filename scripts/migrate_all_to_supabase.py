#!/usr/bin/env python3
"""Comprehensive Supabase data migration script for Rhodesli.

Migrates ALL JSON data files to Supabase Postgres tables.
Idempotent — can be run multiple times safely (uses upsert).

Usage:
    python scripts/migrate_all_to_supabase.py --dry-run   # Preview only
    python scripts/migrate_all_to_supabase.py              # Execute migration

Requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY env vars.
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DATA_DIR = PROJECT_ROOT / "data"

# =========================================================================
# SQL for table creation (output for manual execution if needed)
# =========================================================================

CREATE_TABLE_SQL = {
    "date_labels": """
CREATE TABLE IF NOT EXISTS date_labels (
    photo_id TEXT PRIMARY KEY,
    data JSONB,
    estimated_year INT,
    confidence TEXT,
    scene_description TEXT,
    reanalyzed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
""",
    "photo_locations": """
CREATE TABLE IF NOT EXISTS photo_locations (
    photo_id TEXT PRIMARY KEY,
    data JSONB,
    place TEXT,
    confidence TEXT,
    latitude FLOAT,
    longitude FLOAT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
""",
    "person_comments": """
CREATE TABLE IF NOT EXISTS person_comments (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    identity_id TEXT NOT NULL,
    comment TEXT NOT NULL,
    author TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);
""",
    "discovery_log": """
CREATE TABLE IF NOT EXISTS discovery_log (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    face_id TEXT NOT NULL,
    target_identity_id TEXT,
    decision TEXT NOT NULL,
    decided_by TEXT DEFAULT 'admin',
    data JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);
""",
    "audit_log": """
CREATE TABLE IF NOT EXISTS audit_log (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    action TEXT NOT NULL,
    target_id TEXT,
    target_type TEXT,
    actor TEXT DEFAULT 'admin',
    data JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);
""",
    "pending_uploads": """
CREATE TABLE IF NOT EXISTS pending_uploads (
    job_id TEXT PRIMARY KEY,
    user_id TEXT,
    status TEXT DEFAULT 'pending',
    filename TEXT,
    data JSONB,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
""",
    "comparison_results": """
CREATE TABLE IF NOT EXISTS comparison_results (
    result_id TEXT PRIMARY KEY,
    data JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);
""",
    "birth_year_estimates": """
CREATE TABLE IF NOT EXISTS birth_year_estimates (
    identity_id TEXT PRIMARY KEY,
    estimated_year INT,
    confidence FLOAT,
    data JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);
""",
    "corrections_log": """
CREATE TABLE IF NOT EXISTS corrections_log (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    photo_id TEXT,
    identity_id TEXT,
    correction_type TEXT,
    data JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);
""",
}


def get_client():
    """Get Supabase client."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        logger.error("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
        sys.exit(1)
    from supabase import create_client

    return create_client(url, key)


def try_create_tables(client, dry_run=False):
    """Attempt to create tables via RPC. Outputs SQL if that fails."""
    tables_needed = list(CREATE_TABLE_SQL.keys())
    failed_tables = []

    for table_name in tables_needed:
        sql = CREATE_TABLE_SQL[table_name].strip()
        if dry_run:
            logger.info(f"[DRY RUN] Would create table: {table_name}")
            continue

        try:
            # Try to verify table exists by selecting from it
            client.table(table_name).select("*").limit(0).execute()
            logger.info(f"Table {table_name} already exists")
        except Exception:
            # Table doesn't exist — try to create via SQL RPC
            try:
                client.rpc("exec_sql", {"query": sql}).execute()
                logger.info(f"Created table: {table_name}")
            except Exception:
                failed_tables.append(table_name)
                logger.warning(f"Cannot create {table_name} via API")

    if failed_tables:
        logger.warning("\n" + "=" * 60)
        logger.warning("The following tables need manual creation in Supabase dashboard:")
        logger.warning("Go to: Supabase Dashboard > SQL Editor > New Query")
        logger.warning("=" * 60)
        for t in failed_tables:
            print(CREATE_TABLE_SQL[t])
        logger.warning("=" * 60)
        return failed_tables
    return []


def _upsert_batch(client, table_name, rows, batch_size=100, conflict_col=None):
    """Upsert rows in batches. Returns (success_count, error_count)."""
    success = 0
    errors = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        try:
            if conflict_col:
                client.table(table_name).upsert(batch, on_conflict=conflict_col).execute()
            else:
                client.table(table_name).upsert(batch).execute()
            success += len(batch)
        except Exception as e:
            errors += len(batch)
            logger.error(f"  Batch {i // batch_size + 1} failed: {e}")
    return success, errors


def _insert_batch(client, table_name, rows, batch_size=100):
    """Insert rows in batches (for tables without a natural key). Returns (success, errors)."""
    success = 0
    errors = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        try:
            client.table(table_name).insert(batch).execute()
            success += len(batch)
        except Exception as e:
            errors += len(batch)
            logger.error(f"  Batch {i // batch_size + 1} failed: {e}")
    return success, errors


def migrate_date_labels(client, dry_run=False):
    """Migrate data/date_labels.json -> date_labels table."""
    path = DATA_DIR / "date_labels.json"
    if not path.exists():
        logger.info("date_labels.json not found — skipping")
        return 0, 0

    data = json.loads(path.read_text())
    labels = data.get("labels", [])
    logger.info(f"date_labels: {len(labels)} entries to migrate")

    if dry_run:
        return len(labels), 0

    rows = []
    for label in labels:
        photo_id = label.get("photo_id")
        if not photo_id:
            continue
        rows.append(
            {
                "photo_id": photo_id,
                "data": label,
                "estimated_year": label.get("best_year_estimate"),
                "confidence": label.get("confidence"),
                "scene_description": label.get("scene_description"),
                "reanalyzed_at": label.get("reanalyzed_at"),
            }
        )

    return _upsert_batch(client, "date_labels", rows)


def migrate_photo_locations(client, dry_run=False):
    """Migrate data/photo_locations.json -> photo_locations table."""
    path = DATA_DIR / "photo_locations.json"
    if not path.exists():
        logger.info("photo_locations.json not found — skipping")
        return 0, 0

    data = json.loads(path.read_text())
    photos = data.get("photos", {})
    logger.info(f"photo_locations: {len(photos)} entries to migrate")

    if dry_run:
        return len(photos), 0

    rows = []
    for photo_id, loc in photos.items():
        rows.append(
            {
                "photo_id": photo_id,
                "data": loc,
                "place": loc.get("location_name", ""),
                "confidence": loc.get("confidence"),
                "latitude": loc.get("lat"),
                "longitude": loc.get("lng"),
            }
        )

    return _upsert_batch(client, "photo_locations", rows)


def migrate_birth_year_estimates(client, dry_run=False):
    """Migrate data/birth_year_estimates.json -> birth_year_estimates table."""
    path = DATA_DIR / "birth_year_estimates.json"
    if not path.exists():
        logger.info("birth_year_estimates.json not found — skipping")
        return 0, 0

    data = json.loads(path.read_text())
    estimates = data.get("estimates", [])
    logger.info(f"birth_year_estimates: {len(estimates)} entries to migrate")

    if dry_run:
        return len(estimates), 0

    rows = []
    for est in estimates:
        identity_id = est.get("identity_id")
        if not identity_id:
            continue
        rows.append(
            {
                "identity_id": identity_id,
                "estimated_year": est.get("birth_year_estimate"),
                "confidence": est.get("birth_year_confidence"),
                "data": est,
            }
        )

    return _upsert_batch(client, "birth_year_estimates", rows)


def migrate_discovery_log(client, dry_run=False):
    """Migrate data/discovery_log.json -> discovery_log table."""
    path = DATA_DIR / "discovery_log.json"
    if not path.exists():
        logger.info("discovery_log.json not found — skipping")
        return 0, 0

    data = json.loads(path.read_text())
    entries = data.get("entries", [])
    logger.info(f"discovery_log: {len(entries)} entries to migrate")

    if dry_run:
        return len(entries), 0

    # Clear existing and re-insert (log entries don't have stable IDs)
    try:
        client.table("discovery_log").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
    except Exception as e:
        logger.warning(f"  Could not clear discovery_log: {e}")

    rows = []
    for entry in entries:
        decision = entry.get("user_decision", "pending")
        rows.append(
            {
                "face_id": entry.get("face_id", ""),
                "target_identity_id": entry.get("target_identity_id"),
                "decision": decision,
                "decided_by": "admin",
                "data": entry,
                "created_at": entry.get("timestamp") or entry.get("user_decision_timestamp"),
            }
        )

    return _insert_batch(client, "discovery_log", rows)


def migrate_audit_log(client, dry_run=False):
    """Migrate data/audit_log.json -> audit_log table."""
    path = DATA_DIR / "audit_log.json"
    if not path.exists():
        logger.info("audit_log.json not found — skipping")
        return 0, 0

    data = json.loads(path.read_text())
    entries = data.get("entries", [])
    logger.info(f"audit_log: {len(entries)} entries to migrate")

    if dry_run:
        return len(entries), 0

    # Clear and re-insert
    try:
        client.table("audit_log").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
    except Exception as e:
        logger.warning(f"  Could not clear audit_log: {e}")

    rows = []
    for entry in entries:
        rows.append(
            {
                "action": entry.get("action", "unknown"),
                "target_id": entry.get("annotation_id"),
                "target_type": "annotation",
                "actor": entry.get("admin", "admin"),
                "data": entry,
                "created_at": entry.get("timestamp"),
            }
        )

    return _insert_batch(client, "audit_log", rows)


def migrate_pending_uploads(client, dry_run=False):
    """Migrate data/pending_uploads.json -> pending_uploads table."""
    path = DATA_DIR / "pending_uploads.json"
    if not path.exists():
        logger.info("pending_uploads.json not found — skipping")
        return 0, 0

    data = json.loads(path.read_text())
    uploads = data.get("uploads", {})
    logger.info(f"pending_uploads: {len(uploads)} entries to migrate")

    if dry_run:
        return len(uploads), 0

    rows = []
    for job_id, upload in uploads.items():
        rows.append(
            {
                "job_id": job_id,
                "user_id": upload.get("user_id") or upload.get("uploaded_by"),
                "status": upload.get("status", "pending"),
                "filename": upload.get("filename") or upload.get("original_filename"),
                "data": upload,
                "created_at": upload.get("uploaded_at"),
            }
        )

    return _upsert_batch(client, "pending_uploads", rows)


def migrate_comparison_results(client, dry_run=False):
    """Migrate data/comparison_results.json -> comparison_results table."""
    path = DATA_DIR / "comparison_results.json"
    if not path.exists():
        logger.info("comparison_results.json not found — skipping")
        return 0, 0

    data = json.loads(path.read_text())
    results = data.get("results", {})
    logger.info(f"comparison_results: {len(results)} entries to migrate")

    if dry_run:
        return len(results), 0

    rows = []
    for result_id, result in results.items():
        rows.append(
            {
                "result_id": result_id,
                "data": result,
            }
        )

    return _upsert_batch(client, "comparison_results", rows)


def migrate_corrections_log(client, dry_run=False):
    """Migrate data/corrections_log.json -> corrections_log table."""
    path = DATA_DIR / "corrections_log.json"
    if not path.exists():
        logger.info("corrections_log.json not found — skipping")
        return 0, 0

    data = json.loads(path.read_text())
    corrections = data.get("corrections", [])
    logger.info(f"corrections_log: {len(corrections)} entries to migrate")

    if dry_run:
        return len(corrections), 0

    # Clear and re-insert
    try:
        client.table("corrections_log").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
    except Exception as e:
        logger.warning(f"  Could not clear corrections_log: {e}")

    rows = []
    for corr in corrections:
        rows.append(
            {
                "photo_id": corr.get("photo_id"),
                "identity_id": corr.get("identity_id"),
                "correction_type": corr.get("type") or corr.get("correction_type", "date"),
                "data": corr,
                "created_at": corr.get("timestamp") or corr.get("created_at"),
            }
        )

    return _insert_batch(client, "corrections_log", rows)


def migrate_person_comments(client, dry_run=False):
    """Migrate data/person_comments.json -> person_comments table."""
    path = DATA_DIR / "person_comments.json"
    if not path.exists():
        logger.info("person_comments.json not found — skipping")
        return 0, 0

    data = json.loads(path.read_text())
    # Could be {"comments": [...]} or {"identity_id": [...]}
    comments = data.get("comments", [])
    if not comments and isinstance(data, dict):
        # Try flat dict format {identity_id: [comment_list]}
        for identity_id, comment_list in data.items():
            if identity_id in ("schema_version", "comments"):
                continue
            if isinstance(comment_list, list):
                for c in comment_list:
                    if isinstance(c, dict):
                        c["identity_id"] = identity_id
                        comments.append(c)
                    elif isinstance(c, str):
                        comments.append({"identity_id": identity_id, "comment": c})

    logger.info(f"person_comments: {len(comments)} entries to migrate")

    if dry_run:
        return len(comments), 0

    # Clear and re-insert
    try:
        client.table("person_comments").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
    except Exception as e:
        logger.warning(f"  Could not clear person_comments: {e}")

    rows = []
    for c in comments:
        rows.append(
            {
                "identity_id": c.get("identity_id", ""),
                "comment": c.get("comment", c.get("text", "")),
                "author": c.get("author") or c.get("user", "admin"),
                "created_at": c.get("created_at") or c.get("timestamp"),
            }
        )

    return _insert_batch(client, "person_comments", rows)


def main():
    parser = argparse.ArgumentParser(description="Migrate all Rhodesli data to Supabase")
    parser.add_argument("--dry-run", action="store_true", help="Preview migration without writing")
    args = parser.parse_args()

    if args.dry_run:
        logger.info("=" * 60)
        logger.info("DRY RUN MODE — no data will be written")
        logger.info("=" * 60)

    client = get_client()

    # Step 1: Create tables
    logger.info("\n--- Step 1: Create tables ---")
    failed = try_create_tables(client, args.dry_run)

    # Step 2: Migrate each data file
    logger.info("\n--- Step 2: Migrate data ---")

    migrations = [
        ("date_labels", migrate_date_labels),
        ("photo_locations", migrate_photo_locations),
        ("birth_year_estimates", migrate_birth_year_estimates),
        ("discovery_log", migrate_discovery_log),
        ("audit_log", migrate_audit_log),
        ("pending_uploads", migrate_pending_uploads),
        ("comparison_results", migrate_comparison_results),
        ("corrections_log", migrate_corrections_log),
        ("person_comments", migrate_person_comments),
    ]

    results = {}
    for name, func in migrations:
        logger.info(f"\nMigrating {name}...")
        try:
            success, errors = func(client, args.dry_run)
            results[name] = {"success": success, "errors": errors}
            if args.dry_run:
                logger.info(f"  [DRY RUN] Would migrate {success} rows")
            else:
                logger.info(f"  Success: {success}, Errors: {errors}")
        except Exception as e:
            results[name] = {"success": 0, "errors": -1, "exception": str(e)}
            logger.error(f"  FAILED: {e}")

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("MIGRATION SUMMARY")
    logger.info("=" * 60)
    total_success = 0
    total_errors = 0
    for name, r in results.items():
        status = "OK" if r["errors"] == 0 else "ERRORS" if r["errors"] > 0 else "FAILED"
        logger.info(f"  {name:25s} {status:8s} success={r['success']:5d} errors={r['errors']}")
        total_success += r["success"]
        total_errors += max(r["errors"], 0)

    logger.info(f"\n  TOTAL: {total_success} rows migrated, {total_errors} errors")

    if failed:
        logger.warning(f"\n  {len(failed)} tables need manual creation (SQL printed above)")

    if total_errors > 0:
        logger.error("\n  Some migrations had errors. Re-run to retry (script is idempotent).")
        return 1

    logger.info("\n  Migration complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
