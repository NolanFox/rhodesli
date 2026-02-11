"""Extract confirmed pairs and rejections from identities.json for training.

This module reads the identity registry and produces training signal:
- Confirmed pairs: faces within the same CONFIRMED identity are same-person
- Rejected pairs: faces in negative_ids are confirmed NOT same-person
- Hard negatives: faces from different confirmed identities
"""

import json
import itertools
from pathlib import Path
from typing import NamedTuple

import numpy as np


class FacePair(NamedTuple):
    """A pair of face IDs with a label."""
    face_id_a: str
    face_id_b: str
    label: int  # 1 = same person, 0 = different person
    source: str  # "confirmed", "rejected", "hard_negative"


def load_identities(path: str = "data/identities.json") -> dict:
    """Load identities registry."""
    with open(path) as f:
        data = json.load(f)
    return data.get("identities", data)


def load_embeddings(path: str = "data/embeddings.npy") -> dict:
    """Load embeddings and build face_id -> embedding lookup."""
    raw = np.load(path, allow_pickle=True)
    lookup = {}
    for entry in raw:
        fid = entry.get("face_id")
        if not fid:
            # Generate from filename + index (legacy format)
            continue
        if "embeddings" in entry:
            emb = entry["embeddings"]
            if hasattr(emb, "shape") and len(emb.shape) > 1:
                emb = emb[0]  # Take first embedding if multiple
            lookup[fid] = emb
    return lookup


def harvest_confirmed_pairs(identities: dict) -> list[FacePair]:
    """Extract same-person pairs from confirmed identities.

    For each CONFIRMED identity with N anchor faces, generates
    N*(N-1)/2 positive pairs.
    """
    pairs = []
    for identity in identities.values():
        if not isinstance(identity, dict):
            continue
        if identity.get("state") != "CONFIRMED":
            continue
        if identity.get("merged_into"):
            continue

        face_ids = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])
        face_ids = [f if isinstance(f, str) else f.get("face_id", "") for f in face_ids]
        face_ids = [f for f in face_ids if f]

        for a, b in itertools.combinations(face_ids, 2):
            pairs.append(FacePair(a, b, label=1, source="confirmed"))

    return pairs


def harvest_rejected_pairs(identities: dict) -> list[FacePair]:
    """Extract different-person pairs from explicit rejections.

    For each identity with negative_ids, pairs each negative with
    each anchor/candidate face.
    """
    pairs = []
    for identity in identities.values():
        if not isinstance(identity, dict):
            continue
        if identity.get("merged_into"):
            continue

        neg_ids = identity.get("negative_ids", [])
        if not neg_ids:
            continue

        pos_ids = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])
        pos_ids = [f if isinstance(f, str) else f.get("face_id", "") for f in pos_ids]
        pos_ids = [f for f in pos_ids if f]

        for neg in neg_ids:
            neg_fid = neg if isinstance(neg, str) else neg.get("face_id", "")
            if not neg_fid:
                continue
            for pos in pos_ids:
                pairs.append(FacePair(pos, neg_fid, label=0, source="rejected"))

    return pairs


def harvest_hard_negatives(identities: dict, max_pairs: int = 500) -> list[FacePair]:
    """Generate hard negative pairs from different confirmed identities.

    Pairs faces from different CONFIRMED identities. These are
    high-quality negatives because both identities are human-verified.
    """
    import random

    confirmed = []
    for identity in identities.values():
        if not isinstance(identity, dict):
            continue
        if identity.get("state") != "CONFIRMED" or identity.get("merged_into"):
            continue
        face_ids = identity.get("anchor_ids", [])
        face_ids = [f if isinstance(f, str) else f.get("face_id", "") for f in face_ids]
        face_ids = [f for f in face_ids if f]
        if face_ids:
            confirmed.append(face_ids)

    pairs = []
    if len(confirmed) < 2:
        return pairs

    # Generate cross-identity pairs
    for i, faces_a in enumerate(confirmed):
        for j, faces_b in enumerate(confirmed):
            if i >= j:
                continue
            for a in faces_a[:2]:  # Limit per-identity to avoid explosion
                for b in faces_b[:2]:
                    pairs.append(FacePair(a, b, label=0, source="hard_negative"))

    random.shuffle(pairs)
    return pairs[:max_pairs]


def harvest_all(identities_path: str = "data/identities.json") -> dict:
    """Harvest all training signal from the identity registry.

    Returns dict with:
        confirmed_pairs: list of same-person FacePairs
        rejected_pairs: list of different-person FacePairs from rejections
        hard_negatives: list of different-person FacePairs from cross-identity
        summary: dict with counts
    """
    identities = load_identities(identities_path)

    confirmed = harvest_confirmed_pairs(identities)
    rejected = harvest_rejected_pairs(identities)
    hard_neg = harvest_hard_negatives(identities)

    return {
        "confirmed_pairs": confirmed,
        "rejected_pairs": rejected,
        "hard_negatives": hard_neg,
        "summary": {
            "confirmed_pairs": len(confirmed),
            "rejected_pairs": len(rejected),
            "hard_negatives": len(hard_neg),
            "total_positive": len(confirmed),
            "total_negative": len(rejected) + len(hard_neg),
        }
    }


if __name__ == "__main__":
    result = harvest_all()
    print("Training Signal Summary:")
    for k, v in result["summary"].items():
        print(f"  {k}: {v}")
