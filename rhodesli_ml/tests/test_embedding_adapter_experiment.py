"""Tests for the Session 97 embedding-adapter experiment harness."""

import json
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("torch", exc_type=ImportError)

from rhodesli_ml.embedding_adapter_experiment import (
    build_identity_records,
    build_pair_records,
    run_embedding_adapter_experiment,
)


def _face(mu):
    return {"mu": np.asarray(mu, dtype=np.float32)}


def test_build_pair_records_keeps_family_and_year_gap_metadata(tmp_path):
    identities = {
        "identities": {
            "fox-1": {
                "name": "Roland Fox",
                "state": "CONFIRMED",
                "anchor_ids": ["photo_a:face0", "photo_b:face0"],
                "candidate_ids": [],
            },
            "fox-2": {
                "name": "Betty Fox",
                "state": "CONFIRMED",
                "anchor_ids": ["photo_c:face0", "photo_d:face0"],
                "candidate_ids": [],
            },
        }
    }
    (tmp_path / "date_labels.json").write_text(
        json.dumps(
            {
                "labels": [
                    {"photo_id": "photo_a", "best_year_estimate": 1920},
                    {"photo_id": "photo_b", "best_year_estimate": 1948},
                    {"photo_id": "photo_c", "best_year_estimate": 1930},
                    {"photo_id": "photo_d", "best_year_estimate": 1935},
                ]
            }
        ),
        encoding="utf-8",
    )
    face_data = {
        "photo_a:face0": _face([1.0, 0.0, 0.0, 0.0]),
        "photo_b:face0": _face([0.9, 0.1, 0.0, 0.0]),
        "photo_c:face0": _face([0.7, 0.3, 0.0, 0.0]),
        "photo_d:face0": _face([0.65, 0.35, 0.0, 0.0]),
    }

    records = build_identity_records(identities, face_data, tmp_path)
    pairs = build_pair_records(records, seed=42)

    positive_gaps = {pair["year_gap"] for pair in pairs if pair["label"] == 1.0}
    negative = next(pair for pair in pairs if pair["label"] == 0.0)
    assert 28 in positive_gaps
    assert negative["family_match"] is True


def test_run_embedding_adapter_experiment_smoke(tmp_path):
    identities = {
        "identities": {
            "fox-1": {
                "name": "Roland Fox",
                "state": "CONFIRMED",
                "anchor_ids": ["fa:face0", "fb:face0"],
                "candidate_ids": [],
            },
            "fox-2": {
                "name": "Betty Fox",
                "state": "CONFIRMED",
                "anchor_ids": ["fc:face0", "fd:face0"],
                "candidate_ids": [],
            },
            "ben-1": {
                "name": "Rachel Benatar",
                "state": "CONFIRMED",
                "anchor_ids": ["ga:face0", "gb:face0"],
                "candidate_ids": [],
            },
            "ben-2": {
                "name": "Joseph Benatar",
                "state": "CONFIRMED",
                "anchor_ids": ["gc:face0", "gd:face0"],
                "candidate_ids": [],
            },
        }
    }
    (tmp_path / "date_labels.json").write_text(
        json.dumps(
            {
                "labels": [
                    {"photo_id": "fa", "best_year_estimate": 1920},
                    {"photo_id": "fb", "best_year_estimate": 1945},
                    {"photo_id": "fc", "best_year_estimate": 1930},
                    {"photo_id": "fd", "best_year_estimate": 1937},
                    {"photo_id": "ga", "best_year_estimate": 1910},
                    {"photo_id": "gb", "best_year_estimate": 1938},
                    {"photo_id": "gc", "best_year_estimate": 1925},
                    {"photo_id": "gd", "best_year_estimate": 1931},
                ]
            }
        ),
        encoding="utf-8",
    )
    face_data = {
        "fa:face0": _face([1.0, 0.0, 0.0, 0.0]),
        "fb:face0": _face([0.95, 0.05, 0.0, 0.0]),
        "fc:face0": _face([0.7, 0.3, 0.0, 0.0]),
        "fd:face0": _face([0.65, 0.35, 0.0, 0.0]),
        "ga:face0": _face([0.0, 1.0, 0.0, 0.0]),
        "gb:face0": _face([0.05, 0.95, 0.0, 0.0]),
        "gc:face0": _face([0.0, 0.7, 0.3, 0.0]),
        "gd:face0": _face([0.0, 0.65, 0.35, 0.0]),
    }

    report = run_embedding_adapter_experiment(identities, face_data, tmp_path, seed=42)

    assert report["dataset"]["confirmed_identities"] == 4
    assert report["identity_holdout"]["status"] == "ok"
    assert report["family_holdout"]["status"] in {"ok", "insufficient_groups"}
    assert "passes" in report["gate"]
