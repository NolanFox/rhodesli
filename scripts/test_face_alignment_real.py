#!/usr/bin/env python3
"""
Session 63 Phase 2: Real photo face alignment testing.

Tests face alignment on 3 real photos against the Gemini API.
This is the #1 priority of Session 63 — face alignment was NEVER
tested on real photos (U6 from Session 62).

Usage:
    source venv/bin/activate
    python scripts/test_face_alignment_real.py
"""

import asyncio
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.face_alignment import (
    AlignmentResult,
    FaceDetection,
    run_face_alignment,
)


def load_photo_bytes(photo_path: str) -> bytes | None:
    """Load photo from local filesystem or R2."""
    # Try local raw_photos/
    local_path = Path("raw_photos") / Path(photo_path).name
    if local_path.exists():
        return local_path.read_bytes()

    # Try R2
    r2_url = os.getenv("R2_PUBLIC_URL", "")
    if r2_url:
        filename = Path(photo_path).name
        url = f"{r2_url}/raw_photos/{urllib.parse.quote(filename)}"
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                return resp.read()
        except Exception as e:
            print(f"  R2 load failed: {e}")

    return None


def get_faces_for_photo(photo_id: str, photo_data: dict, identities: dict) -> list[FaceDetection]:
    """Build FaceDetection objects from photo data + embeddings."""
    import numpy as np

    embeddings = np.load("data/embeddings.npy", allow_pickle=True)
    face_ids = photo_data.get("face_ids", [])
    path = photo_data.get("path", "")
    filename = Path(path).name

    # Build confirmed face map
    confirmed_faces = {}
    for iid, identity in identities.get("identities", {}).items():
        if identity.get("state") == "CONFIRMED":
            name = identity.get("name", "Unknown")
            for fid in identity.get("anchor_ids", []):
                confirmed_faces[fid] = name

    # Match face_ids to embeddings
    faces = []
    for i, face_id in enumerate(face_ids):
        # Find embedding for this face
        bbox = None
        det_score = 0.0
        quality = 0.0

        for emb in embeddings:
            emb_filename = emb.get("filename", "")
            emb_face_id = emb.get("face_id", "")

            if emb_face_id == face_id or (
                emb_filename == filename and f"face{i}" in str(emb.get("bbox", ""))
            ):
                bbox_raw = emb.get("bbox", [0, 0, 0, 0])
                if isinstance(bbox_raw, str):
                    bbox_raw = json.loads(bbox_raw)
                bbox = [int(b) for b in bbox_raw]
                det_score = float(emb.get("det_score", 0))
                quality = float(emb.get("quality", 0))
                break

        if bbox is None:
            # Try generate from face_id format like "Image 006_compress:face0"
            for emb in embeddings:
                if emb.get("filename", "") == filename:
                    idx = list(e.get("filename", "") for e in embeddings).count(filename)
                    if "face_id" in emb and emb["face_id"] == face_id:
                        bbox_raw = emb.get("bbox", [0, 0, 0, 0])
                        bbox = [int(b) for b in bbox_raw]
                        det_score = float(emb.get("det_score", 0))
                        quality = float(emb.get("quality", 0))
                        break

        if bbox is None:
            # Brute force: match by filename in embeddings
            face_embs = [e for e in embeddings if e.get("filename", "") == filename]
            if i < len(face_embs):
                emb = face_embs[i]
                bbox_raw = emb.get("bbox", [0, 0, 0, 0])
                bbox = [int(b) for b in bbox_raw]
                det_score = float(emb.get("det_score", 0))
                quality = float(emb.get("quality", 0))

        if bbox is None:
            print(f"  WARNING: No bbox found for face {face_id}, skipping")
            continue

        identity_name = confirmed_faces.get(face_id)
        faces.append(FaceDetection(
            face_id=face_id,
            bbox=bbox,
            face_index=i,
            det_score=det_score,
            quality=quality,
            identity_name=identity_name,
        ))

    return faces


async def test_photo(photo_id: str, photo_data: dict, identities: dict, label: str) -> dict:
    """Run face alignment on a single photo and return results."""
    print(f"\n{'='*60}")
    print(f"Testing: {label}")
    print(f"Photo ID: {photo_id}")
    print(f"Path: {photo_data.get('path', 'N/A')}")
    print(f"Expected faces: {len(photo_data.get('face_ids', []))}")
    print(f"{'='*60}")

    # Load photo bytes
    print("  Loading photo bytes...")
    image_bytes = load_photo_bytes(photo_data.get("path", ""))
    if not image_bytes:
        print("  ERROR: Could not load photo bytes")
        return {"photo_id": photo_id, "error": "Could not load photo", "label": label}

    print(f"  Photo size: {len(image_bytes):,} bytes")

    # Build face detections
    print("  Building face detections...")
    faces = get_faces_for_photo(photo_id, photo_data, identities)
    print(f"  Found {len(faces)} faces with bboxes")
    for f in faces:
        name_str = f" ({f.identity_name})" if f.identity_name else ""
        print(f"    Face {f.face_index}: bbox={f.bbox}{name_str}")

    # Run alignment
    print("  Calling Gemini API...")
    start = time.time()
    result = await run_face_alignment(
        photo_id=photo_id,
        image_bytes=image_bytes,
        faces=faces,
        model="gemini-3.1-pro-preview",
    )
    elapsed = time.time() - start

    # Report results
    if result.error:
        print(f"  ERROR: {result.error}")
        return {"photo_id": photo_id, "error": result.error, "label": label}

    print(f"\n  Results ({elapsed:.1f}s):")
    print(f"  Faces detected: {result.faces_detected}")
    print(f"  Faces described: {result.faces_described}")
    print(f"  Input tokens: {result.input_tokens}")
    print(f"  Output tokens: {result.output_tokens}")
    print(f"  Scene: {result.scene_context[:100]}...")

    cost = (result.input_tokens * 1.25 / 1_000_000) + (result.output_tokens * 10.0 / 1_000_000)
    print(f"  Estimated cost: ${cost:.4f}")

    for af in result.aligned_faces:
        subject_str = "" if af.is_subject else " [NOT SUBJECT]"
        name_str = f" ({af.identity_name})" if af.identity_name else ""
        print(f"\n  Face {af.face_index}{name_str}{subject_str}:")
        print(f"    Age: {af.estimated_age}")
        print(f"    Gender: {af.gender}")
        print(f"    Description: {af.gemini_description[:80]}...")
        print(f"    Clothing: {af.clothing[:60] if af.clothing else 'N/A'}...")
        print(f"    Position: {af.position_in_photo}")

    if result.unmatched_faces:
        print(f"\n  Unmatched faces: {result.unmatched_faces}")
    if result.gemini_only_faces:
        print(f"\n  Gemini-only faces: {len(result.gemini_only_faces)}")
        for gf in result.gemini_only_faces:
            print(f"    - {gf.get('description', 'N/A')}")

    return {
        "photo_id": photo_id,
        "label": label,
        "faces_detected": result.faces_detected,
        "faces_described": result.faces_described,
        "aligned_count": len(result.aligned_faces),
        "unmatched_count": len(result.unmatched_faces),
        "gemini_only_count": len(result.gemini_only_faces),
        "elapsed_seconds": round(elapsed, 1),
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "cost": round(cost, 4),
        "scene_context": result.scene_context,
        "error": None,
        "result": result.to_dict(),
    }


async def main():
    # Load data
    with open("data/photo_index.json") as f:
        pi = json.load(f)
    with open("data/identities.json") as f:
        identities = json.load(f)

    # Check API key
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not set")
        sys.exit(1)
    print(f"GEMINI_API_KEY: {api_key[:10]}...")

    # Test photos
    test_cases = [
        ("2-face Vida Capeluto", "f50118e7db8d6ac5"),
        ("8-face Betty (with confirmed)", "inbox_b5e8a89e_3_603576015.208878"),
        ("12-face Vida group", "8f6a6a0108f019cf"),
    ]

    results = []
    total_cost = 0.0

    for label, photo_id in test_cases:
        photo = pi.get("photos", {}).get(photo_id)
        if not photo:
            print(f"\nERROR: Photo {photo_id} not found in photo_index")
            continue

        result = await test_photo(photo_id, photo, identities, label)
        results.append(result)
        if result.get("cost"):
            total_cost += result["cost"]

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Total photos tested: {len(results)}")
    print(f"Total cost: ${total_cost:.4f}")
    print()

    for r in results:
        status = "PASS" if not r.get("error") else f"FAIL: {r['error']}"
        print(f"  {r['label']}: {status}")
        if not r.get("error"):
            print(f"    Faces: {r['faces_detected']} detected, {r['faces_described']} described, "
                  f"{r['aligned_count']} aligned")
            print(f"    Time: {r['elapsed_seconds']}s, Cost: ${r['cost']:.4f}")

    # Save results
    output_path = Path("results/face_alignment_test_session63.json")
    output_path.parent.mkdir(exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
