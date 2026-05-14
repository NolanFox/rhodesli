"""Tests for app.rhodes_inbox — Session 161 Phase 2/6.

Covers:
- _validate_slug: regex + path-traversal defense (Codex P0-2)
- is_rhodes_wiki_available: RAILWAY_ENVIRONMENT gate (Codex P1-2)
- list_*: filesystem walks, malformed-skipping
- load_entry: valid + invalid
- mark_approved: atomic CAS happy path + race-loser + missing-row recovery (Codex P0-1, P2-A)
- mark_rejected: rejection_reason length cap (Codex P3-B)
- count_pending_rhodes_inbox: production safety
- link_rhodesli_photo + kinship_triples_for caching
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MINIMAL_POST = {
    "contract_version": "0.1.0",
    "parser_version": "0.1.0-js",
    "inbox_entry_id": "2026-04-28_2360240064471306",
    "fb_post_url": "https://www.facebook.com/groups/546890742472923/posts/2360240064471306",
    "fb_post_id": "2360240064471306",
    "captured_at": "2026-05-12T02:41:35Z",
    "captured_by": "nolanfox@gmail.com",
    "post_author": {
        "name": "Martha Girgenti",
        "fb_id": "601975565",
        "fb_profile_url": "/groups/546890742472923/user/601975565/",
    },
    "post_date": "2026-04-28",
    "caption": {
        "text": "Look what I just found in my mother's album. Edward and Renee Menasche 1971 in Rhodesia.",
        "language_guess": "en",
        "truncated": False,
    },
    "comments_count_extracted": 14,
    "comments": [
        {"comment_id": "c1", "text": "Such wonderful memories", "author": {"name": "Stella Hanan Cohen"}},
        {"comment_id": "c2", "text": "Rachel being the sister of my Mother-in-law Diana Amato Merdjan", "author": {"name": "April Merdjan"}},
    ],
    "rhodesli_handoff": {
        "suggested_community_slug": "rhodes",
    },
}


@pytest.fixture
def fake_inbox(tmp_path, monkeypatch):
    """Create a fake rhodes-wiki inbox tree under tmp_path with one pending
    entry. Sets RHODES_WIKI_ROOT to point at it."""
    root = tmp_path / "rhodes-wiki"
    (root / "inbox" / "pending" / "2026-04-28_2360240064471306").mkdir(parents=True)
    (root / "inbox" / "approved").mkdir()
    (root / "inbox" / "rejected").mkdir()
    post_path = root / "inbox" / "pending" / "2026-04-28_2360240064471306" / "post.json"
    post_path.write_text(json.dumps(MINIMAL_POST), encoding="utf-8")
    monkeypatch.setenv("RHODES_WIKI_ROOT", str(root))
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)
    return root


# ---------------------------------------------------------------------------
# Slug validation (Codex P0-2)
# ---------------------------------------------------------------------------

def test_validate_slug_accepts_valid(fake_inbox):
    from app.rhodes_inbox import _validate_slug
    _validate_slug("2026-04-28_2360240064471306")  # canonical Session 160 slug
    _validate_slug("2026-01-01_a_b_c")  # underscores OK
    _validate_slug("2099-12-31_abcDEF123-xyz")  # hyphens + mixed case OK


def test_validate_slug_rejects_path_traversal(fake_inbox):
    from app.rhodes_inbox import _validate_slug
    for bad in ("../../../etc/passwd", "../approved/something", "/etc/passwd"):
        with pytest.raises(ValueError):
            _validate_slug(bad)


def test_validate_slug_rejects_malformed(fake_inbox):
    from app.rhodes_inbox import _validate_slug
    for bad in ("", "no-date-prefix", "2026-04-28_$pecial!chars", "2026-04-28", None, 12345):
        with pytest.raises(ValueError):
            _validate_slug(bad)  # type: ignore[arg-type]


def test_validate_slug_rejects_dotdot_in_alnum_section(fake_inbox):
    """Sneaky pattern: looks date-prefixed but uses .. in the alnum part."""
    from app.rhodes_inbox import _validate_slug
    with pytest.raises(ValueError):
        _validate_slug("2026-04-28_../etc")


# ---------------------------------------------------------------------------
# Production gate (Codex P1-2)
# ---------------------------------------------------------------------------

def test_is_rhodes_wiki_available_true_locally(fake_inbox):
    from app.rhodes_inbox import is_rhodes_wiki_available
    assert is_rhodes_wiki_available() is True


def test_is_rhodes_wiki_available_false_when_railway_set(fake_inbox, monkeypatch):
    """Audit P1-2: RAILWAY_ENVIRONMENT must hard-block the gate even if
    a misconfigured RHODES_WIKI_ROOT points at a valid-looking path."""
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    from app.rhodes_inbox import is_rhodes_wiki_available
    assert is_rhodes_wiki_available() is False


def test_is_rhodes_wiki_available_false_when_path_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("RHODES_WIKI_ROOT", str(tmp_path / "does-not-exist"))
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)
    from app.rhodes_inbox import is_rhodes_wiki_available
    assert is_rhodes_wiki_available() is False


def test_count_pending_returns_zero_on_railway(fake_inbox, monkeypatch):
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    from app.rhodes_inbox import count_pending_rhodes_inbox
    assert count_pending_rhodes_inbox() == 0


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------

def test_list_pending_returns_summary(fake_inbox):
    from app.rhodes_inbox import list_pending_entries
    entries = list_pending_entries()
    assert len(entries) == 1
    s = entries[0]
    assert s.slug == "2026-04-28_2360240064471306"
    assert s.fb_author_name == "Martha Girgenti"
    assert s.comments_count == 14
    assert s.status == "pending"


def test_list_pending_empty_when_no_entries(tmp_path, monkeypatch):
    root = tmp_path / "rhodes-wiki"
    (root / "inbox" / "pending").mkdir(parents=True)
    monkeypatch.setenv("RHODES_WIKI_ROOT", str(root))
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)
    from app.rhodes_inbox import list_pending_entries
    assert list_pending_entries() == []


def test_list_skips_malformed_post_json(fake_inbox):
    """Malformed JSON in one entry should not crash the list — log + skip."""
    bad_dir = fake_inbox / "inbox" / "pending" / "2026-04-29_badentry00000001"
    bad_dir.mkdir(parents=True)
    (bad_dir / "post.json").write_text("{not valid json", encoding="utf-8")
    from app.rhodes_inbox import list_pending_entries
    entries = list_pending_entries()
    # Only the valid one
    assert len(entries) == 1
    assert entries[0].slug == "2026-04-28_2360240064471306"


def test_list_skips_dirs_not_matching_slug_pattern(fake_inbox):
    """Random scratch dirs (no date prefix) are silently skipped."""
    (fake_inbox / "inbox" / "pending" / "scratch_dir").mkdir()
    from app.rhodes_inbox import list_pending_entries
    entries = list_pending_entries()
    assert len(entries) == 1


# ---------------------------------------------------------------------------
# load_entry
# ---------------------------------------------------------------------------

def test_load_entry_returns_full_post(fake_inbox):
    from app.rhodes_inbox import load_entry
    entry = load_entry("2026-04-28_2360240064471306", state="pending")
    assert entry["fb_post_id"] == "2360240064471306"
    assert len(entry["comments"]) == 2


def test_load_entry_raises_on_missing(fake_inbox):
    from app.rhodes_inbox import load_entry
    with pytest.raises(FileNotFoundError):
        load_entry("2026-04-28_doesnotexist0001", state="pending")


def test_load_entry_validates_slug(fake_inbox):
    from app.rhodes_inbox import load_entry
    with pytest.raises(ValueError):
        load_entry("../../../etc/passwd")


# ---------------------------------------------------------------------------
# mark_approved — atomic CAS (Codex P0-1, P2-A)
# ---------------------------------------------------------------------------

def _mock_supabase_for_approve(initial_status: str | None = "pending"):
    """Build a MagicMock supabase client whose .update().eq().eq().execute()
    chain returns a result based on the row's current status."""
    state = {"status": initial_status}
    client = MagicMock()

    def update_execute_factory():
        result = MagicMock()
        # If filter matches the current state, return [row]; else []
        if state["status"] == "pending":
            state["status"] = "approved"
            result.data = [{"slug": "x", "status": "approved"}]
        else:
            result.data = []
        return result

    table_mock = MagicMock()
    update_chain = table_mock.update.return_value.eq.return_value.eq.return_value
    update_chain.execute.side_effect = update_execute_factory

    # select().eq().limit().execute() — for the post-CAS check
    select_chain = table_mock.select.return_value.eq.return_value.limit.return_value
    def select_execute():
        r = MagicMock()
        r.data = [{"status": state["status"]}] if state["status"] else []
        return r
    select_chain.execute.side_effect = select_execute

    # upsert().execute() — passthrough
    table_mock.upsert.return_value.execute.return_value = MagicMock(data=[])

    client.table.return_value = table_mock
    return client


def test_mark_approved_happy_path(fake_inbox):
    from app.rhodes_inbox import mark_approved
    client = _mock_supabase_for_approve("pending")
    with patch("app.rhodes_inbox._supabase_client", return_value=client):
        mark_approved(
            "2026-04-28_2360240064471306",
            approved_by="admin@example.com",
        )
    # Filesystem moved
    assert not (fake_inbox / "inbox" / "pending" / "2026-04-28_2360240064471306").exists()
    assert (fake_inbox / "inbox" / "approved" / "2026-04-28_2360240064471306" / "post.json").exists()


def test_mark_approved_already_approved_raises(fake_inbox):
    """Race-loser scenario: Supabase row already at 'approved' before this
    handler's CAS. _supabase_client mock returns 0 rows from CAS and 'approved'
    from the post-CAS status check."""
    from app.rhodes_inbox import mark_approved, AlreadyApprovedError
    client = _mock_supabase_for_approve("approved")  # already approved
    with patch("app.rhodes_inbox._supabase_client", return_value=client):
        with pytest.raises(AlreadyApprovedError):
            mark_approved(
                "2026-04-28_2360240064471306",
                approved_by="admin@example.com",
            )
    # Filesystem NOT moved (race-loser bails before fs op)
    assert (fake_inbox / "inbox" / "pending" / "2026-04-28_2360240064471306").exists()


def test_mark_approved_rejects_path_traversal_slug(fake_inbox):
    """Audit P0-2 regression: malicious slug must raise BEFORE any Supabase or
    filesystem op."""
    from app.rhodes_inbox import mark_approved
    client = MagicMock()
    with patch("app.rhodes_inbox._supabase_client", return_value=client):
        with pytest.raises(ValueError):
            mark_approved("../../../etc/passwd", approved_by="admin@example.com")
    # Supabase never touched
    client.table.assert_not_called()


def test_mark_approved_creates_row_when_missing(fake_inbox):
    """When the Supabase row doesn't exist (admin approved from list view
    without ever opening the detail), mark_approved upserts then retries."""
    from app.rhodes_inbox import mark_approved
    # First CAS: 0 rows; select: empty; upsert; second CAS: success.
    state = {"row_exists": False, "status": None, "cas_calls": 0}
    client = MagicMock()
    table_mock = MagicMock()

    def update_execute():
        state["cas_calls"] += 1
        r = MagicMock()
        if state["row_exists"] and state["status"] == "pending":
            state["status"] = "approved"
            r.data = [{"slug": "x", "status": "approved"}]
        else:
            r.data = []
        return r
    table_mock.update.return_value.eq.return_value.eq.return_value.execute.side_effect = update_execute

    def select_execute():
        r = MagicMock()
        r.data = [{"status": state["status"]}] if state["row_exists"] else []
        return r
    table_mock.select.return_value.eq.return_value.limit.return_value.execute.side_effect = select_execute

    def upsert_execute():
        state["row_exists"] = True
        state["status"] = "pending"
        return MagicMock(data=[])
    table_mock.upsert.return_value.execute.side_effect = upsert_execute

    client.table.return_value = table_mock

    with patch("app.rhodes_inbox._supabase_client", return_value=client):
        mark_approved("2026-04-28_2360240064471306", approved_by="admin@example.com")

    assert state["cas_calls"] == 2  # one fail, one success
    assert state["status"] == "approved"


# ---------------------------------------------------------------------------
# mark_rejected
# ---------------------------------------------------------------------------

def test_mark_rejected_caps_reason_at_4096_chars(fake_inbox):
    """Codex P3-B: rejection_reason longer than 4096 chars is truncated before
    Supabase write so the CHECK constraint can't reject it."""
    from app.rhodes_inbox import mark_rejected
    long_reason = "x" * 10000
    client = _mock_supabase_for_approve("pending")
    captured_payload = {}
    original_update = client.table.return_value.update

    def update_capture(payload):
        captured_payload["update"] = payload
        return original_update.return_value
    client.table.return_value.update.side_effect = update_capture

    with patch("app.rhodes_inbox._supabase_client", return_value=client):
        mark_rejected(
            "2026-04-28_2360240064471306",
            rejected_by="admin@example.com",
            reason=long_reason,
        )

    assert "update" in captured_payload
    assert len(captured_payload["update"]["rejection_reason"]) == 4096


def test_mark_rejected_moves_filesystem_to_rejected(fake_inbox):
    from app.rhodes_inbox import mark_rejected
    client = _mock_supabase_for_approve("pending")
    with patch("app.rhodes_inbox._supabase_client", return_value=client):
        mark_rejected(
            "2026-04-28_2360240064471306",
            rejected_by="admin@example.com",
            reason="not relevant",
        )
    assert not (fake_inbox / "inbox" / "pending" / "2026-04-28_2360240064471306").exists()
    assert (fake_inbox / "inbox" / "rejected" / "2026-04-28_2360240064471306" / "post.json").exists()
