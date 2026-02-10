#!/usr/bin/env python3
"""
Golden set diversity analysis (ML-011).

Analyzes the golden set for representation gaps:
- Identity distribution (faces per identity)
- Collection coverage (which photo sources are represented)
- Photo quality indicators (detection confidence, face quality)
- Single-face identities (cannot form same-person pairs)

If no golden set exists, auto-generates one from confirmed identities.

Usage:
    python scripts/analyze_golden_set.py
"""

import json
import sys
from pathlib import Path
from collections import Counter, defaultdict

# Resolve project root
project_root = Path(__file__).resolve().parent.parent


def analyze_golden_set(data_path: Path) -> dict:
    """Analyze golden set diversity and return report dict.

    Args:
        data_path: Directory containing golden_set.json, identities.json,
                   and photo_index.json.

    Returns:
        Dict with keys: total_mappings, unique_identities, single_face_identities,
        multi_face_identities, rich_identities, same_person_pairs,
        different_person_pairs, collections, collection_breakdown, gaps,
        identity_distribution.
    """
    golden_set_path = data_path / "golden_set.json"
    identities_path = data_path / "identities.json"
    photo_index_path = data_path / "photo_index.json"

    # Auto-generate golden set from confirmed identities if missing
    if not golden_set_path.exists():
        mappings = _auto_generate_mappings(identities_path)
    else:
        golden_set = json.load(open(golden_set_path))
        mappings = golden_set.get("mappings", [])

    # Handle empty golden set
    if not mappings:
        return {
            "total_mappings": 0,
            "unique_identities": 0,
            "single_face_identities": 0,
            "multi_face_identities": 0,
            "rich_identities": 0,
            "same_person_pairs": 0,
            "different_person_pairs": 0,
            "collections": 0,
            "collection_breakdown": {},
            "gaps": ["CRITICAL: Golden set is empty — no evaluation possible"],
            "identity_distribution": {},
        }

    # Load identity names for readable output
    identity_names = {}
    if identities_path.exists():
        identities = json.load(open(identities_path))
        for iid, data in identities.get("identities", {}).items():
            identity_names[iid] = data.get("name", "Unknown")

    # Load photo index for collection/source info
    photo_sources = {}
    face_to_photo = {}
    if photo_index_path.exists():
        photo_index = json.load(open(photo_index_path))
        for pid, pdata in photo_index.get("photos", {}).items():
            photo_sources[pid] = pdata.get("source", "Unknown")
        face_to_photo = photo_index.get("face_to_photo", {})

    # 1. Identity distribution
    id_counts = Counter(m["identity_id"] for m in mappings)
    single_face = sum(1 for c in id_counts.values() if c == 1)
    multi_face = sum(1 for c in id_counts.values() if c >= 2)
    rich_face = sum(1 for c in id_counts.values() if c >= 5)

    # 2. Pairwise analysis
    total_same_pairs = sum(c * (c - 1) // 2 for c in id_counts.values())
    total_diff_pairs = sum(
        id_counts[a] * id_counts[b]
        for i, a in enumerate(id_counts)
        for b in list(id_counts)[i + 1:]
    )

    # 3. Collection coverage
    face_collections = defaultdict(int)
    for m in mappings:
        face_id = m["face_id"]
        photo_id = face_to_photo.get(face_id, "")
        source = photo_sources.get(photo_id, "Unknown")
        if not source:
            if face_id.startswith("inbox_"):
                source = "Inbox Upload"
            else:
                source = "Unknown"
        face_collections[source] += 1

    # 4. Gaps and recommendations
    gaps = []
    if single_face > len(id_counts) * 0.3:
        gaps.append(
            f"HIGH: {single_face}/{len(id_counts)} identities have only 1 face "
            f"— these cannot contribute same-person pairs for evaluation"
        )
    if len(face_collections) < 3:
        gaps.append(
            f"MEDIUM: Only {len(face_collections)} collection(s) represented "
            f"— add faces from underrepresented collections"
        )
    if rich_face < 5:
        gaps.append(
            f"MEDIUM: Only {rich_face} identities have 5+ faces "
            f"— rich identities strengthen evaluation"
        )
    if total_same_pairs < 50:
        gaps.append(
            f"LOW: Only {total_same_pairs} same-person pairs "
            f"— aim for 100+ for robust threshold calibration"
        )

    # Build identity distribution for report
    identity_distribution = {}
    for iid, count in id_counts.most_common():
        name = identity_names.get(iid, iid[:16])
        identity_distribution[name] = count

    return {
        "total_mappings": len(mappings),
        "unique_identities": len(set(m["identity_id"] for m in mappings)),
        "single_face_identities": single_face,
        "multi_face_identities": multi_face,
        "rich_identities": rich_face,
        "same_person_pairs": total_same_pairs,
        "different_person_pairs": total_diff_pairs,
        "collections": len(face_collections),
        "collection_breakdown": dict(face_collections),
        "gaps": gaps,
        "identity_distribution": identity_distribution,
    }


def _auto_generate_mappings(identities_path: Path) -> list[dict]:
    """Generate golden set mappings from confirmed identities.

    Extracts face IDs from CONFIRMED, non-merged identities.
    """
    if not identities_path.exists():
        return []

    identities = json.load(open(identities_path))
    mappings = []
    for iid, data in identities.get("identities", {}).items():
        if data.get("state") != "CONFIRMED":
            continue
        if data.get("merged_into"):
            continue
        name = data.get("name", "Unknown")

        for face_id in data.get("anchor_ids", []):
            if isinstance(face_id, dict):
                face_id = face_id.get("face_id", "")
            if face_id:
                mappings.append({
                    "face_id": face_id,
                    "identity_id": iid,
                    "identity_name": name,
                    "source": "confirmed_anchor",
                })
        for face_id in data.get("candidate_ids", []):
            if isinstance(face_id, dict):
                face_id = face_id.get("face_id", "")
            if face_id:
                mappings.append({
                    "face_id": face_id,
                    "identity_id": iid,
                    "identity_name": name,
                    "source": "confirmed_candidate",
                })
    return mappings


def print_report(report: dict, identity_names: dict | None = None) -> None:
    """Print a human-readable report from analyze_golden_set output."""
    print("=" * 70)
    print("GOLDEN SET DIVERSITY ANALYSIS (ML-011)")
    print("=" * 70)
    print(f"\nTotal mappings: {report['total_mappings']}")
    print(f"Unique identities: {report['unique_identities']}")

    print("\n--- IDENTITY DISTRIBUTION ---")
    print(f"Single-face identities: {report['single_face_identities']} "
          f"(cannot form same-person pairs)")
    print(f"Multi-face identities: {report['multi_face_identities']} "
          f"(can form same-person pairs)")
    print(f"Rich identities (5+ faces): {report['rich_identities']}")
    print(f"\nFaces per identity:")
    for name, count in report.get("identity_distribution", {}).items():
        print(f"  {name:40s} {count:3d} faces")

    print("\n--- PAIRWISE POTENTIAL ---")
    print(f"Same-person pairs: {report['same_person_pairs']}")
    print(f"Different-person pairs: {report['different_person_pairs']}")
    total = report['same_person_pairs'] + report['different_person_pairs']
    print(f"Total pairs: {total}")
    if report['same_person_pairs'] > 0:
        ratio = report['different_person_pairs'] / report['same_person_pairs']
        print(f"Imbalance ratio: {ratio:.1f}x (different:same)")

    print("\n--- COLLECTION COVERAGE ---")
    breakdown = report.get("collection_breakdown", {})
    total_faces = report["total_mappings"]
    for source, count in sorted(breakdown.items(), key=lambda x: -x[1]):
        pct = count / total_faces * 100 if total_faces else 0
        print(f"  {source:40s} {count:3d} faces ({pct:.0f}%)")

    print("\n--- GAPS & RECOMMENDATIONS ---")
    gaps = report.get("gaps", [])
    if gaps:
        for g in gaps:
            print(f"  * {g}")
    else:
        print("  No critical gaps detected.")

    print("\n--- SUMMARY FOR DASHBOARD ---")
    # Exclude non-serializable items for dashboard JSON
    dashboard = {k: v for k, v in report.items()
                 if k not in ("identity_distribution",)}
    print(json.dumps(dashboard, indent=2))


def main():
    data_path = project_root / "data"
    report = analyze_golden_set(data_path)
    print_report(report)

    # Save analysis
    output_path = data_path / "golden_set_diversity.json"
    saveable = {k: v for k, v in report.items()
                if k not in ("identity_distribution",)}
    with open(output_path, "w") as f:
        json.dump(saveable, f, indent=2)
    print(f"\nAnalysis saved to {output_path}")


if __name__ == "__main__":
    main()
