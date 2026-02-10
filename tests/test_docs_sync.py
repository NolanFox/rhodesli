"""Test that project documentation files are in sync."""

import sys
from pathlib import Path

# Add project root to path so we can import the verification script
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from verify_docs_sync import verify_sync, extract_completed_ids, extract_open_ids


def test_roadmap_backlog_sync():
    """Items completed in ROADMAP.md must not be OPEN in BACKLOG.md."""
    mismatches = verify_sync()
    if mismatches:
        ids = [item_id for item_id, _ in mismatches]
        raise AssertionError(
            f"ROADMAP↔BACKLOG drift: {len(mismatches)} item(s) completed in ROADMAP.md "
            f"but still OPEN in docs/BACKLOG.md: {', '.join(ids)}"
        )


def test_extract_completed_ids():
    """Verify ID extraction from ROADMAP-style lines."""
    text = """
- [x] BUG-001: Fixed something (2026-02-08)
- [ ] FE-052: Not done yet
- [x] ML-004: Dynamic threshold (2026-02-09, AD-013)
- [-] BE-010: In progress
"""
    ids = extract_completed_ids(text)
    assert "BUG-001" in ids
    assert "ML-004" in ids
    assert "FE-052" not in ids  # not completed
    assert "BE-010" not in ids  # in progress, not completed


def test_extract_open_ids():
    """Verify OPEN item extraction from BACKLOG-style table rows."""
    text = """
| FE-052 | First-time user guided tour | OPEN | Step-by-step overlay |
| FE-050 | Welcome landing page | DONE | Fixed 2026-02-06 |
| ML-013 | Evaluation dashboard | OPEN | Web UI for results |
"""
    open_items = extract_open_ids(text)
    assert "FE-052" in open_items
    assert "ML-013" in open_items
    assert "FE-050" not in open_items  # DONE, not OPEN


def test_no_false_positive_on_open_in_text():
    """OPEN in descriptive text (not status column) should not trigger."""
    text = """
| BE-001 | Direction-aware merge | DONE | Was OPEN, now fixed |
"""
    open_items = extract_open_ids(text)
    assert "BE-001" not in open_items  # "OPEN" is in notes, not status column
