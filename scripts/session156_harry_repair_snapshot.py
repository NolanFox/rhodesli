"""Session 156 Track A2 — Pre-repair snapshot of Harry Fox identity + downstream rows.

Writes backups/session-156/harry-fox-before-<UTC>.json with full state:
- Harry Fox identity record (all fields)
- All ml_proposals rows referencing Harry as source or target
- All photo_faces rows for the 2 face IDs being detached (F + G)
- All gedcom_face_links rows referencing Harry's identity_id
- All audit_log rows referencing Harry's identity_id (last 30 days)

Includes embedded SHA256 + restore command in the _meta field.

Read-only — does not mutate any production data.
"""
import json
import hashlib
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Add project root for imports
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from app.supabase_data import get_supabase_client  # noqa: E402

HARRY_ID = "d74cb556-6d44-4288-ade3-1cc8fa2b45a6"
FACE_F = "inbox_1fea75ce2caf"  # photo 01659 Belle Isle
FACE_G = "inbox_e507a54f204a"  # photo 02068 Detroit


def main():
    sb = get_supabase_client()
    if sb is None:
        print("ERROR: Supabase client unavailable", file=sys.stderr)
        sys.exit(1)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    snapshot = {
        "_meta": {
            "session": 156,
            "track": "A2",
            "purpose": "Pre-repair snapshot of Harry Fox identity for option (c) repair",
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "harry_identity_id": HARRY_ID,
            "face_ids_to_detach": [FACE_F, FACE_G],
            "captured_by": "session-156",
            "schema_version": 1,
        },
        "harry_identity": None,
        "ml_proposals_referencing_harry": [],
        "photo_faces_F_G": [],
        "gedcom_face_links_referencing_harry": [],
        "audit_log_recent_harry": [],
    }

    # 1. Harry Fox identity
    r = sb.table("identities").select("*").eq("identity_id", HARRY_ID).execute()
    if not r.data:
        print(f"ERROR: Harry Fox identity {HARRY_ID} not found in Supabase", file=sys.stderr)
        sys.exit(1)
    snapshot["harry_identity"] = r.data[0]

    # 2. ml_proposals referencing Harry as source or target
    src = sb.table("ml_proposals").select("*").eq("source_identity_id", HARRY_ID).execute()
    tgt = sb.table("ml_proposals").select("*").eq("target_identity_id", HARRY_ID).execute()
    seen = set()
    proposals = []
    for row in (src.data or []) + (tgt.data or []):
        pid = row.get("proposal_id")
        if pid not in seen:
            seen.add(pid)
            proposals.append(row)
    snapshot["ml_proposals_referencing_harry"] = proposals

    # 3. photo_faces rows for F + G (essential for restoring face ownership)
    pf = sb.table("photo_faces").select("*").in_("face_id", [FACE_F, FACE_G]).execute()
    snapshot["photo_faces_F_G"] = pf.data or []

    # 4. gedcom_face_links rows referencing Harry
    gfl = sb.table("gedcom_face_links").select("*").eq("identity_id", HARRY_ID).execute()
    snapshot["gedcom_face_links_referencing_harry"] = gfl.data or []

    # 5. recent audit_log entries referencing Harry (last 30 days, capped)
    al = (
        sb.table("audit_log")
        .select("*")
        .eq("entity_id", HARRY_ID)
        .order("created_at", desc=True)
        .limit(50)
        .execute()
    )
    snapshot["audit_log_recent_harry"] = al.data or []

    # Compute SHA256 of payload (excluding _meta.sha256_self)
    payload_for_hash = {k: v for k, v in snapshot.items() if k != "_meta"}
    payload_bytes = json.dumps(payload_for_hash, sort_keys=True, default=str).encode("utf-8")
    snapshot["_meta"]["payload_sha256"] = hashlib.sha256(payload_bytes).hexdigest()

    out_path = Path(f"backups/session-156/harry-fox-before-{ts}.json")
    snapshot["_meta"]["restore_command"] = (
        f"python scripts/session156_harry_repair_restore.py {out_path}"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(snapshot, indent=2, default=str))

    # Summary
    print(f"Snapshot written: {out_path}")
    print(f"  payload SHA256: {snapshot['_meta']['payload_sha256']}")
    print(f"  Harry anchor count: {len(snapshot['harry_identity']['anchor_ids'] or [])}")
    print(f"  Harry version_id: {snapshot['harry_identity']['version_id']}")
    print(f"  ml_proposals referencing Harry: {len(snapshot['ml_proposals_referencing_harry'])}")
    print(f"  photo_faces for F+G: {len(snapshot['photo_faces_F_G'])}")
    print(f"  gedcom_face_links: {len(snapshot['gedcom_face_links_referencing_harry'])}")
    print(f"  audit_log recent: {len(snapshot['audit_log_recent_harry'])}")
    print(f"  size: {out_path.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
