"""Birth year estimation pipeline.

Infers birth years for confirmed identities by cross-referencing:
- Photo dates (best_year_estimate from Gemini/CORAL)
- Per-face age estimates (subject_ages from Gemini, ordered left-to-right)
- Face bounding box x-coordinates (for left-to-right matching)

Algorithm:
1. For each photo, sort detected faces left-to-right by bbox x1
2. Match to Gemini's subject_ages by position (only when counts match)
3. For each confirmed identity, gather all (photo_year, estimated_age) pairs
4. Compute weighted average implied birth year
5. Assign confidence tier based on std deviation and sample count

Output: birth_year_estimates.json with per-identity estimates and evidence chains.
"""

import json
import math
from datetime import datetime, timezone
from pathlib import Path


# --- Confidence tier thresholds ---
HIGH_CONFIDENCE_STD = 3.0
HIGH_CONFIDENCE_MIN_N = 3
MEDIUM_CONFIDENCE_STD = 5.0

# --- Validation bounds ---
MIN_BIRTH_YEAR = 1850
MAX_BIRTH_YEAR = 2010
MAX_AGE = 100
MIN_AGE = 0

# --- Weighting ---
CONFIDENCE_WEIGHTS = {"high": 1.0, "medium": 0.5, "low": 0.25}
SINGLE_PERSON_BONUS = 2.0  # multiply weight for single-person photos


def load_date_labels(path="rhodesli_ml/data/date_labels.json"):
    """Load date labels, return dict keyed by photo_id."""
    with open(path) as f:
        data = json.load(f)
    labels = data.get("labels", data) if isinstance(data, dict) else data
    return {label["photo_id"]: label for label in labels}


def load_identities(path="data/identities.json"):
    """Load identities, return dict of confirmed identities."""
    with open(path) as f:
        data = json.load(f)
    identities = data.get("identities", {})
    return {
        iid: ident for iid, ident in identities.items()
        if ident.get("state") == "CONFIRMED" and "merged_into" not in ident
    }


def load_photo_index(path="data/photo_index.json"):
    """Load photo index, return (photos, face_to_photo) dicts."""
    with open(path) as f:
        data = json.load(f)
    return data.get("photos", {}), data.get("face_to_photo", {})


def load_embeddings(path="data/embeddings.npy"):
    """Load embeddings, return dict keyed by face_id with bbox data."""
    import numpy as np
    entries = np.load(path, allow_pickle=True)
    result = {}
    for entry in entries:
        face_id = entry.get("face_id")
        if not face_id:
            # Generate face_id from filename + index
            filename = entry.get("filename", "")
            # Find the index by counting entries with same filename
            stem = Path(filename).stem
            if stem not in result:
                idx = 0
            else:
                idx = sum(1 for k in result if k.startswith(f"{stem}:"))
            face_id = f"{stem}:face{idx}"
        bbox = entry.get("bbox")
        if bbox is not None:
            if isinstance(bbox, str):
                try:
                    bbox = json.loads(bbox)
                except (json.JSONDecodeError, ValueError):
                    bbox = None
            if hasattr(bbox, 'tolist'):
                bbox = bbox.tolist()
        result[face_id] = {
            "bbox": bbox,
            "filename": entry.get("filename", ""),
        }
    return result


def get_face_ids_for_identity(identity):
    """Get all face IDs for an identity (anchors + candidates)."""
    anchors = identity.get("anchor_ids", [])
    candidates = identity.get("candidate_ids", [])
    return list(set(anchors + candidates))


def match_faces_to_ages(photo_face_ids, face_bboxes, subject_ages):
    """Match face IDs to Gemini age estimates via left-to-right bbox ordering.

    Args:
        photo_face_ids: List of face IDs detected in this photo
        face_bboxes: Dict mapping face_id -> bbox [x1, y1, x2, y2]
        subject_ages: List of integer ages from Gemini (left-to-right)

    Returns:
        Dict mapping face_id -> estimated_age, or empty dict if matching fails.
        Also returns matching_method: "single_person", "bbox_matched", or "ambiguous".
    """
    if not subject_ages or not photo_face_ids:
        return {}, "no_data"

    # Single person — unambiguous
    if len(subject_ages) == 1 and len(photo_face_ids) == 1:
        return {photo_face_ids[0]: subject_ages[0]}, "single_person"

    # Count mismatch — can't reliably match
    if len(photo_face_ids) != len(subject_ages):
        return {}, "count_mismatch"

    # Sort faces left-to-right by bbox x1 coordinate
    faces_with_bbox = []
    for fid in photo_face_ids:
        bbox = face_bboxes.get(fid, {}).get("bbox")
        if bbox and len(bbox) >= 4:
            faces_with_bbox.append((fid, bbox[0]))  # x1 coordinate
        else:
            # No bbox — can't sort
            return {}, "missing_bbox"

    faces_with_bbox.sort(key=lambda x: x[1])

    result = {}
    for i, (fid, _x1) in enumerate(faces_with_bbox):
        result[fid] = subject_ages[i]

    return result, "bbox_matched"


def _median(values):
    """Compute median of a list of numbers."""
    s = sorted(values)
    n = len(s)
    if n == 0:
        return 0
    if n % 2 == 1:
        return s[n // 2]
    return (s[n // 2 - 1] + s[n // 2]) / 2


def _mad(values):
    """Compute Median Absolute Deviation."""
    med = _median(values)
    deviations = [abs(v - med) for v in values]
    return _median(deviations)


# How many MADs from median to consider an outlier
OUTLIER_MAD_THRESHOLD = 3.0


def compute_birth_year_estimate(evidence_items):
    """Compute weighted birth year estimate from evidence items.

    Uses robust estimation: median + MAD to identify outliers from bbox
    mismatches in group photos, then computes weighted average on the
    filtered set.

    Args:
        evidence_items: List of dicts with keys:
            - implied_birth: int
            - weight: float
            - photo_year: int
            - estimated_age: int

    Returns:
        Tuple of (estimate, std, confidence, range_low, range_high, flags)
    """
    if not evidence_items:
        return None, None, None, None, None, []

    # Step 1: Robust outlier detection via median + MAD
    birth_years_raw = [e["implied_birth"] for e in evidence_items]
    flags = []

    if len(evidence_items) >= 3:
        med = _median(birth_years_raw)
        mad_val = _mad(birth_years_raw)
        # MAD-based outlier threshold (use min of 2.0 to avoid zero-MAD)
        threshold = max(mad_val * OUTLIER_MAD_THRESHOLD, 5.0)

        filtered = []
        for e in evidence_items:
            deviation = abs(e["implied_birth"] - med)
            if deviation > threshold:
                flags.append(
                    f"outlier_removed: photo {e['photo_id']} implies {e['implied_birth']} "
                    f"(deviation {deviation:.0f} from median {med:.0f}, threshold {threshold:.0f})"
                )
            else:
                filtered.append(e)

        # Only use filtered set if we have enough data remaining
        if len(filtered) >= 2:
            evidence_items = filtered
    elif len(evidence_items) >= 2:
        # With only 2 items, flag large discrepancies but don't filter
        diff = abs(birth_years_raw[0] - birth_years_raw[1])
        if diff > 10:
            flags.append(f"large_discrepancy: {diff} year spread between 2 estimates")

    # Step 2: Weighted average on (possibly filtered) set
    total_weight = sum(e["weight"] for e in evidence_items)
    if total_weight == 0:
        return None, None, None, None, None, []

    weighted_sum = sum(e["implied_birth"] * e["weight"] for e in evidence_items)
    estimate = weighted_sum / total_weight

    # Standard deviation (weighted)
    n = len(evidence_items)
    if n >= 2:
        variance = sum(
            e["weight"] * (e["implied_birth"] - estimate) ** 2
            for e in evidence_items
        ) / total_weight
        std = math.sqrt(variance)
    else:
        std = float("inf")

    # Confidence tier
    if std < HIGH_CONFIDENCE_STD and n >= HIGH_CONFIDENCE_MIN_N:
        confidence = "high"
    elif std < MEDIUM_CONFIDENCE_STD or n == 2:
        confidence = "medium"
    else:
        confidence = "low"

    # Range (from filtered set)
    birth_years = [e["implied_birth"] for e in evidence_items]
    range_low = min(birth_years)
    range_high = max(birth_years)

    # Validation flags (appended to any outlier flags from step 1)
    rounded = round(estimate)

    # Validate birth year bounds
    if rounded < MIN_BIRTH_YEAR or rounded > MAX_BIRTH_YEAR:
        flags.append(f"birth_year_out_of_range: {rounded}")

    # Check for impossible ages using the filtered evidence
    for e in evidence_items:
        age = e["photo_year"] - rounded
        if age < MIN_AGE:
            flags.append(
                f"negative_age: age={age} in photo {e['photo_id']} ({e['photo_year']})"
            )
        if age > MAX_AGE:
            flags.append(
                f"impossible_age: age={age} in photo {e['photo_id']} ({e['photo_year']})"
                )

    return round(estimate), round(std, 2), confidence, range_low, range_high, flags


def run_birth_year_estimation(
    identities_path="data/identities.json",
    photo_index_path="data/photo_index.json",
    date_labels_path="rhodesli_ml/data/date_labels.json",
    embeddings_path="data/embeddings.npy",
    output_path="rhodesli_ml/data/birth_year_estimates.json",
    min_appearances=1,
):
    """Run the full birth year estimation pipeline.

    Returns:
        Dict with schema_version, generated_at, estimates list, and summary stats.
    """
    # Load data
    date_labels = load_date_labels(date_labels_path)
    confirmed = load_identities(identities_path)
    photos, face_to_photo = load_photo_index(photo_index_path)
    embeddings = load_embeddings(embeddings_path)

    # Build reverse mapping: photo_id -> list of face_ids
    photo_to_faces = {}
    for face_id, photo_id in face_to_photo.items():
        photo_to_faces.setdefault(photo_id, []).append(face_id)

    estimates = []
    stats = {
        "total_confirmed": len(confirmed),
        "with_estimates": 0,
        "high_confidence": 0,
        "medium_confidence": 0,
        "low_confidence": 0,
        "skipped_no_photos": 0,
        "skipped_no_age_data": 0,
    }

    for identity_id, identity in confirmed.items():
        face_ids = get_face_ids_for_identity(identity)
        if not face_ids:
            stats["skipped_no_photos"] += 1
            continue

        # Find all photos this identity appears in
        identity_photos = set()
        face_id_to_photo = {}
        for fid in face_ids:
            pid = face_to_photo.get(fid)
            if pid:
                identity_photos.add(pid)
                face_id_to_photo[fid] = pid

        if not identity_photos:
            stats["skipped_no_photos"] += 1
            continue

        # For each photo, try to match this identity's face to a Gemini age
        evidence_items = []
        for photo_id in identity_photos:
            label = date_labels.get(photo_id)
            if not label:
                continue

            year = label.get("best_year_estimate")
            subject_ages = label.get("subject_ages", [])
            date_confidence = label.get("confidence", "medium")

            if not year or not subject_ages:
                continue

            # Get all faces in this photo
            all_faces_in_photo = photo_to_faces.get(photo_id, [])
            if not all_faces_in_photo:
                continue

            # Match faces to ages
            face_age_map, method = match_faces_to_ages(
                all_faces_in_photo, embeddings, subject_ages
            )

            if not face_age_map:
                continue

            # Find this identity's face(s) in the matched results
            for fid in face_ids:
                if fid in face_age_map:
                    age = face_age_map[fid]
                    implied_birth = year - age

                    # Compute weight
                    weight = CONFIDENCE_WEIGHTS.get(date_confidence, 0.5)
                    if method == "single_person":
                        weight *= SINGLE_PERSON_BONUS

                    evidence_items.append({
                        "photo_id": photo_id,
                        "photo_year": year,
                        "date_confidence": date_confidence,
                        "estimated_age": age,
                        "implied_birth": implied_birth,
                        "matching_method": method,
                        "weight": weight,
                    })
                    break  # Only one face per identity per photo

        if not evidence_items:
            stats["skipped_no_age_data"] += 1
            continue

        if len(evidence_items) < min_appearances:
            stats["skipped_no_age_data"] += 1
            continue

        # Compute estimate
        estimate, std, confidence, range_low, range_high, flags = \
            compute_birth_year_estimate(evidence_items)

        if estimate is None:
            stats["skipped_no_age_data"] += 1
            continue

        entry = {
            "identity_id": identity_id,
            "name": identity.get("name", "Unknown"),
            "birth_year_estimate": estimate,
            "birth_year_confidence": confidence,
            "birth_year_range": [range_low, range_high],
            "birth_year_std": std,
            "n_appearances": len(identity_photos),
            "n_with_age_data": len(evidence_items),
            "evidence": sorted(evidence_items, key=lambda e: e["photo_year"]),
            "flags": flags,
            "source": "ml_inferred",
        }

        estimates.append(entry)
        stats["with_estimates"] += 1
        stats[f"{confidence}_confidence"] += 1

    # Sort by number of evidence items (most evidence first)
    estimates.sort(key=lambda e: e["n_with_age_data"], reverse=True)

    result = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stats": stats,
        "estimates": estimates,
    }

    # Write output
    if output_path:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w") as f:
            json.dump(result, f, indent=2)

    return result
