"""Smoke test for the embedding-adapter experiment CLI."""

import json

from scripts.run_embedding_adapter_experiment import main


def test_run_embedding_adapter_experiment_cli_writes_report(tmp_path, monkeypatch):
    report_path = tmp_path / "report.json"

    def _fake_run(*_args, **_kwargs):
        return {
            "generated_at": "2026-03-11T00:00:00+00:00",
            "git_commit": "abc123",
            "dataset": {"confirmed_identities": 4},
            "identity_holdout": {"status": "ok"},
            "family_holdout": {"status": "ok"},
            "gate": {"passes": False},
            "_models": {},
        }

    monkeypatch.setattr(
        "scripts.run_embedding_adapter_experiment.run_embedding_adapter_experiment",
        _fake_run,
    )
    monkeypatch.setattr(
        "scripts.run_embedding_adapter_experiment.load_face_data",
        lambda *_args, **_kwargs: {},
    )
    monkeypatch.setattr(
        "scripts.run_embedding_adapter_experiment._load_identities",
        lambda *_args, **_kwargs: {"identities": {}},
    )

    result = main(["--dry-run", "--output", str(report_path)])

    assert result == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["gate"]["passes"] is False
    assert report["identity_holdout"]["status"] == "ok"
