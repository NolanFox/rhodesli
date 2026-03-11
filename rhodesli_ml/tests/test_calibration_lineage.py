"""Tests for calibration label lineage and pre-fit safety checks."""

from rhodesli_ml.calibration_lineage import (
    LABEL_TYPE_EXPLICIT_NEGATIVE,
    LABEL_TYPE_EXPLICIT_POSITIVE,
    build_calibration_pair_row,
    build_recalibration_status_report,
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
