import json
from pathlib import Path
import sys
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from rhodesli_ml.importers.gedcom_parser import parse_gedcom
from rhodesli_ml.graph.relationship_graph import build_relationship_graph, save_relationship_graph
from rhodesli_ml.importers.identity_matcher import MatchProposal

# Load confirmed matches from Supabase via HTTP or directly from json
from dotenv import load_dotenv
load_dotenv()
from app.supabase_data import get_supabase_client
sb = get_supabase_client()

# We need the ACTUAL active links, which are in gedcom_face_links
res = sb.table("gedcom_face_links").select("*").execute()
links = res.data if sb else []

# Parse full GEDCOM
parsed = parse_gedcom("/Users/nolanfox/Downloads/gedcom_20260224/Fox_Capeluto_Fogel_Waldorf Family Tree.ged")

# Convert matches to MatchProposal objects
proposals = []
xref_to_ind = {i.xref_id: i for i in parsed.individuals.values()}
print(f"Loaded {len(links)} face links from supabase")

for m in links:
    xref = m["gedcom_id"]
    if xref in xref_to_ind:
        # We just need to trick build_relationship_graph into mapping the xref to the identity_id
        proposals.append(MatchProposal(
            gedcom_individual=xref_to_ind[xref],
            identity_id=m["identity_id"],
            identity_name="Manually Linked",
            match_score=1.0,
            match_reason="gedcom_face_links",
            match_layer="",
            status="confirmed"
        ))

# Build graph
graph = {"relationships": []}
full_graph = build_relationship_graph(parsed, proposals, graph)

save_relationship_graph(full_graph)

# Also sync to Supabase so it persists on restart
from app.supabase_data import sync_relationships
sync_relationships(full_graph["relationships"])

print(f"Saved {len(full_graph['relationships'])} relationships!")
