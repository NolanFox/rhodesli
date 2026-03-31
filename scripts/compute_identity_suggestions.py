#!/usr/bin/env python3
"""
Compute identity suggestions using multi-signal evidence (PRD-059 Phase 4).

For each unidentified person in a target community, scores against a confirmed
family using: family_cluster, co_occurrence, age_trajectory, gedcom_match,
testimony, and provenance signals.

Usage:
    python scripts/compute_identity_suggestions.py --family fox --dry-run
    python scripts/compute_identity_suggestions.py --family fox --execute

Reads from: Supabase (identities, photo_faces, date_labels, co_occurrence_pairs,
            gedcom_individuals), local embeddings.npy
Writes to: Supabase identity_suggestions table (only in --execute mode)

See: AD-235, PRD-059 Phase 4 SDD
"""

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np

# Project root
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Load .env
env_path = ROOT / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            import os

            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("'\"")
            if key not in os.environ:
                os.environ[key] = value


# --- Family Configuration ---

FAMILY_CONFIG = {
    "fox": {
        "community_id": "ce335470-0d96-4524-af9c-1ef815e708e4",  # fox-family
        "threshold": 1.35,  # AD-235: per-family calibrated
        "confirmed_names": [
            "Albert Fox",
            "Esther Burd Fox",
            "Charles Fox",
            "Roland Fox",
            "Rose Weiss Baygel Fox",
            "Harry Fox",
            "Bessie Fox",
            "Rachel Fox Newman",
        ],
    },
}


# --- Signal Computation Functions ---


def compute_family_cluster_score(
    target_centroid: np.ndarray,
    family_centroids: dict[str, np.ndarray],
    threshold: float = 1.35,
) -> dict:
    """AD-235: Mean L2 distance from target to all confirmed family members.

    Returns dict with score (0.0-1.0), raw_distance, closest_member, etc.
    Score = 1.0 at distance 0.8, 0.0 at threshold + 0.2.
    """
    if not family_centroids:
        return {"score": 0.0, "raw_distance": None, "n_family_members": 0}

    distances = {}
    for name, centroid in family_centroids.items():
        dist = float(np.linalg.norm(target_centroid - centroid))
        distances[name] = dist

    mean_distance = np.mean(list(distances.values()))
    closest_name = min(distances, key=distances.get)
    closest_dist = distances[closest_name]

    # Normalize: 1.0 at distance 0.8, 0.0 at threshold + 0.2
    low, high = 0.8, threshold + 0.2
    score = max(0.0, min(1.0, 1.0 - (mean_distance - low) / (high - low)))

    return {
        "score": round(score, 3),
        "raw_distance": round(mean_distance, 4),
        "threshold": threshold,
        "n_family_members": len(family_centroids),
        "closest_member": closest_name,
        "closest_distance": round(closest_dist, 4),
        "n_within_threshold": sum(1 for d in distances.values() if d < threshold),
    }


def compute_co_occurrence_score(
    target_id: str,
    family_ids: set[str],
    co_occurrence_pairs: dict,
) -> dict:
    """Score based on how often target appears in photos with family members."""
    shared = 0
    top_co = []
    for fid in family_ids:
        key = tuple(sorted([target_id, fid]))
        count = co_occurrence_pairs.get(key, 0)
        if count > 0:
            shared += count
            top_co.append({"identity_id": fid, "count": count})

    top_co.sort(key=lambda x: -x["count"])

    # Score: 0.0 at 0 shared, 1.0 at 10+ shared photos
    score = min(1.0, shared / 10.0) if shared > 0 else 0.0

    return {
        "score": round(score, 3),
        "shared_photos_with_family": shared,
        "top_co_occurring": top_co[:5],
    }


def compute_age_feasibility(
    target_id: str,
    candidate_birth_year: int | None,
    date_labels: dict,
    photo_faces: dict,
    max_deviation: float = 10.0,
) -> dict:
    """Check if candidate birth year is feasible given photo dates and estimated ages."""
    if candidate_birth_year is None:
        return {"score": 0.5, "reason": "no_candidate_birth_year"}

    # Get photos containing this person
    target_photos = photo_faces.get(target_id, [])
    if not target_photos:
        return {"score": 0.5, "reason": "no_photos"}

    observations = []
    for photo_id in target_photos:
        label = date_labels.get(photo_id)
        if not label:
            continue
        data = label if isinstance(label, dict) else {}
        photo_year = data.get("estimated_year") or data.get("year_estimate")
        if not photo_year:
            continue

        expected_age = photo_year - candidate_birth_year
        if expected_age < 0 or expected_age > 110:
            return {
                "score": 0.0,
                "reason": "impossible_age",
                "photo_year": photo_year,
                "expected_age": expected_age,
                "candidate_birth_year": candidate_birth_year,
            }

        # Check for estimated age in face analysis
        estimated_age = data.get("estimated_age")
        if estimated_age:
            deviation = abs(estimated_age - expected_age)
            observations.append(
                {
                    "photo_year": photo_year,
                    "estimated_age": estimated_age,
                    "expected_age": expected_age,
                    "deviation": round(deviation, 1),
                }
            )

    if not observations:
        return {"score": 0.5, "reason": "no_age_observations", "candidate_birth_year": candidate_birth_year}

    mad = np.mean([o["deviation"] for o in observations])
    score = max(0.0, 1.0 - (mad / max_deviation))

    return {
        "score": round(score, 3),
        "candidate_birth_year": candidate_birth_year,
        "observations": observations[:5],
        "mean_absolute_deviation": round(mad, 2),
    }


def aggregate_evidence(signals: dict, weights: dict | None = None) -> float:
    """Weighted sum of normalized signal scores. Absent signals redistribute weight."""
    default_weights = {
        "testimony": 0.30,
        "family_cluster": 0.25,
        "age_trajectory": 0.20,
        "co_occurrence": 0.10,
        "gedcom_match": 0.10,
        "provenance": 0.05,
    }
    w = weights or default_weights

    # Filter to present signals (score != None)
    present = {k: v for k, v in signals.items() if v.get("score") is not None}
    if not present:
        return 0.0

    # Redistribute absent weights proportionally
    present_weight_sum = sum(w.get(k, 0) for k in present)
    if present_weight_sum == 0:
        return 0.0

    total = 0.0
    for k, evidence in present.items():
        normalized_weight = w.get(k, 0) / present_weight_sum
        total += normalized_weight * evidence["score"]

    return round(total, 4)


# --- Data Loading ---


def load_embeddings() -> dict[str, np.ndarray]:
    """Load embeddings.npy and build face_id -> embedding lookup.

    Handles both formats:
    - Inbox entries: have explicit face_id field
    - Legacy entries: generate face_id from filename + face index
    """
    emb_path = ROOT / "data" / "embeddings.npy"
    if not emb_path.exists():
        logger.error(f"embeddings.npy not found at {emb_path}")
        return {}

    raw = np.load(emb_path, allow_pickle=True)

    # Track face index per filename for legacy ID generation
    filename_counts: dict[str, int] = {}
    lookup = {}

    for entry in raw:
        fid = entry.get("face_id")
        if not fid:
            # Generate legacy face ID: "stem:faceN"
            filename = entry.get("filename", "")
            if not filename:
                continue
            idx = filename_counts.get(filename, 0)
            filename_counts[filename] = idx + 1
            stem = Path(filename).stem
            fid = f"{stem}:face{idx}"

        # Support both PFE format (mu/sigma_sq) and flat format (embeddings)
        emb = entry.get("mu")
        if emb is None:
            emb = entry.get("embeddings")
        if emb is not None:
            emb = np.asarray(emb, dtype=np.float32)
            if emb.ndim == 2:
                emb = emb[0]  # Take first embedding if multi-row
            lookup[fid] = emb
    return lookup


def compute_centroid(face_ids: list[str], embeddings: dict[str, np.ndarray]) -> np.ndarray | None:
    """Compute mean embedding for a set of face IDs."""
    vecs = [embeddings[fid] for fid in face_ids if fid in embeddings]
    if not vecs:
        return None
    return np.mean(vecs, axis=0)


def load_family_members(sb, family_config: dict) -> dict[str, dict]:
    """Load confirmed family members from Supabase."""
    members = {}
    for name in family_config["confirmed_names"]:
        resp = sb.table("identities").select("identity_id,anchor_ids,state").eq("name", name).execute()
        for row in resp.data:
            if row["state"] == "CONFIRMED":
                anchor_ids = row.get("anchor_ids", [])
                if isinstance(anchor_ids, str):
                    anchor_ids = json.loads(anchor_ids)
                members[name] = {
                    "identity_id": row["identity_id"],
                    "anchor_ids": anchor_ids,
                }
                break
    return members


def load_co_occurrence_pairs(sb) -> dict:
    """Load co-occurrence pair counts from Supabase."""
    try:
        resp = sb.table("co_occurrence_pairs").select("identity_a,identity_b,shared_photo_count").execute()
        pairs = {}
        for row in resp.data:
            key = tuple(sorted([row["identity_a"], row["identity_b"]]))
            pairs[key] = row["shared_photo_count"]
        return pairs
    except Exception as e:
        logger.warning(f"Could not load co_occurrence_pairs: {e}")
        return {}


def load_date_labels(sb) -> dict:
    """Load date labels from Supabase."""
    try:
        resp = sb.table("date_labels").select("photo_id,data").execute()
        labels = {}
        for row in resp.data:
            data = row.get("data", {})
            if isinstance(data, str):
                data = json.loads(data)
            labels[row["photo_id"]] = data
        return labels
    except Exception as e:
        logger.warning(f"Could not load date_labels: {e}")
        return {}


def load_photo_faces_by_identity(sb) -> dict:
    """Build identity_id -> [photo_id] mapping."""
    try:
        resp = sb.table("photo_faces").select("face_id,photo_id").execute()
        face_to_photo = {row["face_id"]: row["photo_id"] for row in resp.data}

        # Now get identity -> face mapping
        resp2 = sb.table("identities").select("identity_id,anchor_ids,candidate_ids,state").execute()
        identity_photos = {}
        for row in resp2.data:
            iid = row["identity_id"]
            faces = row.get("anchor_ids", []) or []
            if isinstance(faces, str):
                faces = json.loads(faces)
            candidates = row.get("candidate_ids", []) or []
            if isinstance(candidates, str):
                candidates = json.loads(candidates)
            all_faces = list(set(faces + candidates))
            photos = list(set(face_to_photo.get(fid, None) for fid in all_faces) - {None})
            if photos:
                identity_photos[iid] = photos
        return identity_photos
    except Exception as e:
        logger.warning(f"Could not load photo_faces: {e}")
        return {}


# --- Main Pipeline ---


def run_pipeline(family_name: str, dry_run: bool = True):
    """Run the identity suggestion pipeline for a family."""
    import os

    from supabase import create_client

    # Use service_role key for writes (RLS requires it), fall back to anon for reads
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_ANON_KEY"]
    sb = create_client(os.environ["SUPABASE_URL"], key)

    if family_name not in FAMILY_CONFIG:
        logger.error(f"Unknown family: {family_name}. Available: {list(FAMILY_CONFIG.keys())}")
        return

    config = FAMILY_CONFIG[family_name]
    threshold = config["threshold"]

    # Load data
    logger.info("Loading embeddings...")
    embeddings = load_embeddings()
    logger.info(f"  {len(embeddings)} face embeddings loaded")

    logger.info("Loading family members...")
    family_members = load_family_members(sb, config)
    logger.info(f"  {len(family_members)} confirmed family members: {list(family_members.keys())}")

    # Compute family centroids
    family_centroids = {}
    for name, member in family_members.items():
        centroid = compute_centroid(member["anchor_ids"], embeddings)
        if centroid is not None:
            family_centroids[name] = centroid
    logger.info(f"  {len(family_centroids)} family centroids computed")

    family_identity_ids = {m["identity_id"] for m in family_members.values()}

    logger.info("Loading co-occurrence pairs...")
    co_occurrence_pairs = load_co_occurrence_pairs(sb)
    logger.info(f"  {len(co_occurrence_pairs)} pairs")

    logger.info("Loading date labels...")
    date_labels = load_date_labels(sb)
    logger.info(f"  {len(date_labels)} date labels")

    logger.info("Loading photo-face mappings...")
    identity_photos = load_photo_faces_by_identity(sb)
    logger.info(f"  {len(identity_photos)} identities with photos")

    # Get all unidentified people in the community
    community_id = config["community_id"]
    logger.info(f"Loading community identities (community_id={community_id})...")

    ic_resp = sb.table("identity_communities").select("identity_id").eq("community_id", community_id).execute()
    community_identity_ids = {row["identity_id"] for row in ic_resp.data}

    # Also include Fox family community
    fox_community_id = "ce335470-0d96-4524-af9c-1ef815e708e4"
    if community_id != fox_community_id:
        fox_resp = sb.table("identity_communities").select("identity_id").eq("community_id", fox_community_id).execute()
        community_identity_ids |= {row["identity_id"] for row in fox_resp.data}

    logger.info(f"  {len(community_identity_ids)} community identities")

    # Filter to unidentified (not CONFIRMED, not merged)
    all_ids_resp = (
        sb.table("identities").select("identity_id,name,state,anchor_ids,candidate_ids,merged_into").execute()
    )
    candidates = []
    for row in all_ids_resp.data:
        iid = row["identity_id"]
        if iid not in community_identity_ids:
            continue
        if iid in family_identity_ids:
            continue  # Skip confirmed family members
        if row.get("merged_into"):
            continue  # Skip merged
        if row["state"] == "CONFIRMED":
            continue  # Skip already confirmed

        faces = row.get("anchor_ids", []) or []
        if isinstance(faces, str):
            faces = json.loads(faces)
        cands = row.get("candidate_ids", []) or []
        if isinstance(cands, str):
            cands = json.loads(cands)
        all_faces = list(set(faces + cands))

        centroid = compute_centroid(all_faces, embeddings)
        if centroid is not None:
            candidates.append(
                {
                    "identity_id": iid,
                    "name": row["name"],
                    "centroid": centroid,
                    "face_ids": all_faces,
                }
            )

    logger.info(f"  {len(candidates)} unidentified candidates to score")

    # Score each candidate
    suggestions = []
    for cand in candidates:
        # Signal 1: Family Cluster Score
        family_score = compute_family_cluster_score(cand["centroid"], family_centroids, threshold)

        # Only proceed if within family threshold (skip obvious non-family)
        if family_score["raw_distance"] is not None and family_score["raw_distance"] > threshold + 0.3:
            continue

        # Signal 2: Co-occurrence
        co_score = compute_co_occurrence_score(cand["identity_id"], family_identity_ids, co_occurrence_pairs)

        # Signal 3: Age trajectory (placeholder — needs GEDCOM candidate matching)
        age_score = {"score": 0.5, "reason": "not_yet_implemented"}

        # Signal 4: GEDCOM match (placeholder)
        gedcom_score = {"score": 0.5, "reason": "not_yet_implemented"}

        # Signal 5: Testimony (placeholder)
        testimony_score = {"score": 0.0, "entries": []}

        # Signal 6: Provenance (placeholder)
        provenance_score = {"score": 0.0, "labels": []}

        evidence = {
            "family_cluster": family_score,
            "co_occurrence": co_score,
            "age_trajectory": age_score,
            "gedcom_match": gedcom_score,
            "testimony": testimony_score,
            "provenance": provenance_score,
        }

        confidence = aggregate_evidence(evidence)

        suggestions.append(
            {
                "target_identity_id": cand["identity_id"],
                "suggested_name": f"Fox family member (score: {confidence})",
                "family_id": family_name,
                "confidence": confidence,
                "evidence_json": evidence,
                "status": "PENDING",
                "person_name": cand["name"],
            }
        )

    # Sort by confidence descending
    suggestions.sort(key=lambda x: -x["confidence"])

    # Report
    logger.info(f"\n{'=' * 60}")
    logger.info(f"RESULTS: {len(suggestions)} candidates scored")
    logger.info(f"{'=' * 60}")

    for i, s in enumerate(suggestions[:20]):
        fc = s["evidence_json"]["family_cluster"]
        co = s["evidence_json"]["co_occurrence"]
        logger.info(
            f"  #{i + 1}: {s['person_name']} — confidence={s['confidence']:.3f}, "
            f"family_dist={fc.get('raw_distance', 'N/A')}, "
            f"closest={fc.get('closest_member', 'N/A')} ({fc.get('closest_distance', 'N/A')}), "
            f"co_occur={co.get('shared_photos_with_family', 0)}"
        )

    if len(suggestions) > 20:
        logger.info(f"  ... and {len(suggestions) - 20} more")

    # Write to Supabase (only in execute mode)
    if not dry_run:
        logger.info(f"\nWriting {len(suggestions)} suggestions to Supabase...")
        written = 0
        for s in suggestions:
            row = {
                "target_identity_id": s["target_identity_id"],
                "suggested_name": s["suggested_name"],
                "family_id": s["family_id"],
                "confidence": s["confidence"],
                "evidence_json": s["evidence_json"],
                "status": "PENDING",
            }
            try:
                sb.table("identity_suggestions").upsert(row, on_conflict="target_identity_id,family_id").execute()
                written += 1
            except Exception as e:
                logger.error(f"  Failed to write suggestion for {s['target_identity_id']}: {e}")
                # Try insert instead (no unique constraint on target+family yet)
                try:
                    sb.table("identity_suggestions").insert(row).execute()
                    written += 1
                except Exception as e2:
                    logger.error(f"  Insert also failed: {e2}")

        logger.info(f"  Written: {written}/{len(suggestions)}")
    else:
        logger.info("\nDRY RUN — no changes written to Supabase")

    return suggestions


def main():
    parser = argparse.ArgumentParser(description="Compute identity suggestions")
    parser.add_argument("--family", required=True, help="Family name (e.g., fox)")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Preview only (default)")
    parser.add_argument("--execute", action="store_true", help="Write to Supabase")
    args = parser.parse_args()

    dry_run = not args.execute
    run_pipeline(args.family, dry_run=dry_run)


if __name__ == "__main__":
    main()
