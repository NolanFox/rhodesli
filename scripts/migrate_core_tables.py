#!/usr/bin/env python3
"""Migrate core tables (identities, photos, photo_faces) to Supabase Postgres.

This completes DATA-007: the final step before flipping DATA_SOURCE=postgres.

Usage:
  python scripts/migrate_core_tables.py --dry-run          # preview counts
  python scripts/migrate_core_tables.py                    # run migration
  python scripts/migrate_core_tables.py --verbose          # detailed logging
"""

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
    """Connect to Supabase Postgres."""
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


def ensure_tables(conn):
    """Create tables if they don't exist, and ensure CHECK constraint covers all states."""
    cur = conn.cursor()

    # Create photos table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS photos (
            photo_id TEXT PRIMARY KEY,
            path TEXT NOT NULL,
            source TEXT,
            collection TEXT,
            source_url TEXT,
            upload_date TIMESTAMPTZ,
            width INTEGER,
            height INTEGER,
            face_count INTEGER DEFAULT 0,
            uploaded_by TEXT,
            job_id TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Create identities table — allow all states found in data
    cur.execute("""
        CREATE TABLE IF NOT EXISTS identities (
            identity_id UUID PRIMARY KEY,
            name TEXT NOT NULL,
            display_name TEXT,
            state TEXT NOT NULL,
            anchor_ids JSONB DEFAULT '[]',
            candidate_ids JSONB DEFAULT '[]',
            negative_ids JSONB DEFAULT '[]',
            metadata JSONB DEFAULT '{}',
            version_id INTEGER DEFAULT 1,
            merged_into UUID,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Drop the old CHECK constraint if it exists (it's too restrictive)
    cur.execute("""
        DO $$
        BEGIN
            ALTER TABLE identities DROP CONSTRAINT IF EXISTS identities_state_check;
        EXCEPTION WHEN undefined_object THEN
            NULL;
        END $$;
    """)

    # Add a broader CHECK constraint that covers all states
    cur.execute("""
        DO $$
        BEGIN
            ALTER TABLE identities ADD CONSTRAINT identities_state_check
                CHECK (state IN ('CONFIRMED', 'PROPOSED', 'INBOX', 'SKIPPED', 'CONTESTED', 'REJECTED'));
        EXCEPTION WHEN duplicate_object THEN
            NULL;
        END $$;
    """)

    # Create photo_faces table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS photo_faces (
            face_id TEXT PRIMARY KEY,
            photo_id TEXT REFERENCES photos(photo_id),
            bbox JSONB,
            det_score FLOAT,
            quality FLOAT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    # Create indexes
    cur.execute("CREATE INDEX IF NOT EXISTS idx_photos_collection ON photos(collection)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_identities_state ON identities(state)")
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_identities_merged_into ON identities(merged_into) WHERE merged_into IS NOT NULL"
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_photo_faces_photo_id ON photo_faces(photo_id)")

    conn.commit()
    print("Tables and indexes created/verified")


def migrate_identities(conn, dry_run: bool, verbose: bool) -> int:
    """identities.json -> identities table."""
    path = DATA_DIR / "identities.json"
    if not path.exists():
        print("  ERROR: identities.json not found")
        return 0

    with open(path) as f:
        data = json.load(f)

    identities = data.get("identities", {})
    if not identities:
        print("  No identities found")
        return 0

    if dry_run:
        print(f"  Would upsert {len(identities)} rows into identities")
        return len(identities)

    cur = conn.cursor()
    count = 0
    for identity_id, entry in identities.items():
        metadata = entry.get("metadata", {})
        # Include extra fields in metadata for preservation
        extra_fields = {}
        for key in ("promoted_at", "promoted_from", "promotion_reason", "display_name"):
            if key in entry:
                extra_fields[key] = entry[key]
        if extra_fields:
            metadata = {**metadata, **extra_fields}

        cur.execute(
            """
            INSERT INTO identities (
                identity_id, name, display_name, state,
                anchor_ids, candidate_ids, negative_ids, metadata,
                version_id, merged_into, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (identity_id) DO UPDATE SET
                name = EXCLUDED.name,
                display_name = EXCLUDED.display_name,
                state = EXCLUDED.state,
                anchor_ids = EXCLUDED.anchor_ids,
                candidate_ids = EXCLUDED.candidate_ids,
                negative_ids = EXCLUDED.negative_ids,
                metadata = EXCLUDED.metadata,
                version_id = EXCLUDED.version_id,
                merged_into = EXCLUDED.merged_into,
                updated_at = NOW()
            """,
            (
                identity_id,
                entry.get("name", ""),
                entry.get("display_name"),
                entry.get("state", "INBOX"),
                json.dumps(entry.get("anchor_ids", [])),
                json.dumps(entry.get("candidate_ids", [])),
                json.dumps(entry.get("negative_ids", [])),
                json.dumps(metadata) if metadata else "{}",
                entry.get("version_id", 1),
                entry.get("merged_into"),
                entry.get("created_at"),
                entry.get("updated_at"),
            ),
        )
        count += 1
        if verbose and count <= 10:
            print(f"    identity: {identity_id} ({entry.get('name')}) [{entry.get('state')}]")

    conn.commit()
    return count


def migrate_photos(conn, dry_run: bool, verbose: bool) -> int:
    """photo_index.json -> photos table."""
    path = DATA_DIR / "photo_index.json"
    if not path.exists():
        print("  ERROR: photo_index.json not found")
        return 0

    with open(path) as f:
        data = json.load(f)

    photos = data.get("photos", {})
    if not photos:
        print("  No photos found")
        return 0

    if dry_run:
        print(f"  Would upsert {len(photos)} rows into photos")
        return len(photos)

    cur = conn.cursor()
    count = 0
    for photo_id, entry in photos.items():
        face_ids = entry.get("face_ids", [])
        face_count = len(face_ids) if isinstance(face_ids, list) else 0

        cur.execute(
            """
            INSERT INTO photos (
                photo_id, path, source, collection, source_url,
                upload_date, width, height, face_count,
                uploaded_by, job_id, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (photo_id) DO UPDATE SET
                path = EXCLUDED.path,
                source = EXCLUDED.source,
                collection = EXCLUDED.collection,
                source_url = EXCLUDED.source_url,
                upload_date = EXCLUDED.upload_date,
                width = EXCLUDED.width,
                height = EXCLUDED.height,
                face_count = EXCLUDED.face_count,
                uploaded_by = EXCLUDED.uploaded_by,
                job_id = EXCLUDED.job_id,
                updated_at = NOW()
            """,
            (
                photo_id,
                entry.get("path", ""),
                entry.get("source", ""),
                entry.get("collection", ""),
                entry.get("source_url", ""),
                entry.get("upload_date"),
                entry.get("width"),
                entry.get("height"),
                face_count,
                entry.get("uploaded_by"),
                entry.get("job_id"),
            ),
        )
        count += 1
        if verbose and count <= 10:
            print(f"    photo: {photo_id} ({entry.get('path')})")

    conn.commit()
    return count


def migrate_photo_faces(conn, dry_run: bool, verbose: bool) -> int:
    """photo_index.json face_to_photo + embeddings -> photo_faces table."""
    path = DATA_DIR / "photo_index.json"
    if not path.exists():
        print("  ERROR: photo_index.json not found")
        return 0

    with open(path) as f:
        data = json.load(f)

    face_to_photo = data.get("face_to_photo", {})
    if not face_to_photo:
        print("  No face_to_photo entries found")
        return 0

    # Try to load embeddings for det_score/quality
    import numpy as np

    emb_path = DATA_DIR / "embeddings.npy"
    emb_lookup = {}
    if emb_path.exists():
        embeddings = np.load(emb_path, allow_pickle=True)
        # Track per-filename face index for legacy ID generation
        filename_counts: dict[str, int] = {}
        for emb in embeddings:
            fid = emb.get("face_id")
            if not fid:
                fname = emb.get("filename", "")
                stem = Path(fname).stem
                idx = filename_counts.get(fname, 0)
                filename_counts[fname] = idx + 1
                fid = f"{stem}:face{idx}"
            emb_lookup[fid] = {
                "bbox": emb.get("bbox"),
                "det_score": float(emb.get("det_score", 0)),
                "quality": float(emb.get("quality", 0)),
            }

    if dry_run:
        print(f"  Would upsert {len(face_to_photo)} rows into photo_faces")
        print(f"  Embedding data available for {len(emb_lookup)} faces")
        return len(face_to_photo)

    cur = conn.cursor()
    count = 0
    for face_id, photo_id in face_to_photo.items():
        emb_data = emb_lookup.get(face_id, {})
        bbox = emb_data.get("bbox")
        if bbox is not None and not isinstance(bbox, str):
            bbox = json.dumps([float(x) for x in bbox])
        elif isinstance(bbox, str):
            bbox = json.dumps(bbox)
        else:
            bbox = None

        cur.execute(
            """
            INSERT INTO photo_faces (face_id, photo_id, bbox, det_score, quality)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (face_id) DO UPDATE SET
                photo_id = EXCLUDED.photo_id,
                bbox = EXCLUDED.bbox,
                det_score = EXCLUDED.det_score,
                quality = EXCLUDED.quality
            """,
            (
                face_id,
                photo_id,
                bbox,
                emb_data.get("det_score"),
                emb_data.get("quality"),
            ),
        )
        count += 1
        if verbose and count <= 10:
            print(f"    face: {face_id} -> {photo_id}")

    conn.commit()
    return count


def verify_counts(conn):
    """Verify row counts match source data."""
    cur = conn.cursor()

    with open(DATA_DIR / "identities.json") as f:
        id_count = len(json.load(f).get("identities", {}))

    with open(DATA_DIR / "photo_index.json") as f:
        data = json.load(f)
        photo_count = len(data.get("photos", {}))
        face_count = len(data.get("face_to_photo", {}))

    cur.execute("SELECT COUNT(*) FROM identities")
    db_identities = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM photos")
    db_photos = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM photo_faces")
    db_faces = cur.fetchone()[0]

    print("\nVERIFICATION:")
    print(f"  identities: JSON={id_count}, DB={db_identities} {'✓' if id_count == db_identities else '✗ MISMATCH'}")
    print(f"  photos:     JSON={photo_count}, DB={db_photos} {'✓' if photo_count == db_photos else '✗ MISMATCH'}")
    print(f"  faces:      JSON={face_count}, DB={db_faces} {'✓' if face_count == db_faces else '✗ MISMATCH'}")

    return id_count == db_identities and photo_count == db_photos and face_count == db_faces


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Migrate core tables to Supabase")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    print(f"{'DRY RUN — ' if args.dry_run else ''}Core Tables Migration (DATA-007)")
    print(f"Data directory: {DATA_DIR}")
    print("=" * 60)

    conn = None
    if not args.dry_run:
        conn = get_connection()
        print("Connected to Supabase Postgres")
        ensure_tables(conn)

    summary = {}

    # Must migrate photos BEFORE photo_faces (FK constraint)
    migrations = [
        ("identities", migrate_identities),
        ("photos", migrate_photos),
        ("photo_faces", migrate_photo_faces),
    ]

    total = 0
    for name, fn in migrations:
        print(f"\n[{name}]")
        try:
            count = fn(conn, args.dry_run, args.verbose)
            summary[name] = count
            total += count
            print(f"  -> {count} rows {'would be migrated' if args.dry_run else 'migrated'}")
        except Exception as e:
            summary[name] = f"ERROR: {e}"
            print(f"  -> ERROR: {e}")
            import traceback

            traceback.print_exc()
            if conn:
                conn.rollback()

    if conn and not args.dry_run:
        all_ok = verify_counts(conn)
        conn.close()
        if not all_ok:
            print("\n⚠ Count mismatch detected — investigate before flipping DATA_SOURCE")
            sys.exit(1)

    print("\n" + "=" * 60)
    print("MIGRATION SUMMARY")
    for name, result in summary.items():
        status = f"{result} rows" if isinstance(result, int) else result
        print(f"  {name:20s} {status}")
    print(f"  {'TOTAL':20s} {total} rows")
    print("=" * 60)

    if args.dry_run:
        print("\nDry run complete. Run without --dry-run to execute.")


if __name__ == "__main__":
    main()
