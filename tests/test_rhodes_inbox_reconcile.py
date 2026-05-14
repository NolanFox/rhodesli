"""Session 161 Phase 8 — post-execution audit P1-1 fix.

Coverage for `scripts/rhodes_inbox_reconcile.py` drift detection and
reconciliation. Pure-unit tests: tmp_path filesystem + mocked Supabase
client — no production data touched.

Test taxonomy:
- detect_drift: consistent state, mismatch case, fs_only case, sb_only case
- reconcile: mismatch → fs moved; fs_only → sb row created; sb_only → no-op
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_inbox(tmp_path, monkeypatch):
    """Create a tmp_path/inbox/{pending,approved,rejected}/ tree.

    Returns the tmp_path root. Tests can populate state subdirs with slug-
    pattern dirs as needed.
    """
    inbox_root = tmp_path / "inbox"
    (inbox_root / "pending").mkdir(parents=True)
    (inbox_root / "approved").mkdir()
    (inbox_root / "rejected").mkdir()
    monkeypatch.setenv("RHODES_WIKI_ROOT", str(tmp_path))
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)
    return tmp_path


def _make_entry(fake_inbox: Path, slug: str, state: str, *, with_post_json: bool = True) -> None:
    """Create a slug directory under the given state with a minimal post.json."""
    entry_dir = fake_inbox / "inbox" / state / slug
    entry_dir.mkdir(parents=True)
    if with_post_json:
        (entry_dir / "post.json").write_text(json.dumps({
            "fb_post_id": "test-fb-id-" + slug,
            "fb_post_url": "https://www.facebook.com/test/" + slug,
            "post_author": {"name": "Test Author", "fb_id": "test-fb-author"},
            "captured_at": "2026-05-13T00:00:00Z",
            "captured_by": "test@example.com",
            "contract_version": "0.1.0",
            "parser_version": "test-parser-1.0",
            "comments_count_extracted": 3,
        }), encoding="utf-8")


# ---------------------------------------------------------------------------
# detect_drift
# ---------------------------------------------------------------------------

def test_detect_drift_consistent_returns_no_drift(fake_inbox):
    """When fs and sb both have slug=X at status=pending, drift is empty."""
    slug = "2026-05-13_test_consistent"
    _make_entry(fake_inbox, slug, "pending")

    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.execute.return_value.data = [
        {"slug": slug, "status": "pending"}
    ]
    with patch("scripts.rhodes_inbox_reconcile._supabase_client", return_value=mock_client):
        from scripts.rhodes_inbox_reconcile import detect_drift
        drift = detect_drift()

    assert drift["fs_only"] == []
    assert drift["sb_only"] == []
    assert drift["mismatch"] == []
    assert drift["consistent"] == 1
    assert drift["totals"] == {"fs": 1, "sb": 1}


def test_detect_drift_mismatch_status(fake_inbox):
    """fs at 'pending' but sb at 'approved' is the post-crash recovery case."""
    slug = "2026-05-13_test_mismatch"
    _make_entry(fake_inbox, slug, "pending")  # fs side at pending

    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.execute.return_value.data = [
        {"slug": slug, "status": "approved"}  # sb side at approved
    ]
    with patch("scripts.rhodes_inbox_reconcile._supabase_client", return_value=mock_client):
        from scripts.rhodes_inbox_reconcile import detect_drift
        drift = detect_drift()

    assert drift["mismatch"] == [(slug, "pending", "approved")]
    assert drift["fs_only"] == []
    assert drift["sb_only"] == []
    assert drift["consistent"] == 0


def test_detect_drift_fs_only(fake_inbox):
    """Filesystem entry with no Supabase row — captured by rhodes-wiki but never
    seen by a rhodesli detail-view-load yet."""
    slug = "2026-05-13_test_fs_only"
    _make_entry(fake_inbox, slug, "pending")

    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.execute.return_value.data = []
    with patch("scripts.rhodes_inbox_reconcile._supabase_client", return_value=mock_client):
        from scripts.rhodes_inbox_reconcile import detect_drift
        drift = detect_drift()

    assert drift["fs_only"] == [slug]
    assert drift["mismatch"] == []
    assert drift["sb_only"] == []


def test_detect_drift_sb_only(fake_inbox):
    """Supabase row with no filesystem entry — admin manually rm'd, or capture
    happened on another machine."""
    slug = "2026-05-13_test_sb_only"
    # No filesystem entry created.

    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.execute.return_value.data = [
        {"slug": slug, "status": "approved"}
    ]
    with patch("scripts.rhodes_inbox_reconcile._supabase_client", return_value=mock_client):
        from scripts.rhodes_inbox_reconcile import detect_drift
        drift = detect_drift()

    assert drift["sb_only"] == [(slug, "approved")]
    assert drift["fs_only"] == []
    assert drift["mismatch"] == []


# ---------------------------------------------------------------------------
# reconcile
# ---------------------------------------------------------------------------

def test_reconcile_mismatch_moves_filesystem_to_supabase_state(fake_inbox):
    """The canonical post-crash recovery path: Supabase=approved, fs=pending →
    reconcile moves fs to approved/."""
    slug = "2026-05-13_test_reconcile_mismatch"
    _make_entry(fake_inbox, slug, "pending")

    mock_client = MagicMock()
    with patch("scripts.rhodes_inbox_reconcile._supabase_client", return_value=mock_client):
        from scripts.rhodes_inbox_reconcile import reconcile
        drift = {
            "mismatch": [(slug, "pending", "approved")],
            "fs_only": [],
            "sb_only": [],
            "consistent": 0,
            "totals": {"fs": 1, "sb": 1},
        }
        actions = reconcile(drift)

    assert actions["fs_moved"] == 1
    assert actions["sb_created"] == 0
    assert actions["fs_missing"] == 0
    # Filesystem is now at approved/
    assert (fake_inbox / "inbox" / "approved" / slug).is_dir()
    assert not (fake_inbox / "inbox" / "pending" / slug).exists()


def test_reconcile_fs_only_creates_supabase_row(fake_inbox):
    """A filesystem-only slug gets a minimal Supabase row at fs state."""
    slug = "2026-05-13_test_reconcile_fs_only"
    _make_entry(fake_inbox, slug, "pending")

    mock_client = MagicMock()
    upsert_mock = MagicMock()
    mock_client.table.return_value.upsert.return_value = upsert_mock
    with patch("scripts.rhodes_inbox_reconcile._supabase_client", return_value=mock_client):
        from scripts.rhodes_inbox_reconcile import reconcile
        drift = {
            "mismatch": [],
            "fs_only": [slug],
            "sb_only": [],
            "consistent": 0,
            "totals": {"fs": 1, "sb": 0},
        }
        actions = reconcile(drift)

    assert actions["sb_created"] == 1
    # Verify the upsert payload had the right shape
    upsert_args, _ = mock_client.table.return_value.upsert.call_args
    payload = upsert_args[0]
    assert payload["slug"] == slug
    assert payload["status"] == "pending"
    assert payload["fb_post_id"] == "test-fb-id-" + slug
    assert payload["fb_post_url"].endswith(slug)


def test_reconcile_sb_only_reports_no_filesystem_side_effects(fake_inbox):
    """sb_only is intentionally reported-only — admin must choose whether to
    create a stub on disk. Reconcile must not touch the filesystem."""
    slug = "2026-05-13_test_reconcile_sb_only"

    mock_client = MagicMock()
    with patch("scripts.rhodes_inbox_reconcile._supabase_client", return_value=mock_client):
        from scripts.rhodes_inbox_reconcile import reconcile
        drift = {
            "mismatch": [],
            "fs_only": [],
            "sb_only": [(slug, "approved")],
            "consistent": 0,
            "totals": {"fs": 0, "sb": 1},
        }
        actions = reconcile(drift)

    assert actions["fs_moved"] == 0
    assert actions["sb_created"] == 0
    # No directories created anywhere
    for state in ("pending", "approved", "rejected"):
        assert not (fake_inbox / "inbox" / state / slug).exists()


def test_reconcile_handles_consistent_state_with_no_actions(fake_inbox):
    """Empty drift → zero actions, no Supabase writes, no filesystem mutations."""
    mock_client = MagicMock()
    with patch("scripts.rhodes_inbox_reconcile._supabase_client", return_value=mock_client):
        from scripts.rhodes_inbox_reconcile import reconcile
        drift = {
            "mismatch": [],
            "fs_only": [],
            "sb_only": [],
            "consistent": 5,
            "totals": {"fs": 5, "sb": 5},
        }
        actions = reconcile(drift)

    assert actions == {"fs_moved": 0, "sb_created": 0, "fs_missing": 0}
    # No upserts attempted
    mock_client.table.return_value.upsert.assert_not_called()
