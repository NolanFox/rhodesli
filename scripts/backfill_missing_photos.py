#!/usr/bin/env python3
"""Backfill photos that exist in JSON but are missing from Supabase.

Compares photo_index.json against Supabase photos table and syncs:
1. Missing photos → photos table
2. Missing photo_communities entries → photo_communities table
3. Missing identities (new faces from ingest) → identities table
4. Missing photo_faces → photo_faces table

Usage:
    python scripts/backfill_missing_photos.py --dry-run
    python scripts/backfill_missing_photos.py --execute
"""

import json
import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

import numpy as np


def get_client():
    from supabase import create_client

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
        sys.exit(1)
    return create_client(url, key)


def get_rhodes_community_id(sb):
    """Get the Rhodes community ID from Supabase."""
    resp = sb.table("communities").select("id").eq("slug", "rhodes").execute()
    if resp.data:
        return resp.data[0]["id"]
    print("ERROR: Rhodes community not found in Supabase")
    sys.exit(1)


def find_missing_photos(sb, json_photos: dict) -> list[str]:
    """Find photo_ids in JSON but not in Supabase."""
    # Get all photo_ids from Supabase
    all_sb_ids = set()
    offset = 0
    while True:
        resp = sb.table("photos").select("photo_id").range(offset, offset + 999).execute()
        if not resp.data:
            break
        for row in resp.data:
            all_sb_ids.add(row["photo_id"])
        if len(resp.data) < 1000:
            break
        offset += 1000

    json_ids = set(json_photos.keys())
    missing = json_ids - all_sb_ids
    print(f"  Supabase has {len(all_sb_ids)} photos, JSON has {len(json_ids)}")
    print(f"  Missing from Supabase: {len(missing)}")
    return sorted(missing)


def find_missing_photo_communities(sb, photo_ids: list[str], community_id: str) -> list[str]:
    """Find photos not yet tagged to the community."""
    if not photo_ids:
        return []
    # Get ALL existing community tags (paginated), then diff
    existing = set()
    offset = 0
    while True:
        resp = (
            sb.table("photo_communities")
            .select("photo_id")
            .eq("community_id", community_id)
            .range(offset, offset + 999)
            .execute()
        )
        if not resp.data:
            break
        for row in resp.data:
            existing.add(row["photo_id"])
        if len(resp.data) < 1000:
            break
        offset += 1000
    return [pid for pid in photo_ids if pid not in existing]


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Backfill missing photos to Supabase")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--execute", action="store_true", help="Actually perform the backfill")
    args = parser.parse_args()

    if not args.dry_run and not args.execute:
        print("Must specify --dry-run or --execute")
        sys.exit(1)

    data_dir = PROJECT_ROOT / "data"
    pi_path = data_dir / "photo_index.json"
    id_path = data_dir / "identities.json"
    emb_path = data_dir / "embeddings.npy"

    # Load JSON data
    with open(pi_path) as f:
        pi_data = json.load(f)
    json_photos = pi_data.get("photos", {})
    face_to_photo = pi_data.get("face_to_photo", {})

    with open(id_path) as f:
        id_data = json.load(f)
    json_identities = id_data.get("identities", {})

    sb = get_client()

    # Get both community IDs
    resp = sb.table("communities").select("id,slug").execute()
    community_map = {row["slug"]: row["id"] for row in resp.data}
    rhodes_id = community_map.get("rhodes")
    fox_id = community_map.get("fox-family")
    print(f"Rhodes community: {rhodes_id}")
    print(f"Fox Family community: {fox_id}")

    def classify_photo(photo_id: str) -> str:
        """Determine which community a photo belongs to."""
        if photo_id.startswith("inbox_fox"):
            return "fox-family"
        return "rhodes"

    # 1. Find missing photos
    print("\n--- Photos ---")
    missing_photo_ids = find_missing_photos(sb, json_photos)

    if missing_photo_ids:
        print(f"  Missing photos: {missing_photo_ids}")
        if args.execute:
            rows = []
            for pid in missing_photo_ids:
                p = json_photos[pid]
                rows.append(
                    {
                        "photo_id": pid,
                        "path": p.get("path", ""),
                        "source": p.get("source", ""),
                        "collection": p.get("collection", ""),
                        "source_url": p.get("source_url", ""),
                        "upload_date": p.get("upload_date"),
                        "width": p.get("width"),
                        "height": p.get("height"),
                    }
                )
            sb.table("photos").upsert(rows).execute()
            print(f"  Upserted {len(rows)} photos")

    # 2. Tag missing photos to correct community
    print("\n--- Photo Communities ---")
    all_json_ids = list(json_photos.keys())

    # Check both communities
    for slug, cid in [("rhodes", rhodes_id), ("fox-family", fox_id)]:
        if not cid:
            continue
        # Photos that belong to this community
        community_photos = [pid for pid in all_json_ids if classify_photo(pid) == slug]
        missing_community = find_missing_photo_communities(sb, community_photos, cid)
        print(f"  {slug}: {len(community_photos)} photos, {len(missing_community)} missing community tag")
        if missing_community:
            print(f"    Sample: {missing_community[:5]}")
            if args.execute:
                rows = [{"photo_id": pid, "community_id": cid} for pid in missing_community]
                for i in range(0, len(rows), 100):
                    batch = rows[i : i + 100]
                    sb.table("photo_communities").upsert(batch).execute()
                print(f"    Upserted {len(rows)} photo_communities entries")

    # 3. Find missing identities
    print("\n--- Identities ---")
    # Get face_ids for missing photos to find new identities
    new_face_ids = set()
    for pid in missing_photo_ids:
        p = json_photos.get(pid, {})
        for fid in p.get("face_ids", []):
            new_face_ids.add(fid)
    print(f"  Faces from missing photos: {len(new_face_ids)}")

    # Find identities containing those faces
    new_identity_ids = set()
    for iid, ident in json_identities.items():
        all_faces = set(ident.get("anchor_ids", [])) | set(ident.get("candidate_ids", []))
        if all_faces & new_face_ids:
            new_identity_ids.add(iid)
    print(f"  Identities containing new faces: {len(new_identity_ids)}")

    if new_identity_ids:
        # Check which are missing from Supabase
        resp = sb.table("identities").select("identity_id").in_("identity_id", list(new_identity_ids)).execute()
        existing_ids = {row["identity_id"] for row in (resp.data or [])}
        truly_missing = new_identity_ids - existing_ids
        print(f"  Already in Supabase: {len(existing_ids)}, missing: {len(truly_missing)}")

        if truly_missing and args.execute:
            rows = []
            for iid in truly_missing:
                ident = json_identities[iid]
                rows.append(
                    {
                        "identity_id": iid,
                        "name": ident.get("name", f"Unidentified Person {iid[:8]}"),
                        "display_name": ident.get("display_name"),
                        "state": ident.get("state", "INBOX"),
                        "anchor_ids": ident.get("anchor_ids", []),
                        "candidate_ids": ident.get("candidate_ids", []),
                        "negative_ids": ident.get("negative_ids", []),
                        "version_id": ident.get("version_id", 1),
                        "merged_into": ident.get("merged_into"),
                    }
                )
            sb.table("identities").upsert(rows).execute()
            print(f"  Upserted {len(rows)} identities")

            # Tag new identities to appropriate community based on their faces
            for iid in truly_missing:
                ident = json_identities[iid]
                all_faces = set(ident.get("anchor_ids", [])) | set(ident.get("candidate_ids", []))
                # Determine community by the photo that contains the face
                for fid in all_faces:
                    pid = face_to_photo.get(fid)
                    if pid:
                        slug = classify_photo(pid)
                        cid = community_map.get(slug)
                        if cid:
                            sb.table("identity_communities").upsert({"identity_id": iid, "community_id": cid}).execute()
                        break
            print(f"  Tagged {len(truly_missing)} identities to communities")

    # 4. Find missing photo_faces
    print("\n--- Photo Faces ---")
    missing_faces = []
    for fid in new_face_ids:
        pid = face_to_photo.get(fid)
        if pid:
            missing_faces.append((fid, pid))
    print(f"  Face entries to check: {len(missing_faces)}")

    if missing_faces:
        face_ids_to_check = [f[0] for f in missing_faces]
        resp = sb.table("photo_faces").select("face_id").in_("face_id", face_ids_to_check).execute()
        existing_faces = {row["face_id"] for row in (resp.data or [])}
        truly_missing_faces = [(fid, pid) for fid, pid in missing_faces if fid not in existing_faces]
        print(f"  Already in Supabase: {len(existing_faces)}, missing: {len(truly_missing_faces)}")

        if truly_missing_faces:
            # Load embeddings for bbox/det_score/quality
            emb_lookup = {}
            if emb_path.exists():
                embeddings = np.load(emb_path, allow_pickle=True)
                filename_counts = {}
                for emb in embeddings:
                    fid = emb.get("face_id")
                    if not fid:
                        fname = emb.get("filename", "")
                        stem = Path(fname).stem
                        idx = filename_counts.get(fname, 0)
                        filename_counts[fname] = idx + 1
                        fid = f"{stem}:face{idx}"
                    emb_lookup[fid] = {
                        "bbox": emb.get("bbox"),
                        "det_score": float(emb.get("det_score", 0)),
                        "quality": float(emb.get("quality", 0)),
                    }

            if args.execute:
                rows = []
                for fid, pid in truly_missing_faces:
                    emb_data = emb_lookup.get(fid, {})
                    bbox = emb_data.get("bbox")
                    if bbox is not None and not isinstance(bbox, str):
                        bbox = json.dumps([float(x) for x in bbox])
                    rows.append(
                        {
                            "face_id": fid,
                            "photo_id": pid,
                            "bbox": bbox,
                            "det_score": emb_data.get("det_score"),
                            "quality": emb_data.get("quality"),
                        }
                    )
                sb.table("photo_faces").upsert(rows).execute()
                print(f"  Upserted {len(rows)} photo_faces")

    print("\n--- Summary ---")
    print(f"  Photos missing: {len(missing_photo_ids)}")
    print(f"  Community tags missing: {len(missing_community)}")
    print(f"  Mode: {'DRY RUN' if args.dry_run else 'EXECUTED'}")


if __name__ == "__main__":
    main()
