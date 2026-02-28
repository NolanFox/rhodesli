"""Rebuild the full relationship graph from GEDCOM + Supabase links.

Loads EXISTING relationships first, then adds new ones on top.
Never starts from empty — that would wipe admin-confirmed UUID relationships.
"""
import json
import os
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

if not os.environ.get("RAILWAY_ENVIRONMENT") and "pytest" not in sys.modules:
    from dotenv import load_dotenv
    load_dotenv()

from rhodesli_ml.importers.gedcom_parser import parse_gedcom
from rhodesli_ml.graph.relationship_graph import (
    build_relationship_graph,
    load_relationship_graph,
    save_relationship_graph,
)
from rhodesli_ml.importers.identity_matcher import MatchProposal
from app.supabase_data import get_supabase_client


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/rebuild_full_graph.py <path-to-gedcom-file>")
        print("Example: python scripts/rebuild_full_graph.py data/gedcom/family_tree.ged")
        sys.exit(1)

    gedcom_path = sys.argv[1]
    if not Path(gedcom_path).exists():
        print(f"Error: GEDCOM file not found: {gedcom_path}")
        sys.exit(1)

    # Load confirmed links from Supabase
    sb = get_supabase_client()
    res = sb.table("gedcom_face_links").select("*").execute()
    links = res.data if res else []
    print(f"Loaded {len(links)} face links from Supabase")

    # Parse GEDCOM
    parsed = parse_gedcom(gedcom_path)

    # Convert links to MatchProposal objects
    xref_to_ind = {i.xref_id: i for i in parsed.individuals.values()}
    proposals = []
    for m in links:
        xref = m["gedcom_id"]
        if xref in xref_to_ind:
            proposals.append(MatchProposal(
                gedcom_individual=xref_to_ind[xref],
                identity_id=m["identity_id"],
                identity_name="Manually Linked",
                match_score=1.0,
                match_reason="gedcom_face_links",
                match_layer="",
                status="confirmed"
            ))

    # Load EXISTING graph — never start from empty
    existing_graph = load_relationship_graph()
    existing_count = len(existing_graph.get("relationships", []))
    print(f"Existing graph: {existing_count} relationships")

    # Build new relationships ON TOP of existing
    full_graph = build_relationship_graph(parsed, proposals, existing_graph)
    new_count = len(full_graph.get("relationships", []))
    print(f"After rebuild: {new_count} relationships (+{new_count - existing_count} new)")

    save_relationship_graph(full_graph)

    # Sync to Supabase
    from app.supabase_data import sync_relationships
    sync_relationships(full_graph["relationships"])

    print(f"Saved {new_count} relationships!")


if __name__ == "__main__":
    main()
