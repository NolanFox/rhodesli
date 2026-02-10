#!/usr/bin/env python3
"""Validate clustering proposals against user tagging decisions.

Re-runs the clustering match logic (from cluster_new_faces.py) and compares
each proposal against the current state of identities.json to determine
which proposals the admin agreed with, disagreed with, skipped, or rejected.

This script is READ-ONLY. It does NOT modify any data.

Usage:
    python scripts/validate_clustering.py
    python scripts/validate_clustering.py --threshold 1.0
    python scripts/validate_clustering.py --output data/clustering_validation.json
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from core.config import MATCH_THRESHOLD_HIGH


def load_identities(data_path: Path) -> dict:
    """Load identities.json."""
    with open(data_path / "identities.json") as f:
        return json.load(f)


def load_face_data(data_path: Path) -> dict:
    """Load face embeddings as face_id -> {mu, sigma_sq} dict."""
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
            mu = np.asarray(entry["embedding"], dtype=np.float32)

        face_data[face_id] = {"mu": np.asarray(mu, dtype=np.float32)}

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


def compute_min_distance(face_embedding, identity_embeddings) -> float:
    """Min Euclidean distance from face to any anchor in identity (AD-001)."""
    import numpy as np
    from scipy.spatial.distance import cdist

    face_matrix = face_embedding.reshape(1, -1)
    dists = cdist(face_matrix, identity_embeddings, metric="euclidean")
    return float(np.min(dists))


def find_current_identity(face_id: str, identities: dict) -> tuple[str | None, str | None, str | None]:
    """Find which identity a face currently belongs to.

    Returns (identity_id, identity_name, identity_state) or (None, None, None).
    Skips merged identities.
    """
    for iid, ident in identities.items():
        if ident.get("merged_into"):
            continue
        all_faces = extract_face_ids(ident)
        if face_id in all_faces:
            return iid, ident.get("name", f"Unknown ({iid[:8]})"), ident.get("state")
        # Also check negative_ids
        if face_id in ident.get("negative_ids", []):
            return iid, ident.get("name", f"Unknown ({iid[:8]})"), "REJECTED_FROM"
    return None, None, None


def validate(data_path: Path, threshold: float) -> dict:
    """Run clustering validation.

    Re-runs the matching logic, then for each proposal checks what happened.
    """
    import numpy as np

    identities_data = load_identities(data_path)
    identities = identities_data.get("identities", {})
    face_data = load_face_data(data_path)

    # Build confirmed identity embeddings (same logic as cluster_new_faces.py)
    confirmed = {}
    confirmed_photos = {}

    for iid, ident in identities.items():
        if ident.get("state") != "CONFIRMED" or ident.get("merged_into"):
            continue
        face_ids = extract_face_ids(ident)
        if not face_ids:
            continue

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
            "face_count": len(valid_fids),
        }

        photos = set()
        for fid in valid_fids:
            pid = get_photo_id(fid)
            if pid:
                photos.add(pid)
        confirmed_photos[iid] = photos

    print(f"Confirmed identities with embeddings: {len(confirmed)}")

    # Find all proposals: unresolved faces matched against confirmed
    proposals = []
    unresolved_states = {"INBOX", "PROPOSED"}

    for iid, ident in identities.items():
        if ident.get("state") not in unresolved_states or ident.get("merged_into"):
            continue

        face_ids = extract_face_ids(ident)
        for face_id in face_ids:
            if face_id not in face_data:
                continue

            face_emb = face_data[face_id]["mu"]
            best_match = None
            best_distance = float("inf")
            second_best_distance = float("inf")

            for conf_id, conf_info in confirmed.items():
                face_photo = get_photo_id(face_id)
                if face_photo and face_photo in confirmed_photos.get(conf_id, set()):
                    continue

                dist = compute_min_distance(face_emb, conf_info["embeddings"])

                if dist < best_distance:
                    second_best_distance = best_distance
                    best_distance = dist
                    best_match = conf_id
                elif dist < second_best_distance:
                    second_best_distance = dist

            if best_match and best_distance < threshold:
                confidence_gap = second_best_distance - best_distance if second_best_distance < float("inf") else None
                proposals.append({
                    "face_id": face_id,
                    "source_identity_id": iid,
                    "source_identity_name": ident.get("name", f"Unknown ({iid[:8]})"),
                    "proposed_target_id": best_match,
                    "proposed_target_name": confirmed[best_match]["name"],
                    "distance": best_distance,
                    "confidence_gap": confidence_gap,
                })

    proposals.sort(key=lambda p: p["distance"])
    print(f"Total proposals at threshold {threshold}: {len(proposals)}")

    # Now validate each proposal against current identity state
    results = {
        "agreed": [],
        "disagreed": [],
        "skipped": [],
        "rejected": [],
    }

    for prop in proposals:
        face_id = prop["face_id"]
        proposed_target_id = prop["proposed_target_id"]

        # Where is this face NOW?
        current_id, current_name, current_state = find_current_identity(face_id, identities)

        if current_id is None:
            # Face not found in any identity — unusual
            prop["verdict"] = "MISSING"
            prop["current_identity"] = None
            prop["current_name"] = None
            results["skipped"].append(prop)
            continue

        if current_state == "REJECTED_FROM":
            # Face was explicitly rejected from the proposed identity
            prop["verdict"] = "REJECTED"
            prop["current_identity"] = current_id
            prop["current_name"] = current_name
            results["rejected"].append(prop)
            continue

        if current_id == proposed_target_id:
            # Face is now in the proposed identity — algorithm was right
            prop["verdict"] = "AGREED"
            prop["current_identity"] = current_id
            prop["current_name"] = current_name
            results["agreed"].append(prop)
            continue

        # Face is in a different identity — check if it's still unresolved
        current_ident = identities.get(current_id, {})
        current_ident_state = current_ident.get("state")

        if current_ident_state in ("INBOX", "PROPOSED"):
            # Face is still in an unresolved identity — user hasn't decided
            prop["verdict"] = "SKIPPED"
            prop["current_identity"] = current_id
            prop["current_name"] = current_name
            results["skipped"].append(prop)
        elif current_ident_state == "CONFIRMED":
            # Face was moved to a DIFFERENT confirmed identity — disagreement
            prop["verdict"] = "DISAGREED"
            prop["current_identity"] = current_id
            prop["current_name"] = current_name
            prop["analysis"] = (
                f"Algorithm proposed {prop['proposed_target_name']}, "
                f"user chose {current_name}"
            )
            results["disagreed"].append(prop)
        else:
            # Ambiguous (e.g., merged identity) — treat as skipped
            prop["verdict"] = "SKIPPED"
            prop["current_identity"] = current_id
            prop["current_name"] = current_name
            results["skipped"].append(prop)

    return proposals, results, confirmed


def distance_band(d: float) -> str:
    """Classify distance into a band."""
    if d < 0.70:
        return "0.50-0.70"
    elif d < 0.80:
        return "0.70-0.80"
    elif d < 0.90:
        return "0.80-0.90"
    elif d < 1.00:
        return "0.90-1.00"
    else:
        return "1.00+"


def main():
    parser = argparse.ArgumentParser(
        description="Validate clustering proposals against user tagging."
    )
    parser.add_argument(
        "--threshold", type=float, default=MATCH_THRESHOLD_HIGH,
        help=f"Match threshold (default: {MATCH_THRESHOLD_HIGH})",
    )
    parser.add_argument(
        "--output", type=Path, default=None,
        help="Output JSON path (default: data/clustering_validation_<date>.json)",
    )
    args = parser.parse_args()

    data_path = project_root / "data"
    today = datetime.now().strftime("%Y-%m-%d")
    output_path = args.output or (data_path / f"clustering_validation_{today}.json")

    print("=" * 70)
    print("CLUSTERING VALIDATION")
    print("=" * 70)
    print(f"Threshold: {args.threshold}")
    print(f"Data: {data_path}")
    print()

    proposals, results, confirmed = validate(data_path, args.threshold)

    n_agreed = len(results["agreed"])
    n_disagreed = len(results["disagreed"])
    n_skipped = len(results["skipped"])
    n_rejected = len(results["rejected"])
    n_validated = n_agreed + n_disagreed + n_rejected
    total = len(proposals)

    # Precision: of the ones the user acted on, how many did the algorithm get right?
    precision = n_agreed / n_validated if n_validated > 0 else None

    # Coverage: what fraction of proposals did the user review?
    coverage = n_validated / total if total > 0 else None

    print()
    print("=" * 70)
    print("VALIDATION RESULTS")
    print("=" * 70)
    print(f"Total proposals: {total}")
    print(f"  AGREED (algorithm correct):    {n_agreed}")
    print(f"  DISAGREED (algorithm wrong):   {n_disagreed}")
    print(f"  SKIPPED (user didn't decide):  {n_skipped}")
    print(f"  REJECTED (explicit rejection): {n_rejected}")
    print()
    if precision is not None:
        print(f"Precision: {precision:.1%} ({n_agreed}/{n_validated} validated)")
    else:
        print("Precision: N/A (no validated proposals)")
    if coverage is not None:
        print(f"Coverage:  {coverage:.1%} ({n_validated}/{total} reviewed)")
    else:
        print("Coverage:  N/A")

    # Distance band analysis
    print()
    print("By distance band:")
    print(f"  {'Band':<12} {'Agreed':>8} {'Disagreed':>10} {'Skipped':>8} {'Rejected':>9} {'Precision':>10}")
    print("  " + "-" * 60)

    bands = {}
    for prop in proposals:
        band = distance_band(prop["distance"])
        if band not in bands:
            bands[band] = {"agreed": 0, "disagreed": 0, "skipped": 0, "rejected": 0}
        bands[band][prop["verdict"].lower()] = bands[band].get(prop["verdict"].lower(), 0) + 1

    for band in sorted(bands.keys()):
        b = bands[band]
        a, d, s, r = b.get("agreed", 0), b.get("disagreed", 0), b.get("skipped", 0), b.get("rejected", 0)
        validated = a + d + r
        prec = f"{a/validated:.0%}" if validated > 0 else "N/A"
        print(f"  {band:<12} {a:>8} {d:>10} {s:>8} {r:>9} {prec:>10}")

    # By identity analysis
    print()
    print("By proposed target identity:")
    identity_stats = {}
    for prop in proposals:
        name = prop["proposed_target_name"]
        if name not in identity_stats:
            identity_stats[name] = {"agreed": 0, "disagreed": 0, "skipped": 0, "rejected": 0, "distances": []}
        identity_stats[name][prop["verdict"].lower()] = identity_stats[name].get(prop["verdict"].lower(), 0) + 1
        identity_stats[name]["distances"].append(prop["distance"])

    for name in sorted(identity_stats.keys(), key=lambda n: -sum(
        identity_stats[n].get(k, 0) for k in ("agreed", "disagreed", "skipped", "rejected")
    )):
        s = identity_stats[name]
        total_id = sum(s.get(k, 0) for k in ("agreed", "disagreed", "skipped", "rejected"))
        a = s.get("agreed", 0)
        d = s.get("disagreed", 0)
        sk = s.get("skipped", 0)
        r = s.get("rejected", 0)
        best_dist = min(s["distances"])
        worst_dist = max(s["distances"])
        print(f"  {name}: {total_id} proposals (A={a} D={d} S={sk} R={r}) "
              f"dist=[{best_dist:.3f}-{worst_dist:.3f}]")

    # Disagreement details
    if results["disagreed"]:
        print()
        print("DISAGREEMENT DETAILS:")
        for prop in results["disagreed"]:
            print(f"  Face: {prop['face_id']}")
            print(f"    Proposed: {prop['proposed_target_name']} (dist={prop['distance']:.4f})")
            print(f"    Actual:   {prop['current_name']}")
            if prop.get("analysis"):
                print(f"    Analysis: {prop['analysis']}")

    # Statistical caveat
    print()
    if n_validated < 10:
        stat_caveat = (
            f"Sample size of {n_validated} validated matches is INSUFFICIENT for confident "
            f"threshold calibration. Treat as directional, not definitive. "
            f"Target: 50+ validated matches for reliable calibration."
        )
    elif n_validated < 30:
        stat_caveat = (
            f"Sample size of {n_validated} validated matches is MARGINAL. "
            f"Results are suggestive but confidence intervals are wide. "
            f"Target: 50+ validated matches for reliable calibration."
        )
    else:
        stat_caveat = (
            f"Sample size of {n_validated} validated matches is SUFFICIENT for "
            f"preliminary threshold calibration with moderate confidence."
        )

    print(f"STATISTICAL CAVEAT: {stat_caveat}")

    # Build output JSON
    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_report": "clustering_report_2026-02-07.txt",
        "threshold": args.threshold,
        "total_proposed": total,
        "agreed": n_agreed,
        "disagreed": n_disagreed,
        "skipped": n_skipped,
        "rejected": n_rejected,
        "precision": round(precision, 4) if precision is not None else None,
        "coverage": round(coverage, 4) if coverage is not None else None,
        "by_distance_band": {
            band: {
                "agreed": bands[band].get("agreed", 0),
                "disagreed": bands[band].get("disagreed", 0),
                "skipped": bands[band].get("skipped", 0),
                "rejected": bands[band].get("rejected", 0),
            }
            for band in sorted(bands.keys())
        },
        "by_identity": {
            name: {
                "agreed": stats.get("agreed", 0),
                "disagreed": stats.get("disagreed", 0),
                "skipped": stats.get("skipped", 0),
                "rejected": stats.get("rejected", 0),
                "best_distance": round(min(stats["distances"]), 4),
                "worst_distance": round(max(stats["distances"]), 4),
            }
            for name, stats in identity_stats.items()
        },
        "disagreements": [
            {
                "face_id": p["face_id"],
                "proposed_identity": p["proposed_target_name"],
                "actual_identity": p["current_name"],
                "distance": round(p["distance"], 4),
                "analysis": p.get("analysis", ""),
            }
            for p in results["disagreed"]
        ],
        "agreed_details": [
            {
                "face_id": p["face_id"],
                "identity": p["proposed_target_name"],
                "distance": round(p["distance"], 4),
            }
            for p in results["agreed"]
        ],
        "statistical_caveat": stat_caveat,
    }

    # Write output
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nValidation report written to: {output_path}")

    return output


if __name__ == "__main__":
    main()
