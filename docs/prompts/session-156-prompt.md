# Session 156 — Harry Fox Repair Execution + PRD-063 Implementation (Day 1 of 3)

**Mode**: Implementation
**Predecessor**: Session 155 (`docs/assessments/session-155-assessment.md`, `docs/session_logs/session-155-log.md`)
**Context file (MANDATORY first read)**: `docs/session_context/session-156-context.md`
**Critical deadline**: 2026-05-29 — Supabase free-tier restrictions kick in if DB > 1.1 GB. Today is 2026-05-07 → ~22 days. This session is **Day 1 of 3** of the PRD-063 full-implementation arc.

**Why this session exists**: User decided in 155 (after audit-corrected analysis):
1. **Harry Fox repair**: SHIP option (c) — replace misassigned faces with conservative descriptive identity, with provenance note that they were originally misidentified as Harry. Existing `registry.add_note()` + `audit_log` mechanisms suffice.
2. **Supabase compliance**: REJECT the band-aid stopgap prune. Implement PRD-063 (efficient redesign) FULLY across 3 sessions. This is Session 156, the first.

## Setup

```bash
echo "156" > .claude/current_session.txt
echo "implementation" > .claude/session_mode.txt
source venv/bin/activate
bash scripts/harness-check.sh             # warn-only on doc-cap is acceptable
make test-fast                             # Baseline — must be green
git log origin/main..HEAD                  # MUST be empty
git pull origin main                       # Safety
git status --short                         # Must show nothing meaningful
```

## Required first reads (in order)

1. `docs/session_context/session-156-context.md` — full carry-over from 155, Harry execution path, PRD-063 roadmap.
2. `docs/session_logs/session-155-log.md` — research, iteration, failures from 155 (8-day arc).
3. `docs/feedback/session-155-user-decisions-analysis.md` v2 — the audit-corrected recommendation analysis.
4. `docs/prds/063_gedcom_mirror_efficient_redesign.md` — the recovered Track 1 PRD draft (verify it's at the canonical path; if at `docs/session_context/session-155-prd-063-draft.md` instead, see Phase 156-0 below).
5. `docs/feedback/session-155-codex-cli-diagnosis.md` — working Codex invocation.
6. `docs/feedback/session-154-supabase-bloat-root-cause.md` — E0.5 evidence base for PRD-063.
7. `docs/feedback/session-154-supabase-prune-plan.md` (commit `1e0b0fbc`) — the BAND-AID we're rejecting; keep it READY in case 156 falls behind schedule.
8. `tasks/lessons.md` — lessons 173-178 are critical.

## Non-negotiable rules

1. READ-ONLY on production browsers (`.claude/rules/browser-read-only.md`).
2. **Codex CLI invocation**: `codex exec "<prompt>" </dev/null`. NEVER `--full-auto`. (4-session hang fixed in 155 Track 5.)
3. Commit atomically per phase. /clear between phases at 300+ transcript lines.
4. Every ML decision gets an AD entry. This session: AD-244 (PRD-063 schema design) likely. Possibly AD-245 (Harry repair detach action).
5. Every IRREVERSIBLE step on production data is gated on user authorization message (verbatim, naming the step). DEFAULT = STOP.
6. R2 backup of GEDCOM source files MUST happen BEFORE any DROP / DELETE on Supabase tables. (PRD-063 §"Operational guardrails".)
7. Per-step snapshots BEFORE each mutation, with embedded SHA256 + restore command. (Lessons 155, 156.)
8. `make test-fast` before every commit.

## CRITICAL — Concurrent genealogy session resilience

**The user may be running a parallel genealogy session** (in another Claude Code instance, an Ancestry browser session, or admin UI on production) while this session runs. That session may be:
- Confirming identities (state INBOX → CONFIRMED)
- Merging identities
- Editing GEDCOM links (`gedcom_face_links` writes)
- Re-importing GEDCOM (would create new `gedcom_versions` row)
- Adding/editing notes
- Confirming or rejecting ML proposals

This session's mutations MUST NOT collide with the genealogy session's. Specific resilience requirements:

### R1 — Coordination marker file
Before any mutation, create `.claude/parallel_session_active` (per CLAUDE.md "Parallel sessions: create `.claude/parallel_session_active` to block main commits"). At end of session, remove it. The PreToolUse hook will block main-branch commits while it exists, forcing the parallel session to coordinate. **However**: this session DOES need to commit to main, so the protocol is: hold the marker only during the IRREVERSIBLE Track A mutation window (Phases A2-A4) and during Track B5 backfill, and release immediately after. Any other commits happen WITHOUT the marker.

### R2 — Optimistic concurrency on identity writes (Track A)
- Use `save_registry()` (canonical save function) — it already implements AD-230 optimistic concurrency: pre-fetches `version_id` from Supabase before upserting, skips stale writes.
- Before Phase A3 (detach + create), pre-fetch Harry Fox `version_id` from Supabase. Compare to local. If different (genealogy session edited Harry), STOP, re-snapshot with the current state, restart Track A. Do NOT blindly overwrite genealogy session's edits.
- After Phase A3, verify the new identity didn't collide with a name conflict (if genealogy session created an identity with the same name, append `-` and the timestamp suffix to the name to disambiguate).

### R3 — Track B (PRD-063) is additive-only on v1
Phases B1-B5 are READ-ONLY on v1 tables and CREATE-ONLY on v2 tables:
- B1 (PRD review): no DB writes.
- B2 (R2 backup of .ged sources): no DB writes; reads from local filesystem only.
- B3 (R2 backup of Supabase versioned data): READ-ONLY queries against v1 tables. Snapshot is a point-in-time copy. **If the genealogy session writes to v1 mid-snapshot, the snapshot reflects state at query time — that's fine. Document the timestamp range in the manifest.**
- B4 (v2 schema CREATE TABLE): purely additive. v1 tables untouched. Genealogy session's writes to v1 keep flowing.
- B5 (initial backfill): READ-ONLY on v1 (`SELECT ... WHERE is_current=TRUE`), INSERT into v2 (with `ON CONFLICT (payload_hash) DO NOTHING`). Genealogy session's NEW writes to v1 happen DURING our backfill — those rows won't appear in v2 yet but will be picked up in Session 157's "full backfill + dual-read confidence check." Document the cutover timestamp in B5's commit.

**v1 tables remain authoritative for production reads through Sessions 156-157.** Cutover to v2 doesn't happen until Session 158, AFTER dual-read confidence in 157.

### R4 — `gedcom_face_links` write coordination (Track A4)
The Harry repair adds a GEDCOM link as "candidate." If the genealogy session is also editing `gedcom_face_links`:
- Use `INSERT ... ON CONFLICT (identity_id) DO UPDATE SET link_state='candidate' WHERE existing.link_state != 'confirmed'` — i.e., do NOT downgrade a confirmed link to candidate if genealogy session got there first.
- If `gedcom_face_links` already has a confirmed link for the new identity (unlikely but possible), STOP and surface to user. Do NOT silently overwrite.

### R5 — Audit log namespace
All writes from this session use `user_email = "session-156"` (or actual admin email if available) with `metadata.session_id = "156"`. The genealogy session would use a different actor. This makes post-session audit queries trivially filterable.

### R6 — Pre-flight check at every phase boundary
Before EACH of Phases A1, A2, A3, A4, A5, B1, B2, B3, B4, B5: re-run a quick consistency check:
```bash
# Check Harry Fox version_id hasn't moved unexpectedly
python -c "
from app.supabase_data import get_supabase_client
sb = get_supabase_client()
r = sb.table('identities').select('version_id, anchor_ids').eq('identity_id', 'd74cb556-6d44-4288-ade3-1cc8fa2b45a6').execute()
print(f'Harry Fox: version_id={r.data[0][\"version_id\"]}, anchor_count={len(r.data[0][\"anchor_ids\"])}')
"
```
If `anchor_count` deviates from 7 (pre-Phase A3) or 5 (post-Phase A3 expected) at unexpected times: investigate before continuing.

### R7 — User cancellation handling
If the user notes mid-session that they'll be running a genealogy session:
- Pause Track A immediately (any phase between A2 and A4 — the irreversible window).
- Snapshot current state.
- Set `.claude/parallel_session_active`.
- Wait for explicit "resume" message from user.
- On resume: re-verify Harry Fox state matches snapshot (or note the divergence and re-plan).

### R8 — R2 namespace isolation
Track B's R2 paths use date + `session-156` to prevent overwrite if genealogy session also runs an R2 backup:
- Sources: `r2://rhodesli-archive/gedcom-source-snapshots/2026-05-07-session-156/<...>`
- Supabase versions: `r2://rhodesli-archive/gedcom-version-snapshots/2026-05-07-session-156/v<N>/<table>.jsonl.gz`

Genealogy session would use its own date+session prefix. R2 keys never collide.

### R9 — Failure modes specifically introduced by concurrency
- **Mid-snapshot v1 write**: Track B3's snapshot reflects query-time state. Acceptable; documented in manifest.
- **Mid-backfill v1 write**: Track B5 backfills only `is_current=TRUE` rows visible at start time. Newer rows picked up in 157.
- **Genealogy session re-imports GEDCOM** mid-156: creates new `gedcom_versions` row. Track B3 backup wouldn't include it. Track B5 backfill wouldn't include it. **Recovery**: 157's full backfill picks it up. Document this risk in B3's commit body.
- **Harry Fox edited mid-A3**: AD-230 optimistic concurrency catches this. STOP, re-snapshot, restart A.
- **Same-name identity created mid-A3**: append timestamp suffix to disambiguate.

## Parallelization plan

```
┌─────────────────────────────────────────────────────────────────────┐
│ Track A — Harry Fox repair execution (MAIN thread, gated)           │
│   Phases A1 (gate verify), A2 (snapshot), A3 (detach + create new), │
│   A4 (note + audit_log + GEDCOM link), A5 (verify + commit)         │
│                                                                     │
│ Track B — PRD-063 implementation Day 1 (worktree subagent)          │
│   Phases B1 (canonical path), B2 (R2 backup .ged sources),          │
│   B3 (R2 backup current Supabase data), B4 (v2 schema build),       │
│   B5 (initial backfill + verify)                                    │
│                                                                     │
│ Track C — CI verification (MAIN thread, gated on user secrets)      │
│                                                                     │
│ Track E — GEDCOM upload UAT (MAIN thread, after Track B5)           │
│   Phases E1 (file path), E2 (baseline), E3 (upload via v1 path),    │
│   E4 (4 verification points), E5 (writeup + commit)                 │
│                                                                     │
│ Track F — Location-correctness UAT (MAIN thread, after A+E)         │
│   Phases F1 (identify photos), F2 (read current), F3 (verify),      │
│   F4 (fix gated on user auth), F5 (verify all surfaces), F6 (commit)│
│                                                                     │
│ Track D — Closeout (MAIN thread, after A+B+E+F finish)              │
└─────────────────────────────────────────────────────────────────────┘
```

Track A and Track B run in parallel. Track E runs sequentially after Track B5 (depends on v2 backfill having a baseline). Track C blocks on user action.

---

## Phase 156-0 — Recovery verification (MAIN thread, ~5-30 min)

Before any new work, verify the Phase 6 recovery from 155 actually landed:

```bash
# Verify these exist on origin/main:
ls docs/prds/063_gedcom_mirror_efficient_redesign.md
ls scripts/session153_shadow_eval.py        # should have AD-243 prompt edits
ls tests/test_shadow_eval_prompt_structure.py
ls tests/test_session_artifact_paths.py
grep "</dev/null" .claude/rules/ai-tool-audit.md
ls docs/feedback/session-155-codex-cli-diagnosis.md
grep "secrets.SUPABASE" .github/workflows/test.yml
```

If any is missing:
- For `docs/prds/063_*` and the staging note: `mv docs/session_context/session-155-prd-063-draft.md docs/prds/063_gedcom_mirror_efficient_redesign.md`, then strip the first ~14 lines (the staging note block at the top).
- For Track 2 patches: run `python docs/feedback/session-155-track2-patches.py` from the worktree where it lives, then verify diff and commit.
- For Track 5 doc: `git cherry-pick bc69a98f` from the original Track 5 branch.
- For Track 3 (CI env + parity test): re-launch a small subagent OR do directly from main thread (it's small).

Commit any recovery work atomically. `make test-fast` must be green.

---

## Track A — Harry Fox repair execution (MAIN thread)

### Phase A1 — Gate verification (~10 min)

Before any mutation, verify these gates from 153b are met (the audit P1#1 from 155 said "ALL must be true before mutation"):

| Gate | How to verify |
|---|---|
| 1. 3009=Bessie at POSSIBLE+ across 3 sources | Read `docs/feedback/session-154-bessie-strengthening.md` final-confidence section. Should say POSSIBLE-GOOD ~55% with kinship-proximity STRONG signal. |
| 2. Face IDs F+G verified | Read `docs/feedback/session-154-harry-face-id-resolution.md`. Should name `inbox_1fea75ce2caf` (F, photo 01659) and `inbox_e507a54f204a` (G, photo 02068) as the definitive 2 face IDs. |
| 3. Replacement label decided | "Belle Isle Conservatory Young Man c.1917-1918" per 153b Opus audit. |
| 4. Backup snapshot scope decided | EXTENDED scope per audit P1#1 — see Phase A2. |
| 5. Audit_log row drafted | Drafted in Phase A4. |
| 6. Structural tests pass | Verified in Phase A5. |

If any gate fails to verify: STOP, document, do not proceed.

### Phase A2 — Snapshot (~5 min, EXTENDED scope per Lesson 142 mitigation)

```bash
mkdir -p backups/session-156/
TS=$(date -u +%Y%m%dT%H%M%SZ)
```

Write `backups/session-156/harry-fox-before-${TS}.json` containing (use a small Python script, not by hand):

1. Full Harry Fox identity record (`d74cb556-6d44-4288-ade3-1cc8fa2b45a6`) — all 7 anchor_ids, candidate_ids, negative_ids, version_id, name, state, merge_history.
2. All `ml_proposals` rows where `source_identity_id` OR `target_identity_id` = `d74cb556-6d44-4288-ade3-1cc8fa2b45a6` (query Supabase).
3. All `cross_batch_matches` rows referencing face_ids `inbox_1fea75ce2caf` OR `inbox_e507a54f204a` (query Supabase).
4. Embedded SHA256 of the JSON payload + a one-liner restore command in the file's `_meta` field.

Verify the snapshot:
```bash
python -c "import json; d = json.load(open('backups/session-156/harry-fox-before-${TS}.json')); print('snapshot keys:', list(d.keys()))"
```

Commit: `chore(session-156): pre-repair snapshot of Harry Fox identity (Track A2)`. Snapshot file IS committed (it's small and the audit trail value outweighs the bytes).

### Phase A3 — Detach + create new identity (~10 min)

Use the Supabase REST client + `core/registry.py` API:

1. Load the registry, find Harry Fox identity.
2. Remove `inbox_1fea75ce2caf` + `inbox_e507a54f204a` from `anchor_ids` (anchors 7 → 5). Bump `version_id`. Update `updated_at`.
3. Create new identity:
   ```python
   new_id = registry.create_identity(
       name="Belle Isle Conservatory Young Man c.1917-1918",
       state="INBOX",
       anchor_ids=["inbox_1fea75ce2caf", "inbox_e507a54f204a"],
       candidate_ids=[],
       negative_ids=[],
   )
   ```
4. Use `save_registry()` (canonical save function — not `.save()` directly per `.claude/rules/data-sync.md`).
5. Verify via re-load: Harry has 5 anchors; new identity has 2 anchors with the right face_ids.

### Phase A4 — Provenance note + audit_log + GEDCOM link (~10 min)

1. **Note via `registry.add_note(new_id, text=PROVENANCE_TEXT, author="session-156")`** where `PROVENANCE_TEXT` is:

   > **Originally misidentified as Harry Fox** in registry until 2026-05-XX. Detached via Session 156 after triangulation across 4 sources confirmed these faces are NOT Harshel Iosha Fox (the actual person behind the "Harry Fox" identity):
   >
   > 1. **Local ML** (Session 153): pairwise distance 1.36-1.43 vs 5 Harshel anchors — different-person territory.
   > 2. **Gemini 3.1 Pro multimodal** (Session 153): blond+blue-eyed Harshel from naturalization photo vs dark+dark center-man + ear morphology = morphologically incompatible.
   > 3. **Codex audit** (Session 153, gpt-5.4): 0.88 confidence "NOT Harshel."
   > 4. **Independent Codex audit** (Session 153b, fresh context): same conclusion.
   >
   > **Belle Isle Conservatory** location verified via Library of Congress LC-DIG-det-4a17798 (Detroit Publishing Co. interior, 1905) + 6 corroborating sources. **Date range** c.1917-1918 from Albert Fox GEDCOM RESI Detroit 1917 + draft induction 7 Jun 1918.
   >
   > **GEDCOM link**: Harry Isaackovitz `@I132506612777@` linked as **candidate** (NOT confirmed). No reference photo of Harry Isaackovitz exists; identification beyond "man at Belle Isle event" is not possible without further evidence (1910s Bessie reference photo OR third Belle Isle frame).
   >
   > **Full evidence trail**: Sessions 153, 153b, 154, 155, 156. See `docs/feedback/session-153-detroit-deep-dive.md`, `docs/feedback/session-153-harry-isaackovitz-breakthrough.md` (note: retracted in 153b), `docs/feedback/session-153b-bessie-validation.md`, `docs/feedback/session-153b-center-man-honest.md`, `docs/feedback/session-154-harry-face-id-resolution.md`, `docs/feedback/session-154-bessie-strengthening.md`, `docs/feedback/session-154-belle-isle-citation.md`.

2. **GEDCOM link** as candidate: use the existing GEDCOM linking endpoint or direct Supabase write to `gedcom_face_links` (or whatever the linking table is — verify via existing AD-160 implementation). Set link_state = "candidate" or equivalent. NOT "confirmed".

3. **Audit log** entry (Supabase `audit_log` table):
   ```python
   audit_log(
       action="identity_detach_replace",
       entity_id=new_identity_id,
       user_email=admin_email,
       metadata={
           "originally_misidentified_as": "Harry Fox",
           "originally_misidentified_identity_id": "d74cb556-6d44-4288-ade3-1cc8fa2b45a6",
           "detached_face_ids": ["inbox_1fea75ce2caf", "inbox_e507a54f204a"],
           "evidence_sessions": [153, "153b", 154, 155, 156],
           "triangulation_sources": ["local_ml", "gemini_3.1_pro", "codex_v0.115_session_153", "codex_v0.125_session_154"],
           "belle_isle_citation": "LoC LC-DIG-det-4a17798",
           "gedcom_link": {"xref": "@I132506612777@", "state": "candidate"},
           "snapshot_path": f"backups/session-156/harry-fox-before-{TS}.json",
       },
   )
   ```

### Phase A5 — Structural tests + browser verify + commit (~10 min)

1. Run `pytest tests/test_data_integrity.py -q --no-header` — must be green.
2. Run `pytest tests/test_audit_logging.py -q --no-header` if it exists — must be green.
3. Run `make test-fast` — must be green.
4. Browser-verify (READ-ONLY per Lesson 149) on production:
   - Harry Fox person page: should now show 5 anchors. Note the specific anchor_ids displayed should NOT include `inbox_1fea75ce2caf` or `inbox_e507a54f204a`.
   - New identity person page (look it up by name "Belle Isle Conservatory Young Man c.1917-1918" or by the new ID): should show 2 anchors (F + G), the provenance note rendered, the GEDCOM Harry Isaackovitz candidate link.
5. Commit: `feat(session-156): Harry Fox repair — detach + create conservative-label identity (Track A)`. Body summarizes the action with new identity ID + audit_log row reference.

---

## Track B — PRD-063 Day 1 implementation (WORKTREE SUBAGENT)

Launch as a worktree subagent at session start so it runs parallel to Track A.

### Phase B1 — PRD canonical path verification (~15 min)

1. If `docs/prds/063_gedcom_mirror_efficient_redesign.md` doesn't exist but `docs/session_context/session-155-prd-063-draft.md` does, do the move + strip-staging-note.
2. Read the PRD end-to-end. Verify:
   - All 10 sections present (problem, current state evidence, functional requirements, storage-reduction proposal, speed estimate, migration plan, operational guardrails, out of scope, open questions, plus title block).
   - Quantitative claims cite E0.5 source.
   - ≤ 300 lines (split if over per `.claude/rules/doc-size-enforcement.md`).
3. Surface any P0 questions in the PRD's "Open Questions" section to the user — main thread will route them.
4. Commit any final tightening: `docs(session-156): PRD-063 final review (Track B1)`.

### Phase B2 — R2 backup of GEDCOM .ged source files (~30 min)

**User dependency**: the .ged source files probably live at `~/Downloads/gedcom_*` based on past session notes. Main thread should ask user to confirm path. Subagent can stage the upload script meanwhile.

1. Write `scripts/session156_r2_backup_gedcom_sources.py`:
   - Lists .ged files at user-specified path.
   - For each: compute SHA256, upload to R2 at `r2://rhodesli-archive/gedcom-source-snapshots/2026-05-07/<filename>-<sha8>.ged`.
   - Manifest at `r2://rhodesli-archive/gedcom-source-snapshots/2026-05-07/manifest.json` with all entries.
   - Verify roundtrip on at least 1 file (download + checksum check).
2. Run script (with user-confirmed path).
3. Commit: `chore(session-156): R2 backup GEDCOM .ged source files (Track B2)`. Manifest URL referenced in commit body.

### Phase B3 — R2 backup current Supabase versioned data (~60 min)

1. Write `scripts/session156_r2_backup_supabase_versions.py`:
   - For each `gedcom_versions` row: dump corresponding rows from `gedcom_individuals`, `gedcom_records`, `gedcom_events`, `gedcom_relationships`, `gedcom_change_log` to gzipped JSONL.
   - Upload to R2 at `r2://rhodesli-archive/gedcom-version-snapshots/v<N>/<table>.jsonl.gz`.
   - Plus a per-version manifest: `r2://...../v<N>/manifest.json` with row counts + checksums.
2. Run script. Total expected size: ~1.5-2 GB compressed (this is the WHOLE versioned mirror — that's the point; we're archiving before pruning).
3. Test reversibility: write a small re-import script that reconstructs Supabase rows from R2 archive for ONE version on a TEST database. Verify row counts match.
4. Commit: `chore(session-156): R2 backup current Supabase versioned data (Track B3)`. Manifest URLs in body. Reversibility-test result documented.

### Phase B4 — New v2 schema build (~30 min)

1. Write migration `scripts/migrations/006_gedcom_v2_schema.sql` (verify next number via `ls scripts/migrations/ | sort`):
   - `CREATE TABLE gedcom_individuals_v2 (...)` — single canonical row per `gedcom_id`.
   - `CREATE TABLE gedcom_families_v2 (...)`.
   - `CREATE TABLE gedcom_change_manifest (...)` — replaces per-row `gedcom_change_log` with one row per import.
   - `CREATE UNIQUE INDEX idx_gedcom_individuals_v2_payload_hash ...` — for INSERT-time dedup.
   - Include only the indexes PRD §"Drop unused indexes" recommends KEEPING.
   - Add comments referencing PRD-063 sections.
2. Apply via psycopg2 + us-west-2 pooler (per Lesson 175):
   ```bash
   python -c "import psycopg2; ..."
   ```
3. Verify schema via `\d gedcom_individuals_v2` (or equivalent SELECT against `information_schema`).
4. Commit: `feat(session-156): PRD-063 v2 schema build (Track B4)`.

### Phase B5 — Initial backfill + verification (~60 min)

1. Write `scripts/session156_backfill_gedcom_v2.py`:
   - Read every `is_current = TRUE` row from v1 `gedcom_individuals` (paginate per Lesson 173).
   - Compute `payload_hash` for each.
   - INSERT into `gedcom_individuals_v2` with `ON CONFLICT (payload_hash) DO NOTHING` (skip duplicates).
   - Same for `gedcom_families_v2`.
   - Build `gedcom_change_manifest` with one row per existing `gedcom_versions` row (summary metadata only).
2. Run script in --dry-run mode first. Verify expected row counts.
3. Run with `--execute`.
4. Verification queries:
   - `SELECT COUNT(*) FROM gedcom_individuals_v2;` should approximate `SELECT COUNT(DISTINCT gedcom_id) FROM gedcom_individuals WHERE is_current=TRUE;` (the de-duplication factor).
   - `SELECT pg_size_pretty(pg_total_relation_size('gedcom_individuals_v2'));` should be much smaller than v1 (~5-10x).
5. Commit: `feat(session-156): PRD-063 initial backfill to v2 tables (Track B5)`.

### Track B return value

At end of run, return:
- B1 status (PRD location + line count)
- B2 R2 backup manifest URL + roundtrip verification result
- B3 R2 backup manifest URLs + reversibility test result
- B4 schema migration commit hash
- B5 backfill row counts + final v2 size estimate
- `make test-fast` final state
- Worktree path + branch

---

## Track C — CI verification (MAIN thread, gated on user)

If `.github/workflows/test.yml` was wired in 155 Track 3 recovery (verify in Phase 156-0):

1. Surface to user: "Paste `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_DB_PASSWORD`, `GEMINI_API_KEY` into GitHub repo settings → Secrets → Actions."
2. After user confirms paste, trigger a CI run via dummy push or `gh workflow run`.
3. Wait up to 5 min for completion.
4. If green: declare 156-C done. Update CI-SUPABASE-ENV BACKLOG entry to CLOSED.
5. If still red: diagnose via `gh run view <id> --log-failed`.

---

## Track E — GEDCOM upload UAT (MAIN thread, after Track B5)

The user did genealogical research on the Fox family during the 8-day gap and has a NEW Fox-family GEDCOM ready to upload. **This serves as the live UAT for PRD-063 Day 1 work.** Four explicit verification points (per user message during 155 closeout):

### E1 — User points at the new GEDCOM (~5 min)

User shares the path to the latest Fox-family `.ged` file (likely `~/Downloads/gedcom_*` based on past sessions). Verify:
- File exists, parses cleanly (`python -c "from rhodesli_ml.importers.gedcom_parser import parse_gedcom; p = parse_gedcom('<path>'); print(f'individuals: {len(p.individuals)}, families: {len(p.families)}')"`)
- Compute SHA256 of the file. Add to R2 backup (Track B2 manifest).

### E2 — Pre-import baseline measurement (~5 min)

BEFORE uploading, capture baseline:
- Supabase total DB size (via `/api/admin/db-size` admin call).
- Row counts of `gedcom_individuals_v2`, `gedcom_families_v2` (from Track B5's initial backfill).
- `make test-fast` green.

### E3 — Upload the new GEDCOM (~30 min)

**Decision point**: which path does the upload take?
- Path α — **upload via the EXISTING v1 importer** (production code path). v2 tables get backfilled from v1 in Session 157. This is SAFE because v1 is still authoritative through 157.
- Path β — **upload directly to v2 schema** via the new INSERT-time-dedup path. Requires the v2 importer to be written (not in scope for 156). Defer.

**Choose Path α for 156.** The new GEDCOM goes through the existing v1 importer. v2 catches up in 157.

Steps:
1. Run the existing GEDCOM import script with the new `.ged` file path. Whatever the canonical command is — likely something like `python scripts/import_gedcom.py --file <path>`.
2. Watch for errors. If the importer hits the bloat-related issue (Lesson 163: "GEDCOM versioned importer doesn't scale to 175K+ rows"), STOP and surface to user. We may need to fall back to the stopgap E1 prune to make room before the upload completes.
3. After import succeeds: re-measure Supabase DB size. **EXPECTED**: size grows by some amount (the new version is a full snapshot under v1's design — that's the bug we're fixing). Document the delta.

### E4 — Verify the four UAT points (per user)

After the upload + Track B5 backfill catches up:

1. **"Make it easier to upload a new one"** — verify the Track B's R2-backup-and-archive flow makes upload friction lower. Specifically: was the upload more or less reversible than before? Did we have a clean backup point if it failed mid-import? Document outcome at `docs/feedback/session-156-gedcom-upload-uat.md`.

2. **"Make it easier to understand the changes for a specific family between GEDCOM versions"** — pick one family (the Fox family is the obvious choice). Run a query against `gedcom_change_manifest` (the new v2 per-import summary table) to find what changed for Fox individuals between previous version and the new one. Compare to what `gedcom_change_log` would show under v1 (the per-row noise). Document the UX delta.

3. **"Make sure we've fixed the issue of the size growing rapidly"** — measure: total DB size before upload, after upload (under v1), after v2 backfill catches up. Compute the per-row growth factor. **EXPECTED**: under v1 the new version adds ~250-300 MB (full snapshot). Under v2 the new version should add only the delta rows (orders of magnitude smaller). If v2 adds anywhere near v1's growth: regression — escalate.

4. **"Make sure we haven't broken Supabase"** — comprehensive smoke test:
   - `/api/admin/db-size` returns expected values (no error)
   - `/health` returns 200 with `supabase: "ok"` (currently shows `supabase: "skipped"` — investigate why)
   - Browser-verify (READ-ONLY): person pages with GEDCOM context render correctly, `/tree` page renders, `/tools/search` rule-based parser still works
   - Run `pytest tests/test_gedcom_*.py -q --no-header` — must be green
   - Run `pytest tests/test_data_integrity.py -q --no-header` — must be green

### E5 — UAT writeup + commit

`docs/feedback/session-156-gedcom-upload-uat.md` with all 4 verification outcomes. If any FAIL: document, surface to user, and recommend either rollback (snapshot exists) or escalation to Session 157.

Commit: `feat(session-156): GEDCOM upload UAT (Track E)`. Body: 4-line summary of the 4 UAT outcomes.

---

## Track F — Location-correctness UAT (MAIN thread, after Tracks A + B)

**User requirement** (added 2026-05-07 mid-closeout): verify that the Detroit photos AND the Asheville NC photo with Victoria + Victor are returning the correct location AND that location is represented in the app.

### F1 — Identify the photos in scope (~10 min)

**Detroit photos** (known from Session 153/153b/154 work):
- `inbox_fox-charlie-001_204_02068_p_13akf5twbc3600` — Belle Isle Conservatory, Detroit, c.1917-1918
- `inbox_fox-charlie-001_3_01659_p_13akf5twbc1045` — same event, second frame
- Possible third frame: `91b6f6b296e93a60` (referenced in `docs/session_context/session-154-context.md` line 25, "may be a third frame — not in Supabase under that exact string, needs investigation"). Investigate.

**Asheville NC photo** with Victoria + Victor: photo_id NOT yet known. To find it:
```python
# Find identities matching Victoria / Victor
sb = get_supabase_client()
ids = sb.table("identities").select("identity_id, name").or_("name.ilike.%Victoria%,name.ilike.%Victor%").execute()
victoria_ids = [r["identity_id"] for r in ids.data if "victoria" in r["name"].lower()]
victor_ids = [r["identity_id"] for r in ids.data if r["name"].lower().startswith("victor") and "victoria" not in r["name"].lower()]

# Find photos where BOTH a Victoria face AND a Victor face appear
# Query photo_faces joined to identities; co-occurrence
# Filter to photos with >0 Victoria face_ids AND >0 Victor face_ids
# Should return a small set; user can confirm which is the Asheville photo
```

If the search returns multiple candidates, ask user to confirm the right photo_id. Otherwise pick the single match.

### F2 — Read current stored location for each photo (~10 min)

For each photo in scope:
1. Query `date_labels` Supabase table for the photo's location data:
   ```python
   sb.table("date_labels").select("data").eq("photo_id", "<photo_id>").execute()
   ```
   Look at `data.gemini_raw_location.place` and `data.gemini_calibrated_location.place` (or whatever the canonical field is — verify in the schema).
2. Query `photo_locations` geo table (Session 144b dual-write):
   ```python
   sb.table("photo_locations").select("*").eq("photo_id", "<photo_id>").execute()
   ```
3. Render the public photo page and read the location displayed:
   ```bash
   curl -s https://rhodesli.nolanandrewfox.com/photo/<photo_id> | grep -i "location\|detroit\|asheville\|belle isle"
   ```

### F3 — Verify expected vs actual

Build a table of expected vs actual:

| Photo ID | Expected location | `date_labels.data.location` | `photo_locations` | Public page | Verdict |
|---|---|---|---|---|---|
| inbox_..._02068_... | Detroit, MI (Belle Isle) | ? | ? | ? | ? |
| inbox_..._01659_... | Detroit, MI (Belle Isle) | ? | ? | ? | ? |
| 91b6f6b296e93a60 (if found) | Detroit, MI | ? | ? | ? | ? |
| (Asheville Victoria+Victor) | Asheville, NC | ? | ? | ? | ? |

**Note from Session 153/154 evidence**: Phase A3 of Session 154 (Detroit subset rerun) showed photo 02068 was being predicted as NYC by Gemini across all 3 prompt variants. The CURRENT stored location may also be NYC — that's the bug we need to find + fix.

For Session 153b: photo 02068 was the photo where Session 153 had previously over-claimed identification. Its production `date_labels.gemini_raw_location` was NEVER corrected per Session 153b prompt (user explicitly skipped that fix). So the stored location for 02068 is likely STILL NYC.

### F4 — Fix incorrect locations (gated on user authorization)

For each photo where Verdict = MISMATCH:
1. Identify the correct location from external evidence:
   - Detroit photos: GOOD-confirmed via LoC LC-DIG-det-4a17798 + Albert Fox GEDCOM RESI Detroit 1917 (Session 154 Track C1).
   - Asheville: confirm with user — what's the evidence basis? Family knowledge + GEDCOM if available.
2. Write a corrective `date_labels` row (or update existing):
   - Set `data.gemini_raw_location.place` = correct city
   - Set `data.gemini_raw_location.confidence` = "high" (we have triangulated evidence)
   - Set `data.gemini_raw_location.source_type` = "human_corrected" (or whatever the existing convention is — verify in `app/photo_routes.py` or admin endpoints)
   - Bump `version_id` (optimistic concurrency).
3. Use `save_*_registry()` canonical save function (NEVER `.save()` directly per `.claude/rules/data-sync.md`).
4. Add `audit_log` row:
   ```python
   audit_log(
       action="location_correction",
       entity_id=photo_id,
       metadata={
           "old_location": <previous>,
           "new_location": <corrected>,
           "evidence_source": "Session 154 Track C1 + GEDCOM RESI" (or equivalent),
           "session_id": "156",
       },
   )
   ```
5. Browser verify (READ-ONLY): re-render the public photo page; confirm the corrected location appears.

**Authorization protocol**: list ALL photos to be corrected with their old + new locations in a single message to the user. Ask for explicit "fix the locations" authorization before any write.

### F5 — Verify location data flows to all surfaces

For each corrected photo, verify the new location appears on:
- Public photo page (`/photo/<id>`)
- `/map` view (if photo has geo coordinates)
- Person pages where the photo appears in the gallery
- Search results (`/tools/search` for "Detroit" should find these photos)
- Photo metadata in admin views

If any surface still shows stale data: it's a cache invalidation issue. Document and fix.

### F6 — Commit + UAT writeup

`docs/feedback/session-156-location-correctness-uat.md` with:
- The 4 photos checked
- Before/after table
- Audit_log row IDs for each correction
- Browser verification screenshots (or curl excerpts)
- Note any cache-invalidation issues found

Commit: `fix(session-156): location corrections for Detroit + Asheville photos (Track F)`. Body: per-photo summary.

---

## Phase 156-D — Closeout (MAIN thread, ~30 min)

Mandatory 11-step harness closeout per `.claude/rules/session-defaults.md`:

1. `docs/assessments/session-156-assessment.md` — full self-assessment with AI Tool Usage section.
2. CHANGELOG: bump to v0.99.71 (or higher). Entry covers Harry repair + PRD-063 Day 1.
3. ROADMAP: add to Recently Completed.
4. `docs/BACKLOG.md`: close items resolved.
   - HARRY-REPAIR-001 → CLOSED.
   - PRD-063-WRITE → CLOSED (PRD shipped + initial implementation).
   - SUPABASE-PRUNE-EXEC-001 → DEFERRED-PERMANENTLY (user rejected stopgap; full implementation in flight).
   - CI-SUPABASE-ENV → status update based on 156-C.
   - Add entries: PRD-063-IMPL-DAY-2 (Session 157), PRD-063-IMPL-DAY-3 (Session 158).
5. `git push origin main`.
6. Browser verify the canonical 6 + new identity person page (READ-ONLY).
7. `git log origin/main..HEAD` empty.
8. `git status --short` empty.
9. `bash scripts/harness-check.sh` exit 0 (warn-only on doc-cap acceptable).
10. `bash scripts/backup-memory.sh`.
11. Run `/session-review` skill.
12. **Codex audit pass**: now that Codex CLI works, run the audit:
    ```bash
    codex exec "Audit Session 156 changes for security, data-integrity, regression risk. P0/P1/P2/P3. Files changed: [list]. <500 words." </dev/null
    ```
    Output to `docs/session_context/session-156-codex-audit.md`. Address P0/P1 before declaring closeout done.

---

## Success gates

| Gate | How to check |
|---|---|
| Recovery from 155 timeouts complete | All Phase 156-0 verifications pass |
| Harry repair shipped | `audit_log` row exists; new identity has 2 anchors + provenance note rendered; Harry Fox has 5 anchors |
| PRD-063 at canonical path | `ls docs/prds/063_gedcom_mirror_efficient_redesign.md && wc -l ...` ≤ 300 |
| R2 backup of .ged sources verified | Roundtrip test on 1 file passed; manifest at known URL |
| R2 backup of versioned data verified | Reversibility test on 1 version on test DB passed; manifest URLs in commit body |
| v2 schema applied | `\d gedcom_individuals_v2` returns table; payload_hash unique index exists |
| Initial backfill complete | `COUNT(*) FROM gedcom_individuals_v2` ≈ `COUNT(DISTINCT gedcom_id) FROM gedcom_individuals WHERE is_current=TRUE` |
| CI green | If user pasted secrets in Phase 156-C |
| Codex audit pass | `docs/session_context/session-156-codex-audit.md` exists; P0/P1 addressed |
| Full closeout | All 12 harness steps; `git log` + `git status` clean |

## Anti-patterns to avoid

- ❌ Running `merge.sh` from a sub-worktree cwd (Lesson 176 — guard now in place but verify it fires).
- ❌ Pruning Supabase without per-step snapshots (Lessons 155, 156).
- ❌ DROP TABLE before R2 archive verification (PRD-063 §"Operational guardrails").
- ❌ Editing hook-blocked files at high transcript line counts without /clear first.
- ❌ Subagent with 4+ phase plan including a large design phase (Lesson 178).
- ❌ Assuming `select(...).execute()` returns all rows — paginate (Lesson 173).
- ❌ Codex CLI `--full-auto` (4-session hang) — use `codex exec "..." </dev/null` (Lesson candidate from 155 Track 5).
- ❌ Skipping the provenance note on the new identity. The user explicitly asked for "originally misidentified as Harry" to be visible.
- ❌ Linking GEDCOM Harry Isaackovitz as "confirmed" — must be "candidate" only. (No reference photo exists.)

## Phase timing estimates

| Track / Phase | Solo-time |
|---|---|
| 156-0 recovery verification | 5-30 min |
| A1 gate verification | 10 min |
| A2 snapshot | 5 min |
| A3 detach + create | 10 min |
| A4 note + audit_log + GEDCOM link | 10 min |
| A5 verify + commit | 10 min |
| **Track A total** | **45 min** |
| B1 PRD canonical path | 15 min |
| B2 R2 backup .ged | 30 min |
| B3 R2 backup Supabase | 60 min |
| B4 v2 schema | 30 min |
| B5 backfill + verify | 60 min |
| **Track B total** | **3h 15min** |
| C1 CI verification | 5 min (gated on user) |
| D closeout | 30 min |
| **Total sequential** | **~5h** |
| **Parallel (A in main, B in worktree)** | **~3h 30min** |

## Codex CLI invocation reminder

```bash
codex exec "<prompt>" </dev/null    # Form A — recommended (27s typical)
codex exec <<< "<prompt>"           # Form B (22s)
echo "<prompt>" | codex exec -      # Form C (23s)
```

`~/.codex/config.toml`: model = "gpt-5.5", reasoning_effort = "xhigh". DO NOT use `--full-auto`. Diagnosis: `docs/feedback/session-155-codex-cli-diagnosis.md`.

## What to NOT do this session

- DO NOT execute Track 2's Phase 2C/2D Detroit Gemini reruns. The user has deferred prompt-iteration work.
- DO NOT execute the stopgap E1 prune (commit `1e0b0fbc`). User rejected it; we're implementing PRD-063 fully.
- DO NOT drop v1 GEDCOM tables. That's Session 158 work, gated on dual-read confidence pass.
- DO NOT touch Albert Fox / Bessie Fox / Irving Fox identities. Only Harry Fox `d74cb556-...` gets modified, and only the 2 specific face_ids get detached.
- DO NOT pay for Gemini API calls without user authorization. Track A doesn't need them; Track B doesn't need them.
