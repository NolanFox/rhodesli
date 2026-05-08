"""Session 156 Track B2 — R2 backup GEDCOM .ged source files.

Per PRD-063 Operational guardrails: archive .ged source files to R2 before
any structural change to the Supabase mirror. Provides the FINAL fallback
restoration path (re-import from .ged) if R2 archives + reversibility test
both fail.

Usage:
    python scripts/session156_r2_backup_gedcom_sources.py SOURCE_DIR
    python scripts/session156_r2_backup_gedcom_sources.py ~/Downloads/gedcom_20260508/

Defaults to dry-run; pass --execute to actually upload.

R2 path: rhodesli-archive/gedcom-source-snapshots/2026-05-08-session-156/
Manifest: .../manifest.json with SHA256 checksums + sizes for each .ged file.
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def get_r2_client():
    import boto3
    account_id = os.environ["R2_ACCOUNT_ID"]
    return boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
    )


def sha256_file(path: Path, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            data = f.read(chunk)
            if not data:
                break
            h.update(data)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source_dir", help="Directory containing .ged files")
    parser.add_argument("--execute", action="store_true", help="Actually upload")
    parser.add_argument(
        "--bucket",
        default=os.environ.get("R2_BUCKET_NAME", "rhodesli-archive"),
        help="R2 bucket name",
    )
    parser.add_argument(
        "--prefix",
        default=f"gedcom-source-snapshots/2026-05-08-session-156",
        help="R2 key prefix",
    )
    args = parser.parse_args()

    source = Path(args.source_dir).expanduser()
    if not source.is_dir():
        print(f"ERROR: source_dir is not a directory: {source}", file=sys.stderr)
        sys.exit(1)

    ged_files = sorted(source.rglob("*.ged"))
    if not ged_files:
        print(f"WARN: no .ged files in {source}", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(ged_files)} .ged file(s) in {source}")
    print(f"Bucket: {args.bucket}")
    print(f"Prefix: {args.prefix}")
    print()

    manifest = {
        "_meta": {
            "session": 156,
            "track": "B2",
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "source_dir": str(source),
            "bucket": args.bucket,
            "prefix": args.prefix,
            "purpose": "PRD-063 operational guardrail: .ged source archive before v2 schema cutover",
        },
        "files": [],
    }

    client = None if not args.execute else get_r2_client()

    for ged in ged_files:
        size = ged.stat().st_size
        digest = sha256_file(ged)
        # R2 key: <prefix>/<basename>-<sha8>.ged
        sha8 = digest[:8]
        # Sanitize filename — replace spaces with underscores
        safe_name = ged.stem.replace(" ", "_") + f"-{sha8}.ged"
        r2_key = f"{args.prefix}/{safe_name}"

        manifest["files"].append({
            "local_path": str(ged),
            "size_bytes": size,
            "sha256": digest,
            "r2_key": r2_key,
            "uploaded": False,
        })

        print(f"  {ged.name}")
        print(f"    size: {size / (1024*1024):.2f} MB")
        print(f"    sha256: {digest[:16]}...")
        print(f"    r2_key: {r2_key}")

        if args.execute:
            with open(ged, "rb") as f:
                client.put_object(
                    Bucket=args.bucket,
                    Key=r2_key,
                    Body=f,
                    ContentType="text/plain",
                    Metadata={
                        "sha256": digest,
                        "session": "156",
                        "track": "B2",
                    },
                )
            print(f"    ✓ uploaded")
            manifest["files"][-1]["uploaded"] = True
        else:
            print(f"    [DRY-RUN]")
        print()

    # Roundtrip verify on first file (download head + checksum check)
    if args.execute and manifest["files"]:
        first = manifest["files"][0]
        print(f"Roundtrip verify: {first['r2_key']}")
        head = client.head_object(Bucket=args.bucket, Key=first["r2_key"])
        assert head["ContentLength"] == first["size_bytes"], "size mismatch"
        # Download and compare hash
        obj = client.get_object(Bucket=args.bucket, Key=first["r2_key"])
        body = obj["Body"].read()
        rt_digest = hashlib.sha256(body).hexdigest()
        assert rt_digest == first["sha256"], f"sha256 mismatch on roundtrip: {rt_digest} vs {first['sha256']}"
        print(f"  ✓ size matches, sha256 matches")
        manifest["_meta"]["roundtrip_verified"] = first["r2_key"]

    # Upload manifest
    manifest_key = f"{args.prefix}/manifest.json"
    manifest_bytes = json.dumps(manifest, indent=2).encode("utf-8")
    if args.execute:
        client.put_object(
            Bucket=args.bucket,
            Key=manifest_key,
            Body=manifest_bytes,
            ContentType="application/json",
        )
        print(f"\n✓ Uploaded manifest to {manifest_key}")
    else:
        print(f"\n[DRY-RUN] would upload manifest to {manifest_key}")

    # Also write manifest locally for commit
    local_manifest = Path("backups/session-156/r2-source-manifest.json")
    local_manifest.parent.mkdir(parents=True, exist_ok=True)
    local_manifest.write_text(json.dumps(manifest, indent=2))
    print(f"Local manifest: {local_manifest}")


if __name__ == "__main__":
    main()
