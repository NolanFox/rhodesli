# Session 156 Context — Carry-Over From Session 155

**Predecessor**: Session 155 (`docs/assessments/session-155-assessment.md`, `docs/session_logs/session-155-log.md`)
**Predecessor-predecessor**: Session 154 (`docs/assessments/session-154-assessment.md`)
**Written**: 2026-05-07 at end of Session 155 by main thread
**Span goal**: Sessions 156, 157, 158 — full PRD-063 implementation arc + Harry repair shipped in 156 only.
**Critical deadline**: 2026-05-29 (Supabase free-tier restrictions kick in if DB > 1.1 GB at that date) → ~22 days from session 156 kickoff.

---

## TL;DR — what user decided in 155

After 8 days away, the user came back 2026-05-07 and gave two clear directives:

### Decision 1 — Harry Fox repair
**SHIP option (c)**: replace the misassigned `inbox_1fea75ce2caf` + `inbox_e507a54f204a` faces with new INBOX identity "Belle Isle Conservatory Young Man c.1917-1918". User added: **include a provenance note that the faces were originally misidentified as Harry Fox**. If no place exists, build one.

**Research outcome (this context file)**: existing mechanisms suffice — no new build required.
- `core/registry.py:2259 add_note(identity_id, text, author)` exists and renders on person pages via `registry.get_notes()`.
- `app/audit.py::audit_log(action, entity_id, ...)` writes to Supabase audit_log table.
- Plan: use BOTH. Notes for human-visible "originally misidentified" text on the new identity's page. Audit_log for machine-readable trail.

### Decision 2 — Supabase compliance
**REJECT the band-aid stopgap prune**. **Implement PRD-063 fully**. ~22 days to deadline; user said "we have a little bit of time so we should be able to properly fix that."

**Plan**: 3-session arc (156 → 157 → 158) at 1 session per week:
- **156** (this prompt): PRD-063 finalized at canonical path + R2 backup of GEDCOM .ged source files + new schema build in parallel + initial backfill.
- **157**: full backfill + dual-read confidence check (1 session of observation).
- **158**: cutover reads + drop v1 tables + VACUUM FULL + browser verify.

If 156 reveals unforeseen complexity, fall back to the stopgap E1 plan (commit `1e0b0fbc`) to buy more time. Keep that plan READY but unused.

---

## State at 156 kickoff (verify these first)

### Recoverable artifacts from 155 timed-out subagents
The Phase 6 recovery subagent in 155 should have landed these by 156 kickoff:
- `docs/prds/063_gedcom_mirror_efficient_redesign.md` — moved from `docs/session_context/session-155-prd-063-draft.md` with staging note stripped. ~373 lines.
- `scripts/session153_shadow_eval.py` — Track 2's AD-243 + AD-242 prompt edits applied.
- `docs/ml/ALGORITHMIC_DECISIONS.md` — AD-243 appended.
- `tests/test_shadow_eval_prompt_structure.py` — NEW from Track 2 patches.
- `docs/feedback/session-155-codex-cli-diagnosis.md` — Track 5 doc cherry-picked from worktree.
- `.claude/rules/ai-tool-audit.md` — updated with `</dev/null` invocation fix.
- `.github/workflows/test.yml` — Supabase + Gemini secrets env block (user MUST paste secrets in GitHub UI).
- `tests/test_session_artifact_paths.py` — NEW allowlist parity test.

If any of these is missing at 156 kickoff: see "Phase 156-0" below for re-recovery.

### Live state (verify with bash before starting work)
- Production: HTTP 200 (was healthy throughout 155).
- Supabase DB size: 2.22 GB (last measured pre-155 — will need fresh measurement via `/api/admin/db-size` admin call).
- Git HEAD: latest commits from 155 closeout. Should be at the recovery subagent's final commit. `git log origin/main..HEAD` MUST be empty.
- CI status: still failing on `test_identity_suggestions::test_table_exists` UNTIL the user pastes Supabase secrets into GitHub repo settings (Track 3 wired the workflow but the secrets need user action).

---

## Codex CLI fix — USE THIS NOW

**Working invocation** (Track 5 of 155, doc at `docs/feedback/session-155-codex-cli-diagnosis.md`):
```bash
codex exec "<prompt>" </dev/null
```
The trailing `</dev/null` closes stdin and prevents the 4-session hang. DO NOT use `--full-auto`. `</dev/null` redirect is what's required.

Side bug to ignore: every successful Codex run prints `failed to record rollout items: thread <uuid> not found` ERROR — benign telemetry issue.

---

## Harry repair execution path (Session 156 will execute)

User authorized (c). The execution path is encoded for the Session 156 prompt's Track A. Pre-execution, verify gates:

| Gate | Status |
|---|---|
| 1. 3009=Bessie at POSSIBLE+ across 3 sources | MET (Session 154 B2 kinship-proximity STRONG + Claude multimodal POSSIBLE + Opus POSSIBLE) |
| 2. Face IDs F + G verified | MET (`inbox_1fea75ce2caf` + `inbox_e507a54f204a`) |
| 3. Replacement label decided | MET ("Belle Isle Conservatory Young Man c.1917-1918") |
| 4. Backup snapshot saved | DO at execution time, EXTENDED scope (per Lesson 142 mitigation): identity record + version_id + downstream `ml_proposals` rows + `cross_batch_matches` referencing F+G face IDs |
| 5. audit_log row drafted | DO at execution time |
| 6. Structural tests pass | DO post-execution |

Steps:
1. **Snapshot** (extended scope per audit P1#1):
   ```bash
   mkdir -p backups/session-156/
   ```
   Write `backups/session-156/harry-fox-before-<UTC>.json` with:
   - Full Harry Fox identity record (all 7 anchors, candidate_ids, negative_ids, version_id, name, state, merge_history)
   - All `ml_proposals` rows with `source_identity_id` OR `target_identity_id` = `d74cb556-6d44-4288-ade3-1cc8fa2b45a6`
   - All `cross_batch_matches` rows referencing `inbox_1fea75ce2caf` OR `inbox_e507a54f204a`
   - Embedded SHA256 checksum + restore command
2. **Detach**: Remove `inbox_1fea75ce2caf` + `inbox_e507a54f204a` from `d74cb556-6d44-4288-ade3-1cc8fa2b45a6`.anchor_ids. Anchors 7 → 5. Bump version_id.
3. **Create new identity** with state=INBOX, name="Belle Isle Conservatory Young Man c.1917-1918", anchor_ids=[F, G].
4. **Add note** to new identity via `registry.add_note(<new-id>, text=PROVENANCE_NOTE_TEXT, author="session-156")`. The text must include: "Originally misidentified as Harry Fox in registry until 2026-05-XX. Detached via Session 156 after triangulation across 4 sources (local ML d=1.36-1.43 vs 5 Harshel anchors; Gemini 3.1 Pro multimodal blond+blue Harshel vs dark+dark center-man + ear morphology; Codex audit Session 153 0.88 confidence; independent Codex audit Session 153b same conclusion). Belle Isle Conservatory location verified via Library of Congress LC-DIG-det-4a17798. GEDCOM Harry Isaackovitz @I132506612777@ linked as candidate (NOT confirmed). Full evidence: Sessions 153, 153b, 154, 155."
5. **Link GEDCOM Harry Isaackovitz `@I132506612777@` as candidate** — use existing GEDCOM linking mechanism. Set link_state to "candidate" or equivalent (NOT "confirmed").
6. **Audit log** entry with rich metadata:
   ```json
   {
     "action": "identity_detach_replace",
     "entity_id": "<new-identity-id>",
     "metadata": {
       "originally_misidentified_as": "Harry Fox",
       "originally_misidentified_identity_id": "d74cb556-6d44-4288-ade3-1cc8fa2b45a6",
       "detached_face_ids": ["inbox_1fea75ce2caf", "inbox_e507a54f204a"],
       "evidence_sessions": [153, "153b", 154, 155, 156],
       "triangulation_sources": ["local_ml", "gemini_3.1_pro", "codex_v0.115_session_153", "codex_v0.125_session_154"],
       "belle_isle_citation": "LoC LC-DIG-det-4a17798",
       "gedcom_link": {"xref": "@I132506612777@", "state": "candidate"},
       "snapshot_path": "backups/session-156/harry-fox-before-<UTC>.json",
       "session_id": "156"
     },
     "user_email": "<admin-email>",
     "timestamp": "<ISO-8601>"
   }
   ```
7. **Run structural tests**: `pytest tests/test_data_integrity.py -q --no-header` must be green.
8. **Browser verify** (READ-ONLY per Lesson 149): Harry Fox person page (now 5 anchors), new identity person page (note rendered, GEDCOM candidate link visible).

---

## PRD-063 implementation roadmap (Sessions 156-158)

### Session 156 (this one)
1. **PRD finalization**: confirm `docs/prds/063_gedcom_mirror_efficient_redesign.md` is at canonical path (not `session_context/`). User reviews; respond to any P0 questions.
2. **R2 backup of GEDCOM .ged sources** (operational guardrail per PRD §"Operational guardrails"):
   - List the .ged files used for the 9 historical imports. Likely lives in `~/Downloads/gedcom_*` or similar — user will need to point at them.
   - Upload each to R2 under `r2://rhodesli-archive/gedcom-source-snapshots/<date>/<hash>.ged`.
   - Verify roundtrip (download + checksum) on at least 1.
3. **R2 backup of current Supabase versioned data** (per PRD migration step 1):
   - For each `gedcom_versions` row, dump corresponding rows from `gedcom_individuals`, `gedcom_records`, `gedcom_events`, `gedcom_relationships`, `gedcom_change_log` to compressed JSONL.
   - Upload to R2 under `r2://rhodesli-archive/gedcom-version-snapshots/v<N>/<table>.jsonl.gz`.
   - This is REVERSIBLE: re-import script that reconstructs Supabase rows from R2 archive, tested on 1 version on a test database.
4. **New schema build in parallel** (per PRD migration step 2):
   - Migration SQL `scripts/migrations/006_gedcom_v2_schema.sql` (number TBD per existing convention).
   - Tables: `gedcom_individuals_v2`, `gedcom_families_v2`, `gedcom_change_manifest` (replaces per-row `gedcom_change_log`).
   - Indexes: only the ones PRD §"Drop unused indexes" recommends KEEPING + new payload_hash unique index for INSERT-time dedup.
   - Migration applied via psycopg2 + us-west-2 pooler (per Lesson 175).
5. **Initial backfill** (per PRD migration step 3):
   - Read every `is_current = TRUE` row from v1 tables.
   - INSERT into v2 tables with hash-dedup.
   - Verify row counts: distinct individuals (~10-13K) should match v1's `is_current=TRUE` row count.
6. **Verification**: structural tests on v2 tables; v1 tables still serve production reads.

### Session 157
- Full backfill (any remaining current-version rows; finalize per-individual de-duplication).
- Dual-read in app code: read v2 if exists, fall back to v1. One session of observation.
- Side-by-side query timing on 5 most-frequent GEDCOM read paths (per PRD §"Speed estimate") — compare v1 vs v2.

### Session 158
- Cutover reads to v2.
- Drop v1 tables. (Snapshots + R2 archive provide rollback path.)
- VACUUM FULL on Supabase.
- Re-query DB size — confirm ≤ 1.1 GB ceiling met. Target 600-700 MB per PRD estimates.
- Browser verify all 6 canonical pages + GEDCOM-aware pages (`/tree`, `/tools/search`, person pages with GEDCOM context).
- Update OD-013 in `docs/ops/OPS_DECISIONS.md` with final outcome.

---

## Identity IDs / face IDs (carry-over from 154/155)

| Person | ID | State |
|---|---|---|
| Albert Fox | `85546ebf-75b9-4971-a9d4-b2ce2271bc19` | CONFIRMED, 197 anchors |
| Bessie Fox | `b4a43575-9312-40ec-a574-85bf4294d0af` | CONFIRMED |
| Harry Fox (registry — actually Harshel; F+G to be detached in 156) | `d74cb556-6d44-4288-ade3-1cc8fa2b45a6` | CONFIRMED, 7 anchors → 5 after detach |
| Irving Israel Fox | `7e6aae2b-2b70-4a8a-9ee5-46e2b2c16c41` | CONFIRMED, 8 anchors |
| Person 3009 (back-right Detroit, hypothesized Bessie) | `63a1c0c1-aed2-4429-9e54-9dfae1b099d4` | INBOX |

| Face | ID | Photo |
|---|---|---|
| F (center young man, 01659) | `inbox_1fea75ce2caf` | photo 01659 Belle Isle |
| G (center seated young man, 02068) | `inbox_e507a54f204a` | photo 02068 Detroit |

---

## Supabase access (carry-over)

- Direct host `db.<project_ref>.supabase.co` is IPv6-only and unreachable from many networks.
- Use pooler: `aws-0-us-west-2.pooler.supabase.com` port 5432 (session) or 6543 (transaction).
- Username: `postgres.fvynibivlphxwfowzkjl`. Password: `SUPABASE_DB_PASSWORD` env.
- Lesson 175 in `tasks/lessons.md`.

---

## Outstanding work — Session 156 task list (priority order)

| # | Task | Track | Time est | Blocked on |
|---|---|---|---|---|
| 1 | Verify recovery subagent's commits landed | 156-0 | 5 min | — |
| 2 | Re-recover anything missing from 155 timeouts | 156-0 | 0-30 min | depends |
| 3 | Harry repair execution per option (c) with provenance note | 156-A | ~45 min | gate verification |
| 4 | PRD-063 final review + canonical-path confirmation | 156-B1 | 15 min | — |
| 5 | R2 backup GEDCOM .ged sources | 156-B2 | 30 min | user pointing at .ged file locations |
| 6 | R2 backup current Supabase versioned data | 156-B3 | 60 min | — |
| 7 | New v2 schema build + apply | 156-B4 | 30 min | — |
| 8 | Initial backfill + verification | 156-B5 | 60 min | — |
| 9 | CI verification (after user pastes secrets) | 156-C | 5 min | user action |
| 10 | Closeout (assessment, CHANGELOG, push, verify, memory backup, /session-review) | 156-D | 30 min | all of the above |

**Total time estimate**: 4-5 hours of Claude time + ~30 min of user time (verbatim authorization for Harry execution + paste secrets).

---

## Workflow preferences (carry-over)

- READ-ONLY on production browsers (`.claude/rules/browser-read-only.md`).
- /clear between phases at 300+ transcript lines (Opus 4.7 MRCR drops fast).
- Commit atomically per phase. `make test-fast` before each commit.
- Parallelize via worktree subagents — but plan token-budget per subagent (Lesson 178). Don't dispatch a 4-phase subagent including a large design phase.
- Subagent worktree should default `.claude/session_mode.txt` to `interactive` — current 600-line block fires on turn 0 because orchestrator's system-reminder payload is inherited.
- Codex CLI: `codex exec "<prompt>" </dev/null`. NEVER `--full-auto`.

---

## DO NOT repeat (regression list from 155 closeout)

- ❌ Run `scripts/merge.sh` from a sub-worktree cwd. (Guard is in place; verify it fires.)
- ❌ Edit hook-blocked files at high transcript line counts without /clear first. The pre-work-clear-gate hook blocks at 600+ transcript lines unless session_mode is `interactive`.
- ❌ Dispatch a subagent with a 4+ phase plan including a large design phase. (Lesson 178.) Split into 2 subagents.
- ❌ Trust paraphrased thresholds — quote the source verbatim. (Audit P0#1 of 155.)
- ❌ Claim "snapshotted PK sets" or "full reversibility" without checking the source plan/lesson. (Audit P1#2 + P2#1.)
- ❌ Pay for Gemini API calls without explicit user authorization on cost. Phase 2C/2D Detroit reruns are deferred until user requests.
- ❌ Drop production tables without R2 archive verification first. (PRD-063 §"Operational guardrails".)
