#!/usr/bin/env python3
"""Investigate 'Conflicting face assignment' badges on CONFIRMED identities.

Session 143, Track D — investigation only.

Checks:
1. Victoria Capeluto's identity data (anchor_ids, candidate_ids, negative_ids)
2. Whether candidate_ids on CONFIRMED identities triggers the badge
3. Actual face assignment conflicts (same face in multiple identities)
4. Bounding box overlaps that trigger the badge
"""

import json
import os
import sys
from collections import defaultdict
from pathlib import Path

# Load .env from main repo root (worktree may not have it)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv

# Try worktree .env first, then main repo .env
worktree_root = Path(__file__).resolve().parent.parent
main_repo_root = Path("/Users/nolanfox/rhodesli")
if (worktree_root / ".env").exists():
    load_dotenv(worktree_root / ".env")
else:
    load_dotenv(main_repo_root / ".env")

from supabase import create_client


def get_client():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
        sys.exit(1)
    return create_client(url, key)


def ensure_list(val):
    """Handle JSONB columns that may be stored as strings."""
    if val is None:
        return []
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            return parsed if isinstance(parsed, list) else [parsed]
        except (json.JSONDecodeError, TypeError):
            return [val]
    if isinstance(val, list):
        return val
    return [val]


def main():
    client = get_client()

    # --- 1. Find Victoria Capeluto ---
    print("=" * 70)
    print("INVESTIGATION: Conflicting Face Assignment Badges")
    print("=" * 70)

    print("\n--- 1. Finding Victoria Capeluto ---")
    resp = client.table("identities").select("*").ilike("name", "%Victoria%Capeluto%").execute()
    if not resp.data:
        # Try broader search
        resp = client.table("identities").select("*").ilike("name", "%Victoria%").execute()

    victorias = [r for r in (resp.data or []) if "victoria" in r.get("name", "").lower()]
    for v in victorias:
        print(f"\n  Identity: {v['identity_id']}")
        print(f"  Name: {v['name']}")
        print(f"  State: {v['state']}")
        anchor_ids = ensure_list(v.get("anchor_ids"))
        candidate_ids = ensure_list(v.get("candidate_ids"))
        negative_ids = ensure_list(v.get("negative_ids"))
        print(f"  anchor_ids ({len(anchor_ids)}): {anchor_ids}")
        print(f"  candidate_ids ({len(candidate_ids)}): {candidate_ids}")
        print(f"  negative_ids ({len(negative_ids)}): {negative_ids}")
        print(f"  merged_into: {v.get('merged_into')}")

    # --- 2. Badge logic analysis ---
    print("\n--- 2. Badge Logic Analysis ---")
    print("""
    The 'Conflicting face assignment' badge on the PERSON PAGE appears when
    _photo_context_conflict() returns True. This happens when:

    A) The face's identity state is 'REJECTED' or 'CONTESTED'
       (checked on line 143 of person_routes.py)

    B) Two faces in the same photo have overlapping bounding boxes (IoU >= 0.8)
       AND one belongs to this person, AND the other belongs to a DIFFERENT person
       (checked on lines 146-151 of person_routes.py)

    IMPORTANT: get_identity_for_face() looks up faces in BOTH anchor_ids AND
    candidate_ids. So if a face is in Victoria's candidate_ids AND another
    identity's anchor_ids, AND their bboxes overlap, the badge shows.

    The badge does NOT appear just because candidate_ids is non-empty.
    It requires actual bbox overlap or REJECTED/CONTESTED state.
    """)

    # --- 3. Check for actual face assignment conflicts ---
    print("--- 3. Checking for face assignment conflicts across ALL identities ---")

    # Load all non-merged identities
    all_resp = (
        client.table("identities")
        .select("identity_id, name, state, anchor_ids, candidate_ids, merged_into")
        .is_("merged_into", "null")
        .execute()
    )

    identities = all_resp.data or []
    print(f"  Total non-merged identities: {len(identities)}")

    # Build face -> identity mapping (mirrors get_identity_for_face logic)
    face_to_identities = defaultdict(list)
    for ident in identities:
        iid = ident["identity_id"]
        name = ident.get("name", "?")
        state = ident.get("state", "?")
        for fid in ensure_list(ident.get("anchor_ids")):
            face_id = fid if isinstance(fid, str) else fid.get("face_id", "")
            if face_id:
                face_to_identities[face_id].append({"identity_id": iid, "name": name, "state": state, "list": "anchor"})
        for fid in ensure_list(ident.get("candidate_ids")):
            face_id = fid if isinstance(fid, str) else fid.get("face_id", "")
            if face_id:
                face_to_identities[face_id].append(
                    {"identity_id": iid, "name": name, "state": state, "list": "candidate"}
                )

    # Find multi-claimed faces
    multi_claimed = {fid: owners for fid, owners in face_to_identities.items() if len(owners) > 1}
    print(f"  Multi-claimed faces (same face in multiple identities): {len(multi_claimed)}")

    if multi_claimed:
        print("\n  Multi-claimed faces:")
        for fid, owners in sorted(multi_claimed.items())[:20]:
            owner_strs = [f"{o['name']} ({o['state']}, {o['list']})" for o in owners]
            print(f"    {fid}: {', '.join(owner_strs)}")
        if len(multi_claimed) > 20:
            print(f"    ... and {len(multi_claimed) - 20} more")

    # --- 4. Check CONFIRMED identities with candidate_ids ---
    print("\n--- 4. CONFIRMED identities with candidate_ids ---")
    confirmed_with_candidates = []
    for ident in identities:
        if ident.get("state") != "CONFIRMED":
            continue
        candidates = ensure_list(ident.get("candidate_ids"))
        if candidates:
            confirmed_with_candidates.append(
                {
                    "identity_id": ident["identity_id"],
                    "name": ident.get("name", "?"),
                    "anchor_count": len(ensure_list(ident.get("anchor_ids"))),
                    "candidate_count": len(candidates),
                    "candidate_ids": candidates,
                }
            )

    print(f"  CONFIRMED identities with candidate_ids: {len(confirmed_with_candidates)}")
    for c in confirmed_with_candidates:
        print(
            f"    {c['name']} (ID: {c['identity_id'][:8]}...): "
            f"{c['anchor_count']} anchors, {c['candidate_count']} candidates"
        )
        # Check if any candidates are also claimed by other identities
        for cid in c["candidate_ids"]:
            face_id = cid if isinstance(cid, str) else cid.get("face_id", "")
            if face_id and face_id in multi_claimed:
                owners = multi_claimed[face_id]
                other_owners = [o for o in owners if o["identity_id"] != c["identity_id"]]
                if other_owners:
                    print(f"      CONFLICT: face {face_id} also in: {', '.join(o['name'] for o in other_owners)}")

    # --- 5. Check Victoria's photos for bbox overlaps ---
    print("\n--- 5. Checking Victoria's photos for bbox overlaps ---")
    victoria_ids = [v["identity_id"] for v in victorias if v.get("state") == "CONFIRMED"]
    if victoria_ids:
        vid = victoria_ids[0]
        victoria_data = next(v for v in victorias if v["identity_id"] == vid)
        all_face_ids = ensure_list(victoria_data.get("anchor_ids")) + ensure_list(victoria_data.get("candidate_ids"))

        # Get photo_faces for Victoria's faces
        face_id_strs = []
        for fid in all_face_ids:
            face_id_strs.append(fid if isinstance(fid, str) else fid.get("face_id", ""))

        print(f"  Victoria's face IDs: {face_id_strs}")

        # Query photo_faces for these faces to get photo_ids
        if face_id_strs:
            pf_resp = (
                client.table("photo_faces").select("face_id, photo_id, bbox").in_("face_id", face_id_strs).execute()
            )
            victoria_photos = {}
            for pf in pf_resp.data or []:
                pid = pf["photo_id"]
                if pid not in victoria_photos:
                    victoria_photos[pid] = []
                victoria_photos[pid].append(pf)

            print(f"  Victoria appears in {len(victoria_photos)} photos")

            # For each photo, get ALL faces and check for overlaps
            for pid, v_faces in victoria_photos.items():
                all_faces_resp = client.table("photo_faces").select("face_id, bbox").eq("photo_id", pid).execute()
                all_faces = all_faces_resp.data or []

                for vf in v_faces:
                    v_bbox = vf.get("bbox")
                    if not v_bbox or not isinstance(v_bbox, list) or len(v_bbox) < 4:
                        continue

                    for other in all_faces:
                        if other["face_id"] == vf["face_id"]:
                            continue
                        o_bbox = other.get("bbox")
                        if not o_bbox or not isinstance(o_bbox, list) or len(o_bbox) < 4:
                            continue

                        # Compute IoU
                        iou = _bbox_iou(v_bbox, o_bbox)
                        if iou >= 0.8:
                            # Who owns the other face?
                            other_owners = face_to_identities.get(other["face_id"], [])
                            other_names = [o["name"] for o in other_owners]
                            print(f"\n  OVERLAP FOUND in photo {pid}:")
                            print(f"    Victoria's face {vf['face_id']}: bbox={v_bbox}")
                            print(f"    Other face {other['face_id']}: bbox={o_bbox}")
                            print(f"    IoU: {iou:.3f}")
                            print(f"    Other face belongs to: {other_names or 'NO IDENTITY'}")
    else:
        print("  No CONFIRMED Victoria found")

    # --- Summary ---
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Total non-merged identities: {len(identities)}")
    print(f"  CONFIRMED with candidate_ids: {len(confirmed_with_candidates)}")
    print(f"  Multi-claimed faces: {len(multi_claimed)}")
    print(f"  Victoria identities found: {len(victorias)}")


def _bbox_iou(bbox_a, bbox_b):
    """Compute intersection-over-union of two [x1, y1, x2, y2] bounding boxes."""
    try:
        ax1, ay1, ax2, ay2 = [float(v) for v in bbox_a[:4]]
        bx1, by1, bx2, by2 = [float(v) for v in bbox_b[:4]]
    except (TypeError, ValueError):
        return 0.0

    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)

    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0

    intersection = (ix2 - ix1) * (iy2 - iy1)
    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    union = area_a + area_b - intersection

    return intersection / union if union > 0 else 0.0


if __name__ == "__main__":
    main()
