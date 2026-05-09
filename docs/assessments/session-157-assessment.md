# Session 157 Assessment

**Date**: 2026-05-08
**Mode**: Implementation (truncated)
**Predecessor**: Session 156 (`docs/assessments/session-156-assessment.md`)
**Successor**: Session 157b (continuation — `docs/prompts/session-157b-prompt.md`)
**Critical deadline carried forward**: 2026-05-29 — Supabase free-tier 1.1 GB ceiling. PRD-063 implementation arc is at risk of slipping if 157b + 158 don't land in the next 21 days, but on-track if 157b lands within 5 days.

---

## Shipped

### Phase 157-0 — Carry verification — ✅ PASS
Direct Supabase queries verified all Session 156 deliverables intact:
- `gedcom_individuals_v2` 21,998 rows, `gedcom_families_v2` 6,741, `gedcom_change_manifest` 9 — all matching end-of-156 counts (no concurrent genealogy session activity since cutover at `2026-05-08T04:56:15Z`).
- Harry Fox identity (`d74cb556-...`): 5 anchors, version_id = 14 (post-repair).
- Belle Isle Conservatory Young Man identity (`ef39908e-...`): state = INBOX, 1 note in `metadata.notes`.
- Scripts present: `scripts/migrations/gedcom_v2_schema.sql`, `scripts/session156_backfill_gedcom_v2.py`.
- AD-244 not yet in `docs/ml/ALGORITHMIC_DECISIONS.md` (expected — deferred to 157 first commit).

### Track A1.1 — AD-244 entry — ✅ SHIPPED (inline on main, not subagent)
Commit `fb4b200f`. 30-line addition to `docs/ml/ALGORITHMIC_DECISIONS.md`. Captures the full PRD-063 design lineage:
- **Context**: Supabase 1.1 GB ceiling, ~2.21 GB GEDCOM bloat root cause (is_current=FALSE retention across 9 versions, 7 of which were "failed-and-retained"), payload_hash index unused (rows repeat 7×), user rejected band-aid prune in Session 155.
- **Decision**: v2 schema with INSERT-time dedup excluding `is_current=FALSE` (other v1 tables — records/events/relationships — deferred to Session 158 cutover work).
- **v2 row counts**: 21,998 / 6,741 / 9 → 18×/14×/1400× smaller than v1 → **~98% reduction (~45× smaller)** projected when v1 dropped in Session 158.
- **Mechanism**: storage win is entirely from excluding is_current=FALSE — payload_hash dedup factor is 1.00× because every is_current=TRUE row already has a unique payload.
- **Migration plan**: Day 1 ✅ (Session 156), Day 2 (157b — full backfill + dual-read + query timing), Day 3 (158 — cutover + drop v1 + VACUUM FULL).
- **Operational guardrails**: R2 archives at `gedcom-source-snapshots/...` and `gedcom-version-snapshots/...`; reversibility verified on v9 (21,228 rows).
- **Risks**: dual-read assumption that app code handles v1-or-v2 returns; other v2 tables not yet built (BACKLOG GEDCOM-V2-OTHER-TABLES); concurrent-genealogy-session handling.
- **Acceptance gate for Session 158 cutover**: Day 2 query timing v2 ≥ v1 on top 5 read paths AND dual-read tests pass AND no schema drift.
- **References**: B3/B4/B5/merge commit hashes pinned.

---

## Deferred

### Track A1.2 — NOTES-BACKFILL-156 — DEFERRED to 157b
Pre-existing bug (Session 156 lesson 179): `add_note()` writes top-level `identity["notes"]` but `shadow_write_identity` only persisted `metadata` JSONB until Session 156 commit `49298a76`. Identities created via `add_note` between Sessions 105-156 may have local-only notes never persisted to Supabase. Now that the round-trip fix is live, backfill is safe to run. Script not written this session. **Risk**: With DATA_SOURCE=postgres, lost notes are invisible on production until backfill lands.

### Track A1.3 — Codex audit of Session 156 commits — DEFERRED to 157b
Codex CLI is operational (Session 155 Track 5 verified `</dev/null` invocation). Audit of `app/supabase_data.py` (notes embedding paths), `core/registry.py` (load_from_postgres), Harry repair scripts, R2 backup scripts, v2 schema migration, Detroit fix audit_log construction not run this session. **Risk**: data-layer changes (notes round-trip) shipped without independent security/data-integrity review.

### Track A2.1 — CI-COMPARE-FAIL-156 — DEFERRED to 157b
`tests/test_compare.py::test_compare_upload_stages_file` PASSES locally but FAILS in CI. Likely R2 / insightface / state-leak in CI env. **Risk**: CI signal noise; one test failure masks future regressions.

### Track A2.2 — TEST-ISOLATION-156 — DEFERRED to 157b
4 tests fail under sequential pytest, pass under xdist parallel. Likely cache leakage. **Risk**: low — main test gate (xdist) is green at 4246 passed; sequential mode is only used by `merge.sh` post-merge run.

### Track B (PRD-063 Day 2) — DEFERRED to 157b in full
B1 full backfill, B2 dual-read helper, B3 query timing, B4 confidence assessment — all unwritten. **Risk to deadline**: 157b must land within ~5 days to keep Session 158 cutover before 2026-05-29.

### Track E — GEDCOM upload UAT — DEFERRED to 157b
Was already gated on user E1 authorization (the new Fox-family GEDCOM upload is irreversible). **Risk**: if user has continued downloading newer Fox-family GEDCOMs since 156, the R2 archive at `2026-05-08-session-156/` is now stale relative to what the user actually wants imported.

---

## Red Flags

### 🔴 Anthropic usage-limit blocked all parallel work — P1
- **What**: Both Track A subagents (`general-purpose`, `isolation: "worktree"`) returned `You've hit your limit · resets 4:10am (America/New_York)` within 5-10 seconds of launch, with 0-2 tokens consumed each, no `pwd`, no `git rev-parse`, no commits.
- **Mechanism**: Subagents share the orchestrator's account budget. Sessions 156 + start-of-157 had drained the budget before 157 parallel calls fired. The harness has no pre-flight budget check.
- **Recovery this session**: Captured the highest-value artifact (AD-244) inline on main thread, where budget was still available. Six tracks deferred to 157b.
- **Fix**: 157b should launch ONE agent first, verify it consumes >>2 tokens, then launch the second. OR: skip parallelization for budget-tight sessions and run serially. OR: reschedule the session to >5 hours after the previous one (loose heuristic).
- **Lesson candidate (182)**: "Verify subagent budget consumption before assuming parallel work is in flight."

### 🟡 Pre-existing notes-backfill risk lingers — P2
- **What**: Lesson 179's bug shipped a fix in Session 156 (`49298a76`) but the historical backfill was deferred. With DATA_SOURCE=postgres, any pre-156 `add_note` call to an identity that wasn't subsequently re-saved through the new round-trip path may have its notes invisible on production.
- **Severity**: P2 — invisible on production until backfill runs. Magnitude unknown without dry-run.
- **Fix**: Session 157b Phase A1.2 runs the backfill script and reports the delta count.

### 🟡 Codex audit gap on Session 156's data-layer change — P2
- **What**: The notes round-trip fix (`49298a76`) modifies `shadow_write_identity` and `load_from_postgres` — both data-layer paths used on every identity write/read. No independent audit performed before or after merge.
- **Severity**: P2 — production stable so far (no incidents in 24h), but the change touches a hot path.
- **Fix**: Session 157b Phase A1.3 runs Codex audit per `.claude/rules/ai-tool-audit.md`.

### 🟢 Single-commit session passes harness without ceremony — P3
- **What**: Session 157 produced 1 commit (AD-244) and is closing out. Harness session-defaults requires CHANGELOG bump, ROADMAP update, BACKLOG update, deploy verify, browser verify even on a tiny session.
- **Severity**: P3 — administrative, not a defect.
- **Fix**: Closeout artifacts written in this session pass the harness gates. CHANGELOG bumped to v0.99.73 (small bump, AD-only).

---

## Closeout gaps (rolled to 157b Track Z-prelude)

Three of the 12 mandatory session-end steps from `.claude/rules/session-defaults.md` were not completed this session. All three are explicitly carried to 157b:

| Step | Status this session | 157b carry |
|---|---|---|
| 3. SESSION_HISTORY.md update | ❌ Not done. Pre-existing harness drift — file ends at Session 153b; 154/155/156 also missing. | Z-pre.1: backfill at minimum 156+157 (154/155 optional, else log SESSION-HISTORY-DRIFT-001). |
| 6. Browser verify 6 canonical pages | ❌ Only `curl /` and `curl /health` ran (200/200). Did NOT visually verify landing, people grid, person page, compare, estimate, 404. | Z-pre.2: claude-in-chrome MCP verify, screenshot each, log to `docs/feedback/session-157b-browser-verify.md`. |
| 9. Run `/session-review` skill | ❌ Not run. | Z-pre.3: run twice — retroactively for 157, then at 157b's own end. |

Step 10 (Codex audit) is documented as DEFERRED at `docs/session_context/session-157-codex-audit.md`, which satisfies `stop-gate.sh`. Step 3 was done partially (ROADMAP updated, SESSION_HISTORY not). Steps 1, 2, 4, 5, 7, 8 all completed.

The decision to roll these three to 157b (vs run them inline) was made by the user after honest audit: the truncated session budget is better spent on writing a thorough continuation prompt than on stretching to complete every step here at the cost of a less-prepared 157b.

## Verification gate

| Gate | How verified | Result |
|---|---|---|
| Phase 157-0 carry verification | Direct Supabase queries | ✅ PASS |
| AD-244 entry | `grep "^### AD-244" docs/ml/ALGORITHMIC_DECISIONS.md` | ✅ PASS |
| Notes backfill complete or no-op confirmed | Not run | ❌ DEFERRED to 157b |
| Codex audit pass | Not run | ❌ DEFERRED to 157b |
| CI-COMPARE-FAIL fixed | Not investigated | ❌ DEFERRED to 157b |
| TEST-ISOLATION fixed | Not investigated | ❌ DEFERRED to 157b |
| Day 2 backfill complete | Not run | ❌ DEFERRED to 157b |
| Dual-read helper shipped | Not built | ❌ DEFERRED to 157b |
| Query timing recorded | Not measured | ❌ DEFERRED to 157b |
| Confidence assessment for Day 3 | Not written | ❌ DEFERRED to 157b |
| GEDCOM UAT shipped | Not run | ❌ DEFERRED to 157b |
| `make test-fast` | xdist parallel | ✅ PASS (4246 passed, no regression vs 156 baseline) |
| Closeout artifacts | This file + log + CHANGELOG + ROADMAP + BACKLOG + 157b prompt | ✅ in progress |

---

## AI Tool Usage

- **Tool**: Track A1 subagent (Claude Opus 4.7 general-purpose, fresh worktree context)
- **Agent type**: Independent (fresh context)
- **Task**: AD-244 + NOTES-BACKFILL + Codex audit
- **Findings**: NONE — agent returned in 10s with `You've hit your limit · resets 4:10am (America/New_York)`. Total tokens: 2. No commits.
- **Acted on**: Recovered by re-doing AD-244 inline on the main thread.
- **Discarded**: N/A.
- **Value assessment**: NONE — agent never executed.

- **Tool**: Track A2 subagent (Claude Opus 4.7 general-purpose, fresh worktree context)
- **Agent type**: Independent
- **Task**: CI-COMPARE-FAIL + TEST-ISOLATION fixes
- **Findings**: NONE — same usage-limit return, 5851ms duration, 0 tokens, no commits.
- **Value assessment**: NONE.

- **Codex CLI**: NOT INVOKED this session (was scheduled for Phase A1.3, deferred to 157b).

- **Lesson learned**: Pre-flight budget check before launching parallel agents. Once usage limit fires, recovery requires either (a) waiting for budget reset (3+ hours), (b) running work serially in main thread (limited budget remains), or (c) closeout + continuation prompt for a fresh session window. Path (c) was chosen here for the deferred tracks.

---

## Concurrency resilience (R1-R9)

- **R1 marker file**: NOT held this session — only Track A docs work shipped (reversible). Day 2 backfill and Track E import would have held it; both deferred to 157b.
- **R2-R9**: N/A — no Supabase mutations, no R2 writes, no v2 writes this session.

---

## Next session (157b) should verify FIRST

1. **Re-run Phase 157-0 carry verification**: production state could have shifted if a parallel genealogy session imported a new GEDCOM between Session 157 and 157b. Confirm v2 row counts, Harry repair, Belle Isle identity, and (NEW) the post-cutover v1 row count to know how big the Day 2 backfill batch will be.
2. **Pre-flight Anthropic budget check**: confirm the budget is fresh before launching parallel subagents (lesson 182 candidate).
3. **AD-244 already in main**: do NOT re-write. Reference it from 157b first commit body if helpful.
4. **NOTES-BACKFILL-156**: dry-run first. Surface delta count to user before `--execute`.
5. **CODEX-AUDIT-156**: invoke `codex exec "<prompt>" </dev/null` (NEVER `--full-auto`). Save to `docs/session_context/session-157b-codex-audit.md` with provenance header.
6. **Track E user authorization**: confirm the GEDCOM file at `~/Downloads/gedcom_20260508/Fox_Capeluto_Fogel_Waldorf Family Tree.ged` is still the user's intended canonical version. If user has downloaded newer, re-archive to R2 and use the new path.

---

## Commit summary (1 commit this session)

| Commit | Description |
|---|---|
| `fb4b200f` | docs(session-157): AD-244 PRD-063 v2 schema design entry |

`git log origin/main..HEAD` will be empty after push. 4246 tests pass under xdist parallel.

---

## Open question for the user (raised at session end)

User asked at session end:
> "I want you to finish off the work you were doing, give me some options on what we should work on next..."

**Options for what 157b (or follow-up sessions) should tackle, ranked by deadline-criticality and value**:

| Option | What | Why now | Effort |
|---|---|---|---|
| **A — Run 157b as a continuation** | Tier 1 sweep + Day 2 dual-read + Track E (everything deferred from 157) | Keeps PRD-063 arc on schedule for the 2026-05-29 deadline. The full prompt at `docs/prompts/session-157b-prompt.md` is ready to fire. | ~3-4 hours fresh budget |
| **B — Skip Tier 1, jump to Day 2 only** | Just Track B1+B2+B3+B4 (full backfill + dual-read + timing + confidence) | If budget is tight, this is the **deadline-critical** subset. Tier 1 items (notes backfill, Codex audit, CI fix, test isolation) can roll to 158 or later. | ~2 hours |
| **C — Tier 1 sweep only, defer Day 2** | A1.2 + A1.3 + A2.1 + A2.2 only | If user wants the small wins to flush carry-over before bigger work. Risks 158 cutover slipping. | ~1.5 hours |
| **D — Track E (GEDCOM upload UAT) only** | E1-E5: upload new GEDCOM via v1 path, 4 verification points | Pivots back to the user's actual UX question (was the 156 storage win real? does upload still work?). Independent of Day 2 dual-read. | ~1.5 hours |
| **E — Codex audit of all 156+157 commits, full pass** | A1.3 expanded with broader scope | Highest data-integrity-risk-mitigation per dollar. Recommended if user wants confidence before 158 cutover. | ~30-45 minutes |

**Recommended**: Option A (full 157b continuation) if budget permits. Otherwise Option B (Day 2-only). Track E (Option D) is the most user-visible and could be sliced into either A or done standalone.
