#!/usr/bin/env python3
"""Compare local InsightFace embeddings with ML service embeddings.

Session 120 Phase 1: Validates that the ML service produces identical
(or near-identical) embeddings to local InsightFace for the same photo.

Usage:
    # Compare local vs ML service
    python scripts/compare_ml_embeddings.py --photo raw_photos/test.jpg

    # Local-only (no ML service call)
    python scripts/compare_ml_embeddings.py --photo raw_photos/test.jpg --local-only

Requires:
    ML_SERVICE_URL + ML_SERVICE_TOKEN env vars for ML service path.
    InsightFace models installed locally.

Exit codes:
    0 — All matched face pairs have cosine similarity >= 0.999
    1 — At least one pair below threshold, or other error
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.999


def compute_cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    """Cosine similarity of two vectors. For L2-normed vectors, equals dot product."""
    return float(np.dot(vec_a, vec_b))


def compute_iou(bbox_a: list, bbox_b: list) -> float:
    """Compute Intersection over Union of two bounding boxes [x1, y1, x2, y2]."""
    x1 = max(bbox_a[0], bbox_b[0])
    y1 = max(bbox_a[1], bbox_b[1])
    x2 = min(bbox_a[2], bbox_b[2])
    y2 = min(bbox_a[3], bbox_b[3])

    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    if intersection == 0:
        return 0.0

    area_a = (bbox_a[2] - bbox_a[0]) * (bbox_a[3] - bbox_a[1])
    area_b = (bbox_b[2] - bbox_b[0]) * (bbox_b[3] - bbox_b[1])
    union = area_a + area_b - intersection

    return intersection / union if union > 0 else 0.0


def match_faces_by_order_and_iou(
    local_faces: list[dict],
    remote_faces: list[dict],
    iou_threshold: float = 0.5,
) -> list[tuple[int, int]]:
    """Match local and remote faces by detection order, with IoU fallback.

    Primary: match by index (same model, same det_size -> same order).
    Fallback: if counts differ, match by highest IoU on bounding boxes.

    Returns list of (local_idx, remote_idx) pairs.
    """
    if len(local_faces) == len(remote_faces):
        # Same count — match by detection order
        return list(zip(range(len(local_faces)), range(len(remote_faces))))

    # Different counts — use IoU matching
    matched = []
    used_remote = set()

    for li, local_face in enumerate(local_faces):
        local_bbox = local_face.get("bbox", [0, 0, 0, 0])
        best_iou = 0.0
        best_ri = -1

        for ri, remote_face in enumerate(remote_faces):
            if ri in used_remote:
                continue
            remote_bbox = remote_face.get("bbox", [0, 0, 0, 0])
            iou = compute_iou(local_bbox, remote_bbox)
            if iou > best_iou:
                best_iou = iou
                best_ri = ri

        if best_ri >= 0 and best_iou >= iou_threshold:
            matched.append((li, best_ri))
            used_remote.add(best_ri)

    return matched


def extract_local_faces(photo_path: Path) -> list[dict]:
    """Run local InsightFace face detection and return PFE dicts."""
    from core.ingest_inbox import extract_faces

    faces, width, height = extract_faces(photo_path)
    logger.info(f"Local: detected {len(faces)} face(s) in {photo_path.name} ({width}x{height})")
    return faces


async def extract_remote_faces(photo_path: Path) -> list[dict]:
    """Call ML service for face detection and return face dicts."""
    from core.ml_client import MLServiceClient

    client = MLServiceClient()
    if not client.is_configured:
        raise RuntimeError("ML service not configured. Set ML_SERVICE_URL and ML_SERVICE_TOKEN env vars.")

    result = await client.detect_and_embed(str(photo_path))
    faces = result.get("faces", [])
    image_size = result.get("image_size", {})
    processing_time = result.get("processing_time_ms", "?")

    if isinstance(image_size, dict):
        w, h = image_size.get("width", 0), image_size.get("height", 0)
    else:
        w, h = image_size[0], image_size[1]

    logger.info(f"Remote: detected {len(faces)} face(s) in {photo_path.name} ({w}x{h}, {processing_time}ms)")
    await client.close()
    return faces


def extract_remote_faces_via_url(photo_path: Path, base_url: str) -> list[dict]:
    """Call admin compare endpoint for face detection. No ML_SERVICE_URL needed.

    Session 121: Allows running comparison from local machine by proxying
    through the web app's /api/admin/ml-compare endpoint.
    """
    import requests

    url = f"{base_url.rstrip('/')}/api/admin/ml-compare"
    with open(photo_path, "rb") as f:
        resp = requests.post(url, files={"file": (photo_path.name, f, "image/jpeg")}, timeout=180)
    resp.raise_for_status()
    result = resp.json()

    if "error" in result:
        raise RuntimeError(f"Admin compare endpoint error: {result['error']}")

    faces = result.get("faces", [])
    image_size = result.get("image_size", {})
    processing_time = result.get("processing_time_ms", "?")

    if isinstance(image_size, dict):
        w, h = image_size.get("width", 0), image_size.get("height", 0)
    elif isinstance(image_size, list) and len(image_size) >= 2:
        w, h = image_size[0], image_size[1]
    else:
        w, h = 0, 0

    logger.info(f"Remote (via {base_url}): {len(faces)} face(s) in {photo_path.name} ({w}x{h}, {processing_time}ms)")
    return faces


def compare_embeddings(
    local_faces: list[dict],
    remote_faces: list[dict],
) -> list[dict]:
    """Compare matched face pairs and return comparison results.

    Returns list of dicts with: local_idx, remote_idx, cosine_similarity, pass.
    """
    matches = match_faces_by_order_and_iou(local_faces, remote_faces)

    results = []
    for li, ri in matches:
        local_emb = np.asarray(local_faces[li]["mu"], dtype=np.float32)
        remote_emb = np.asarray(remote_faces[ri]["embedding"], dtype=np.float32)

        # Ensure normalization
        local_norm = np.linalg.norm(local_emb)
        remote_norm = np.linalg.norm(remote_emb)
        if local_norm > 0:
            local_emb = local_emb / local_norm
        if remote_norm > 0:
            remote_emb = remote_emb / remote_norm

        similarity = compute_cosine_similarity(local_emb, remote_emb)
        results.append(
            {
                "local_idx": li,
                "remote_idx": ri,
                "cosine_similarity": similarity,
                "pass": similarity >= SIMILARITY_THRESHOLD,
                "local_bbox": local_faces[li].get("bbox"),
                "remote_bbox": remote_faces[ri].get("bbox"),
            }
        )

    return results


def check_exit_code(results: list[dict]) -> int:
    """Return 0 if all pairs pass threshold, 1 otherwise."""
    if not results:
        return 1  # No matches = failure
    return 0 if all(r["pass"] for r in results) else 1


def main():
    parser = argparse.ArgumentParser(description="Compare local InsightFace vs ML service embeddings")
    parser.add_argument(
        "--photo",
        type=Path,
        required=True,
        help="Path to photo file",
    )
    parser.add_argument(
        "--local-only",
        action="store_true",
        help="Only run local detection (no ML service call)",
    )
    parser.add_argument(
        "--url",
        type=str,
        default=None,
        help="Base URL of the web app (e.g., https://rhodesli.nolanandrewfox.com). "
        "Uses /api/admin/ml-compare endpoint instead of direct ML service.",
    )
    args = parser.parse_args()

    if not args.photo.exists():
        logger.error(f"Photo not found: {args.photo}")
        sys.exit(1)

    # Local detection
    local_faces = extract_local_faces(args.photo)

    if args.local_only:
        print("\n=== Local-Only Mode ===")
        print(f"Detected {len(local_faces)} face(s)")
        for i, face in enumerate(local_faces):
            emb = np.asarray(face["mu"], dtype=np.float32)
            norm = float(np.linalg.norm(emb))
            print(
                f"  Face {i}: bbox={face.get('bbox')}, det_score={face.get('det_score', '?'):.4f}, emb_norm={norm:.6f}"
            )
        sys.exit(0)

    # Remote detection — via admin endpoint or direct ML service
    if args.url:
        remote_faces = extract_remote_faces_via_url(args.photo, args.url)
    else:
        remote_faces = asyncio.run(extract_remote_faces(args.photo))

    # Compare
    results = compare_embeddings(local_faces, remote_faces)

    # Report
    print(f"\n=== Embedding Comparison: {args.photo.name} ===")
    print(f"Local faces: {len(local_faces)}, Remote faces: {len(remote_faces)}, Matched pairs: {len(results)}")
    print(f"Threshold: {SIMILARITY_THRESHOLD}")
    print()

    all_pass = True
    for r in results:
        status = "PASS" if r["pass"] else "FAIL"
        if not r["pass"]:
            all_pass = False
        iou = compute_iou(r["local_bbox"], r["remote_bbox"]) if r["local_bbox"] and r["remote_bbox"] else 0.0
        print(
            f"  Face {r['local_idx']}↔{r['remote_idx']}: similarity={r['cosine_similarity']:.6f}  bbox_iou={iou:.4f}  [{status}]"
        )

    # Report unmatched faces
    matched_local = {r["local_idx"] for r in results}
    matched_remote = {r["remote_idx"] for r in results}
    unmatched_local = set(range(len(local_faces))) - matched_local
    unmatched_remote = set(range(len(remote_faces))) - matched_remote

    if unmatched_local:
        print(f"\n  Unmatched local faces: {sorted(unmatched_local)}")
        all_pass = False
    if unmatched_remote:
        print(f"  Unmatched remote faces: {sorted(unmatched_remote)}")
        all_pass = False

    print(f"\nOverall: {'PASS' if all_pass else 'FAIL'}")
    exit_code = check_exit_code(results)
    if unmatched_local or unmatched_remote:
        exit_code = 1
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
