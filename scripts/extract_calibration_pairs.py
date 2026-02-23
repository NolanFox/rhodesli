#!/usr/bin/env python3
"""
Session 63 Phase 5: Extract ground truth pairs for calibration.

Match pairs: faces confirmed as same person (admin merges).
Non-match pairs: faces from different confirmed identities (implicit negatives).

Usage:
    python scripts/extract_calibration_pairs.py --dry-run
    python scripts/extract_calibration_pairs.py --execute
"""

import argparse
import json
import logging
import os
import random
import sys
from itertools import combinations
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger(__name__)


def compute_cosine_similarity(emb_a: np.ndarray, emb_b: np.ndarray) -> float:
    """Compute cosine similarity between two embeddings."""
    dot = np.dot(emb_a, emb_b)
    norm_a = np.linalg.norm(emb_a)
    norm_b = np.linalg.norm(emb_b)
    if norm_a < 1e-10 or norm_b < 1e-10:
        return 0.0
    return float(dot / (norm_a * norm_b))


def load_embeddings_map() -> dict:
    """Load embeddings and build face_id -> embedding vector map."""
    emb_path = PROJECT_ROOT / "data" / "embeddings.npy"
    embeddings = np.load(str(emb_path), allow_pickle=True)

    face_map = {}
    for emb in embeddings:
        face_id = emb.get("face_id", "")
        if not face_id:
            # Generate face_id from filename + index
            filename = emb.get("filename", "")
            # Try to match by position
            continue

        embedding = emb.get("embeddings")
        if embedding is None:
            continue

        if isinstance(embedding, dict):
            # PFE format: get mean vector
            mu = embedding.get("mu") or embedding.get("mean")
            if mu is not None:
                face_map[face_id] = np.array(mu, dtype=np.float32)
        elif isinstance(embedding, (list, np.ndarray)):
            arr = np.array(embedding, dtype=np.float32)
            if arr.ndim == 1:
                face_map[face_id] = arr
            elif arr.ndim == 2 and arr.shape[0] == 1:
                face_map[face_id] = arr[0]

    return face_map


def load_embeddings_map_v2() -> dict:
    """V2: handle both explicit face_id and generated face_ids."""
    emb_path = PROJECT_ROOT / "data" / "embeddings.npy"
    embeddings = np.load(str(emb_path), allow_pickle=True)

    # Load photo_index for face_id resolution
    with open(PROJECT_ROOT / "data" / "photo_index.json") as f:
        pi = json.load(f)

    # Build filename -> face_ids mapping
    face_map = {}

    # First pass: explicit face_ids
    for emb in embeddings:
        face_id = emb.get("face_id", "")
        if face_id:
            embedding = _extract_vector(emb)
            if embedding is not None:
                face_map[face_id] = embedding

    # Second pass: generate face_ids for legacy entries
    filename_groups = {}
    for emb in embeddings:
        fn = emb.get("filename", "")
        if fn:
            filename_groups.setdefault(fn, []).append(emb)

    for fn, entries in filename_groups.items():
        for i, emb in enumerate(entries):
            if emb.get("face_id"):
                continue  # Already handled
            # Generate legacy face_id
            stem = Path(fn).stem
            face_id = f"{stem}:face{i}"
            embedding = _extract_vector(emb)
            if embedding is not None:
                face_map[face_id] = embedding

    return face_map


def _extract_vector(emb_entry: dict) -> np.ndarray | None:
    """Extract the embedding vector from various formats.

    Rhodesli embeddings use PFE format with top-level 'mu' key.
    """
    # Primary format: top-level 'mu' (PFE mean vector)
    mu = emb_entry.get("mu")
    if mu is not None:
        if isinstance(mu, np.ndarray):
            return mu.astype(np.float32)
        return np.array(mu, dtype=np.float32)

    # Fallback: 'embeddings' key (some formats)
    embedding = emb_entry.get("embeddings")
    if embedding is None:
        return None

    if isinstance(embedding, dict):
        mu = embedding.get("mu") or embedding.get("mean")
        if mu is not None:
            return np.array(mu, dtype=np.float32)
        return None

    arr = np.array(embedding, dtype=np.float32)
    if arr.ndim == 1:
        return arr
    elif arr.ndim == 2 and arr.shape[0] == 1:
        return arr[0]
    return None


def extract_match_pairs(identities: dict, face_map: dict) -> list:
    """
    Extract match pairs from confirmed identities.

    For every identity with 2+ faces: compute similarity between
    all face pairs and create match entries.
    """
    pairs = []

    for iid, identity in identities.get("identities", {}).items():
        if identity.get("state") != "CONFIRMED":
            continue

        anchor_ids = identity.get("anchor_ids", [])
        if len(anchor_ids) < 2:
            continue

        # Get embeddings for all faces
        face_embeddings = {}
        for fid in anchor_ids:
            if fid in face_map:
                face_embeddings[fid] = face_map[fid]

        if len(face_embeddings) < 2:
            continue

        # All pairs
        face_ids = list(face_embeddings.keys())
        for fa, fb in combinations(face_ids, 2):
            sim = compute_cosine_similarity(face_embeddings[fa], face_embeddings[fb])
            # Canonical ordering
            pair = (min(fa, fb), max(fa, fb))
            pairs.append({
                "face_id_a": pair[0],
                "face_id_b": pair[1],
                "similarity_score": round(sim, 6),
                "is_match": True,
                "source": "admin_merge",
                "weight": 1.0,
            })

    return pairs


def extract_nonmatch_pairs(
    identities: dict,
    face_map: dict,
    target_count: int = None,
    seed: int = 42,
) -> list:
    """
    Extract non-match pairs from different confirmed identities.

    Strategy:
    - Pick one face per person
    - For each pair of different people: compute similarity
    - Prioritize hard negatives (similarity > 0.3) and easy negatives (< 0.2)
    - Target ~1:1 ratio with match pairs
    """
    random.seed(seed)

    # Get one face per confirmed identity
    identity_faces = {}
    for iid, identity in identities.get("identities", {}).items():
        if identity.get("state") != "CONFIRMED":
            continue
        anchor_ids = identity.get("anchor_ids", [])
        for fid in anchor_ids:
            if fid in face_map:
                identity_faces[iid] = (fid, face_map[fid], identity.get("name", "Unknown"))
                break

    if len(identity_faces) < 2:
        return []

    # Compute all pairs between different people
    all_pairs = []
    identity_ids = list(identity_faces.keys())
    for ia, ib in combinations(identity_ids, 2):
        fa, emb_a, name_a = identity_faces[ia]
        fb, emb_b, name_b = identity_faces[ib]
        sim = compute_cosine_similarity(emb_a, emb_b)
        pair = (min(fa, fb), max(fa, fb))
        all_pairs.append({
            "face_id_a": pair[0],
            "face_id_b": pair[1],
            "similarity_score": round(sim, 6),
            "is_match": False,
            "source": "implicit_different_id",
            "weight": 1.0,
        })

    if target_count and len(all_pairs) > target_count:
        # Stratified sampling: prioritize hard negatives
        hard = [p for p in all_pairs if p["similarity_score"] > 0.3]
        easy = [p for p in all_pairs if p["similarity_score"] < 0.2]
        medium = [p for p in all_pairs if 0.2 <= p["similarity_score"] <= 0.3]

        selected = []
        # Take all hard negatives (most informative)
        selected.extend(hard)
        # Fill with easy negatives
        remaining = target_count - len(selected)
        if remaining > 0 and easy:
            selected.extend(random.sample(easy, min(len(easy), remaining // 2)))
        remaining = target_count - len(selected)
        if remaining > 0 and medium:
            selected.extend(random.sample(medium, min(len(medium), remaining)))
        return selected[:target_count]

    return all_pairs


def main():
    parser = argparse.ArgumentParser(description="Extract calibration pairs")
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(levelname)s: %(message)s'
    )

    # Load data
    with open(PROJECT_ROOT / "data" / "identities.json") as f:
        identities = json.load(f)

    logger.info("Loading embeddings...")
    face_map = load_embeddings_map_v2()
    logger.info(f"Loaded {len(face_map)} face embeddings")

    # Extract match pairs
    match_pairs = extract_match_pairs(identities, face_map)
    logger.info(f"Match pairs: {len(match_pairs)}")

    # Show score distribution
    if match_pairs:
        scores = [p["similarity_score"] for p in match_pairs]
        logger.info(f"  Score range: {min(scores):.3f} - {max(scores):.3f}")
        logger.info(f"  Mean: {sum(scores)/len(scores):.3f}")

    # Extract non-match pairs (target 1:1 ratio)
    nonmatch_pairs = extract_nonmatch_pairs(
        identities, face_map,
        target_count=max(len(match_pairs), 50),
    )
    logger.info(f"Non-match pairs: {len(nonmatch_pairs)}")

    if nonmatch_pairs:
        scores = [p["similarity_score"] for p in nonmatch_pairs]
        logger.info(f"  Score range: {min(scores):.3f} - {max(scores):.3f}")
        logger.info(f"  Mean: {sum(scores)/len(scores):.3f}")
        hard = sum(1 for s in scores if s > 0.3)
        logger.info(f"  Hard negatives (>0.3): {hard}")

    all_pairs = match_pairs + nonmatch_pairs
    logger.info(f"\nTotal pairs: {len(all_pairs)} ({len(match_pairs)} match, {len(nonmatch_pairs)} non-match)")

    if not args.execute:
        logger.info("DRY RUN — use --execute to insert into Supabase")
        # Save locally
        output = PROJECT_ROOT / "results" / "calibration_pairs_session63.json"
        with open(output, "w") as f:
            json.dump({"pairs": all_pairs, "stats": {
                "match": len(match_pairs),
                "nonmatch": len(nonmatch_pairs),
                "total": len(all_pairs),
            }}, f, indent=2)
        logger.info(f"Saved to {output}")
        return

    # Insert into Supabase
    import httpx
    url = os.environ['SUPABASE_URL']
    key = os.environ['SUPABASE_SERVICE_ROLE_KEY']

    from supabase import create_client
    sb = create_client(url, key)

    # Upsert in batches
    for i in range(0, len(all_pairs), 500):
        chunk = all_pairs[i:i + 500]
        sb.table('calibration_pairs').upsert(
            chunk, on_conflict='face_id_a,face_id_b'
        ).execute()
        logger.info(f"  Upserted {min(i + 500, len(all_pairs))}/{len(all_pairs)} pairs")

    logger.info(f"Inserted {len(all_pairs)} calibration pairs into Supabase")

    # Save results file
    output = PROJECT_ROOT / "results" / "calibration_pairs_session63.json"
    with open(output, "w") as f:
        json.dump({"pairs": all_pairs, "stats": {
            "match": len(match_pairs),
            "nonmatch": len(nonmatch_pairs),
            "total": len(all_pairs),
        }}, f, indent=2)
    logger.info(f"Results saved to {output}")


if __name__ == '__main__':
    main()
