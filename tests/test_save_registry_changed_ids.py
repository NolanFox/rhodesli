"""Structural test: all save_registry calls in triage routes must pass changed_ids.

Session 123 Phase 2 (PERF-B): When changed_ids is None, save_registry writes ALL
~3500 identities to Supabase. Triage routes should always pass the specific IDs
that were modified to avoid 5-10 second operations.

Whitelisted files (legitimate bulk callers):
- upload_routes.py: bulk ingest writes many identities
- sync_routes.py: full sync operations
"""

import re
from pathlib import Path


# Files that MUST pass changed_ids on every save_registry call
TRIAGE_ROUTE_FILES = [
    "app/identity_routes.py",
    "app/cluster_review_routes.py",
    "app/discoveries_routes.py",
    "app/browse_routes.py",
    "app/engagement_routes.py",
    "app/match_facecompare_routes.py",
    "app/page_routes.py",
    "app/relationship_routes.py",
    "app/admin_routes.py",
]


def _find_bare_save_registry_calls(filepath: str) -> list[tuple[int, str]]:
    """Find save_registry calls that don't include changed_ids."""
    path = Path(filepath)
    if not path.exists():
        return []

    violations = []
    content = path.read_text()
    lines = content.split("\n")

    i = 0
    while i < len(lines):
        line = lines[i]
        # Skip comments
        stripped = line.strip()
        if stripped.startswith("#"):
            i += 1
            continue

        if "save_registry(" in line:
            # Collect the full call (may span multiple lines)
            call_text = line
            paren_count = line.count("(") - line.count(")")
            j = i + 1
            while paren_count > 0 and j < len(lines):
                call_text += "\n" + lines[j]
                paren_count += lines[j].count("(") - lines[j].count(")")
                j += 1

            # Check if changed_ids is in the call
            if "changed_ids" not in call_text:
                violations.append((i + 1, stripped))

        i += 1

    return violations


def test_no_bare_save_registry_in_triage_routes():
    """Every save_registry() call in triage routes must pass changed_ids.

    This prevents the performance regression where all ~3500 identities
    are written to Supabase on every single triage action (FB-069).
    """
    all_violations = {}

    for filepath in TRIAGE_ROUTE_FILES:
        violations = _find_bare_save_registry_calls(filepath)
        if violations:
            all_violations[filepath] = violations

    if all_violations:
        msg_parts = ["Bare save_registry() calls found (missing changed_ids):"]
        for filepath, violations in all_violations.items():
            for line_num, line_text in violations:
                msg_parts.append(f"  {filepath}:{line_num}: {line_text}")
        msg_parts.append("\nFix: add changed_ids={identity_id} (or set of changed IDs) to each call.")
        raise AssertionError("\n".join(msg_parts))
