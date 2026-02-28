#!/usr/bin/env python3
"""Sync GEDCOM relationships from local data/relationships.json to Supabase.

This script pushes the curated local relationships (1,019 entries using a mix
of UUID identity IDs and GEDCOM xref IDs) to Supabase, replacing any existing
raw GEDCOM relationships.

The local relationships.json contains relationships mapped from the GEDCOM file
through the identity linking process, where confirmed identities get UUID IDs
and unlinked GEDCOM individuals keep their @I...@ xref IDs. This is what the
/tree route needs to render the family tree correctly.

Usage:
    # Dry run (preview what would be synced)
    python scripts/sync_gedcom_to_supabase.py --dry-run

    # Actually sync
    python scripts/sync_gedcom_to_supabase.py

    # Sync with verbose output
    python scripts/sync_gedcom_to_supabase.py --verbose

Requires: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables
(or .env file in the project root).
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger(__name__)


def load_env():
    """Load environment variables from .env file if available.

    Checks the project root first, then walks up parent directories
    to find .env (handles worktree layouts where .env is in the main repo).
    """
    env_path = None
    for candidate in [
        PROJECT_ROOT / ".env",
        PROJECT_ROOT.parent.parent.parent / ".env",  # worktree: .claude/worktrees/X/
    ]:
        if candidate.exists():
            env_path = candidate
            break
    if not env_path:
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


def load_local_relationships(data_dir: Path) -> list:
    """Load relationships from local data/relationships.json.

    Returns list of relationship dicts.
    """
    rel_path = data_dir / "relationships.json"
    if not rel_path.exists():
        raise FileNotFoundError(f"relationships.json not found at {rel_path}")

    data = json.loads(rel_path.read_text(encoding="utf-8"))
    relationships = data.get("relationships", [])
    return relationships


def get_supabase_relationship_count(sb) -> int:
    """Get current count of relationships in Supabase."""
    result = sb.table("relationships").select("id", count="exact").execute()
    return result.count or 0


def sync_relationships_to_supabase(sb, relationships: list, batch_size: int = 200) -> dict:
    """Sync relationships to Supabase using delete-all + batch insert.

    Args:
        sb: Supabase client
        relationships: list of relationship dicts from local JSON
        batch_size: number of rows per insert batch

    Returns:
        dict with sync stats: inserted, errors, etc.
    """
    stats = {"deleted": 0, "inserted": 0, "errors": 0, "error_details": []}

    # Step 1: Delete all existing relationships
    try:
        sb.table("relationships").delete().neq(
            "id", "00000000-0000-0000-0000-000000000000"
        ).execute()
        stats["deleted"] = True
    except Exception as e:
        stats["errors"] += 1
        stats["error_details"].append(f"Delete failed: {e}")
        return stats

    if not relationships:
        return stats

    # Step 2: Build rows for insert
    rows = []
    for r in relationships:
        rows.append({
            "person_a": r.get("person_a"),
            "person_b": r.get("person_b"),
            "relationship_type": r.get("type"),
            "source": r.get("source", "gedcom"),
            "data": r,
            "updated_at": r.get("created_at"),
        })

    # Step 3: Batch insert
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        try:
            sb.table("relationships").insert(batch).execute()
            stats["inserted"] += len(batch)
        except Exception as e:
            stats["errors"] += 1
            stats["error_details"].append(
                f"Insert batch {i // batch_size} failed: {e}"
            )

    return stats


def verify_sync(sb, expected_count: int) -> dict:
    """Verify the sync was successful by checking counts."""
    actual = get_supabase_relationship_count(sb)
    return {
        "expected": expected_count,
        "actual": actual,
        "match": actual == expected_count,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Sync GEDCOM relationships to Supabase"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be synced without making changes",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Verbose output"
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=PROJECT_ROOT / "data",
        help="Path to data directory",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    # Load .env
    load_env()

    # Check env vars
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not supabase_key:
        logger.error(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set. "
            "Check your .env file."
        )
        sys.exit(1)

    # Load local relationships
    try:
        relationships = load_local_relationships(args.data_dir)
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)

    # Analyze local data
    types = {}
    person_ids = set()
    uuid_count = 0
    gedcom_count = 0
    for r in relationships:
        t = r.get("type", "unknown")
        types[t] = types.get(t, 0) + 1
        for key in ("person_a", "person_b"):
            pid = r.get(key, "")
            person_ids.add(pid)
            if pid.startswith("@"):
                gedcom_count += 1
            else:
                uuid_count += 1

    print(f"\n{'=' * 60}")
    print("GEDCOM Relationship Sync to Supabase")
    print(f"{'=' * 60}")
    print(f"Local relationships: {len(relationships)}")
    print(f"  By type: {types}")
    print(f"  Unique persons: {len(person_ids)}")
    print(f"  UUID person refs: {uuid_count}")
    print(f"  GEDCOM person refs: {gedcom_count}")

    if args.dry_run:
        # Connect to Supabase for read-only check
        from supabase import create_client

        sb = create_client(supabase_url, supabase_key)
        current_count = get_supabase_relationship_count(sb)
        print(f"\nSupabase current: {current_count} relationships")
        print(f"After sync: {len(relationships)} relationships")
        print(f"Net change: {len(relationships) - current_count:+d}")
        print("\n[DRY RUN] No changes made. Run without --dry-run to sync.")
        return

    # Connect and sync
    from supabase import create_client

    sb = create_client(supabase_url, supabase_key)
    current_count = get_supabase_relationship_count(sb)
    print(f"\nSupabase before: {current_count} relationships")

    print("Syncing...")
    stats = sync_relationships_to_supabase(sb, relationships)
    print(f"  Deleted existing: {'yes' if stats['deleted'] else 'FAILED'}")
    print(f"  Inserted: {stats['inserted']}")
    if stats["errors"]:
        print(f"  Errors: {stats['errors']}")
        for detail in stats["error_details"]:
            print(f"    {detail}")

    # Verify
    verification = verify_sync(sb, len(relationships))
    print(f"\nVerification:")
    print(f"  Expected: {verification['expected']}")
    print(f"  Actual:   {verification['actual']}")
    print(f"  Status:   {'PASS' if verification['match'] else 'FAIL'}")

    if not verification["match"]:
        logger.error("Sync verification FAILED — counts don't match!")
        sys.exit(1)

    print(f"\nSync complete. {len(relationships)} relationships in Supabase.")


if __name__ == "__main__":
    main()
