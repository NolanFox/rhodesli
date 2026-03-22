#!/usr/bin/env python3
"""Audit merge chains in Supabase identities table.

READ-ONLY audit — no data modifications.

Finds:
- All identities with merged_into set
- Chains > 1 hop (A->B->C)
- Circular references
- Targets that are themselves merged
"""

import sys
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

from app.supabase_data import get_supabase_client


def fetch_all_identities(client):
    """Fetch all identities with their merged_into status."""
    # Fetch in pages of 1000
    all_rows = []
    offset = 0
    page_size = 1000
    while True:
        resp = (
            client.table("identities")
            .select("identity_id, name, state, merged_into, anchor_ids, candidate_ids")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        rows = resp.data
        all_rows.extend(rows)
        if len(rows) < page_size:
            break
        offset += page_size
    return all_rows


def build_merge_graph(identities):
    """Build a dict of identity_id -> merged_into for all merged identities."""
    merged = {}
    all_ids = set()
    id_to_name = {}
    id_to_state = {}
    id_to_anchors = {}
    id_to_candidates = {}

    for ident in identities:
        iid = ident["identity_id"]
        all_ids.add(iid)
        id_to_name[iid] = ident.get("name", "?")
        id_to_state[iid] = ident.get("state", "?")
        id_to_anchors[iid] = ident.get("anchor_ids") or []
        id_to_candidates[iid] = ident.get("candidate_ids") or []
        if ident.get("merged_into"):
            merged[iid] = ident["merged_into"]

    return merged, all_ids, id_to_name, id_to_state, id_to_anchors, id_to_candidates


def follow_chain(start, merged):
    """Follow a merge chain from start, detecting cycles."""
    chain = [start]
    visited = {start}
    current = start
    while current in merged:
        nxt = merged[current]
        if nxt in visited:
            # Circular!
            chain.append(nxt)
            return chain, True
        visited.add(nxt)
        chain.append(nxt)
        current = nxt
    return chain, False


def audit(identities):
    merged, all_ids, names, states, anchors, candidates = build_merge_graph(identities)

    print(f"\nTotal identities: {len(all_ids)}")
    print(f"Merged identities (merged_into != null): {len(merged)}")
    print(f"Active identities: {len(all_ids) - len(merged)}")

    # Build all chains
    chains = {}  # source -> (chain, is_circular)
    for source in merged:
        chain, circular = follow_chain(source, merged)
        chains[source] = (chain, circular)

    # Find multi-hop chains
    multi_hop = {s: (c, circ) for s, (c, circ) in chains.items() if len(c) > 2}
    circular = {s: (c, circ) for s, (c, circ) in chains.items() if circ}

    # Find merged targets that are themselves merged (the root cause of multi-hop)
    intermediate_merges = set()
    for source, target in merged.items():
        if target in merged:
            intermediate_merges.add(target)

    # Find dangling references (merged_into points to non-existent identity)
    dangling = {}
    for source, target in merged.items():
        if target not in all_ids:
            dangling[source] = target

    # Find merged identities that still have faces (orphan risk)
    merged_with_faces = {}
    for source in merged:
        anc = anchors.get(source, [])
        cand = candidates.get(source, [])
        if anc or cand:
            merged_with_faces[source] = {
                "anchor_ids": anc,
                "candidate_ids": cand,
                "merged_into": merged[source],
            }

    # Build reverse graph: who merged into each target
    reverse = defaultdict(list)
    for source, target in merged.items():
        final = follow_chain(source, merged)[0][-1]
        reverse[final].append(source)

    # Report
    report_lines = []
    report_lines.append("# Session 132 — Merge Chain Audit")
    report_lines.append("")
    report_lines.append("## Summary")
    report_lines.append(f"- Total identities: {len(all_ids)}")
    report_lines.append(f"- Merged identities: {len(merged)}")
    report_lines.append(f"- Active identities: {len(all_ids) - len(merged)}")
    report_lines.append(f"- Multi-hop chains (>1 hop): {len(multi_hop)}")
    report_lines.append(f"- Circular chains: {len(circular)}")
    report_lines.append(f"- Intermediate merge targets (themselves merged): {len(intermediate_merges)}")
    report_lines.append(f"- Dangling references (target doesn't exist): {len(dangling)}")
    report_lines.append(f"- Merged identities still holding faces: {len(merged_with_faces)}")
    report_lines.append("")

    if circular:
        report_lines.append("## CRITICAL: Circular Merge Chains")
        for source, (chain, _) in sorted(circular.items()):
            chain_str = " -> ".join(f"{cid} ({names.get(cid, '?')})" for cid in chain)
            report_lines.append(f"- {chain_str}")
        report_lines.append("")

    if multi_hop:
        report_lines.append("## Multi-Hop Chains (>1 hop)")
        # Deduplicate: only show unique chains by their final target
        seen_chains = set()
        for source, (chain, circ) in sorted(multi_hop.items()):
            chain_tuple = tuple(chain)
            if chain_tuple in seen_chains:
                continue
            seen_chains.add(chain_tuple)
            chain_str = " -> ".join(f"{cid} ({names.get(cid, '?')}, {states.get(cid, '?')})" for cid in chain)
            hops = len(chain) - 1
            report_lines.append(f"- **{hops} hops**: {chain_str}")
        report_lines.append("")

    if intermediate_merges:
        report_lines.append("## Intermediate Merge Targets (need flattening)")
        report_lines.append("These identities are merged_into targets but are themselves merged.")
        for iid in sorted(intermediate_merges):
            final_chain, _ = follow_chain(iid, merged)
            final_target = final_chain[-1]
            report_lines.append(
                f"- {iid} ({names.get(iid, '?')}) -> "
                f"merged_into={merged[iid]} -> final={final_target} ({names.get(final_target, '?')})"
            )
        report_lines.append("")

    if dangling:
        report_lines.append("## Dangling References (target doesn't exist)")
        for source, target in sorted(dangling.items()):
            report_lines.append(f"- {source} ({names.get(source, '?')}) -> {target} (NOT FOUND)")
        report_lines.append("")

    if merged_with_faces:
        report_lines.append("## Merged Identities Still Holding Faces")
        report_lines.append("These merged identities still have anchor_ids or candidate_ids.")
        report_lines.append("Faces should have been transferred to the merge target.")
        for source, info in sorted(merged_with_faces.items()):
            n_anchors = len(info["anchor_ids"]) if isinstance(info["anchor_ids"], list) else 0
            n_candidates = len(info["candidate_ids"]) if isinstance(info["candidate_ids"], list) else 0
            target = info["merged_into"]
            report_lines.append(
                f"- {source} ({names.get(source, '?')}) -> {target} ({names.get(target, '?')}): "
                f"{n_anchors} anchors, {n_candidates} candidates still held"
            )
        report_lines.append("")

    # Top merge targets (identities that absorbed the most others)
    top_targets = sorted(reverse.items(), key=lambda x: len(x[1]), reverse=True)[:10]
    if top_targets:
        report_lines.append("## Top Merge Targets (most merges absorbed)")
        for target, sources in top_targets:
            report_lines.append(
                f"- {target} ({names.get(target, '?')}, {states.get(target, '?')}): {len(sources)} identities merged in"
            )
        report_lines.append("")

    # Flatten recommendations
    if multi_hop or circular or dangling or merged_with_faces:
        report_lines.append("## Recommended Fixes")
        if circular:
            report_lines.append("- **P0**: Break circular merge chains — pick canonical target, update others")
        if multi_hop:
            report_lines.append(
                f"- **P1**: Flatten {len(multi_hop)} multi-hop chains — "
                "update merged_into to point directly to final target"
            )
        if dangling:
            report_lines.append(
                f"- **P1**: Fix {len(dangling)} dangling references — target identities may have been deleted"
            )
        if merged_with_faces:
            report_lines.append(
                f"- **P1**: Transfer faces from {len(merged_with_faces)} merged identities — "
                "these faces are orphaned (not visible in any active identity)"
            )
        report_lines.append("")
    else:
        report_lines.append("## Status: CLEAN")
        report_lines.append("No merge chain issues found.")
        report_lines.append("")

    report = "\n".join(report_lines)
    print(report)
    return report


def main():
    client = get_supabase_client()
    if not client:
        print("ERROR: Could not connect to Supabase. Check .env for SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")
        sys.exit(1)

    print("Fetching all identities from Supabase...")
    identities = fetch_all_identities(client)
    print(f"Fetched {len(identities)} identities.")

    report = audit(identities)

    # Write report
    output_path = "docs/session_context/session-132-merge-chain-audit.md"
    with open(output_path, "w") as f:
        f.write(report)
    print(f"\nReport written to {output_path}")


if __name__ == "__main__":
    main()
