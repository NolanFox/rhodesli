"""rhodes_inbox_entries ↔ filesystem reconciliation script (Session 161).

Supabase `rhodes_inbox_entries.status` is authoritative (AD-S161-6). The
filesystem (`~/rhodes-wiki/inbox/<state>/<slug>/`) mirrors it for offline-
readable provenance. They can drift if:
  - mark_approved succeeds at Supabase but crashes before filesystem move
  - mark_rejected succeeds at Supabase but crashes before filesystem move
  - Filesystem entry exists with no Supabase row (e.g. fresh capture by
    rhodes-wiki not yet seen by a rhodesli detail-view-load)
  - Supabase row exists but filesystem entry deleted manually

Usage::

    python -m scripts.rhodes_inbox_reconcile --dry-run   # report only
    python -m scripts.rhodes_inbox_reconcile --apply     # reconcile

The `--apply` path TRUSTS SUPABASE. It will:
  - Move filesystem entries to match the Supabase status
  - Create Supabase rows (status=pending) for orphan filesystem entries
  - Refuse to delete filesystem entries (admin must do that manually)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

# Load .env so SUPABASE_URL / SUPABASE_KEY are visible
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from app.rhodes_inbox import (
    _SLUG_PATTERN,
    _rhodes_wiki_inbox_root,
    _supabase_client,
    is_rhodes_wiki_available,
)

logger = logging.getLogger(__name__)


def _filesystem_state(slug: str) -> str | None:
    """Return the filesystem state for slug ('pending'|'approved'|'rejected') or None if absent."""
    inbox_root = _rhodes_wiki_inbox_root()
    for state in ("pending", "approved", "rejected"):
        if (inbox_root / state / slug).is_dir():
            return state
    return None


def _scan_filesystem() -> dict[str, str]:
    """Return {slug: state} for every entry on the filesystem."""
    out: dict[str, str] = {}
    inbox_root = _rhodes_wiki_inbox_root()
    for state in ("pending", "approved", "rejected"):
        state_dir = inbox_root / state
        if not state_dir.is_dir():
            continue
        for slug_dir in state_dir.iterdir():
            if not slug_dir.is_dir():
                continue
            slug = slug_dir.name
            if not _SLUG_PATTERN.fullmatch(slug):
                continue
            if slug in out:
                logger.warning(
                    "slug %s exists in multiple states (%s and %s) — keeping latest",
                    slug, out[slug], state,
                )
            out[slug] = state
    return out


def _scan_supabase() -> dict[str, str]:
    """Return {slug: status} from rhodes_inbox_entries."""
    client = _supabase_client()
    if not client:
        raise RuntimeError("Supabase client unavailable")
    result = client.table("rhodes_inbox_entries").select("slug,status").execute()
    return {row["slug"]: row["status"] for row in (result.data or [])}


def detect_drift() -> dict:
    """Returns a dict with categorized drift cases:
        {
            "fs_only": [slug, ...],      # FS has entry, Supabase has no row
            "sb_only": [(slug, status), ...],   # SB has row, FS has no entry
            "mismatch": [(slug, fs_state, sb_status), ...],
            "consistent": int,           # count of consistent slugs
        }
    """
    fs = _scan_filesystem()
    sb = _scan_supabase()

    fs_only = sorted(slug for slug in fs if slug not in sb)
    sb_only = sorted(
        (slug, status) for slug, status in sb.items() if slug not in fs
    )
    mismatch = sorted(
        (slug, fs[slug], sb[slug])
        for slug in fs
        if slug in sb and fs[slug] != sb[slug]
    )
    consistent = sum(1 for slug in fs if slug in sb and fs[slug] == sb[slug])

    return {
        "fs_only": fs_only,
        "sb_only": sb_only,
        "mismatch": mismatch,
        "consistent": consistent,
        "totals": {"fs": len(fs), "sb": len(sb)},
    }


def reconcile(drift: dict) -> dict:
    """Apply the drift fixes. Supabase wins on mismatch. Returns action counts."""
    client = _supabase_client()
    if not client:
        raise RuntimeError("Supabase client unavailable")
    inbox_root = _rhodes_wiki_inbox_root()
    actions = {"fs_moved": 0, "sb_created": 0, "fs_missing": 0}

    # Mismatch: trust Supabase, move filesystem
    for slug, fs_state, sb_status in drift["mismatch"]:
        src = inbox_root / fs_state / slug
        dst = inbox_root / sb_status / slug
        if not src.exists():
            actions["fs_missing"] += 1
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        os.replace(src, dst)
        actions["fs_moved"] += 1
        logger.info("moved %s/%s -> %s/%s", fs_state, slug, sb_status, slug)

    # fs_only: filesystem entry but no Supabase row → create row at the
    # filesystem's state. We DON'T re-summarize — we only insert minimal
    # provenance so the row exists; admin can re-render detail view to enrich.
    for slug in drift["fs_only"]:
        fs_state = _filesystem_state(slug)
        if not fs_state:
            continue
        post_json_path = inbox_root / fs_state / slug / "post.json"
        if not post_json_path.is_file():
            continue
        try:
            post = json.loads(post_json_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        client.table("rhodes_inbox_entries").upsert({
            "slug": slug,
            "fb_post_id": post.get("fb_post_id") or "",
            "fb_post_url": post.get("fb_post_url") or "",
            "fb_author_name": (post.get("post_author") or {}).get("name"),
            "fb_author_id": (post.get("post_author") or {}).get("fb_id"),
            "captured_at": post.get("captured_at"),
            "captured_by": post.get("captured_by"),
            "contract_version": post.get("contract_version"),
            "parser_version": post.get("parser_version"),
            "comments_count": int(post.get("comments_count_extracted") or 0),
            "status": fs_state,
        }, on_conflict="slug", ignore_duplicates=True).execute()
        actions["sb_created"] += 1
        logger.info("created Supabase row for %s (status=%s)", slug, fs_state)

    # sb_only: never auto-delete or auto-create filesystem entries (admin
    # decision). Just report.
    return actions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Reconcile rhodes_inbox_entries (Supabase) against the local "
            "rhodes-wiki inbox/ filesystem. Supabase is authoritative."
        )
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Report drift only, do not modify anything (default).")
    parser.add_argument("--apply", action="store_true",
                        help="Apply reconciliation: Supabase wins on mismatch; "
                             "filesystem-only entries get Supabase rows created.")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if not is_rhodes_wiki_available():
        print("ERROR: rhodes-wiki vault not available (production gate or missing path)", file=sys.stderr)
        return 2

    print("Scanning rhodes_inbox_entries + filesystem...")
    drift = detect_drift()
    print(f"\nConsistent: {drift['consistent']} entries")
    print(f"Filesystem total: {drift['totals']['fs']}; Supabase total: {drift['totals']['sb']}")

    if drift["mismatch"]:
        print(f"\n⚠️  MISMATCH ({len(drift['mismatch'])} entries — Supabase != filesystem):")
        for slug, fs_state, sb_status in drift["mismatch"]:
            print(f"  {slug}: filesystem={fs_state}, supabase={sb_status}")

    if drift["fs_only"]:
        print(f"\n⚠️  FILESYSTEM-ONLY ({len(drift['fs_only'])} entries — no Supabase row):")
        for slug in drift["fs_only"]:
            print(f"  {slug}")

    if drift["sb_only"]:
        print(f"\n⚠️  SUPABASE-ONLY ({len(drift['sb_only'])} entries — no filesystem):")
        for slug, status in drift["sb_only"]:
            print(f"  {slug} (status={status})")

    total_drift = len(drift["mismatch"]) + len(drift["fs_only"]) + len(drift["sb_only"])
    if total_drift == 0:
        print("\n✓ No drift detected.")
        return 0

    if args.apply:
        print("\n--- APPLYING reconciliation (Supabase wins) ---")
        actions = reconcile(drift)
        print(f"  filesystem moves:       {actions['fs_moved']}")
        print(f"  Supabase rows created:  {actions['sb_created']}")
        print(f"  filesystem entries missing: {actions['fs_missing']}")
        if drift["sb_only"]:
            print(f"  (Supabase-only entries left as-is; admin must investigate)")
        return 0
    else:
        print("\nDry-run mode (default). Pass --apply to reconcile.")
        return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
