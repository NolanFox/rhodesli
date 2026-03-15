#!/usr/bin/env python3
"""Compare two ML clustering runs by proposals file or run_id.

Usage:
    python scripts/compare_ml_runs.py --file-a proposals_baseline.json --file-b proposals_reranker.json
    python scripts/compare_ml_runs.py --run-a <run_id> --run-b <run_id>

Output: Markdown table showing new/removed/changed proposals between runs.
"""

import argparse
import json
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


def load_proposals_from_file(path: Path) -> list[dict]:
    """Load proposals from a proposals.json file."""
    data = json.load(open(path))
    return data.get("proposals", [])


def load_proposals_from_supabase(run_id: str) -> list[dict]:
    """Load proposals from ml_proposals table by run_id."""
    try:
        from app.supabase_data import get_supabase_client

        sb = get_supabase_client()
        if sb is None:
            print(f"WARNING: Supabase not configured, cannot load run {run_id}")
            return []
        result = sb.table("ml_proposals").select("*").eq("run_id", run_id).execute()
        rows = result.data or []
        # Normalize to proposals.json format
        return [
            {
                "source_identity_id": r["source_identity_id"],
                "target_identity_id": r["target_identity_id"],
                "distance": r["score"],
                "reranker_score": r.get("calibrated_score"),
                "tier": r.get("tier"),
                "confidence": _tier_to_confidence(r.get("tier")),
            }
            for r in rows
        ]
    except Exception as e:
        print(f"WARNING: Failed to load run {run_id}: {e}")
        return []


def _tier_to_confidence(tier: str | None) -> str:
    return {"tier1": "VERY HIGH", "tier2": "HIGH", "tier3": "MODERATE"}.get(tier or "", "UNKNOWN")


def compare_proposals(proposals_a: list[dict], proposals_b: list[dict]) -> dict:
    """Compare two sets of proposals and return a structured diff."""

    def proposal_key(p):
        return (p["source_identity_id"], p.get("face_id", ""), p["target_identity_id"])

    def face_key(p):
        return (p["source_identity_id"], p.get("face_id", ""))

    a_by_key = {proposal_key(p): p for p in proposals_a}
    b_by_key = {proposal_key(p): p for p in proposals_b}
    a_by_face = {face_key(p): p for p in proposals_a}
    b_by_face = {face_key(p): p for p in proposals_b}

    a_keys = set(a_by_key)
    b_keys = set(b_by_key)
    a_faces = set(a_by_face)
    b_faces = set(b_by_face)

    # Same face+source, same target — score changes only
    same_match = []
    for k in a_keys & b_keys:
        pa, pb = a_by_key[k], b_by_key[k]
        delta = pb["distance"] - pa["distance"]
        same_match.append(
            {
                "source_identity_id": pa["source_identity_id"],
                "source_name": pa.get("source_identity_name", pa["source_identity_id"][:8]),
                "target_name": pa.get("target_identity_name", pa["target_identity_id"][:8]),
                "distance_a": pa["distance"],
                "distance_b": pb["distance"],
                "delta": round(delta, 6),
                "confidence_a": pa.get("confidence", ""),
                "confidence_b": pb.get("confidence", ""),
                "reranker_score_b": pb.get("reranker_score"),
            }
        )

    # Same face, different target (reranker changed the match)
    target_changes = []
    for fk in a_faces & b_faces:
        pa, pb = a_by_face[fk], b_by_face[fk]
        if pa["target_identity_id"] != pb["target_identity_id"]:
            target_changes.append(
                {
                    "source_name": pa.get("source_identity_name", pa["source_identity_id"][:8]),
                    "face_id": pa.get("face_id", ""),
                    "target_a": pa.get("target_identity_name", pa["target_identity_id"][:8]),
                    "distance_a": pa["distance"],
                    "target_b": pb.get("target_identity_name", pb["target_identity_id"][:8]),
                    "distance_b": pb["distance"],
                    "reranker_score_b": pb.get("reranker_score"),
                }
            )

    # Only in A (removed by B)
    only_a_faces = a_faces - b_faces
    removed = [a_by_face[fk] for fk in only_a_faces]

    # Only in B (new in B)
    only_b_faces = b_faces - a_faces
    added = [b_by_face[fk] for fk in only_b_faces]

    # Tier changes
    tier_changes = []
    for k in a_keys & b_keys:
        pa, pb = a_by_key[k], b_by_key[k]
        ca, cb = pa.get("confidence", ""), pb.get("confidence", "")
        if ca and cb and ca != cb:
            tier_changes.append(
                {
                    "source_name": pa.get("source_identity_name", ""),
                    "target_name": pa.get("target_identity_name", ""),
                    "tier_a": ca,
                    "tier_b": cb,
                    "distance_a": pa["distance"],
                    "distance_b": pb["distance"],
                }
            )

    return {
        "count_a": len(proposals_a),
        "count_b": len(proposals_b),
        "same_match": same_match,
        "target_changes": target_changes,
        "added": added,
        "removed": removed,
        "tier_changes": tier_changes,
    }


def format_markdown(diff: dict, label_a: str = "Run A", label_b: str = "Run B") -> str:
    """Format comparison results as markdown."""
    lines = [
        f"# ML Run Comparison: {label_a} vs {label_b}",
        "",
        "## Summary",
        f"| Metric | {label_a} | {label_b} |",
        "|--------|---------|---------|",
        f"| Total proposals | {diff['count_a']} | {diff['count_b']} |",
        f"| Target changes | — | {len(diff['target_changes'])} |",
        f"| New proposals | — | {len(diff['added'])} |",
        f"| Removed proposals | {len(diff['removed'])} | — |",
        f"| Tier changes | — | {len(diff['tier_changes'])} |",
        "",
    ]

    if diff["target_changes"]:
        lines.extend(
            [
                "## Target Changes (Reranker changed the best match)",
                "| Source | Face | Old Target | Old Dist | New Target | New Dist | Reranker Score |",
                "|--------|------|-----------|----------|-----------|----------|---------------|",
            ]
        )
        for tc in diff["target_changes"]:
            lines.append(
                f"| {tc['source_name'][:25]} | {tc['face_id'][:20]} | {tc['target_a'][:20]} | "
                f"{tc['distance_a']:.4f} | {tc['target_b'][:20]} | {tc['distance_b']:.4f} | "
                f"{tc.get('reranker_score_b', '—')} |"
            )
        lines.append("")

    if diff["added"]:
        lines.extend(
            [
                f"## New Proposals (in {label_b} only)",
                "| Source | Target | Distance | Confidence |",
                "|--------|--------|----------|-----------|",
            ]
        )
        for p in diff["added"][:20]:
            lines.append(
                f"| {p.get('source_identity_name', p['source_identity_id'][:8])[:25]} | "
                f"{p.get('target_identity_name', p['target_identity_id'][:8])[:20]} | "
                f"{p['distance']:.4f} | {p.get('confidence', '')} |"
            )
        if len(diff["added"]) > 20:
            lines.append(f"| ... | ({len(diff['added']) - 20} more) | | |")
        lines.append("")

    if diff["removed"]:
        lines.extend(
            [
                f"## Removed Proposals (in {label_a} only)",
                "| Source | Target | Distance | Confidence |",
                "|--------|--------|----------|-----------|",
            ]
        )
        for p in diff["removed"][:20]:
            lines.append(
                f"| {p.get('source_identity_name', p['source_identity_id'][:8])[:25]} | "
                f"{p.get('target_identity_name', p['target_identity_id'][:8])[:20]} | "
                f"{p['distance']:.4f} | {p.get('confidence', '')} |"
            )
        lines.append("")

    if diff["tier_changes"]:
        lines.extend(
            [
                "## Tier Changes",
                "| Source | Target | Old Tier | New Tier | Old Dist | New Dist |",
                "|--------|--------|----------|----------|----------|----------|",
            ]
        )
        for tc in diff["tier_changes"]:
            lines.append(
                f"| {tc['source_name'][:25]} | {tc['target_name'][:20]} | "
                f"{tc['tier_a']} | {tc['tier_b']} | {tc['distance_a']:.4f} | {tc['distance_b']:.4f} |"
            )
        lines.append("")

    # Score distribution for matched proposals
    if diff["same_match"]:
        deltas = [m["delta"] for m in diff["same_match"]]
        non_zero_deltas = [d for d in deltas if abs(d) > 0.0001]
        lines.extend(
            [
                "## Score Changes (same target)",
                f"- Proposals with identical scores: {len(deltas) - len(non_zero_deltas)}",
                f"- Proposals with score changes: {len(non_zero_deltas)}",
            ]
        )
        if non_zero_deltas:
            lines.extend(
                [
                    f"- Min delta: {min(non_zero_deltas):.6f}",
                    f"- Max delta: {max(non_zero_deltas):.6f}",
                    f"- Mean delta: {sum(non_zero_deltas) / len(non_zero_deltas):.6f}",
                ]
            )
        lines.append("")

    # Net assessment
    lines.extend(["## Assessment"])
    if not diff["target_changes"] and not diff["added"] and not diff["removed"] and not diff["tier_changes"]:
        lines.append("**Neutral** — Runs produce identical proposals. The reranker agrees with the baseline.")
    elif len(diff["target_changes"]) > 0:
        lines.append(
            f"**Active** — Reranker changed {len(diff['target_changes'])} target matches. Manual review needed."
        )
    else:
        net = len(diff["added"]) - len(diff["removed"])
        direction = "positive" if net > 0 else "negative" if net < 0 else "neutral"
        lines.append(f"**Net {direction}** — {len(diff['added'])} added, {len(diff['removed'])} removed.")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Compare two ML clustering runs")
    parser.add_argument("--file-a", type=Path, help="Proposals JSON file for run A")
    parser.add_argument("--file-b", type=Path, help="Proposals JSON file for run B")
    parser.add_argument("--run-a", type=str, help="Supabase run_id for run A")
    parser.add_argument("--run-b", type=str, help="Supabase run_id for run B")
    parser.add_argument("--label-a", type=str, default="Baseline", help="Label for run A")
    parser.add_argument("--label-b", type=str, default="Reranker", help="Label for run B")
    parser.add_argument("--output", type=Path, help="Write markdown to file")
    args = parser.parse_args()

    if args.file_a:
        proposals_a = load_proposals_from_file(args.file_a)
    elif args.run_a:
        proposals_a = load_proposals_from_supabase(args.run_a)
    else:
        print("ERROR: Specify --file-a or --run-a", file=sys.stderr)
        return 1

    if args.file_b:
        proposals_b = load_proposals_from_file(args.file_b)
    elif args.run_b:
        proposals_b = load_proposals_from_supabase(args.run_b)
    else:
        print("ERROR: Specify --file-b or --run-b", file=sys.stderr)
        return 1

    diff = compare_proposals(proposals_a, proposals_b)
    md = format_markdown(diff, args.label_a, args.label_b)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as f:
            f.write(md)
        print(f"Wrote comparison to {args.output}")
    else:
        print(md)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
