# Session 154 Kickoff — Conversation Log

**Conversation span:** 2026-04-28 → 2026-05-07 (with implementation gap in between)
**Mode:** Bridge / harness prep — NOT a Rhodesli feature session
**Predecessor:** Session 153b (`docs/assessments/session-153b-assessment.md`)
**Successor:** Session 154 (`docs/assessments/session-154-assessment.md`) + Session 155 prep
**Why this exists:** The harness changes and Session 154 prompt hardening done in this conversation laid the foundation for Session 154's actual implementation work. This log documents the bridge.

## What this conversation shipped

### Phase 1 — Closeout audit for Sessions 152/153/153b (2026-04-28)

Found one harness gap that 153b had explicitly deferred:
- **SESSION_HISTORY archive ends at Session 142.** Sessions 143-153b never archived. Spawned a worktree subagent to backfill the 15 entries (including discovering Session 148d which the prompt missed). Cherry-picked into main as commit `52bbdc6e`.

All other 153b closeout steps verified complete (assessments exist, CHANGELOG up to v0.99.69, ROADMAP "Recently Completed" populated, push clean, memory backup done).

### Phase 2 — Session 154 prompt — Track E added (2026-04-28)

User flagged a new constraint: Supabase emailed 2026-04-28 saying the org exceeded **database storage** quota (2.39 GB, threshold 1.1 GB, grace until 2026-05-29). This is distinct from egress (already addressed in OD-011/OD-012).

Added to `docs/prompts/session-154-prompt.md`:
- **Track E** with Phases E0 (size discovery, READ-ONLY), E1 (prune plan with user-authorization gate), E2 (gated execution), E3 (retention + monitoring + OD-013).
- Closeout backfill: extended Phase D2 with SESSION_HISTORY archive of 143-153b before any ROADMAP trim (Lesson 77).
- Codex notes: v0.125+ baseline, gpt-5.5/xhigh defaults, `--full-auto` removed (3-session stdin hang).

Committed as `3d0a31ea`.

### Phase 3 — Parallel discovery work (2026-04-28)

Spawned three background jobs:
1. **Codex audit on the new prompt** (gpt-5.5/xhigh, fresh context). Findings recorded at `docs/feedback/session-154-codex-audit-prompt-review.md`.
2. **Worktree subagent — SESSION_HISTORY backfill 143→153b** (closeout gap from 153b). Cherry-picked: `52bbdc6e`.
3. **Worktree subagent — Track E0 Supabase size discovery** (read-only). Output: `docs/feedback/session-154-supabase-size-baseline.json` + `…-summary.md`. Cherry-picked: `4278cdbc`.

E0 surfaced the empirical bloat distribution: **97.9% of 2.22 GB lives in `gedcom_*` tables**. `gedcom_individuals` 783 MB / 196,645 rows. `gedcom_change_log` 397 MB / 1.65M rows. Non-GEDCOM tables combined: ~50 MB.

### Phase 4 — Codex audit findings hardening (2026-04-28)

Codex (gpt-5.5/xhigh) returned 0 P0s, 2 P1s, 3 P2s, 1 P3 on the new prompt. Hardened in commit `945795bb`:
- **P1 (auth gate)**: destructive-action authorization was self-authorable. Now requires user's literal message naming plan-commit hash + tables + DELETE predicates + snapshot paths + VACUUM list. "Or similar" wording removed.
- **P1 (E3 retention)**: ungated recurring DELETE outside E2 gates. Now dry-run-default; `--execute` gated; per-table snapshots; no scheduler enablement until OD-013 user-approved.
- **P2 (snapshot rigor)**: snapshots must include PKs + row counts + checksums + restore commands BEFORE VACUUM FULL. DELETEs use snapshotted PK set, not free-form WHERE.
- **P2 (file ownership)**: clarified Track E owns only `session-154-supabase-*.json` (not all `*.json` — Track A's shadow eval JSON conflict).
- **P2 (closeout)**: added `git status --short` empty + `harness-check.sh` exit 0 as separate gates.
- **P3 (SESSION_HISTORY verification)**: success gate now requires all sessions 143-153b present, not just 143.

### Phase 5 — Codex model pin + 14-day refresh protocol (2026-04-28)

User directives: harness must default to best Codex model + auto-track new releases.

Shipped in `945795bb`:
- **`.claude/rules/codex-model-pin.txt`** — single-line pin file (`model|effort|cli_min|verified_date|source_url|note`).
- **`scripts/harness-check.sh` [5/6] section** — reads pin, fails if `verified_date` > 14 days old.
- **`.claude/rules/ai-tool-audit.md`**: added "Principle: ALWAYS USE THE BEST AVAILABLE MODEL FOR AUDIT WORK" + "Staying current" protocol (14-day window) + upgrade discipline (4-step commit) + downgrade discipline (justification + BACKLOG + 30-day timeline).
- **`.claude/rules/session-defaults.md`**: Codex Dual-Audit Protocol no longer references `--full-auto`.

### Phase 6 — GEDCOM bloat root-cause investigation request (2026-04-28)

User pushback: "I have only updated the gedcom a handful of times… it doesn't make sense that several updates would generate 2-3 orders of magnitude more data."

Investigated `scripts/supabase_migration_003_gedcom_rich_mirror.sql` (Session 98). Confirmed root cause:
- Migration explicitly **drops the unique constraint on `gedcom_id`** (line 18) — versioned duplicates by design.
- Each row gets 14 JSONB columns (line 21-30) PLUS `raw_record_json` storing the full payload (line 32) — same data stored ~12 different ways per row.
- `payload_hash` index added (line 41) but apparently NOT used to dedup at INSERT.

Added two new phases to the prompt (`dbad14a9`):
- **Phase E0.5 (root-cause investigation, READ-ONLY, 30 min)** — verify the suspected mechanisms empirically before pruning.
- **Phase E4 (mirror-redesign PRD, design-only, 45 min)** — writes `docs/prds/063_gedcom_mirror_efficient_redesign.md` with hash-dedup at insert, single-canonical-row-per-individual, raw payload moved to R2, per-import change manifest replacing per-cell change_log. Zero-data-loss migration path.

Phase E2 (prune) reframed explicitly as a stopgap; the real fix is the E4 redesign in a follow-up session.

### Phase 7 — Implementation gap (2026-04-29 → 2026-05-07)

Sessions 154 and start-of-155 ran in separate Claude Code conversations. See:
- `docs/assessments/session-154-assessment.md` — full Session 154 implementation results (v0.99.70).
- `docs/prompts/session-155-prompt.md` — Session 155 prep with Track 4 user decisions surfaced.

### Phase 8 — Toolchain refresh (2026-05-07)

User asked to update Claude Code + Codex CLI:
- Claude Code: 2.1.122 → **2.1.133**
- Codex CLI: 0.125.0 → **0.129.0**

Verified gpt-5.5 still latest Codex model (no 5.6 released as of 2026-05-07; gpt-5.5 hits 58.6% SWE-Bench Pro / 82.7% Terminal-Bench 2.0). Refreshed pin verified_date 2026-04-28 → 2026-05-07. Committed as `0f3b6f9b`.

## Commits attributable to this conversation

| Hash | Message |
|---|---|
| `3d0a31ea` | docs(session-154): add Track E (Supabase free-tier compliance) + closeout backfill |
| `52bbdc6e` | docs(session-history): backfill sessions 143-153b — closeout gap from 153b |
| `4278cdbc` | docs(session-154-E0): supabase size baseline + summary (read-only discovery) |
| `945795bb` | chore(harness): codex model pin (gpt-5.5/xhigh) + 154 prompt hardening from codex audit |
| `dbad14a9` | docs(session-154): add Phase E0.5 (bloat root cause) + E4 (mirror redesign PRD) |
| `0f3b6f9b` | chore(harness): refresh codex model pin (no model change, verified 2026-05-07) |

All on `origin/main`.

## Files created or modified by this conversation

- `docs/prompts/session-154-prompt.md` — extensive additions (Track E, Phase E0.5, Phase E4, Codex P1/P2 hardening)
- `docs/feedback/session-154-codex-audit-prompt-review.md` — new
- `docs/feedback/session-154-supabase-size-baseline.json` — new (Track E0)
- `docs/feedback/session-154-supabase-size-summary.md` — new (Track E0)
- `docs/roadmap/SESSION_HISTORY.md` — 15 backfilled entries (143-153b)
- `.claude/rules/codex-model-pin.txt` — new
- `.claude/rules/ai-tool-audit.md` — best-model principle + staying-current protocol
- `.claude/rules/session-defaults.md` — Codex `--full-auto` removed
- `scripts/harness-check.sh` — new `[5/6]` Codex pin freshness section
- `docs/session_logs/session-154-kickoff-log.md` — this file

## What this conversation did NOT do

- Did not run Tracks A/B/C/D implementation — Session 154 conversation did that.
- Did not execute Phase E2 (Supabase prune) — required user authorization message; deferred to a future session.
- Did not write PRD-063 (GEDCOM mirror redesign) — Track E subagent hit usage limit during Session 154; deferred to Session 155.

## Lessons / harness reflections

- The 14-day pin-freshness gate now in `harness-check.sh` is novel — no prior session had ratchet-style "check yourself against the world." If it works (forces a refresh check at session start when stale), it could generalize to other external dependencies (Supabase SDK version, Gemini model id, Railway runtime).
- The user's GEDCOM "this doesn't add up" intuition was correct and saved us from the wrong fix (just-prune). The redesign PRD will be more valuable than the stopgap prune.
- Codex audit (gpt-5.5/xhigh) on the prompt found a real authorization-gating gap that I had under-specified. ROI was high — would not have caught the self-authorable auth-file path without an independent reviewer.

## Closeout state

- Working tree: clean (`session_mode.txt` reverted to committed `implementation`).
- `git log origin/main..HEAD`: empty.
- Harness-check: 1 pre-existing failure (78 docs over 300-line cap, flagged in 153b, out of scope here). All other gates green including Codex pin freshness (0 days old).
- Memory backup: pending — running at end of this commit.

## Provenance

- Initial context (2026-04-28): Session 153b assessment, ROADMAP, CHANGELOG.
- Codex audit auditor: Codex CLI v0.125 (gpt-5.5, xhigh), independent fresh context.
- Worktree subagents: 2 launched, both completed and cherry-picked successfully.
- Background bash: 1 (Codex audit) — completed cleanly.
