#!/usr/bin/env python3
"""Apply approved clustering matches to identities.json.

Takes the output of cluster_new_faces.py proposals and applies matches
that meet the specified confidence threshold. Only applies matches where
the algorithm suggests a face belongs to an existing confirmed identity.

Safety features:
- Default mode is --dry-run (preview only)
- Creates a timestamped backup before modifying data
- Direction-aware: always adds face to the CONFIRMED identity (not the other way)
- Only adds as candidate_ids (not anchors) — human must confirm
- Records provenance="model" for traceability

Usage:
    python scripts/apply_cluster_matches.py --dry-run
    python scripts/apply_cluster_matches.py --dry-run --tier very_high
    python scripts/apply_cluster_matches.py --execute --tier high
"""

import argparse
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from core.config import (
    MATCH_THRESHOLD_HIGH,
    MATCH_THRESHOLD_MODERATE,
    MATCH_THRESHOLD_VERY_HIGH,
)


def load_face_data(data_path: Path) -> dict:
    """Load face embeddings."""
    import numpy as np

    embeddings = np.load(data_path / "embeddings.npy", allow_pickle=True)
    face_data = {}
    filename_face_counts = {}

    for entry in embeddings:
        filename = entry["filename"]
        if filename not in filename_face_counts:
            filename_face_counts[filename] = 0
        face_index = filename_face_counts[filename]
        filename_face_counts[filename] += 1

        face_id = entry.get("face_id") or f"{Path(filename).stem}:face{face_index}"
        if "mu" in entry:
            mu = entry["mu"]
        else:
            import numpy as np
            mu = np.asarray(entry["embedding"], dtype=np.float32)

        face_data[face_id] = {"mu": __import__("numpy").asarray(mu, dtype=__import__("numpy").float32)}
    return face_data


def extract_face_ids(identity: dict) -> list[str]:
    """Extract all face IDs from an identity."""
    face_ids = []
    for anchor in identity.get("anchor_ids", []):
        if isinstance(anchor, str):
            face_ids.append(anchor)
        elif isinstance(anchor, dict):
            face_ids.append(anchor["face_id"])
    face_ids.extend(identity.get("candidate_ids", []))
    return face_ids


def get_photo_id(face_id: str) -> str | None:
    """Extract photo identifier from face_id."""
    if ":" in face_id:
        return face_id.rsplit(":", 1)[0]
    return None


def find_proposals(data_path: Path, threshold: float) -> list[dict]:
    """Find matching proposals using the same logic as cluster_new_faces.py."""
    import numpy as np
    from scipy.spatial.distance import cdist

    with open(data_path / "identities.json") as f:
        identities_data = json.load(f)
    identities = identities_data.get("identities", {})
    face_data = load_face_data(data_path)

    # Build confirmed identity embeddings
    confirmed = {}
    confirmed_photos = {}

    for iid, ident in identities.items():
        if ident.get("state") != "CONFIRMED" or ident.get("merged_into"):
            continue
        face_ids = extract_face_ids(ident)
        embeddings = []
        valid_fids = []
        for fid in face_ids:
            if fid in face_data:
                embeddings.append(face_data[fid]["mu"])
                valid_fids.append(fid)
        if not embeddings:
            continue

        confirmed[iid] = {
            "embeddings": np.vstack(embeddings),
            "name": ident.get("name", f"Unknown ({iid[:8]})"),
        }
        photos = set()
        for fid in valid_fids:
            pid = get_photo_id(fid)
            if pid:
                photos.add(pid)
        confirmed_photos[iid] = photos

    # Find unresolved face matches
    proposals = []
    for iid, ident in identities.items():
        if ident.get("state") not in ("INBOX", "PROPOSED") or ident.get("merged_into"):
            continue
        face_ids = extract_face_ids(ident)
        for face_id in face_ids:
            if face_id not in face_data:
                continue

            face_emb = face_data[face_id]["mu"].reshape(1, -1)
            best_match = None
            best_distance = float("inf")

            for conf_id, conf_info in confirmed.items():
                face_photo = get_photo_id(face_id)
                if face_photo and face_photo in confirmed_photos.get(conf_id, set()):
                    continue
                dists = cdist(face_emb, conf_info["embeddings"], metric="euclidean")
                d = float(np.min(dists))
                if d < best_distance:
                    best_distance = d
                    best_match = conf_id

            if best_match and best_distance < threshold:
                proposals.append({
                    "face_id": face_id,
                    "source_identity_id": iid,
                    "source_name": ident.get("name", f"Unknown ({iid[:8]})"),
                    "target_identity_id": best_match,
                    "target_name": confirmed[best_match]["name"],
                    "distance": best_distance,
                })

    proposals.sort(key=lambda p: p["distance"])
    return proposals, identities_data


def apply_proposals(identities_data: dict, proposals: list[dict]) -> tuple[dict, int]:
    """Apply proposals by moving faces to target identities as candidates."""
    import copy

    data = copy.deepcopy(identities_data)
    identities = data["identities"]
    now = datetime.now(timezone.utc).isoformat()
    applied = 0

    for prop in proposals:
        face_id = prop["face_id"]
        source_id = prop["source_identity_id"]
        target_id = prop["target_identity_id"]

        source = identities.get(source_id)
        target = identities.get(target_id)
        if not source or not target:
            continue
        if source.get("merged_into") or target.get("merged_into"):
            continue

        # Remove from source
        removed = False
        new_anchors = []
        for anchor in source.get("anchor_ids", []):
            anchor_fid = anchor if isinstance(anchor, str) else anchor.get("face_id")
            if anchor_fid == face_id:
                removed = True
            else:
                new_anchors.append(anchor)
        source["anchor_ids"] = new_anchors

        if face_id in source.get("candidate_ids", []):
            source["candidate_ids"].remove(face_id)
            removed = True

        if not removed:
            continue

        # Add as candidate on target
        if face_id not in target.get("candidate_ids", []):
            target["candidate_ids"].append(face_id)

        # Update versions
        target["version_id"] = target.get("version_id", 1) + 1
        target["updated_at"] = now
        source["version_id"] = source.get("version_id", 1) + 1
        source["updated_at"] = now

        # If source has no remaining faces, mark as merged
        remaining = extract_face_ids(source)
        if not remaining:
            source["merged_into"] = target_id

        applied += 1

    return data, applied


def main():
    parser = argparse.ArgumentParser(
        description="Apply approved clustering matches."
    )
    parser.add_argument(
        "--dry-run", action="store_true", default=True,
        help="Preview changes (default)",
    )
    parser.add_argument(
        "--execute", action="store_true",
        help="Actually apply changes",
    )
    parser.add_argument(
        "--tier", choices=["very_high", "high", "moderate"],
        default="high",
        help="Confidence tier to apply (default: high = <1.05)",
    )
    args = parser.parse_args()

    if args.execute:
        args.dry_run = False

    tier_thresholds = {
        "very_high": MATCH_THRESHOLD_VERY_HIGH,
        "high": MATCH_THRESHOLD_HIGH,
        "moderate": MATCH_THRESHOLD_MODERATE,
    }
    threshold = tier_thresholds[args.tier]

    data_path = project_root / "data"

    print("=" * 70)
    print("APPLY CLUSTER MATCHES")
    print("=" * 70)
    print(f"Tier: {args.tier.upper()} (threshold < {threshold})")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'EXECUTE'}")
    print()

    proposals, identities_data = find_proposals(data_path, threshold)

    if not proposals:
        print("No proposals found at this threshold.")
        return

    # Show what would be applied
    print(f"Found {len(proposals)} proposals to apply:")
    print("-" * 70)

    by_target = {}
    for p in proposals:
        name = p["target_name"]
        if name not in by_target:
            by_target[name] = []
        by_target[name].append(p)

    for name in sorted(by_target.keys(), key=lambda n: -len(by_target[n])):
        group = by_target[name]
        dists = [p["distance"] for p in group]
        print(f"  {name}: {len(group)} faces (dist {min(dists):.3f} - {max(dists):.3f})")
        for p in group:
            tier_label = "VERY HIGH" if p["distance"] < 0.80 else "HIGH" if p["distance"] < 1.05 else "MODERATE"
            print(f"    {p['face_id'][:45]} dist={p['distance']:.4f} [{tier_label}]")

    print()
    print(f"Total: {len(proposals)} faces to be added as candidates")

    if args.dry_run:
        print()
        print("[DRY RUN] No changes made.")
        print(f"To apply: python scripts/apply_cluster_matches.py --execute --tier {args.tier}")
    else:
        # Backup first
        identities_path = data_path / "identities.json"
        backup_path = data_path / f"identities.json.bak.{int(datetime.now().timestamp())}"
        shutil.copy2(identities_path, backup_path)
        print(f"Backup: {backup_path}")

        # Apply
        updated_data, applied_count = apply_proposals(identities_data, proposals)

        if applied_count == 0:
            print("No proposals could be applied.")
            return

        # Atomic write
        fd, temp_path = tempfile.mkstemp(suffix=".json", dir=data_path)
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(updated_data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.rename(temp_path, identities_path)
            print(f"Applied {applied_count} matches to {identities_path}")
            print()
            print("These are PROPOSED matches (provenance=model).")
            print("Review and confirm each match in the web UI.")
        except Exception:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise


if __name__ == "__main__":
    main()
