"""Tests for calibration label lineage and pre-fit safety checks."""

import json
from unittest.mock import patch

from rhodesli_ml.calibration_lineage import (
    LABEL_TYPE_EXPLICIT_NEGATIVE,
    LABEL_TYPE_EXPLICIT_POSITIVE,
    build_calibration_pair_row,
    build_recalibration_status_report,
    record_pair_state_event,
    prepare_pairs_for_recalibration,
)


def test_prepare_pairs_excludes_inactive_rows():
    pairs = [
        build_calibration_pair_row(
            "face_a",
            "face_b",
            similarity_score=0.91,
            is_match=True,
            source="merge_admin",
            label_type=LABEL_TYPE_EXPLICIT_POSITIVE,
            state_event_action="merge",
            actor_id="admin",
            source_surface="test",
        ),
        build_calibration_pair_row(
            "face_c",
            "face_d",
            similarity_score=0.14,
            is_match=False,
            source="reject_admin",
            label_type=LABEL_TYPE_EXPLICIT_NEGATIVE,
            state_event_action="reject",
            actor_id="admin",
            source_surface="test",
            active=False,
        ),
    ]

    prepared = prepare_pairs_for_recalibration(pairs)

    assert prepared["counts"]["active_pair_count"] == 1
    assert prepared["counts"]["inactive_pair_count"] == 1
    assert len(prepared["active_pairs"]) == 1
    assert prepared["active_pairs"][0]["pair_key"] == "face_a::face_b"


def test_prepare_pairs_detects_transitive_conflict():
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
            similarity_score=0.18,
            is_match=False,
            source="reject_admin",
            label_type=LABEL_TYPE_EXPLICIT_NEGATIVE,
            state_event_action="reject",
            actor_id="admin",
            source_surface="test",
        ),
    ]

    prepared = prepare_pairs_for_recalibration(pairs)

    assert prepared["conflicts"]
    assert prepared["conflicts"][0]["type"] == "transitive_conflict"
    assert prepared["conflicts"][0]["pair_key"] == "face_a::face_c"


def test_status_report_without_model_recommends_fit():
    pairs = [
        build_calibration_pair_row(
            "face_a",
            "face_b",
            similarity_score=0.92,
            is_match=True,
            source="merge_admin",
            label_type=LABEL_TYPE_EXPLICIT_POSITIVE,
            state_event_action="merge",
            actor_id="admin",
            source_surface="test",
        ),
        build_calibration_pair_row(
            "face_c",
            "face_d",
            similarity_score=0.11,
            is_match=False,
            source="reject_admin",
            label_type=LABEL_TYPE_EXPLICIT_NEGATIVE,
            state_event_action="reject",
            actor_id="admin",
            source_surface="test",
        ),
    ]

    report = build_recalibration_status_report(pairs, model_report={"status": "no_model"}, source="test")

    assert report["status"] == "ok"
    assert report["should_recalibrate"] is True
    assert report["reason"] == "no_model_exists"


def test_record_pair_state_event_appends_local_audit(tmp_path):
    row = build_calibration_pair_row(
        "face_a",
        "face_b",
        similarity_score=0.91,
        is_match=True,
        source="merge_admin",
        label_type=LABEL_TYPE_EXPLICIT_POSITIVE,
        state_event_action="merge",
        actor_id="admin@test.com",
        source_surface="test",
    )

    with patch("rhodesli_ml.calibration_lineage.DATA_DIR", str(tmp_path)), patch(
        "app.supabase_data.sync_audit_log_entry"
    ) as mock_sync:
        event = record_pair_state_event(
            row,
            source_surface="test",
            actor_id="admin@test.com",
            action="merge",
        )

    audit = json.loads((tmp_path / "audit_log.json").read_text(encoding="utf-8"))
    assert audit["entries"][-1]["target_id"] == row["pair_key"]
    assert audit["entries"][-1]["data"]["event_id"] == event["event_id"]
    mock_sync.assert_called_once()
