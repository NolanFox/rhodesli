#!/usr/bin/env python3
"""Import a new GEDCOM version with temporal tracking and change detection.

Compares against the previous version and creates a change log.
Old data is never deleted, only superseded. The app reads "current" state via views.

Usage:
    python scripts/import_gedcom_version.py --file ~/Downloads/Family.ged --dry-run
    python scripts/import_gedcom_version.py --file ~/Downloads/Family.ged --execute
    python scripts/import_gedcom_version.py --file ~/Downloads/Family.ged --execute --notes "Added Marcus branch"
"""

import argparse
import hashlib
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


def hash_file(filepath: Path) -> str:
    """SHA256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def get_next_version_number(sb, community_id: str = 'rhodesli') -> int:
    """Get the next version number for a community."""
    result = (sb.table('gedcom_versions')
              .select('version_number')
              .eq('community_id', community_id)
              .order('version_number', desc=True)
              .limit(1)
              .execute())
    if result.data:
        return result.data[0]['version_number'] + 1
    return 1


def check_duplicate_hash(sb, source_hash: str, community_id: str = 'rhodesli') -> dict | None:
    """Check if this exact file was already imported. Returns version if duplicate."""
    result = (sb.table('gedcom_versions')
              .select('*')
              .eq('source_hash', source_hash)
              .eq('community_id', community_id)
              .limit(1)
              .execute())
    return result.data[0] if result.data else None


def load_current_individuals(sb) -> dict:
    """Load all current (non-superseded) individuals, keyed by gedcom_id."""
    individuals = {}
    offset = 0
    page_size = 1000
    while True:
        result = (sb.table('gedcom_individuals')
                  .select('*')
                  .or_('is_current.eq.true,is_current.is.null')
                  .range(offset, offset + page_size - 1)
                  .execute())
        for row in result.data:
            individuals[row['gedcom_id']] = row
        if len(result.data) < page_size:
            break
        offset += page_size
    return individuals


INDIVIDUAL_COMPARE_FIELDS = [
    'name', 'given_name', 'surname', 'gender',
    'birth_date', 'birth_place', 'death_date', 'death_place',
]


def diff_individual(old: dict, new_data: dict) -> list[dict]:
    """Compare an old individual row to new parsed data. Returns field-level changes."""
    changes = []
    for field in INDIVIDUAL_COMPARE_FIELDS:
        old_val = old.get(field) or ''
        new_val = new_data.get(field) or ''
        if str(old_val).strip() != str(new_val).strip():
            changes.append({
                'field_name': field,
                'old_value': str(old_val) if old_val else None,
                'new_value': str(new_val) if new_val else None,
            })
    return changes


def build_individual_row(xref_id: str, indi, source_file: str) -> dict:
    """Build a row dict from a parsed GEDCOM individual."""
    return {
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
    }


def import_versioned(sb, parsed, source_file: str, source_hash: str,
                     community_id: str = 'rhodesli', notes: str = None,
                     dry_run: bool = False) -> dict:
    """Import a new GEDCOM version with full change tracking.

    Returns summary dict: {version_id, added, modified, removed, unchanged, changes}
    """
    # Check for duplicate
    existing = check_duplicate_hash(sb, source_hash, community_id) if sb else None
    if existing:
        logger.warning(f"This exact file was already imported as version {existing['version_number']} "
                       f"on {existing['imported_at']}. Skipping.")
        return {'skipped': True, 'reason': 'duplicate_hash',
                'existing_version': existing['version_number']}

    version_number = get_next_version_number(sb, community_id) if sb else 1
    logger.info(f"Creating version {version_number} for community '{community_id}'")

    # Load current state for comparison
    current_individuals = load_current_individuals(sb) if sb else {}
    logger.info(f"Current database has {len(current_individuals)} individuals")

    # Build new individual rows
    new_individuals = {}
    for xref_id, indi in parsed.individuals.items():
        new_individuals[xref_id] = build_individual_row(xref_id, indi, source_file)

    # Classify changes
    added = []
    modified = []
    unchanged = []
    all_changes = []

    new_xrefs = set(new_individuals.keys())
    old_xrefs = set(current_individuals.keys())

    for xref_id in new_xrefs:
        new_data = new_individuals[xref_id]
        if xref_id not in old_xrefs:
            added.append(new_data)
            all_changes.append({
                'change_type': 'added',
                'entity_type': 'individual',
                'xref_id': xref_id,
            })
        else:
            field_changes = diff_individual(current_individuals[xref_id], new_data)
            if field_changes:
                modified.append((xref_id, new_data, field_changes))
                for fc in field_changes:
                    all_changes.append({
                        'change_type': 'modified',
                        'entity_type': 'individual',
                        'xref_id': xref_id,
                        **fc,
                    })
            else:
                unchanged.append(xref_id)

    removed_xrefs = old_xrefs - new_xrefs
    for xref_id in removed_xrefs:
        all_changes.append({
            'change_type': 'removed',
            'entity_type': 'individual',
            'xref_id': xref_id,
        })

    summary = {
        'added': len(added),
        'modified': len(modified),
        'removed': len(removed_xrefs),
        'unchanged': len(unchanged),
        'total_changes': len(all_changes),
    }

    logger.info(f"Diff summary: {summary['added']} added, {summary['modified']} modified, "
                f"{summary['removed']} removed, {summary['unchanged']} unchanged")

    if dry_run:
        logger.info("DRY RUN — no changes written")
        # Show sample changes
        for change in all_changes[:10]:
            logger.info(f"  {change['change_type']}: {change['xref_id']} "
                        f"{change.get('field_name', '')} "
                        f"{change.get('old_value', '')!r} → {change.get('new_value', '')!r}")
        if len(all_changes) > 10:
            logger.info(f"  ... and {len(all_changes) - 10} more changes")
        return {'dry_run': True, **summary}

    # --- Write to database ---

    # 1. Create version entry
    version_result = sb.table('gedcom_versions').insert({
        'version_number': version_number,
        'community_id': community_id,
        'source_file': source_file,
        'source_hash': source_hash,
        'individual_count': len(new_individuals),
        'family_count': parsed.family_count,
        'summary': summary,
        'notes': notes,
    }).execute()
    version_id = version_result.data[0]['id']
    logger.info(f"Created version {version_number} (id: {version_id})")

    # 2. Mark modified individuals as superseded
    for xref_id, new_data, field_changes in modified:
        old_row = current_individuals[xref_id]
        old_id = old_row.get('id')
        if old_id:
            # Insert new row first
            new_row = {**new_data, 'version_id': version_id, 'is_current': True}
            insert_result = sb.table('gedcom_individuals').insert(new_row).execute()
            new_id = insert_result.data[0]['id']
            # Mark old row as superseded
            sb.table('gedcom_individuals').update({
                'is_current': False,
                'superseded_by': new_id,
            }).eq('id', old_id).execute()

    # 3. Insert added individuals
    for i in range(0, len(added), 500):
        chunk = added[i:i + 500]
        for row in chunk:
            row['version_id'] = version_id
            row['is_current'] = True
        sb.table('gedcom_individuals').insert(chunk).execute()
    logger.info(f"Inserted {len(added)} new individuals")

    # 4. Mark removed individuals as not current
    for xref_id in removed_xrefs:
        old_row = current_individuals.get(xref_id)
        if old_row and old_row.get('id'):
            sb.table('gedcom_individuals').update({
                'is_current': False,
            }).eq('id', old_row['id']).execute()
    if removed_xrefs:
        logger.info(f"Marked {len(removed_xrefs)} removed individuals as not current")

    # 5. Write change log
    for i in range(0, len(all_changes), 500):
        chunk = all_changes[i:i + 500]
        for entry in chunk:
            entry['version_id'] = version_id
        sb.table('gedcom_change_log').insert(chunk).execute()
    logger.info(f"Wrote {len(all_changes)} change log entries")

    # 6. Queue re-enrichment for modified/removed individuals
    _queue_enrichments(sb, version_id, modified, removed_xrefs)

    return {'version_id': version_id, 'version_number': version_number, **summary}


def _queue_enrichments(sb, version_id: str, modified: list, removed_xrefs: set):
    """Queue photos for re-enrichment when their linked GEDCOM individuals changed."""
    # Get all face links to find affected photos
    affected_xrefs = {xref_id for xref_id, _, _ in modified} | removed_xrefs
    if not affected_xrefs:
        return

    # Load face links
    links_result = sb.table('gedcom_face_links').select('*').execute()
    face_links = {row['gedcom_id']: row for row in links_result.data}

    queue_rows = []
    for xref_id in affected_xrefs:
        link = face_links.get(xref_id)
        if not link:
            continue
        identity_id = link.get('identity_id')
        if not identity_id:
            continue
        # Find photos containing this identity — we'll use a placeholder photo_id
        # since the actual photo lookup requires the identity registry
        change_type = 'modified' if xref_id in {x for x, _, _ in modified} else 'removed'
        queue_rows.append({
            'photo_id': f'lookup:{identity_id}',  # Resolved at enrichment time
            'identity_id': identity_id,
            'gedcom_id': xref_id,
            'trigger': 'gedcom_update',
            'reason': f'GEDCOM {change_type}: {xref_id}',
            'version_id': version_id,
            'status': 'pending',
        })

    if queue_rows:
        for i in range(0, len(queue_rows), 500):
            chunk = queue_rows[i:i + 500]
            sb.table('gedcom_enrichment_queue').insert(chunk).execute()
        logger.info(f"Queued {len(queue_rows)} photos for re-enrichment")


def main():
    parser = argparse.ArgumentParser(description="Import versioned GEDCOM into Supabase")
    parser.add_argument('--file', required=True, help='Path to GEDCOM file')
    parser.add_argument('--execute', action='store_true', help='Actually import (default: dry-run)')
    parser.add_argument('--community', default='rhodesli', help='Community ID')
    parser.add_argument('--notes', default=None, help='Notes for this version')
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

    # Hash the file for dedup
    source_hash = hash_file(filepath)
    logger.info(f"File: {filepath.name} (SHA256: {source_hash[:16]}...)")

    # Parse GEDCOM
    logger.info(f"Parsing GEDCOM: {filepath.name}")
    from rhodesli_ml.importers.gedcom_parser import parse_gedcom
    parsed = parse_gedcom(str(filepath))
    logger.info(f"Parsed: {parsed.individual_count} individuals, {parsed.family_count} families")

    if dry_run:
        # For dry run, we still need Supabase to compare current state
        try:
            from dotenv import load_dotenv
            load_dotenv()
            sb = get_supabase_client()
        except Exception as e:
            logger.warning(f"Could not connect to Supabase for diff: {e}")
            logger.info("Showing parse results only (no diff without Supabase)")
            logger.info(f"  Individuals: {parsed.individual_count}")
            logger.info(f"  Families: {parsed.family_count}")
            return

        result = import_versioned(sb, parsed, filepath.name, source_hash,
                                  community_id=args.community, notes=args.notes,
                                  dry_run=True)
        logger.info(f"\nDRY RUN result: {json.dumps(result, indent=2)}")
        return

    from dotenv import load_dotenv
    load_dotenv()
    sb = get_supabase_client()
    logger.info("Connected to Supabase")

    result = import_versioned(sb, parsed, filepath.name, source_hash,
                              community_id=args.community, notes=args.notes,
                              dry_run=False)

    if result.get('skipped'):
        logger.info(f"Import skipped: {result['reason']}")
        return

    logger.info(f"\n=== IMPORT COMPLETE ===")
    logger.info(f"Version:    {result.get('version_number', '?')}")
    logger.info(f"Added:      {result.get('added', 0)}")
    logger.info(f"Modified:   {result.get('modified', 0)}")
    logger.info(f"Removed:    {result.get('removed', 0)}")
    logger.info(f"Unchanged:  {result.get('unchanged', 0)}")
    logger.info(f"Changes:    {result.get('total_changes', 0)}")


if __name__ == '__main__':
    main()
