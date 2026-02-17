#!/usr/bin/env python3
"""Auto-confirm high-confidence GEDCOM matches and build relationship graph.

All 14 GEDCOM matches have scores >= 0.87 (Layer 1 — surname variant matches).
This script confirms them all and builds data/relationships.json.

Usage:
    python scripts/confirm_gedcom_matches.py --dry-run    # Preview
    python scripts/confirm_gedcom_matches.py --execute     # Apply
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from rhodesli_ml.importers.gedcom_matches import load_gedcom_matches, update_match_status
from rhodesli_ml.importers.gedcom_parser import parse_gedcom
from rhodesli_ml.importers.identity_matcher import MatchProposal
from rhodesli_ml.graph.relationship_graph import (
    build_relationship_graph,
    save_relationship_graph,
    load_relationship_graph,
)


def main():
    parser = argparse.ArgumentParser(description="Confirm GEDCOM matches and build relationship graph")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Preview only (default)")
    parser.add_argument("--execute", action="store_true", help="Apply changes")
    parser.add_argument("--min-score", type=float, default=0.85, help="Minimum score to auto-confirm")
    args = parser.parse_args()

    if args.execute:
        args.dry_run = False

    matches_path = project_root / "data" / "gedcom_matches.json"
    gedcom_path = project_root / "tests" / "fixtures" / "test_capeluto.ged"
    relationships_path = project_root / "data" / "relationships.json"

    if not matches_path.exists():
        print("ERROR: data/gedcom_matches.json not found")
        return 1

    if not gedcom_path.exists():
        print("ERROR: tests/fixtures/test_capeluto.ged not found")
        return 1

    # Load matches
    raw = load_gedcom_matches(str(matches_path))
    matches_data = raw.get("matches", []) if isinstance(raw, dict) else raw
    pending = [m for m in matches_data if m.get("status") == "pending"]
    high_confidence = [m for m in pending if m.get("match_score", 0) >= args.min_score]

    print(f"Total matches: {len(matches_data)}")
    print(f"Pending: {len(pending)}")
    print(f"High-confidence (>={args.min_score}): {len(high_confidence)}")
    print()

    for m in high_confidence:
        print(f"  {m['gedcom_name']:25s} → {m['identity_name']:30s} (score: {m['match_score']:.2f})")

    if args.dry_run:
        print(f"\nDRY RUN: Would confirm {len(high_confidence)} matches")
        print("Run with --execute to apply")
        return 0

    # Confirm all high-confidence matches
    for m in high_confidence:
        update_match_status(str(matches_path), m["gedcom_xref"], "confirmed")
        print(f"  CONFIRMED: {m['gedcom_name']} → {m['identity_name']}")

    # Reload matches after confirmation
    raw2 = load_gedcom_matches(str(matches_path))
    confirmed_matches_data = raw2.get("matches", []) if isinstance(raw2, dict) else raw2
    confirmed = [m for m in confirmed_matches_data if m.get("status") == "confirmed"]
    print(f"\nConfirmed: {len(confirmed)} matches")

    # Parse GEDCOM to build relationship graph
    parsed = parse_gedcom(str(gedcom_path))
    print(f"GEDCOM: {parsed.individual_count} individuals, {parsed.family_count} families")

    # Create MatchProposal objects for confirmed matches
    # The builder needs MatchProposal objects with gedcom_individual references
    from rhodesli_ml.importers.identity_matcher import MatchProposal as MP

    xref_to_individual = {ind.xref_id: ind for ind in parsed.individuals.values()}
    proposals = []
    for m in confirmed:
        xref = m["gedcom_xref"]
        if xref in xref_to_individual:
            proposal = MP(
                gedcom_individual=xref_to_individual[xref],
                identity_id=m["identity_id"],
                identity_name=m["identity_name"],
                match_score=m["match_score"],
                match_reason=m["match_reason"],
                match_layer=m["match_layer"],
                status="confirmed",
            )
            proposals.append(proposal)

    # Build relationship graph
    existing_graph = load_relationship_graph(str(relationships_path))
    graph = build_relationship_graph(parsed, proposals, existing_graph)

    print(f"\nRelationship graph: {len(graph['relationships'])} relationships")
    for rel in graph["relationships"]:
        # Look up names from matches
        name_a = next((m["identity_name"] for m in confirmed if m["identity_id"] == rel["person_a"]), rel["person_a"][:8])
        name_b = next((m["identity_name"] for m in confirmed if m["identity_id"] == rel["person_b"]), rel["person_b"][:8])
        print(f"  {name_a:30s} --{rel['type']:15s}--> {name_b}")

    save_relationship_graph(graph, str(relationships_path))
    print(f"\nSaved to {relationships_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
