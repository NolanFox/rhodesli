# Session 163 Assessment — Supabase Free-Tier Recovery + GEDCOM Storage Redesign Design

**Date**: 2026-06-08 → 2026-06-09 · **Mode**: interactive (emergency recovery + design)
**Prompt**: `docs/prompts/session-163-prompt.md` (recovery) · **Context**:
`docs/session_context/session-163-context.md`

## What happened
Production `rhodesli.nolanandrewfox.com` was down (0 people/matches). Diagnosed → fixed
→ redesigned the underlying data model with the user.

## Shipped (with evidence)
- [x] **Diagnosis**: `/health` → `supabase: error: Name or service not known`;
  Management API → project `INACTIVE` (paused). Then post-restore → `402
  exceed_db_size_quota`. Root cause: plan reverted Pro→Free; DB 1,309 MB ≫ 500 MB limit.
- [x] **Restored** paused project via Management API `POST /restore` → ACTIVE_HEALTHY.
- [x] **DB cleanup 1,309 MB → 423 MB** (commit `aff6f379` script; executed). Dropped
  vestigial `gedcom_events`+`gedcom_records` (545 MB, 0 app refs), deleted 731,942
  superseded `gedcom_relationships` rows, VACUUM FULL. **Fresh R2 snapshot of all 3
  full tables first** (sha256 manifest) → no data loss. Verified app-facing tables
  intact (identities 4112, photos 1127, photo_faces 3338, etc.).
- [x] **Root-caused the bloat**: importer is non-atomic (per-batch commits); 7 of 9
  GEDCOM "versions" were failed retries leaving duplicate rows. (Lesson 199.)
- [x] **PRD-064** GEDCOM storage redesign written; **Codex audit** (gpt-5.5/xhigh,
  `session-163-codex-audit.md`) → revised recommendation to **Option B-plus**
  (current-state tables + R2 history artifacts + atomic importer + compensating unwind +
  "what's new" version-diff). 3 P0s caught.
- [x] **Session 164 prompt + context** written (end-to-end implementation).
- [x] **Harness updated**: Lessons 199/200/201, OD-015, repeat-offender row, Codex pin
  refreshed (2026-06-09), memory `project_supabase_egress` corrected.

## Deferred (with reason)
- **Restore live service** — BLOCKED on billing: Fair-Use restriction lifts only via Pro
  upgrade (immediate) or ~25 Jun cycle reset. User will upgrade after Session 164 (data
  layer solid). Site remains down until then by user decision.
- **B-plus implementation** → Session 164 (own focused session; data-integrity work).
- **OPS-002 monitoring** (health/size alerts + keep-alive) → BACKLOG.
- **RHODES-WIKI-004** (original 163 scope) → future session.

## Red flags / watch items
- [medium] Site is DOWN pending the user's Pro upgrade — expected, user-decided, not a bug.
- [low] DB at 92% of Free limit until Session 164 trims `individuals_v2` (~290→ target).
- [low] `test_gedcom_versioning.py:649` asserts rows survive a failed import — MUST be
  inverted in Session 164 (it institutionalized the bloat bug).

## AI Tool Usage
- **Tool**: Codex CLI v0.139.0 (gpt-5.5, xhigh) · **Agent type**: Independent (fresh context)
- **Task**: Audit PRD-064 storage redesign (Option A) + recommend best design.
- **Findings**: 3 P0, 3 P1, 4 P2. **Acted on**: all — recommendation changed A→B-plus.
- **Discarded**: none. **Value**: STRONG — caught non-atomic-import root cause, the
  field-log unwind hole (NULL adds/removes), and reverse-replay unsafety. Would not have
  fully caught these solo.

## Next session (164) should verify FIRST
1. Inherited state: DB size, `_v2` tables, R2 snapshots intact, pooler/Mgmt-API work.
2. That the atomic-import structural test is written BEFORE the importer rewrite.
3. The `test_gedcom_versioning.py:649` inversion.
