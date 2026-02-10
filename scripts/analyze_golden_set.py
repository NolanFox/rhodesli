#!/usr/bin/env python3
"""
Golden set diversity analysis (ML-011).

Analyzes the golden set for representation gaps:
- Identity distribution (faces per identity)
- Collection coverage (which photo sources are represented)
- Photo quality indicators (detection confidence, face quality)
- Single-face identities (cannot form same-person pairs)

Usage:
    python scripts/analyze_golden_set.py
"""

import json
import sys
from pathlib import Path
from collections import Counter, defaultdict

# Resolve project root
project_root = Path(__file__).resolve().parent.parent


def main():
    golden_set_path = project_root / "data" / "golden_set.json"
    identities_path = project_root / "data" / "identities.json"
    photo_index_path = project_root / "data" / "photo_index.json"

    if not golden_set_path.exists():
        print("ERROR: data/golden_set.json not found")
        sys.exit(1)

    golden_set = json.load(open(golden_set_path))
    mappings = golden_set["mappings"]

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

    print("=" * 70)
    print("GOLDEN SET DIVERSITY ANALYSIS (ML-011)")
    print("=" * 70)
    print(f"\nTotal mappings: {len(mappings)}")
    print(f"Unique identities: {len(set(m['identity_id'] for m in mappings))}")

    # 1. Identity distribution
    print("\n--- IDENTITY DISTRIBUTION ---")
    id_counts = Counter(m["identity_id"] for m in mappings)
    single_face = sum(1 for c in id_counts.values() if c == 1)
    multi_face = sum(1 for c in id_counts.values() if c >= 2)
    rich_face = sum(1 for c in id_counts.values() if c >= 5)

    print(f"Single-face identities: {single_face} (cannot form same-person pairs)")
    print(f"Multi-face identities: {multi_face} (can form same-person pairs)")
    print(f"Rich identities (5+ faces): {rich_face}")
    print(f"\nFaces per identity:")
    for iid, count in id_counts.most_common():
        name = identity_names.get(iid, iid[:16])
        print(f"  {name:40s} {count:3d} faces")

    # 2. Pairwise analysis
    print("\n--- PAIRWISE POTENTIAL ---")
    total_same_pairs = sum(c * (c - 1) // 2 for c in id_counts.values())
    total_diff_pairs = sum(
        id_counts[a] * id_counts[b]
        for i, a in enumerate(id_counts)
        for b in list(id_counts)[i + 1:]
    )
    print(f"Same-person pairs: {total_same_pairs}")
    print(f"Different-person pairs: {total_diff_pairs}")
    print(f"Total pairs: {total_same_pairs + total_diff_pairs}")
    if total_same_pairs > 0:
        ratio = total_diff_pairs / total_same_pairs
        print(f"Imbalance ratio: {ratio:.1f}x (different:same)")

    # 3. Collection coverage
    print("\n--- COLLECTION COVERAGE ---")
    face_collections = defaultdict(int)
    for m in mappings:
        face_id = m["face_id"]
        photo_id = face_to_photo.get(face_id, "")
        source = photo_sources.get(photo_id, "Unknown")
        if not source:
            # Try to infer from face_id format
            if face_id.startswith("inbox_"):
                source = "Inbox Upload"
            else:
                source = "Unknown"
        face_collections[source] += 1

    for source, count in sorted(face_collections.items(), key=lambda x: -x[1]):
        pct = count / len(mappings) * 100
        print(f"  {source:40s} {count:3d} faces ({pct:.0f}%)")

    # 4. Gaps and recommendations
    print("\n--- GAPS & RECOMMENDATIONS ---")
    gaps = []
    if single_face > len(id_counts) * 0.3:
        gaps.append(f"HIGH: {single_face}/{len(id_counts)} identities have only 1 face "
                    f"— these cannot contribute same-person pairs for evaluation")
    if len(face_collections) < 3:
        gaps.append(f"MEDIUM: Only {len(face_collections)} collection(s) represented "
                    f"— add faces from underrepresented collections")
    if rich_face < 5:
        gaps.append(f"MEDIUM: Only {rich_face} identities have 5+ faces "
                    f"— rich identities strengthen evaluation")
    if total_same_pairs < 50:
        gaps.append(f"LOW: Only {total_same_pairs} same-person pairs "
                    f"— aim for 100+ for robust threshold calibration")

    if gaps:
        for g in gaps:
            print(f"  * {g}")
    else:
        print("  No critical gaps detected.")

    # 5. Summary stats for dashboard
    print("\n--- SUMMARY FOR DASHBOARD ---")
    summary = {
        "total_mappings": len(mappings),
        "unique_identities": len(set(m["identity_id"] for m in mappings)),
        "single_face_identities": single_face,
        "multi_face_identities": multi_face,
        "rich_identities": rich_face,
        "same_person_pairs": total_same_pairs,
        "different_person_pairs": total_diff_pairs,
        "collections": len(face_collections),
        "collection_breakdown": dict(face_collections),
    }
    print(json.dumps(summary, indent=2))

    # Save analysis
    output_path = project_root / "data" / "golden_set_diversity.json"
    with open(output_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nAnalysis saved to {output_path}")


if __name__ == "__main__":
    main()
