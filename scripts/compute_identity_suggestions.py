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
import re
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


# --- Fox Sibling GEDCOM Data (1894 Minsk revision list) ---

FOX_SIBLINGS_BIRTH_YEARS = {
    "Bessie Fox": 1877,
    "Sarah Fox": 1882,
    "Harry Fox": 1884,
    "Sadie Fox": 1884,
    "Rachel Fox": 1889,
    "Albert Fox": 1893,
    "Irving Fox": 1899,
    "Jacob Fox": 1903,
}

# Birth year range for feasibility checks on unidentified candidates
FOX_BIRTH_YEAR_RANGE = (1877, 1910)  # Siblings + spouses born ~1877-1910
FOX_BIRTH_YEAR_MIDDLE = (FOX_BIRTH_YEAR_RANGE[0] + FOX_BIRTH_YEAR_RANGE[1]) // 2  # 1893

# Already confirmed/linked siblings — exclude from unlinked matching
CONFIRMED_FOX_SIBLINGS = {"Albert Fox", "Harry Fox", "Bessie Fox", "Rachel Fox"}
# Esther Burd Fox is a spouse, not a sibling

UNLINKED_FOX_SIBLINGS = {
    name: year for name, year in FOX_SIBLINGS_BIRTH_YEARS.items() if name not in CONFIRMED_FOX_SIBLINGS
}


# --- Known Testimony (hardcoded until testimony_evidence Supabase table) ---

KNOWN_TESTIMONY = {
    "273ac560-bf13-43f5-8f87-e0f7ec967b2c": {  # Person 3481
        "score": 0.0,
        "entries": [
            {
                "source": "Howard Newman",
                "relationship": "grandson of Rachel Fox",
                "statement": "almost certain NOT my grandmother",
                "polarity": "NEGATIVE",
                "session": "145",
                "date": "2026-03-31",
            }
        ],
    },
}
# TODO(PRD-059-P5): migrate to testimony_evidence Supabase table


# --- Known Provenance (hardcoded until structured Supabase table) ---

KNOWN_PROVENANCE: dict[str, dict] = {
    # TODO(PRD-059-P5): migrate provenance to structured Supabase table
    # Add identity_id -> {"score": float, "labels": [...]} entries as discovered
}


def load_gedcom_birth_years(sb) -> dict[str, int]:
    """Load birth years from GEDCOM individuals table.

    Tries current_gedcom_individuals view first, falls back to gedcom_individuals.
    Parses birth_date TEXT field to extract 4-digit years from formats like
    "1889", "ABT 1890", "BEF 1895", etc.
    """
    birth_years = {}
    raw_data = []

    for table_name in ["current_gedcom_individuals", "gedcom_individuals"]:
        try:
            resp = sb.table(table_name).select("id,given_names,surname,birth_date").execute()
            raw_data = resp.data or []
            if raw_data:
                logger.info(f"  Loaded {len(raw_data)} GEDCOM individuals from {table_name}")
                break
        except Exception as e:
            logger.warning(f"  Could not load {table_name}: {e}")

    for row in raw_data:
        birth_date = row.get("birth_date", "")
        if not birth_date:
            continue
        # Extract 4-digit year from various formats
        match = re.search(r"\b(\d{4})\b", str(birth_date))
        if match:
            year = int(match.group(1))
            if 1700 < year < 2030:  # Sanity check
                given = row.get("given_names", "") or ""
                surname = row.get("surname", "") or ""
                full_name = f"{given} {surname}".strip()
                if full_name:
                    birth_years[full_name] = year
                # Also store by ID for direct lookups
                row_id = row.get("id")
                if row_id:
                    birth_years[f"gedcom:{row_id}"] = year

    return birth_years


def compute_gedcom_match_score(
    target_id: str,
    family_identity_ids: set[str],
    co_occurrence_pairs: dict,
    date_labels: dict,
    identity_photos: dict,
) -> dict:
    """Score how well a target matches an unlinked Fox sibling based on GEDCOM data.

    Score 1.0 if target co-occurs with confirmed family AND estimated age range
    matches an unlinked sibling.
    Score 0.5 if partial match (right generation but no specific sibling match).
    Score 0.0 if contradicts (impossible era).
    """
    # Check co-occurrence with confirmed family
    co_occur_count = 0
    for fid in family_identity_ids:
        key = tuple(sorted([target_id, fid]))
        co_occur_count += co_occurrence_pairs.get(key, 0)

    has_family_co_occurrence = co_occur_count > 0

    # Estimate the target's likely birth year from photos
    target_photos = identity_photos.get(target_id, [])
    estimated_birth_years = []

    for photo_id in target_photos:
        label = date_labels.get(photo_id)
        if not label or not isinstance(label, dict):
            continue
        photo_year = label.get("estimated_year") or label.get("year_estimate")
        estimated_age = label.get("estimated_age")
        if photo_year and estimated_age and estimated_age > 0:
            estimated_birth_years.append(photo_year - estimated_age)

    if not estimated_birth_years:
        # No age data — can only score based on co-occurrence
        if has_family_co_occurrence:
            return {"score": 0.5, "reason": "co_occurrence_only", "co_occur_count": co_occur_count}
        return {"score": 0.0, "reason": "no_data"}

    mean_estimated_birth = int(np.mean(estimated_birth_years))

    # Check if birth year is impossible for the Fox generation
    if mean_estimated_birth < 1860 or mean_estimated_birth > 1930:
        return {
            "score": 0.0,
            "reason": "impossible_era",
            "estimated_birth_year": mean_estimated_birth,
        }

    # Check match against unlinked siblings
    best_match = None
    best_diff = 999
    for name, birth_year in UNLINKED_FOX_SIBLINGS.items():
        diff = abs(mean_estimated_birth - birth_year)
        if diff < best_diff:
            best_diff = diff
            best_match = name

    if has_family_co_occurrence and best_diff <= 5:
        # Strong match: co-occurs with family AND age matches a specific sibling
        return {
            "score": 1.0,
            "reason": "full_match",
            "estimated_birth_year": mean_estimated_birth,
            "best_sibling_match": best_match,
            "birth_year_diff": best_diff,
            "co_occur_count": co_occur_count,
        }
    elif best_diff <= 10:
        # Partial match: right generation
        return {
            "score": 0.5,
            "reason": "partial_match",
            "estimated_birth_year": mean_estimated_birth,
            "best_sibling_match": best_match,
            "birth_year_diff": best_diff,
            "co_occur_count": co_occur_count,
        }
    else:
        return {
            "score": 0.0,
            "reason": "wrong_generation",
            "estimated_birth_year": mean_estimated_birth,
            "best_sibling_match": best_match,
            "birth_year_diff": best_diff,
        }


def get_testimony(target_identity_id: str) -> dict:
    """Look up known testimony for a target identity."""
    return KNOWN_TESTIMONY.get(
        target_identity_id,
        {"score": 0.0, "entries": []},
    )


def get_provenance(target_identity_id: str) -> dict:
    """Look up known provenance for a target identity."""
    return KNOWN_PROVENANCE.get(
        target_identity_id,
        {"score": 0.0, "labels": []},
    )


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

    logger.info("Loading GEDCOM birth years...")
    gedcom_birth_years = load_gedcom_birth_years(sb)
    logger.info(f"  {len(gedcom_birth_years)} GEDCOM birth years loaded")

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

        # Signal 3: Age trajectory — use middle of Fox birth year range for general feasibility
        age_score = compute_age_feasibility(cand["identity_id"], FOX_BIRTH_YEAR_MIDDLE, date_labels, identity_photos)

        # Signal 4: GEDCOM match — check if target matches an unlinked Fox sibling
        gedcom_score = compute_gedcom_match_score(
            cand["identity_id"],
            family_identity_ids,
            co_occurrence_pairs,
            date_labels,
            identity_photos,
        )

        # Signal 5: Testimony — known human statements about this identity
        testimony_score = get_testimony(cand["identity_id"])

        # Signal 6: Provenance — known provenance labels for this identity
        provenance_score = get_provenance(cand["identity_id"])

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
        # Preserve reviewed suggestions — never overwrite REJECTED/ACCEPTED/NEEDS_MORE
        try:
            existing_resp = (
                sb.table("identity_suggestions")
                .select("target_identity_id,family_id,status")
                .eq("family_id", family_name)
                .in_("status", ["REJECTED", "ACCEPTED", "NEEDS_MORE"])
                .execute()
            )
            reviewed_keys = {(r["target_identity_id"], r["family_id"]) for r in (existing_resp.data or [])}
            if reviewed_keys:
                logger.info(f"  Preserving {len(reviewed_keys)} reviewed suggestions (REJECTED/ACCEPTED/NEEDS_MORE)")
        except Exception as e:
            logger.warning(f"  Could not load reviewed suggestions: {e}")
            reviewed_keys = set()

        logger.info(f"\nWriting {len(suggestions)} suggestions to Supabase...")
        written = 0
        skipped_reviewed = 0
        for s in suggestions:
            # Skip suggestions that have already been reviewed by admin
            if (s["target_identity_id"], s["family_id"]) in reviewed_keys:
                skipped_reviewed += 1
                continue
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
        if skipped_reviewed > 0:
            logger.info(f"  Skipped (already reviewed): {skipped_reviewed}")
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
