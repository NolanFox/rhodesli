# Session 163 Prompt — Supabase Restore + Site Recovery (UNPLANNED)

**Context:** [docs/session_context/session-163-context.md](../session_context/session-163-context.md)
**Date:** 2026-06-08
**Mode:** interactive
**Goal:** Get production `rhodesli.nolanandrewfox.com` fully working again. The site
shows 0 people / 0 matches because the Supabase project auto-paused. Restore it,
confirm the app reconnects, verify end-to-end in Claude Chrome, and add a guard so
this silent failure mode is caught next time.

## Phases

### Phase 0 — Diagnose (DONE)
- `/health` → `supabase: error: Name or service not known`; Management API →
  `status: INACTIVE`. Root cause = paused free-tier Supabase project.

### Phase 1 — Restore Supabase (DONE)
- `POST https://api.supabase.com/v1/projects/{ref}/restore` with `SUPABASE_ACCESS_TOKEN`.
- Poll Management API until `status == ACTIVE_HEALTHY` and DNS resolves.

### Phase 2 — Reconnect the app
- Confirm `/health` shows `supabase: ok` and `data_parity.synced` populates.
- App self-heals within ~10 min via TTL caches. For instant recovery, ask user to
  `railway login`, then `railway redeploy` (Railway CLI was Unauthorized at session start).

### Phase 3 — Browser verification (Claude Chrome, READ-ONLY)
- Verify: New Matches, People (non-zero count), a person page, Photos grid, Map,
  Help Identify, and a community switch. Screenshot evidence to
  `docs/screenshots/session-163/`.
- Confirm "X of Y identified" footer is non-zero and People count matches DB.

### Phase 4 — Prevention guard
- Add an OPS BACKLOG item (+ optionally implement) a scheduled monitor that alerts
  when `/health` `supabase != ok` OR Management API `status != ACTIVE_HEALTHY`.
- Consider a free-tier keep-alive cron, or an admin "database offline" banner so the
  next outage doesn't masquerade as data loss.

### Phase 5 — Closeout
- Assessment `docs/assessments/session-163-assessment.md`, CHANGELOG, ROADMAP +
  SESSION_HISTORY, BACKLOG. `/session-review`.

## Acceptance Criteria
- [ ] Supabase `ACTIVE_HEALTHY`; `/health` `supabase: ok`.
- [ ] People count > 0 in production UI (Claude Chrome verified, screenshot).
- [ ] No regression: `make test-fast` green if any code changed.
- [ ] Prevention item logged (and/or shipped).

## Notes / Rules
- Browser automation on production is **READ-ONLY** (Lesson 149). No clicking
  action buttons.
- Do NOT pursue the original RHODES-WIKI-004 scope this session — recovery only.
