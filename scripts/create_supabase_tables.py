#!/usr/bin/env python3
"""Create all Supabase tables for full Rhodesli data migration.

Creates tables for:
1. Core data migration (date_labels, photo_locations, etc.)
2. Observability (sentry_events, posthog_events, railway_logs)
3. Community (contributor_suggestions, upload_tracking)
4. Corrections and audit trail

Uses direct Postgres connection via DATABASE_URL.
Safe to run multiple times (IF NOT EXISTS).
"""

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

import psycopg2

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set")
    sys.exit(1)


SQL_STATEMENTS = [
    # ============================================================
    # 1. CORE DATA MIGRATION TABLES
    # ============================================================
    """
    CREATE TABLE IF NOT EXISTS date_labels (
        id BIGSERIAL PRIMARY KEY,
        photo_id TEXT NOT NULL UNIQUE,
        estimated_decade INTEGER,
        best_year_estimate INTEGER,
        confidence TEXT,
        year_range_start INTEGER,
        year_range_end INTEGER,
        scene_description TEXT,
        tags TEXT[],
        evidence JSONB DEFAULT '{}',
        model TEXT,
        prompt_version TEXT,
        reanalyzed_at TIMESTAMPTZ,
        location_evidence JSONB DEFAULT '{}',
        visible_text TEXT,
        gemini_raw_location TEXT,
        full_data JSONB DEFAULT '{}',
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_date_labels_photo_id ON date_labels(photo_id);",
    "CREATE INDEX IF NOT EXISTS idx_date_labels_decade ON date_labels(estimated_decade);",
    """
    CREATE TABLE IF NOT EXISTS photo_locations (
        id BIGSERIAL PRIMARY KEY,
        photo_id TEXT NOT NULL UNIQUE,
        lat DOUBLE PRECISION,
        lng DOUBLE PRECISION,
        location_name TEXT,
        location_estimate TEXT,
        confidence TEXT,
        region TEXT,
        biographical_evidence TEXT,
        missing_child_analysis TEXT,
        visual_evidence TEXT,
        gemini_raw_location TEXT,
        full_data JSONB DEFAULT '{}',
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_photo_locations_photo_id ON photo_locations(photo_id);",
    """
    CREATE TABLE IF NOT EXISTS person_comments (
        id BIGSERIAL PRIMARY KEY,
        identity_id TEXT NOT NULL,
        user_id TEXT,
        user_email TEXT,
        comment_text TEXT NOT NULL,
        comment_type TEXT DEFAULT 'general',
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_person_comments_identity ON person_comments(identity_id);",
    """
    CREATE TABLE IF NOT EXISTS discovery_log (
        id BIGSERIAL PRIMARY KEY,
        source_identity_id TEXT NOT NULL,
        target_identity_id TEXT NOT NULL,
        action TEXT NOT NULL,
        distance DOUBLE PRECISION,
        admin_user TEXT,
        notes TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_discovery_log_source ON discovery_log(source_identity_id);",
    "CREATE INDEX IF NOT EXISTS idx_discovery_log_action ON discovery_log(action);",
    """
    CREATE TABLE IF NOT EXISTS audit_log (
        id BIGSERIAL PRIMARY KEY,
        action TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        user_id TEXT,
        user_email TEXT,
        old_value JSONB,
        new_value JSONB,
        metadata JSONB DEFAULT '{}',
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_audit_log_entity ON audit_log(entity_type, entity_id);",
    "CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action);",
    "CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log(created_at);",
    """
    CREATE TABLE IF NOT EXISTS pending_uploads (
        id BIGSERIAL PRIMARY KEY,
        job_id TEXT NOT NULL,
        filename TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        uploaded_by TEXT,
        file_size_bytes BIGINT,
        mime_type TEXT,
        source TEXT,
        collection TEXT,
        processing_result JSONB,
        faces_detected INTEGER,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        processed_at TIMESTAMPTZ
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_pending_uploads_status ON pending_uploads(status);",
    "CREATE INDEX IF NOT EXISTS idx_pending_uploads_job ON pending_uploads(job_id);",
    """
    CREATE TABLE IF NOT EXISTS comparison_results (
        id BIGSERIAL PRIMARY KEY,
        photo_id_1 TEXT,
        photo_id_2 TEXT,
        face_id_1 TEXT,
        face_id_2 TEXT,
        distance DOUBLE PRECISION,
        calibrated_score DOUBLE PRECISION,
        comparison_type TEXT,
        user_id TEXT,
        result_data JSONB DEFAULT '{}',
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_comparison_results_photos ON comparison_results(photo_id_1, photo_id_2);",
    """
    CREATE TABLE IF NOT EXISTS birth_year_estimates (
        id BIGSERIAL PRIMARY KEY,
        identity_id TEXT NOT NULL,
        photo_id TEXT NOT NULL,
        estimated_age INTEGER,
        photo_year INTEGER,
        estimated_birth_year INTEGER,
        source TEXT DEFAULT 'gemini',
        confidence TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_birth_year_identity ON birth_year_estimates(identity_id);",
    """
    CREATE TABLE IF NOT EXISTS corrections_log (
        id BIGSERIAL PRIMARY KEY,
        photo_id TEXT NOT NULL,
        field TEXT NOT NULL,
        old_value TEXT,
        new_value TEXT,
        corrected_by TEXT,
        correction_type TEXT DEFAULT 'manual',
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_corrections_photo ON corrections_log(photo_id);",
    # ============================================================
    # 2. OBSERVABILITY TABLES
    # ============================================================
    """
    CREATE TABLE IF NOT EXISTS sentry_events (
        id BIGSERIAL PRIMARY KEY,
        event_id TEXT UNIQUE,
        level TEXT NOT NULL DEFAULT 'error',
        message TEXT,
        exception_type TEXT,
        exception_value TEXT,
        stacktrace TEXT,
        tags JSONB DEFAULT '{}',
        extra JSONB DEFAULT '{}',
        user_id TEXT,
        url TEXT,
        environment TEXT DEFAULT 'production',
        release_version TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_sentry_events_level ON sentry_events(level);",
    "CREATE INDEX IF NOT EXISTS idx_sentry_events_created ON sentry_events(created_at);",
    """
    CREATE TABLE IF NOT EXISTS posthog_events (
        id BIGSERIAL PRIMARY KEY,
        event_name TEXT NOT NULL,
        distinct_id TEXT,
        properties JSONB DEFAULT '{}',
        session_id TEXT,
        page_url TEXT,
        referrer TEXT,
        device_type TEXT,
        browser TEXT,
        country TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_posthog_events_name ON posthog_events(event_name);",
    "CREATE INDEX IF NOT EXISTS idx_posthog_events_created ON posthog_events(created_at);",
    "CREATE INDEX IF NOT EXISTS idx_posthog_events_distinct ON posthog_events(distinct_id);",
    """
    CREATE TABLE IF NOT EXISTS railway_logs (
        id BIGSERIAL PRIMARY KEY,
        log_level TEXT DEFAULT 'INFO',
        message TEXT NOT NULL,
        source TEXT DEFAULT 'app',
        request_method TEXT,
        request_path TEXT,
        status_code INTEGER,
        latency_ms INTEGER,
        user_agent TEXT,
        ip_address TEXT,
        metadata JSONB DEFAULT '{}',
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_railway_logs_level ON railway_logs(log_level);",
    "CREATE INDEX IF NOT EXISTS idx_railway_logs_created ON railway_logs(created_at);",
    "CREATE INDEX IF NOT EXISTS idx_railway_logs_path ON railway_logs(request_path);",
    # ============================================================
    # 3. COMMUNITY & CONTRIBUTOR TABLES
    # ============================================================
    """
    CREATE TABLE IF NOT EXISTS contributor_suggestions (
        id BIGSERIAL PRIMARY KEY,
        face_id TEXT,
        photo_id TEXT,
        identity_id TEXT,
        suggested_name TEXT,
        suggested_by_user_id TEXT,
        suggested_by_email TEXT,
        suggestion_type TEXT DEFAULT 'identification',
        confidence_note TEXT,
        status TEXT DEFAULT 'pending',
        reviewed_by TEXT,
        reviewed_at TIMESTAMPTZ,
        review_notes TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_suggestions_status ON contributor_suggestions(status);",
    "CREATE INDEX IF NOT EXISTS idx_suggestions_photo ON contributor_suggestions(photo_id);",
    "CREATE INDEX IF NOT EXISTS idx_suggestions_face ON contributor_suggestions(face_id);",
    """
    CREATE TABLE IF NOT EXISTS upload_tracking (
        id BIGSERIAL PRIMARY KEY,
        batch_id TEXT NOT NULL,
        filename TEXT NOT NULL,
        original_filename TEXT,
        file_hash TEXT,
        file_size_bytes BIGINT,
        mime_type TEXT,
        source TEXT,
        collection TEXT,
        uploaded_by_user_id TEXT,
        uploaded_by_email TEXT,
        upload_status TEXT DEFAULT 'uploaded',
        processing_status TEXT DEFAULT 'pending',
        photo_id TEXT,
        faces_detected INTEGER,
        r2_path TEXT,
        error_message TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        processed_at TIMESTAMPTZ
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_upload_tracking_batch ON upload_tracking(batch_id);",
    "CREATE INDEX IF NOT EXISTS idx_upload_tracking_status ON upload_tracking(upload_status);",
    "CREATE INDEX IF NOT EXISTS idx_upload_tracking_photo ON upload_tracking(photo_id);",
    # ============================================================
    # 4. SEARCH & ANALYTICS TABLES
    # ============================================================
    """
    CREATE TABLE IF NOT EXISTS search_queries (
        id BIGSERIAL PRIMARY KEY,
        query_text TEXT NOT NULL,
        query_type TEXT DEFAULT 'text',
        results_count INTEGER,
        user_id TEXT,
        session_id TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_search_queries_created ON search_queries(created_at);",
    """
    CREATE TABLE IF NOT EXISTS page_views (
        id BIGSERIAL PRIMARY KEY,
        page_path TEXT NOT NULL,
        page_type TEXT,
        entity_id TEXT,
        user_id TEXT,
        session_id TEXT,
        referrer TEXT,
        user_agent TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_page_views_path ON page_views(page_path);",
    "CREATE INDEX IF NOT EXISTS idx_page_views_created ON page_views(created_at);",
]


def main():
    print("Connecting to Supabase Postgres...")
    db_password = os.environ.get("SUPABASE_DB_PASSWORD", "")
    project_ref = "fvynibivlphxwfowzkjl"
    conn = psycopg2.connect(
        host=f"db.{project_ref}.supabase.co",
        port=5432,
        dbname="postgres",
        user="postgres",
        password=db_password,
    )
    conn.autocommit = True
    cur = conn.cursor()

    success = 0
    errors = 0

    for i, sql in enumerate(SQL_STATEMENTS):
        try:
            cur.execute(sql)
            # Extract table/index name for logging
            sql_stripped = sql.strip()
            if "CREATE TABLE" in sql_stripped:
                name = (
                    sql_stripped.split("EXISTS")[1].split("(")[0].strip()
                    if "EXISTS" in sql_stripped
                    else f"statement {i}"
                )
                print(f"  [OK] Table: {name}")
            elif "CREATE INDEX" in sql_stripped:
                name = (
                    sql_stripped.split("EXISTS")[1].split(" ON")[0].strip()
                    if "EXISTS" in sql_stripped
                    else f"index {i}"
                )
                print(f"  [OK] Index: {name}")
            success += 1
        except Exception as e:
            print(f"  [ERROR] Statement {i}: {e}")
            errors += 1

    # Verify tables exist
    cur.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public'
        ORDER BY table_name;
    """)
    tables = [row[0] for row in cur.fetchall()]

    print(f"\n{'=' * 60}")
    print(f"Results: {success} succeeded, {errors} errors")
    print(f"\nAll public tables ({len(tables)}):")
    for t in tables:
        print(f"  - {t}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
