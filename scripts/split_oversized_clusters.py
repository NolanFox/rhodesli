#!/usr/bin/env python3
"""Split oversized identity clusters back into individual INBOX identities.

After the single-linkage grouping bug created garbage clusters (252, 157, 121 faces),
this script splits any identity with more faces than --max-faces back into
individual single-face INBOX identities.

Usage:
    python scripts/split_oversized_clusters.py --dry-run              # Preview
    python scripts/split_oversized_clusters.py --execute              # Actually split
    python scripts/split_oversized_clusters.py --max-faces 50 --execute
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


def main():
    parser = argparse.ArgumentParser(description="Split oversized identity clusters")
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument(
        "--max-faces", type=int, default=50, help="Split identities with more faces than this (default: 50)"
    )
    args = parser.parse_args()

    if args.execute:
        args.dry_run = False

    data_path = project_root / "data"

    from core.registry import IdentityRegistry

    print("=" * 60)
    print("SPLIT OVERSIZED CLUSTERS")
    print("=" * 60)
    print(f"Max faces per identity: {args.max_faces}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'EXECUTE'}")
    print()

    identities_path = data_path / "identities.json"
    registry = IdentityRegistry.load(identities_path)

    # Find oversized identities
    oversized = []
    for ident in registry.list_identities():
        if ident.get("merged_into"):
            continue
        all_faces = ident.get("anchor_ids", []) + ident.get("candidate_ids", [])
        if len(all_faces) > args.max_faces:
            oversized.append(
                {
                    "identity_id": ident["identity_id"],
                    "name": ident.get("name", "Unknown"),
                    "state": ident.get("state", "INBOX"),
                    "face_count": len(all_faces),
                    "face_ids": all_faces,
                }
            )

    if not oversized:
        print(f"No identities with >{args.max_faces} faces found. Nothing to split.")
        return

    print(f"Found {len(oversized)} oversized identities:")
    total_faces = 0
    for item in sorted(oversized, key=lambda x: x["face_count"], reverse=True):
        print(f"  {item['name']} ({item['identity_id'][:8]}...): {item['face_count']} faces [{item['state']}]")
        total_faces += item["face_count"]
    print(f"  Total faces to split: {total_faces}")
    print()

    if args.dry_run:
        print("DRY RUN — no changes made. Use --execute to split.")
        return

    # Execute: detach all faces except the first from each oversized identity
    total_detached = 0
    new_identities = 0
    for item in oversized:
        iid = item["identity_id"]
        faces = item["face_ids"]
        print(f"Splitting {item['name']} ({len(faces)} faces)...")

        # Keep the first face, detach all others
        for face_id in faces[1:]:
            try:
                result = registry.detach_face(iid, face_id, user_source="split_oversized_script")
                if result.get("success"):
                    total_detached += 1
                    new_identities += 1
                else:
                    print(f"  Warning: could not detach {face_id}: {result.get('reason')}")
            except Exception as e:
                print(f"  Error detaching {face_id}: {e}")

        print(f"  Detached {len(faces) - 1} faces → {len(faces) - 1} new INBOX identities")

    print()
    print(f"Total detached: {total_detached}")
    print(f"New INBOX identities: {new_identities}")

    # Save
    print("Saving registry...")
    registry.save(identities_path)
    print(f"Saved to {identities_path}")
    print()
    print("NEXT STEPS:")
    print("  1. Run: python scripts/group_inbox_faces.py --execute")
    print("  2. Run: python scripts/cluster_new_faces.py --dry-run")
    print("  3. Commit and push")


if __name__ == "__main__":
    main()
