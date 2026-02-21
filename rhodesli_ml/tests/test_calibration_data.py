"""Tests for calibration pair generation and data loading."""

import json
import tempfile
from pathlib import Path

import numpy as np
import pytest
import torch

from rhodesli_ml.calibration.data import (
    PairDataset,
    generate_pairs,
    load_confirmed_identities,
    load_face_embeddings,
    split_identities,
)


@pytest.fixture
def data_dir():
    """Create a temporary data directory with test data."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        # Create identities.json with 6 identities (3 multi-face, 3 single-face)
        identities = {
            "schema_version": 1,
            "identities": {
                "id-a": {
                    "identity_id": "id-a",
                    "name": "Alice",
                    "state": "CONFIRMED",
                    "anchor_ids": ["face-a1", "face-a2", "face-a3"],
                    "candidate_ids": [],
                    "negative_ids": [],
                },
                "id-b": {
                    "identity_id": "id-b",
                    "name": "Bob",
                    "state": "CONFIRMED",
                    "anchor_ids": ["face-b1", "face-b2"],
                    "candidate_ids": [],
                    "negative_ids": [],
                },
                "id-c": {
                    "identity_id": "id-c",
                    "name": "Carol",
                    "state": "CONFIRMED",
                    "anchor_ids": ["face-c1", "face-c2", "face-c3", "face-c4"],
                    "candidate_ids": [],
                    "negative_ids": [],
                },
                "id-d": {
                    "identity_id": "id-d",
                    "name": "Dave",
                    "state": "CONFIRMED",
                    "anchor_ids": ["face-d1"],
                    "candidate_ids": [],
                    "negative_ids": [],
                },
                "id-e": {
                    "identity_id": "id-e",
                    "name": "Eve",
                    "state": "CONFIRMED",
                    "anchor_ids": ["face-e1"],
                    "candidate_ids": [],
                    "negative_ids": [],
                },
                "id-f": {
                    "identity_id": "id-f",
                    "name": "Frank",
                    "state": "CONFIRMED",
                    "anchor_ids": ["face-f1"],
                    "candidate_ids": [],
                    "negative_ids": [],
                },
                # Should be excluded: PROPOSED state
                "id-proposed": {
                    "identity_id": "id-proposed",
                    "name": "Proposed",
                    "state": "PROPOSED",
                    "anchor_ids": ["face-p1"],
                    "candidate_ids": [],
                    "negative_ids": [],
                },
                # Should be excluded: merged
                "id-merged": {
                    "identity_id": "id-merged",
                    "name": "Merged",
                    "state": "CONFIRMED",
                    "merged_into": "id-a",
                    "anchor_ids": ["face-m1"],
                    "candidate_ids": [],
                    "negative_ids": [],
                },
            },
        }
        (tmp_path / "identities.json").write_text(json.dumps(identities))

        # Create embeddings.npy with known vectors
        rng = np.random.RandomState(42)
        face_ids = [
            "face-a1", "face-a2", "face-a3",
            "face-b1", "face-b2",
            "face-c1", "face-c2", "face-c3", "face-c4",
            "face-d1", "face-e1", "face-f1",
        ]
        entries = []
        for fid in face_ids:
            mu = rng.randn(512).astype(np.float32)
            mu = mu / np.linalg.norm(mu)  # Normalize
            entries.append({
                "filename": f"{fid}.jpg",
                "face_id": fid,
                "mu": mu,
                "bbox": [0, 0, 100, 100],
                "det_score": 0.99,
                "quality": 0.8,
            })
        np.save(tmp_path / "embeddings.npy", np.array(entries, dtype=object))

        yield tmp_path


class TestLoadConfirmedIdentities:
    def test_loads_confirmed_only(self, data_dir):
        identities = load_confirmed_identities(data_dir)
        names = {i["name"] for i in identities}
        assert "Alice" in names
        assert "Bob" in names
        assert "Proposed" not in names
        assert "Merged" not in names

    def test_excludes_merged(self, data_dir):
        identities = load_confirmed_identities(data_dir)
        ids = {i["identity_id"] for i in identities}
        assert "id-merged" not in ids

    def test_face_ids_populated(self, data_dir):
        identities = load_confirmed_identities(data_dir)
        alice = next(i for i in identities if i["name"] == "Alice")
        assert len(alice["face_ids"]) == 3
        assert "face-a1" in alice["face_ids"]


class TestLoadFaceEmbeddings:
    def test_loads_all_faces(self, data_dir):
        embs = load_face_embeddings(data_dir)
        assert len(embs) == 12
        assert "face-a1" in embs
        assert "face-f1" in embs

    def test_embedding_shape(self, data_dir):
        embs = load_face_embeddings(data_dir)
        assert embs["face-a1"].shape == (512,)
        assert embs["face-a1"].dtype == np.float32


class TestSplitIdentities:
    def test_no_overlap(self, data_dir):
        identities = load_confirmed_identities(data_dir)
        embs = load_face_embeddings(data_dir)
        train, eval_ = split_identities(identities, embs, seed=42)
        train_ids = {i["identity_id"] for i in train}
        eval_ids = {i["identity_id"] for i in eval_}
        assert train_ids.isdisjoint(eval_ids)

    def test_all_identities_assigned(self, data_dir):
        identities = load_confirmed_identities(data_dir)
        embs = load_face_embeddings(data_dir)
        train, eval_ = split_identities(identities, embs, seed=42)
        assert len(train) + len(eval_) == len(identities)

    def test_eval_has_multi_face(self, data_dir):
        identities = load_confirmed_identities(data_dir)
        embs = load_face_embeddings(data_dir)
        _, eval_ = split_identities(identities, embs, min_eval_multi_face=1, seed=42)
        multi_face_eval = [
            i for i in eval_
            if len([f for f in i["face_ids"] if f in embs]) >= 2
        ]
        assert len(multi_face_eval) >= 1

    def test_deterministic(self, data_dir):
        identities = load_confirmed_identities(data_dir)
        embs = load_face_embeddings(data_dir)
        t1, e1 = split_identities(identities, embs, seed=42)
        t2, e2 = split_identities(identities, embs, seed=42)
        assert {i["identity_id"] for i in t1} == {i["identity_id"] for i in t2}
        assert {i["identity_id"] for i in e1} == {i["identity_id"] for i in e2}


class TestGeneratePairs:
    def test_positive_pairs_correct_count(self, data_dir):
        identities = load_confirmed_identities(data_dir)
        embs = load_face_embeddings(data_dir)
        pairs = generate_pairs(identities, embs, neg_ratio=0, seed=42)
        # Only positives when neg_ratio=0
        # Alice: C(3,2)=3, Bob: C(2,2)=1, Carol: C(4,2)=6 = 10 total
        positive_count = sum(1 for _, _, label in pairs if label == 1.0)
        assert positive_count == 10

    def test_negative_ratio(self, data_dir):
        identities = load_confirmed_identities(data_dir)
        embs = load_face_embeddings(data_dir)
        pairs = generate_pairs(identities, embs, neg_ratio=3, seed=42)
        positives = sum(1 for _, _, label in pairs if label == 1.0)
        negatives = sum(1 for _, _, label in pairs if label == 0.0)
        # Should have approximately 3x negatives (may differ due to hard neg pool)
        assert negatives >= positives  # At least as many negatives
        assert positives == 10

    def test_labels_are_binary(self, data_dir):
        identities = load_confirmed_identities(data_dir)
        embs = load_face_embeddings(data_dir)
        pairs = generate_pairs(identities, embs, seed=42)
        for _, _, label in pairs:
            assert label in (0.0, 1.0)

    def test_embedding_shapes(self, data_dir):
        identities = load_confirmed_identities(data_dir)
        embs = load_face_embeddings(data_dir)
        pairs = generate_pairs(identities, embs, seed=42)
        for emb_a, emb_b, _ in pairs:
            assert emb_a.shape == (512,)
            assert emb_b.shape == (512,)

    def test_empty_identities(self, data_dir):
        embs = load_face_embeddings(data_dir)
        pairs = generate_pairs([], embs, seed=42)
        assert pairs == []

    def test_deterministic(self, data_dir):
        identities = load_confirmed_identities(data_dir)
        embs = load_face_embeddings(data_dir)
        p1 = generate_pairs(identities, embs, seed=42)
        p2 = generate_pairs(identities, embs, seed=42)
        assert len(p1) == len(p2)
        for (a1, b1, l1), (a2, b2, l2) in zip(p1, p2):
            assert np.allclose(a1, a2)
            assert np.allclose(b1, b2)
            assert l1 == l2


class TestPairDataset:
    def test_len(self, data_dir):
        identities = load_confirmed_identities(data_dir)
        embs = load_face_embeddings(data_dir)
        pairs = generate_pairs(identities, embs, seed=42)
        dataset = PairDataset(pairs)
        assert len(dataset) == len(pairs)

    def test_getitem_shapes(self, data_dir):
        identities = load_confirmed_identities(data_dir)
        embs = load_face_embeddings(data_dir)
        pairs = generate_pairs(identities, embs, seed=42)
        dataset = PairDataset(pairs)
        emb_a, emb_b, label = dataset[0]
        assert emb_a.shape == (512,)
        assert emb_b.shape == (512,)
        assert label.shape == ()

    def test_tensor_types(self, data_dir):
        identities = load_confirmed_identities(data_dir)
        embs = load_face_embeddings(data_dir)
        pairs = generate_pairs(identities, embs, seed=42)
        dataset = PairDataset(pairs)
        emb_a, emb_b, label = dataset[0]
        assert emb_a.dtype == torch.float32
        assert emb_b.dtype == torch.float32
        assert label.dtype == torch.float32
