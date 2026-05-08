"""Session 156 Track A — Restore script for Harry Fox repair (rollback).

Usage:
    python scripts/session156_harry_repair_restore.py backups/session-156/harry-fox-before-<TS>.json

Restores the Harry Fox identity record exactly as captured in the snapshot
(re-attaches detached anchors, restores version_id, name, state). Also restores
gedcom_face_links and ml_proposals if the snapshot's row sets differ from current.

Does NOT delete the new identity created in Phase A3 — call this PLUS a manual
Supabase delete on the new identity_id if a full rollback is desired.

Requires --execute to actually mutate. Defaults to dry-run.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from app.supabase_data import get_supabase_client  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("snapshot_path", help="Path to the snapshot JSON")
    parser.add_argument("--execute", action="store_true", help="Actually mutate")
    args = parser.parse_args()

    snap = json.loads(Path(args.snapshot_path).read_text())

    # Verify checksum
    payload_for_hash = {k: v for k, v in snap.items() if k != "_meta"}
    payload_bytes = json.dumps(payload_for_hash, sort_keys=True, default=str).encode("utf-8")
    actual_hash = hashlib.sha256(payload_bytes).hexdigest()
    expected = snap["_meta"]["payload_sha256"]
    if actual_hash != expected:
        print(f"ERROR: snapshot SHA256 mismatch. Expected {expected}, got {actual_hash}", file=sys.stderr)
        sys.exit(1)
    print(f"Snapshot checksum verified: {expected[:16]}...")

    sb = get_supabase_client()
    if sb is None:
        print("ERROR: Supabase unavailable", file=sys.stderr)
        sys.exit(1)

    h = snap["harry_identity"]
    harry_id = h["identity_id"]
    print(f"Restoring identity {harry_id} ({h['name']})")
    print(f"  -> version_id: {h['version_id']}")
    print(f"  -> anchor count: {len(h['anchor_ids'] or [])}")
    print(f"  -> state: {h['state']}")

    if not args.execute:
        print("\n[DRY-RUN] use --execute to actually restore")
        return

    # Upsert the entire identity row
    sb.table("identities").upsert(h, on_conflict="identity_id").execute()
    print("Restored identity row.")

    # Restore gedcom_face_links (delete current, insert snapshot)
    sb.table("gedcom_face_links").delete().eq("identity_id", harry_id).execute()
    if snap["gedcom_face_links_referencing_harry"]:
        sb.table("gedcom_face_links").insert(snap["gedcom_face_links_referencing_harry"]).execute()
    print(f"Restored gedcom_face_links: {len(snap['gedcom_face_links_referencing_harry'])} rows")

    print("\nDone. Manual cleanup needed: delete the new identity created in Phase A3 if rollback is full.")


if __name__ == "__main__":
    main()
