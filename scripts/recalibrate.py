#!/usr/bin/env python3
"""Check and fit the local similarity calibration model.

Phase 1 rules:
- production routes only collect labels
- recalibration is a local explicit step
- inactive / reverted labels are excluded
- logical conflicts block fitting
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from rhodesli_ml.calibration_lineage import (  # noqa: E402
    build_recalibration_status_report,
    load_pairs_from_json,
    load_pairs_from_supabase,
    prepare_pairs_for_recalibration,
    resolve_git_commit,
)
from rhodesli_ml.similarity_calibration import SimilarityCalibrator  # noqa: E402


def _default_model_dir() -> Path:
    return PROJECT_ROOT / "rhodesli_ml" / "artifacts" / "calibration"


def _default_report_path(fit: bool) -> Path:
    reports_dir = _default_model_dir() / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    filename = "recalibration_run_latest.json" if fit else "calibration_status_latest.json"
    return reports_dir / filename


def _load_pairs(args) -> tuple[list[dict], str]:
    if args.pairs_json:
        return load_pairs_from_json(args.pairs_json), f"json:{Path(args.pairs_json).name}"

    from app.supabase_data import get_supabase_client

    sb = get_supabase_client()
    if not sb:
        raise RuntimeError("Supabase client unavailable and no --pairs-json provided")
    return load_pairs_from_supabase(sb), "supabase:calibration_pairs"


def _load_current_model_report(model_dir: Path) -> dict:
    calibrator = SimilarityCalibrator(model_dir=model_dir)
    calibrator.load_latest_model()
    return calibrator.calibration_report()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as handle:
        json.dump(payload, handle, indent=2)


def _print_status(report: dict) -> None:
    counts = report["counts"]
    current_model = report["current_model"]
    print(f"status={report['status']} should_recalibrate={report['should_recalibrate']} reason={report['reason']}")
    print(
        "pairs="
        f"{counts['active_pair_count']} active / {counts['inactive_pair_count']} inactive "
        f"({counts['match_count']} match, {counts['nonmatch_count']} non-match)"
    )
    print(f"label_types={counts['label_type_counts']}")
    if report["conflicts"]:
        print(f"conflicts={len(report['conflicts'])}")
    print(f"current_model={current_model}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local calibration status and retraining")
    parser.add_argument("--check", action="store_true", help="Compute and print calibration status")
    parser.add_argument("--fit", action="store_true", help="Fit a new local calibration model")
    parser.add_argument("--dry-run", action="store_true", help="Do not persist the fitted model")
    parser.add_argument("--pairs-json", help="Use a local JSON payload instead of Supabase")
    parser.add_argument("--write-pairs", help="Write filtered active pairs to this JSON path")
    parser.add_argument("--write-report", help="Write the status/run manifest to this JSON path")
    parser.add_argument("--model-dir", default=str(_default_model_dir()), help="Directory for calibration artifacts")
    args = parser.parse_args(argv)

    if not args.check and not args.fit:
        args.check = True

    model_dir = Path(args.model_dir)
    report_path = Path(args.write_report) if args.write_report else _default_report_path(args.fit)

    try:
        pairs, pair_source = _load_pairs(args)
    except Exception as exc:
        print(f"Failed to load calibration pairs: {exc}", file=sys.stderr)
        return 1

    prepared = prepare_pairs_for_recalibration(pairs)
    current_model = _load_current_model_report(model_dir)
    preflight = build_recalibration_status_report(
        pairs,
        model_report=current_model,
        git_commit=resolve_git_commit(),
        source=pair_source,
    )

    report = {
        "run_id": str(uuid.uuid4()),
        "run_type": "recalibration",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": resolve_git_commit(),
        "pair_source": pair_source,
        "preflight": preflight,
        "fit": {
            "requested": bool(args.fit),
            "executed": False,
            "dry_run": bool(args.dry_run),
            "saved_model_path": None,
        },
    }

    if args.write_pairs:
        _write_json(Path(args.write_pairs), {"pairs": prepared["active_pairs"]})

    if args.check:
        _print_status(preflight)

    if prepared["conflicts"]:
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        report["status"] = "blocked"
        _write_json(report_path, report)
        print(f"Blocked: {len(prepared['conflicts'])} logical conflicts present", file=sys.stderr)
        return 2

    if args.fit:
        calibrator = SimilarityCalibrator(model_dir=model_dir)
        calibrator.load_latest_model()
        model = calibrator.fit(prepared["active_pairs"])
        report["fit"]["executed"] = True
        if not args.dry_run:
            saved_path = calibrator.save_model()
            report["fit"]["saved_model_path"] = str(saved_path) if saved_path else None
        report["new_model"] = calibrator.calibration_report()
        if current_model.get("status") != "no_model":
            report["threshold_delta_90_precision"] = round(
                report["new_model"]["threshold_at_90_precision"] - current_model["threshold_at_90_precision"],
                4,
            )
        report["new_model_version"] = model.version
        report["postfit"] = build_recalibration_status_report(
            prepared["active_pairs"],
            model_report=report["new_model"],
            git_commit=report["git_commit"],
            source=pair_source,
        )

    report["status"] = "ok"
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    _write_json(report_path, report)
    print(f"report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
