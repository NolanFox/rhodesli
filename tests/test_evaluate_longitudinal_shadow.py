"""Smoke tests for the Phase 2 longitudinal shadow CLI."""

import json

from scripts import evaluate_longitudinal_shadow


def test_evaluate_longitudinal_shadow_writes_report(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "identities.json").write_text(json.dumps({"identities": {}}, indent=2))

    class _Runtime:
        prototype_bank = {"id-a": {"prototype_face_ids": ["face0"]}}

    def _fake_train(*args, **kwargs):
        del args, kwargs
        return (
            {
                "dataset_rows": 12,
                "train_rows": 8,
                "test_rows": 4,
                "top_k": 5,
                "max_prototypes": 5,
                "best_variant": "full",
                "variants": {
                    "full": {
                        "feature_names": ["baseline_distance"],
                        "metrics": {
                            "baseline_top1_recall": 0.7,
                            "reranker_top1_recall": 0.8,
                            "baseline_top3_recall": 0.9,
                            "reranker_top3_recall": 0.95,
                            "baseline_auc": 0.7,
                            "reranker_auc": 0.82,
                            "year_gap_ge_20": {"baseline_top1_recall": 0.5, "reranker_top1_recall": 0.6},
                            "year_gap_ge_30": {"baseline_top1_recall": 0.4, "reranker_top1_recall": 0.45},
                            "dominant_lift_ratio": 2.1,
                            "tail_recall_delta": 0.02,
                            "same_family_false_positive_rate": {"baseline": 0.1, "reranker": 0.08},
                        },
                    }
                },
                "_models": {},
            },
            _Runtime(),
        )

    monkeypatch.setattr(evaluate_longitudinal_shadow, "project_root", tmp_path)
    monkeypatch.setattr(evaluate_longitudinal_shadow, "load_face_data", lambda path: {})
    monkeypatch.setattr(evaluate_longitudinal_shadow, "train_longitudinal_shadow_reranker", _fake_train)

    report_path = tmp_path / "report.json"
    prototype_path = tmp_path / "prototype_bank.json"
    result = evaluate_longitudinal_shadow.main(
        [
            "--dry-run",
            "--output",
            str(report_path),
            "--prototype-output",
            str(prototype_path),
        ]
    )

    assert result == 0
    assert report_path.exists()
    assert prototype_path.exists()

    report = json.loads(report_path.read_text())
    assert report["best_variant"] == "full"
    assert report["phase2_gate"]["passes"] is True
