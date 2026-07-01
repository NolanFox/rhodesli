"""Tests for the Phase 2 longitudinal shadow reranker helpers."""

import json
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("sklearn", exc_type=ImportError)

from rhodesli_ml.longitudinal_reranker import (
    build_prototype_bank,
    build_shadow_dataset,
    load_face_to_photo_lookup,
    load_photo_metadata,
)


def _make_face(mu, det_score=0.9):
    return {"mu": np.asarray(mu, dtype=np.float32), "det_score": det_score}


def test_face_to_photo_lookup_uses_photo_index(tmp_path):
    photo_index = {
        "photos": {
            "photo_hash_a": {"face_ids": ["image_a:face0"], "collection": "A", "source": "A"},
            "photo_hash_b": {"face_ids": ["image_b:face0"], "collection": "B", "source": "B"},
        }
    }
    (tmp_path / "photo_index.json").write_text(json.dumps(photo_index, indent=2))

    lookup = load_face_to_photo_lookup(tmp_path)

    assert lookup["image_a:face0"] == "photo_hash_a"
    assert lookup["image_b:face0"] == "photo_hash_b"


def test_build_prototype_bank_prefers_temporal_spread(tmp_path):
    photo_index = {
        "photos": {
            "photo_1900": {"face_ids": ["alpha:face0"], "collection": "A", "source": "A"},
            "photo_1910": {"face_ids": ["beta:face0"], "collection": "A", "source": "A"},
            "photo_1940": {"face_ids": ["gamma:face0"], "collection": "A", "source": "A"},
        }
    }
    date_labels = {
        "labels": [
            {"photo_id": "photo_1900", "best_year_estimate": 1900},
            {"photo_id": "photo_1910", "best_year_estimate": 1910},
            {"photo_id": "photo_1940", "best_year_estimate": 1940},
        ]
    }
    (tmp_path / "photo_index.json").write_text(json.dumps(photo_index, indent=2))
    (tmp_path / "date_labels.json").write_text(json.dumps(date_labels, indent=2))

    identities_data = {
        "identities": {
            "id-a": {
                "identity_id": "id-a",
                "name": "Alpha",
                "state": "CONFIRMED",
                "anchor_ids": ["alpha:face0", "beta:face0", "gamma:face0"],
                "candidate_ids": [],
                "negative_ids": [],
            }
        }
    }
    face_data = {
        "alpha:face0": _make_face([1.0, 0.0, 0.0]),
        "beta:face0": _make_face([0.9, 0.1, 0.0]),
        "gamma:face0": _make_face([0.8, 0.2, 0.0]),
    }

    photo_metadata = load_photo_metadata(tmp_path)
    prototype_bank = build_prototype_bank(
        identities_data,
        face_data,
        photo_metadata,
        max_prototypes=2,
        face_to_photo_id=load_face_to_photo_lookup(tmp_path),
    )

    selected = prototype_bank["id-a"]["prototype_face_ids"]
    assert len(selected) == 2
    assert "alpha:face0" in selected
    assert "gamma:face0" in selected


def test_build_shadow_dataset_uses_canonical_photo_ids_for_year_gaps(tmp_path):
    photo_index = {
        "photos": {
            "photo_hash_a": {"face_ids": ["image_a:face0"], "collection": "A", "source": "A"},
            "photo_hash_b": {"face_ids": ["image_b:face0"], "collection": "A", "source": "A"},
            "photo_hash_c": {"face_ids": ["image_c:face0"], "collection": "B", "source": "B"},
            "photo_hash_d": {"face_ids": ["image_d:face0"], "collection": "B", "source": "B"},
        }
    }
    date_labels = {
        "labels": [
            {"photo_id": "photo_hash_a", "best_year_estimate": 1900},
            {"photo_id": "photo_hash_b", "best_year_estimate": 1930},
            {"photo_id": "photo_hash_c", "best_year_estimate": 1905},
            {"photo_id": "photo_hash_d", "best_year_estimate": 1910},
        ]
    }
    (tmp_path / "photo_index.json").write_text(json.dumps(photo_index, indent=2))
    (tmp_path / "date_labels.json").write_text(json.dumps(date_labels, indent=2))

    identities_data = {
        "identities": {
            "id-a": {
                "identity_id": "id-a",
                "name": "Alpha",
                "state": "CONFIRMED",
                "anchor_ids": ["image_a:face0", "image_b:face0"],
                "candidate_ids": [],
                "negative_ids": [],
            },
            "id-b": {
                "identity_id": "id-b",
                "name": "Beta",
                "state": "CONFIRMED",
                "anchor_ids": ["image_c:face0", "image_d:face0"],
                "candidate_ids": [],
                "negative_ids": [],
            },
        }
    }
    face_data = {
        "image_a:face0": _make_face([1.0, 0.0, 0.0]),
        "image_b:face0": _make_face([0.99, 0.01, 0.0]),
        "image_c:face0": _make_face([-1.0, 0.0, 0.0]),
        "image_d:face0": _make_face([-0.99, 0.01, 0.0]),
    }

    rows, runtime, meta = build_shadow_dataset(
        identities_data,
        face_data,
        tmp_path,
        top_k=2,
        max_prototypes=2,
    )

    assert rows
    assert runtime.face_to_photo_id["image_a:face0"] == "photo_hash_a"
    assert any(summary["year_gap"] == 30 for summary in meta["query_summary"].values())
