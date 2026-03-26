#!/usr/bin/env python3
"""Audit missing face crops — compare embeddings.npy face_ids against local crop files.

Usage:
    python scripts/audit_missing_crops.py [--check-r2]

Reports:
    - Total faces in embeddings
    - Faces with local crops
    - Faces missing local crops (by source collection)
    - Optionally checks R2 availability via HEAD requests
"""

import argparse
import glob
import json
import os
import sys

import numpy as np


def main():
    parser = argparse.ArgumentParser(description="Audit missing face crops")
    parser.add_argument("--check-r2", action="store_true", help="Also check R2 availability (slow)")
    parser.add_argument("--data-dir", default="data", help="Data directory")
    parser.add_argument("--crops-dir", default="app/static/crops", help="Local crops directory")
    args = parser.parse_args()

    # Load embeddings
    embs_path = os.path.join(args.data_dir, "embeddings.npy")
    if not os.path.exists(embs_path):
        print(f"ERROR: {embs_path} not found")
        sys.exit(1)

    embs = np.load(embs_path, allow_pickle=True)
    print(f"Total embeddings: {len(embs)}")

    # Get local crops
    local_crops = set(os.path.basename(f).replace(".jpg", "") for f in glob.glob(os.path.join(args.crops_dir, "*.jpg")))
    print(f"Local crop files: {len(local_crops)}")

    # Load photo index for source info
    pi_path = os.path.join(args.data_dir, "photo_index.json")
    face_to_photo = {}
    photos = {}
    if os.path.exists(pi_path):
        with open(pi_path) as f:
            pi = json.load(f)
        face_to_photo = pi.get("face_to_photo", {})
        photos = pi.get("photos", {})

    # Find missing crops
    missing = []
    has_crop = 0
    no_face_id = 0

    for e in embs:
        fid = e.get("face_id", "")
        if not fid:
            # Legacy format — face_id generated from filename + index
            no_face_id += 1
            continue

        if fid in local_crops:
            has_crop += 1
        else:
            bbox = e.get("bbox")
            filename = e.get("filename", "")
            photo_id = face_to_photo.get(fid, "")
            photo = photos.get(photo_id, {})
            source = photo.get("source", "unknown")
            path = photo.get("path", filename)
            missing.append(
                {
                    "face_id": fid,
                    "source": source,
                    "photo_path": path,
                    "has_bbox": bbox is not None,
                    "bbox": list(bbox) if bbox is not None else None,
                }
            )

    print(f"\nFaces with local crop: {has_crop}")
    print(f"Faces without face_id (legacy): {no_face_id}")
    print(f"Faces missing local crop: {len(missing)}")
    print(f"Faces missing crop WITH bbox data: {sum(1 for m in missing if m['has_bbox'])}")

    # Group by source
    by_source = {}
    for m in missing:
        src = m["source"]
        by_source.setdefault(src, []).append(m)

    print("\nMissing by source:")
    for src, items in sorted(by_source.items(), key=lambda x: -len(x[1])):
        regenerable = sum(1 for i in items if i["has_bbox"])
        print(f"  {src or '(empty)'}: {len(items)} ({regenerable} regenerable)")

    # Check R2 if requested
    if args.check_r2:
        from dotenv import load_dotenv

        load_dotenv()
        r2_url = os.getenv("R2_PUBLIC_URL", "")
        if not r2_url:
            print("\nR2_PUBLIC_URL not configured — cannot check R2")
        else:
            import requests

            print(f"\nChecking R2 ({r2_url})...")
            on_r2 = 0
            not_on_r2 = 0
            for m in missing[:50]:  # Sample first 50
                url = f"{r2_url}/crops/{m['face_id']}.jpg"
                try:
                    resp = requests.head(url, timeout=5)
                    if resp.status_code == 200:
                        on_r2 += 1
                    else:
                        not_on_r2 += 1
                except Exception:
                    not_on_r2 += 1
            print(f"  Checked 50 missing: {on_r2} on R2, {not_on_r2} not on R2")

    # Write report
    report_path = "docs/session_context/session-139-crop-audit.json"
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(
            {
                "total_embeddings": len(embs),
                "local_crops": len(local_crops),
                "missing_count": len(missing),
                "regenerable_count": sum(1 for m in missing if m["has_bbox"]),
                "by_source": {src: len(items) for src, items in by_source.items()},
                "missing_faces": [m["face_id"] for m in missing],
            },
            f,
            indent=2,
        )
    print(f"\nReport saved to {report_path}")


if __name__ == "__main__":
    main()
