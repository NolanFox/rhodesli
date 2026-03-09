#!/usr/bin/env python3
"""Data integrity validator — catches orphaned identities, missing photos, broken links.

Run before every deploy and after every ingest to ensure no data is lost.
Root cause: Session 96c David Capeloto incident — identity synced from production
but photo_index entry was not, leaving a confirmed identity with no photo.

Usage:
    python scripts/validate_data_integrity.py          # check and report
    python scripts/validate_data_integrity.py --strict  # exit 1 on any error
"""

import json
import sys
from pathlib import Path
import numpy as np


def load_data():
    """Load all data files."""
    base = Path(__file__).parent.parent / "data"

    with open(base / "identities.json") as f:
        identities_data = json.load(f)
    identities = identities_data.get("identities", {})

    with open(base / "photo_index.json") as f:
        photo_data = json.load(f)
    photos = photo_data.get("photos", {})
    face_to_photo = photo_data.get("face_to_photo", {})

    embs = np.load(base / "embeddings.npy", allow_pickle=True)
    emb_face_ids = set()
    for e in embs:
        fid = e.get("face_id")
        if fid:
            emb_face_ids.add(fid)

    return identities, photos, face_to_photo, emb_face_ids


def validate(identities, photos, face_to_photo, emb_face_ids):
    """Run all integrity checks. Returns list of (severity, message) tuples."""
    issues = []

    # 1. Every anchor/candidate face_id must exist in face_to_photo
    for iid, ident in identities.items():
        if ident.get("merged_into"):
            continue  # skip merged identities
        state = ident.get("state", "")
        name = ident.get("name", "?")
        for face_id in ident.get("anchor_ids", []):
            if face_id not in face_to_photo:
                issues.append(
                    (
                        "CRITICAL",
                        f"Identity {iid[:8]} ({name}, {state}): anchor face '{face_id}' not in photo_index.face_to_photo",
                    )
                )
            if face_id not in emb_face_ids:
                issues.append(
                    ("CRITICAL", f"Identity {iid[:8]} ({name}, {state}): anchor face '{face_id}' not in embeddings.npy")
                )
        for face_id in ident.get("candidate_ids", []):
            if face_id not in face_to_photo:
                issues.append(
                    (
                        "WARNING",
                        f"Identity {iid[:8]} ({name}, {state}): candidate face '{face_id}' not in photo_index.face_to_photo",
                    )
                )

    # 2. Every face in face_to_photo must point to an existing photo
    for face_id, photo_id in face_to_photo.items():
        if photo_id not in photos:
            issues.append(("ERROR", f"face_to_photo: face '{face_id}' points to non-existent photo '{photo_id}'"))

    # 3. Every photo's face_ids must be in face_to_photo
    for photo_id, photo_data in photos.items():
        for face_id in photo_data.get("face_ids", []):
            if face_id not in face_to_photo:
                issues.append(("WARNING", f"Photo {photo_id}: face '{face_id}' listed but not in face_to_photo"))

    # 4. Check for CONFIRMED identities with 0 anchors
    # Note: GEDCOM-linked identities may be confirmed without faces (they have
    # GEDCOM records but no photos yet). Only flag as INFO, not ERROR.
    for iid, ident in identities.items():
        if ident.get("merged_into"):
            continue
        if ident.get("state") == "CONFIRMED" and not ident.get("anchor_ids"):
            issues.append(
                ("INFO", f"Identity {iid[:8]} ({ident.get('name', '?')}): CONFIRMED with 0 anchor faces (GEDCOM-only?)")
            )

    # 5. Check crop files exist for anchors of confirmed identities
    crops_dir = Path(__file__).parent.parent / "app" / "static" / "crops"
    for iid, ident in identities.items():
        if ident.get("merged_into"):
            continue
        if ident.get("state") != "CONFIRMED":
            continue
        for face_id in ident.get("anchor_ids", []):
            crop_path = crops_dir / f"{face_id}.jpg"
            if not crop_path.exists():
                issues.append(
                    ("WARNING", f"Identity {iid[:8]} ({ident.get('name', '?')}): crop missing for face '{face_id}'")
                )

    return issues


def main():
    strict = "--strict" in sys.argv
    identities, photos, face_to_photo, emb_face_ids = load_data()

    print(
        f"Loaded: {len(identities)} identities, {len(photos)} photos, "
        f"{len(face_to_photo)} face_to_photo, {len(emb_face_ids)} embeddings"
    )

    issues = validate(identities, photos, face_to_photo, emb_face_ids)

    if not issues:
        print("\nAll integrity checks passed.")
        return 0

    criticals = [i for i in issues if i[0] == "CRITICAL"]
    errors = [i for i in issues if i[0] == "ERROR"]
    warnings = [i for i in issues if i[0] == "WARNING"]

    print(f"\nFound {len(issues)} issues: {len(criticals)} CRITICAL, {len(errors)} ERROR, {len(warnings)} WARNING\n")

    for severity, msg in issues:
        print(f"  [{severity}] {msg}")

    if strict and (criticals or errors):
        print(f"\n--strict mode: exiting with error ({len(criticals)} critical, {len(errors)} errors)")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
