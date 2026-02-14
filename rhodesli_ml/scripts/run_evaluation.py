"""CLI for running date estimation model evaluation.

Usage:
    python -m rhodesli_ml.scripts.run_evaluation \\
        --model rhodesli_ml/checkpoints/best.ckpt \\
        --data rhodesli_ml/data/date_labels.json

Exit code 0 = pass, 1 = fail (for CI integration).
"""

import argparse
import json
import sys
from pathlib import Path

import torch

from rhodesli_ml.models.date_classifier import DateEstimationModel
from rhodesli_ml.evaluation.regression_gate import evaluate_model
from rhodesli_ml.data.date_dataset import load_labels_from_file


def main():
    parser = argparse.ArgumentParser(description="Evaluate date estimation model")
    parser.add_argument(
        "--model", required=True,
        help="Path to model checkpoint (.ckpt)",
    )
    parser.add_argument(
        "--data", required=True,
        help="Path to date labels JSON file",
    )
    parser.add_argument(
        "--photos-dir", default="raw_photos",
        help="Directory containing photos",
    )
    parser.add_argument(
        "--output", default=None,
        help="Path to save evaluation results JSON",
    )
    args = parser.parse_args()

    # Load model
    print(f"Loading model from {args.model}...")
    model = DateEstimationModel.load_from_checkpoint(args.model)
    model.eval()

    # Load labels
    print(f"Loading labels from {args.data}...")
    labels = load_labels_from_file(args.data)
    if not labels:
        print("ERROR: No labels found.")
        sys.exit(1)
    print(f"Loaded {len(labels)} labels")

    # Load photo index for path resolution
    photo_index_path = Path("data/photo_index.json")
    photo_index = {}
    if photo_index_path.exists():
        with open(photo_index_path) as f:
            pi_data = json.load(f)
        photo_index = pi_data.get("photos", {})
        print(f"Loaded photo index: {len(photo_index)} photos")

    # Run evaluation
    result = evaluate_model(
        model=model,
        labels=labels,
        photos_dir=args.photos_dir,
        photo_index=photo_index,
    )

    # Print report
    result.print_report()

    # Save results if requested
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(result.to_dict(), f, indent=2)
        print(f"\nResults saved to {output_path}")

    # Exit code for CI
    sys.exit(0 if result.passed else 1)


if __name__ == "__main__":
    main()
