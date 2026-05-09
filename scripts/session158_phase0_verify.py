"""Phase 158-0 carry verification — v2/v1 row counts, Harry/Belle Isle intact, R2 readable.

Replaces 5 inline python -c blocks from the prompt with a single auditable script.
"""
import os
import sys

import boto3
from dotenv import load_dotenv

load_dotenv()

from app.supabase_data import get_supabase_client


def check(label, value, expected, tolerance=0):
    """Assert value matches expected (with optional tolerance for >=)."""
    if tolerance:
        ok = value >= expected
    else:
        ok = value == expected
    marker = "OK " if ok else "FAIL"
    print(f"  [{marker}] {label}: {value} (expected: {'>=' if tolerance else '=='}{expected})")
    return ok


def main():
    sb = get_supabase_client()
    failures = []

    print("=== 1. v2 row counts (must match 157b end) ===")
    v2_counts = {}
    for t, expected in [
        ("gedcom_individuals_v2", 21998),
        ("gedcom_families_v2", 6741),
        ("gedcom_change_manifest", 9),
    ]:
        r = sb.table(t).select("*", count="exact").limit(1).execute()
        v2_counts[t] = r.count
        # Allow >= because a concurrent session may have imported between 157b and 158
        if not check(t, r.count, expected, tolerance=1):
            failures.append(f"{t} count below 157b baseline")

    print()
    print("=== 2. v1 still intact ===")
    v1_counts = {}
    for t in ["gedcom_individuals", "gedcom_families"]:
        total = sb.table(t).select("*", count="exact").limit(1).execute().count
        current = sb.table(t).select("*", count="exact").eq("is_current", True).limit(1).execute().count
        v1_counts[t] = (total, current)
        print(f"  [INFO] {t}: total={total}, is_current=TRUE={current}, historical={total - current}")

    print()
    print("=== 3. Harry Fox + Belle Isle intact ===")
    h = sb.table("identities").select("anchor_ids,version_id").eq(
        "identity_id", "d74cb556-6d44-4288-ade3-1cc8fa2b45a6"
    ).execute().data
    if not h:
        failures.append("Harry Fox identity not found")
    else:
        h = h[0]
        h_anchors = len(h.get("anchor_ids", []) or [])
        h_ver = h.get("version_id")
        ok_h = check("Harry anchors", h_anchors, 5)
        ok_h_ver = check("Harry version_id", h_ver, 14, tolerance=1)
        if not (ok_h and ok_h_ver):
            failures.append("Harry repair state diverged")

    n = sb.table("identities").select("name,state,metadata").eq(
        "identity_id", "ef39908e-283a-4cec-8f72-3ec83bc8d84f"
    ).execute().data
    if not n:
        failures.append("Belle Isle identity not found")
    else:
        n = n[0]
        ok_name = check("Belle Isle name contains 'Belle Isle'", "Belle Isle" in (n.get("name") or ""), True)
        ok_state = check("Belle Isle state", n.get("state"), "INBOX")
        meta = n.get("metadata") or {}
        ok_notes = check("Belle Isle has notes in metadata", bool(meta.get("notes")), True)
        if not (ok_name and ok_state and ok_notes):
            failures.append("Belle Isle state diverged")

    print()
    print("=== 4. R2 archive readability (CRITICAL gate) ===")
    s3 = boto3.client(
        "s3",
        endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
    )
    bucket = "rhodesli-photos"
    prefix = "gedcom-version-snapshots/2026-05-08-session-156/"

    paginator = s3.get_paginator("list_objects_v2")
    contents = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        contents.extend(page.get("Contents", []))

    print(f"  [INFO] R2 archive at {prefix}: {len(contents)} files")
    if not contents:
        failures.append("R2 archive is EMPTY — rollback path broken")
    else:
        total_bytes = sum(o["Size"] for o in contents)
        print(f"  [INFO] total bytes: {total_bytes:,}")
        v9_keys = [o["Key"] for o in contents if "v9/" in o["Key"]]
        if not v9_keys:
            failures.append("R2 archive has no v9/ files (latest version archive missing)")
        else:
            print(f"  [INFO] v9/ files: {len(v9_keys)}")
            for k in v9_keys[:3]:
                try:
                    head = s3.head_object(Bucket=bucket, Key=k)
                    print(f"  [OK ] {k}: {head['ContentLength']:,} bytes, etag={head['ETag']}")
                except Exception as e:
                    failures.append(f"R2 head_object failed for {k}: {e}")

    print()
    print("=== Summary ===")
    if failures:
        print("FAILURES:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("ALL OK — Phase 158-0 carry verification passed")
    sys.exit(0)


if __name__ == "__main__":
    main()
