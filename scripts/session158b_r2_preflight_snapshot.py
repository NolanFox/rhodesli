#!/usr/bin/env python3
"""
Session 158b Phase 158-3.1 — Fresh R2 snapshot of v1 GEDCOM tables.

Captures gedcom_individuals, gedcom_families, gedcom_change_log, and
gedcom_versions to gzipped JSONL files in R2 under prefix:
  gedcom-pre-drop-snapshots/<UTC-date>-session-158b/

Even though Session 156 R2 archive at
  gedcom-version-snapshots/2026-05-08-session-156/
is the canonical rollback, this fresh snapshot:
  1. Captures any 157b/158/158b changes (should be none, but verify)
  2. Provides a clean "minutes-ago" baseline immediately before DROP
  3. Doubles up on safety with two independent snapshots

For each upload, we compute SHA256 locally, upload to R2, then verify the
returned ETag matches (PostgREST/S3 ETag is MD5 for non-multipart, so we
also capture the local MD5 as the actual comparison against ETag).

Reads via REST .range() pagination — pooler is degraded today, so we
avoid psycopg2 server-side cursors.

Usage:
    python scripts/session158b_r2_preflight_snapshot.py --dry-run    # default
    python scripts/session158b_r2_preflight_snapshot.py --execute
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
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except Exception:
    pass

import boto3

from app.supabase_data import get_supabase_client

R2_BUCKET = os.environ.get("R2_BUCKET_NAME", "rhodesli-photos")
PAGE_SIZE = 1000

# Tables to snapshot. Order matters: smaller tables first so we discover
# REST or upload errors quickly without burning the big read.
TABLES = [
    ("gedcom_versions", None),       # tiny — no chunking needed
    ("gedcom_change_log", None),     # ~1.65M rows — heaviest read
    ("gedcom_families", None),       # 33,324 rows
    ("gedcom_individuals", None),    # 196,645 rows — biggest individual table
]


def _r2_client():
    return boto3.client(
        "s3",
        endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )


def _stream_table_to_jsonl_gz(sb, table: str) -> tuple[bytes, int, str, str]:
    """Read all rows via REST and stream-encode to gzipped JSONL bytes.

    Returns: (gz_bytes, row_count, sha256_hex, md5_hex)
    """
    buf = io.BytesIO()
    h_sha = hashlib.sha256()
    h_md5 = hashlib.md5()

    # Use gzip with mtime=0 for byte-stable archives
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as gz:
        offset = 0
        rows = 0
        while True:
            for retry in range(3):
                try:
                    resp = sb.table(table).select("*").range(offset, offset + PAGE_SIZE - 1).execute()
                    break
                except Exception as exc:
                    if retry == 2:
                        raise
                    print(f"    [{table}] retry {retry+1}: {exc.__class__.__name__}")
                    time.sleep(2)
            page = resp.data or []
            if not page:
                break
            for row in page:
                line = json.dumps(row, ensure_ascii=False, default=str, sort_keys=True).encode("utf-8") + b"\n"
                gz.write(line)
            rows += len(page)
            if rows % 10000 == 0:
                print(f"    [{table}] streamed {rows:,} rows...")
            if len(page) < PAGE_SIZE:
                break
            offset += PAGE_SIZE

    raw_bytes = buf.getvalue()
    h_sha.update(raw_bytes)
    h_md5.update(raw_bytes)
    return raw_bytes, rows, h_sha.hexdigest(), h_md5.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    dry_run = not args.execute

    print(f"Session 158b Phase 158-3.1 — R2 preflight snapshot (Mode: {'DRY-RUN' if dry_run else 'EXECUTE'})")
    print(f"  Time: {dt.datetime.utcnow().isoformat()}Z")

    sb = get_supabase_client()
    if not sb:
        sys.exit("ERROR: Supabase client unavailable")

    date = dt.datetime.utcnow().strftime("%Y-%m-%d")
    prefix = f"gedcom-pre-drop-snapshots/{date}-session-158b/"

    if not dry_run:
        s3 = _r2_client()

    manifest = {"prefix": prefix, "files": [], "started": dt.datetime.utcnow().isoformat() + "Z"}

    for (table, _opts) in TABLES:
        print(f"\n=== {table} ===")
        t0 = time.time()
        gz_bytes, rows, sha, md5 = _stream_table_to_jsonl_gz(sb, table)
        elapsed = time.time() - t0
        print(f"  rows={rows:,}, gz_size={len(gz_bytes):,} bytes, sha256={sha[:12]}..., md5={md5[:12]}...")
        print(f"  encoded in {elapsed:.1f}s")

        key = f"{prefix}{table}.jsonl.gz"
        if dry_run:
            print(f"  [DRY-RUN] would upload {len(gz_bytes):,} bytes to s3://{R2_BUCKET}/{key}")
            manifest["files"].append({
                "table": table, "key": key, "rows": rows,
                "size_bytes": len(gz_bytes), "sha256": sha, "md5": md5,
                "uploaded": False,
            })
            continue

        # Upload
        s3.put_object(Bucket=R2_BUCKET, Key=key, Body=gz_bytes)
        head = s3.head_object(Bucket=R2_BUCKET, Key=key)
        etag = head["ETag"].strip('"')
        match = etag == md5
        marker = "OK" if match else "MISMATCH"
        print(f"  [{marker}] uploaded etag={etag} (md5={md5})")

        manifest["files"].append({
            "table": table, "key": key, "rows": rows,
            "size_bytes": len(gz_bytes), "sha256": sha, "md5": md5,
            "etag": etag, "etag_md5_match": match, "uploaded": True,
        })

    manifest["finished"] = dt.datetime.utcnow().isoformat() + "Z"

    report_path = PROJECT_ROOT / "docs" / "feedback" / "session-158b-r2-preflight-manifest.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        f"# Session 158b Phase 158-3.1 — R2 Preflight Snapshot Manifest\n\n"
        f"**Date**: {manifest['finished']}\n"
        f"**Mode**: {'DRY-RUN' if dry_run else 'EXECUTE'}\n"
        f"**R2 Prefix**: `{prefix}`\n\n"
        f"## Files\n```json\n{json.dumps(manifest['files'], indent=2)}\n```\n"
    )
    print(f"\nManifest: {report_path}")

    if not dry_run:
        all_match = all(f["etag_md5_match"] for f in manifest["files"])
        if not all_match:
            sys.exit("ERROR: ETag mismatch on at least one file — investigate")
        print("\nALL UPLOADS VERIFIED — etag matches md5 for every file")


if __name__ == "__main__":
    main()
