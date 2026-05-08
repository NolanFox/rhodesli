#!/usr/bin/env python3
"""
Session 156 — Track B3: R2 backup of current Supabase versioned GEDCOM data.

PRD-063 §6 Step 1: Archive every existing gedcom_versions row (incl.
is_current=FALSE history) to R2 as gzipped JSONL before any v2 schema work.

Per concurrency rule R3: this is READ-ONLY on v1 tables. Snapshot reflects
query-time state. Documents the timestamp range in the manifest.

Per Lesson 173: uses psycopg2 directly via Supabase pooler (NOT the REST
client) for tables with 200K-1.6M rows — REST paginates 1000 rows at a time
and the dump would be intolerably slow.

Per Lesson 175: connects via aws-0-us-west-2.pooler.supabase.com:6543
(direct hostname db.<project>.supabase.co is IPv6-only and unreachable from
many networks).

R2 layout (per concurrency rule R8):
    r2://<bucket>/gedcom-version-snapshots/2026-05-08-session-156/v<N>/<table>.jsonl.gz
    r2://<bucket>/gedcom-version-snapshots/2026-05-08-session-156/v<N>/manifest.json

Tables snapshotted per version: gedcom_individuals, gedcom_records,
gedcom_events, gedcom_relationships, gedcom_change_log, gedcom_families.

Usage:
    python scripts/session156_r2_backup_supabase_versions.py --dry-run
    python scripts/session156_r2_backup_supabase_versions.py --execute
    python scripts/session156_r2_backup_supabase_versions.py --execute --reversibility-test
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import io
import json
import os
import sys
import time
import uuid
from pathlib import Path

# Project root for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Load .env (Lesson: feedback_supabase_local_access)
try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
except Exception:
    pass


# Snapshot date prefix per concurrency rule R8 (today is 2026-05-07 / 08 UTC at script run time)
SNAPSHOT_DATE = "2026-05-08-session-156"
R2_PREFIX = f"gedcom-version-snapshots/{SNAPSHOT_DATE}"

# Tables to snapshot per version (all have version_id FK to gedcom_versions.id)
CHILD_TABLES = [
    "gedcom_individuals",
    "gedcom_records",
    "gedcom_events",
    "gedcom_relationships",
    "gedcom_change_log",
    "gedcom_families",
]

# Pooler config per Lesson 175
POOLER_HOST = "aws-0-us-west-2.pooler.supabase.com"
POOLER_PORT = 6543
SUPABASE_PROJECT_REF = "fvynibivlphxwfowzkjl"
POOLER_USER = f"postgres.{SUPABASE_PROJECT_REF}"


def get_pg_conn():
    """Return a live psycopg2 connection via Supabase pooler."""
    import psycopg2

    password = os.environ.get("SUPABASE_DB_PASSWORD")
    if not password:
        sys.exit("ERROR: SUPABASE_DB_PASSWORD not set in env")

    return psycopg2.connect(
        host=POOLER_HOST,
        port=POOLER_PORT,
        user=POOLER_USER,
        password=password,
        database="postgres",
        connect_timeout=30,
    )


def get_r2_client():
    """Return boto3 S3 client configured for R2."""
    import boto3

    account_id = os.environ.get("R2_ACCOUNT_ID")
    access_key = os.environ.get("R2_ACCESS_KEY_ID")
    secret_key = os.environ.get("R2_SECRET_ACCESS_KEY")
    bucket = os.environ.get("R2_BUCKET_NAME")

    missing = [
        n
        for n, v in [
            ("R2_ACCOUNT_ID", account_id),
            ("R2_ACCESS_KEY_ID", access_key),
            ("R2_SECRET_ACCESS_KEY", secret_key),
            ("R2_BUCKET_NAME", bucket),
        ]
        if not v
    ]
    if missing:
        sys.exit(f"ERROR: missing R2 env vars: {missing}")

    endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"
    client = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )
    return client, bucket


def list_versions(conn) -> list[dict]:
    """Return all gedcom_versions rows."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, version_number, community_id, imported_at, status,
               individual_count, family_count, source_file, source_hash
        FROM gedcom_versions
        ORDER BY version_number ASC
        """
    )
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    cur.close()
    return rows


def count_table_for_version(conn, table: str, version_uuid: str) -> int:
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {table} WHERE version_id = %s", (version_uuid,))
    n = cur.fetchone()[0]
    cur.close()
    return n


def _json_default(o):
    """JSON encoder for datetime, UUID, Decimal."""
    if isinstance(o, (dt.datetime, dt.date)):
        return o.isoformat()
    if isinstance(o, uuid.UUID):
        return str(o)
    try:
        from decimal import Decimal

        if isinstance(o, Decimal):
            return float(o)
    except Exception:
        pass
    if isinstance(o, (bytes, memoryview)):
        return o.hex() if isinstance(o, bytes) else o.tobytes().hex()
    raise TypeError(f"Cannot JSON-encode {type(o).__name__}")


def stream_table_to_jsonl_gz(
    conn, table: str, version_uuid: str, out_path: Path, batch_size: int = 5000
) -> tuple[int, str]:
    """
    Stream rows from `table` filtered by version_id to gzipped JSONL.
    Returns (row_count, sha256_hex).
    """
    sha = hashlib.sha256()

    # First, get column names via a regular cursor (named cursors don't expose
    # description until first fetchmany; safer to grab columns separately)
    col_cur = conn.cursor()
    col_cur.execute(f"SELECT * FROM {table} LIMIT 0")
    cols = [d[0] for d in col_cur.description]
    col_cur.close()

    # Server-side cursor — psycopg2 streams rows
    cur_name = f"dump_{table}_{uuid.uuid4().hex[:8]}"
    cur = conn.cursor(name=cur_name)
    cur.itersize = batch_size

    cur.execute(f"SELECT * FROM {table} WHERE version_id = %s", (version_uuid,))

    row_count = 0
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(out_path, "wt", encoding="utf-8", compresslevel=6) as gz:
        while True:
            batch = cur.fetchmany(batch_size)
            if not batch:
                break
            for r in batch:
                obj = dict(zip(cols, r))
                line = json.dumps(obj, default=_json_default, separators=(",", ":")) + "\n"
                gz.write(line)
                sha.update(line.encode("utf-8"))
                row_count += 1
    cur.close()
    return row_count, sha.hexdigest()


def upload_file_to_r2(client, bucket: str, key: str, local_path: Path):
    """Upload local file to R2."""
    client.upload_file(str(local_path), bucket, key)


def upload_bytes_to_r2(client, bucket: str, key: str, data: bytes, content_type="application/json"):
    client.put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type)


def reversibility_test_one_version(
    conn, client, bucket: str, version_uuid: str, version_number: int
) -> dict:
    """
    Download one version snapshot from R2, restore gedcom_individuals rows
    into a TEST table, verify count matches, then drop the test table.

    Returns dict with test outcome.
    """
    import psycopg2.extras

    test_table = f"gedcom_individuals_v1_restore_test_{version_number}"

    # Download from R2
    r2_key = f"{R2_PREFIX}/v{version_number}/gedcom_individuals.jsonl.gz"
    print(f"  [reversibility] downloading {r2_key}")
    obj = client.get_object(Bucket=bucket, Key=r2_key)
    body = obj["Body"].read()

    # Decompress in memory
    decompressed = gzip.decompress(body)
    sha = hashlib.sha256(decompressed).hexdigest()

    # Count lines
    line_count = decompressed.count(b"\n")
    if decompressed and not decompressed.endswith(b"\n"):
        line_count += 1

    # Build a minimal test table — just id + gedcom_id + version_id, the
    # signal we need for "row count parity"
    cur = conn.cursor()
    cur.execute(f"DROP TABLE IF EXISTS {test_table}")
    cur.execute(
        f"""
        CREATE TABLE {test_table} (
            id UUID,
            gedcom_id TEXT,
            version_id UUID,
            payload_hash TEXT
        )
        """
    )

    # Stream-insert rows from the JSONL
    inserted = 0
    insert_sql = f"INSERT INTO {test_table} (id, gedcom_id, version_id, payload_hash) VALUES %s"
    batch = []
    for line in decompressed.splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        batch.append(
            (
                rec.get("id"),
                rec.get("gedcom_id"),
                rec.get("version_id"),
                rec.get("payload_hash"),
            )
        )
        if len(batch) >= 5000:
            psycopg2.extras.execute_values(cur, insert_sql, batch)
            inserted += len(batch)
            batch.clear()
    if batch:
        psycopg2.extras.execute_values(cur, insert_sql, batch)
        inserted += len(batch)

    conn.commit()

    # Compare to live count
    live_count = count_table_for_version(conn, "gedcom_individuals", version_uuid)

    # Drop test table
    cur.execute(f"DROP TABLE {test_table}")
    conn.commit()
    cur.close()

    return {
        "version_number": version_number,
        "r2_key": r2_key,
        "decompressed_sha256": sha,
        "lines_in_archive": line_count,
        "rows_inserted_into_test_table": inserted,
        "live_count_in_v1_table": live_count,
        "parity": inserted == live_count,
    }


def backup_one_version(
    conn, client, bucket: str, version_row: dict, dry_run: bool, work_dir: Path
) -> dict:
    """Backup all child tables for one version. Returns per-version manifest dict."""
    version_uuid = str(version_row["id"])
    version_number = version_row["version_number"]
    version_dir = work_dir / f"v{version_number}"
    version_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "session_id": "156",
        "snapshot_date_utc": SNAPSHOT_DATE,
        "version_uuid": version_uuid,
        "version_number": version_number,
        "version_status": version_row.get("status"),
        "version_imported_at": _json_default(version_row["imported_at"])
        if version_row.get("imported_at")
        else None,
        "snapshot_started_utc": dt.datetime.utcnow().isoformat() + "Z",
        "tables": {},
    }

    for table in CHILD_TABLES:
        live_count = count_table_for_version(conn, table, version_uuid)
        if live_count == 0:
            print(f"  v{version_number} {table}: 0 rows — skipping")
            manifest["tables"][table] = {
                "row_count": 0,
                "skipped_empty": True,
            }
            continue

        local_path = version_dir / f"{table}.jsonl.gz"
        r2_key = f"{R2_PREFIX}/v{version_number}/{table}.jsonl.gz"

        if dry_run:
            print(
                f"  [DRY-RUN] v{version_number} {table}: would dump {live_count} rows -> {r2_key}"
            )
            manifest["tables"][table] = {
                "row_count": live_count,
                "dry_run": True,
                "r2_key": r2_key,
            }
            continue

        t0 = time.time()
        print(f"  v{version_number} {table}: dumping {live_count} rows...")
        row_count, sha = stream_table_to_jsonl_gz(conn, table, version_uuid, local_path)
        size_bytes = local_path.stat().st_size
        elapsed = time.time() - t0
        print(
            f"    dumped {row_count} rows -> {local_path.name} "
            f"({size_bytes / 1024 / 1024:.1f} MB, sha256={sha[:12]}..., {elapsed:.1f}s)"
        )

        # Upload to R2
        t1 = time.time()
        upload_file_to_r2(client, bucket, r2_key, local_path)
        upload_elapsed = time.time() - t1
        print(f"    uploaded to r2://{bucket}/{r2_key} ({upload_elapsed:.1f}s)")

        manifest["tables"][table] = {
            "row_count": row_count,
            "sha256": sha,
            "size_bytes": size_bytes,
            "r2_key": r2_key,
            "dump_seconds": round(elapsed, 2),
            "upload_seconds": round(upload_elapsed, 2),
        }

    manifest["snapshot_completed_utc"] = dt.datetime.utcnow().isoformat() + "Z"

    # Write per-version manifest
    manifest_key = f"{R2_PREFIX}/v{version_number}/manifest.json"
    manifest_bytes = json.dumps(manifest, indent=2, default=_json_default).encode("utf-8")
    if not dry_run:
        upload_bytes_to_r2(client, bucket, manifest_key, manifest_bytes)
        # Also save locally for the commit
        local_manifest = version_dir / "manifest.json"
        local_manifest.write_bytes(manifest_bytes)
        print(f"  manifest -> r2://{bucket}/{manifest_key}")
    manifest["r2_manifest_key"] = manifest_key
    return manifest


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--dry-run", action="store_true", help="Print plan without uploading")
    ap.add_argument("--execute", action="store_true", help="Run the backup")
    ap.add_argument(
        "--reversibility-test",
        action="store_true",
        help="After backup, download smallest version's gedcom_individuals from R2 "
        "and restore into a test table. Compare row counts. Drop test table.",
    )
    ap.add_argument(
        "--work-dir",
        default=str(PROJECT_ROOT / "backups" / "session-156" / "r2-staging"),
        help="Local staging dir for gz files",
    )
    args = ap.parse_args()

    if not args.dry_run and not args.execute:
        ap.error("Must pass --dry-run or --execute")

    work_dir = Path(args.work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    print(f"Snapshot prefix: r2://<bucket>/{R2_PREFIX}/v<N>/<table>.jsonl.gz")
    print(f"Local staging: {work_dir}")
    print(f"Mode: {'EXECUTE' if args.execute else 'DRY-RUN'}")
    print()

    conn = get_pg_conn()
    print(f"Connected to Supabase pooler at {POOLER_HOST}:{POOLER_PORT}")

    versions = list_versions(conn)
    print(f"Found {len(versions)} gedcom_versions rows")
    for v in versions:
        print(
            f"  v{v['version_number']:<3}  status={v['status']:<10}  "
            f"individuals={v.get('individual_count', 0):>7}  "
            f"imported={v.get('imported_at')}"
        )
    print()

    if not args.dry_run:
        client, bucket = get_r2_client()
        print(f"R2 bucket: {bucket}")
    else:
        client, bucket = None, None

    overall = {
        "session_id": "156",
        "snapshot_date_utc": SNAPSHOT_DATE,
        "started_utc": dt.datetime.utcnow().isoformat() + "Z",
        "versions": [],
    }

    for v in versions:
        print(f"\n=== Version {v['version_number']} ({v['status']}) ===")
        m = backup_one_version(conn, client, bucket, v, args.dry_run, work_dir)
        overall["versions"].append(m)

    overall["completed_utc"] = dt.datetime.utcnow().isoformat() + "Z"

    # Save aggregate manifest locally + R2
    if not args.dry_run:
        agg_local = work_dir / "manifest.aggregate.json"
        agg_local.write_text(json.dumps(overall, indent=2, default=_json_default))
        agg_key = f"{R2_PREFIX}/manifest.aggregate.json"
        upload_bytes_to_r2(
            client, bucket, agg_key, agg_local.read_bytes(), content_type="application/json"
        )
        print(f"\nAggregate manifest -> r2://{bucket}/{agg_key}")
        print(f"                      {agg_local}")

    # Reversibility test
    if args.reversibility_test and not args.dry_run:
        # Pick smallest version with individuals — minimize test cost
        candidates = [
            v
            for v in versions
            if count_table_for_version(conn, "gedcom_individuals", str(v["id"])) > 0
        ]
        if not candidates:
            print("\nNo version has gedcom_individuals rows — skipping reversibility test")
        else:
            smallest = min(
                candidates,
                key=lambda v: count_table_for_version(conn, "gedcom_individuals", str(v["id"])),
            )
            print(
                f"\n=== Reversibility test on v{smallest['version_number']} "
                f"({smallest['status']}, smallest) ==="
            )
            result = reversibility_test_one_version(
                conn, client, bucket, str(smallest["id"]), smallest["version_number"]
            )
            print(f"  parity: {result['parity']}")
            print(f"  archive lines: {result['lines_in_archive']}")
            print(f"  rows restored: {result['rows_inserted_into_test_table']}")
            print(f"  live v1 count: {result['live_count_in_v1_table']}")

            # Save reversibility result to manifest
            overall["reversibility_test"] = result
            if not args.dry_run:
                agg_local = work_dir / "manifest.aggregate.json"
                agg_local.write_text(json.dumps(overall, indent=2, default=_json_default))
                agg_key = f"{R2_PREFIX}/manifest.aggregate.json"
                upload_bytes_to_r2(
                    client,
                    bucket,
                    agg_key,
                    agg_local.read_bytes(),
                    content_type="application/json",
                )

    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
