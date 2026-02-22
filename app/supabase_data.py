"""Supabase data layer for user-entered data persistence.

Architecture (AD-135):
- Supabase = source of truth for user decisions
- JSON files = read cache (not modified directly by end-users)
- All user writes go through save_registry() → this module
- If Supabase is unavailable, app continues from JSON (degraded mode)

Tables:
- identity_overrides: complete identity records for user-modified identities
- annotations: community annotations (name suggestions, bios, etc.)
- relationships: person-to-person relationships
- gedcom_matches: GEDCOM individual → identity match decisions
"""

import json
import logging
import os

logger = logging.getLogger(__name__)

# Module-level client cache
_supabase_client = None
_supabase_available = None  # None = not tested, True/False = tested


def get_supabase_client():
    """Get Supabase client using service role key. Returns None if not configured."""
    global _supabase_client, _supabase_available

    if _supabase_available is False:
        return None
    if _supabase_client is not None:
        return _supabase_client

    url = os.environ.get('SUPABASE_URL')
    key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
    if not url or not key:
        _supabase_available = False
        logger.info("Supabase not configured (no SERVICE_ROLE_KEY) — JSON-only mode")
        return None

    try:
        from supabase import create_client
        _supabase_client = create_client(url, key)
        _supabase_available = True
        logger.info("Supabase client initialized")
        return _supabase_client
    except Exception as e:
        _supabase_available = False
        logger.warning(f"Supabase client init failed: {e}")
        return None


def reset_client():
    """Reset client cache (for testing)."""
    global _supabase_client, _supabase_available
    _supabase_client = None
    _supabase_available = None


def _is_user_modified_identity(data):
    """Check if an identity has been modified by users.

    User-modified means state was changed from ML-default, or has
    user-entered metadata, or has been merged, or has face rejections.
    """
    state = data.get('state', 'INBOX')
    if state in ('CONFIRMED', 'CONTESTED', 'SKIPPED'):
        return True
    if data.get('merged_into') is not None:
        return True
    if len(data.get('negative_ids', [])) > 0:
        return True
    metadata = data.get('metadata', {})
    user_fields = ['birth_year', 'death_year', 'birth_place', 'death_place',
                   'maiden_name', 'generation_qualifier', 'relationship_notes',
                   'bio', 'gedcom_xref', 'ancestry_url']
    if any(metadata.get(f) for f in user_fields):
        return True
    return False


# =========================================================================
# IDENTITY SYNC
# =========================================================================

def sync_identity_overrides(identities_dict):
    """Upsert all user-modified identities to Supabase.

    Called after every save_registry(). Syncs the full state of each
    user-modified identity so Supabase stays current.

    Args:
        identities_dict: dict of {identity_id: identity_data} from the registry
    """
    sb = get_supabase_client()
    if not sb:
        return

    rows = []
    for identity_id, data in identities_dict.items():
        if _is_user_modified_identity(data):
            rows.append({
                'identity_id': identity_id,
                'state': data.get('state', 'INBOX'),
                'name': data.get('name'),
                'merged_into': data.get('merged_into'),
                'data': data,
                'updated_by': 'admin',
                'updated_at': data.get('updated_at'),
            })

    if not rows:
        return

    try:
        batch_size = 100
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            sb.table('identity_overrides').upsert(batch).execute()
        logger.debug(f"Synced {len(rows)} identity overrides to Supabase")
    except Exception as e:
        logger.warning(f"Supabase identity sync failed (degraded mode): {e}")


# =========================================================================
# ANNOTATION SYNC
# =========================================================================

def sync_annotations(annotations_dict):
    """Upsert all annotations to Supabase.

    Called after every _save_annotations(). Syncs the full annotations dict.

    Args:
        annotations_dict: dict of {annotation_id: annotation_data}
    """
    sb = get_supabase_client()
    if not sb:
        return

    rows = []
    for ann_id, ann in annotations_dict.items():
        rows.append({
            'annotation_id': ann_id,
            'identity_id': ann.get('target_id') if ann.get('target_type') == 'identity' else None,
            'photo_id': ann.get('target_id') if ann.get('target_type') == 'photo' else None,
            'type': ann.get('type'),
            'status': ann.get('status', 'pending'),
            'data': ann,
            'updated_at': ann.get('reviewed_at') or ann.get('submitted_at'),
        })

    if not rows:
        return

    try:
        sb.table('annotations').upsert(rows).execute()
        logger.debug(f"Synced {len(rows)} annotations to Supabase")
    except Exception as e:
        logger.warning(f"Supabase annotation sync failed (degraded mode): {e}")


# =========================================================================
# RELATIONSHIP SYNC
# =========================================================================

def sync_relationships(relationships_list):
    """Sync relationships to Supabase.

    Args:
        relationships_list: list of relationship dicts from relationships.json
    """
    sb = get_supabase_client()
    if not sb:
        return

    try:
        # Delete all existing and re-insert (relationships don't have stable IDs)
        sb.table('relationships').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()

        if not relationships_list:
            return

        rows = []
        for r in relationships_list:
            rows.append({
                'person_a': r.get('person_a'),
                'person_b': r.get('person_b'),
                'relationship_type': r.get('type'),
                'source': r.get('source', 'human'),
                'data': r,
                'updated_at': r.get('created_at'),
            })

        sb.table('relationships').insert(rows).execute()
        logger.debug(f"Synced {len(rows)} relationships to Supabase")
    except Exception as e:
        logger.warning(f"Supabase relationship sync failed (degraded mode): {e}")


# =========================================================================
# GEDCOM SYNC
# =========================================================================

def sync_gedcom_matches(matches_list):
    """Sync GEDCOM matches to Supabase.

    Args:
        matches_list: list of match dicts from gedcom_matches.json
    """
    sb = get_supabase_client()
    if not sb:
        return

    rows = []
    for m in matches_list:
        rows.append({
            'xref_id': m.get('gedcom_xref'),
            'identity_id': m.get('identity_id'),
            'decision': m.get('status', 'pending'),
            'data': m,
            'updated_at': m.get('updated_at'),
        })

    if not rows:
        return

    try:
        sb.table('gedcom_matches').upsert(rows).execute()
        logger.debug(f"Synced {len(rows)} GEDCOM matches to Supabase")
    except Exception as e:
        logger.warning(f"Supabase GEDCOM sync failed (degraded mode): {e}")


# =========================================================================
# STARTUP SYNC (Supabase → JSON)
# =========================================================================

def sync_from_supabase_on_startup(data_path):
    """Rebuild JSON cache from Supabase source of truth.

    Runs on every deploy/restart. Ensures JSON files reflect the latest
    Supabase state, even if a deploy bundled stale JSON files.

    This is what makes deploys data-safe: the bundled JSON gets merged
    with Supabase truth on startup.

    Args:
        data_path: Path to the data directory (e.g., /app/storage/data/)
    """
    sb = get_supabase_client()
    if not sb:
        logger.warning("Supabase unavailable on startup — using existing JSON cache")
        return False

    from pathlib import Path
    import portalocker

    data_path = Path(data_path)
    changes_made = False

    # --- Sync identity overrides ---
    try:
        result = sb.table('identity_overrides').select('identity_id, data').execute()
        overrides = {row['identity_id']: row['data'] for row in result.data}

        if overrides:
            ids_path = data_path / 'identities.json'
            if ids_path.exists():
                with open(ids_path) as f:
                    ids_data = json.load(f)

                identities = ids_data.get('identities', {})
                applied = 0
                for identity_id, override_data in overrides.items():
                    identities[identity_id] = override_data
                    applied += 1

                ids_data['identities'] = identities

                # Atomic write with lock
                tmp_path = ids_path.with_suffix('.tmp')
                with open(tmp_path, 'w') as f:
                    portalocker.lock(f, portalocker.LOCK_EX)
                    json.dump(ids_data, f, indent=2)
                tmp_path.replace(ids_path)

                logger.info(f"Startup sync: applied {applied} identity overrides from Supabase")
                changes_made = True
    except Exception as e:
        logger.error(f"Startup sync failed for identities: {e}")

    # --- Sync annotations ---
    try:
        result = sb.table('annotations').select('annotation_id, data').execute()
        if result.data:
            ann_path = data_path / 'annotations.json'
            ann_data = {'schema_version': 1, 'annotations': {}}
            if ann_path.exists():
                with open(ann_path) as f:
                    ann_data = json.load(f)

            for row in result.data:
                ann_data.setdefault('annotations', {})[row['annotation_id']] = row['data']

            tmp_path = ann_path.with_suffix('.tmp')
            with open(tmp_path, 'w') as f:
                portalocker.lock(f, portalocker.LOCK_EX)
                json.dump(ann_data, f, indent=2)
            tmp_path.replace(ann_path)

            logger.info(f"Startup sync: applied {len(result.data)} annotations from Supabase")
            changes_made = True
    except Exception as e:
        logger.error(f"Startup sync failed for annotations: {e}")

    # --- Sync relationships ---
    try:
        result = sb.table('relationships').select('data').execute()
        if result.data:
            rel_path = data_path / 'relationships.json'
            rel_data = {
                'schema_version': 1,
                'relationships': [row['data'] for row in result.data]
            }

            tmp_path = rel_path.with_suffix('.tmp')
            with open(tmp_path, 'w') as f:
                portalocker.lock(f, portalocker.LOCK_EX)
                json.dump(rel_data, f, indent=2)
            tmp_path.replace(rel_path)

            logger.info(f"Startup sync: applied {len(result.data)} relationships from Supabase")
            changes_made = True
    except Exception as e:
        logger.error(f"Startup sync failed for relationships: {e}")

    # --- Sync GEDCOM matches ---
    try:
        result = sb.table('gedcom_matches').select('data').execute()
        if result.data:
            gm_path = data_path / 'gedcom_matches.json'
            gm_data = {'schema_version': 1, 'matches': []}
            if gm_path.exists():
                with open(gm_path) as f:
                    gm_data = json.load(f)

            # Replace matches list with Supabase data
            gm_data['matches'] = [row['data'] for row in result.data]

            tmp_path = gm_path.with_suffix('.tmp')
            with open(tmp_path, 'w') as f:
                portalocker.lock(f, portalocker.LOCK_EX)
                json.dump(gm_data, f, indent=2)
            tmp_path.replace(gm_path)

            logger.info(f"Startup sync: applied {len(result.data)} GEDCOM matches from Supabase")
            changes_made = True
    except Exception as e:
        logger.error(f"Startup sync failed for GEDCOM matches: {e}")

    if changes_made:
        logger.info("Startup sync from Supabase complete — JSON cache updated")
    else:
        logger.info("Startup sync: no changes from Supabase")

    return changes_made
