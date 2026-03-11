"""Tests for the Phase 3 active-learning queue and label cache."""

import json
from collections import Counter
from pathlib import Path
from unittest.mock import patch

import numpy as np

from rhodesli_ml.active_learning import (
    build_active_learning_queue,
    load_active_learning_labels,
    record_active_learning_label,
    revert_active_learning_label,
    save_active_learning_labels,
)
from rhodesli_ml.calibration_lineage import build_calibration_pair_row


def _face(face_id: str, filename: str, mu: list[float]) -> dict:
    return {
        "face_id": face_id,
        "filename": filename,
        "mu": np.asarray(mu, dtype=np.float32),
        "sigma_sq": np.full(len(mu), 0.5, dtype=np.float32),
    }


def _identity(name: str, state: str, face_ids: list[str]) -> dict:
    return {
        "name": name,
        "state": state,
        "anchor_ids": face_ids,
        "candidate_ids": [],
        "negative_ids": [],
        "version_id": 1,
    }


def test_build_active_learning_queue_respects_diversity_and_exclusions(tmp_path):
    face_data = {
        "fox_a:face0": _face("fox_a:face0", "fox_a.jpg", [0.0, 0.0]),
        "fox_a:face1": _face("fox_a:face1", "fox_a.jpg", [0.05, 0.0]),
        "fox_a:face2": _face("fox_a:face2", "fox_a.jpg", [0.0, 0.05]),
        "fox_b:face0": _face("fox_b:face0", "fox_b.jpg", [0.5, 0.0]),
        "fox_b:face1": _face("fox_b:face1", "fox_b.jpg", [0.55, 0.0]),
        "fox_b:face2": _face("fox_b:face2", "fox_b.jpg", [0.5, 0.05]),
        "tail_c:face0": _face("tail_c:face0", "tail_c.jpg", [1.2, 0.0]),
        "tail_c:face1": _face("tail_c:face1", "tail_c.jpg", [1.25, 0.0]),
        "tail_d:face0": _face("tail_d:face0", "tail_d.jpg", [0.0, 1.2]),
        "tail_d:face1": _face("tail_d:face1", "tail_d.jpg", [0.05, 1.25]),
        "u1:face0": _face("u1:face0", "u1.jpg", [0.25, 0.0]),
        "u2:face0": _face("u2:face0", "u2.jpg", [0.3, 0.02]),
        "u3:face0": _face("u3:face0", "u3.jpg", [1.12, 0.02]),
        "u4:face0": _face("u4:face0", "u4.jpg", [0.03, 1.1]),
        "u5:face0": _face("u5:face0", "u5.jpg", [0.75, 0.02]),
        "u6:face0": _face("u6:face0", "u6.jpg", [0.98, 0.01]),
    }
    identities_data = {
        "identities": {
            "fox-a": _identity("Roland Fox", "CONFIRMED", ["fox_a:face0", "fox_a:face1", "fox_a:face2"]),
            "fox-b": _identity("Betty Fox", "CONFIRMED", ["fox_b:face0", "fox_b:face1", "fox_b:face2"]),
            "tail-c": _identity("Albert Capeluto", "CONFIRMED", ["tail_c:face0", "tail_c:face1"]),
            "tail-d": _identity("Rachel Benatar", "CONFIRMED", ["tail_d:face0", "tail_d:face1"]),
            "src-1": _identity("Unidentified Person 1", "INBOX", ["u1:face0"]),
            "src-2": _identity("Unidentified Person 2", "INBOX", ["u2:face0"]),
            "src-3": _identity("Unidentified Person 3", "INBOX", ["u3:face0"]),
            "src-4": _identity("Unidentified Person 4", "INBOX", ["u4:face0"]),
            "src-5": _identity("Unidentified Person 5", "INBOX", ["u5:face0"]),
            "src-6": _identity("Unidentified Person 6", "INBOX", ["u6:face0"]),
        }
    }

    labels_path = tmp_path / "active_learning_labels.json"
    excluded = build_calibration_pair_row(
        "u1:face0",
        "fox_a:face0",
        similarity_score=0.95,
        is_match=True,
        source="active_learning_same",
        state_event_action="active_learning_label",
        actor_id="admin",
        source_surface="test",
    )
    save_active_learning_labels(
        {
            "schema_version": 1,
            "updated_at": excluded["labeled_at"],
            "labels": {excluded["pair_key"]: excluded},
        },
        labels_path,
    )

    queue = build_active_learning_queue(
        identities_data,
        face_data,
        labels_path=labels_path,
        limit=8,
        top_k=2,
        lower_distance=0.2,
        upper_distance=1.0,
        tail_face_limit=2,
        per_identity_cap=2,
        batch_size=10,
        minimum_hard_share=0.3,
    )

    pair_keys = {item["pair_key"] for item in queue["items"]}
    assert excluded["pair_key"] not in pair_keys
    assert queue["stats"]["candidate_count"] >= len(queue["items"])
    assert queue["stats"]["underrepresented_or_hard_share"] >= 0.3
    first_batch_counts = Counter(item["target_identity_id"] for item in queue["items"][:10])
    assert max(first_batch_counts.values(), default=0) <= 2


def test_record_and_revert_active_learning_label_updates_local_cache(tmp_path):
    labels_path = tmp_path / "active_learning_labels.json"
    embeddings_path = tmp_path / "embeddings.npy"
    np.save(
        embeddings_path,
        [
            {"filename": "a.jpg", "face_id": "a:face0", "mu": np.asarray([1.0, 0.0], dtype=np.float32)},
            {"filename": "b.jpg", "face_id": "b:face0", "mu": np.asarray([0.9, 0.1], dtype=np.float32)},
        ],
        allow_pickle=True,
    )

    with patch("rhodesli_ml.calibration_lineage.DATA_DIR", str(tmp_path)), patch(
        "app.supabase_data.sync_audit_log_entry"
    ) as mock_sync:
        row = record_active_learning_label(
            "a:face0",
            "b:face0",
            is_same_person=False,
            actor_id="admin@test.com",
            labels_path=labels_path,
            embeddings_path=embeddings_path,
            metadata={"queue_run_id": "queue-1"},
        )
        reverted = revert_active_learning_label(
            "a:face0",
            "b:face0",
            actor_id="admin@test.com",
            labels_path=labels_path,
        )

    cache = load_active_learning_labels(labels_path)
    stored = cache["labels"][row["pair_key"]]
    assert stored["active"] is False
    assert stored["is_match"] is False
    assert stored["linked_event_id"] == row["state_event_id"]
    assert reverted is not None
    audit = json.loads((tmp_path / "audit_log.json").read_text(encoding="utf-8"))
    assert [entry["action"] for entry in audit["entries"]][-2:] == ["active_learning_label", "revert"]
    assert mock_sync.call_count == 2
