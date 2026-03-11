"""Tests for the Phase 0 longitudinal baseline CLI helpers."""

import json
from pathlib import Path

import numpy as np

from scripts.evaluate_longitudinal import (
    compute_identity_volume_stats,
    generate_phase0_baseline,
)


def _identity(identity_id, name, face_ids):
    return {
        "identity_id": identity_id,
        "name": name,
        "state": "CONFIRMED",
        "anchor_ids": list(face_ids),
        "candidate_ids": [],
        "negative_ids": [],
    }


def _embedding_entry(filename: str, face_id: str, vector: np.ndarray) -> dict:
    return {
        "filename": filename,
        "face_id": face_id,
        "mu": vector.astype(np.float32),
        "sigma_sq": np.full(vector.shape[0], 0.2, dtype=np.float32),
        "det_score": 0.9,
    }


def _cluster_vectors(base_index: int, count: int, *, dim: int = 16) -> list[np.ndarray]:
    base = np.zeros(dim, dtype=np.float32)
    base[base_index] = 1.0
    return [base + (np.ones(dim, dtype=np.float32) * 0.01 * idx) for idx in range(count)]


def _write_fixture_archive(tmp_path: Path) -> Path:
    identities = {
        "id_dom_a": _identity(
            "id_dom_a",
            "Dominant A",
            [f"dom_a_{idx}:face0" for idx in range(5)],
        ),
        "id_dom_b": _identity(
            "id_dom_b",
            "Dominant B",
            [f"dom_b_{idx}:face0" for idx in range(4)],
        ),
        "id_dom_c": _identity(
            "id_dom_c",
            "Dominant C",
            [f"dom_c_{idx}:face0" for idx in range(4)],
        ),
        "id_tail": _identity(
            "id_tail",
            "Tail Person",
            ["tail_0:face0", "tail_1:face0"],
        ),
    }
    with open(tmp_path / "identities.json", "w") as handle:
        json.dump({"schema_version": 1, "identities": identities}, handle)

    entries = []
    for prefix, base_index, count in [
        ("dom_a", 0, 5),
        ("dom_b", 1, 4),
        ("dom_c", 2, 4),
        ("tail", 3, 2),
    ]:
        for idx, vector in enumerate(_cluster_vectors(base_index, count)):
            filename = f"{prefix}_{idx}.jpg"
            face_id = f"{prefix}_{idx}:face0"
            entries.append(_embedding_entry(filename, face_id, vector))

    np.save(tmp_path / "embeddings.npy", np.array(entries, dtype=object), allow_pickle=True)
    return tmp_path


class TestComputeIdentityVolumeStats:
    def test_marks_dominant_and_tail_identities(self):
        mappings = (
            [{"identity_id": "a"}] * 5
            + [{"identity_id": "b"}] * 4
            + [{"identity_id": "c"}] * 4
            + [{"identity_id": "tail"}] * 2
        )

        stats = compute_identity_volume_stats(mappings)
        assert stats["dominant_identity_ids"] == ["a", "b", "c"]
        assert stats["tail_identity_ids"] == ["b", "c", "tail"]
        assert stats["tail_identity_count"] == 3
        assert stats["positive_pair_gini"] > 0


class TestGeneratePhase0Baseline:
    def test_returns_rebuilt_golden_set_and_slice_metrics(self, tmp_path):
        data_path = _write_fixture_archive(tmp_path)

        report, golden_set = generate_phase0_baseline(
            data_path,
            threshold=0.5,
            cross_pairs=8,
            seed=7,
        )

        assert golden_set["stats"]["unique_identities"] == 4
        assert report["golden_set_stats"]["total_mappings"] == 15
        assert report["threshold_metrics"]["tp"] > 0
        assert report["slice_metrics"]["dominant_positive_pairs"]["pair_count"] > 0
        assert report["slice_metrics"]["tail_positive_pairs"]["pair_count"] > 0
        assert report["pair_metadata"]["dominant_identities"][0]["identity_id"] == "id_dom_a"
        assert report["mls_vs_euclidean"]["same_pairs"] > 0
        assert report["mls_vs_euclidean"]["cross_pairs"] > 0
