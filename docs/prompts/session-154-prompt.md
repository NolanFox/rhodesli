# Session 154 — Gemini Prompt Fix + Harry Repair Unblock + 153 Codex P0s + Supabase Free-Tier Compliance

**Mode:** Implementation + interactive (mixed)
**Predecessor:** Session 153b (`docs/assessments/session-153b-assessment.md`)
**Context file (MANDATORY first read):** `docs/session_context/session-154-context.md`
**Why this session exists:**
1. The Session 153b shadow eval was invalidated by a design bug — the candidate prompt's 3-round scaffold expects GEDCOM context but the script never passes any. Fix that and validate.
2. In parallel, unblock the Harry Fox anchor repair and close the remaining Session 153 Codex P0s.
3. **NEW (added 2026-04-28 by user):** Supabase organization received a quota-exceeded notice — DB storage is at **2.39 GB** but free-tier "Fair Use" threshold is **1.1 GB**. Grace period until **2026-05-29** (~31 days). This is **storage**, not egress (OD-011/OD-012 already addressed egress). New track E adds a one-shot pruning pass + retention policy + monitoring so we don't trip restrictions.
4. **Closeout backfill:** SESSION_HISTORY ends at Session 142 — sessions 143-153b never archived. Roll up at 154 close.

**Codex CLI baseline:** v0.125.0 with `model = "gpt-5.5"` and `model_reasoning_effort = "xhigh"` (already set in `~/.codex/config.toml`). DO NOT use `--full-auto` — it hung on stdin in sessions 152/153/153b. Use `codex exec "<prompt>"` with prompt as positional arg, or pipe via `<<< "prompt"` heredoc. Test in Phase A0 before relying on it.

## Orientation (READ IN ORDER before any work)

1. `docs/session_context/session-154-context.md` — full carry-over state from Session 153b
2. `docs/assessments/session-153b-assessment.md` — what shipped / deferred / red-flagged in 153b
3. `docs/feedback/session-153b-shadow-eval-results.md` — the invalidated eval + root-cause analysis
4. `docs/feedback/session-153b-harry-repair-decision.md` — the 6-gate list blocking repair
5. `docs/feedback/session-153b-bessie-validation.md` — current honest confidence on Bessie = 3009
6. `scripts/session153_shadow_eval.py` lines 278-314 (`build_prompt`) — the design bug
7. `rhodesli_ml/gemini_extraction.py` lines 319, 364-369 — production `gedcom_context` plumbing (REFERENCE for how to pass it)
8. `tasks/lessons.md` lessons 89, 171, 172

## Session setup

```bash
echo "154" > .claude/current_session.txt
echo "implementation" > .claude/session_mode.txt
source venv/bin/activate
bash scripts/harness-check.sh          # If this fails, STOP and fix first
make test-fast                         # Baseline
git log origin/main..HEAD              # Should be empty after 153b closeout
```

## Non-negotiable rules

1. **READ-ONLY on production** (`.claude/rules/browser-read-only.md`).
2. **Never over-claim.** STRONG/GOOD/POSSIBLE/WEAK/UNKNOWN — not "confirmed" unless triangulated across ≥3 independent sources WITH reference data.
3. **Every phase commits atomically.** `/clear` between phases at 300+ transcript lines.
4. **Every ML decision gets an AD entry** (`docs/ml/ALGORITHMIC_DECISIONS.md`). Session 154 will create AD-241 and AD-242 (see below).
5. **Harness closeout is mandatory.** Do all 9 steps from `.claude/rules/session-defaults.md` Session End. Sessions 152 + 153 drifted; 153b backfilled. DO NOT repeat that drift.

---

## Parallelization plan

Four tracks can run mostly independently, with one merge point.

```
┌──────────────────────────────────────────────────────────────────┐
│ Track A — Gemini prompt fix (MAIN thread)                        │
│   Phases A0, A1, A2, A3, A4                                      │
│                                                                  │
│ Track B — Harry anchor repair unblock (worktree subagent)        │
│   Phases B1, B2                                                  │
│                                                                  │
│ Track C — 153 Codex P0 closure (worktree subagent)               │
│   Phases C1, C2                                                  │
│                                                                  │
│ Track E — Supabase free-tier compliance (worktree subagent)      │
│   Phases E0, E1, E2, E3                                          │
└──────────────────────────────────────────────────────────────────┘
                               │
                               ▼
                   Merge point — Phase D (close)
```

All four tracks work on DIFFERENT files (see §Parallelization constraints in the context file + §Track E file scope below). Launch Tracks B, C, E as background worktree subagents at the start, run Track A in main thread, then synthesize.

**Track-E parallelism note:** E0/E1 are read-only Supabase queries + analysis docs — fully parallel-safe. E2 (DELETE / VACUUM) is destructive; it MUST run last and MUST snapshot first (see Phase E2 gates). E3 (retention policy code) touches new files only and can run in parallel with A.

---

## Track A — Gemini location prompt fix (main thread)

### Phase A0 — Schema drift + API stability (~10 min)

1. **Fix `gemini_api_calls.experiment_id` column missing**:
   - `ALTER TABLE gemini_api_calls ADD COLUMN experiment_id TEXT;`
   - Verify with a read: `SELECT COUNT(*) FROM gemini_api_calls WHERE experiment_id IS NULL;`
   - Commit migration SQL under `scripts/migrations/` (or wherever existing convention places them — check `ls scripts/ | grep -i migra` first).

2. **Add retry-with-backoff to `scripts/session153_shadow_eval.py`** `call_gemini()`:
   - Currently no retry — a 503/504 counts as a permanent fail on that call
   - Use exponential backoff: 2s, 5s, 15s (3 retries max)
   - Don't retry on 4xx (those are request-side failures)

Acceptance: re-run `session153_shadow_eval.py --dry-run` — verifies test-set pulls and emits `experiment_id`. Real run in Phase A3.

### Phase A1 — Patch shadow eval to pass `gedcom_context` (~20 min)

**Root cause reminder:** `build_prompt()` at `scripts/session153_shadow_eval.py:278` only passes `collection`, `source`, `filename`. The prompt references "GEDCOM context" 15+ times but it's never populated.

**Changes:**
1. Add a `gedcom_context` kwarg to `build_prompt()`. When provided, append a `## Genealogical Context` section (match the production format at `rhodesli_ml/gemini_extraction.py:364-369`).
2. Add `resolve_gedcom_context(photo_id, sb)` helper: for each photo in the test set, look up confirmed subjects → their GEDCOM records → their RESI events → format as a concise bulleted list. Prefer:
   - Subject's own RESI events at dates compatible with photo era
   - Subject's OCCUPATION events
   - Subject's children's BIRTH events
   - Deprioritize spouse's residences unless subject has no RESI near the era
3. Pass `gedcom_context` into BOTH variants (baseline + candidate) so the A/B is measuring prompt structure, not data availability. THIS IS CRITICAL.
4. Log the resolved `gedcom_context` alongside each Gemini call for auditability.
5. Record the Detroit-control subjects explicitly in a fixture file at `tests/fixtures/session154_detroit_gedcom_context.json` so re-runs are deterministic.

**Write `AD-241` in `docs/ml/ALGORITHMIC_DECISIONS.md`:**
- Title: `AD-241: GEDCOM context injection in Gemini location prompts (shadow eval)`
- Context: 153b shadow eval invalidated because the prompt expected biographical data it never got
- Decision: location prompts (baseline + candidate) both receive `gedcom_context` derived from confirmed subjects' GEDCOM records
- Rationale: A/B must measure prompt structure, not data availability
- Affects: `scripts/session153_shadow_eval.py`, future `rhodesli_ml/gemini_extraction.py` eval scripts

### Phase A2 — Add iterative refinement / prior-prediction retry (~30 min)

User question answered: "Is there a way if Gemini has already given a prediction about a place that that could be included in a retry?" — Yes. Implementing it.

**Design:**
1. Add a new variant `candidate_with_prior` to `build_prompt()`. It works as a second-pass call:
   - First call: run `candidate` variant (gets an initial prediction)
   - Second call: re-issue with an additional `## Prior prediction to cross-check` block containing the initial prediction's `place` + `confidence` + `reasoning`
   - The block instructs Gemini to **validate the prior prediction against the GEDCOM context and the visual features** and either confirm, refute (with reason), or amend.
2. Key prompt addition (inside the retry section):
   ```
   Your first-pass prediction: place=<X>, confidence=<Y>.
   Cross-check this against:
   - The subjects' GEDCOM residences at the photo's likely date range
   - The diagnostic visual features from Round 1
   Does the prior prediction stand? If not, name the specific feature or GEDCOM fact that refutes it and amend.
   ```
3. **Cost note**: this doubles the per-photo call cost. Log both calls under the same `experiment_id` with sub-keys `pass=1` and `pass=2`.
4. **Failure mode to guard against**: Gemini may sycophantically accept its own prior prediction even when wrong. Mitigation: the prompt explicitly asks for a refuting feature OR a confirming GEDCOM fact — can't just agree with yourself.

**Write `AD-242` in `docs/ml/ALGORITHMIC_DECISIONS.md`:**
- Title: `AD-242: Iterative refinement / prior-prediction retry in Gemini location prompts`
- Context: Session 153b candidate hallucinated "NYBG" for Detroit photo with no biographical context; single-pass prompts have no self-correction mechanism
- Decision: optional second-pass call that embeds prior prediction + demands specific refuting feature or confirming GEDCOM fact
- Rationale: catches confident-hallucination class of errors; cheap ($0.01-0.02 per retry)
- Failure modes + mitigations: sycophancy (guarded by refuting-feature requirement)
- Affects: `scripts/session153_shadow_eval.py`; future `rhodesli_ml/gemini_extraction.py` production option

### Phase A3 — Rerun shadow eval on Detroit-only subset (~10 min)

1. Run ONLY the 2 Detroit photos (02068 + 01659) with THREE variants: `baseline`, `candidate`, `candidate_with_prior`. 6 calls total, <$0.10.
2. Accept the run if:
   - Both Detroit photos get `place` = Detroit/Belle Isle/Michigan at `≥medium` confidence under `candidate_with_prior`
   - Neither regresses under `candidate` (vs baseline) when given GEDCOM context
3. Commit raw output as `docs/feedback/session-154-shadow-eval-detroit-rerun.json`.

### Phase A4 — Full eval if Detroit subset passes (~30 min, Gemini rate-limit dependent)

1. If Phase A3 passes on Detroit, run full 12-photo shadow eval with all 3 variants: 36 calls, ~$0.50 cost cap.
2. Write summary doc `docs/feedback/session-154-shadow-eval-full.md` with per-photo verdicts and a go/no-go on prompt deployment.
3. **Deployment decision is NOT in this session** — per 153b prompt, deployment is always a separate reviewed PR. Session 154 produces evidence, not the deploy commit.

---

## Track B — Harry anchor repair unblock (background worktree subagent)

Launch at session start. Runs parallel to Track A.

### Phase B1 — Resolve face-ID discrepancy (~15 min)

**The discrepancy:** Codex audit cited face `inbox_1fea75...`; Session 153 breakthrough doc cited `inbox_2bc31a40c34a`. They should be the same face (F in the F+G cluster that is NOT Harshel). One is wrong.

**How to resolve:**
1. Grep `data/embeddings.npy` entries: which face IDs actually exist and correspond to 02068?
2. Query Supabase `photo_faces` for `photo_id = inbox_fox-charlie-001_204_02068_p_13akf5twbc3600`
3. Query Supabase `identities.anchor_ids` for the Harry Fox identity (`d74cb556-6d44-4288-ade3-1cc8fa2b45a6`) — which 7 face IDs does it currently claim?
4. Cross-reference: which of F and G are in the anchor list, and which actual face IDs are they?
5. Produce `docs/feedback/session-154-harry-face-id-resolution.md` with the definitive 2 face IDs + evidence.

### Phase B2 — Strengthen Bessie hypothesis (or falsify) (~20 min)

**Three tests to run (any one of which can materially move the needle):**

1. **Multi-frame triangulation**: if face 3009-equivalent appears in 01659 (second Belle Isle frame), that's independent corroboration of the woman's presence at the event. Use embedding proximity search across 01659's detected faces vs 3009's embedding. Threshold: d < 1.10 = same person.
2. **Kinship proximity test**: Bessie's confirmed daughter Leona Fox Smilg ranked #15 at d=1.24 for 3009 in the 153b run. Check systematically: does 3009 have similar proximity to OTHER Bessie-adjacent identities (Bessie's other children, grandchildren, Albert as her brother)? A kinship-cluster pattern would strengthen the hypothesis.
3. **Age-adjacent Bessie photos**: search Ancestry tree 162873127 for a 1910s Bessie photo (user task / Ancestry search). If found, run embedding distance against 3009. A 1915-1920 Bessie photo near 3009 would be the strongest possible signal.

Produce `docs/feedback/session-154-bessie-strengthening.md` with the test results + updated confidence.

---

## Track C — Session 153 Codex P0 closure (background worktree subagent)

Launch at session start. Runs parallel.

### Phase C1 — Belle Isle archival citation (~20 min)

**Goal:** independent archival confirmation that 02068 + 01659 are at Belle Isle Conservatory, Detroit. Should not require site access — publicly available archives should suffice.

1. Search the Burton Historical Collection (Detroit Public Library) catalog online for "Belle Isle Conservatory" 1917-1918 photos
2. If any publicly indexed photo shows the same conservatory architecture as 02068 + 01659, cite it (URL, date, accession number)
3. Alternative archives: Detroit Historical Society, Wayne State archives
4. Produce `docs/feedback/session-154-belle-isle-citation.md` with the citations + confidence rating

### Phase C2 — Irving anchor verification (~15 min)

**Goal:** confirm seated-left man in 02068 IS Irving Fox (as asserted in Session 153, but never verified — Codex flagged the gap).

1. Pull Irving Fox's 8 confirmed anchors from Supabase
2. Compute embedding distance from the 02068 seated-left face to each of Irving's anchors
3. Compare to cross-sibling baseline (Albert↔Irving min = 1.095 per Codex's baseline analysis)
4. Produce `docs/feedback/session-154-irving-verification.md` with the distance matrix + verdict (STRONG / GOOD / POSSIBLE / WEAK / UNKNOWN)

---

## Track E — Supabase free-tier compliance (background worktree subagent)

**Why:** Supabase emailed 2026-04-28 — org "Nolan Fox Projects" exceeded free-tier database-storage quota. **Current size: 2.39 GB. Threshold for restrictions: 1.1 GB.** Grace until **2026-05-29**. This is *database storage* (table+index bytes on disk), distinct from egress (OD-011/OD-012, network bytes shipped). User just downgraded back to free after a 1-month Pro stint that addressed egress — storage was never pruned.

**Hard rule:** Track E is **READ-ONLY in Phases E0+E1**. The destructive Phase E2 (DELETE/VACUUM) only fires if E1 produces a written plan that the user (or main thread, if user has approved the auto-prune list ahead of time) explicitly authorizes. Default behavior at session end if no authorization: stop after E1, leave a written plan, do NOT prune.

### Phase E0 — Size discovery (~10 min, READ-ONLY)

Run a Supabase SQL query that lists every table + index by size on disk. Save raw output to `docs/feedback/session-154-supabase-size-baseline.json`.

```sql
-- run in Supabase SQL editor or via psql
SELECT
  schemaname,
  relname AS table_name,
  pg_size_pretty(pg_total_relation_size(relid)) AS total_size,
  pg_total_relation_size(relid) AS total_bytes,
  pg_size_pretty(pg_relation_size(relid)) AS table_size,
  pg_size_pretty(pg_total_relation_size(relid) - pg_relation_size(relid)) AS index_size,
  n_live_tup AS row_estimate
FROM pg_catalog.pg_statio_user_tables
JOIN pg_stat_user_tables USING (relid)
ORDER BY pg_total_relation_size(relid) DESC
LIMIT 30;
```

Also dump per-column average size for the top 5 tables (helps identify JSONB/text columns eating space):

```sql
-- replace 'gemini_api_calls' for each top-5 table
SELECT
  attname,
  pg_size_pretty(SUM(pg_column_size(t.*))::bigint) AS total
FROM gemini_api_calls t, LATERAL (SELECT * FROM jsonb_each(to_jsonb(t))) j
GROUP BY attname
ORDER BY SUM(pg_column_size(t.*))::bigint DESC;
```
(Adjust per actual schema — pseudocode above; the agent should write the right SQL for each table.)

Acceptance: baseline JSON committed; top-5 tables identified with byte counts.

### Phase E1 — Pruning plan (~30 min, READ-ONLY)

Based on E0, write `docs/feedback/session-154-supabase-prune-plan.md` with:

1. **Table-by-table verdict** for the top 10 tables: KEEP_ALL / PRUNE_OLD / PRUNE_COLUMNS / VACUUM_ONLY
2. **Suspected biggest culprits to evaluate** (verify against actual sizes from E0):
   - `gemini_api_calls.prompt_text` + `full_response` + `gedcom_context` (Session 92 added these — can balloon at 5-50KB per row × hundreds of rows)
   - `change_log` (Lesson 163 noted 175K+ rows for GEDCOM versioning)
   - `gedcom_*` versioned mirror tables (`002_gedcom_versioning.sql`, `003_gedcom_rich_mirror.sql`)
   - `ml_proposals` (Session 109b added 1130 rows)
   - `audit_log` (Session 113 — 22 call sites)
3. **Per-table proposed action** with row-count estimate, byte savings estimate, and reversibility:
   - Example: `gemini_api_calls`: archive rows where `created_at < NOW() - INTERVAL '90 days'` to local JSONL backup at `backups/session-154/gemini_api_calls_pre-prune-{UTC}.jsonl.gz`, then DELETE. Reversible via re-import.
   - Example: `change_log` for GEDCOM versions ≥3 versions stale: ditto.
4. **VACUUM FULL plan**: which tables need it (DELETE alone doesn't reclaim disk — Postgres requires VACUUM FULL or `pg_repack` to actually shrink).
5. **Target final size**: ≤900 MB (gives 200 MB headroom under the 1.1 GB threshold).
6. **Authorization gate**: explicit "USER MUST APPROVE before E2 runs" line. Default = STOP.

Acceptance: plan doc committed; final-size estimate ≤ 900 MB; user-approval gate present.

### Phase E2 — Execute pruning (~30 min, DESTRUCTIVE — gated)

**Gates** (ALL must be met before any DELETE / TRUNCATE / VACUUM FULL runs):
1. Phase E1 plan exists and is committed.
2. User authorization recorded in `docs/feedback/session-154-supabase-prune-authorization.md` (single line: `Authorized by Nolan Fox 2026-04-28` or similar). If absent: STOP.
3. Snapshot script `scripts/session154_supabase_prune.py` written and dry-run tested. Each pruning step gets its own snapshot file under `backups/session-154/`. NO step runs without writing its snapshot first.
4. `make test-fast` passes after each individual prune step (catches table-disappearance regressions).

If gates met:
1. Run `scripts/session154_supabase_prune.py --execute --step <name>` once per step from the plan, sequentially.
2. After each step, re-run the E0 size query and append to `docs/feedback/session-154-supabase-size-progress.json` (size-over-time evidence).
3. Final step: `VACUUM FULL` on each pruned table (this is the only way to actually reclaim disk on Postgres — DELETE alone returns space to the table's free list, not the OS). Note: VACUUM FULL takes an exclusive table lock — should be brief at our scale but flag if any table > 100K rows.
4. Re-query DB size; confirm ≤ 1.1 GB (mandatory) and ≤ 900 MB (target).
5. Browser-verify the production app works post-prune (admin pages that read from pruned tables — `/admin/audit`, photo pages with Gemini analysis, GEDCOM triage). READ-ONLY browser checks per `.claude/rules/browser-read-only.md`.

If ANY gate fails OR ANY step regresses tests: STOP, revert from snapshot, document in plan doc.

### Phase E3 — Retention policy + monitoring (~20 min)

Add ongoing prevention so this doesn't recur:

1. **Retention policy code** in a new module (e.g., `app/retention.py` or `scripts/retention_sweep.py`):
   - `gemini_api_calls`: rows older than 90 days → archive to local JSONL → DELETE. Run weekly.
   - `change_log`: keep latest 3 versions per entity, archive + DELETE older.
   - `audit_log`: keep 365 days, archive + DELETE older. (User may want longer — flag for decision.)
   - `ml_proposals`: keep when REJECTED/ACCEPTED for 30 days then archive; KEEP all PENDING.

2. **Monitoring**: add a `/api/admin/db-size` endpoint that returns current DB size + top-10 table sizes. Optional: add a Sentry breadcrumb if size > 800 MB (warning) or > 1 GB (critical).

3. **Document as `OD-013` in `docs/ops/OPS_DECISIONS.md`** with full provenance:
   - Date, Session 154, Context (the Supabase email), Decision (the prune plan + retention policy), Tradeoffs, Monitoring thresholds, Alternatives rejected (e.g., upgrade to Pro: deferred — user wants free-tier sustainability), Breadcrumbs (OD-011, OD-012, this email).

4. **Update `.claude/rules/egress-budget.md`** → rename mentally to "Supabase budget awareness" — it currently only covers egress. Add a "Database storage" section pointing to OD-013. Don't rename the file; add a header section.

5. **BACKLOG entries** for follow-ups identified during E0/E1 that aren't fixed in this session.

Acceptance: retention script committed (with tests), `/api/admin/db-size` endpoint live + browser-verified, OD-013 written, rule updated.

### Track E file scope (parallelism)

E owns these files exclusively:
- `docs/feedback/session-154-supabase-*.md` and `*.json`
- `scripts/session154_supabase_prune.py`
- `scripts/retention_sweep.py` or `app/retention.py`
- New `/api/admin/db-size` endpoint (route file extension OR a small new file — prefer new file `app/admin_db_routes.py`)
- `docs/ops/OPS_DECISIONS.md` (OD-013 append — coordinate with main if both editing)
- `.claude/rules/egress-budget.md` (header section append)

E does NOT touch: `rhodesli_ml/gemini_extraction.py`, `scripts/session153_shadow_eval.py`, identity registry code, photos.

---

## Merge point — Phase D (main thread only, after A+B+C+E finish)

### D1 — Harry anchor repair decision (revisit)
Given Phase B1 + B2 outputs, re-evaluate the 6 gates from `docs/feedback/session-153b-harry-repair-decision.md`. If all met:
- Snapshot the Harry Fox identity to `backups/session-154/harry-fox-before-{UTC}.json`
- Draft audit_log row
- Execute the anchor move (detach the 2 wrong anchors from Harry, create new INBOX identity "Belle Isle Conservatory Young Man c.1917-1918" with those 2 faces, link to GEDCOM Harry Isaackovitz record as a *candidate*, not confirmed)
- Run structural tests
- Browser verify the Harry Fox person page + the new identity

If ANY gate still fails: do NOT execute. Document the blocker(s) in an updated decision doc.

### D2 — Full harness closeout (mandatory 9 steps + SESSION_HISTORY backfill)

1. `docs/assessments/session-154-assessment.md` — with full AI tool usage section
2. CHANGELOG: add v0.99.70 for Session 154
3. ROADMAP: add to Recently Completed
4. BACKLOG: close items resolved (shadow eval validation, Harry repair status, schema fix, Supabase prune execution, OD-013, etc.)
5. **SESSION_HISTORY backfill** (was deferred at 153b): archive sessions 143 → 153b from ROADMAP "Recently Completed" into `docs/roadmap/SESSION_HISTORY.md` (it currently stops at Session 142). Per Lesson 77: backfill SESSION_HISTORY entries first, then trim ROADMAP in the same commit. Keep entries terse (1-2 lines + version + date) to match the existing format. NEW sessions 143-153b need entries; 154 itself does NOT get archived yet (lives in ROADMAP for the next ~10 sessions).
6. `git push origin main`
7. Browser verify the 6 canonical pages (landing, people, person, compare, estimate, 404) PLUS the new `/api/admin/db-size` endpoint if Track E shipped E3
8. `git log origin/main..HEAD` must be empty
9. `bash scripts/backup-memory.sh`
10. Run `/session-review` skill

---

## Success gates

| Gate | How to check |
|---|---|
| Gemini schema drift fixed | `\d gemini_api_calls` shows `experiment_id TEXT` column |
| Shadow eval passes GEDCOM context | `grep gedcom_context scripts/session153_shadow_eval.py` shows the new kwarg + helper |
| Detroit subset passes under `candidate_with_prior` | Both photos → `place` includes Detroit/Belle Isle/Michigan at ≥medium |
| Face-ID discrepancy resolved | `docs/feedback/session-154-harry-face-id-resolution.md` exists with evidence |
| Bessie hypothesis updated | `docs/feedback/session-154-bessie-strengthening.md` has a confidence delta vs 153b |
| Belle Isle archival citation | `docs/feedback/session-154-belle-isle-citation.md` exists |
| Irving verification | `docs/feedback/session-154-irving-verification.md` has a verdict |
| Harry repair executed OR blockers documented | Either audit_log row exists OR updated decision doc |
| **Supabase E0 baseline captured** | `docs/feedback/session-154-supabase-size-baseline.json` exists with top-30 tables |
| **Supabase E1 prune plan written** | `docs/feedback/session-154-supabase-prune-plan.md` exists with target ≤900 MB and authorization gate |
| **Supabase E2 executed (if gated)** | DB size ≤1.1 GB confirmed via re-query; OR plan committed and STOP documented |
| **Supabase E3 retention shipped** | OD-013 in OPS_DECISIONS, `/api/admin/db-size` returns 200 |
| **SESSION_HISTORY archived 143-153b** | `grep "Session 143" docs/roadmap/SESSION_HISTORY.md` returns ≥1 line |
| Full harness closeout | All 10 steps done; `git log origin/main..HEAD` empty |

## Anti-patterns to avoid (from 153b post-mortem)

- ❌ Running shadow eval piped through `tail` (buffers output; looks stuck)
- ❌ Retrying Claude Chrome MCP upload_image (architecturally blocked, not transient)
- ❌ Relying on `codex exec --full-auto` for audits (stdin hangs — same bug in 3 sessions now). Use `codex exec "prompt as positional arg"` or `codex exec <<< "prompt heredoc"` instead.
- ❌ Declaring a session complete without pushing (153 left 18 commits unpushed)
- ❌ Single-source hypothesis claims without triangulation ("user-confirmed via Ancestry" → not actually confirmed)
- ❌ Over-scoped phases that can't /clear cleanly
- ❌ Pruning Supabase tables without per-step snapshots (Lesson 155 — un-merging required a 7th repair step because of un-snapshotted intermediate state)
- ❌ DELETE without VACUUM FULL (DELETE returns space to table free list, NOT to the OS — DB size on disk does not shrink)

## Codex audit invocation pattern (gpt-5.5 + xhigh)

`~/.codex/config.toml` defaults are correct: `model = "gpt-5.5"`, `model_reasoning_effort = "xhigh"`. Invoke:

```bash
codex exec "Review the changes in {files}. Flag P0/P1/P2/P3 by severity. Focus on: security, data-integrity, test coverage, regression risk."
```

If the above hangs (same 3-session bug), fall back to:

```bash
echo "Review the changes in ..." | codex exec -
# or
codex exec <<< "Review the changes in ..."
```

If still hung after 60 seconds, abandon Codex audit for that phase and substitute a Claude subagent (general-purpose, fresh context) with the same review prompt.

## Phase timing estimates (for parallelization decisions)

| Track | Phase | Solo-time |
|---|---|---|
| A | A0 schema + backoff | 10 min |
| A | A1 GEDCOM injection | 20 min |
| A | A2 iterative refinement | 30 min |
| A | A3 Detroit rerun | 10 min (+3-5 min Gemini wait) |
| A | A4 full eval | 30 min (+15-30 min Gemini wait) |
| B | B1 face-ID resolution | 15 min |
| B | B2 Bessie strengthening | 20 min |
| C | C1 Belle Isle citation | 20 min (web research) |
| C | C2 Irving verification | 15 min |
| E | E0 Size discovery | 10 min |
| E | E1 Prune plan | 30 min |
| E | E2 Execute prune (if gated) | 30 min |
| E | E3 Retention + monitoring | 20 min |
| D | D1 Harry repair | 20 min (if gates met) |
| D | D2 Closeout (incl. SESSION_HISTORY backfill) | 25 min |
| **Total** | sequential | **~5h 15min** |
| **Parallel** | A main + B/C/E in subagents | **~3h** |

## Explicit user decisions to surface

Before executing Track D1 (Harry repair), surface these to user:
- **Replacement identity label**: "Harry Isaackovich" (risky) vs "Belle Isle Conservatory Young Man c.1917-1918" (conservative). Default: conservative, per Opus audit recommendation.
- **Whether to link new identity to GEDCOM Harry Isaackovitz record** as a candidate (not confirmed). Default: yes, with `confidence=possible` and provenance note.
