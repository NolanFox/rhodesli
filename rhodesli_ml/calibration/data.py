"""Pair generation and data loading for similarity calibration.

Generates positive (same-person) and negative (different-person) pairs
from confirmed identities and their face embeddings. Supports hard
negative mining and identity-level train/eval splitting.

Decision provenance: AD-124 (hard negatives), AD-125 (identity split).
"""

import json
import random
from itertools import combinations
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import Dataset


def load_confirmed_identities(data_dir: Path) -> list[dict]:
    """Load confirmed, non-merged identities with their face IDs.

    Returns list of dicts with keys: identity_id, name, face_ids.
    """
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

        if face_ids:
            result.append({
                "identity_id": iid,
                "name": ident.get("name", ""),
                "face_ids": face_ids,
            })
    return result


def load_face_embeddings(data_dir: Path) -> dict[str, np.ndarray]:
    """Load face embeddings as face_id -> 512-dim mu vector."""
    embeddings = np.load(data_dir / "embeddings.npy", allow_pickle=True)
    face_data: dict[str, np.ndarray] = {}
    filename_face_counts: dict[str, int] = {}

    for entry in embeddings:
        filename = str(entry.get("filename", ""))
        if filename not in filename_face_counts:
            filename_face_counts[filename] = 0
        face_index = filename_face_counts[filename]
        filename_face_counts[filename] += 1

        face_id = entry.get("face_id")
        if not face_id:
            stem = Path(filename).stem
            face_id = f"{stem}:face{face_index}"

        mu = entry.get("mu")
        if mu is not None:
            mu = np.asarray(mu, dtype=np.float32)
            if mu.shape == (512,):
                face_data[face_id] = mu

    return face_data


def split_identities(
    identities: list[dict],
    face_embeddings: dict[str, np.ndarray],
    eval_fraction: float = 0.2,
    min_eval_multi_face: int = 4,
    seed: int = 42,
) -> tuple[list[dict], list[dict]]:
    """Split identities into train/eval sets at the identity level.

    Ensures no identity's faces appear in both sets (AD-125).
    Stratifies to guarantee eval has enough multi-face identities.

    Returns (train_identities, eval_identities).
    """
    rng = random.Random(seed)

    # Separate multi-face and single-face identities
    multi_face = []
    single_face = []
    for ident in identities:
        matched = [fid for fid in ident["face_ids"] if fid in face_embeddings]
        if len(matched) >= 2:
            multi_face.append(ident)
        elif len(matched) == 1:
            single_face.append(ident)

    # Shuffle both lists
    rng.shuffle(multi_face)
    rng.shuffle(single_face)

    # Allocate multi-face identities to eval first
    n_eval_multi = max(min_eval_multi_face, int(len(multi_face) * eval_fraction))
    n_eval_multi = min(n_eval_multi, len(multi_face) - 1)  # Keep at least 1 for train

    eval_identities = multi_face[:n_eval_multi]
    train_identities = multi_face[n_eval_multi:]

    # Allocate single-face identities
    n_eval_single = max(0, int(len(single_face) * eval_fraction))
    eval_identities.extend(single_face[:n_eval_single])
    train_identities.extend(single_face[n_eval_single:])

    return train_identities, eval_identities


def generate_pairs(
    identities: list[dict],
    face_embeddings: dict[str, np.ndarray],
    neg_ratio: int = 3,
    hard_neg_threshold: float = 1.2,
    seed: int = 42,
) -> list[tuple[np.ndarray, np.ndarray, float]]:
    """Generate (embedding_a, embedding_b, label) pairs.

    Positives: all face pairs within each multi-face identity.
    Negatives: hard negatives (distance < threshold) + random easy negatives.
    Label: 1.0 for same person, 0.0 for different person.

    Returns list of (emb_a, emb_b, label) tuples.
    """
    from scipy.spatial.distance import cdist

    rng = random.Random(seed)

    # Build per-identity embeddings
    id_embeddings: dict[str, list[tuple[str, np.ndarray]]] = {}
    for ident in identities:
        embs = []
        for fid in ident["face_ids"]:
            if fid in face_embeddings:
                embs.append((fid, face_embeddings[fid]))
        if embs:
            id_embeddings[ident["identity_id"]] = embs

    # Positive pairs: same-person face pairs
    positives = []
    for _iid, embs in id_embeddings.items():
        if len(embs) < 2:
            continue
        for (_, emb_a), (_, emb_b) in combinations(embs, 2):
            positives.append((emb_a, emb_b, 1.0))

    if not positives:
        return []

    # Negative pairs: cross-identity
    target_negatives = len(positives) * neg_ratio
    hard_negatives = []
    easy_negative_pool = []

    identity_ids = list(id_embeddings.keys())
    for i, j in combinations(range(len(identity_ids)), 2):
        iid_a = identity_ids[i]
        iid_b = identity_ids[j]
        embs_a = id_embeddings[iid_a]
        embs_b = id_embeddings[iid_b]

        # Compute pairwise distances
        mat_a = np.vstack([e for _, e in embs_a])
        mat_b = np.vstack([e for _, e in embs_b])
        dists = cdist(mat_a, mat_b, metric="euclidean")

        # Find hard negatives (close but different identity)
        for ai in range(len(embs_a)):
            for bi in range(len(embs_b)):
                dist = dists[ai, bi]
                pair = (embs_a[ai][1], embs_b[bi][1], 0.0)
                if dist < hard_neg_threshold:
                    hard_negatives.append(pair)
                else:
                    easy_negative_pool.append(pair)

    # Sample to reach target count
    negatives = hard_negatives[:]
    if len(negatives) < target_negatives and easy_negative_pool:
        n_easy = target_negatives - len(negatives)
        if n_easy > len(easy_negative_pool):
            negatives.extend(easy_negative_pool)
        else:
            negatives.extend(rng.sample(easy_negative_pool, n_easy))

    all_pairs = positives + negatives
    rng.shuffle(all_pairs)
    return all_pairs


class PairDataset(Dataset):
    """PyTorch Dataset for embedding pairs."""

    def __init__(self, pairs: list[tuple[np.ndarray, np.ndarray, float]]):
        self.emb_a = torch.tensor(
            np.array([p[0] for p in pairs]), dtype=torch.float32
        )
        self.emb_b = torch.tensor(
            np.array([p[1] for p in pairs]), dtype=torch.float32
        )
        self.labels = torch.tensor(
            np.array([p[2] for p in pairs]), dtype=torch.float32
        )

    def __len__(self) -> int:
        return len(self.labels)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        return self.emb_a[idx], self.emb_b[idx], self.labels[idx]
