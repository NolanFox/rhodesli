"""Shadow scoring — calibrator alongside existing threshold system.

Scores all inbox faces against confirmed identities using both the
trained calibrator and the current distance threshold system. Saves
results and prints disagreements where the two systems differ.

Usage:
    python -m rhodesli_ml.scripts.shadow_score
    python -m rhodesli_ml.scripts.shadow_score --data-dir data/ --model rhodesli_ml/artifacts/calibration_v1.pt
"""

import argparse
import json
from pathlib import Path

import numpy as np
import torch

from rhodesli_ml.calibration.data import (
    load_confirmed_identities,
    load_face_embeddings,
)
from rhodesli_ml.calibration.evaluate import load_model


def threshold_score(distance: float) -> tuple[str, float]:
    """Current production threshold system: distance -> (tier, score)."""
    if distance < 0.80:
        return "VERY_HIGH", 0.95
    elif distance < 1.00:
        return "HIGH", 0.75
    elif distance < 1.20:
        return "MODERATE", 0.50
    else:
        return "LOW", 0.20


def shadow_score(data_dir: Path, model_path: Path, top_k: int = 5):
    """Score inbox faces against confirmed identities with both systems."""
    # Load data
    identities_raw = json.loads((data_dir / "identities.json").read_text())
    face_embeddings = load_face_embeddings(data_dir)
    confirmed = load_confirmed_identities(data_dir)

    # Build confirmed face -> identity mapping
    confirmed_faces = {}  # face_id -> (identity_id, name, embedding)
    for ident in confirmed:
        for fid in ident["face_ids"]:
            if fid in face_embeddings:
                confirmed_faces[fid] = (ident["identity_id"], ident["name"], face_embeddings[fid])

    # Get inbox faces
    inbox_faces = {}
    for iid, ident in identities_raw["identities"].items():
        if ident.get("state") != "INBOX" or ident.get("merged_into"):
            continue
        face_ids = ident.get("anchor_ids", []) + ident.get("candidate_ids", [])
        for entry in face_ids:
            fid = entry if isinstance(entry, str) else entry.get("face_id")
            if fid and fid in face_embeddings:
                inbox_faces[fid] = (iid, ident.get("name", ""), face_embeddings[fid])

    print(f"Confirmed faces: {len(confirmed_faces)}")
    print(f"Inbox faces: {len(inbox_faces)}")

    if not inbox_faces or not confirmed_faces:
        print("Not enough data for shadow scoring")
        return {}

    # Load calibrator
    model = load_model(model_path)

    # Score each inbox face against all confirmed faces
    results = []
    conf_items = list(confirmed_faces.items())
    conf_embs = np.array([emb for _, (_, _, emb) in conf_items])

    for inbox_fid, (inbox_iid, inbox_name, inbox_emb) in inbox_faces.items():
        # Distances to all confirmed faces
        dists = np.linalg.norm(conf_embs - inbox_emb, axis=1)

        # Calibrator scores
        inbox_tensor = torch.tensor(inbox_emb, dtype=torch.float32).unsqueeze(0).expand(len(conf_embs), -1)
        conf_tensor = torch.tensor(conf_embs, dtype=torch.float32)
        model.eval()
        with torch.no_grad():
            cal_scores = model(inbox_tensor, conf_tensor).squeeze(-1).numpy()

        # Top-k by distance
        top_idx = np.argsort(dists)[:top_k]

        for idx in top_idx:
            conf_fid, (conf_iid, conf_name, _) = conf_items[idx]
            dist = float(dists[idx])
            cal_score = float(cal_scores[idx])
            tier, thresh_score = threshold_score(dist)

            results.append({
                "inbox_face_id": inbox_fid,
                "inbox_identity": inbox_name,
                "confirmed_face_id": conf_fid,
                "confirmed_identity": conf_name,
                "distance": round(dist, 4),
                "threshold_tier": tier,
                "threshold_score": round(thresh_score, 4),
                "calibrator_score": round(cal_score, 4),
                "disagree": (cal_score >= 0.5) != (thresh_score >= 0.5),
            })

    # Find disagreements
    disagreements = [r for r in results if r["disagree"]]
    agreements = [r for r in results if not r["disagree"]]

    # Print summary
    print(f"\nTotal comparisons: {len(results)}")
    print(f"Agreements: {len(agreements)}")
    print(f"Disagreements: {len(disagreements)}")

    if disagreements:
        print(f"\n{'Inbox Face':<30} {'Confirmed':<25} {'Dist':>6} {'Thresh':>8} {'Calib':>8} {'Type':<15}")
        print("-" * 100)
        for d in sorted(disagreements, key=lambda x: x["distance"])[:20]:
            dtype = "CALIB_MATCH" if d["calibrator_score"] >= 0.5 else "THRESH_MATCH"
            print(f"  {d['inbox_identity'][:28]:<30} {d['confirmed_identity'][:23]:<25} "
                  f"{d['distance']:>6.3f} {d['threshold_score']:>8.3f} {d['calibrator_score']:>8.3f} {dtype:<15}")

    # Save results
    output = {
        "metadata": {
            "confirmed_faces": len(confirmed_faces),
            "inbox_faces": len(inbox_faces),
            "top_k": top_k,
            "total_comparisons": len(results),
            "agreements": len(agreements),
            "disagreements": len(disagreements),
        },
        "disagreements": disagreements[:50],  # Limit output size
        "top_matches": sorted(results, key=lambda x: -x["calibrator_score"])[:50],
    }

    return output


def main():
    parser = argparse.ArgumentParser(description="Shadow scoring: calibrator vs thresholds")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--model", type=Path,
                        default=Path("rhodesli_ml/artifacts/calibration_v1.pt"))
    parser.add_argument("--output", type=Path,
                        default=Path("rhodesli_ml/data/shadow_scores.json"))
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    if not args.model.exists():
        print(f"Model not found: {args.model}")
        return

    output = shadow_score(args.data_dir, args.model, args.top_k)

    if output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as f:
            json.dump(output, f, indent=2)
        print(f"\nSaved to {args.output}")


if __name__ == "__main__":
    main()
