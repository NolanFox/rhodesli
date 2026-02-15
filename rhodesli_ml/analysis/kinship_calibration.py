"""
Kinship Calibration — Empirical distance thresholds from confirmed identity data.

Computes three distance distributions from confirmed identities:
  SAME_PERSON:      Intra-identity face pairs (faces of one confirmed person)
  SAME_FAMILY:      Cross-identity pairs sharing a surname variant group
  DIFFERENT_PERSON:  Cross-identity pairs from different surname groups

Outputs calibrated thresholds for the Compare tool's tiered display:
  - Identity Match: likely the same person
  - Family Resemblance: possible relative (shared features)
  - Community Member: similar features, no familial link

Usage:
    python -m rhodesli_ml.analysis.kinship_calibration [--output PATH] [--dry-run]

Decision provenance: AD-067 (Kinship Calibration Methodology)
"""

import json
import sys
from itertools import combinations
from pathlib import Path

import numpy as np
from scipy.spatial.distance import cdist


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_confirmed_identities(data_dir: Path) -> list[dict]:
    """Load confirmed, non-merged identities with their face IDs."""
    with open(data_dir / "identities.json") as f:
        raw = json.load(f)

    result = []
    for iid, ident in raw["identities"].items():
        if ident.get("state") != "CONFIRMED":
            continue
        if ident.get("merged_into"):
            continue

        face_ids = []
        for entry in ident.get("anchor_ids", []) + ident.get("candidate_ids", []):
            fid = entry if isinstance(entry, str) else entry.get("face_id")
            if fid:
                face_ids.append(fid)

        result.append({
            "identity_id": iid,
            "name": ident.get("name", ""),
            "face_ids": face_ids,
        })
    return result


def _load_face_embeddings(data_dir: Path) -> dict[str, np.ndarray]:
    """Load face embeddings as face_id -> mu vector.

    Mirrors the face_id generation logic in app/main.py:load_face_embeddings().
    Legacy entries use {stem}:face{index}, inbox entries use stored face_id.
    """
    embeddings = np.load(data_dir / "embeddings.npy", allow_pickle=True)
    face_data = {}
    filename_face_counts: dict[str, int] = {}

    for entry in embeddings:
        filename = str(entry.get("filename", ""))

        # Track face index per filename (same logic as app/main.py)
        if filename not in filename_face_counts:
            filename_face_counts[filename] = 0
        face_index = filename_face_counts[filename]
        filename_face_counts[filename] += 1

        # Use stored face_id if present (inbox format), otherwise generate legacy format
        face_id = entry.get("face_id")
        if not face_id:
            stem = Path(filename).stem
            face_id = f"{stem}:face{face_index}"

        # Extract mu (512-dim embedding)
        mu = entry.get("mu")
        if mu is not None:
            mu = np.asarray(mu, dtype=np.float32)
            if mu.shape == (512,):
                face_data[face_id] = mu

    return face_data


def _load_surname_variants(data_dir: Path) -> dict[str, str]:
    """Build variant -> canonical surname lookup."""
    path = data_dir / "surname_variants.json"
    if not path.exists():
        return {}
    with open(path) as f:
        raw = json.load(f)

    lookup = {}
    for group in raw.get("variant_groups", []):
        canonical = group["canonical"]
        lookup[canonical.lower()] = canonical
        for variant in group.get("variants", []):
            lookup[variant.lower()] = canonical

    return lookup


# ---------------------------------------------------------------------------
# Family grouping
# ---------------------------------------------------------------------------

def _get_family_group(name: str, variant_lookup: dict[str, str]) -> str | None:
    """Determine the canonical family group for a person name."""
    parts = name.split()
    for part in parts:
        canonical = variant_lookup.get(part.lower())
        if canonical:
            return canonical
    return None


# ---------------------------------------------------------------------------
# Distance computation
# ---------------------------------------------------------------------------

def compute_distributions(
    identities: list[dict],
    face_embeddings: dict[str, np.ndarray],
    variant_lookup: dict[str, str],
) -> dict:
    """
    Compute three distance distributions from confirmed identity data.

    Returns dict with:
        same_person_distances: list[float]
        same_family_distances: list[float]
        different_person_distances: list[float]
        metadata: calibration info
    """
    # Build per-identity embedding matrices
    id_embeddings = {}  # identity_id -> np.ndarray (n_faces, 512)
    for ident in identities:
        embs = []
        for fid in ident["face_ids"]:
            if fid in face_embeddings:
                embs.append(face_embeddings[fid])
        if embs:
            id_embeddings[ident["identity_id"]] = np.vstack(embs)

    # Map identity_id -> family group
    id_family = {}
    for ident in identities:
        family = _get_family_group(ident["name"], variant_lookup)
        if family:
            id_family[ident["identity_id"]] = family

    # --- SAME_PERSON: intra-identity pairwise distances ---
    same_person_dists = []
    for iid, emb_matrix in id_embeddings.items():
        if emb_matrix.shape[0] < 2:
            continue
        # All pairwise distances within this identity
        pairwise = cdist(emb_matrix, emb_matrix, metric='euclidean')
        # Upper triangle only (avoid duplicates and self-comparison)
        n = pairwise.shape[0]
        for i in range(n):
            for j in range(i + 1, n):
                same_person_dists.append(float(pairwise[i, j]))

    # --- SAME_FAMILY and DIFFERENT_PERSON: cross-identity distances ---
    same_family_dists = []
    different_person_dists = []

    identity_ids = list(id_embeddings.keys())
    for i, j in combinations(range(len(identity_ids)), 2):
        iid_a = identity_ids[i]
        iid_b = identity_ids[j]
        emb_a = id_embeddings[iid_a]
        emb_b = id_embeddings[iid_b]

        # Use best-linkage (min distance) to represent the pair
        dists = cdist(emb_a, emb_b, metric='euclidean')
        min_dist = float(np.min(dists))

        family_a = id_family.get(iid_a)
        family_b = id_family.get(iid_b)

        if family_a and family_b and family_a == family_b:
            same_family_dists.append(min_dist)
        elif family_a and family_b and family_a != family_b:
            different_person_dists.append(min_dist)
        # If either has no family group, skip (ambiguous)

    return {
        "same_person_distances": same_person_dists,
        "same_family_distances": same_family_dists,
        "different_person_distances": different_person_dists,
        "metadata": {
            "n_confirmed_identities": len(identities),
            "n_with_embeddings": len(id_embeddings),
            "n_multi_face": sum(1 for e in id_embeddings.values() if e.shape[0] >= 2),
            "n_with_family_group": len(id_family),
            "family_groups_found": list(set(id_family.values())),
        },
    }


# ---------------------------------------------------------------------------
# Statistics & threshold recommendation
# ---------------------------------------------------------------------------

def _compute_stats(distances: list[float]) -> dict:
    """Compute summary statistics for a distance distribution."""
    if not distances:
        return {"n": 0}
    arr = np.array(distances)
    return {
        "n": len(arr),
        "mean": round(float(np.mean(arr)), 4),
        "std": round(float(np.std(arr)), 4),
        "min": round(float(np.min(arr)), 4),
        "max": round(float(np.max(arr)), 4),
        "p5": round(float(np.percentile(arr, 5)), 4),
        "p25": round(float(np.percentile(arr, 25)), 4),
        "p50": round(float(np.percentile(arr, 50)), 4),
        "p75": round(float(np.percentile(arr, 75)), 4),
        "p95": round(float(np.percentile(arr, 95)), 4),
    }


def recommend_thresholds(distributions: dict) -> dict:
    """
    Derive recommended thresholds from empirical distributions.

    Key finding: family resemblance is NOT reliably separable from
    different-person distances in embedding space. The same_family
    and different_person distributions overlap almost completely.

    Strategy — three-tier model based on same_person distribution:
    - strong_match:  < P75 of same_person (covers 75% of confirmed pairs)
    - possible_match: < P95 of same_person (covers 95%, includes age/pose extremes)
    - similar_features: between P95 of same_person and P5 of different_person

    Above similar_features threshold: no meaningful facial similarity signal.
    """
    sp = distributions["same_person_distances"]
    sf = distributions["same_family_distances"]
    dp = distributions["different_person_distances"]

    # Strong match: covers 75% of same-person pairs — high confidence
    strong_threshold = round(float(np.percentile(sp, 75)), 4) if sp else 1.10

    # Possible match: covers 95% of same-person pairs — includes extreme
    # age variation, pose, vintage photo quality
    possible_threshold = round(float(np.percentile(sp, 95)), 4) if sp else 1.30

    # Similar features: beyond identity territory, into the overlap zone
    # where family resemblance and coincidental similarity are indistinguishable.
    # Use different_person P25 — below this, SOME faces look similar even though
    # they are confirmed different people.
    dp_p25 = round(float(np.percentile(dp, 25)), 4) if dp else 1.40
    similar_threshold = max(round(possible_threshold + 0.05, 4), dp_p25)

    # Separation metrics — how well can we distinguish the distributions?
    separation = {}
    if sp and dp:
        # Cohen's d between same_person and different_person
        sp_arr = np.array(sp)
        dp_arr = np.array(dp)
        pooled_std = np.sqrt((sp_arr.std()**2 + dp_arr.std()**2) / 2)
        if pooled_std > 0:
            separation["cohens_d_sp_vs_dp"] = round(
                float((dp_arr.mean() - sp_arr.mean()) / pooled_std), 4
            )
    if sf and dp:
        sf_arr = np.array(sf)
        dp_arr = np.array(dp)
        pooled_std = np.sqrt((sf_arr.std()**2 + dp_arr.std()**2) / 2)
        if pooled_std > 0:
            separation["cohens_d_sf_vs_dp"] = round(
                float((dp_arr.mean() - sf_arr.mean()) / pooled_std), 4
            )

    return {
        "strong_match": strong_threshold,
        "possible_match": possible_threshold,
        "similar_features": similar_threshold,
        "separation_metrics": separation,
        "finding": (
            "Family resemblance is NOT reliably separable from different-person "
            "distances in 512-dim embedding space. Same-family and different-person "
            "distributions overlap almost completely. The compare tool uses a "
            "same-person-derived threshold model instead of a kinship model."
        ),
    }


def build_kinship_report(data_dir: Path) -> dict:
    """
    Full calibration: load data, compute distributions, recommend thresholds.

    Returns the complete kinship_thresholds.json structure.
    """
    identities = _load_confirmed_identities(data_dir)
    face_embeddings = _load_face_embeddings(data_dir)
    variant_lookup = _load_surname_variants(data_dir)

    distributions = compute_distributions(identities, face_embeddings, variant_lookup)

    sp_stats = _compute_stats(distributions["same_person_distances"])
    sf_stats = _compute_stats(distributions["same_family_distances"])
    dp_stats = _compute_stats(distributions["different_person_distances"])

    thresholds = recommend_thresholds(distributions)

    from datetime import date
    return {
        "same_person": sp_stats,
        "same_family": sf_stats,
        "different_person": dp_stats,
        "recommended_thresholds": thresholds,
        "calibration_metadata": {
            "n_same_person_pairs": sp_stats["n"],
            "n_same_family_pairs": sf_stats["n"],
            "n_different_pairs": dp_stats["n"],
            "date_calibrated": str(date.today()),
            **distributions["metadata"],
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Compute kinship distance thresholds")
    parser.add_argument("--data-dir", type=Path, default=Path("data"),
                        help="Path to data directory")
    parser.add_argument("--output", type=Path,
                        default=Path("rhodesli_ml/data/model_comparisons/kinship_thresholds.json"),
                        help="Output JSON path")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print results without saving")
    args = parser.parse_args()

    report = build_kinship_report(args.data_dir)

    # Print summary
    print("=" * 60)
    print("KINSHIP CALIBRATION REPORT")
    print("=" * 60)

    for label, key in [
        ("SAME PERSON", "same_person"),
        ("SAME FAMILY", "same_family"),
        ("DIFFERENT PERSON", "different_person"),
    ]:
        stats = report[key]
        if stats["n"] == 0:
            print(f"\n{label}: No data")
            continue
        print(f"\n{label} (n={stats['n']})")
        print(f"  Mean: {stats['mean']:.4f}  Std: {stats['std']:.4f}")
        print(f"  Min:  {stats['min']:.4f}  Max: {stats['max']:.4f}")
        print(f"  P5:   {stats['p5']:.4f}  P25: {stats['p25']:.4f}  P50: {stats['p50']:.4f}")
        print(f"  P75:  {stats['p75']:.4f}  P95: {stats['p95']:.4f}")

    print(f"\nRECOMMENDED THRESHOLDS:")
    t = report["recommended_thresholds"]
    print(f"  Strong Match:        < {t['strong_match']:.4f}  (same person, high confidence)")
    print(f"  Possible Match:      < {t['possible_match']:.4f}  (same person, age/pose variation)")
    print(f"  Similar Features:    < {t['similar_features']:.4f}  (family or coincidence)")
    if "separation_metrics" in t:
        sep = t["separation_metrics"]
        if "cohens_d_sp_vs_dp" in sep:
            print(f"\n  Cohen's d (same_person vs different): {sep['cohens_d_sp_vs_dp']:.2f}")
        if "cohens_d_sf_vs_dp" in sep:
            print(f"  Cohen's d (same_family vs different):  {sep['cohens_d_sf_vs_dp']:.2f}")
            print(f"  (d < 0.5 = small effect — family resemblance is weak in embedding space)")

    meta = report["calibration_metadata"]
    print(f"\nCALIBRATION DATA:")
    print(f"  Confirmed identities:  {meta['n_confirmed_identities']}")
    print(f"  With embeddings:       {meta['n_with_embeddings']}")
    print(f"  Multi-face (2+ faces): {meta['n_multi_face']}")
    print(f"  Family groups:         {meta['family_groups_found']}")

    if args.dry_run:
        print(f"\n[DRY RUN] Would save to {args.output}")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\nSaved to {args.output}")

    return report


if __name__ == "__main__":
    main()
