#!/usr/bin/env python3
"""
Active Learning Loop CLI for Identity Management.

Human-in-the-loop interface for managing face identities with full
provenance and reversibility.

Usage:
    python scripts/manage_identities.py list
    python scripts/manage_identities.py show <identity_id>
    python scripts/manage_identities.py create --anchor face_001 --name "John Doe"
    python scripts/manage_identities.py promote <identity_id> <face_id>
    python scripts/manage_identities.py reject <identity_id> <face_id>
    python scripts/manage_identities.py undo <identity_id>
    python scripts/manage_identities.py confirm <identity_id>
    python scripts/manage_identities.py contest <identity_id> --reason "Disputed"
    python scripts/manage_identities.py history <identity_id>
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from core.registry import IdentityRegistry, IdentityState

# Default registry path
DEFAULT_REGISTRY_PATH = project_root / "data" / "identities.json"


def load_registry(path: Path) -> IdentityRegistry:
    """Load registry from file or create new one."""
    if path.exists():
        return IdentityRegistry.load(path)
    return IdentityRegistry()


def save_registry(registry: IdentityRegistry, path: Path) -> None:
    """Save registry to file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    registry.save(path)


def cmd_list(args):
    """List all identities."""
    registry = load_registry(args.registry)

    state_filter = None
    if args.state:
        state_filter = IdentityState[args.state.upper()]

    identities = registry.list_identities(state=state_filter)

    if not identities:
        print("No identities found.")
        return

    print(f"\n{'ID':<40} {'Name':<20} {'State':<12} {'Anchors':<8} {'Candidates':<10}")
    print("-" * 95)

    for identity in identities:
        name = identity.get("name") or "(unnamed)"
        print(
            f"{identity['identity_id']:<40} "
            f"{name[:20]:<20} "
            f"{identity['state']:<12} "
            f"{len(identity['anchor_ids']):<8} "
            f"{len(identity['candidate_ids']):<10}"
        )

    print(f"\nTotal: {len(identities)} identities")


def cmd_show(args):
    """Show identity details."""
    registry = load_registry(args.registry)

    try:
        identity = registry.get_identity(args.identity_id)
    except KeyError:
        print(f"Error: Identity not found: {args.identity_id}")
        sys.exit(1)

    print(f"\n{'=' * 60}")
    print(f"Identity: {identity['identity_id']}")
    print(f"{'=' * 60}")
    print(f"Name:       {identity.get('name') or '(unnamed)'}")
    print(f"State:      {identity['state']}")
    print(f"Version:    {identity['version_id']}")
    print(f"Created:    {identity['created_at']}")
    print(f"Updated:    {identity['updated_at']}")
    print()
    print(f"Anchors ({len(identity['anchor_ids'])}):")
    for face_id in identity['anchor_ids']:
        print(f"  - {face_id}")
    print()
    print(f"Candidates ({len(identity['candidate_ids'])}):")
    for face_id in identity['candidate_ids']:
        print(f"  - {face_id}")
    print()
    print(f"Rejected ({len(identity['negative_ids'])}):")
    for face_id in identity['negative_ids']:
        print(f"  - {face_id}")


def cmd_create(args):
    """Create a new identity."""
    registry = load_registry(args.registry)

    identity_id = registry.create_identity(
        anchor_ids=args.anchor,
        name=args.name,
        candidate_ids=args.candidate or [],
        user_source=args.user or "cli",
    )

    save_registry(registry, args.registry)

    print(f"Created identity: {identity_id}")
    if args.name:
        print(f"Name: {args.name}")
    print(f"Anchors: {args.anchor}")
    if args.candidate:
        print(f"Candidates: {args.candidate}")


def cmd_promote(args):
    """Promote a candidate to anchor."""
    registry = load_registry(args.registry)

    try:
        registry.promote_candidate(
            args.identity_id,
            args.face_id,
            user_source=args.user or "cli",
            confidence_weight=args.weight,
        )
    except (KeyError, ValueError) as e:
        print(f"Error: {e}")
        sys.exit(1)

    save_registry(registry, args.registry)
    print(f"Promoted {args.face_id} to anchor for {args.identity_id}")


def cmd_reject(args):
    """Reject a candidate."""
    registry = load_registry(args.registry)

    try:
        registry.reject_candidate(
            args.identity_id,
            args.face_id,
            user_source=args.user or "cli",
        )
    except (KeyError, ValueError) as e:
        print(f"Error: {e}")
        sys.exit(1)

    save_registry(registry, args.registry)
    print(f"Rejected {args.face_id} from {args.identity_id}")


def cmd_undo(args):
    """Undo the last action on an identity."""
    registry = load_registry(args.registry)

    try:
        registry.undo(args.identity_id, user_source=args.user or "cli")
    except (KeyError, ValueError) as e:
        print(f"Error: {e}")
        sys.exit(1)

    save_registry(registry, args.registry)
    print(f"Undid last action on {args.identity_id}")


def cmd_confirm(args):
    """Confirm an identity."""
    registry = load_registry(args.registry)

    try:
        registry.confirm_identity(args.identity_id, user_source=args.user or "cli")
    except KeyError as e:
        print(f"Error: {e}")
        sys.exit(1)

    save_registry(registry, args.registry)
    print(f"Confirmed identity {args.identity_id}")


def cmd_contest(args):
    """Contest an identity."""
    registry = load_registry(args.registry)

    try:
        registry.contest_identity(
            args.identity_id,
            user_source=args.user or "cli",
            reason=args.reason,
        )
    except KeyError as e:
        print(f"Error: {e}")
        sys.exit(1)

    save_registry(registry, args.registry)
    print(f"Contested identity {args.identity_id}")
    if args.reason:
        print(f"Reason: {args.reason}")


def cmd_history(args):
    """Show event history for an identity."""
    registry = load_registry(args.registry)

    try:
        registry.get_identity(args.identity_id)  # Verify exists
    except KeyError:
        print(f"Error: Identity not found: {args.identity_id}")
        sys.exit(1)

    history = registry.get_history(args.identity_id)

    if not history:
        print("No history found.")
        return

    print(f"\nHistory for {args.identity_id}")
    print("=" * 80)

    for event in history:
        print(f"\n[{event['timestamp']}] {event['action'].upper()}")
        print(f"  Event ID: {event['event_id']}")
        print(f"  User: {event['user_source']}")
        if event['face_ids']:
            print(f"  Faces: {event['face_ids']}")
        if event['confidence_weight'] != 1.0:
            print(f"  Confidence: {event['confidence_weight']}")
        if event['metadata']:
            print(f"  Metadata: {event['metadata']}")


def main():
    parser = argparse.ArgumentParser(
        description="Active Learning Loop CLI for Identity Management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=DEFAULT_REGISTRY_PATH,
        help=f"Path to registry file (default: {DEFAULT_REGISTRY_PATH})",
    )
    parser.add_argument(
        "--user",
        type=str,
        default=None,
        help="User source for provenance tracking",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # list command
    list_parser = subparsers.add_parser("list", help="List all identities")
    list_parser.add_argument(
        "--state",
        choices=["proposed", "confirmed", "contested"],
        help="Filter by state",
    )
    list_parser.set_defaults(func=cmd_list)

    # show command
    show_parser = subparsers.add_parser("show", help="Show identity details")
    show_parser.add_argument("identity_id", help="Identity ID to show")
    show_parser.set_defaults(func=cmd_show)

    # create command
    create_parser = subparsers.add_parser("create", help="Create new identity")
    create_parser.add_argument(
        "--anchor",
        action="append",
        required=True,
        help="Anchor face ID (can specify multiple)",
    )
    create_parser.add_argument("--name", help="Identity name")
    create_parser.add_argument(
        "--candidate",
        action="append",
        help="Candidate face ID (can specify multiple)",
    )
    create_parser.set_defaults(func=cmd_create)

    # promote command
    promote_parser = subparsers.add_parser("promote", help="Promote candidate to anchor")
    promote_parser.add_argument("identity_id", help="Identity ID")
    promote_parser.add_argument("face_id", help="Face ID to promote")
    promote_parser.add_argument(
        "--weight",
        type=float,
        default=1.0,
        help="Confidence weight (default: 1.0)",
    )
    promote_parser.set_defaults(func=cmd_promote)

    # reject command
    reject_parser = subparsers.add_parser("reject", help="Reject a candidate")
    reject_parser.add_argument("identity_id", help="Identity ID")
    reject_parser.add_argument("face_id", help="Face ID to reject")
    reject_parser.set_defaults(func=cmd_reject)

    # undo command
    undo_parser = subparsers.add_parser("undo", help="Undo last action")
    undo_parser.add_argument("identity_id", help="Identity ID")
    undo_parser.set_defaults(func=cmd_undo)

    # confirm command
    confirm_parser = subparsers.add_parser("confirm", help="Confirm identity")
    confirm_parser.add_argument("identity_id", help="Identity ID")
    confirm_parser.set_defaults(func=cmd_confirm)

    # contest command
    contest_parser = subparsers.add_parser("contest", help="Contest identity")
    contest_parser.add_argument("identity_id", help="Identity ID")
    contest_parser.add_argument("--reason", help="Reason for contesting")
    contest_parser.set_defaults(func=cmd_contest)

    # history command
    history_parser = subparsers.add_parser("history", help="Show event history")
    history_parser.add_argument("identity_id", help="Identity ID")
    history_parser.set_defaults(func=cmd_history)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
