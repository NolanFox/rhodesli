"""rhodes-wiki inbox reader + Supabase status sync (Session 161).

Reads inbox JSON contract entries from the sibling rhodes-wiki vault at
`~/rhodes-wiki/inbox/<state>/<slug>/` and mirrors approval state to the
`rhodes_inbox_entries` Supabase table.

This module is the rhodesli-side consumer of the rhodes-wiki ↔ rhodesli
boundary defined in rhodes-wiki's `docs/ARCHITECTURE.md` §3.1 (the inbox
JSON contract v0.1.0).

ARCHITECTURE NOTES (Session 161, see docs/architecture/RHODES_INBOX.md):

- **Local-dev-only**: The admin route that uses this module is gated by
  `is_rhodes_wiki_available()` which requires BOTH local path existence
  AND no production env marker (RAILWAY_ENVIRONMENT). Production rhodesli
  has neither → admin route returns 404 cleanly. (AD-S161-1, Codex P1-2)

- **Supabase is authoritative for status**: filesystem mirrors it for
  offline-readable provenance. The atomic CAS in `mark_approved` writes
  Supabase first; the filesystem move is the second step. On crash between
  the two, the reconciliation script `scripts/rhodes_inbox_reconcile.py`
  detects drift. (AD-S161-6, Codex P0-1)

- **Path traversal defense**: every state-mutating function calls
  `_validate_slug()` which both regex-matches the slug AND verifies the
  resolved candidate path stays under inbox_root. (Codex P0-2)

- **Cross-repo decoupling**: `extract_kinship` was COPIED into rhodesli
  (`app/extract_kinship.py`) at Session 161 Phase 0 — rhodesli does NOT
  import from rhodes-wiki's Python at runtime. (Codex P1-7)
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Production gate (Codex P1-2)
# ---------------------------------------------------------------------------

def _rhodes_wiki_root() -> Path:
    """Return the rhodes-wiki repo root path. Defaults to ~/rhodes-wiki/."""
    return Path(os.environ.get("RHODES_WIKI_ROOT", str(Path.home() / "rhodes-wiki")))


def _rhodes_wiki_inbox_root() -> Path:
    return _rhodes_wiki_root() / "inbox"


def is_rhodes_wiki_available() -> bool:
    """Defense-in-depth gate: True only when BOTH path exists AND not on production.

    On Railway production the RAILWAY_ENVIRONMENT env var is set, which hard-
    blocks this gate even if a misconfigured RHODES_WIKI_ROOT points at a
    valid-looking directory. Local dev has no such marker.
    """
    if os.environ.get("RAILWAY_ENVIRONMENT"):
        return False
    return (_rhodes_wiki_inbox_root() / "pending").is_dir() or \
           (_rhodes_wiki_inbox_root() / "approved").is_dir()


# ---------------------------------------------------------------------------
# Slug validation (Codex P0-2)
# ---------------------------------------------------------------------------

# Matches slugs like "2026-04-28_2360240064471306" (date underscore alnum).
# This is the contract format documented in rhodes-wiki ARCHITECTURE.md §3.2.
_SLUG_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}_[a-zA-Z0-9_-]{1,64}$")

_VALID_STATES = ("pending", "approved", "rejected")


def _validate_slug(slug: str) -> None:
    """Reject malformed slugs AND slugs that resolve outside inbox root.

    Raises ValueError on any of:
      - slug fails the regex
      - resolved candidate path escapes inbox_root (path traversal attempt)

    Called from every state-mutating function and from the admin routes
    that take slug as a URL path parameter.
    """
    if not isinstance(slug, str) or not _SLUG_PATTERN.fullmatch(slug):
        raise ValueError(f"invalid slug: {slug!r}")
    inbox_root = _rhodes_wiki_inbox_root().resolve()
    inbox_root_str = str(inbox_root)
    for state in _VALID_STATES:
        candidate = (inbox_root / state / slug).resolve()
        try:
            common = os.path.commonpath([str(candidate), inbox_root_str])
        except ValueError:
            # commonpath raises if paths are on different drives (Windows)
            # or otherwise incomparable. Treat as traversal.
            raise ValueError(f"slug resolves outside inbox root: {slug!r}")
        if common != inbox_root_str:
            raise ValueError(f"slug resolves outside inbox root: {slug!r}")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class InboxSummary:
    slug: str
    fb_post_id: str
    fb_post_url: str
    fb_author_name: str
    captured_at: str
    comments_count: int
    status: Literal["pending", "approved", "rejected"]

    def to_dict(self) -> dict:
        return {
            "slug": self.slug,
            "fb_post_id": self.fb_post_id,
            "fb_post_url": self.fb_post_url,
            "fb_author_name": self.fb_author_name,
            "captured_at": self.captured_at,
            "comments_count": self.comments_count,
            "status": self.status,
        }


class AlreadyApprovedError(RuntimeError):
    """Raised when mark_approved cannot CAS — slug is no longer in 'pending'.

    Indicates either: (a) concurrent admin already approved, or (b) admin
    is retrying an already-completed action. Caller should treat as
    success-equivalent for the user-facing flow.
    """


class AlreadyRejectedError(RuntimeError):
    """Same as AlreadyApprovedError for the reject path."""


# ---------------------------------------------------------------------------
# Filesystem reads
# ---------------------------------------------------------------------------

def _read_post_json(slug: str, state: str) -> dict | None:
    """Read post.json for a slug + state. Returns None on missing/malformed
    (so list-style scans don't crash on one bad entry — they log + skip)."""
    path = _rhodes_wiki_inbox_root() / state / slug / "post.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.warning("malformed post.json at %s: %s", path, exc)
        return None


def _summarize(slug: str, state: str, post: dict) -> InboxSummary | None:
    """Build an InboxSummary from a post.json dict. Returns None on missing
    required contract fields (logs + skips upstream)."""
    try:
        return InboxSummary(
            slug=slug,
            fb_post_id=post.get("fb_post_id") or "",
            fb_post_url=post.get("fb_post_url") or "",
            fb_author_name=(post.get("post_author") or {}).get("name") or "",
            captured_at=post.get("captured_at") or "",
            comments_count=int(post.get("comments_count_extracted") or 0),
            status=state,  # type: ignore[arg-type]
        )
    except (TypeError, ValueError) as exc:
        logger.warning("bad post.json shape for slug=%s state=%s: %s", slug, state, exc)
        return None


def _list_state(state: str) -> list[InboxSummary]:
    """List inbox entries in a given filesystem state. Logs + skips malformed."""
    if state not in _VALID_STATES:
        raise ValueError(f"invalid state: {state!r}")
    if not is_rhodes_wiki_available():
        return []
    state_dir = _rhodes_wiki_inbox_root() / state
    if not state_dir.is_dir():
        return []
    out: list[InboxSummary] = []
    for slug_dir in sorted(state_dir.iterdir(), reverse=True):
        if not slug_dir.is_dir():
            continue
        slug = slug_dir.name
        # Defensive: silently skip dirs that don't match the slug pattern
        # (some other process could have dropped scratch dirs)
        if not _SLUG_PATTERN.fullmatch(slug):
            continue
        post = _read_post_json(slug, state)
        if post is None:
            continue
        summary = _summarize(slug, state, post)
        if summary is not None:
            out.append(summary)
    return out


def list_pending_entries() -> list[InboxSummary]:
    return _list_state("pending")


def list_approved_entries() -> list[InboxSummary]:
    return _list_state("approved")


def list_rejected_entries() -> list[InboxSummary]:
    return _list_state("rejected")


def count_pending_rhodes_inbox() -> int:
    """Used by admin nav for the pending-count badge. Safe in production
    (returns 0 when rhodes-wiki is unavailable)."""
    if not is_rhodes_wiki_available():
        return 0
    try:
        return len(list_pending_entries())
    except Exception:  # noqa: BLE001
        logger.exception("count_pending_rhodes_inbox failed; returning 0")
        return 0


def load_entry(slug: str, *, state: Literal["pending", "approved", "rejected"] = "pending") -> dict:
    """Return the full post.json content for slug. Raises ValueError on bad
    slug, FileNotFoundError on missing file."""
    _validate_slug(slug)
    if state not in _VALID_STATES:
        raise ValueError(f"invalid state: {state!r}")
    post = _read_post_json(slug, state)
    if post is None:
        raise FileNotFoundError(
            f"no post.json found for slug={slug!r} in state={state!r}"
        )
    return post


# ---------------------------------------------------------------------------
# Status transitions (Codex P0-1: Supabase-first, atomic CAS)
# ---------------------------------------------------------------------------

def _supabase_client():
    """Lazy import — Supabase client construction is slow at import time."""
    from app.supabase_data import get_supabase_client
    return get_supabase_client()


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _upsert_inbox_row_for_pending(slug: str, post: dict) -> None:
    """Insert the row at status=pending if not yet present. Idempotent."""
    client = _supabase_client()
    if not client:
        raise RuntimeError("Supabase client unavailable; cannot upsert inbox row")
    payload = {
        "slug": slug,
        "fb_post_id": post.get("fb_post_id") or "",
        "fb_group_id": post.get("rhodesli_handoff", {}).get("suggested_community_slug")
        if isinstance(post.get("rhodesli_handoff"), dict) else None,
        "fb_post_url": post.get("fb_post_url") or "",
        "fb_author_name": (post.get("post_author") or {}).get("name"),
        "fb_author_id": (post.get("post_author") or {}).get("fb_id"),
        "captured_at": post.get("captured_at"),
        "captured_by": post.get("captured_by"),
        "contract_version": post.get("contract_version"),
        "parser_version": post.get("parser_version"),
        "comments_count": int(post.get("comments_count_extracted") or 0),
        "status": "pending",
    }
    # ON CONFLICT DO NOTHING — re-render of detail view is idempotent
    client.table("rhodes_inbox_entries").upsert(
        payload,
        on_conflict="slug",
        ignore_duplicates=True,
    ).execute()


def mark_approved(
    slug: str,
    *,
    approved_by: str,
    rhodesli_photo_id: str | None = None,
) -> None:
    """Atomic-CAS approval. Supabase first, filesystem second.

    Order (per AD-S161-6, Codex P0-1):
      1. _validate_slug(slug)  — path-traversal guard
      2. Supabase update with WHERE status='pending' filter
         - If 0 rows updated → raise AlreadyApprovedError
      3. os.replace(inbox/pending/<slug>, inbox/approved/<slug>) — POSIX atomic
         - If this fails: Supabase row stays at 'approved'; reconciliation
           script detects drift; re-raise OSError so caller surfaces it.
      4. Audit log (best-effort; not transactional)
    """
    _validate_slug(slug)

    client = _supabase_client()
    if not client:
        raise RuntimeError("Supabase client unavailable; cannot approve")

    update_payload = {
        "status": "approved",
        "approved_by": approved_by,
        "approved_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    if rhodesli_photo_id is not None:
        update_payload["rhodesli_photo_id"] = rhodesli_photo_id

    # Atomic CAS via Supabase REST: filter on status='pending' so only the
    # winning racer's update flips the row. Race losers see 0 rows.
    result = (
        client.table("rhodes_inbox_entries")
        .update(update_payload)
        .eq("slug", slug)
        .eq("status", "pending")
        .execute()
    )

    if not result.data:
        # CAS lost — either someone else already approved, or the row doesn't
        # exist yet. Check whether the row even exists.
        check = (
            client.table("rhodes_inbox_entries")
            .select("status")
            .eq("slug", slug)
            .limit(1)
            .execute()
        )
        if check.data:
            raise AlreadyApprovedError(
                f"slug {slug!r} is already in status={check.data[0].get('status')!r}"
            )
        # Row doesn't exist — must upsert first then retry. This handles the
        # "approve from list-view-only" case where the detail-view upsert hasn't
        # fired yet. List the entry from filesystem to populate.
        post = _read_post_json(slug, "pending")
        if post is None:
            raise FileNotFoundError(f"no pending entry for slug={slug!r}")
        _upsert_inbox_row_for_pending(slug, post)
        # Retry the CAS now that the row exists
        result = (
            client.table("rhodes_inbox_entries")
            .update(update_payload)
            .eq("slug", slug)
            .eq("status", "pending")
            .execute()
        )
        if not result.data:
            raise RuntimeError(f"CAS retry failed for slug={slug!r}")

    # Filesystem move (POSIX atomic same-filesystem rename)
    src = _rhodes_wiki_inbox_root() / "pending" / slug
    dst = _rhodes_wiki_inbox_root() / "approved" / slug
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.replace(src, dst)
        except OSError as exc:
            logger.error(
                "Supabase approved %s but filesystem move failed: %s. "
                "Reconcile via scripts/rhodes_inbox_reconcile.py.",
                slug, exc,
            )
            raise
    elif dst.exists():
        logger.info("filesystem already at approved/%s (idempotent retry)", slug)
    else:
        # Both src and dst missing — unusual; log warning but proceed
        logger.warning(
            "Supabase approved %s but no filesystem entry found in pending/ or approved/",
            slug,
        )

    # Audit log (best-effort, fire-and-forget)
    try:
        from app.audit import _log_audit
        _log_audit(
            action="rhodes_inbox.approve",
            entity_id=slug,
            user_email=approved_by,
            new_value={"status": "approved", "rhodesli_photo_id": rhodesli_photo_id},
        )
    except Exception:  # noqa: BLE001
        logger.exception("audit_log write failed for rhodes_inbox.approve %s", slug)


def mark_rejected(slug: str, *, rejected_by: str, reason: str) -> None:
    """Atomic-CAS rejection. Same ordering as mark_approved.

    Caps reason at 4096 chars per schema CHECK constraint (Codex P3-B).
    """
    _validate_slug(slug)
    reason = (reason or "")[:4096]

    client = _supabase_client()
    if not client:
        raise RuntimeError("Supabase client unavailable; cannot reject")

    update_payload = {
        "status": "rejected",
        "rejection_reason": reason,
        "approved_by": rejected_by,  # reuse approved_by as actor; approved_at left null
        "approved_at": _now_iso(),
        "updated_at": _now_iso(),
    }

    result = (
        client.table("rhodes_inbox_entries")
        .update(update_payload)
        .eq("slug", slug)
        .eq("status", "pending")
        .execute()
    )

    if not result.data:
        check = (
            client.table("rhodes_inbox_entries")
            .select("status")
            .eq("slug", slug)
            .limit(1)
            .execute()
        )
        if check.data:
            raise AlreadyRejectedError(
                f"slug {slug!r} is already in status={check.data[0].get('status')!r}"
            )
        # Row doesn't exist yet — upsert first
        post = _read_post_json(slug, "pending")
        if post is None:
            raise FileNotFoundError(f"no pending entry for slug={slug!r}")
        _upsert_inbox_row_for_pending(slug, post)
        result = (
            client.table("rhodes_inbox_entries")
            .update(update_payload)
            .eq("slug", slug)
            .eq("status", "pending")
            .execute()
        )
        if not result.data:
            raise RuntimeError(f"CAS retry failed for slug={slug!r}")

    # Filesystem move
    src = _rhodes_wiki_inbox_root() / "pending" / slug
    dst = _rhodes_wiki_inbox_root() / "rejected" / slug
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.replace(src, dst)
        except OSError as exc:
            logger.error(
                "Supabase rejected %s but filesystem move failed: %s.",
                slug, exc,
            )
            raise
    elif dst.exists():
        logger.info("filesystem already at rejected/%s (idempotent retry)", slug)

    # Audit
    try:
        from app.audit import _log_audit
        _log_audit(
            action="rhodes_inbox.reject",
            entity_id=slug,
            user_email=rejected_by,
            new_value={"status": "rejected", "reason": reason[:200]},
        )
    except Exception:  # noqa: BLE001
        logger.exception("audit_log write failed for rhodes_inbox.reject %s", slug)


def link_rhodesli_photo(slug: str, rhodesli_photo_id: str) -> None:
    """After upload completes, link the new photo_id back to the inbox row."""
    _validate_slug(slug)
    if not rhodesli_photo_id:
        return
    client = _supabase_client()
    if not client:
        return
    client.table("rhodes_inbox_entries").update({
        "rhodesli_photo_id": rhodesli_photo_id,
        "updated_at": _now_iso(),
    }).eq("slug", slug).execute()


# ---------------------------------------------------------------------------
# Kinship triples cache (Codex P1-7)
# ---------------------------------------------------------------------------

def kinship_triples_for(slug: str, *, state: str = "pending") -> list[dict]:
    """Return cached kinship triples; compute + cache on first request.

    Cached in `rhodes_inbox_entries.kinship_triples_json`. If the column
    is null, computes via `app.extract_kinship.extract_kinship_from_post`,
    upserts the cache, returns the result.
    """
    _validate_slug(slug)

    client = _supabase_client()
    if client:
        cached = (
            client.table("rhodes_inbox_entries")
            .select("kinship_triples_json")
            .eq("slug", slug)
            .limit(1)
            .execute()
        )
        if cached.data and cached.data[0].get("kinship_triples_json") is not None:
            data = cached.data[0]["kinship_triples_json"]
            if isinstance(data, list):
                return data
            # Tolerate JSON-string-encoded form
            try:
                parsed = json.loads(data) if isinstance(data, str) else data
                if isinstance(parsed, list):
                    return parsed
            except (TypeError, json.JSONDecodeError):
                pass

    # Compute fresh
    post = _read_post_json(slug, state)
    if post is None:
        return []
    from app.extract_kinship import extract_kinship_from_post
    triples = [t.to_dict() for t in extract_kinship_from_post(post)]

    # Cache (best-effort)
    if client:
        try:
            # Upsert row first if it doesn't exist
            _upsert_inbox_row_for_pending(slug, post)
            client.table("rhodes_inbox_entries").update({
                "kinship_triples_json": triples,
                "updated_at": _now_iso(),
            }).eq("slug", slug).execute()
        except Exception:  # noqa: BLE001
            logger.exception("kinship cache write failed for %s", slug)

    return triples
