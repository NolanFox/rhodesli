#!/usr/bin/env python3
"""
One-Time Bootstrap: Seed Identity Registry from Clustering Output.

Creates PROPOSED identities from existing face clusters without re-ingesting
images or recomputing embeddings.

Usage:
    python scripts/seed_registry.py --dry-run   # Preview actions
    python scripts/seed_registry.py             # Write to registry

Safety:
    - Aborts if data/identities.json already exists
    - Does not mutate embeddings, crops, or images
"""

import argparse
import hashlib
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from core.clustering import MLS_DROP_THRESHOLD, cluster_identities
from core.pfe import compute_sigma_sq, mutual_likelihood_score
from core.photo_registry import PhotoRegistry
from core.registry import IdentityRegistry
from core.temporal import ERAS, EraEstimate

# Default paths
DEFAULT_EMBEDDINGS_PATH = project_root / "data" / "embeddings.npy"
DEFAULT_REGISTRY_PATH = project_root / "data" / "identities.json"
DEFAULT_PHOTO_INDEX_PATH = project_root / "data" / "photo_index.json"


def generate_photo_id(filename: str) -> str:
    """
    Generate a stable, deterministic photo_id from filename.

    Uses SHA256 hash of the filename (not path) to ensure:
    - Deterministic for the same image
    - Extremely unlikely to collide for different images
    - Portable across different directory structures

    Args:
        filename: Image filename (basename or full path)

    Returns:
        Short hash prefix (16 chars) for human-readability
    """
    # Use basename only for portability
    basename = Path(filename).name
    hash_bytes = hashlib.sha256(basename.encode("utf-8")).hexdigest()
    # Use first 16 chars for readability while maintaining collision resistance
    return hash_bytes[:16]


def create_neutral_era() -> EraEstimate:
    """
    Create a neutral era estimate with uniform probability.

    Used when era classification is not available. Uniform distribution
    means no temporal penalty is applied during clustering.
    """
    uniform_prob = 1.0 / len(ERAS)
    probabilities = {era: uniform_prob for era in ERAS}
    return EraEstimate(
        era=ERAS[1],  # Middle era as default
        probabilities=probabilities,
        confidence=0.0,  # No confidence = uniform prior
    )


def generate_face_id(face: dict, index: int) -> str:
    """
    Generate a stable face ID from filename and index.

    Format: {filename_stem}:face{index}
    Example: photo_001:face0
    """
    filename = face.get("filename", f"unknown_{index}")
    stem = Path(filename).stem
    # Count faces per file to handle multiple faces in same image
    return f"{stem}:face{index}"


def load_embeddings(path: Path) -> list[dict]:
    """
    Load face embeddings from .npy file.

    Returns list of face dicts with mu, sigma_sq, and metadata.
    """
    if not path.exists():
        raise FileNotFoundError(f"Embeddings file not found: {path}")

    data = np.load(path, allow_pickle=True)
    faces = list(data)

    print(f"Loaded {len(faces)} faces from {path}")
    return faces


def convert_to_pfe(face: dict) -> dict:
    """
    Convert legacy embedding format to PFE format if needed.

    Legacy format has 'embedding', PFE format has 'mu' and 'sigma_sq'.

    For bootstrap clustering, we use a minimum sigma_sq of 0.1 to ensure
    clustering behaves correctly (scipy's fcluster requires non-negative
    distances in the linkage matrix).
    """
    # Minimum sigma_sq for bootstrap clustering
    #
    # IMPORTANT: Large sigma_sq destroys identity discrimination!
    # sigma_sq appears in MLS denominator: higher sigma = flatter likelihood surface
    # = less penalty for embedding differences = everything clusters together.
    #
    # Previous value 0.5 caused pathological over-clustering (super-cluster bug).
    # Value of 0.05 preserves embedding-based discrimination while ensuring
    # numeric stability. This is conservative: may under-cluster (prefer precision).
    MIN_BOOTSTRAP_SIGMA_SQ = 0.05

    face_copy = face.copy()

    # Already in PFE format
    if "mu" in face_copy and "sigma_sq" in face_copy:
        # Ensure minimum sigma_sq for clustering stability
        face_copy["sigma_sq"] = np.maximum(face_copy["sigma_sq"], MIN_BOOTSTRAP_SIGMA_SQ)
        return face_copy

    # Convert legacy format
    if "embedding" in face_copy:
        face_copy["mu"] = np.asarray(face_copy["embedding"], dtype=np.float32)

        # Compute sigma_sq from quality signals
        det_score = face_copy.get("det_score", 0.5)
        bbox = face_copy.get("bbox", [0, 0, 100, 100])
        x1, y1, x2, y2 = bbox
        face_area = (x2 - x1) * (y2 - y1)

        sigma_sq = compute_sigma_sq(det_score, face_area)
        # Ensure minimum for clustering stability
        face_copy["sigma_sq"] = np.maximum(sigma_sq, MIN_BOOTSTRAP_SIGMA_SQ)

    return face_copy


def prepare_faces_for_clustering(faces: list[dict]) -> list[dict]:
    """
    Add face_id, photo_id, neutral era, and convert to PFE format for clustering.

    Groups faces by filename to assign sequential indices per image.
    Also generates stable photo_id for PhotoRegistry integration.
    """
    # Group by filename to assign face indices
    faces_by_file = defaultdict(list)
    for i, face in enumerate(faces):
        filename = face.get("filename", f"unknown_{i}")
        faces_by_file[filename].append((i, face))

    # Assign face IDs, photo_ids, and era, convert to PFE
    neutral_era = create_neutral_era()
    prepared = []

    for filename, indexed_faces in faces_by_file.items():
        # Generate stable photo_id for this image
        photo_id = generate_photo_id(filename)

        for face_idx, (original_idx, face) in enumerate(indexed_faces):
            # Convert to PFE format if needed
            face_copy = convert_to_pfe(face)
            face_copy["face_id"] = generate_face_id(face, face_idx)
            face_copy["photo_id"] = photo_id
            face_copy["era"] = neutral_era
            face_copy["_original_index"] = original_idx
            prepared.append(face_copy)

    return prepared


def seed_registry(
    embeddings_path: Path,
    registry_path: Path,
    photo_index_path: Path = None,
    dry_run: bool = False,
) -> dict:
    """
    Bootstrap identity registry and photo index from clustering output.

    Args:
        embeddings_path: Path to embeddings.npy
        registry_path: Path to identities.json (must not exist)
        photo_index_path: Path to photo_index.json (default: data/photo_index.json)
        dry_run: If True, print actions without writing

    Returns:
        Summary dict with counts
    """
    if photo_index_path is None:
        photo_index_path = registry_path.parent / "photo_index.json"

    # Safety check: abort if registry exists
    if registry_path.exists():
        raise FileExistsError(
            f"Registry already exists: {registry_path}\n\n"
            "To apply new clustering parameters, delete the registry and rerun:\n"
            f"    rm {registry_path}\n"
            "    python scripts/seed_registry.py\n\n"
            "WARNING: This will discard all manual identity edits!"
        )

    # Load existing embeddings
    faces = load_embeddings(embeddings_path)
    if not faces:
        raise ValueError("No faces found in embeddings file")

    # Prepare faces for clustering
    prepared_faces = prepare_faces_for_clustering(faces)
    print(f"Prepared {len(prepared_faces)} faces for clustering")

    # Initialize PhotoRegistry and register all faces
    photo_registry = PhotoRegistry()
    for face in prepared_faces:
        face_id = face["face_id"]
        photo_id = face["photo_id"]
        filename = face.get("filename", "unknown")
        photo_registry.register_face(photo_id, filename, face_id)

    # Count unique photos
    unique_photos = len(set(f["photo_id"] for f in prepared_faces))
    print(f"Registered {len(prepared_faces)} faces across {unique_photos} photos")

    # DEBUG: Print MLS scores for first pairs to verify fix
    if len(prepared_faces) >= 2:
        print("\n[DEBUG] MLS scores for first pairs (verifying scalar sigma fix):")
        debug_pairs = []
        for i in range(min(3, len(prepared_faces))):
            for j in range(i + 1, min(4, len(prepared_faces))):
                f1, f2 = prepared_faces[i], prepared_faces[j]
                mls = mutual_likelihood_score(
                    f1["mu"], f1["sigma_sq"],
                    f2["mu"], f2["sigma_sq"]
                )
                pair_name = f"{f1.get('face_id', i)}-{f2.get('face_id', j)}"
                debug_pairs.append(f"{pair_name}={mls:.1f}")
        print(f"  {', '.join(debug_pairs)}")
        print(f"  sigma_sq[0] sample: {prepared_faces[0]['sigma_sq'][0]:.4f}")
        print()

    # Run clustering
    print(f"Running clustering with MLS_DROP_THRESHOLD={MLS_DROP_THRESHOLD}")
    clusters = cluster_identities(prepared_faces)
    print(f"Found {len(clusters)} clusters")

    # Initialize registry
    registry = IdentityRegistry()
    timestamp = datetime.now(timezone.utc).isoformat()

    # Provenance metadata for all seeded identities
    provenance = {
        "source": "auto_cluster",
        "timestamp": timestamp,
        "mls_drop_threshold": MLS_DROP_THRESHOLD,
        "metric": "mls_with_temporal",
        "era_mode": "neutral_uniform",
    }

    # Create identities from clusters
    identities_created = 0
    faces_assigned = 0

    for cluster in clusters:
        cluster_id = cluster["cluster_id"]
        cluster_faces = cluster["faces"]
        match_range = cluster["match_range"]

        # Extract face IDs
        face_ids = [f["face_id"] for f in cluster_faces]

        # Generate neutral human-facing label
        label = f"Unidentified Person {cluster_id:03d}"

        if dry_run:
            print(f"\n[DRY-RUN] Would create identity: {label}")
            print(f"  Cluster ID: {cluster_id}")
            print(f"  Faces ({len(face_ids)}): {face_ids[:5]}{'...' if len(face_ids) > 5 else ''}")
            if match_range:
                min_p, max_p = match_range
                print(f"  Match range: {int(min_p*100)}%-{int(max_p*100)}%")
        else:
            # Create PROPOSED identity with all faces as candidates (no anchors)
            # This allows human review before any faces become authoritative
            identity_id = registry.create_identity(
                anchor_ids=[],  # No anchors initially
                user_source="seed_registry",
                name=label,
                candidate_ids=face_ids,
            )

            # Store provenance in the identity's first history event
            history = registry.get_history(identity_id)
            if history:
                history[0]["metadata"] = {
                    **history[0].get("metadata", {}),
                    "provenance": {
                        **provenance,
                        "cluster_id": cluster_id,
                        "match_range": match_range,
                    },
                }

        identities_created += 1
        faces_assigned += len(face_ids)

    # Save registry and photo index
    if not dry_run:
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry.save(registry_path)
        print(f"\nRegistry saved to: {registry_path}")

        photo_registry.save(photo_index_path)
        print(f"Photo index saved to: {photo_index_path}")

    return {
        "identities_created": identities_created,
        "faces_assigned": faces_assigned,
        "photos_indexed": unique_photos,
        "dry_run": dry_run,
    }


def main():
    parser = argparse.ArgumentParser(
        description="One-time bootstrap: seed identity registry from clustering output",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--embeddings",
        type=Path,
        default=DEFAULT_EMBEDDINGS_PATH,
        help=f"Path to embeddings.npy (default: {DEFAULT_EMBEDDINGS_PATH})",
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=DEFAULT_REGISTRY_PATH,
        help=f"Path to identities.json (default: {DEFAULT_REGISTRY_PATH})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print actions without writing files",
    )
    args = parser.parse_args()

    try:
        summary = seed_registry(
            embeddings_path=args.embeddings,
            registry_path=args.registry,
            dry_run=args.dry_run,
        )

        # Print summary
        print("\n" + "=" * 50)
        print("SUMMARY")
        print("=" * 50)
        print(f"Mode:               {'DRY-RUN' if summary['dry_run'] else 'WRITE'}")
        print(f"Identities created: {summary['identities_created']}")
        print(f"Faces assigned:     {summary['faces_assigned']}")
        print(f"Photos indexed:     {summary['photos_indexed']}")

        if summary["dry_run"]:
            print("\nNo files were written. Run without --dry-run to persist.")

    except FileExistsError as e:
        print(f"ABORT: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
