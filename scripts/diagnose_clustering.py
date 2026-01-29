#!/usr/bin/env python3
"""
Diagnostic script to investigate clustering failures.
Analyzes embeddings, sigma values, MLS scores, and clustering configuration.
"""

import numpy as np
from pathlib import Path
import sys

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.pfe import compute_sigma_sq, mutual_likelihood_score

# Paths
DATA_DIR = PROJECT_ROOT / "data"
EMBEDDINGS_PATH = DATA_DIR / "embeddings.npy"


def load_embeddings():
    """Load embeddings from npy file."""
    if not EMBEDDINGS_PATH.exists():
        print(f"ERROR: Embeddings not found at {EMBEDDINGS_PATH}")
        return None

    embeddings = np.load(EMBEDDINGS_PATH, allow_pickle=True)
    return list(embeddings)


def compute_face_sigma(face: dict) -> np.ndarray:
    """Compute sigma_sq for a face using PFE formula."""
    bbox = face["bbox"]
    x1, y1, x2, y2 = bbox
    face_area = (x2 - x1) * (y2 - y1)
    return compute_sigma_sq(face["det_score"], face_area)


def cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(np.dot(v1, v2) / (norm1 * norm2))


def compute_reference_mls(sigma_sq_values: list) -> float:
    """Compute reference MLS for self-match with average sigma."""
    all_sigma = np.array(sigma_sq_values)
    avg_sigma_sq = np.mean(all_sigma, axis=0)
    # Self-match: diff = 0, so only uncertainty term remains
    # MLS = -512 * log(2 * avg_σ²) for 512-D embeddings
    return float(-np.sum(np.log(2 * avg_sigma_sq)))


def print_separator(title: str):
    """Print a section separator."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def section_1_embedding_health(embeddings: list):
    """Analyze embedding vectors for health issues."""
    print_separator("SECTION 1: EMBEDDING HEALTH CHECK")

    n_faces = min(10, len(embeddings))
    print(f"Analyzing first {n_faces} faces out of {len(embeddings)} total\n")

    # Print individual face stats
    print("Individual Face Statistics:")
    print("-" * 70)
    print(f"{'Face':<6} {'Filename':<30} {'emb_min':>8} {'emb_max':>8} {'emb_mean':>8} {'emb_std':>8}")
    print("-" * 70)

    for i in range(n_faces):
        face = embeddings[i]
        emb = face["embedding"]
        filename = Path(face.get("filename", face.get("filepath", "unknown"))).name[:28]

        print(f"{i:<6} {filename:<30} {emb.min():>8.4f} {emb.max():>8.4f} {emb.mean():>8.4f} {emb.std():>8.4f}")

    # Check for identical embeddings
    print("\n\nCosine Similarities (Face 0 vs others):")
    print("-" * 50)

    emb0 = embeddings[0]["embedding"]
    for i in range(1, n_faces):
        emb_i = embeddings[i]["embedding"]
        sim = cosine_similarity(emb0, emb_i)
        filename_i = Path(embeddings[i].get("filename", "unknown")).name[:30]
        flag = "⚠️ VERY HIGH" if sim > 0.95 else ("⚠️ VERY LOW" if sim < 0.1 else "")
        print(f"  Face 0 ↔ Face {i}: {sim:>7.4f}  {filename_i}  {flag}")

    # Full pairwise analysis for first 10
    print("\n\nAll Pairwise Cosine Similarities (first 10 faces):")
    print("-" * 50)

    high_sim_count = 0
    low_sim_count = 0
    all_sims = []

    for i in range(n_faces):
        for j in range(i + 1, n_faces):
            sim = cosine_similarity(embeddings[i]["embedding"], embeddings[j]["embedding"])
            all_sims.append(sim)
            if sim > 0.95:
                high_sim_count += 1
            if sim < 0.1:
                low_sim_count += 1

    if all_sims:
        print(f"  Min cosine sim: {min(all_sims):.4f}")
        print(f"  Max cosine sim: {max(all_sims):.4f}")
        print(f"  Mean cosine sim: {np.mean(all_sims):.4f}")
        print(f"  Std cosine sim: {np.std(all_sims):.4f}")
        print(f"  Pairs with sim > 0.95: {high_sim_count}")
        print(f"  Pairs with sim < 0.10: {low_sim_count}")


def section_2_sigma_analysis(embeddings: list):
    """Analyze sigma (uncertainty) values."""
    print_separator("SECTION 2: SIGMA (UNCERTAINTY) ANALYSIS")

    # Compute all sigma values
    all_sigma_sq = []
    all_det_scores = []
    all_face_areas = []

    for face in embeddings:
        bbox = face["bbox"]
        x1, y1, x2, y2 = bbox
        face_area = (x2 - x1) * (y2 - y1)
        sigma_sq = compute_sigma_sq(face["det_score"], face_area)
        all_sigma_sq.append(sigma_sq)
        all_det_scores.append(face["det_score"])
        all_face_areas.append(face_area)

    all_sigma_sq = np.array(all_sigma_sq)

    # Per-face mean sigma (all dimensions same, so just take [0])
    per_face_sigma_scalar = all_sigma_sq[:, 0]

    print("Per-Face σ² Statistics (computed from det_score and face_area):")
    print("-" * 50)
    print(f"  Number of faces: {len(embeddings)}")
    print(f"  Min σ²: {per_face_sigma_scalar.min():.6f}")
    print(f"  Max σ²: {per_face_sigma_scalar.max():.6f}")
    print(f"  Mean σ²: {per_face_sigma_scalar.mean():.6f}")
    print(f"  Std σ²: {per_face_sigma_scalar.std():.6f}")

    # Quality signal analysis
    print(f"\n  Detection score range: [{min(all_det_scores):.4f}, {max(all_det_scores):.4f}]")
    print(f"  Face area range: [{min(all_face_areas):.0f}, {max(all_face_areas):.0f}] pixels")

    # Check for unreasonable values
    high_sigma_count = np.sum(per_face_sigma_scalar > 0.5)
    very_high_count = np.sum(per_face_sigma_scalar > 0.9)
    low_sigma_count = np.sum(per_face_sigma_scalar < 0.05)

    print(f"\n  Faces with σ² > 0.5 (high uncertainty): {high_sigma_count}")
    print(f"  Faces with σ² > 0.9 (very high uncertainty): {very_high_count}")
    print(f"  Faces with σ² < 0.05 (high confidence): {low_sigma_count}")

    # Show first 10 faces
    print("\n\nFirst 10 Faces - σ² derivation details:")
    print("-" * 85)
    print(f"{'Face':<6} {'Filename':<30} {'det_score':>10} {'face_area':>10} {'σ²':>10}")
    print("-" * 85)

    for i in range(min(10, len(embeddings))):
        face = embeddings[i]
        filename = Path(face.get("filename", face.get("filepath", "unknown"))).name[:28]
        bbox = face["bbox"]
        x1, y1, x2, y2 = bbox
        face_area = (x2 - x1) * (y2 - y1)

        print(f"{i:<6} {filename:<30} {face['det_score']:>10.4f} {face_area:>10.0f} {per_face_sigma_scalar[i]:>10.6f}")

    # Check if all sigma values are identical (constant uncertainty - bad sign)
    sigma_range = per_face_sigma_scalar.max() - per_face_sigma_scalar.min()
    if sigma_range < 0.001:
        print("\n⚠️  WARNING: All faces have nearly identical σ² values!")
        print("    This suggests uncertainty is not varying across faces.")

    return all_sigma_sq


def section_3_mls_matrix(embeddings: list, all_sigma_sq: np.ndarray):
    """Compute and display MLS pairwise matrix."""
    print_separator("SECTION 3: MLS PAIRWISE MATRIX (First 10 Faces)")

    n_faces = min(10, len(embeddings))

    # Compute reference MLS
    ref_mls = compute_reference_mls(list(all_sigma_sq))
    print(f"Reference MLS (self-match baseline): {ref_mls:.2f}\n")

    # Compute MLS matrix
    mls_matrix = np.zeros((n_faces, n_faces))

    for i in range(n_faces):
        for j in range(n_faces):
            if i == j:
                # Self-match
                sigma_sq = all_sigma_sq[i]
                mls_matrix[i, j] = float(-np.sum(np.log(2 * sigma_sq)))
            else:
                mls_matrix[i, j] = mutual_likelihood_score(
                    embeddings[i]["embedding"], all_sigma_sq[i],
                    embeddings[j]["embedding"], all_sigma_sq[j]
                )

    # Print filenames
    print("Face IDs and filenames:")
    for i in range(n_faces):
        filename = Path(embeddings[i].get("filename", "unknown")).name[:40]
        print(f"  [{i}] {filename}")

    # Print matrix header
    print("\n\nMLS Score Matrix:")
    print("-" * (12 + n_faces * 10))
    header = "        " + "".join([f"[{i}]".center(10) for i in range(n_faces)])
    print(header)
    print("-" * (12 + n_faces * 10))

    for i in range(n_faces):
        row = f"[{i}]     "
        for j in range(n_faces):
            score = mls_matrix[i, j]
            row += f"{score:>9.1f} "
        print(row)

    # Analyze off-diagonal scores
    off_diag = []
    for i in range(n_faces):
        for j in range(i + 1, n_faces):
            off_diag.append(mls_matrix[i, j])

    if off_diag:
        print("\n\nOff-diagonal MLS Statistics:")
        print("-" * 50)
        print(f"  Min MLS (least similar pair): {min(off_diag):.2f}")
        print(f"  Max MLS (most similar pair): {max(off_diag):.2f}")
        print(f"  Mean MLS: {np.mean(off_diag):.2f}")
        print(f"  Std MLS: {np.std(off_diag):.2f}")

        # What would clustering threshold be?
        threshold_mls = ref_mls - 30  # Current MLS_DROP_THRESHOLD
        pairs_above_threshold = sum(1 for m in off_diag if m > threshold_mls)
        print(f"\n  Clustering threshold (ref - 30): {threshold_mls:.2f}")
        print(f"  Pairs that would cluster (MLS > threshold): {pairs_above_threshold} / {len(off_diag)}")

    return mls_matrix, ref_mls


def section_4_clustering_config(embeddings: list, ref_mls: float):
    """Show current clustering configuration."""
    print_separator("SECTION 4: CLUSTERING CONFIGURATION")

    # Try to load identities to see current clustering
    identities_path = DATA_DIR / "identities.json"

    print("Current Threshold Configuration:")
    print("-" * 50)
    print(f"  MLS_DROP_THRESHOLD: 30 (hardcoded in core/clustering.py)")
    print(f"  Reference MLS: {ref_mls:.2f}")
    print(f"  Effective threshold: {ref_mls - 30:.2f}")
    print(f"  Linkage method: complete (prevents chaining)")

    if identities_path.exists():
        import json
        with open(identities_path, "r") as f:
            data = json.load(f)

        identities_dict = data.get("identities", {})
        identities = list(identities_dict.values())
        print(f"\n  Number of clusters/identities: {len(identities)}")

        # Show cluster sizes
        cluster_sizes = [len(id_rec.get("candidate_ids", [])) for id_rec in identities]
        if cluster_sizes:
            print(f"  Largest cluster size: {max(cluster_sizes)}")
            print(f"  Smallest cluster size: {min(cluster_sizes)}")
            print(f"  Mean cluster size: {np.mean(cluster_sizes):.1f}")

            # Show first few clusters
            print("\n\nFirst 5 Clusters:")
            print("-" * 70)
            for i, id_rec in enumerate(identities[:5]):
                name = id_rec.get("name", "Unknown")
                candidates = id_rec.get("candidate_ids", [])
                print(f"  {name}: {len(candidates)} faces")
                for cid in candidates[:3]:
                    print(f"    - {cid}")
                if len(candidates) > 3:
                    print(f"    ... and {len(candidates) - 3} more")
    else:
        print(f"\n  ⚠️  No identities file found at {identities_path}")
        print("     Run core/build_clusters.py to generate clusters.")


def section_5_diagnosis(embeddings: list, all_sigma_sq: np.ndarray, mls_matrix: np.ndarray, ref_mls: float):
    """Provide preliminary diagnosis."""
    print_separator("SECTION 5: DIAGNOSIS")

    n_faces = min(10, len(embeddings))

    # Check embeddings
    all_sims = []
    for i in range(n_faces):
        for j in range(i + 1, n_faces):
            sim = cosine_similarity(embeddings[i]["embedding"], embeddings[j]["embedding"])
            all_sims.append(sim)

    mean_cosine = np.mean(all_sims) if all_sims else 0

    # Check sigma values
    per_face_sigma = all_sigma_sq[:, 0]  # All dims same
    mean_sigma = np.mean(per_face_sigma)
    sigma_std = np.std(per_face_sigma)

    # Check MLS spread
    off_diag_mls = []
    for i in range(n_faces):
        for j in range(i + 1, n_faces):
            off_diag_mls.append(mls_matrix[i, j])

    mls_spread = max(off_diag_mls) - min(off_diag_mls) if off_diag_mls else 0
    mean_mls = np.mean(off_diag_mls) if off_diag_mls else 0

    threshold_mls = ref_mls - 30

    issues = []

    # Diagnosis logic
    if mean_cosine > 0.90:
        issues.append(("EMBEDDING ISSUE",
            f"Mean cosine similarity is {mean_cosine:.3f} (>0.90). "
            "Embeddings may be nearly identical or corrupted."))

    if mean_cosine < 0.05:
        issues.append(("EMBEDDING ISSUE",
            f"Mean cosine similarity is {mean_cosine:.3f} (<0.05). "
            "Embeddings may be random noise or corrupted."))

    if sigma_std < 0.001:
        issues.append(("SIGMA ISSUE",
            f"Sigma std is {sigma_std:.6f}. All faces have identical uncertainty. "
            "Per-face sigma computation may be broken."))

    if mean_sigma > 0.8:
        issues.append(("SIGMA ISSUE",
            f"Mean σ² is {mean_sigma:.4f} (>0.8). "
            "All faces have very high uncertainty, MLS will be unreliable."))

    if mls_spread < 50 and mls_spread > 0:
        issues.append(("MLS ISSUE",
            f"MLS spread is only {mls_spread:.1f}. "
            "Different faces have similar MLS scores - clustering can't distinguish them."))

    if mean_mls > threshold_mls:
        issues.append(("THRESHOLD ISSUE",
            f"Mean MLS ({mean_mls:.1f}) > threshold ({threshold_mls:.1f}). "
            "Threshold is too permissive - most pairs will cluster together."))

    # Print diagnosis
    print("Analysis Results:")
    print("-" * 50)
    print(f"  Mean cosine similarity: {mean_cosine:.4f}")
    print(f"  Mean σ²: {mean_sigma:.4f}")
    print(f"  σ² standard deviation: {sigma_std:.6f}")
    print(f"  MLS spread: {mls_spread:.1f}")
    print(f"  Mean MLS: {mean_mls:.1f}")
    print(f"  Threshold MLS: {threshold_mls:.1f}")

    print("\n\nDIAGNOSIS:")
    print("=" * 50)

    if not issues:
        print("✅ UNKNOWN - Data looks reasonable but clustering may still be wrong.")
        print("   Manual inspection of specific problematic clusters needed.")
    else:
        for issue_type, description in issues:
            print(f"\n❌ {issue_type}")
            print(f"   {description}")

    # Additional recommendations
    print("\n\nRECOMMENDATIONS:")
    print("-" * 50)

    if mean_mls > threshold_mls:
        stricter = ref_mls - mean_mls + 10
        print(f"  → Consider stricter threshold: MLS_DROP_THRESHOLD = {stricter:.0f}")
        print(f"    (Current: 30, would need: {ref_mls - mean_mls:.0f}+ to separate mean pair)")

    if mls_spread < 100:
        print("  → MLS scores are too compressed. Check if:")
        print("    1. Sigma values are reasonable (not all high)")
        print("    2. Embeddings are actually different (check cosine sim)")
        print("    3. Face detection is finding actual faces (not noise)")


def main():
    print("\n" + "=" * 70)
    print("  RHODESLI CLUSTERING DIAGNOSTIC REPORT")
    print("=" * 70)

    # Load embeddings
    embeddings = load_embeddings()
    if embeddings is None:
        return

    print(f"\nLoaded {len(embeddings)} face embeddings from {EMBEDDINGS_PATH}")

    # Run all sections
    section_1_embedding_health(embeddings)
    all_sigma_sq = section_2_sigma_analysis(embeddings)
    mls_matrix, ref_mls = section_3_mls_matrix(embeddings, all_sigma_sq)
    section_4_clustering_config(embeddings, ref_mls)
    section_5_diagnosis(embeddings, all_sigma_sq, mls_matrix, ref_mls)

    print("\n" + "=" * 70)
    print("  END OF DIAGNOSTIC REPORT")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
