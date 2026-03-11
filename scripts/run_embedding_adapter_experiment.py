#!/usr/bin/env python3
"""Run the Session 97 embedding-adapter experiment harness."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from core.embeddings_io import load_face_data  # noqa: E402
from rhodesli_ml.embedding_adapter_experiment import (  # noqa: E402
    run_embedding_adapter_experiment,
    save_adapter_artifact,
)


def _load_identities(data_path: Path) -> dict:
    with open(data_path / "identities.json") as handle:
        return json.load(handle)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the embedding-adapter experiment harness")
    parser.add_argument(
        "--output",
        type=Path,
        default=project_root / "docs" / "assessments" / "session-97-phase4-adapter-report.json",
        help="Where to write the experiment report JSON",
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=project_root / "rhodesli_ml" / "artifacts" / "embedding_adapter_experiment",
        help="Where to store the experiment artifact when saving is enabled",
    )
    parser.add_argument("--dry-run", action="store_true", help="Do not persist the artifact")
    parser.add_argument(
        "--force-save",
        action="store_true",
        help="Persist the experiment artifact even when the gate does not pass",
    )
    args = parser.parse_args(argv)

    data_path = project_root / "data"
    identities = _load_identities(data_path)
    face_data = load_face_data(data_path / "embeddings.npy")
    report = run_embedding_adapter_experiment(identities, face_data, data_path)

    artifact_manifest = None
    if not args.dry_run and (report["gate"]["passes"] or args.force_save):
        artifact_manifest = save_adapter_artifact(args.artifact_dir, report)

    sanitized = {key: value for key, value in report.items() if key != "_models"}
    sanitized["artifact_manifest"] = artifact_manifest
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(sanitized, indent=2), encoding="utf-8")

    print(f"identity_holdout={sanitized['identity_holdout'].get('status')}")
    print(f"family_holdout={sanitized['family_holdout'].get('status')}")
    print(f"gate={sanitized['gate']}")
    print(f"output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
