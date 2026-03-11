#!/usr/bin/env python3
"""Build the Phase 3 active-learning queue offline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from core.embeddings_io import load_face_data  # noqa: E402
from rhodesli_ml.active_learning import (  # noqa: E402
    build_active_learning_queue,
    default_labels_path,
    default_queue_path,
    save_active_learning_queue,
)
from rhodesli_ml.calibration_lineage import load_pairs_from_supabase  # noqa: E402


def _load_identities(data_path: Path) -> dict:
    with open(data_path / "identities.json") as handle:
        return json.load(handle)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the offline active-learning queue")
    parser.add_argument(
        "--output",
        type=Path,
        default=default_queue_path(project_root / "data"),
        help="Where to write the queue JSON artifact",
    )
    parser.add_argument(
        "--labels-path",
        type=Path,
        default=default_labels_path(project_root / "data"),
        help="Current-state active-learning label cache used for duplicate exclusion",
    )
    parser.add_argument(
        "--report-output",
        type=Path,
        default=project_root / "docs" / "assessments" / "session-97-phase3-queue-report.json",
        help="Where to write the queue stats report",
    )
    parser.add_argument("--limit", type=int, default=20, help="Maximum queue size")
    parser.add_argument("--top-k", type=int, default=3, help="How many candidates per unresolved face to inspect")
    parser.add_argument(
        "--include-supabase-pairs",
        action="store_true",
        help="Exclude currently active calibration pairs from Supabase in addition to the local label cache",
    )
    args = parser.parse_args(argv)

    data_path = project_root / "data"
    identities = _load_identities(data_path)
    face_data = load_face_data(data_path / "embeddings.npy")

    extra_pairs = None
    if args.include_supabase_pairs:
        try:
            from app.supabase_data import get_supabase_client

            client = get_supabase_client()
        except Exception:
            client = None
        if client is not None:
            extra_pairs = load_pairs_from_supabase(client)

    queue = build_active_learning_queue(
        identities,
        face_data,
        labels_path=args.labels_path,
        extra_pairs=extra_pairs,
        limit=args.limit,
        top_k=args.top_k,
    )
    save_active_learning_queue(queue, args.output)

    report = {
        "generated_at": queue["generated_at"],
        "git_commit": queue["git_commit"],
        "queue_run_id": queue["queue_run_id"],
        "stats": queue["stats"],
        "config": queue["config"],
        "sample_items": queue["items"][:5],
    }
    args.report_output.parent.mkdir(parents=True, exist_ok=True)
    args.report_output.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"queue_run_id={queue['queue_run_id']}")
    print(f"queue_count={queue['stats']['queue_count']}")
    print(f"hard_share={queue['stats']['underrepresented_or_hard_share']}")
    print(f"first_batch_identity_cap_passes={queue['stats']['first_batch_identity_cap_passes']}")
    print(f"output={args.output}")
    print(f"report={args.report_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
