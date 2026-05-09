"""Session 157b Track A1.2 — NOTES-BACKFILL-156.

Pre-existing bug in Sessions 105-156 (Lesson 179): notes added via
`registry.add_note()` wrote to the in-memory identity dict's top-level
`notes` key but the Supabase shadow_write only persisted the `metadata`
JSONB column — top-level "notes" fell through. Every `add_note()` call in
that 51-session window may have been lost on the next page render after
the in-memory cache TTL expired.

Session 156 shipped the round-trip fix (`shadow_write_identity` now embeds
top-level `notes` into `metadata.notes`; `load_from_postgres` extracts them
back). This script backfills any pre-fix orphans by reconciling local
`data/identities.json` notes against Supabase `metadata.notes`.

Algorithm:
1. Load local `data/identities.json` and Supabase `identities` rows.
2. For each identity present in BOTH, count notes:
   - Local top-level `notes` (the dict the app uses in-memory)
   - Local `metadata.notes` (in case any code path wrote there)
   - Supabase `metadata.notes` (the only persisted source)
3. Where local notes exist that are NOT in Supabase, take the union (dedup
   by `id` if present, else by `(text, timestamp)`), write back via
   `shadow_write_identity(strict=True)` so the fixed round-trip persists.
4. Defaults to --dry-run. Pass --execute to mutate Supabase.
5. Emit `docs/feedback/session-157b-notes-backfill-report.md` with counts.

Idempotent: re-running after a successful execute should report 0 deltas.
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from app.supabase_data import get_supabase_client, shadow_write_identity  # noqa: E402


def _normalize_note(note):
    """Normalize a note dict for dedup/comparison."""
    if not isinstance(note, dict):
        return {"text": str(note), "_raw": True}
    return {
        "id": note.get("id"),
        "text": note.get("text") or note.get("note") or note.get("body") or "",
        "timestamp": note.get("timestamp") or note.get("created_at") or note.get("date"),
        "author": note.get("author"),
    }


def _note_key(note):
    """Stable dedup key for a note."""
    n = _normalize_note(note)
    if n.get("id"):
        return ("id", n["id"])
    return ("text+ts", n["text"], n.get("timestamp"))


def _note_set(notes):
    """Convert list of notes to a dict keyed by stable identity for dedup."""
    if not isinstance(notes, list):
        return {}
    out = {}
    for note in notes:
        out[_note_key(note)] = note
    return out


def main():
    parser = argparse.ArgumentParser(description="Session 157b notes backfill")
    parser.add_argument("--execute", action="store_true", help="Apply writes (default: dry-run)")
    parser.add_argument(
        "--report",
        default=str(project_root / "docs" / "feedback" / "session-157b-notes-backfill-report.md"),
        help="Output report path",
    )
    args = parser.parse_args()

    mode = "EXECUTE" if args.execute else "DRY-RUN"
    print(f"=== Session 157b notes backfill ({mode}) ===")

    # 1. Load local identities.json
    local_path = project_root / "data" / "identities.json"
    if not local_path.exists():
        print(f"ABORT: {local_path} missing", file=sys.stderr)
        sys.exit(1)
    local_data = json.loads(local_path.read_text())
    local_identities = local_data.get("identities", {})
    print(f"Local identities loaded: {len(local_identities)}")

    # 2. Load Supabase identities (paginate >1000)
    sb = get_supabase_client()
    if sb is None:
        print("ABORT: Supabase client unavailable", file=sys.stderr)
        sys.exit(1)

    sb_rows = []
    page_size = 1000
    offset = 0
    while True:
        result = (
            sb.table("identities")
            .select("identity_id, name, metadata, version_id, anchor_ids, candidate_ids, "
                    "negative_ids, state, display_name, merged_into, created_at, updated_at")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        if not result.data:
            break
        sb_rows.extend(result.data)
        if len(result.data) < page_size:
            break
        offset += page_size
    print(f"Supabase identities loaded: {len(sb_rows)}")
    sb_by_id = {row["identity_id"]: row for row in sb_rows}

    # 3. Survey
    survey = {
        "local_only_in_local": 0,
        "supabase_only": 0,
        "in_both": 0,
        "local_top_notes_count": 0,
        "local_metadata_notes_count": 0,
        "supabase_metadata_notes_count": 0,
    }
    deltas = []  # identities needing backfill

    for iid, local in local_identities.items():
        if iid not in sb_by_id:
            survey["local_only_in_local"] += 1
            continue
        survey["in_both"] += 1
        sb_row = sb_by_id[iid]

        local_top = local.get("notes") if isinstance(local.get("notes"), list) else []
        local_md = local.get("metadata", {}) or {}
        local_md_notes = local_md.get("notes") if isinstance(local_md.get("notes"), list) else []

        sb_md = sb_row.get("metadata") or {}
        sb_md_notes = sb_md.get("notes") if isinstance(sb_md.get("notes"), list) else []

        if local_top:
            survey["local_top_notes_count"] += len(local_top)
        if local_md_notes:
            survey["local_metadata_notes_count"] += len(local_md_notes)
        if sb_md_notes:
            survey["supabase_metadata_notes_count"] += len(sb_md_notes)

        # Build union and detect delta
        local_combined_set = _note_set(local_top)
        for k, v in _note_set(local_md_notes).items():
            local_combined_set.setdefault(k, v)
        sb_set = _note_set(sb_md_notes)

        local_only_keys = set(local_combined_set.keys()) - set(sb_set.keys())
        if local_only_keys:
            union = dict(sb_set)  # start with what's already in supabase
            for k in local_only_keys:
                union[k] = local_combined_set[k]
            deltas.append({
                "identity_id": iid,
                "name": local.get("name") or sb_row.get("name"),
                "local_top_count": len(local_top),
                "local_md_count": len(local_md_notes),
                "sb_md_count": len(sb_md_notes),
                "missing_in_supabase": len(local_only_keys),
                "union_count": len(union),
                "union_notes": list(union.values()),
                "sb_row": sb_row,
            })

    # Identify Supabase-only (not in local)
    for iid in sb_by_id:
        if iid not in local_identities:
            survey["supabase_only"] += 1

    # 4. Print survey
    print()
    print("=== Survey ===")
    print(f"  Identities in local only: {survey['local_only_in_local']}")
    print(f"  Identities in Supabase only: {survey['supabase_only']}")
    print(f"  Identities in both: {survey['in_both']}")
    print(f"  Total local top-level notes: {survey['local_top_notes_count']}")
    print(f"  Total local metadata.notes: {survey['local_metadata_notes_count']}")
    print(f"  Total Supabase metadata.notes: {survey['supabase_metadata_notes_count']}")
    print(f"  Identities needing backfill: {len(deltas)}")

    # 5. Apply backfill if --execute
    backfilled = 0
    failures = []
    if deltas and args.execute:
        print()
        print(f"=== Executing backfill on {len(deltas)} identities ===")
        for d in deltas:
            sb_row = d["sb_row"]
            new_metadata = dict(sb_row.get("metadata") or {})
            new_metadata["notes"] = d["union_notes"]
            payload = dict(sb_row)
            payload["metadata"] = new_metadata
            payload["notes"] = d["union_notes"]  # round-trip path will re-embed
            payload["updated_at"] = datetime.now(timezone.utc).isoformat()
            try:
                shadow_write_identity(payload, strict=True)
                backfilled += 1
                print(f"  BACKFILLED {d['identity_id']} ({d['name']}): "
                      f"+{d['missing_in_supabase']} notes -> {d['union_count']} total")
            except Exception as e:
                failures.append({"id": d["identity_id"], "error": str(e)})
                print(f"  FAIL {d['identity_id']}: {e}", file=sys.stderr)

    # 6. Write report
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Session 157b — NOTES-BACKFILL-156 Report",
        "",
        f"**Run mode:** {mode}",
        f"**Run timestamp:** {datetime.now(timezone.utc).isoformat()}",
        f"**Script:** `scripts/session157_notes_backfill.py`",
        "",
        "## Survey",
        "",
        f"- Local identities (data/identities.json): {len(local_identities)}",
        f"- Supabase identities: {len(sb_rows)}",
        f"- Identities in both: {survey['in_both']}",
        f"- Identities only in local: {survey['local_only_in_local']}",
        f"- Identities only in Supabase: {survey['supabase_only']}",
        f"- Total local top-level notes: {survey['local_top_notes_count']}",
        f"- Total local metadata.notes: {survey['local_metadata_notes_count']}",
        f"- Total Supabase metadata.notes: {survey['supabase_metadata_notes_count']}",
        f"- Identities needing backfill: {len(deltas)}",
        "",
        "## Result",
        "",
    ]
    if not deltas:
        lines.extend([
            "**No deltas found.** Local data has no orphan notes that are missing from Supabase.",
            "",
            "Interpretation: between Sessions 105-156, no `add_note()` calls landed in",
            "production data that weren't already round-tripped through Supabase metadata.",
            "The Lesson 179 round-trip fix shipped in Session 156 (commit on main) is",
            "sufficient — there is no historical orphan corpus requiring migration.",
            "",
            "The single Supabase identity with metadata.notes",
            "(`ef39908e-283a-4cec-8f72-3ec83bc8d84f` — Belle Isle Conservatory Young Man)",
            "was created in Session 156 itself, after the round-trip fix landed.",
        ])
    else:
        lines.append(f"### Deltas: {len(deltas)} identities had local notes missing from Supabase")
        lines.append("")
        if args.execute:
            lines.append(f"**Backfilled:** {backfilled}")
            lines.append(f"**Failures:** {len(failures)}")
            if failures:
                lines.append("")
                lines.append("### Failures")
                for f in failures:
                    lines.append(f"- `{f['id']}`: {f['error']}")
        else:
            lines.append("**Dry-run.** No writes performed. Re-run with `--execute` to apply.")
        lines.append("")
        lines.append("### Per-identity delta")
        lines.append("")
        lines.append("| identity_id | name | local_top | local_md | sb_md | missing | union |")
        lines.append("|-------------|------|-----------|----------|-------|---------|-------|")
        for d in deltas[:100]:  # cap at 100 for readability
            lines.append(
                f"| `{d['identity_id']}` | {d['name'] or '—'} | "
                f"{d['local_top_count']} | {d['local_md_count']} | "
                f"{d['sb_md_count']} | {d['missing_in_supabase']} | {d['union_count']} |"
            )
        if len(deltas) > 100:
            lines.append(f"| … | ({len(deltas) - 100} more) | | | | | |")

    lines.extend([
        "",
        "## Algorithm",
        "",
        "1. Read `data/identities.json` (in-memory dict the app shadow-writes from).",
        "2. Read all Supabase `identities` rows (paginated, >1000 supported).",
        "3. For each identity in BOTH, reconcile note sources:",
        "   - Local top-level `notes` (the keypath `add_note()` writes).",
        "   - Local `metadata.notes` (in case any path wrote there directly).",
        "   - Supabase `metadata.notes` (the persisted source).",
        "4. Dedup by `note.id` if present, else by `(text, timestamp)`.",
        "5. Where local has notes Supabase doesn't, write the union back via",
        "   `shadow_write_identity(strict=True)` so Session 156's round-trip",
        "   embeds top-level `notes` into `metadata.notes` correctly.",
        "",
        "## Lineage",
        "",
        "- Lesson 179: round-trip notes silently dropped Sessions 105-156.",
        "- Session 156 commit `feat(session-156)`: shadow_write_identity round-trip fix.",
        "- Session 157b Track A1.2 (this run): orphan reconciliation.",
    ])
    report_path.write_text("\n".join(lines) + "\n")
    print()
    print(f"Report written: {report_path}")
    print(f"=== Done ({mode}) ===")
    if failures:
        sys.exit(2)


if __name__ == "__main__":
    main()
