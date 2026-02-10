#!/usr/bin/env python3
"""Verify ROADMAP.md and docs/BACKLOG.md are in sync.

Checks that items marked [x] in ROADMAP.md are not marked OPEN in BACKLOG.md.
Run after any documentation update to catch drift.

Usage:
    python scripts/verify_docs_sync.py
"""

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ROADMAP_PATH = PROJECT_ROOT / "ROADMAP.md"
BACKLOG_PATH = PROJECT_ROOT / "docs" / "BACKLOG.md"

# Pattern to extract item IDs like BUG-001, FE-010, ML-004, etc.
ID_PATTERN = re.compile(r"(BUG|FE|BE|ML|QA|OPS|DATA|AN|ROLE|GEN)-(\d+)")


def extract_completed_ids(roadmap_text: str) -> set[str]:
    """Extract item IDs from lines marked [x] in ROADMAP.md."""
    completed = set()
    for line in roadmap_text.splitlines():
        if "[x]" in line:
            for match in ID_PATTERN.finditer(line):
                completed.add(match.group(0))
    return completed


def extract_open_ids(backlog_text: str) -> dict[str, str]:
    """Extract item IDs that are marked OPEN in BACKLOG.md.

    Returns dict of {item_id: line_text} for items with OPEN status.
    """
    open_items = {}
    for line in backlog_text.splitlines():
        # Look for table rows with OPEN status
        if "| OPEN |" in line or "| OPEN " in line:
            for match in ID_PATTERN.finditer(line):
                open_items[match.group(0)] = line.strip()
    return open_items


def verify_sync() -> list[tuple[str, str]]:
    """Check for items completed in ROADMAP but still OPEN in BACKLOG.

    Returns list of (item_id, backlog_line) tuples for mismatches.
    """
    if not ROADMAP_PATH.exists():
        print(f"WARNING: {ROADMAP_PATH} not found", file=sys.stderr)
        return []
    if not BACKLOG_PATH.exists():
        print(f"WARNING: {BACKLOG_PATH} not found", file=sys.stderr)
        return []

    roadmap_text = ROADMAP_PATH.read_text()
    backlog_text = BACKLOG_PATH.read_text()

    completed_ids = extract_completed_ids(roadmap_text)
    open_items = extract_open_ids(backlog_text)

    mismatches = []
    for item_id in sorted(completed_ids):
        if item_id in open_items:
            mismatches.append((item_id, open_items[item_id]))

    return mismatches


def main():
    mismatches = verify_sync()

    if not mismatches:
        print("OK: ROADMAP.md and docs/BACKLOG.md are in sync.")
        print(f"  Checked {ROADMAP_PATH.name} and {BACKLOG_PATH.name}")
        sys.exit(0)
    else:
        print(f"DRIFT DETECTED: {len(mismatches)} item(s) completed in ROADMAP.md but still OPEN in BACKLOG.md:\n")
        for item_id, line in mismatches:
            print(f"  {item_id}: {line}")
        print(f"\nFix: Update docs/BACKLOG.md to mark these items as DONE.")
        sys.exit(1)


if __name__ == "__main__":
    main()
