"""Session 156 Track A — Execute Harry Fox repair (Phases A3 + A4).

IRREVERSIBLE on production Supabase. User-authorized 2026-05-07.

Steps:
1. Pre-flight: re-verify Harry Fox state matches snapshot (version_id, anchor count).
   If genealogy session edited Harry mid-156, STOP per R2 optimistic concurrency.
2. Detach face IDs F + G from Harry Fox (anchors 7 -> 5; bump version_id).
3. Create new identity "Belle Isle Conservatory Young Man c.1917-1918"
   (state=INBOX, anchors=[F, G], metadata.notes=[provenance_note]).
4. Insert gedcom_face_links row linking new identity -> Harry Isaackovitz
   (gedcom_id @I132506612777@, confidence=0.3 to mark as candidate).
5. Write audit_log entry with full provenance metadata.
6. Verify post-state.

Defaults to --dry-run. Pass --execute to actually mutate.
"""

import argparse
import hashlib
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from app.supabase_data import get_supabase_client  # noqa: E402

HARRY_ID = "d74cb556-6d44-4288-ade3-1cc8fa2b45a6"
FACE_F = "inbox_1fea75ce2caf"  # photo 01659
FACE_G = "inbox_e507a54f204a"  # photo 02068
NEW_IDENTITY_NAME = "Belle Isle Conservatory Young Man c.1917-1918"
GEDCOM_HARRY_ISAACKOVITZ_XREF = "@I132506612777@"

PROVENANCE_TEXT = (
    "Originally misidentified as Harry Fox in registry until 2026-05-08. "
    "Detached via Session 156 after triangulation across 4 sources confirmed "
    "these faces are NOT Harshel Iosha Fox (the actual person behind the 'Harry Fox' identity): "
    "(1) Local ML (Session 153): pairwise distance 1.36-1.43 vs 5 Harshel anchors — "
    "different-person territory. "
    "(2) Gemini 3.1 Pro multimodal (Session 153): blond+blue-eyed Harshel from "
    "naturalization photo vs dark+dark center-man + ear morphology = morphologically incompatible. "
    "(3) Codex audit (Session 153, gpt-5.4): 0.88 confidence 'NOT Harshel.' "
    "(4) Independent Codex audit (Session 153b, fresh context): same conclusion. "
    "Belle Isle Conservatory location verified via Library of Congress LC-DIG-det-4a17798 "
    "(Detroit Publishing Co. interior, 1905) + 6 corroborating sources. "
    "Date range c.1917-1918 from Albert Fox GEDCOM RESI Detroit 1917 + draft induction 7 Jun 1918. "
    "GEDCOM link: Harry Isaackovitz @I132506612777@ linked as candidate (NOT confirmed). "
    "No reference photo of Harry Isaackovitz exists; identification beyond "
    "'man at Belle Isle event' is not possible without further evidence "
    "(1910s Bessie reference photo OR third Belle Isle frame). "
    "Full evidence trail: Sessions 153, 153b, 154, 155, 156. See "
    "docs/feedback/session-153-detroit-deep-dive.md, "
    "docs/feedback/session-153b-bessie-validation.md, "
    "docs/feedback/session-153b-center-man-honest.md, "
    "docs/feedback/session-154-harry-face-id-resolution.md, "
    "docs/feedback/session-154-bessie-strengthening.md, "
    "docs/feedback/session-154-belle-isle-citation.md."
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="Actually mutate")
    parser.add_argument("--snapshot", required=True, help="Path to A2 snapshot")
    args = parser.parse_args()

    snap = json.loads(Path(args.snapshot).read_text())
    payload_for_hash = {k: v for k, v in snap.items() if k != "_meta"}
    payload_bytes = json.dumps(payload_for_hash, sort_keys=True, default=str).encode("utf-8")
    actual_hash = hashlib.sha256(payload_bytes).hexdigest()
    expected = snap["_meta"]["payload_sha256"]
    if actual_hash != expected:
        print(f"ABORT: snapshot SHA256 mismatch", file=sys.stderr)
        sys.exit(1)
    print(f"Snapshot verified: {expected[:16]}...")

    sb = get_supabase_client()
    if sb is None:
        print("ABORT: Supabase unavailable", file=sys.stderr)
        sys.exit(1)

    # === R6 pre-flight: verify Harry state matches snapshot ===
    r = sb.table("identities").select("*").eq("identity_id", HARRY_ID).execute()
    if not r.data:
        print(f"ABORT: Harry Fox not found", file=sys.stderr)
        sys.exit(1)
    current = r.data[0]
    snap_h = snap["harry_identity"]

    if current["version_id"] != snap_h["version_id"]:
        print(f"ABORT (R2 concurrency): version drift {snap_h['version_id']} -> {current['version_id']}", file=sys.stderr)
        print("Genealogy session may have edited Harry. Re-snapshot and restart Track A.", file=sys.stderr)
        sys.exit(1)

    current_anchors = set(current.get("anchor_ids") or [])
    if FACE_F not in current_anchors or FACE_G not in current_anchors:
        print(f"ABORT: F or G no longer in Harry's anchors", file=sys.stderr)
        sys.exit(1)

    if len(current_anchors) != 7:
        print(f"ABORT: expected 7 anchors, got {len(current_anchors)}", file=sys.stderr)
        sys.exit(1)
    print(f"Pre-flight PASS: version_id={current['version_id']}, anchors=7")

    # === Build new state ===
    new_harry_anchors = [a for a in (current.get("anchor_ids") or []) if a not in (FACE_F, FACE_G)]
    assert len(new_harry_anchors) == 5, f"Expected 5, got {len(new_harry_anchors)}"
    new_harry_version = current["version_id"] + 1
    now_iso = datetime.now(timezone.utc).isoformat()

    new_identity_id = str(uuid.uuid4())

    # Disambiguate name if a same-name identity exists (R2 collision check)
    name_check = sb.table("identities").select("identity_id").eq("name", NEW_IDENTITY_NAME).execute()
    new_name = NEW_IDENTITY_NAME
    if name_check.data:
        suffix = datetime.now(timezone.utc).strftime("-%H%M%S")
        new_name = NEW_IDENTITY_NAME + suffix
        print(f"Name collision detected; using disambiguated name: {new_name}")

    provenance_note = {
        "id": str(uuid.uuid4())[:8],
        "text": PROVENANCE_TEXT,
        "author": "session-156",
        "timestamp": now_iso,
    }

    new_identity_row = {
        "identity_id": new_identity_id,
        "name": new_name,
        "display_name": None,
        "state": "INBOX",
        "anchor_ids": [FACE_F, FACE_G],
        "candidate_ids": [],
        "negative_ids": [],
        "metadata": {
            "notes": [provenance_note],
            "originally_misidentified_as": "Harry Fox",
            "originally_misidentified_identity_id": HARRY_ID,
            "session_created": 156,
            "snapshot_path": args.snapshot,
        },
        "version_id": 1,
        "merged_into": None,
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    detached_harry_row = {
        "identity_id": HARRY_ID,
        "name": current.get("name", "Harry Fox"),
        "display_name": current.get("display_name"),
        "state": current.get("state", "CONFIRMED"),
        "anchor_ids": new_harry_anchors,
        "candidate_ids": current.get("candidate_ids") or [],
        "negative_ids": current.get("negative_ids") or [],
        "metadata": current.get("metadata") or {},
        "version_id": new_harry_version,
        "merged_into": current.get("merged_into"),
        "created_at": current.get("created_at"),
        "updated_at": now_iso,
        "primary_face_id": current.get("primary_face_id"),
    }

    audit_row = {
        "action": "identity_detach_replace",
        "entity_type": "identity",
        "entity_id": new_identity_id,
        "user_id": None,
        "user_email": "session-156",
        "old_value": json.dumps({
            "harry_anchor_ids_before": current.get("anchor_ids"),
            "harry_version_before": current["version_id"],
        }),
        "new_value": json.dumps({
            "new_identity_id": new_identity_id,
            "new_identity_name": new_name,
            "harry_anchor_ids_after": new_harry_anchors,
            "harry_version_after": new_harry_version,
        }),
        "metadata": {
            "originally_misidentified_as": "Harry Fox",
            "originally_misidentified_identity_id": HARRY_ID,
            "detached_face_ids": [FACE_F, FACE_G],
            "evidence_sessions": [153, "153b", 154, 155, 156],
            "triangulation_sources": [
                "local_ml",
                "gemini_3.1_pro",
                "codex_v0.115_session_153",
                "codex_v0.125_session_154",
            ],
            "belle_isle_citation": "LoC LC-DIG-det-4a17798",
            "gedcom_link": {
                "xref": GEDCOM_HARRY_ISAACKOVITZ_XREF,
                "state": "candidate",
                "confidence": 0.3,
            },
            "snapshot_path": args.snapshot,
            "snapshot_sha256": expected,
            "session_id": "156",
        },
    }

    gedcom_link_row = {
        "identity_id": new_identity_id,
        "gedcom_id": GEDCOM_HARRY_ISAACKOVITZ_XREF,
        "confidence": 0.3,
        "linked_by": "session-156-candidate",
    }

    print()
    print("=== PLANNED MUTATION ===")
    print(f"  Detach from Harry Fox:  {FACE_F}, {FACE_G}")
    print(f"  Harry anchors:          7 -> 5")
    print(f"  Harry version_id:       {current['version_id']} -> {new_harry_version}")
    print(f"  New identity_id:        {new_identity_id}")
    print(f"  New identity name:      {new_name}")
    print(f"  GEDCOM link:            {GEDCOM_HARRY_ISAACKOVITZ_XREF} confidence=0.3")
    print(f"  Audit log entity:       {new_identity_id}")
    print()

    if not args.execute:
        print("[DRY-RUN] Pass --execute to actually mutate")
        return

    # === EXECUTE ===
    print("EXECUTING...")

    # 1. Insert new identity FIRST (so audit_log + gedcom_face_links FK targets exist)
    sb.table("identities").insert(new_identity_row).execute()
    print(f"  ✓ Created new identity {new_identity_id[:8]}...")

    # 2. Detach F+G from Harry (upsert with new anchor_ids + bumped version_id)
    sb.table("identities").upsert(detached_harry_row, on_conflict="identity_id").execute()
    print(f"  ✓ Detached F+G from Harry Fox (version 13 -> 14)")

    # 3. GEDCOM link
    try:
        sb.table("gedcom_face_links").upsert(
            gedcom_link_row, on_conflict="identity_id,gedcom_id"
        ).execute()
        print(f"  ✓ Inserted gedcom_face_links candidate row")
    except Exception as e:
        print(f"  ! gedcom_face_links failed: {e}")

    # 4. Audit log
    sb.table("audit_log").insert(audit_row).execute()
    print(f"  ✓ Wrote audit_log entry")

    # === VERIFY ===
    print()
    print("=== POST-EXECUTION VERIFY ===")
    r2 = sb.table("identities").select("anchor_ids, version_id").eq("identity_id", HARRY_ID).execute()
    h_after = r2.data[0]
    assert len(h_after["anchor_ids"]) == 5, f"Harry should have 5 anchors, got {len(h_after['anchor_ids'])}"
    assert h_after["version_id"] == new_harry_version
    assert FACE_F not in h_after["anchor_ids"]
    assert FACE_G not in h_after["anchor_ids"]
    print(f"  ✓ Harry: anchors=5, version_id={h_after['version_id']}")

    r3 = sb.table("identities").select("anchor_ids, name, state, metadata").eq("identity_id", new_identity_id).execute()
    n_after = r3.data[0]
    assert set(n_after["anchor_ids"]) == {FACE_F, FACE_G}
    assert n_after["state"] == "INBOX"
    assert "notes" in n_after["metadata"]
    assert "originally_misidentified_as" in n_after["metadata"]
    print(f"  ✓ New identity: anchors={n_after['anchor_ids']}, state={n_after['state']}, has notes={('notes' in n_after['metadata'])}")
    print()
    print(f"NEW_IDENTITY_ID={new_identity_id}")


if __name__ == "__main__":
    main()
