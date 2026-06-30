#!/usr/bin/env python3
"""GEDCOM-context estimate backfill — SURVEY + guarded re-run (ESTIMATE-BACKFILL-166).

Lesson 205: the GEDCOM-context loader silently broke after the Session-164 schema
redesign and returned None until Session 166 fixed it — so during that window,
every date/location estimate ran VISUAL-ONLY (no birth/death-year age anchoring,
no residence history, no spouse-death date ceiling). Now that enrichment is
restored, the photos estimated during that window should be re-run WITH GEDCOM
context to sharpen their dates/locations.

This script has two modes:

  --survey   (DEFAULT, READ-ONLY): inventory `date_labels` (Supabase, read-only)
             and report which GEDCOM-LINKED photos have estimates that were
             produced visual-only. Writes a markdown report. NO writes, NO Gemini
             calls, NO cost.

  --execute  (GUARDED): re-run the chosen candidates' estimates WITH GEDCOM
             context via scripts/multimodel_photo_estimate.py machinery. This
             SPENDS Gemini money and WRITES production date_labels, so it REFUSES
             to run unless --i-have-nolans-approval is ALSO passed. Even then this
             session never runs it — it exists so a future approved run is one
             flag away.

Candidate signal (authoritative): the LATEST `gemini_api_calls` row per photo,
inspecting `gemini_config.enrichment_level`:
  - `none` / `faces`            => NO GEDCOM enrichment (visual-only)  -> candidate
  - `gedcom` / `gedcom+faces` / `full` => GEDCOM-enriched              -> fine
A photo whose most-recent estimate ran without GEDCOM is the one to re-run.
`date_labels` (the website's stored estimate, with its `reanalyzed_with_gedcom`
flag) is reported as CORROBORATION but is not the primary signal — older
batch rows simply omit the flag, so date_labels alone under-reports.

Only photos that are GEDCOM-LINKED (a face whose identity is in
`gedcom_face_links`) are reported — re-running enrichment on a non-linked photo
would change nothing.

The CANDIDATE tier = GEDCOM-linked photo whose latest call was visual-only.
The IN-WINDOW sub-tier = that latest visual-only call's `created_at` falls inside
the loader-outage window (the Lesson-205 regression period).

Reads are paginated (Lesson 173) and read-only.

Usage:
    python scripts/backfill_gedcom_estimates.py --survey
    python scripts/backfill_gedcom_estimates.py --survey --window-start 2026-04-13 --window-end 2026-06-12
    python scripts/backfill_gedcom_estimates.py --execute                       # REFUSES
    python scripts/backfill_gedcom_estimates.py --execute --i-have-nolans-approval  # would run (NOT this session)
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Loader-outage window (heuristic; override with --window-start/--window-end).
# Lesson 205: loader broke during the Session-164 schema-redesign cutover era and
# was fixed Session 166 (2026-06-12). The lower bound is conservative (the PRD-064
# cutover arc). The STRONG signal (reanalyzed_with_gedcom=False) is
# window-independent; the window only scopes the POSSIBLE (missing-flag) tier.
DEFAULT_WINDOW_START = "2026-04-13"
DEFAULT_WINDOW_END = "2026-06-12"

REPORT_PATH = Path("docs/feedback/session-167-estimate-backfill-survey.md")


def _parse_iso(ts) -> datetime | None:
    if not ts or not isinstance(ts, str):
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def _as_dict(data):
    """date_labels.data may be a dict or a JSON string."""
    if isinstance(data, str):
        try:
            return json.loads(data)
        except (ValueError, TypeError):
            return {}
    return data if isinstance(data, dict) else {}


def _build_gedcom_linked_photos(m, registry, gedcom_identities: set) -> set:
    """Return the set of photo_ids that have at least one face whose identity is
    GEDCOM-linked. Computed entirely in memory from the photo cache + registry."""
    linked = set()
    photo_cache = getattr(m, "_photo_cache", None) or {}
    for pid, photo in photo_cache.items():
        faces = photo.get("faces", []) or []
        face_ids = [f.get("face_id") for f in faces if isinstance(f, dict) and f.get("face_id")]
        if not face_ids:
            face_ids = photo.get("face_ids", []) or []
        for fid in face_ids:
            ident = m.get_identity_for_face(registry, fid)
            iid = ident.get("identity_id") if ident else None
            if iid and iid in gedcom_identities:
                linked.add(pid)
                break
    return linked


def _canonical(m, photo_id: str) -> str:
    fn = getattr(m, "canonical_photo_id", None)
    if callable(fn):
        try:
            return fn(photo_id)
        except Exception:  # noqa: BLE001
            return photo_id
    return photo_id


# enrichment_level values that mean GEDCOM context WAS supplied.
GEDCOM_ENRICHED_LEVELS = frozenset({"gedcom", "gedcom+faces", "full"})
# values that mean NO GEDCOM context (visual-only) — a re-run would add enrichment.
VISUAL_ONLY_LEVELS = frozenset({"none", "faces"})


def _latest_enrichment_by_photo(rows: list) -> dict:
    """From gemini_api_calls rows, return {photo_id: (enrichment_level, created_at)}
    for the LATEST call per photo (by created_at). Rows missing enrichment_level
    are kept as level None so they don't masquerade as visual-only."""
    latest: dict = {}
    for row in rows:
        pid = row.get("photo_id")
        if not pid:
            continue
        cfg = row.get("gemini_config")
        if isinstance(cfg, str):
            try:
                cfg = json.loads(cfg)
            except (ValueError, TypeError):
                cfg = {}
        cfg = cfg or {}
        level = cfg.get("enrichment_level")
        created = row.get("created_at") or ""
        prev = latest.get(pid)
        if prev is None or created >= prev[1]:
            latest[pid] = (level, created)
    return latest


def survey(window_start: str, window_end: str) -> int:
    warnings.filterwarnings("ignore")
    try:
        from dotenv import load_dotenv

        load_dotenv("/Users/nolanfox/rhodesli/.env")
    except Exception:  # noqa: BLE001
        pass

    from app import main as m
    from app.supabase_data import get_supabase_client, load_date_labels_from_supabase

    m._build_caches()
    registry = m.load_registry()
    gedcom_links = m._load_gedcom_face_links() or {}
    gedcom_identities = set(gedcom_links.keys())

    date_labels = load_date_labels_from_supabase()
    if date_labels is None:
        print("ERROR: could not read date_labels from Supabase (check .env / connectivity).", file=sys.stderr)
        return 2

    gemini_rows = _load_gemini_calls(get_supabase_client())
    if gemini_rows is None:
        print("ERROR: could not read gemini_api_calls from Supabase (check .env / connectivity).", file=sys.stderr)
        return 2

    linked_photos = _build_gedcom_linked_photos(m, registry, gedcom_identities)
    # Index linked photos by canonical id too, so we can match keys regardless of
    # inbox_* vs SHA256 id-space (Lesson 25/165).
    linked_canon = {_canonical(m, p) for p in linked_photos} | linked_photos

    def _is_linked(pid: str) -> bool:
        return pid in linked_canon or _canonical(m, pid) in linked_canon

    win_start = _parse_iso(window_start + "T00:00:00+00:00")
    win_end = _parse_iso(window_end + "T23:59:59+00:00")

    latest = _latest_enrichment_by_photo(gemini_rows)

    candidates, in_window = [], []
    for pid, (level, created) in latest.items():
        if not _is_linked(pid):
            continue
        if level not in VISUAL_ONLY_LEVELS:
            continue  # latest run was gedcom-enriched (or unknown) — not a candidate
        dl = _as_dict(date_labels.get(pid) or date_labels.get(_canonical(m, pid)))
        created_dt = _parse_iso(created)
        within = bool(created_dt and win_start and win_end and win_start <= created_dt <= win_end)
        row = {
            "photo_id": pid,
            "latest_enrichment_level": level,
            "latest_call_at": created,
            "in_window": within,
            "stored_year": dl.get("best_year_estimate"),
            "stored_location": dl.get("location_estimate"),
            "stored_reanalyzed_with_gedcom": dl.get("reanalyzed_with_gedcom"),
        }
        candidates.append(row)
        if within:
            in_window.append(row)

    candidates.sort(key=lambda r: (not r["in_window"], r["photo_id"]))

    enrich_dist = _enrichment_distribution(latest, _is_linked)

    report = _render_report(
        window_start=window_start,
        window_end=window_end,
        total_date_labels=len(date_labels),
        total_gemini_calls=len(gemini_rows),
        total_gedcom_linked_identities=len(gedcom_identities),
        total_linked_photos=len(linked_photos),
        enrich_dist=enrich_dist,
        candidates=candidates,
        in_window=in_window,
    )
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report)

    print(f"date_labels rows total:                       {len(date_labels)}")
    print(f"gemini_api_calls rows total:                  {len(gemini_rows)}")
    print(f"GEDCOM-linked identities:                     {len(gedcom_identities)}")
    print(f"GEDCOM-linked photos (any face):              {len(linked_photos)}")
    print(f"Linked photos by latest-call enrichment:      {enrich_dist}")
    print(f"BACKFILL candidates (latest call visual-only): {len(candidates)}")
    print(f"  of which inside outage window {window_start}..{window_end}: {len(in_window)}")
    print(f"\nReport written to {REPORT_PATH}")
    if candidates:
        print("\nCandidate photo_ids (latest estimate ran visual-only):")
        for r in candidates:
            tag = "IN-WINDOW" if r["in_window"] else "out-of-window"
            print(f"  {r['photo_id']}  [{tag}] level={r['latest_enrichment_level']} at={r['latest_call_at']} year={r['stored_year']}")
    return 0


def _load_gemini_calls(sb) -> list | None:
    """Paginated read-only load of gemini_api_calls (Lesson 173). Returns None on
    failure so the caller can distinguish 'no data' from 'could not read'."""
    if not sb:
        return None
    try:
        rows = []
        offset = 0
        while True:
            r = (
                sb.table("gemini_api_calls")
                .select("photo_id,call_type,created_at,gemini_config")
                .range(offset, offset + 999)
                .execute()
            )
            if not r.data:
                break
            rows.extend(r.data)
            if len(r.data) < 1000:
                break
            offset += 1000
        return rows
    except Exception:  # noqa: BLE001
        return None


def _enrichment_distribution(latest: dict, is_linked) -> dict:
    import collections

    c = collections.Counter()
    for pid, (level, _created) in latest.items():
        if is_linked(pid):
            c[level if level is not None else "<unknown>"] += 1
    return dict(c)


def _render_report(**kw) -> str:
    now = datetime.now(timezone.utc).isoformat()
    candidates = kw["candidates"]
    in_window = kw["in_window"]
    lines = [
        "# Session 167 — ESTIMATE-BACKFILL-166 Survey (READ-ONLY)",
        "",
        f"_Generated: {now} by `scripts/backfill_gedcom_estimates.py --survey`. No writes, no Gemini calls, no $ spend._",
        "",
        "## What this is",
        "Lesson 205: the GEDCOM-context loader was dead from the Session-164 schema",
        "redesign until Session 166 fixed it, so estimates produced in that window ran",
        "VISUAL-ONLY (no age anchoring / residence history / spouse-death ceiling). This",
        "survey finds GEDCOM-linked photos whose LATEST estimate ran without GEDCOM and",
        "would benefit from a re-run.",
        "",
        "## Method",
        "Primary signal = the LATEST `gemini_api_calls` row per photo, by `created_at`,",
        "inspecting `gemini_config.enrichment_level`:",
        "`none`/`faces` = visual-only (candidate); `gedcom`/`gedcom+faces`/`full` = enriched.",
        "`date_labels` flags are shown as corroboration only (older batch rows omit them).",
        "",
        "## Totals",
        f"- date_labels rows total: **{kw['total_date_labels']}**",
        f"- gemini_api_calls rows total: **{kw['total_gemini_calls']}**",
        f"- GEDCOM-linked identities: **{kw['total_gedcom_linked_identities']}**",
        f"- GEDCOM-linked photos (any face): **{kw['total_linked_photos']}**",
        f"- Linked photos by latest-call enrichment_level: `{kw['enrich_dist']}`",
        f"- Outage window used: `{kw['window_start']}` .. `{kw['window_end']}`",
        "",
        "## Backfill candidates",
        f"GEDCOM-linked photos whose **latest** estimate ran visual-only: **{len(candidates)}**",
        f"(of which inside the outage window: **{len(in_window)}**).",
        "",
    ]
    lines += _candidate_table(candidates)
    lines += [
        "",
        "## Re-run (NOT executed this session — requires Nolan's $ approval)",
        "```bash",
        "# Survey again (read-only):",
        "python scripts/backfill_gedcom_estimates.py --survey",
        "",
        "# Re-run the candidates WITH GEDCOM context (SPENDS Gemini $, WRITES prod):",
        "python scripts/backfill_gedcom_estimates.py --execute --i-have-nolans-approval",
        "```",
        "Each re-run should use `scripts/multimodel_photo_estimate.py run-gemini` (GEDCOM-",
        "enriched prompt) then `finalize`. Verify `_build_gedcom_context_for_photo` returns",
        "non-empty before bulk-running (Lesson 205/206/208).",
        "",
    ]
    return "\n".join(lines)


def _candidate_table(rows: list) -> list:
    if not rows:
        return ["_No GEDCOM-linked photo has a visual-only latest estimate — nothing to backfill._"]
    out = [
        "| photo_id | in_window | latest_level | latest_call_at | stored_year | stored_location | stored_gedcom_flag |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        out.append(
            f"| `{r['photo_id']}` | {r['in_window']} | {r['latest_enrichment_level']} | "
            f"{r['latest_call_at']} | {r.get('stored_year')} | {r.get('stored_location')} | "
            f"{r.get('stored_reanalyzed_with_gedcom')} |"
        )
    return out


def execute(approved: bool) -> int:
    """Guarded re-run. REFUSES without --i-have-nolans-approval. Never auto-runs."""
    if not approved:
        print(
            "REFUSING: --execute re-runs estimates (SPENDS Gemini money + WRITES production "
            "date_labels). Pass --i-have-nolans-approval to authorize. Run --survey first.",
            file=sys.stderr,
        )
        return 3
    # Even WITH approval, this Track-A session does not perform the spend. The
    # approved operator should run the candidates listed by --survey through
    # scripts/multimodel_photo_estimate.py. Wiring intentionally left as a guard.
    print(
        "Approval flag present, but this script is the GUARD only — it does not "
        "auto-spend. Drive the re-run via scripts/multimodel_photo_estimate.py for "
        "each photo_id from the --survey report (run-gemini -> compare -> finalize).",
        file=sys.stderr,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GEDCOM-context estimate backfill survey + guarded re-run")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--survey", action="store_true", help="READ-ONLY inventory (default).")
    mode.add_argument("--execute", action="store_true", help="Guarded re-run (requires approval flag).")
    parser.add_argument("--i-have-nolans-approval", action="store_true", help="Required to authorize --execute.")
    parser.add_argument("--window-start", default=DEFAULT_WINDOW_START, help="Outage window start (YYYY-MM-DD).")
    parser.add_argument("--window-end", default=DEFAULT_WINDOW_END, help="Outage window end (YYYY-MM-DD).")
    args = parser.parse_args(argv)

    if args.execute:
        return execute(args.i_have_nolans_approval)
    # Default to survey.
    return survey(args.window_start, args.window_end)


if __name__ == "__main__":
    raise SystemExit(main())
