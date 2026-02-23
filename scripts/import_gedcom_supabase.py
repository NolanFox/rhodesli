#!/usr/bin/env python3
"""Import GEDCOM data into Supabase for persistent storage and web queries.

Parse once, store in Supabase, query fast. Populates:
- gedcom_individuals: all people
- gedcom_events: life events (birth, death, residence, etc.)
- gedcom_relationships: family relationships
- gedcom_face_links: identity-to-GEDCOM links (from existing matches)

Idempotent: re-running upserts on gedcom_id.

Usage:
    python scripts/import_gedcom_supabase.py --file ~/Downloads/Family.ged --dry-run
    python scripts/import_gedcom_supabase.py --file ~/Downloads/Family.ged --execute
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger(__name__)


def get_supabase_client():
    """Get Supabase client with service role key."""
    url = os.environ.get('SUPABASE_URL')
    key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    from supabase import create_client
    return create_client(url, key)


def import_individuals(sb, parsed, source_file, dry_run=False):
    """Import individuals into gedcom_individuals table."""
    rows = []
    for xref_id, indi in parsed.individuals.items():
        rows.append({
            'gedcom_id': xref_id,
            'name': indi.full_name or 'Unknown',
            'given_name': indi.given_name or None,
            'surname': indi.surname or None,
            'gender': indi.gender or 'U',
            'birth_date': indi.birth.raw_date if indi.birth else None,
            'birth_place': indi.birth_place,
            'death_date': indi.death.raw_date if indi.death else None,
            'death_place': indi.death_place,
            'source_file': source_file,
        })

    if dry_run:
        logger.info(f"DRY RUN: Would import {len(rows)} individuals")
        return len(rows)

    imported = 0
    for i in range(0, len(rows), 500):
        chunk = rows[i:i + 500]
        sb.table('gedcom_individuals').upsert(chunk, on_conflict='gedcom_id').execute()
        imported += len(chunk)
        if imported % 2000 == 0:
            logger.info(f"  Imported {imported}/{len(rows)} individuals...")

    logger.info(f"Imported {imported} individuals")
    return imported


def import_events(sb, parsed, dry_run=False):
    """Import all events into gedcom_events table."""
    rows = []
    for xref_id, indi in parsed.individuals.items():
        if indi.birth:
            rows.append({
                'gedcom_individual_id': xref_id,
                'event_type': 'birth',
                'date': str(indi.birth.date.year) if indi.birth.date and indi.birth.date.year else None,
                'place': indi.birth.place,
                'raw_date': indi.birth.raw_date,
            })
        if indi.death:
            rows.append({
                'gedcom_individual_id': xref_id,
                'event_type': 'death',
                'date': str(indi.death.date.year) if indi.death.date and indi.death.date.year else None,
                'place': indi.death.place,
                'raw_date': indi.death.raw_date,
            })
        for event in indi.events:
            rows.append({
                'gedcom_individual_id': xref_id,
                'event_type': event.event_type,
                'date': str(event.date.year) if event.date and event.date.year else None,
                'place': event.place,
                'raw_date': event.raw_date,
            })

    if dry_run:
        logger.info(f"DRY RUN: Would import {len(rows)} events")
        return len(rows)

    # Clear and re-insert (idempotent)
    sb.table('gedcom_events').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()

    imported = 0
    for i in range(0, len(rows), 500):
        chunk = rows[i:i + 500]
        sb.table('gedcom_events').insert(chunk).execute()
        imported += len(chunk)
        if imported % 5000 == 0:
            logger.info(f"  Imported {imported}/{len(rows)} events...")

    logger.info(f"Imported {imported} events")
    return imported


def import_relationships(sb, parsed, dry_run=False):
    """Import family relationships into gedcom_relationships table."""
    rows = []
    for fam_xref, fam in parsed.families.items():
        parents = [x for x in [fam.husband_xref, fam.wife_xref] if x]

        for parent_xref in parents:
            for child_xref in fam.children_xrefs:
                rows.append({
                    'individual_gedcom_id': parent_xref,
                    'related_gedcom_id': child_xref,
                    'relationship_type': 'parent',
                    'family_gedcom_id': fam_xref,
                })
                rows.append({
                    'individual_gedcom_id': child_xref,
                    'related_gedcom_id': parent_xref,
                    'relationship_type': 'child',
                    'family_gedcom_id': fam_xref,
                })

        if fam.husband_xref and fam.wife_xref:
            rows.append({
                'individual_gedcom_id': fam.husband_xref,
                'related_gedcom_id': fam.wife_xref,
                'relationship_type': 'spouse',
                'family_gedcom_id': fam_xref,
            })
            rows.append({
                'individual_gedcom_id': fam.wife_xref,
                'related_gedcom_id': fam.husband_xref,
                'relationship_type': 'spouse',
                'family_gedcom_id': fam_xref,
            })

        for i, child_a in enumerate(fam.children_xrefs):
            for child_b in fam.children_xrefs[i + 1:]:
                rows.append({
                    'individual_gedcom_id': child_a,
                    'related_gedcom_id': child_b,
                    'relationship_type': 'sibling',
                    'family_gedcom_id': fam_xref,
                })
                rows.append({
                    'individual_gedcom_id': child_b,
                    'related_gedcom_id': child_a,
                    'relationship_type': 'sibling',
                    'family_gedcom_id': fam_xref,
                })

    if dry_run:
        logger.info(f"DRY RUN: Would import {len(rows)} relationships")
        return len(rows)

    sb.table('gedcom_relationships').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()

    imported = 0
    for i in range(0, len(rows), 500):
        chunk = rows[i:i + 500]
        sb.table('gedcom_relationships').insert(chunk).execute()
        imported += len(chunk)
        if imported % 5000 == 0:
            logger.info(f"  Imported {imported}/{len(rows)} relationships...")

    logger.info(f"Imported {imported} relationships")
    return imported


def import_face_links(sb, dry_run=False):
    """Import existing GEDCOM match decisions from data/gedcom_matches.json."""
    matches_path = PROJECT_ROOT / "data" / "gedcom_matches.json"
    if not matches_path.exists():
        logger.info("No gedcom_matches.json found — skipping face links")
        return 0

    with open(matches_path) as f:
        data = json.load(f)

    rows = []
    for match in data.get("matches", []):
        if match.get("status") == "confirmed":
            rows.append({
                'identity_id': match.get('identity_id', ''),
                'gedcom_id': match.get('gedcom_xref', ''),
                'confidence': match.get('match_score', 0),
                'linked_by': 'admin',
            })
        elif match.get("status") != "rejected":
            rows.append({
                'identity_id': match.get('identity_id', ''),
                'gedcom_id': match.get('gedcom_xref', ''),
                'confidence': match.get('match_score', 0),
                'linked_by': 'auto-match',
            })

    if dry_run:
        logger.info(f"DRY RUN: Would import {len(rows)} face links")
        return len(rows)

    if rows:
        sb.table('gedcom_face_links').upsert(
            rows, on_conflict='identity_id,gedcom_id'
        ).execute()

    logger.info(f"Imported {len(rows)} face links")
    return len(rows)


def main():
    parser = argparse.ArgumentParser(description="Import GEDCOM data into Supabase")
    parser.add_argument('--file', required=True, help='Path to GEDCOM file')
    parser.add_argument('--execute', action='store_true', help='Actually import (default: dry-run)')
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()

    dry_run = not args.execute
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(levelname)s: %(message)s'
    )

    filepath = Path(args.file).expanduser()
    if not filepath.exists():
        logger.error(f"GEDCOM file not found: {filepath}")
        sys.exit(1)

    logger.info(f"Parsing GEDCOM: {filepath.name}")
    from rhodesli_ml.importers.gedcom_parser import parse_gedcom
    parsed = parse_gedcom(str(filepath))
    logger.info(f"Parsed: {parsed.individual_count} individuals, {parsed.family_count} families")

    total_events = sum(
        (1 if i.birth else 0) + (1 if i.death else 0) + len(i.events)
        for i in parsed.individuals.values()
    )
    logger.info(f"Total events: {total_events}")

    if dry_run:
        import_individuals(None, parsed, filepath.name, dry_run=True)
        import_events(None, parsed, dry_run=True)
        import_relationships(None, parsed, dry_run=True)
        import_face_links(None, dry_run=True)
        logger.info("\nDRY RUN complete. Use --execute to import.")
        return

    from dotenv import load_dotenv
    load_dotenv()

    sb = get_supabase_client()
    logger.info("Connected to Supabase")

    n_indi = import_individuals(sb, parsed, filepath.name)
    n_events = import_events(sb, parsed)
    n_rels = import_relationships(sb, parsed)
    n_links = import_face_links(sb)

    logger.info(f"\n=== IMPORT COMPLETE ===")
    logger.info(f"Individuals: {n_indi}")
    logger.info(f"Events:      {n_events}")
    logger.info(f"Relationships: {n_rels}")
    logger.info(f"Face links:  {n_links}")


if __name__ == '__main__':
    main()
