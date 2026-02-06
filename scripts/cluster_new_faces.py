#!/usr/bin/env python3
"""Cluster newly detected faces against confirmed identity centroids.

For each new face (from INBOX/PROPOSED identities), compute distance to
each CONFIRMED identity's centroid and suggest matches.

IMPORTANT: This script NEVER auto-merges. It only creates PROPOSED matches
that require human review. Per the forensic invariants:
  provenance="human" overrides provenance="model"

The script works by:
1. Loading confirmed identities and computing their centroid embeddings
2. For each unresolved face (INBOX/PROPOSED), finding the closest centroid
3. If distance < threshold, suggesting a match
4. In --execute mode, updating identities.json to move matched faces
   as candidates (NOT anchors) on the target identity, with provenance="model"

Usage:
    python scripts/cluster_new_faces.py --dry-run
    python scripts/cluster_new_faces.py --execute --threshold 1.0
    python scripts/cluster_new_faces.py --dry-run --threshold 0.8
"""

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path for core imports
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from core.config import MATCH_THRESHOLD_HIGH, MATCH_THRESHOLD_MEDIUM


def load_face_data(data_path: Path) -> dict:
    """Load face embeddings as face_id -> {mu, sigma_sq} dict.

    Mirrors the logic in app/main.py load_face_embeddings().
    Uses deferred imports per CLAUDE.md rules.
    """
    import numpy as np

    embeddings_path = data_path / "embeddings.npy"
    if not embeddings_path.exists():
        raise FileNotFoundError(f"Embeddings not found: {embeddings_path}")

    embeddings = np.load(embeddings_path, allow_pickle=True)

    face_data = {}
    filename_face_counts = {}

    for entry in embeddings:
        filename = entry["filename"]

        if filename not in filename_face_counts:
            filename_face_counts[filename] = 0
        face_index = filename_face_counts[filename]
        filename_face_counts[filename] += 1

        face_id = entry.get("face_id") or generate_face_id(filename, face_index)

        if "mu" in entry:
            mu = entry["mu"]
            sigma_sq = entry["sigma_sq"]
        else:
            mu = np.asarray(entry["embedding"], dtype=np.float32)
            det_score = entry.get("det_score", 0.5)
            sigma_sq_val = 1.0 - (det_score * 0.9)
            sigma_sq = np.full(512, sigma_sq_val, dtype=np.float32)

        face_data[face_id] = {
            "mu": np.asarray(mu, dtype=np.float32),
            "sigma_sq": np.asarray(sigma_sq, dtype=np.float32),
        }

    return face_data


def generate_face_id(filename: str, face_index: int) -> str:
    """Generate a stable face ID from filename and index."""
    stem = Path(filename).stem
    return f"{stem}:face{face_index}"


def load_identities(data_path: Path) -> dict:
    """Load identities.json and return the raw data."""
    identities_path = data_path / "identities.json"
    if not identities_path.exists():
        raise FileNotFoundError(f"Identities not found: {identities_path}")

    with open(identities_path) as f:
        return json.load(f)


def extract_face_ids(identity: dict) -> list[str]:
    """Extract all face IDs from an identity (anchors + candidates).

    Handles both string and dict anchor formats.
    """
    face_ids = []

    for anchor in identity.get("anchor_ids", []):
        if isinstance(anchor, str):
            face_ids.append(anchor)
        elif isinstance(anchor, dict):
            face_ids.append(anchor["face_id"])

    face_ids.extend(identity.get("candidate_ids", []))

    return face_ids


def get_photo_id(face_id: str) -> str | None:
    """Extract photo identifier from face_id (everything before :faceN)."""
    if ":" in face_id:
        return face_id.rsplit(":", 1)[0]
    return None


def compute_centroid(face_ids: list[str], face_data: dict):
    """Compute mean embedding (centroid) for a set of faces.

    Uses deferred numpy import.

    Returns numpy array or None if no valid faces.
    """
    import numpy as np

    embeddings = []
    for fid in face_ids:
        if fid in face_data:
            embeddings.append(face_data[fid]["mu"])

    if not embeddings:
        return None

    return np.mean(np.vstack(embeddings), axis=0)


def compute_distance_to_centroid(face_embedding, centroid) -> float:
    """Compute Euclidean distance from face embedding to centroid.

    Uses same metric as core/neighbors.py.
    """
    import numpy as np

    diff = face_embedding - centroid
    return float(np.sqrt(np.sum(diff ** 2)))


def find_matches(
    identities_data: dict,
    face_data: dict,
    threshold: float,
) -> list[dict]:
    """Find suggested matches for unresolved faces.

    Returns list of match suggestions, sorted by distance (best first).
    """
    identities = identities_data.get("identities", {})

    # Step 1: Build confirmed identity centroids
    confirmed_centroids = {}
    confirmed_photos = {}  # identity_id -> set of photo_ids (for co-occurrence check)

    for identity_id, identity in identities.items():
        if identity.get("state") != "CONFIRMED":
            continue
        if identity.get("merged_into"):
            continue

        face_ids = extract_face_ids(identity)
        if not face_ids:
            continue

        centroid = compute_centroid(face_ids, face_data)
        if centroid is None:
            continue

        confirmed_centroids[identity_id] = {
            "centroid": centroid,
            "name": identity.get("name", f"Unknown ({identity_id[:8]})"),
            "face_count": len(face_ids),
        }

        # Track photos for co-occurrence check
        photos = set()
        for fid in face_ids:
            photo_id = get_photo_id(fid)
            if photo_id:
                photos.add(photo_id)
        confirmed_photos[identity_id] = photos

    if not confirmed_centroids:
        print("WARNING: No confirmed identities with embeddings found.")
        return []

    print(f"Confirmed identity centroids: {len(confirmed_centroids)}")

    # Step 2: Find unresolved identities (INBOX or PROPOSED)
    unresolved_states = {"INBOX", "PROPOSED"}
    suggestions = []

    for identity_id, identity in identities.items():
        if identity.get("state") not in unresolved_states:
            continue
        if identity.get("merged_into"):
            continue

        face_ids = extract_face_ids(identity)
        if not face_ids:
            continue

        # Get photos for co-occurrence check
        source_photos = set()
        for fid in face_ids:
            photo_id = get_photo_id(fid)
            if photo_id:
                source_photos.add(photo_id)

        # For each face in this identity, find closest confirmed centroid
        for face_id in face_ids:
            if face_id not in face_data:
                continue

            face_embedding = face_data[face_id]["mu"]
            best_match = None
            best_distance = float("inf")

            for conf_id, conf_info in confirmed_centroids.items():
                # Co-occurrence check: skip if face's photo appears in confirmed identity
                face_photo = get_photo_id(face_id)
                if face_photo and face_photo in confirmed_photos.get(conf_id, set()):
                    continue

                distance = compute_distance_to_centroid(
                    face_embedding, conf_info["centroid"]
                )

                if distance < best_distance:
                    best_distance = distance
                    best_match = conf_id

            if best_match and best_distance < threshold:
                suggestions.append({
                    "face_id": face_id,
                    "source_identity_id": identity_id,
                    "source_identity_name": identity.get(
                        "name", f"Unknown ({identity_id[:8]})"
                    ),
                    "target_identity_id": best_match,
                    "target_identity_name": confirmed_centroids[best_match]["name"],
                    "distance": best_distance,
                    "target_face_count": confirmed_centroids[best_match]["face_count"],
                })

    # Sort by distance (best matches first)
    suggestions.sort(key=lambda s: s["distance"])

    return suggestions


def apply_suggestions(
    identities_data: dict,
    suggestions: list[dict],
) -> dict:
    """Apply match suggestions by moving faces to target identities as candidates.

    Returns updated identities_data. Does NOT modify in place.

    Rules:
    - Face is added as a candidate_id on the target identity (NOT anchor)
    - Face is removed from the source identity
    - If source identity has no remaining faces, it is marked as merged
    - provenance is recorded as "model" for full traceability
    """
    import copy

    data = copy.deepcopy(identities_data)
    identities = data["identities"]

    now = datetime.now(timezone.utc).isoformat()
    applied = 0

    for suggestion in suggestions:
        face_id = suggestion["face_id"]
        source_id = suggestion["source_identity_id"]
        target_id = suggestion["target_identity_id"]

        source = identities.get(source_id)
        target = identities.get(target_id)

        if not source or not target:
            continue

        # Skip if already merged
        if source.get("merged_into") or target.get("merged_into"):
            continue

        # Remove face from source
        removed = False

        # Check anchor_ids (handle both string and dict)
        new_anchors = []
        for anchor in source.get("anchor_ids", []):
            anchor_fid = anchor if isinstance(anchor, str) else anchor.get("face_id")
            if anchor_fid == face_id:
                removed = True
            else:
                new_anchors.append(anchor)
        source["anchor_ids"] = new_anchors

        # Check candidate_ids
        if face_id in source.get("candidate_ids", []):
            source["candidate_ids"].remove(face_id)
            removed = True

        if not removed:
            continue

        # Add face as candidate on target
        if face_id not in target.get("candidate_ids", []):
            target["candidate_ids"].append(face_id)

        # Update target version
        target["version_id"] = target.get("version_id", 1) + 1
        target["updated_at"] = now

        # Update source version
        source["version_id"] = source.get("version_id", 1) + 1
        source["updated_at"] = now

        # If source has no remaining faces, mark as merged
        remaining_faces = extract_face_ids(source)
        if not remaining_faces:
            source["merged_into"] = target_id

        applied += 1

    return data, applied


def main():
    parser = argparse.ArgumentParser(
        description="Cluster newly detected faces against confirmed identity centroids."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Preview match suggestions without modifying data (default)",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply match suggestions to identities.json",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=MATCH_THRESHOLD_HIGH,
        help=f"Distance threshold for matching (default: {MATCH_THRESHOLD_HIGH})",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of suggestions to apply",
    )
    args = parser.parse_args()

    if args.execute:
        args.dry_run = False

    data_path = project_root / "data"
    identities_path = data_path / "identities.json"

    print("=" * 60)
    print("CLUSTER NEW FACES")
    print("=" * 60)
    print(f"Data path: {data_path}")
    print(f"Threshold: {args.threshold}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'EXECUTE'}")
    print()

    # Load data
    print("Loading identities...")
    identities_data = load_identities(data_path)
    identity_count = len(identities_data.get("identities", {}))
    print(f"Loaded {identity_count} identities")

    print("Loading face embeddings...")
    face_data = load_face_data(data_path)
    print(f"Loaded {len(face_data)} face embeddings")
    print()

    # Find matches
    suggestions = find_matches(identities_data, face_data, args.threshold)

    if args.limit:
        suggestions = suggestions[:args.limit]

    if not suggestions:
        print("No match suggestions found at this threshold.")
        print(f"Try increasing --threshold (current: {args.threshold})")
        return

    # Display suggestions
    print(f"\nFound {len(suggestions)} match suggestions:")
    print("-" * 80)
    print(f"{'Face ID':<35} {'->':>3} {'Target Identity':<25} {'Distance':>10}")
    print("-" * 80)

    for s in suggestions:
        face_display = s["face_id"]
        if len(face_display) > 34:
            face_display = face_display[:31] + "..."
        target_display = s["target_identity_name"]
        if len(target_display) > 24:
            target_display = target_display[:21] + "..."

        confidence = "HIGH" if s["distance"] < MATCH_THRESHOLD_HIGH else "MEDIUM"
        print(f"  {face_display:<34} -> {target_display:<24} "
              f"{s['distance']:>8.4f}  [{confidence}]")

    # Group by source identity for readability
    print()
    source_groups = {}
    for s in suggestions:
        source_name = s["source_identity_name"]
        if source_name not in source_groups:
            source_groups[source_name] = []
        source_groups[source_name].append(s)

    print("Summary by source identity:")
    for source_name, group in sorted(source_groups.items()):
        targets = set(s["target_identity_name"] for s in group)
        print(f"  {source_name} ({len(group)} faces) -> {', '.join(targets)}")

    print()

    if args.dry_run:
        print("[DRY RUN] No changes made.")
        print("Run with --execute to apply these suggestions.")
    else:
        print("Applying suggestions...")
        updated_data, applied_count = apply_suggestions(identities_data, suggestions)

        if applied_count == 0:
            print("No suggestions could be applied (all faces already moved or merged).")
            return

        # Atomic write: temp file + rename
        fd, temp_path = tempfile.mkstemp(
            suffix=".json",
            dir=identities_path.parent,
        )
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(updated_data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.rename(temp_path, identities_path)
            print(f"Applied {applied_count} suggestions to {identities_path}")
            print()
            print("IMPORTANT: These are PROPOSED matches (provenance=model).")
            print("A human must review and confirm each match in the UI.")
        except Exception:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise


if __name__ == "__main__":
    main()
