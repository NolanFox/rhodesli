#!/usr/bin/env python3
"""
Session 63 Phase 4: Link Rhodesli identified faces to GEDCOM individuals.

Fuzzy name matching handles:
- Surname variants: Capeluto/Capelluto/Capouano/Capelouto/Capuano
- Nicknames: "Big Leon" → "Leon", "Betty" → "Betty Susan"
- Given names: exact → prefix → edit distance
- Compound names: "Betty Capeluto Fox" → try all surname combinations

Usage:
    python scripts/link_faces_to_gedcom.py --dry-run
    python scripts/link_faces_to_gedcom.py --execute
"""

import argparse
import json
import logging
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger(__name__)


# Sephardic surname variant clusters
SURNAME_CLUSTERS = {
    "capeluto": {"capeluto", "capelluto", "capelouto", "capouano", "capuano"},
    "moussafer": {"moussafer", "mousafir", "mosafir"},
    "pizanti": {"pizanti", "pizante"},
    "franco": {"franco"},
    "hazan": {"hazan", "hasson"},
    "sedikaro": {"sedikaro", "sedikaru"},
    "capouya": {"capouya", "capuya"},
    "cukran": {"cukran"},
    "taranto": {"taranto"},
    "surmani": {"surmani"},
    "louza": {"louza"},
}

# Build reverse lookup: variant → cluster key
SURNAME_TO_CLUSTER = {}
for cluster_key, variants in SURNAME_CLUSTERS.items():
    for v in variants:
        SURNAME_TO_CLUSTER[v] = cluster_key

# Nickname expansions
NICKNAME_MAP = {
    "big leon": "leon",
    "betty": "betty",  # could match "betty susan"
    "ray": "ray",
    "molly": "molly",
    "belle": "belle",
}

# Prefixes to strip
TITLE_PREFIXES = {"big", "little", "old", "young"}


def normalize_name(name: str) -> tuple[str, str]:
    """Normalize a name into (given, surname) parts.

    Handles compound names by returning the last word as surname.
    """
    parts = name.strip().lower().split()
    # Strip titles/qualifiers
    parts = [p for p in parts if p not in TITLE_PREFIXES]
    if not parts:
        return ("", "")
    if len(parts) == 1:
        return (parts[0], "")
    return (" ".join(parts[:-1]), parts[-1])


def surname_matches(s1: str, s2: str) -> bool:
    """Check if two surnames match, accounting for Sephardic variants."""
    s1 = s1.lower().strip()
    s2 = s2.lower().strip()
    if s1 == s2:
        return True
    c1 = SURNAME_TO_CLUSTER.get(s1, s1)
    c2 = SURNAME_TO_CLUSTER.get(s2, s2)
    return c1 == c2


def given_name_score(g1: str, g2: str) -> float:
    """Score given name match: 1.0 exact, 0.8 prefix, 0.5 partial, 0 none."""
    g1 = g1.lower().strip()
    g2 = g2.lower().strip()
    if not g1 or not g2:
        return 0.0
    if g1 == g2:
        return 1.0
    # Prefix match: "betty" matches "betty susan"
    if g1.startswith(g2) or g2.startswith(g1):
        return 0.8
    # First given name match
    g1_first = g1.split()[0]
    g2_first = g2.split()[0]
    if g1_first == g2_first:
        return 0.9
    # Edit distance (simple)
    if len(g1_first) > 2 and len(g2_first) > 2:
        if g1_first[:3] == g2_first[:3]:
            return 0.5
    return 0.0


def match_identity_to_gedcom(identity_name: str, gedcom_individuals: list) -> list:
    """
    Match one Rhodesli identity name against GEDCOM individuals.

    Returns list of (gedcom_row, confidence) sorted by confidence desc.
    """
    # Parse identity name
    id_given, id_surname = normalize_name(identity_name)

    # Handle nicknames
    clean_name = identity_name.lower().strip()
    for nickname, expansion in NICKNAME_MAP.items():
        if clean_name.startswith(nickname):
            id_given = expansion
            break

    # Try multiple surname extraction strategies for compound names
    # e.g., "Betty Capeluto Fox" → try Capeluto AND Fox
    parts = identity_name.strip().lower().split()
    parts = [p for p in parts if p not in TITLE_PREFIXES]
    candidate_surnames = set()
    if len(parts) >= 2:
        candidate_surnames.add(parts[-1])  # Last word
        if len(parts) >= 3:
            candidate_surnames.add(parts[-2])  # Second to last (maiden name)
            candidate_surnames.add(parts[1])   # Common pattern: "First Maiden Married"

    if id_surname:
        candidate_surnames.add(id_surname)

    matches = []
    for row in gedcom_individuals:
        gedcom_name = row.get("name", "")
        gedcom_given = (row.get("given_name") or "").lower().strip()
        gedcom_surname = (row.get("surname") or "").lower().strip()

        # Check surname match (any of our candidate surnames)
        surname_match = False
        for cs in candidate_surnames:
            if surname_matches(cs, gedcom_surname):
                surname_match = True
                break

        if not surname_match:
            continue

        # Score given name
        g_score = given_name_score(id_given, gedcom_given)
        if g_score < 0.5:
            continue

        # Overall confidence
        confidence = g_score * 0.7 + 0.3  # Surname match is worth 0.3
        if g_score >= 1.0:
            confidence = min(confidence + 0.05, 1.0)

        matches.append((row, confidence))

    matches.sort(key=lambda x: x[1], reverse=True)
    return matches


def run_linking(dry_run=True):
    """Run the full face-to-GEDCOM linking pipeline."""
    # Load identities
    with open(PROJECT_ROOT / "data" / "identities.json") as f:
        idents = json.load(f)

    confirmed = {}
    for iid, identity in idents.get("identities", {}).items():
        if identity.get("state") == "CONFIRMED":
            confirmed[iid] = identity.get("name", "Unknown")

    logger.info(f"Confirmed identities: {len(confirmed)}")

    # Load GEDCOM individuals from Supabase
    import httpx
    url = os.environ['SUPABASE_URL']
    key = os.environ['SUPABASE_SERVICE_ROLE_KEY']
    headers = {'apikey': key, 'Authorization': f'Bearer {key}'}

    # Fetch all GEDCOM individuals (paginate if needed)
    all_individuals = []
    offset = 0
    while True:
        resp = httpx.get(
            f"{url}/rest/v1/gedcom_individuals?select=*&order=name&offset={offset}&limit=1000",
            headers=headers, timeout=30,
        )
        batch = resp.json()
        all_individuals.extend(batch)
        if len(batch) < 1000:
            break
        offset += 1000

    logger.info(f"GEDCOM individuals loaded: {len(all_individuals)}")

    # Match each confirmed identity
    auto_links = []  # confidence >= 0.8
    review_links = []  # 0.5 <= confidence < 0.8
    no_match = []

    for iid, name in sorted(confirmed.items(), key=lambda x: x[1]):
        matches = match_identity_to_gedcom(name, all_individuals)
        if not matches:
            no_match.append((iid, name))
            continue

        best_row, best_conf = matches[0]
        if best_conf >= 0.8:
            auto_links.append({
                "identity_id": iid,
                "identity_name": name,
                "gedcom_id": best_row["gedcom_id"],
                "gedcom_name": best_row["name"],
                "confidence": round(best_conf, 3),
                "birth_date": best_row.get("birth_date"),
                "birth_place": best_row.get("birth_place"),
                "alternatives": len(matches) - 1,
            })
        else:
            review_links.append({
                "identity_id": iid,
                "identity_name": name,
                "gedcom_id": best_row["gedcom_id"],
                "gedcom_name": best_row["name"],
                "confidence": round(best_conf, 3),
            })

    # Report
    logger.info(f"\n=== MATCHING RESULTS ===")
    logger.info(f"Auto-linked (>=0.8): {len(auto_links)}")
    for link in auto_links:
        logger.info(f"  ✓ {link['identity_name']} → {link['gedcom_name']} "
                     f"(conf={link['confidence']}, born {link.get('birth_date', '?')})")

    logger.info(f"\nFor review (0.5-0.8): {len(review_links)}")
    for link in review_links:
        logger.info(f"  ? {link['identity_name']} → {link['gedcom_name']} "
                     f"(conf={link['confidence']})")

    logger.info(f"\nNo match: {len(no_match)}")
    for iid, name in no_match:
        logger.info(f"  ✗ {name}")

    if dry_run:
        logger.info(f"\nDRY RUN — no data written. Use --execute to insert links.")
        return auto_links, review_links, no_match

    # Insert auto-links into Supabase
    rows_to_insert = []
    for link in auto_links:
        rows_to_insert.append({
            "identity_id": link["identity_id"],
            "gedcom_id": link["gedcom_id"],
            "confidence": link["confidence"],
            "linked_by": "auto-match-session63",
        })
    # Also insert review candidates with lower confidence
    for link in review_links:
        rows_to_insert.append({
            "identity_id": link["identity_id"],
            "gedcom_id": link["gedcom_id"],
            "confidence": link["confidence"],
            "linked_by": "review-needed",
        })

    if rows_to_insert:
        # Use upsert to handle existing links
        from supabase import create_client
        sb = create_client(url, key)
        sb.table('gedcom_face_links').upsert(
            rows_to_insert, on_conflict='identity_id,gedcom_id'
        ).execute()
        logger.info(f"Upserted {len(rows_to_insert)} face links into Supabase")

    # Save results file
    results = {
        "auto_linked": auto_links,
        "review_needed": review_links,
        "no_match": [{"identity_id": iid, "name": name} for iid, name in no_match],
        "stats": {
            "total_confirmed": len(confirmed),
            "auto_linked": len(auto_links),
            "review_needed": len(review_links),
            "no_match": len(no_match),
        }
    }
    output_path = PROJECT_ROOT / "results" / "gedcom_face_links_session63.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    logger.info(f"Results saved to {output_path}")

    return auto_links, review_links, no_match


def main():
    parser = argparse.ArgumentParser(description="Link faces to GEDCOM individuals")
    parser.add_argument('--execute', action='store_true', help='Actually insert (default: dry-run)')
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(levelname)s: %(message)s'
    )

    run_linking(dry_run=not args.execute)


if __name__ == '__main__':
    main()
