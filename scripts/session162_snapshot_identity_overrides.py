"""Session 162 — Snapshot identity_overrides to R2 before DROP.

Defensive backup. Table is known empty as of 2026-05-22 but the snapshot
preserves schema + (any) rows + a timestamp for forensic recovery.

Writes ``r2://<R2_BUCKET_NAME>/backups/session162/identity_overrides_snapshot.json.gz``.

Run from repo root: ``python scripts/session162_snapshot_identity_overrides.py``
"""

from __future__ import annotations

import gzip
import io
import json
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()


def main() -> int:
    import boto3  # noqa: F401 — picked up at runtime; not in core deps
    import psycopg2  # type: ignore

    project_ref = "fvynibivlphxwfowzkjl"
    conn = psycopg2.connect(
        host="aws-0-us-west-2.pooler.supabase.com",
        port=5432,
        dbname="postgres",
        user=f"postgres.{project_ref}",
        password=os.environ["SUPABASE_DB_PASSWORD"],
        connect_timeout=10,
        sslmode="require",
    )
    conn.autocommit = True
    cur = conn.cursor()

    # Capture schema
    cur.execute(
        """SELECT column_name, data_type, is_nullable, column_default
           FROM information_schema.columns
          WHERE table_schema='public' AND table_name='identity_overrides'
          ORDER BY ordinal_position"""
    )
    schema = [
        {"column": r[0], "type": r[1], "nullable": r[2], "default": r[3]}
        for r in cur.fetchall()
    ]

    # Capture indexes
    cur.execute(
        "SELECT indexname, indexdef FROM pg_indexes "
        "WHERE schemaname='public' AND tablename='identity_overrides' "
        "ORDER BY indexname"
    )
    indexes = [{"name": r[0], "def": r[1]} for r in cur.fetchall()]

    # Capture rows (expected: 0)
    cur.execute("SELECT * FROM identity_overrides")
    cols = [d[0] for d in cur.description]
    rows = [
        {c: (v.isoformat() if hasattr(v, "isoformat") else v) for c, v in zip(cols, row)}
        for row in cur.fetchall()
    ]

    snapshot = {
        "session": "162",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "database": "rhodesli",
        "project_ref": project_ref,
        "table": "identity_overrides",
        "row_count": len(rows),
        "schema": schema,
        "indexes": indexes,
        "rows": rows,
    }

    payload = json.dumps(snapshot, indent=2).encode("utf-8")
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
        gz.write(payload)
    compressed = buf.getvalue()

    bucket = os.environ.get("R2_BUCKET_NAME")
    if not bucket:
        sys.exit("ERROR: R2_BUCKET_NAME not set")

    import boto3  # type: ignore

    s3 = boto3.client(
        "s3",
        endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )

    key = "backups/session162/identity_overrides_snapshot.json.gz"
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=compressed,
        ContentType="application/json",
        ContentEncoding="gzip",
    )

    print("=== Session 162 — identity_overrides R2 snapshot ===")
    print(f"  bucket: {bucket}")
    print(f"  key: {key}")
    print(f"  size: {len(compressed):,} bytes (gz) / {len(payload):,} bytes (raw)")
    print(f"  rows: {len(rows)}")
    print(f"  captured_at: {snapshot['captured_at']}")
    print("  status: OK")
    cur.close()
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
