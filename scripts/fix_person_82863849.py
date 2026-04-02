#!/usr/bin/env python3
"""
One-time fix: Restore Person 82863849 from REJECTED to INBOX.

The admin accidentally rejected this Fader collection identity from a mobile device.
This script finds the identity whose ID ends with "82863849" and restores it.

Usage:
    python scripts/fix_person_82863849.py --dry-run   # Preview
    python scripts/fix_person_82863849.py --execute    # Apply fix
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from core.registry import IdentityRegistry


def find_identity_by_suffix(registry: IdentityRegistry, suffix: str) -> tuple[str, dict] | None:
    """Find an identity whose identity_id ends with the given suffix."""
    for identity_id, identity in registry._identities.items():
        if identity_id.endswith(suffix):
            return identity_id, identity
    return None


def main():
    parser = argparse.ArgumentParser(description="Restore Person 82863849 from REJECTED to INBOX")
    parser.add_argument("--dry-run", action="store_true", help="Preview without making changes")
    parser.add_argument("--execute", action="store_true", help="Apply the fix")
    args = parser.parse_args()

    if not args.dry_run and not args.execute:
        print("ERROR: Must specify --dry-run or --execute")
        sys.exit(1)

    registry = IdentityRegistry.load()
    result = find_identity_by_suffix(registry, "82863849")

    if result is None:
        print("ERROR: No identity found with ID ending in '82863849'")
        sys.exit(1)

    identity_id, identity = result
    state = identity.get("state", "UNKNOWN")
    name = identity.get("name", "Unknown")

    print(f"Found: {name}")
    print(f"  identity_id: {identity_id}")
    print(f"  state: {state}")
    print(f"  anchor_ids: {len(identity.get('anchor_ids', []))}")
    print(f"  candidate_ids: {len(identity.get('candidate_ids', []))}")

    if state not in ("REJECTED", "CONTESTED"):
        print(f"\nINFO: Identity is already in state '{state}', no fix needed.")
        sys.exit(0)

    if args.dry_run:
        print(f"\nDRY RUN: Would change state from '{state}' to 'INBOX'")
        print("Run with --execute to apply.")
        return

    # Apply the fix
    print(f"\nApplying fix: {state} -> INBOX")
    registry.reset_identity(identity_id, user_source="data_fix_session_147")
    registry.save()
    print(f"DONE: Identity {identity_id} restored to INBOX")
    print(f"  Previous state: {state}")
    print("  New state: INBOX")


if __name__ == "__main__":
    main()
