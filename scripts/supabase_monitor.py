#!/usr/bin/env python3
"""Supabase health + project-status monitor with optional keep-alive.

OPS-002 / OD-015 / Lesson 200. A silent free-tier pause-or-over-quota took the
site down with no alert (Session 163). This script gives us a single command
that an external scheduler (cron or a Claude Code Remote routine) can run to
detect that failure mode early.

It checks TWO independent signals:

  1. **A fresh, unthrottled direct Supabase REST/Auth probe** — `GET
     {SUPABASE_URL}/auth/v1/health`. Under a DB-size over-quota restriction the
     Auth/REST services return 402 while the `db` service stays healthy (Lesson
     200), so this probe catches over-quota directly. Under inactivity pause the
     host NXDOMAINs (transport error). This is the PRIMARY reachability signal —
     it does its OWN request, so it is never masked by the in-app ping throttle.
  2. **The live app's `/health` endpoint `supabase` field** — the production
     process's own view. NOTE: that field is `_ping_supabase()`, throttled to
     once per hour, so it is usually `"skipped"` (a NO-SIGNAL value). This
     monitor therefore treats `"skipped"` as INCONCLUSIVE (never a pass, never an
     alert) — only a literal `"ok"` passes, and `"error:..."`/`"not_configured"`
     alert. (Codex P1, Session 167: a previous version treated `"skipped"` as
     healthy, which would have masked the exact over-quota failure it must catch.)
  3. **The Supabase Management API project status** — `status != ACTIVE_HEALTHY`
     catches an inactivity auto-pause (empty/paused project) BEFORE the public
     REST API even resolves.

If any signal is definitively unhealthy the script prints an `ALERT:` line to
stderr and exits non-zero (so a scheduler can page on the exit code). If NO
signal could be evaluated (all inconclusive — e.g. no creds locally and the app
reports `skipped`), it prints a `WARN:` line and exits 0 (no false page) but the
report makes the gap visible.

Optionally (`--keep-alive`) it runs a trivial `SELECT 1` via the Management API
SQL endpoint (which keeps working even under a 402 size restriction — Lesson 200)
to reset the inactivity-pause timer. The keep-alive is best-effort and never
changes data.

------------------------------------------------------------------------------
Usage
------------------------------------------------------------------------------
    python scripts/supabase_monitor.py --check                 # one-shot, exit 0/1
    python scripts/supabase_monitor.py --check --keep-alive    # + SELECT 1
    python scripts/supabase_monitor.py --check --json          # machine-readable
    python scripts/supabase_monitor.py --check --require-mgmt  # missing PAT => fail

Environment (loaded from the repo .env via python-dotenv):
    HEALTH_URL             default https://rhodesli.nolanandrewfox.com/health
    SUPABASE_ACCESS_TOKEN  Management API personal access token (sbp_...).
                           Without it, the project-status check is SKIPPED with a
                           warning (not a hard failure unless --require-mgmt).
    SUPABASE_PROJECT_REF   default fvynibivlphxwfowzkjl

------------------------------------------------------------------------------
Scheduling (DESIGN ONLY — this script does NOT install or enable any schedule)
------------------------------------------------------------------------------
cron (every 6h; the exit code drives the alert, logs capture the detail):

    0 */6 * * *  cd /Users/nolanfox/rhodesli && \
        venv/bin/python scripts/supabase_monitor.py --check --keep-alive \
        >> logs/supabase_monitor.log 2>&1 || /usr/local/bin/notify "Supabase ALERT"

Claude Code Remote routine (preferred — gets push/email on a noteworthy run):
    create_trigger(
        name="supabase-health-monitor",
        cron_expression="0 */6 * * *",
        prompt="Run `python scripts/supabase_monitor.py --check --keep-alive`. "
               "If it exits non-zero, summarize the ALERT line and notify Nolan.",
    )

Keep DB comfortably < 500 MB (target <= 300 MB post-Session-164), not at 92%.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

DEFAULT_HEALTH_URL = "https://rhodesli.nolanandrewfox.com/health"
DEFAULT_PROJECT_REF = "fvynibivlphxwfowzkjl"
MGMT_API_BASE = "https://api.supabase.com"

# /health `supabase` field. Only a live "ok" PASSES. "skipped" is the in-app
# once-per-hour ping throttle — a NO-SIGNAL value, treated as INCONCLUSIVE (not a
# pass; see Codex P1, Session 167). Everything else ("not_configured",
# "error:...") is a real problem and ALERTS.
HEALTHY_SUPABASE_FIELD_VALUES = frozenset({"ok"})
INCONCLUSIVE_SUPABASE_FIELD_VALUES = frozenset({"skipped"})

HEALTHY_PROJECT_STATUS = "ACTIVE_HEALTHY"


# --------------------------------------------------------------------------- #
# HTTP indirection (injectable for tests — pass any object with .get/.post that
# returns a response exposing .status_code and .json()). httpx.Client satisfies
# this contract.
# --------------------------------------------------------------------------- #
def _default_client():
    import httpx

    return httpx.Client(timeout=10.0)


# --------------------------------------------------------------------------- #
# Signal 1: the live app's /health endpoint
# --------------------------------------------------------------------------- #
def check_supabase_rest(supabase_url: str | None, anon_key: str | None, client) -> dict:
    """Fresh, unthrottled probe of the Supabase Auth/REST surface.

    GET {SUPABASE_URL}/auth/v1/health. A 200 PASSES; a 402 (over DB-size quota,
    Lesson 200) or any other non-200 FAILS; a transport error (NXDOMAIN from an
    inactivity pause) FAILS. Missing creds → SKIPPED (ok=None).

    This is the PRIMARY reachability signal because it makes its OWN request and
    is therefore never masked by the in-app once-per-hour ping throttle.
    """
    result = {"check": "supabase_rest", "ok": None, "http_status": None, "error": None}
    if not supabase_url or not anon_key:
        result["error"] = "SUPABASE_URL/SUPABASE_ANON_KEY not set — direct REST probe skipped"
        return result
    try:
        resp = client.get(
            f"{supabase_url.rstrip('/')}/auth/v1/health",
            headers={"apikey": anon_key},
        )
        result["http_status"] = resp.status_code
        if resp.status_code == 200:
            result["ok"] = True
        else:
            result["ok"] = False
            result["error"] = f"Supabase REST returned HTTP {resp.status_code}"
    except Exception as e:  # noqa: BLE001 — transport error (e.g. NXDOMAIN) = unhealthy
        result["ok"] = False
        result["error"] = f"{type(e).__name__}: {e}"
    return result


def check_health_endpoint(health_url: str, client) -> dict:
    """Fetch /health and inspect the `supabase` field.

    Returns a dict: ok (True pass / False alert / None inconclusive),
    supabase (str|None), http_status (int|None), error (str|None).
    Only a literal "ok" passes; "skipped" is inconclusive (ok=None).
    """
    result = {"check": "health_endpoint", "url": health_url, "ok": False, "supabase": None, "http_status": None, "error": None}
    try:
        resp = client.get(health_url)
        result["http_status"] = resp.status_code
        if resp.status_code != 200:
            result["error"] = f"health endpoint returned HTTP {resp.status_code}"
            return result
        body = resp.json()
        field = body.get("supabase")
        result["supabase"] = field
        if field in HEALTHY_SUPABASE_FIELD_VALUES:
            result["ok"] = True
        elif field in INCONCLUSIVE_SUPABASE_FIELD_VALUES:
            result["ok"] = None  # throttled no-signal — neither pass nor alert
            result["error"] = f"supabase field = {field!r} (throttled no-signal; see direct REST probe)"
        else:
            result["error"] = f"supabase field = {field!r}"
    except Exception as e:  # noqa: BLE001 — surface any transport/JSON error as a failed check
        result["error"] = f"{type(e).__name__}: {e}"
    return result


# --------------------------------------------------------------------------- #
# Signal 2: the Supabase Management API project status
# --------------------------------------------------------------------------- #
def check_project_status(token: str | None, project_ref: str, client, *, require: bool = False) -> dict:
    """GET /v1/projects/{ref} and inspect `status`.

    Without a token the check is SKIPPED (ok=None) unless require=True, in which
    case it is a hard failure (ok=False).
    """
    result = {"check": "project_status", "project_ref": project_ref, "ok": None, "status": None, "error": None}
    if not token:
        if require:
            result["ok"] = False
            result["error"] = "SUPABASE_ACCESS_TOKEN not set (--require-mgmt)"
        else:
            result["error"] = "SUPABASE_ACCESS_TOKEN not set — project-status check skipped"
        return result
    try:
        resp = client.get(
            f"{MGMT_API_BASE}/v1/projects/{project_ref}",
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code != 200:
            result["ok"] = False
            result["error"] = f"management API returned HTTP {resp.status_code}"
            return result
        status = resp.json().get("status")
        result["status"] = status
        result["ok"] = status == HEALTHY_PROJECT_STATUS
        if not result["ok"]:
            result["error"] = f"project status = {status!r} (expected {HEALTHY_PROJECT_STATUS})"
    except Exception as e:  # noqa: BLE001
        result["ok"] = False
        result["error"] = f"{type(e).__name__}: {e}"
    return result


# --------------------------------------------------------------------------- #
# Optional keep-alive: trivial SELECT 1 (never mutates)
# --------------------------------------------------------------------------- #
def keep_alive(token: str | None, project_ref: str, client) -> dict:
    """Run `SELECT 1` via the Management API SQL endpoint to reset the
    inactivity-pause timer. Works even under a 402 size restriction (Lesson 200).

    Best-effort: a failed keep-alive is reported but does NOT, by itself, set the
    overall alert (the two health signals above are the alert drivers).
    """
    result = {"check": "keep_alive", "ok": False, "error": None}
    if not token:
        result["error"] = "SUPABASE_ACCESS_TOKEN not set — keep-alive skipped"
        return result
    try:
        resp = client.post(
            f"{MGMT_API_BASE}/v1/projects/{project_ref}/database/query",
            headers={"Authorization": f"Bearer {token}"},
            json={"query": "SELECT 1"},
        )
        if resp.status_code in (200, 201):
            result["ok"] = True
        else:
            result["error"] = f"keep-alive query returned HTTP {resp.status_code}"
    except Exception as e:  # noqa: BLE001
        result["error"] = f"{type(e).__name__}: {e}"
    return result


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #
def run_monitor(
    *,
    health_url: str,
    token: str | None,
    project_ref: str,
    supabase_url: str | None = None,
    anon_key: str | None = None,
    do_keep_alive: bool = False,
    require_mgmt: bool = False,
    client=None,
) -> dict:
    """Run all checks. Returns a report dict with `alert`, `inconclusive`, `checks`.

    `alert` is True iff ANY health signal is definitively unhealthy (ok is False):
      - the direct Supabase REST probe failed, OR
      - the /health endpoint reported a bad `supabase` field, OR
      - the Management API project status != ACTIVE_HEALTHY (a None/skipped status
        does NOT alert unless require_mgmt forced it to False).
    The keep-alive result NEVER sets `alert`.

    `inconclusive` is True when no health signal could be affirmatively evaluated
    (every health check ok is None) — surfaced as a WARN, not an alert.
    """
    owns_client = client is None
    if owns_client:
        client = _default_client()
    try:
        checks = []
        rest = check_supabase_rest(supabase_url, anon_key, client)
        checks.append(rest)
        health = check_health_endpoint(health_url, client)
        checks.append(health)
        project = check_project_status(token, project_ref, client, require=require_mgmt)
        checks.append(project)
        if do_keep_alive:
            checks.append(keep_alive(token, project_ref, client))

        health_signals = [rest, health, project]
        alert = any(c["ok"] is False for c in health_signals)
        inconclusive = not alert and all(c["ok"] is None for c in health_signals)
        return {"alert": alert, "inconclusive": inconclusive, "checks": checks}
    finally:
        if owns_client:
            close = getattr(client, "close", None)
            if callable(close):
                close()


def _format_report(report: dict) -> str:
    lines = []
    if report["alert"]:
        prefix = "ALERT"
    elif report.get("inconclusive"):
        prefix = "WARN"
    else:
        prefix = "OK"
    for c in report["checks"]:
        ok = c.get("ok")
        mark = "PASS" if ok is True else ("SKIP" if ok is None else "FAIL")
        detail = c.get("error") or c.get("supabase") or c.get("status") or ""
        lines.append(f"  [{mark}] {c['check']}: {detail}".rstrip())
    header = f"{prefix}: supabase monitor"
    return header + "\n" + "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Supabase health + project-status monitor")
    parser.add_argument("--check", action="store_true", help="Run the one-shot health check (required).")
    parser.add_argument("--keep-alive", action="store_true", help="Also run a trivial SELECT 1 to prevent inactivity pause.")
    parser.add_argument("--json", action="store_true", help="Emit the report as JSON.")
    parser.add_argument("--require-mgmt", action="store_true", help="Treat a missing SUPABASE_ACCESS_TOKEN as a hard failure.")
    parser.add_argument("--health-url", default=None, help="Override HEALTH_URL.")
    args = parser.parse_args(argv)

    if not args.check:
        parser.error("--check is required (this is a one-shot monitor; no daemon mode)")

    # Load .env so SUPABASE_* are available locally (no-op if dotenv missing).
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:  # noqa: BLE001
        pass

    health_url = args.health_url or os.getenv("HEALTH_URL", DEFAULT_HEALTH_URL)
    token = os.getenv("SUPABASE_ACCESS_TOKEN") or None
    project_ref = os.getenv("SUPABASE_PROJECT_REF", DEFAULT_PROJECT_REF)
    supabase_url = os.getenv("SUPABASE_URL") or None
    anon_key = os.getenv("SUPABASE_ANON_KEY") or None

    report = run_monitor(
        health_url=health_url,
        token=token,
        project_ref=project_ref,
        supabase_url=supabase_url,
        anon_key=anon_key,
        do_keep_alive=args.keep_alive,
        require_mgmt=args.require_mgmt,
    )

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        out = _format_report(report)
        print(out, file=sys.stderr if report["alert"] else sys.stdout)

    return 1 if report["alert"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
