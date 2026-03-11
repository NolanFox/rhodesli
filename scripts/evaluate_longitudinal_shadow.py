#!/usr/bin/env python3
"""Train and evaluate the Phase 2 longitudinal shadow reranker."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from core.embeddings_io import load_face_data  # noqa: E402
from rhodesli_ml.longitudinal_reranker import (  # noqa: E402
    resolve_git_commit,
    save_shadow_artifact,
    train_longitudinal_shadow_reranker,
)


def atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(suffix=".json", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(payload, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def _load_identities(data_path: Path) -> dict:
    with open(data_path / "identities.json") as handle:
        return json.load(handle)


def _passes_gate(metrics: dict) -> dict:
    baseline_age20 = metrics["year_gap_ge_20"]["baseline_top1_recall"] or 0.0
    reranker_age20 = metrics["year_gap_ge_20"]["reranker_top1_recall"] or 0.0
    same_family = metrics["same_family_false_positive_rate"]
    same_family_ok = (
        same_family["reranker"] is None
        or same_family["baseline"] is None
        or same_family["reranker"] <= same_family["baseline"]
    )
    dominant_ok = metrics["dominant_lift_ratio"] is not None and metrics["dominant_lift_ratio"] < 3.0
    tail_ok = metrics["tail_recall_delta"] is not None and metrics["tail_recall_delta"] >= 0.0
    age20_ok = (reranker_age20 - baseline_age20) >= 0.05
    return {
        "passes": all([same_family_ok, dominant_ok, tail_ok, age20_ok]),
        "age20_improvement": round(reranker_age20 - baseline_age20, 4),
        "same_family_ok": same_family_ok,
        "dominant_bias_ok": dominant_ok,
        "tail_recall_ok": tail_ok,
        "age20_ok": age20_ok,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate the longitudinal shadow reranker")
    parser.add_argument(
        "--output",
        type=Path,
        default=project_root / "evaluation" / "baselines" / "longitudinal_shadow_report.json",
        help="Where to write the JSON evaluation report",
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=project_root / "rhodesli_ml" / "artifacts" / "longitudinal_shadow",
        help="Where to write the best shadow artifact when not using --dry-run",
    )
    parser.add_argument(
        "--prototype-output",
        type=Path,
        default=project_root / "evaluation" / "baselines" / "longitudinal_prototype_bank.json",
        help="Where to write the prototype bank snapshot",
    )
    parser.add_argument("--top-k", type=int, default=5, help="Baseline shortlist size for reranking")
    parser.add_argument("--max-prototypes", type=int, default=5, help="Maximum prototypes per identity")
    parser.add_argument("--dry-run", action="store_true", help="Do not persist the trained model artifact")
    parser.add_argument("--force-save", action="store_true", help="Persist the artifact even if the Phase 2 gate fails")
    args = parser.parse_args(argv)

    data_path = project_root / "data"
    identities = _load_identities(data_path)
    face_data = load_face_data(data_path / "embeddings.npy")

    report, runtime = train_longitudinal_shadow_reranker(
        identities,
        face_data,
        data_path,
        top_k=args.top_k,
        max_prototypes=args.max_prototypes,
    )
    report["trained_at"] = datetime.now(timezone.utc).isoformat()
    report["git_commit"] = resolve_git_commit()
    report["phase2_gate"] = _passes_gate(report["variants"][report["best_variant"]]["metrics"])

    model_manifest = None
    if not args.dry_run and (report["phase2_gate"]["passes"] or args.force_save):
        model_manifest = save_shadow_artifact(args.artifact_dir, report)

    sanitized = {
        key: value
        for key, value in report.items()
        if key != "_models"
    }
    sanitized["artifact_manifest"] = model_manifest
    atomic_write_json(args.output, sanitized)
    atomic_write_json(args.prototype_output, runtime.prototype_bank)

    best_metrics = report["variants"][report["best_variant"]]["metrics"]
    print(f"best_variant={report['best_variant']}")
    print(f"top1 baseline={best_metrics['baseline_top1_recall']} reranker={best_metrics['reranker_top1_recall']}")
    print(
        "year_gap_ge_20 baseline="
        f"{best_metrics['year_gap_ge_20']['baseline_top1_recall']} "
        f"reranker={best_metrics['year_gap_ge_20']['reranker_top1_recall']}"
    )
    print(f"phase2_gate={sanitized['phase2_gate']}")
    print(f"report={args.output}")
    if not args.dry_run:
        print(f"artifact_dir={args.artifact_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
