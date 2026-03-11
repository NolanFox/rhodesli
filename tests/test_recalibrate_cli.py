"""Tests for the local recalibration CLI."""

import json
from pathlib import Path

from rhodesli_ml.calibration_lineage import (
    LABEL_TYPE_EXPLICIT_NEGATIVE,
    LABEL_TYPE_EXPLICIT_POSITIVE,
    build_calibration_pair_row,
)
from scripts.recalibrate import main


def _write_pairs(path: Path, pairs: list[dict]) -> None:
    with open(path, "w") as handle:
        json.dump({"pairs": pairs}, handle, indent=2)


def _write_active_learning_labels(path: Path, labels: list[dict]) -> None:
    payload = {
        "schema_version": 1,
        "updated_at": "2026-03-11T00:00:00+00:00",
        "labels": {row["pair_key"]: row for row in labels},
    }
    with open(path, "w") as handle:
        json.dump(payload, handle, indent=2)


def _balanced_pairs() -> list[dict]:
    pairs = []
    for idx in range(6):
        pairs.append(
            build_calibration_pair_row(
                f"match_{idx}",
                f"match_{idx + 10}",
                similarity_score=0.82 + (idx * 0.01),
                is_match=True,
                source="merge_admin",
                label_type=LABEL_TYPE_EXPLICIT_POSITIVE,
                state_event_action="merge",
                actor_id="admin",
                source_surface="test",
            )
        )
        pairs.append(
            build_calibration_pair_row(
                f"nonmatch_{idx}",
                f"nonmatch_{idx + 10}",
                similarity_score=0.08 + (idx * 0.02),
                is_match=False,
                source="reject_admin",
                label_type=LABEL_TYPE_EXPLICIT_NEGATIVE,
                state_event_action="reject",
                actor_id="admin",
                source_surface="test",
            )
        )
    pairs.append(
        build_calibration_pair_row(
            "inactive_a",
            "inactive_b",
            similarity_score=0.19,
            is_match=False,
            source="reject_admin",
            label_type=LABEL_TYPE_EXPLICIT_NEGATIVE,
            state_event_action="reject",
            actor_id="admin",
            source_surface="test",
            active=False,
        )
    )
    return pairs


def test_recalibrate_cli_fits_and_filters_inactive_pairs(tmp_path):
    pairs_path = tmp_path / "pairs.json"
    filtered_path = tmp_path / "filtered_pairs.json"
    report_path = tmp_path / "report.json"
    model_dir = tmp_path / "model"
    _write_pairs(pairs_path, _balanced_pairs())

    result = main(
        [
            "--fit",
            "--pairs-json",
            str(pairs_path),
            "--model-dir",
            str(model_dir),
            "--write-report",
            str(report_path),
            "--write-pairs",
            str(filtered_path),
        ]
    )

    assert result == 0
    assert (model_dir / "calibration_latest.json").exists()

    with open(filtered_path) as handle:
        filtered = json.load(handle)
    assert len(filtered["pairs"]) == 12

    with open(report_path) as handle:
        report = json.load(handle)
    assert report["fit"]["executed"] is True
    assert report["preflight"]["counts"]["inactive_pair_count"] == 1
    assert report["postfit"]["should_recalibrate"] is False


def test_recalibrate_cli_blocks_logical_conflicts(tmp_path):
    pairs_path = tmp_path / "pairs.json"
    report_path = tmp_path / "report.json"
    model_dir = tmp_path / "model"
    pairs = [
        build_calibration_pair_row(
            "face_a",
            "face_b",
            similarity_score=0.95,
            is_match=True,
            source="merge_admin",
            label_type=LABEL_TYPE_EXPLICIT_POSITIVE,
            state_event_action="merge",
            actor_id="admin",
            source_surface="test",
        ),
        build_calibration_pair_row(
            "face_b",
            "face_c",
            similarity_score=0.94,
            is_match=True,
            source="merge_admin",
            label_type=LABEL_TYPE_EXPLICIT_POSITIVE,
            state_event_action="merge",
            actor_id="admin",
            source_surface="test",
        ),
        build_calibration_pair_row(
            "face_a",
            "face_c",
            similarity_score=0.12,
            is_match=False,
            source="reject_admin",
            label_type=LABEL_TYPE_EXPLICIT_NEGATIVE,
            state_event_action="reject",
            actor_id="admin",
            source_surface="test",
        ),
    ]
    _write_pairs(pairs_path, pairs)

    result = main(
        [
            "--fit",
            "--pairs-json",
            str(pairs_path),
            "--model-dir",
            str(model_dir),
            "--write-report",
            str(report_path),
        ]
    )

    assert result == 2
    assert not (model_dir / "calibration_latest.json").exists()

    with open(report_path) as handle:
        report = json.load(handle)
    assert report["status"] == "blocked"
    assert report["preflight"]["conflicts"]


def test_recalibrate_cli_merges_active_learning_labels(tmp_path):
    pairs_path = tmp_path / "pairs.json"
    labels_path = tmp_path / "active_learning_labels.json"
    filtered_path = tmp_path / "filtered_pairs.json"
    report_path = tmp_path / "report.json"
    model_dir = tmp_path / "model"
    _write_pairs(pairs_path, _balanced_pairs())
    extra_label = build_calibration_pair_row(
        "queue_a",
        "queue_b",
        similarity_score=0.88,
        is_match=True,
        source="active_learning_same",
        label_type=LABEL_TYPE_EXPLICIT_POSITIVE,
        state_event_action="active_learning_label",
        actor_id="admin",
        source_surface="test",
    )
    _write_active_learning_labels(labels_path, [extra_label])

    result = main(
        [
            "--check",
            "--pairs-json",
            str(pairs_path),
            "--active-learning-labels",
            str(labels_path),
            "--model-dir",
            str(model_dir),
            "--write-report",
            str(report_path),
            "--write-pairs",
            str(filtered_path),
        ]
    )

    assert result == 0
    with open(filtered_path) as handle:
        filtered = json.load(handle)
    assert any(row["pair_key"] == extra_label["pair_key"] for row in filtered["pairs"])

    with open(report_path) as handle:
        report = json.load(handle)
    assert "active_learning" in report["pair_source"]
