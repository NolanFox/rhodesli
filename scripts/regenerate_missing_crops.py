#!/usr/bin/env python3
"""Regenerate missing face crops from source photos + bbox data in embeddings.npy.

Usage:
    python scripts/regenerate_missing_crops.py --dry-run     # Preview only
    python scripts/regenerate_missing_crops.py --execute      # Generate crops locally
    python scripts/regenerate_missing_crops.py --execute --upload  # Generate + upload to R2

For each missing crop:
1. Read bbox from embeddings.npy
2. Download source photo from R2 (or read locally)
3. Crop face with 10% padding
4. Save to app/static/crops/{face_id}.jpg
5. Optionally upload to R2
"""

import argparse
import glob
import json
import os
import sys

import cv2
import numpy as np


def add_padding(bbox, img_shape, pad_ratio=0.1):
    """Add padding around a face bounding box."""
    h, w = img_shape[:2]
    x1, y1, x2, y2 = [int(v) for v in bbox]
    bw, bh = x2 - x1, y2 - y1
    pad_x = int(bw * pad_ratio)
    pad_y = int(bh * pad_ratio)
    return [
        max(0, x1 - pad_x),
        max(0, y1 - pad_y),
        min(w, x2 + pad_x),
        min(h, y2 + pad_y),
    ]


def main():
    parser = argparse.ArgumentParser(description="Regenerate missing face crops")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--execute", action="store_true", help="Generate crop files")
    parser.add_argument("--upload", action="store_true", help="Also upload to R2")
    parser.add_argument("--data-dir", default="data", help="Data directory")
    parser.add_argument("--crops-dir", default="app/static/crops", help="Output crops directory")
    parser.add_argument("--photos-dir", default="raw_photos", help="Source photos directory")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of crops to regenerate (0=all)")
    args = parser.parse_args()

    if not args.dry_run and not args.execute:
        print("ERROR: Specify --dry-run or --execute")
        sys.exit(1)

    # Load embeddings
    embs = np.load(os.path.join(args.data_dir, "embeddings.npy"), allow_pickle=True)
    print(f"Total embeddings: {len(embs)}")

    # Get existing crops
    local_crops = set(os.path.basename(f).replace(".jpg", "") for f in glob.glob(os.path.join(args.crops_dir, "*.jpg")))

    # Find faces needing crops
    to_regenerate = []
    for e in embs:
        fid = e.get("face_id", "")
        if not fid or fid in local_crops:
            continue
        bbox = e.get("bbox")
        filename = e.get("filename", "")
        if bbox is not None and filename:
            to_regenerate.append(
                {
                    "face_id": fid,
                    "bbox": bbox,
                    "filename": filename,
                }
            )

    print(f"Faces needing crops: {len(to_regenerate)}")

    if args.limit > 0:
        to_regenerate = to_regenerate[: args.limit]
        print(f"Limited to: {len(to_regenerate)}")

    if args.dry_run:
        print(f"\nDRY RUN — would regenerate {len(to_regenerate)} crops")
        # Group by source photo
        by_photo = {}
        for item in to_regenerate:
            by_photo.setdefault(item["filename"], []).append(item["face_id"])
        print(f"From {len(by_photo)} source photos")
        for photo, faces in list(by_photo.items())[:10]:
            print(f"  {photo}: {len(faces)} faces")
        return

    # Execute mode
    os.makedirs(args.crops_dir, exist_ok=True)
    generated = 0
    skipped = 0
    errors = 0

    for item in to_regenerate:
        fid = item["face_id"]
        bbox = item["bbox"]
        filename = item["filename"]

        # Find source photo
        photo_path = os.path.join(args.photos_dir, filename)
        if not os.path.exists(photo_path):
            # Try without path prefix
            photo_path = os.path.join(args.photos_dir, os.path.basename(filename))
        if not os.path.exists(photo_path):
            skipped += 1
            continue

        try:
            img = cv2.imread(photo_path)
            if img is None:
                errors += 1
                continue

            # Crop with padding
            padded = add_padding(bbox, img.shape)
            x1, y1, x2, y2 = padded
            crop = img[y1:y2, x1:x2]

            if crop.size == 0:
                errors += 1
                continue

            # Save crop
            crop_path = os.path.join(args.crops_dir, f"{fid}.jpg")
            cv2.imwrite(crop_path, crop, [cv2.IMWRITE_JPEG_QUALITY, 95])
            generated += 1

            if generated % 50 == 0:
                print(f"  Generated {generated}/{len(to_regenerate)}...")

        except Exception as e:
            print(f"  ERROR: {fid}: {e}")
            errors += 1

    print("\nResults:")
    print(f"  Generated: {generated}")
    print(f"  Skipped (no source photo): {skipped}")
    print(f"  Errors: {errors}")

    # Upload to R2 if requested
    if args.upload and generated > 0:
        from dotenv import load_dotenv

        load_dotenv()
        try:
            import boto3

            r2_account = os.getenv("R2_ACCOUNT_ID")
            r2_key = os.getenv("R2_ACCESS_KEY_ID")
            r2_secret = os.getenv("R2_SECRET_ACCESS_KEY")
            r2_bucket = os.getenv("R2_BUCKET_NAME")

            if not all([r2_account, r2_key, r2_secret, r2_bucket]):
                print("\nR2 credentials not configured — skipping upload")
                return

            s3 = boto3.client(
                "s3",
                endpoint_url=f"https://{r2_account}.r2.cloudflarestorage.com",
                aws_access_key_id=r2_key,
                aws_secret_access_key=r2_secret,
            )

            uploaded = 0
            for item in to_regenerate:
                crop_path = os.path.join(args.crops_dir, f"{item['face_id']}.jpg")
                if os.path.exists(crop_path):
                    s3.upload_file(
                        crop_path,
                        r2_bucket,
                        f"crops/{item['face_id']}.jpg",
                        ExtraArgs={"ContentType": "image/jpeg"},
                    )
                    uploaded += 1

            print(f"\nUploaded {uploaded} crops to R2")

        except ImportError:
            print("\nboto3 not installed — cannot upload to R2")
        except Exception as e:
            print(f"\nR2 upload error: {e}")


if __name__ == "__main__":
    main()
