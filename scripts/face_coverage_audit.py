#!/usr/bin/env python3
"""Face-Identity Coverage Audit (READ-ONLY).

Cross-references identities, photo_faces, and photos tables in Supabase
to find:
  - Ghost faces: face IDs referenced by identities but missing from photo_faces
  - Orphaned faces: face IDs in photo_faces not claimed by any non-merged identity
  - Broken photo mappings: faces in photo_faces pointing to non-existent photos

Usage:
    python scripts/face_coverage_audit.py
"""

import json
import os
import sys
from collections import defaultdict
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

from supabase import create_client


def paginated_select(table, columns="*", filters=None, page_size=1000):
    """Fetch all rows from a Supabase table with pagination."""
    all_rows = []
    offset = 0
    while True:
        q = table.select(columns).range(offset, offset + page_size - 1)
        if filters:
            for col, op, val in filters:
                q = getattr(q, op)(col, val)
        resp = q.execute()
        if not resp.data:
            break
        all_rows.extend(resp.data)
        if len(resp.data) < page_size:
            break
        offset += page_size
    return all_rows


def ensure_list(val):
    """Safely convert anchor_ids/candidate_ids to a list."""
    if val is None:
        return []
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
        return []
    if isinstance(val, list):
        return val
    return []


def main():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_ANON_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("ERROR: SUPABASE_URL and SUPABASE_ANON_KEY must be set")
        sys.exit(1)

    sb = create_client(url, key)
    print("Connected to Supabase")

    # --- Fetch all data ---
    print("Fetching identities...")
    identities = paginated_select(
        sb.table("identities"),
        "identity_id,name,state,anchor_ids,candidate_ids,negative_ids,merged_into",
    )
    print(f"  {len(identities)} identities fetched")

    print("Fetching photo_faces...")
    photo_faces = paginated_select(sb.table("photo_faces"), "face_id,photo_id")
    print(f"  {len(photo_faces)} photo_faces rows fetched")

    print("Fetching photos...")
    photos = paginated_select(sb.table("photos"), "photo_id,path")
    print(f"  {len(photos)} photos fetched")

    # --- Build indexes ---
    # All face IDs that physically exist (in photo_faces table)
    existing_face_ids = {row["face_id"] for row in photo_faces}
    # face_id -> photo_id mapping
    face_to_photo = {row["face_id"]: row["photo_id"] for row in photo_faces}
    # All photo IDs that exist
    existing_photo_ids = {row["photo_id"] for row in photos}

    # Separate merged vs active identities
    merged_ids = set()
    active_identities = []
    for ident in identities:
        if ident.get("merged_into"):
            merged_ids.add(ident["identity_id"])
        else:
            active_identities.append(ident)

    confirmed = [i for i in active_identities if i["state"] == "CONFIRMED"]
    proposed = [i for i in active_identities if i["state"] == "PROPOSED"]
    inbox = [i for i in active_identities if i["state"] == "INBOX"]

    print("\nIdentity breakdown:")
    print(f"  CONFIRMED: {len(confirmed)}")
    print(f"  PROPOSED:  {len(proposed)}")
    print(f"  INBOX:     {len(inbox)}")
    print(f"  Merged:    {len(merged_ids)}")
    print(f"  Total active: {len(active_identities)}")

    # --- Audit 1: Ghost faces (referenced by identities, missing from photo_faces) ---
    print("\n=== Audit 1: Ghost Faces ===")
    ghost_faces_confirmed = []  # (identity_id, name, face_id, list_type)
    ghost_faces_other = []

    for ident in active_identities:
        iid = ident["identity_id"]
        name = ident["name"]
        state = ident["state"]

        for list_type, key in [("anchor", "anchor_ids"), ("candidate", "candidate_ids")]:
            face_ids = ensure_list(ident.get(key))
            for fid in face_ids:
                if fid not in existing_face_ids:
                    entry = (iid, name, state, fid, list_type)
                    if state == "CONFIRMED":
                        ghost_faces_confirmed.append(entry)
                    else:
                        ghost_faces_other.append(entry)

    print(f"  Ghost faces in CONFIRMED identities: {len(ghost_faces_confirmed)}")
    print(f"  Ghost faces in other identities: {len(ghost_faces_other)}")
    if ghost_faces_confirmed:
        for iid, name, state, fid, lt in ghost_faces_confirmed[:20]:
            print(f"    [{state}] {name} ({iid[:8]}): {fid} in {lt}_ids")

    # --- Audit 2: Orphaned faces (in photo_faces but no identity claims them) ---
    print("\n=== Audit 2: Orphaned Faces ===")
    claimed_face_ids = set()
    for ident in active_identities:
        for key in ["anchor_ids", "candidate_ids"]:
            for fid in ensure_list(ident.get(key)):
                claimed_face_ids.add(fid)

    orphaned_faces = existing_face_ids - claimed_face_ids
    print(f"  Faces in photo_faces: {len(existing_face_ids)}")
    print(f"  Faces claimed by active identities: {len(claimed_face_ids)}")
    print(f"  Orphaned faces (no identity): {len(orphaned_faces)}")
    if orphaned_faces:
        # Group by photo for readability
        orphan_by_photo = defaultdict(list)
        for fid in orphaned_faces:
            pid = face_to_photo.get(fid, "UNKNOWN")
            orphan_by_photo[pid].append(fid)
        print(f"  Spread across {len(orphan_by_photo)} photos")
        for pid, fids in sorted(orphan_by_photo.items(), key=lambda x: -len(x[1]))[:10]:
            print(f"    photo {pid[:16]}: {len(fids)} orphaned faces ({fids[0]}, ...)")

    # --- Audit 3: Broken photo mappings (face -> photo_id doesn't exist in photos) ---
    print("\n=== Audit 3: Broken Photo Mappings ===")
    broken_photo_mappings = []
    for row in photo_faces:
        if row["photo_id"] not in existing_photo_ids:
            broken_photo_mappings.append((row["face_id"], row["photo_id"]))
    print(f"  Faces pointing to non-existent photos: {len(broken_photo_mappings)}")
    if broken_photo_mappings:
        for fid, pid in broken_photo_mappings[:10]:
            print(f"    face {fid} -> photo {pid} (MISSING)")

    # --- Audit 4: Faces claimed by multiple active identities ---
    print("\n=== Audit 4: Multi-Claimed Faces ===")
    face_to_identities = defaultdict(list)
    for ident in active_identities:
        iid = ident["identity_id"]
        name = ident["name"]
        for key in ["anchor_ids", "candidate_ids"]:
            for fid in ensure_list(ident.get(key)):
                face_to_identities[fid].append((iid, name, key.replace("_ids", "")))
    multi_claimed = {fid: owners for fid, owners in face_to_identities.items() if len(owners) > 1}
    print(f"  Faces claimed by 2+ active identities: {len(multi_claimed)}")
    if multi_claimed:
        for fid, owners in list(multi_claimed.items())[:10]:
            owner_strs = [f"{name} ({iid[:8]}, {lt})" for iid, name, lt in owners]
            print(f"    {fid}: {', '.join(owner_strs)}")

    # --- Audit 5: CONFIRMED identities with zero anchor_ids ---
    print("\n=== Audit 5: CONFIRMED with Empty Anchors ===")
    empty_confirmed = [i for i in confirmed if not ensure_list(i.get("anchor_ids"))]
    print(f"  CONFIRMED identities with 0 anchor_ids: {len(empty_confirmed)}")
    for ident in empty_confirmed[:10]:
        print(f"    {ident['name']} ({ident['identity_id'][:8]})")

    # --- Write report ---
    report_path = "docs/session_context/session-132-face-coverage-audit.md"
    os.makedirs(os.path.dirname(report_path), exist_ok=True)

    with open(report_path, "w") as f:
        f.write("# Session 132 — Face-Identity Coverage Audit\n\n")
        f.write(f"**Generated:** {datetime.now().isoformat()[:19]}\n")
        f.write("**Type:** READ-ONLY audit (no data modified)\n\n")

        f.write("## Summary\n\n")
        f.write("| Metric | Count |\n")
        f.write("|--------|-------|\n")
        f.write(f"| Total identities | {len(identities)} |\n")
        f.write(f"| Active (non-merged) | {len(active_identities)} |\n")
        f.write(f"| CONFIRMED | {len(confirmed)} |\n")
        f.write(f"| PROPOSED | {len(proposed)} |\n")
        f.write(f"| INBOX | {len(inbox)} |\n")
        f.write(f"| Merged | {len(merged_ids)} |\n")
        f.write(f"| photo_faces rows | {len(photo_faces)} |\n")
        f.write(f"| photos rows | {len(photos)} |\n")
        f.write(f"| Faces claimed by identities | {len(claimed_face_ids)} |\n\n")

        f.write("## Audit 1: Ghost Faces\n\n")
        f.write("Face IDs referenced in identity anchor_ids/candidate_ids but missing from photo_faces.\n\n")
        f.write(f"- **CONFIRMED ghost faces: {len(ghost_faces_confirmed)}**\n")
        f.write(f"- Other ghost faces: {len(ghost_faces_other)}\n\n")
        if ghost_faces_confirmed:
            f.write("### CONFIRMED Ghost Faces (P0)\n\n")
            f.write("| Identity | Name | Face ID | List |\n")
            f.write("|----------|------|---------|------|\n")
            for iid, name, state, fid, lt in ghost_faces_confirmed:
                f.write(f"| {iid[:8]} | {name} | `{fid}` | {lt} |\n")
            f.write("\n")
        if ghost_faces_other:
            f.write(f"### Other Ghost Faces ({len(ghost_faces_other)} total)\n\n")
            f.write("| Identity | Name | State | Face ID | List |\n")
            f.write("|----------|------|-------|---------|------|\n")
            for iid, name, state, fid, lt in ghost_faces_other[:50]:
                f.write(f"| {iid[:8]} | {name} | {state} | `{fid}` | {lt} |\n")
            if len(ghost_faces_other) > 50:
                f.write(f"\n*...and {len(ghost_faces_other) - 50} more*\n")
            f.write("\n")

        f.write("## Audit 2: Orphaned Faces\n\n")
        f.write("Face IDs in photo_faces not claimed by any active identity.\n\n")
        f.write(f"- **Orphaned faces: {len(orphaned_faces)}**\n")
        f.write(f"- Across {len(orphan_by_photo) if orphaned_faces else 0} photos\n\n")
        if orphaned_faces:
            f.write("### Top Photos with Orphaned Faces\n\n")
            f.write("| Photo ID | Orphaned Faces | Sample Face ID |\n")
            f.write("|----------|---------------|----------------|\n")
            for pid, fids in sorted(orphan_by_photo.items(), key=lambda x: -len(x[1]))[:30]:
                f.write(f"| {pid[:16]} | {len(fids)} | `{fids[0]}` |\n")
            f.write("\n")

        f.write("## Audit 3: Broken Photo Mappings\n\n")
        f.write("Faces in photo_faces pointing to photo_ids that don't exist in photos table.\n\n")
        f.write(f"- **Broken mappings: {len(broken_photo_mappings)}**\n\n")
        if broken_photo_mappings:
            f.write("| Face ID | Missing Photo ID |\n")
            f.write("|---------|------------------|\n")
            for fid, pid in broken_photo_mappings[:30]:
                f.write(f"| `{fid}` | `{pid}` |\n")
            f.write("\n")

        f.write("## Audit 4: Multi-Claimed Faces\n\n")
        f.write("Faces claimed by 2+ active (non-merged) identities.\n\n")
        f.write(f"- **Multi-claimed faces: {len(multi_claimed)}**\n\n")
        if multi_claimed:
            f.write("| Face ID | Owners |\n")
            f.write("|---------|--------|\n")
            for fid, owners in list(multi_claimed.items())[:30]:
                owner_strs = [f"{name} ({iid[:8]}, {lt})" for iid, name, lt in owners]
                f.write(f"| `{fid}` | {'; '.join(owner_strs)} |\n")
            if len(multi_claimed) > 30:
                f.write(f"\n*...and {len(multi_claimed) - 30} more*\n")
            f.write("\n")

        f.write("## Audit 5: CONFIRMED with Empty Anchors\n\n")
        f.write(f"- **CONFIRMED identities with 0 anchor_ids: {len(empty_confirmed)}**\n\n")
        if empty_confirmed:
            f.write("| Identity | Name |\n")
            f.write("|----------|------|\n")
            for ident in empty_confirmed:
                f.write(f"| {ident['identity_id'][:8]} | {ident['name']} |\n")
            f.write("\n")

        f.write("## Severity Assessment\n\n")
        p0_count = len(ghost_faces_confirmed) + len(empty_confirmed) + len(broken_photo_mappings)
        p1_count = len(multi_claimed)
        p2_count = len(orphaned_faces) + len(ghost_faces_other)
        f.write(
            f"- **P0 (data loss risk):** {p0_count} — ghost faces in CONFIRMED, empty CONFIRMED anchors, broken photo mappings\n"
        )
        f.write(f"- **P1 (integrity):** {p1_count} — multi-claimed faces\n")
        f.write(f"- **P2 (cleanup):** {p2_count} — orphaned faces, ghost faces in non-CONFIRMED\n")

    print(f"\nReport written to {report_path}")
    print("DONE — no data was modified.")


if __name__ == "__main__":
    main()
