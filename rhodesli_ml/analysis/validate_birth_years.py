#!/usr/bin/env python3
"""Validate birth year estimates and produce a report.

Checks:
1. Lists all estimates with evidence and confidence
2. Flags temporal inconsistencies
3. Compares to known/confirmed birth years (from metadata)
4. Identifies identities where more data would help most
5. Outputs a validation report

Usage:
    python -m rhodesli_ml.analysis.validate_birth_years
"""

import json
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))


def load_estimates(path="rhodesli_ml/data/birth_year_estimates.json"):
    with open(path) as f:
        return json.load(f)


def load_identities(path="data/identities.json"):
    with open(path) as f:
        data = json.load(f)
    return data.get("identities", {})


def load_date_labels(path="rhodesli_ml/data/date_labels.json"):
    with open(path) as f:
        data = json.load(f)
    return {label["photo_id"]: label for label in data.get("labels", [])}


def validate():
    estimates_data = load_estimates()
    estimates = estimates_data["estimates"]
    identities = load_identities()
    date_labels = load_date_labels()

    print("=" * 70)
    print("BIRTH YEAR ESTIMATION VALIDATION REPORT")
    print("=" * 70)

    # Section 1: Summary
    stats = estimates_data.get("stats", {})
    print(f"\nGenerated at: {estimates_data.get('generated_at', 'unknown')}")
    print(f"Total confirmed identities: {stats.get('total_confirmed', '?')}")
    print(f"With estimates: {stats.get('with_estimates', '?')}")
    print(f"  High confidence: {stats.get('high_confidence', 0)}")
    print(f"  Medium confidence: {stats.get('medium_confidence', 0)}")
    print(f"  Low confidence: {stats.get('low_confidence', 0)}")

    # Section 2: Metadata comparison
    print(f"\n{'=' * 70}")
    print("METADATA COMPARISON")
    print(f"{'=' * 70}")

    comparisons = 0
    for est in estimates:
        iid = est["identity_id"]
        identity = identities.get(iid, {})
        meta = identity.get("metadata", {}) or {}
        known_birth = meta.get("birth_year")
        if known_birth:
            diff = abs(int(known_birth) - est["birth_year_estimate"])
            status = "MATCH" if diff <= 3 else "CLOSE" if diff <= 7 else "DIVERGE"
            print(f"  {est['name']}: known={known_birth}, estimated={est['birth_year_estimate']}, "
                  f"diff={diff} [{status}]")
            comparisons += 1

    if comparisons == 0:
        print("  No identities have confirmed birth years in metadata.")
        print("  (This is expected — metadata.birth_year has never been populated.)")

    # Section 3: Temporal consistency
    print(f"\n{'=' * 70}")
    print("TEMPORAL CONSISTENCY FLAGS")
    print(f"{'=' * 70}")

    flagged_count = 0
    for est in estimates:
        if est.get("flags"):
            flagged_count += 1
            print(f"\n  {est['name']} (birth ~{est['birth_year_estimate']}):")
            for flag in est["flags"]:
                print(f"    - {flag}")

    if flagged_count == 0:
        print("  No temporal consistency issues found.")

    # Section 4: Data improvement opportunities
    print(f"\n{'=' * 70}")
    print("DATA IMPROVEMENT OPPORTUNITIES")
    print(f"{'=' * 70}")
    print("  Identities where more age-matched photos would improve confidence:\n")

    confirmed = {
        iid: ident for iid, ident in identities.items()
        if ident.get("state") == "CONFIRMED" and "merged_into" not in ident
    }

    # Find identities with many photos but few age matches
    opportunities = []
    estimate_map = {e["identity_id"]: e for e in estimates}
    for iid, ident in confirmed.items():
        est = estimate_map.get(iid)
        n_faces = len(ident.get("anchor_ids", [])) + len(ident.get("candidate_ids", []))
        if est:
            unmatched = est["n_appearances"] - est["n_with_age_data"]
            if unmatched > 0:
                opportunities.append({
                    "name": ident.get("name", "?"),
                    "n_photos": est["n_appearances"],
                    "n_matched": est["n_with_age_data"],
                    "n_unmatched": unmatched,
                    "current_confidence": est["birth_year_confidence"],
                })
        else:
            if n_faces >= 2:
                opportunities.append({
                    "name": ident.get("name", "?"),
                    "n_photos": n_faces,
                    "n_matched": 0,
                    "n_unmatched": n_faces,
                    "current_confidence": "none",
                })

    opportunities.sort(key=lambda x: x["n_unmatched"], reverse=True)

    print(f"  {'Name':<35} {'Photos':>6} {'Matched':>8} {'Gap':>4} {'Confidence':>12}")
    print(f"  {'-' * 35} {'-' * 6} {'-' * 8} {'-' * 4} {'-' * 12}")
    for opp in opportunities[:15]:
        print(f"  {opp['name'][:34]:<35} {opp['n_photos']:>6} "
              f"{opp['n_matched']:>8} {opp['n_unmatched']:>4} {opp['current_confidence']:>12}")

    # Section 5: Big Leon deep dive (validation anchor)
    print(f"\n{'=' * 70}")
    print("VALIDATION ANCHOR: Big Leon Capeluto")
    print(f"{'=' * 70}")

    leon = next((e for e in estimates if "Big Leon" in e["name"]), None)
    if leon:
        print(f"  Birth year estimate: {leon['birth_year_estimate']}")
        print(f"  Confidence: {leon['birth_year_confidence']} (std={leon['birth_year_std']:.2f})")
        print(f"  Range: [{leon['birth_year_range'][0]}, {leon['birth_year_range'][1]}]")
        print(f"  Evidence points: {leon['n_with_age_data']} / {leon['n_appearances']} photos")

        # Show single-person evidence (highest quality)
        single = [e for e in leon["evidence"] if e["matching_method"] == "single_person"]
        if single:
            print(f"\n  Single-person photos (highest quality):")
            for ev in single:
                print(f"    {ev['photo_year']}: age {ev['estimated_age']} → born {ev['implied_birth']}")

        if leon["flags"]:
            print(f"\n  Flags:")
            for flag in leon["flags"]:
                print(f"    - {flag}")
    else:
        print("  WARNING: Big Leon Capeluto not found in estimates!")

    print(f"\n{'=' * 70}")
    print("REPORT COMPLETE")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    validate()
