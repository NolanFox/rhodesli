# Session 157b — Continuation of 157 (Tier 1 sweep + PRD-063 Day 2 + Track E)

**Mode**: Implementation
**Predecessor**: Session 157 (`docs/assessments/session-157-assessment.md`, `docs/session_logs/session-157-log.md`)
**Critical deadline**: 2026-05-29 — Supabase free-tier 1.1 GB ceiling. Today is the day this session runs (re-confirm via `date -u`). The PRD-063 implementation arc is now Day 2 of 3; Day 3 (cutover + drop v1 + VACUUM FULL) is Session 158. **If 157b lands within 5 days, the arc completes before the deadline with margin.**

**Why this session exists**: Session 157 fired two parallel Track A subagents that both hit Anthropic's usage limit at launch and returned without doing any work. Only AD-244 was salvaged inline (commit `fb4b200f`). All six Tier 1 quick wins, all four Day 2 phases, and all five Track E phases need to land here. The original Session 157 prompt remains the canonical source of truth at `docs/prompts/session-157-prompt.md` — this prompt scopes 157b as "everything 157 deferred," with one structural addition: a pre-flight budget check before parallel work.

## Setup

```bash
echo "157b" > .claude/current_session.txt
echo "implementation" > .claude/session_mode.txt
source venv/bin/activate
bash scripts/harness-check.sh             # warn-only on doc-cap acceptable
make test-fast                             # baseline — must be green (4246 expected)
git log origin/main..HEAD                  # MUST be empty
git pull origin main                       # safety
git status --short                         # nothing meaningful
```

## NEW — Pre-flight budget check (before launching parallel work)

Before spawning ANY parallel subagent in this session:

1. **Time-since-last-session check**: confirm at least 4 hours have elapsed since Session 157's final commit (or however long since the last heavy parallel-agent session). Anthropic's user-level usage limit resets daily; tight back-to-back sessions can drain it.
2. **Single-agent canary**: launch ONE subagent first (Subagent #1 from the original prompt). Wait for it to return. If duration is **< 30 seconds AND total_tokens < 100**, that's a usage-limit failure pattern — abort the second launch, recover the first agent's work inline OR reschedule the session.
3. **If the canary succeeds (does real work)**: launch Subagent #2 immediately. They run in parallel from there.

This is a temporary mitigation pending Lesson 182 candidate ("Verify subagent budget consumption before assuming parallel work is in flight").

## Required first reads (in order)

1. `docs/assessments/session-157-assessment.md` — what 157 actually shipped vs deferred + open question with options.
2. `docs/session_logs/session-157-log.md` — phase checklist + verification gate.
3. `docs/prompts/session-157-prompt.md` — the **canonical** prompt; 157b is "all of this minus AD-244."
4. `docs/assessments/session-156-assessment.md` — for context on what Day 1 shipped.
5. `docs/prds/063_gedcom_mirror_efficient_redesign.md` — the design.
6. `docs/BACKLOG.md` — search "Session 156 deferred items" block.
7. Lessons 173-181 in `tasks/lessons.md`. **Add lesson 182 candidate** (budget pre-flight) if the canary check works.

## Non-negotiable rules

(carry forward verbatim from 157 prompt §"Non-negotiable rules")

1. READ-ONLY on production browsers (`.claude/rules/browser-read-only.md`).
2. **Codex CLI invocation**: `codex exec "<prompt>" </dev/null`. NEVER `--full-auto`.
3. Commit atomically per phase. /clear between phases at 300+ transcript lines.
4. Every ML decision gets an AD entry. **AD-244 is already on main as commit `fb4b200f` — do NOT re-write.** AD-245 likely if dual-read helper is non-trivial.
5. R2 reversibility test must remain valid throughout — do NOT drop v1 in 157b (158 work).
6. `make test-fast` before every commit.
7. Track E uploads new GEDCOM through PRODUCTION import path — irreversible. Snapshot `gedcom_versions` row count + sizes BEFORE upload. Gated on E1 user authorization.

## Concurrent-genealogy-session resilience (R1-R9)

Same as Session 157 prompt. R1 marker file held during Track E import + Day 2 (B1) full-backfill commit only.

---

## Phase 157b-0 — Carry verification (~10 min, NOT 5)

Spend the extra 5 min because production state could have shifted since 157.

```bash
ls docs/assessments/session-156-assessment.md docs/assessments/session-157-assessment.md
ls docs/session_logs/session-156-log.md docs/session_logs/session-157-log.md
ls scripts/migrations/gedcom_v2_schema.sql scripts/session156_backfill_gedcom_v2.py
grep "^### AD-244" docs/ml/ALGORITHMIC_DECISIONS.md && echo "AD-244 already on main (Session 157 commit fb4b200f)"

# v2 tables — count + post-cutover delta
python -c "
from dotenv import load_dotenv; load_dotenv()
from app.supabase_data import get_supabase_client
sb = get_supabase_client()
for t in ['gedcom_individuals_v2', 'gedcom_families_v2', 'gedcom_change_manifest']:
    r = sb.table(t).select('*', count='exact').limit(1).execute()
    print(f'{t}: count={r.count}')
# Post-cutover v1 delta — how big is the Day 2 backfill batch?
for t in ['gedcom_individuals', 'gedcom_families']:
    r = sb.table(t).select('*', count='exact').eq('is_current', True).gt('created_at', '2026-05-08T04:56:15Z').limit(1).execute()
    print(f'{t} new is_current=TRUE since cutover: {r.count}')
"

# Harry repair landed?
python -c "
from dotenv import load_dotenv; load_dotenv()
from app.supabase_data import get_supabase_client
sb = get_supabase_client()
h = sb.table('identities').select('anchor_ids,version_id').eq('identity_id','d74cb556-6d44-4288-ade3-1cc8fa2b45a6').execute().data[0]
n = sb.table('identities').select('name,state,metadata').eq('identity_id','ef39908e-283a-4cec-8f72-3ec83bc8d84f').execute().data[0]
print(f'Harry: anchors={len(h[\"anchor_ids\"])}, version_id={h[\"version_id\"]}')
print(f'New: name={n[\"name\"]}, state={n[\"state\"]}, has_notes={bool(n[\"metadata\"].get(\"notes\"))}')
"
```

Expected: v2 tables 21,998 / 6,741 / 9 (or higher if a parallel genealogy session imported new GEDCOM); Harry 5 anchors version 14; Belle Isle INBOX with notes. Post-cutover v1 delta is the size of B1's backfill batch — **expect 0 unless a concurrent session imported**.

If anything is missing or surprising: STOP, surface to user. Do NOT proceed to Tracks A/B/E without explanation.

---

## Track A — Tier 1 quick wins (CARRY FROM 157)

**Use the original 157 prompt §Track A verbatim** at `docs/prompts/session-157-prompt.md` lines 116-247. **Skip Phase A1.1** (AD-244 already shipped on `fb4b200f`).

Quick recap (full text in 157 prompt):

### Subagent #1 (after canary check passes)

- ~~A1.1 — AD-244 entry~~ **SKIP — already on main (commit fb4b200f).**
- **A1.2 — NOTES-BACKFILL-156** (~25 min): write `scripts/session157_notes_backfill.py`, dry-run, commit script + report. Execute only if delta > 0 AND nothing surprising.
- **A1.3 — Codex audit of Session 156 commits** (~10 min): `codex exec "<156 audit prompt from 157 prompt §A1.3>" </dev/null`. Save to `docs/session_context/session-157b-codex-audit.md` (note: filename is **157b**, not 157). If Codex stalls: fall back to a Claude general-purpose subagent. Surface P0/P1 findings to orchestrator BEFORE Track B begins.

### Subagent #2 (parallel with #1, after canary)

- **A2.1 — CI-COMPARE-FAIL-156** (~15 min): investigate, pick fix, commit. See 157 prompt §A2.1 for the full 4-step diagnosis flow.
- **A2.2 — TEST-ISOLATION-156** (~15 min): repro the 4 failing tests under `-p no:xdist`, diagnose cache leakage, fix `tests/conftest.py`, verify both sequential and xdist pass.

### Track A merge

After both subagents return: orchestrator runs `./scripts/merge.sh <branch1> <branch2>` from main repo cwd (Lesson 176 guard fires). Push. Verify CI green.

**If P0/P1 from Codex audit**: fix on main BEFORE Track B begins.

---

## Track B — PRD-063 Day 2 (CARRY FROM 157)

Use the original 157 prompt §Track B verbatim at lines 250-326. Quick recap:

### Phase B1 — Full backfill since cutover (~30 min)

```bash
python scripts/session157_full_backfill_gedcom_v2.py --dry-run
```

Note: **filename is `scripts/session157_full_backfill_gedcom_v2.py`** even though we're in 157b — keeps the script name aligned with the cutover timestamp namespace. Adjust if you prefer `session157b_*` for clarity.

Reads is_current=TRUE rows added to v1 since `2026-05-08T04:56:15Z`. INSERTs into v2 with `ON CONFLICT (payload_hash) DO NOTHING`. **R1 marker file held during the `--execute` run.** Commit: `feat(session-157b): PRD-063 full backfill catching post-cutover rows (Track B1)`.

If the post-cutover delta from Phase 157b-0 was 0: this is a no-op confirmation commit. Document accordingly.

### Phase B2 — Dual-read helper (~30 min)

`app/gedcom_dual_read.py` with `get_individual(gedcom_id)` and `get_family(family_gedcom_id)`. v2 preferred, v1 fallback. Wire into `app/relationship_routes.py::_load_gedcom_face_links`. Surgical only — do NOT refactor the GEDCOM stack.

`tests/test_gedcom_dual_read.py` with 4 cases (v2-only, both-v2-wins, v1-only, neither-returns-None).

If the helper grows non-trivial (>100 lines or non-obvious tradeoffs): write **AD-245** in the same commit explaining the dual-read semantics + fallback rules.

Commit: `feat(session-157b): PRD-063 dual-read helper for v2 with v1 fallback (Track B2)`.

### Phase B3 — Side-by-side query timing (~30 min)

`scripts/session157b_query_timing.py` benchmarks the top 5 GEDCOM read paths against v1 vs v2:
1. `_load_gedcom_face_links`
2. Person page GEDCOM context
3. `/tree`
4. `/tools/search` GEDCOM lookups
5. GEDCOM triage page

100 iterations each. Median + p95 latency. Output to `docs/session_context/session-157b-query-timing.md`.

If v2 ≥ v1 across the board: dual-read confidence GREEN → 158 cutover safe. If slower: investigate index gaps, document, recommend either index additions in 158 or v1-primary reads for those paths.

Commit: `chore(session-157b): PRD-063 dual-read query timing (Track B3)`.

### Phase B4 — Confidence assessment (~15 min)

`docs/feedback/session-157b-day-2-confidence.md`:
- B1 backfill row counts
- B2 dual-read test results
- B3 query timing comparison
- Open issues for Session 158 (other v2 tables — backfill or read-bridge?)
- **Recommendation**: PROCEED to 158 cutover OR HOLD for 157c

Commit: `docs(session-157b): PRD-063 Day 2 confidence assessment (Track B4)`.

---

## Track E — GEDCOM upload UAT (CARRY FROM 157, gated on user E1 authorization)

Use the original 157 prompt §Track E verbatim at lines 330-384. Quick recap:

### E1 — User confirmation (~5 min)

**ASK THE USER**: "Is the file at `~/Downloads/gedcom_20260508/Fox_Capeluto_Fogel_Waldorf Family Tree.ged` (17.08 MB, sha256 `f7832541...`) still the canonical newest Fox-family GEDCOM you want imported? Or have you downloaded a newer one since Session 156?"

If user confirms 156's file: proceed. If user has newer: re-archive to R2 (Session 156 Track B2 pattern) under a new namespace (`2026-MM-DD-session-157b/`), then proceed.

**If user declines or wants to defer**: document at `docs/feedback/session-157b-track-e-deferred.md` and skip to Track Z. Track E rolls to a future session.

### E2 — Pre-import baseline (~5 min)

Capture row counts for `gedcom_versions`, `gedcom_individuals`, `gedcom_records`, `gedcom_events`, `gedcom_relationships`, `gedcom_change_log`, `gedcom_families`, plus v2 row counts and Supabase total DB size.

### E3 — Upload via v1 importer (~30 min)

**IRREVERSIBLE.** Set marker:
```bash
touch .claude/parallel_session_active
```

Run the existing import path (likely `python scripts/import_gedcom.py --file <path>` or admin UI POST). Watch for Lesson 163 (175K+ rows scaling issue). If errors: STOP, surface to user, decide rollback (R2 archive) / patch / band-aid prune fallback.

If success: capture `gedcom_versions` new row (likely v10) + child-table row counts.

```bash
rm .claude/parallel_session_active
```

### E4 — 4 verification points (~30 min)

(Per user message during 155 closeout — full text in 157 prompt §E4):
1. Easier to upload — was the rollback path clean?
2. Easier to understand changes per family — query `gedcom_change_manifest` for v10 vs v9 Fox family.
3. Storage growth fixed — measure size delta. v1 expected to add ~250-300 MB. v2 backfill expected to add only delta. **If v2 grows like v1: regression — escalate.**
4. Supabase not broken — `/api/admin/db-size`, `/health`, browser-verify person/tree/search, `pytest tests/test_gedcom_*.py -q --no-header`, `pytest tests/test_data_integrity.py -q --no-header`.

### E5 — UAT writeup + commit (~10 min)

`docs/feedback/session-157b-gedcom-upload-uat.md`. Commit: `feat(session-157b): GEDCOM upload UAT (Track E)`.

---

## Track Z-prelude — 157 closeout backfill (~15 min, MANDATORY before Track Z)

Three closeout gaps from Session 157 must be resolved here before 157b's own closeout begins:

### Z-pre.1 — SESSION_HISTORY.md backfill
`docs/roadmap/SESSION_HISTORY.md` ends at Session 153b. Sessions 154, 155, 156, 157 are all missing. Append entries for at minimum 156 + 157 (157b can leave 154/155 as a separate BACKLOG-tracked drift cleanup if budget is tight). Format follows the existing pattern — one `## Session N: Title (date) — vX.Y.Z` heading per session with bullet summary of what shipped.

If you choose to backfill 154/155 too: read `docs/assessments/session-15{4,5}-assessment.md` and `CHANGELOG.md` for source material. Otherwise log a `SESSION-HISTORY-DRIFT-001` BACKLOG entry capturing the gap.

Commit: `docs(session-157b): SESSION_HISTORY.md backfill for sessions 156+157 (Track Z-pre.1)`.

### Z-pre.2 — Browser verify 6 canonical pages (READ-ONLY)
Per `.claude/rules/session-defaults.md` step 6, every session must browser-verify these 6 pages on production via claude-in-chrome MCP (READ-ONLY per `.claude/rules/browser-read-only.md`):

1. Landing (`/`)
2. People grid (`/people` or `/c/<community>/people`)
3. Person page (any `/person/<id>` — Belle Isle `ef39908e-...` is a good Session 156 verify target since it should now render past the 600s cache TTL)
4. Compare (`/tools/compare` or `/facecompare`)
5. Estimate (`/tools/estimate`)
6. 404 (any garbage URL — confirm it returns the styled 404 page, not a stack trace)

Take screenshots, log results to `docs/feedback/session-157b-browser-verify.md`. If any page errors: STOP, surface to user, decide hot-fix vs BACKLOG.

This was skipped in Session 157 (only `curl -I /` and `curl -I /health` ran). Catching the visual state of all 6 pages on entry to 157b is a fresh sanity check before the riskier dual-read + GEDCOM upload work begins.

### Z-pre.3 — Run `/session-review` skill (for Session 157 retroactively)
Per session-defaults.md step 9, every session ends with the `/session-review` skill. Session 157 didn't run it. 157b should run it twice: once retroactively for 157 (point it at `docs/assessments/session-157-assessment.md` + the 3 commits `fb4b200f`, `18e4acea`, `e3a91ede`), then again at 157b's own end.

If `/session-review` hits the same usage-limit that killed Track A in 157: document and skip — the assessment file already exists and stop-gate.sh accepts the deferral pattern.

---

## Track Z — Closeout (~30 min, mandatory 12-step harness)

Per `.claude/rules/session-defaults.md`:

1. `docs/assessments/session-157b-assessment.md` with full AI Tool Usage section (Codex audit value rating, subagent value ratings).
2. CHANGELOG: bump to v0.99.74 (or whatever is next from 157's v0.99.73).
3. ROADMAP: add to Recently Completed; remove Session 157b from Planned Sessions.
4. `docs/BACKLOG.md`: close items resolved.
   - NOTES-BACKFILL-156 → CLOSED (or NO-OP if 0 deltas)
   - CODEX-AUDIT-156 → CLOSED
   - CI-COMPARE-FAIL-156 → CLOSED
   - TEST-ISOLATION-156 → CLOSED
   - GEDCOM-UAT-156 → CLOSED (or DEFERRED if user declined E1)
   - PRD-063-DAY-2-IMPL → CLOSED
   - GEDCOM-V2-OTHER-TABLES → decision documented (backfill in 158 or read-bridge)
   - Add: PRD-063-DAY-3-IMPL (Session 158)
5. `git push origin main`.
6. Browser verify the canonical 6 pages + new GEDCOM-context render (READ-ONLY).
7. `git log origin/main..HEAD` empty.
8. `git status --short` empty.
9. `bash scripts/harness-check.sh` exit 0.
10. `bash scripts/backup-memory.sh`.
11. Run `/session-review` skill.
12. Codex final-pass audit on all 157b commits.

---

## Success gates

| Gate | How to check |
|---|---|
| Phase 157b-0 carry verification | All 156+157 deliverables intact |
| Pre-flight budget canary | First subagent does real work (>30s, >100 tokens) |
| Notes backfill complete or no-op confirmed | Report at `docs/feedback/session-157b-notes-backfill-report.md` |
| Codex audit pass | `docs/session_context/session-157b-codex-audit.md` exists; P0/P1 addressed |
| CI-COMPARE-FAIL fixed | Latest CI run green |
| TEST-ISOLATION fixed | Sequential pytest of the 4 tests passes |
| Day 2 backfill complete | New v2 rows since cutover landed (or 0-delta confirmed) |
| Dual-read helper shipped | `app/gedcom_dual_read.py` + 4 unit tests pass |
| Query timing recorded | `docs/session_context/session-157b-query-timing.md` |
| Confidence assessment for Day 3 | `docs/feedback/session-157b-day-2-confidence.md` |
| GEDCOM UAT shipped or explicitly deferred | All 4 verification points pass; writeup committed; OR user-declined deferral doc |
| Codex final audit pass | (recommended) |
| Full closeout | All 12 harness steps; `git log` + `git status` clean |

## Phase timing estimates

| Track / Phase | Solo-time |
|---|---|
| 157b-0 carry verification (extended) | 10 min |
| Subagent #1 canary (notes backfill + Codex) | 35 min |
| Subagent #2 (CI-COMPARE + TEST-ISOLATION) | 30 min |
| Track A merge | 5 min |
| **Track A total** | **~50 min** (with parallelization, after canary passes) |
| B1 full backfill | 30 min |
| B2 dual-read helper | 30 min |
| B3 query timing | 30 min |
| B4 confidence doc | 15 min |
| **Track B total** | **~1h 45min** |
| E1-E5 GEDCOM UAT | ~80 min |
| Z closeout | 30 min |
| **Total parallel** | **~4h 25min** (assuming canary passes; serial-only fallback ~5h 30min) |

## Codex CLI invocation reminder

```bash
codex exec "<prompt>" </dev/null    # Form A — recommended
codex exec <<< "<prompt>"           # Form B
echo "<prompt>" | codex exec -      # Form C
```

`~/.codex/config.toml`: model = "gpt-5.5", reasoning_effort = "xhigh". DO NOT use `--full-auto`. Diagnosis: `docs/feedback/session-155-codex-cli-diagnosis.md`.

## What to NOT do this session

- DO NOT drop v1 GEDCOM tables. That's Session 158 work.
- DO NOT pay for Gemini API calls (PRD-LOCATION-001 has its own session).
- DO NOT build `gedcom_records_v2` / `gedcom_events_v2` / `gedcom_relationships_v2` — out of scope.
- DO NOT touch identity rows beyond the notes-backfill (READ-ONLY on Harry/Belle Isle/Albert/Bessie/Irving/Person 3009).
- DO NOT re-write AD-244 — it's on main as `fb4b200f`.
- DO NOT skip the pre-flight budget canary — Session 157 was lost to that exact failure mode.
