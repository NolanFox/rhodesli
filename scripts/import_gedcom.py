#!/usr/bin/env python3
"""Import a GEDCOM file and generate match proposals.

Usage:
    python scripts/import_gedcom.py path/to/file.ged [--execute]
    python scripts/import_gedcom.py path/to/file.ged  # dry-run (default)

By default, runs in dry-run mode showing what would happen.
Use --execute to save match proposals to data/gedcom_matches.json
and build/update the relationship and co-occurrence graphs.
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def main():
    parser = argparse.ArgumentParser(description="Import GEDCOM file into Rhodesli")
    parser.add_argument("gedcom_file", help="Path to .ged file")
    parser.add_argument("--execute", action="store_true",
                       help="Save proposals and build graphs (default: dry-run)")
    parser.add_argument("--build-cooccurrence", action="store_true",
                       help="Build co-occurrence graph from existing photo data")
    args = parser.parse_args()

    gedcom_path = Path(args.gedcom_file)
    if not gedcom_path.exists():
        print(f"Error: File not found: {gedcom_path}")
        sys.exit(1)

    data_path = PROJECT_ROOT / "data"

    # --- Step 1: Parse GEDCOM ---
    print(f"\n{'='*60}")
    print(f"Parsing GEDCOM: {gedcom_path.name}")
    print(f"{'='*60}")

    from rhodesli_ml.importers.gedcom_parser import parse_gedcom
    parsed = parse_gedcom(str(gedcom_path))

    print(f"  Individuals: {parsed.individual_count}")
    print(f"  Families:    {parsed.family_count}")
    print()

    # Show sample individuals
    for xref, indi in sorted(parsed.individuals.items()):
        birth = f"b.{indi.birth_year}" if indi.birth_year else "b.?"
        death = f"d.{indi.death_year}" if indi.death_year else ""
        place = indi.birth_place or ""
        print(f"  {indi.full_name:35s} {birth:10s} {death:10s} {place}")

    # --- Step 2: Match against archive identities ---
    print(f"\n{'='*60}")
    print("Matching against archive identities")
    print(f"{'='*60}")

    with open(data_path / "identities.json") as f:
        id_data = json.load(f)
    identities = id_data["identities"]

    # Load ML birth year estimates
    birth_estimates = {}
    for est_path in [
        PROJECT_ROOT / "rhodesli_ml" / "data" / "birth_year_estimates.json",
        data_path / "birth_year_estimates.json",
    ]:
        if est_path.exists():
            with open(est_path) as f:
                est_data = json.load(f)
            birth_estimates = {e["identity_id"]: e for e in est_data.get("estimates", [])}
            break

    from rhodesli_ml.importers.identity_matcher import match_gedcom_to_identities
    result = match_gedcom_to_identities(
        parsed, identities,
        surname_variants_path=str(data_path / "surname_variants.json"),
        birth_year_estimates=birth_estimates,
    )

    print(f"\n  Matches found:      {result.match_count}")
    print(f"  Unmatched GEDCOM:   {len(result.unmatched_gedcom)}")
    print(f"  Unmatched archive:  {len(result.unmatched_identities)}")
    print()

    for p in result.proposals:
        ged = p.gedcom_individual
        score_bar = "#" * int(p.match_score * 20)
        print(f"  [{p.match_score:.0%}] {score_bar:20s} {ged.full_name:25s} -> {p.identity_name}")
        print(f"        Layer {p.match_layer}: {p.match_reason}")
        if ged.birth_year:
            print(f"        GEDCOM: b.{ged.birth_year}", end="")
            if ged.birth_place:
                print(f", {ged.birth_place}", end="")
            if ged.death_year:
                print(f" | d.{ged.death_year}", end="")
            print()
        print()

    if result.unmatched_gedcom:
        print("  Unmatched GEDCOM individuals:")
        for u in result.unmatched_gedcom:
            print(f"    - {u.full_name} (b.{u.birth_year})")
        print()

    # --- Step 3: Build co-occurrence graph ---
    if args.build_cooccurrence or args.execute:
        print(f"\n{'='*60}")
        print("Building co-occurrence graph from photo data")
        print(f"{'='*60}")

        with open(data_path / "photo_index.json") as f:
            photo_index = json.load(f)

        from rhodesli_ml.graph.co_occurrence_graph import build_co_occurrence_graph
        cooccur = build_co_occurrence_graph(identities, photo_index)

        print(f"  Edges:              {cooccur['stats']['total_edges']}")
        print(f"  Photos with pairs:  {cooccur['stats']['total_photos_with_pairs']}")
        print(f"  Max co-occurrences: {cooccur['stats']['max_co_occurrences']}")

        if cooccur["edges"]:
            print("\n  Top co-occurrences:")
            for edge in cooccur["edges"][:5]:
                a = identities.get(edge["person_a"], {}).get("name", "?")
                b = identities.get(edge["person_b"], {}).get("name", "?")
                print(f"    {a} <-> {b}: {edge['count']} shared photos")

    # --- Step 4: Save (if --execute) ---
    if args.execute:
        print(f"\n{'='*60}")
        print("Saving results")
        print(f"{'='*60}")

        # Save match proposals
        from rhodesli_ml.importers.gedcom_matches import save_gedcom_matches
        save_gedcom_matches(
            result.proposals,
            filepath=str(data_path / "gedcom_matches.json"),
            source_file=gedcom_path.name,
        )
        print(f"  Saved {result.match_count} match proposals to data/gedcom_matches.json")

        # Save co-occurrence graph
        from rhodesli_ml.graph.co_occurrence_graph import save_co_occurrence_graph
        save_co_occurrence_graph(cooccur, str(data_path / "co_occurrence_graph.json"))
        print(f"  Saved co-occurrence graph to data/co_occurrence_graph.json")

        print(f"\n  Next steps:")
        print(f"  1. Review matches at /admin/gedcom")
        print(f"  2. Confirm/reject each match")
        print(f"  3. Relationship graph will be built from confirmed matches")
    else:
        print(f"\n  DRY RUN — no files written.")
        print(f"  Use --execute to save match proposals and graphs.")


if __name__ == "__main__":
    main()
