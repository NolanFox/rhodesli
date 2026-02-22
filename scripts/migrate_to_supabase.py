"""One-time migration: JSON data → Supabase tables.

AD-135: Migrate user-entered data to Supabase.
Run once to populate tables, then verify counts.

Usage:
    python scripts/migrate_to_supabase.py --dry-run   # Preview what would be migrated
    python scripts/migrate_to_supabase.py --execute    # Actually migrate
"""

import json
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def load_env():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass


def get_supabase_client():
    from supabase import create_client
    url = os.environ.get('SUPABASE_URL')
    key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
    if not url or not key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
        sys.exit(1)
    return create_client(url, key)


def find_user_modified_identities(identities):
    """Identify which identities have been modified by users.

    User-modified means:
    - State changed to CONFIRMED, CONTESTED, or SKIPPED (user decision)
    - Has merged_into set (user merged it)
    - Has negative_ids (user rejected face candidates)
    - Has non-empty metadata with user-entered fields
    """
    modified = {}
    for identity_id, data in identities.items():
        state = data.get('state', 'INBOX')
        is_user_modified = (
            state in ('CONFIRMED', 'CONTESTED', 'SKIPPED') or
            data.get('merged_into') is not None or
            len(data.get('negative_ids', [])) > 0 or
            _has_user_metadata(data.get('metadata', {}))
        )
        if is_user_modified:
            modified[identity_id] = data
    return modified


def _has_user_metadata(metadata):
    """Check if metadata has user-entered fields (not just ML-generated)."""
    user_fields = ['birth_year', 'death_year', 'birth_place', 'death_place',
                   'maiden_name', 'generation_qualifier', 'relationship_notes',
                   'bio', 'gedcom_xref', 'ancestry_url']
    return any(metadata.get(f) for f in user_fields)


def migrate_identities(sb, identities, dry_run=True):
    """Migrate user-modified identities to identity_overrides table."""
    modified = find_user_modified_identities(identities)
    print(f"\nIdentities to migrate: {len(modified)}")

    if dry_run:
        by_state = {}
        for data in modified.values():
            s = data.get('state', 'UNKNOWN')
            by_state[s] = by_state.get(s, 0) + 1
        for s, c in sorted(by_state.items()):
            print(f"  {s}: {c}")
        return len(modified)

    # Batch insert in chunks of 50
    rows = []
    for identity_id, data in modified.items():
        rows.append({
            'identity_id': identity_id,
            'state': data.get('state', 'INBOX'),
            'name': data.get('name'),
            'merged_into': data.get('merged_into'),
            'data': data,
            'updated_by': 'migration_59c',
            'updated_at': data.get('updated_at'),
        })

    batch_size = 50
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        sb.table('identity_overrides').upsert(batch).execute()
        print(f"  Inserted batch {i // batch_size + 1}/{(len(rows) - 1) // batch_size + 1}")

    return len(rows)


def migrate_annotations(sb, dry_run=True):
    """Migrate annotations.json to annotations table."""
    ann_path = Path('data/annotations.json')
    if not ann_path.exists():
        print("\nNo annotations.json found — skipping")
        return 0

    with open(ann_path) as f:
        ann_data = json.load(f)

    items = ann_data.get('annotations', {})
    print(f"\nAnnotations to migrate: {len(items)}")

    if dry_run:
        for ann_id, ann in items.items():
            print(f"  {ann_id[:8]}... type={ann.get('type')} status={ann.get('status')}")
        return len(items)

    rows = []
    for ann_id, ann in items.items():
        rows.append({
            'annotation_id': ann_id,
            'identity_id': ann.get('target_id') if ann.get('target_type') == 'identity' else None,
            'photo_id': ann.get('target_id') if ann.get('target_type') == 'photo' else None,
            'type': ann.get('type'),
            'status': ann.get('status', 'pending'),
            'data': ann,
            'updated_at': ann.get('reviewed_at') or ann.get('submitted_at'),
        })

    if rows:
        sb.table('annotations').upsert(rows).execute()

    return len(rows)


def migrate_relationships(sb, dry_run=True):
    """Migrate relationships.json to relationships table."""
    rel_path = Path('data/relationships.json')
    if not rel_path.exists():
        print("\nNo relationships.json found — skipping")
        return 0

    with open(rel_path) as f:
        rel_data = json.load(f)

    rels = rel_data.get('relationships', [])
    print(f"\nRelationships to migrate: {len(rels)}")

    if dry_run:
        for r in rels[:5]:
            print(f"  {r.get('person_a', '?')[:8]}... → {r.get('person_b', '?')[:8]}... ({r.get('type')})")
        if len(rels) > 5:
            print(f"  ... and {len(rels) - 5} more")
        return len(rels)

    rows = []
    for r in rels:
        rows.append({
            'person_a': r.get('person_a'),
            'person_b': r.get('person_b'),
            'relationship_type': r.get('type'),
            'source': r.get('source', 'human'),
            'data': r,
            'updated_at': r.get('created_at'),
        })

    if rows:
        sb.table('relationships').upsert(rows, on_conflict='id').execute()

    return len(rows)


def migrate_gedcom_matches(sb, dry_run=True):
    """Migrate gedcom_matches.json to gedcom_matches table."""
    gm_path = Path('data/gedcom_matches.json')
    if not gm_path.exists():
        print("\nNo gedcom_matches.json found — skipping")
        return 0

    with open(gm_path) as f:
        gm_data = json.load(f)

    matches = gm_data.get('matches', [])
    print(f"\nGEDCOM matches to migrate: {len(matches)}")

    if dry_run:
        for m in matches[:5]:
            print(f"  {m.get('gedcom_xref')} → {m.get('identity_name', '?')} ({m.get('status')})")
        if len(matches) > 5:
            print(f"  ... and {len(matches) - 5} more")
        return len(matches)

    rows = []
    for m in matches:
        rows.append({
            'xref_id': m.get('gedcom_xref'),
            'identity_id': m.get('identity_id'),
            'decision': m.get('status', 'pending'),
            'data': m,
            'updated_at': m.get('updated_at'),
        })

    if rows:
        sb.table('gedcom_matches').upsert(rows).execute()

    return len(rows)


def verify_counts(sb, expected):
    """Verify Supabase row counts match expected migration counts."""
    print("\n=== VERIFICATION ===")
    all_match = True
    for table, exp_count in expected.items():
        result = sb.table(table).select('*', count='exact').limit(0).execute()
        actual = result.count
        status = "OK" if actual == exp_count else "MISMATCH"
        if status == "MISMATCH":
            all_match = False
        print(f"  {table}: expected={exp_count}, actual={actual} [{status}]")
    return all_match


def main():
    load_env()

    dry_run = '--execute' not in sys.argv
    if dry_run:
        print("=== DRY RUN (use --execute to migrate) ===\n")
    else:
        print("=== EXECUTING MIGRATION ===\n")

    # Load identity data
    with open('data/identities.json') as f:
        ids_data = json.load(f)
    identities = ids_data.get('identities', {})

    sb = None if dry_run else get_supabase_client()

    counts = {}
    counts['identity_overrides'] = migrate_identities(sb, identities, dry_run)
    counts['annotations'] = migrate_annotations(sb, dry_run)
    counts['relationships'] = migrate_relationships(sb, dry_run)
    counts['gedcom_matches'] = migrate_gedcom_matches(sb, dry_run)

    print(f"\n=== SUMMARY ===")
    total = 0
    for table, count in counts.items():
        print(f"  {table}: {count} rows")
        total += count
    print(f"  TOTAL: {total} rows")

    if not dry_run:
        sb = get_supabase_client()
        if not verify_counts(sb, counts):
            print("\nERROR: Count mismatch detected! Investigate before proceeding.")
            sys.exit(1)
        print("\nMigration complete. All counts verified.")


if __name__ == '__main__':
    main()
