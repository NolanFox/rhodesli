#!/usr/bin/env python3
"""
Session 63 Phase 8: Batch face alignment for all photos.

Runs Gemini face alignment on all 271 photos with:
- Model: gemini-3.1-pro-preview
- GEDCOM variant: curated (when available)
- Face coordinate bridging
- Results stored versioned locally

Usage:
    python scripts/run_batch_alignment.py --limit 5  # validation
    python scripts/run_batch_alignment.py --execute    # all photos
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.face_alignment import (
    FaceDetection,
    run_face_alignment,
    save_alignment_to_file,
)

logger = logging.getLogger(__name__)


def load_photo_bytes(photo_path: str) -> bytes | None:
    """Load photo from local filesystem or R2."""
    local_path = PROJECT_ROOT / "raw_photos" / Path(photo_path).name
    if local_path.exists():
        return local_path.read_bytes()

    r2_url = os.getenv("R2_PUBLIC_URL", "")
    if r2_url:
        filename = Path(photo_path).name
        url = f"{r2_url}/raw_photos/{urllib.parse.quote(filename)}"
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                return resp.read()
        except Exception as e:
            logger.warning(f"R2 load failed for {filename}: {e}")

    return None


def build_faces_for_photo(photo_data: dict, identities: dict, embeddings) -> list[FaceDetection]:
    """Build FaceDetection objects from photo + embeddings data."""
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

    # Match face_ids to embeddings by filename
    face_embs = [e for e in embeddings if e.get("filename", "") == filename]

    faces = []
    for i, face_id in enumerate(face_ids):
        bbox = None
        det_score = 0.0
        quality = 0.0

        # Try explicit face_id match first
        for emb in embeddings:
            if emb.get("face_id") == face_id:
                bbox_raw = emb.get("bbox", [0, 0, 0, 0])
                bbox = [int(b) for b in bbox_raw]
                det_score = float(emb.get("det_score", 0))
                quality = float(emb.get("quality", 0))
                break

        # Fallback: match by filename index
        if bbox is None and i < len(face_embs):
            emb = face_embs[i]
            bbox_raw = emb.get("bbox", [0, 0, 0, 0])
            bbox = [int(b) for b in bbox_raw]
            det_score = float(emb.get("det_score", 0))
            quality = float(emb.get("quality", 0))

        if bbox is None:
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


async def process_photo(photo_id: str, photo_data: dict, identities: dict,
                        embeddings, model: str) -> dict:
    """Process a single photo through the alignment pipeline."""
    filename = Path(photo_data.get("path", "")).name

    # Build faces
    faces = build_faces_for_photo(photo_data, identities, embeddings)
    if not faces:
        return {"photo_id": photo_id, "status": "skipped", "reason": "no faces with bboxes"}

    # Load image bytes
    image_bytes = load_photo_bytes(photo_data.get("path", ""))
    if not image_bytes:
        return {"photo_id": photo_id, "status": "skipped", "reason": "could not load image"}

    # Run alignment
    start = time.time()
    try:
        result = await run_face_alignment(
            photo_id=photo_id,
            image_bytes=image_bytes,
            faces=faces,
            model=model,
        )
    except Exception as e:
        return {"photo_id": photo_id, "status": "error", "reason": str(e)}

    elapsed = time.time() - start

    if result.error:
        return {"photo_id": photo_id, "status": "error", "reason": result.error}

    # Save result
    save_alignment_to_file(result, output_dir=PROJECT_ROOT / "data")

    # Estimate cost
    cost = (result.input_tokens * 1.25 / 1_000_000) + (result.output_tokens * 10.0 / 1_000_000)

    return {
        "photo_id": photo_id,
        "status": "success",
        "faces_detected": result.faces_detected,
        "faces_described": result.faces_described,
        "elapsed": round(elapsed, 1),
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "cost": round(cost, 4),
    }


async def main():
    parser = argparse.ArgumentParser(description="Batch face alignment")
    parser.add_argument('--limit', type=int, default=5, help='Max photos to process (default: 5 validation)')
    parser.add_argument('--execute', action='store_true', help='Process all photos (overrides --limit)')
    parser.add_argument('--model', default='gemini-3.1-pro-preview')
    parser.add_argument('--delay', type=float, default=2.0, help='Delay between API calls (seconds)')
    parser.add_argument('--skip-aligned', action='store_true', help='Skip already aligned photos')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    # Check API key
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        logger.error("GEMINI_API_KEY not set")
        sys.exit(1)

    # Load data
    with open(PROJECT_ROOT / "data" / "photo_index.json") as f:
        photo_index = json.load(f)
    with open(PROJECT_ROOT / "data" / "identities.json") as f:
        identities = json.load(f)

    embeddings = np.load(str(PROJECT_ROOT / "data" / "embeddings.npy"), allow_pickle=True)

    photos = photo_index.get("photos", {})
    logger.info(f"Total photos: {len(photos)}")

    # Filter to photos with faces
    eligible = {pid: p for pid, p in photos.items() if p.get("face_ids")}
    logger.info(f"Photos with faces: {len(eligible)}")

    # Skip already aligned if requested
    if args.skip_aligned:
        from app.face_alignment import load_alignments_from_file
        existing = load_alignments_from_file(PROJECT_ROOT / "data")
        before = len(eligible)
        eligible = {pid: p for pid, p in eligible.items() if pid not in existing}
        logger.info(f"After skipping aligned: {len(eligible)} (skipped {before - len(eligible)})")

    # Apply limit
    limit = len(eligible) if args.execute else args.limit
    photo_list = list(eligible.items())[:limit]
    logger.info(f"Processing {len(photo_list)} photos with {args.model}")

    # Process
    results = []
    total_cost = 0.0
    success = 0
    errors = 0
    skipped = 0

    for i, (pid, pdata) in enumerate(photo_list):
        logger.info(f"[{i+1}/{len(photo_list)}] {pid} ({len(pdata.get('face_ids', []))} faces)")
        result = await process_photo(pid, pdata, identities, embeddings, args.model)
        results.append(result)

        if result["status"] == "success":
            success += 1
            total_cost += result.get("cost", 0)
            logger.info(f"  ✓ {result['faces_described']}/{result['faces_detected']} faces, "
                        f"${result['cost']:.4f}, {result['elapsed']}s")
        elif result["status"] == "skipped":
            skipped += 1
            logger.info(f"  ⊘ Skipped: {result['reason']}")
        else:
            errors += 1
            logger.error(f"  ✗ Error: {result['reason']}")

        # Rate limit
        if i < len(photo_list) - 1:
            await asyncio.sleep(args.delay)

    # Summary
    logger.info(f"\n{'='*60}")
    logger.info(f"BATCH COMPLETE")
    logger.info(f"{'='*60}")
    logger.info(f"Success: {success}/{len(photo_list)}")
    logger.info(f"Errors: {errors}")
    logger.info(f"Skipped: {skipped}")
    logger.info(f"Total cost: ${total_cost:.4f}")

    # Save results
    output = PROJECT_ROOT / "results" / f"batch_alignment_{time.strftime('%Y%m%d_%H%M%S')}.json"
    with open(output, "w") as f:
        json.dump({
            "model": args.model,
            "total_photos": len(photo_list),
            "success": success,
            "errors": errors,
            "skipped": skipped,
            "total_cost": round(total_cost, 4),
            "results": results,
        }, f, indent=2)
    logger.info(f"Results saved to {output}")


if __name__ == '__main__':
    asyncio.run(main())
