#!/usr/bin/env python3
"""Run the birth year estimation pipeline and print results.

Usage:
    python -m rhodesli_ml.scripts.run_birth_estimation [--dry-run] [--min-appearances N]

The --dry-run flag prints results without writing to disk.
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from rhodesli_ml.pipelines.birth_year_estimation import run_birth_year_estimation


def main():
    parser = argparse.ArgumentParser(description="Estimate birth years for confirmed identities")
    parser.add_argument("--dry-run", action="store_true", help="Print results without writing")
    parser.add_argument("--min-appearances", type=int, default=1,
                        help="Minimum photo appearances for estimation (default: 1)")
    parser.add_argument("--output", default="rhodesli_ml/data/birth_year_estimates.json",
                        help="Output file path")
    args = parser.parse_args()

    output_path = None if args.dry_run else args.output
    result = run_birth_year_estimation(
        output_path=output_path,
        min_appearances=args.min_appearances,
    )

    # Print summary
    stats = result["stats"]
    estimates = result["estimates"]

    print("=" * 70)
    print("BIRTH YEAR ESTIMATION RESULTS")
    print("=" * 70)
    print(f"\nTotal confirmed identities: {stats['total_confirmed']}")
    print(f"With estimates:             {stats['with_estimates']}")
    print(f"  High confidence:          {stats['high_confidence']}")
    print(f"  Medium confidence:        {stats['medium_confidence']}")
    print(f"  Low confidence:           {stats['low_confidence']}")
    print(f"Skipped (no photos):        {stats['skipped_no_photos']}")
    print(f"Skipped (no age data):      {stats['skipped_no_age_data']}")

    print(f"\n{'=' * 70}")
    print(f"{'Name':<35} {'Birth':>6} {'Conf':>8} {'Std':>5} {'N':>3} {'Range':<15}")
    print(f"{'-' * 35} {'-' * 6} {'-' * 8} {'-' * 5} {'-' * 3} {'-' * 15}")

    for est in estimates:
        name = est["name"][:34]
        birth = est["birth_year_estimate"]
        conf = est["birth_year_confidence"]
        std = est["birth_year_std"]
        n = est["n_with_age_data"]
        lo, hi = est["birth_year_range"]
        print(f"{name:<35} {birth:>6} {conf:>8} {std:>5.1f} {n:>3} [{lo}-{hi}]")

    # Print detailed evidence for top 3
    print(f"\n{'=' * 70}")
    print("DETAILED EVIDENCE (top 3 by data points)")
    print(f"{'=' * 70}")

    for est in estimates[:3]:
        print(f"\n--- {est['name']} ---")
        print(f"Birth year estimate: {est['birth_year_estimate']}")
        print(f"Confidence: {est['birth_year_confidence']} (std={est['birth_year_std']:.2f})")
        print(f"Appearances: {est['n_appearances']} photos, {est['n_with_age_data']} with age data")

        if est["flags"]:
            print(f"Flags: {', '.join(est['flags'])}")

        print(f"\n  {'Photo':>16} {'Year':>5} {'Age':>4} {'Birth':>6} {'Method':<15} {'Weight':>6}")
        print(f"  {'-' * 16} {'-' * 5} {'-' * 4} {'-' * 6} {'-' * 15} {'-' * 6}")
        for ev in est["evidence"]:
            print(f"  {ev['photo_id'][:16]:>16} {ev['photo_year']:>5} "
                  f"{ev['estimated_age']:>4} {ev['implied_birth']:>6} "
                  f"{ev['matching_method']:<15} {ev['weight']:>6.1f}")

    if output_path:
        print(f"\nResults written to: {output_path}")
    else:
        print(f"\n(dry-run mode — no output written)")


if __name__ == "__main__":
    main()
