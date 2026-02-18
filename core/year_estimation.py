"""Year estimation engine — estimate when a photo was taken.

V1 uses pre-computed data from Gemini labels and birth year estimates.
Combines apparent ages with known birth years for identified faces.

Pipeline:
1. Load face data for a photo from date_labels (subject_ages)
2. Match faces to identities via photo_index face_ids
3. For each identified face with a known birth year:
   estimated_year = birth_year + apparent_age
4. Aggregate across faces (weighted average by source confidence)
5. Include scene evidence from Gemini labels
6. Return combined estimate with per-face reasoning
"""
import json
import logging
from pathlib import Path


def estimate_photo_year(
    photo_id: str,
    date_labels: dict = None,
    photo_cache: dict = None,
    identity_registry=None,
    birth_year_fn=None,
    face_to_identity_fn=None,
) -> dict | None:
    """Estimate when a photo was taken using facial age analysis.

    Args:
        photo_id: The photo ID to estimate
        date_labels: Dict of photo_id -> Gemini label data
        photo_cache: Dict of photo_id -> photo metadata
        identity_registry: IdentityRegistry instance
        birth_year_fn: Function(identity_id, identity) -> (year, source, confidence)
        face_to_identity_fn: Function(registry, face_id) -> identity dict or None

    Returns:
        Dict with estimation results, or None if insufficient data.
    """
    if not date_labels or not photo_cache:
        return None

    label = date_labels.get(photo_id)
    photo = photo_cache.get(photo_id)
    if not photo:
        return None

    # Get subject ages from Gemini label
    subject_ages = []
    if label:
        subject_ages = label.get("subject_ages") or label.get("metadata", {}).get("subject_ages", []) or []

    # Get face IDs for this photo
    face_ids = photo.get("face_ids", [])

    # Match faces to ages (left-to-right ordering, same as birth year pipeline)
    # subject_ages are ordered left-to-right in the photo
    face_evidence = []
    if face_ids and subject_ages and identity_registry and birth_year_fn and face_to_identity_fn:
        # Sort face_ids by bbox x-coordinate for left-to-right matching
        faces_with_bbox = []
        for fid in face_ids:
            for face_data in photo.get("faces", []):
                if face_data.get("face_id") == fid:
                    bbox = face_data.get("bbox", [0, 0, 0, 0])
                    x1 = float(bbox[0]) if bbox else 0
                    faces_with_bbox.append((fid, x1))
                    break
            else:
                faces_with_bbox.append((fid, 0))

        faces_with_bbox.sort(key=lambda x: x[1])

        # Match ages to sorted faces (1:1 by position)
        for i, (fid, _x) in enumerate(faces_with_bbox):
            if i >= len(subject_ages):
                break

            age_entry = subject_ages[i]
            apparent_age = None
            if isinstance(age_entry, dict):
                apparent_age = age_entry.get("age") or age_entry.get("estimated_age")
            elif isinstance(age_entry, (int, float)):
                apparent_age = int(age_entry)
            elif isinstance(age_entry, str):
                try:
                    apparent_age = int(age_entry)
                except ValueError:
                    pass

            if apparent_age is None:
                continue

            # Look up identity for this face
            identity = face_to_identity_fn(identity_registry, fid)
            if not identity:
                face_evidence.append({
                    "face_id": fid,
                    "apparent_age": apparent_age,
                    "has_identity": False,
                })
                continue

            identity_id = identity.get("identity_id", "")
            person_name = identity.get("name", "Unknown")
            if person_name.startswith("Unidentified"):
                person_name = None

            # Get birth year
            birth_year, by_source, by_confidence = birth_year_fn(identity_id, identity)

            estimated_year = None
            if birth_year and apparent_age:
                estimated_year = int(birth_year) + int(apparent_age)

            face_evidence.append({
                "face_id": fid,
                "identity_id": identity_id,
                "person_name": person_name,
                "apparent_age": apparent_age,
                "birth_year": birth_year,
                "birth_year_source": by_source,
                "estimated_year": estimated_year,
                "has_identity": True,
            })

    # Aggregate face-based estimates
    face_years = [
        e for e in face_evidence
        if e.get("estimated_year") and e.get("birth_year")
    ]

    aggregated_year = None
    margin = None
    confidence = None

    if face_years:
        # Weight confirmed birth years higher than ML-inferred
        weighted_sum = 0
        weight_total = 0
        for e in face_years:
            w = 2.0 if e.get("birth_year_source") == "confirmed" else 1.0
            weighted_sum += e["estimated_year"] * w
            weight_total += w
        aggregated_year = round(weighted_sum / weight_total)

        # Margin based on spread
        years = [e["estimated_year"] for e in face_years]
        spread = max(years) - min(years) if len(years) > 1 else 10
        margin = max(3, min(15, round(spread / 2) + 3))

        # Confidence based on number of faces and birth year sources
        confirmed_count = sum(1 for e in face_years if e.get("birth_year_source") == "confirmed")
        if confirmed_count >= 2:
            confidence = "high"
        elif confirmed_count >= 1:
            confidence = "medium"
        elif len(face_years) >= 2:
            confidence = "medium"
        else:
            confidence = "low"

    # Scene evidence from Gemini
    scene_evidence = None
    if label:
        clues = []
        metadata = label.get("metadata", {})
        if metadata.get("photo_type"):
            clues.append(metadata["photo_type"].replace("_", " ").title())
        if metadata.get("setting"):
            clues.append(metadata["setting"].replace("_", " ").title())
        if metadata.get("condition"):
            clues.append(f"Condition: {metadata['condition']}")
        if metadata.get("clothing_notes"):
            clues.append(metadata["clothing_notes"][:80])

        scene_decade = label.get("estimated_decade")
        scene_year = label.get("best_year_estimate")
        scene_estimate = f"{scene_decade}s" if scene_decade else None

        scene_evidence = {
            "clues": clues,
            "scene_estimate": scene_estimate,
            "scene_year": scene_year,
            "scene_confidence": label.get("confidence", "medium"),
        }

    # If no face-based estimate, fall back to scene
    if aggregated_year is None and scene_evidence and scene_evidence.get("scene_year"):
        try:
            aggregated_year = int(scene_evidence["scene_year"])
            margin = 10
            confidence = "low"
        except (ValueError, TypeError):
            pass

    if aggregated_year is None:
        return None

    # Build reasoning text
    reasoning_parts = []
    for e in face_evidence:
        if e.get("estimated_year") and e.get("person_name"):
            by_text = f"born ~{e['birth_year']}" if e.get("birth_year") else ""
            reasoning_parts.append(
                f"{e['person_name']} ({by_text}) appears ~{e['apparent_age']} years old -> c. {e['estimated_year']}"
            )
    if scene_evidence and scene_evidence.get("scene_estimate"):
        clue_text = ", ".join(scene_evidence["clues"][:3]) if scene_evidence["clues"] else "visual analysis"
        reasoning_parts.append(f"Scene analysis ({clue_text}) suggests {scene_evidence['scene_estimate']}")

    return {
        "year": aggregated_year,
        "confidence": confidence,
        "margin": margin or 10,
        "method": "facial_age_aggregation" if face_years else "scene_analysis",
        "face_evidence": face_evidence,
        "scene_evidence": scene_evidence,
        "reasoning": " | ".join(reasoning_parts) if reasoning_parts else None,
        "face_count": len(face_years),
    }
