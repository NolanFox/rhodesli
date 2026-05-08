# Session 157 — PRD-063 Day 2 + Session 156 Carry-Over (Tier 1 sweep + Track E)

**Mode**: Implementation
**Predecessor**: Session 156 (`docs/assessments/session-156-assessment.md`, `docs/session_logs/session-156-log.md`)
**Critical deadline**: 2026-05-29 — Supabase free-tier 1.1 GB ceiling. Today is 2026-05-08 → ~21 days. This session is **Day 2 of 3** of the PRD-063 implementation arc (157 = dual-read confidence; 158 = cutover + drop v1 + VACUUM).

**Why this session exists**: User asked Session 156 to "tackle all of the work deferred to 157." This prompt fits that ask within one coherent session by including: (a) Tier 1 quick wins (5 small items), (b) Track E GEDCOM upload UAT (deferred from 156), and (c) PRD-063 Day 2 dual-read confidence check + query timing. **Deferred OUT of this session**: GEDCOM-V2-OTHER-TABLES (events/relationships/records v2 — sized for 158 alongside cutover), PRD-LOCATION-001 (Gemini prompt iteration — paid API calls, deserves its own focused session with explicit cost authorization).

## Setup

```bash
echo "157" > .claude/current_session.txt
echo "implementation" > .claude/session_mode.txt
source venv/bin/activate
bash scripts/harness-check.sh             # warn-only on doc-cap acceptable
make test-fast                             # baseline — must be green
git log origin/main..HEAD                  # MUST be empty
git pull origin main                       # safety
git status --short                         # nothing meaningful
```

## Required first reads (in order)

1. `docs/session_context/session-156-assessment.md` — full carry-over from 156 with red flags, deferrals, and "Next session should verify FIRST" list.
2. `docs/session_logs/session-156-log.md` — phase checklist + verification gate results.
3. `docs/prds/063_gedcom_mirror_efficient_redesign.md` — the design we're implementing.
4. `docs/BACKLOG.md` — search for "Session 156 deferred items" block.
5. Lessons 173-181 in `tasks/lessons.md` — particularly 173 (pagination), 175 (pooler), 178 (token budgets), 179-181 (notes round-trip + worktree leak + GitHub secrets).

## Non-negotiable rules

1. READ-ONLY on production browsers (`.claude/rules/browser-read-only.md`).
2. **Codex CLI invocation**: `codex exec "<prompt>" </dev/null`. NEVER `--full-auto` (4-session hang fixed in 155 Track 5).
3. Commit atomically per phase. /clear between phases at 300+ transcript lines.
4. Every ML decision gets an AD entry. This session: AD-244 likely (the carry-over), AD-245 if dual-read helper is non-trivial.
5. R2 reversibility test must remain valid throughout — do NOT drop v1 in 157 (158 work).
6. `make test-fast` before every commit.
7. Track E uploads new GEDCOM through PRODUCTION import path — irreversible. Snapshot `gedcom_versions` row count + sizes BEFORE upload. Gated on E1 user authorization.

## CRITICAL — Concurrent genealogy session resilience

Same R1-R9 as Session 156 (carry forward verbatim). Specifically:
- **R1 marker file**: hold `.claude/parallel_session_active` only during Track E import window (irreversible) and during Day 2 full-backfill commit.
- **R2 optimistic concurrency**: pre-flight check before any Supabase write that touches identity rows (notes-backfill).
- **R3 additive only on v2**: Day 2 backfill is INSERT into v2 with ON CONFLICT DO NOTHING; dual-read helper is read-only.
- **R8 R2 namespace**: `2026-05-08-session-157` prefix for any new R2 archives (Track E v10 if upload creates new version).

---

## Parallelization plan

```
┌─────────────────────────────────────────────────────────────────────┐
│ Track 0 — Phase 156-0 carry verification (MAIN, ~5 min)             │
│                                                                     │
│ Track A — Tier 1 quick wins (PARALLEL via 2 worktree subagents)     │
│   A1: AD-244 + NOTES-BACKFILL-156 + CODEX-AUDIT-156 (subagent #1)   │
│   A2: CI-COMPARE-FAIL-156 + TEST-ISOLATION-156 (subagent #2)        │
│                                                                     │
│ Track B — PRD-063 Day 2 (MAIN thread)                                │
│   B1: Full backfill catching new is_current=TRUE rows since cutover │
│   B2: Dual-read helper (prefer v2, fall back to v1)                 │
│   B3: Side-by-side query timing on top 5 GEDCOM read paths          │
│   B4: Confidence assessment doc                                     │
│                                                                     │
│ Track E — GEDCOM upload UAT (MAIN thread, after Track A merge)      │
│   E1: User points at file (already in R2 from Session 156 Track B2) │
│   E2: Pre-import baseline measurement                               │
│   E3: Upload via existing v1 importer                               │
│   E4: 4 verification points (per user from 155)                     │
│   E5: Writeup + commit                                              │
│                                                                     │
│ Track Z — Closeout (MAIN, ~30 min)                                  │
└─────────────────────────────────────────────────────────────────────┘
```

Track A's two subagents run in parallel. Track B runs sequentially after Track A merge (so Codex audit results inform Day 2 design choices). Track E runs after Track B (so any Day 2 issues surface before the irreversible upload).

---

## Phase 157-0 — Carry verification (~5 min)

```bash
ls docs/assessments/session-156-assessment.md docs/session_logs/session-156-log.md
ls scripts/migrations/gedcom_v2_schema.sql scripts/session156_backfill_gedcom_v2.py
grep "AD-244" docs/ml/ALGORITHMIC_DECISIONS.md && echo "AD-244 already exists (carry forward content if so)"

# v2 tables exist?
python -c "
from dotenv import load_dotenv; load_dotenv()
from app.supabase_data import get_supabase_client
sb = get_supabase_client()
for t in ['gedcom_individuals_v2', 'gedcom_families_v2', 'gedcom_change_manifest']:
    r = sb.table(t).select('*', count='exact').limit(1).execute()
    print(f'{t}: count={r.count}')
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

Expected: v2 tables exist (21,998 / 6,741 / 9 rows respectively); Harry has 5 anchors + version 14; new identity is INBOX with notes.

If anything is missing: re-run the relevant Session 156 script (most are idempotent) OR escalate.

---

## Track A — Tier 1 quick wins

Launch **TWO worktree subagents in parallel** at session start. Each gets ~3 phases, ~30-45 min total. This stays well under Lesson 178's token-budget limit.

### Subagent #1 — Doc + audit + backfill (~45 min)

**Worktree setup (FIRST ACTION)**:
```bash
echo "interactive" > .claude/session_mode.txt
echo "157" > .claude/current_session.txt
source venv/bin/activate
make test-fast 2>&1 | tail -3
```

#### Phase A1.1 — AD-244 entry (~10 min)
Append to `docs/ml/ALGORITHMIC_DECISIONS.md` after AD-235:

```markdown
### AD-244: PRD-063 GEDCOM Mirror Efficient Redesign — v2 Schema with INSERT-Time Dedup (2026-05-08)
- **Date**: 2026-05-08 | **Sessions**: 156 (Day 1 — schema + backfill), 157 (Day 2 — full backfill + dual-read), 158 (Day 3 — cutover + drop v1)
- **Context**: <copy from session-156-assessment.md "Track B" section + 156 commits>
- **Decision**: <see PRD-063 §4>
- **v2 tables**: gedcom_individuals_v2 (21,998 rows / 43 MB, 18× smaller), gedcom_families_v2 (6,741 / 5.2 MB, 14× smaller), gedcom_change_manifest (9 / 280 KB, 1400× smaller). Total: ~98% reduction projected.
- **Mechanism**: Storage win comes from EXCLUDING is_current=FALSE rows (PRD-063 §4.2 confirmed) — payload_hash dedup factor is 1.00× because every is_current=TRUE row has a unique payload.
- **Migration plan**: Day 1 ✅, Day 2 (this session), Day 3 (158 — cutover gated on dual-read confidence).
- **Operational guardrails**: R2 archives at gedcom-source-snapshots/2026-05-08-session-156/ (.ged) and gedcom-version-snapshots/2026-05-08-session-156/v<N>/ (Supabase). Reversibility verified on v9.
- **Commits**: B3 `2d484c99`, B4 `a47344f9`, B5 `562129b6`.
- **Risks**: Dual-read window assumes app code can handle v1-or-v2 returns. Other v2 tables not built (events/relationships/records — 158 cutover work).
- **Affects**: GEDCOM read paths (`app/relationship_routes.py::_load_gedcom_face_links`, person page GEDCOM context, /tree, /tools/search), Sessions 157+158, OD-013.
```

Commit: `docs(session-157): AD-244 PRD-063 v2 schema design entry (Track A1.1)`

#### Phase A1.2 — NOTES-BACKFILL-156 (~25 min)
Pre-existing bug in Session 156 lesson 179: notes added via `add_note()` between Sessions 105-156 may have written to local `data/identities.json` only (top-level "notes" key) but never persisted to Supabase metadata.notes.

Write `scripts/session157_notes_backfill.py`:
- Read `data/identities.json` — for each identity with non-empty top-level `notes`, capture id + notes count.
- Read each identity's Supabase row — get `metadata.notes` count (may be null).
- For any identity where local count > Supabase count: take the union of the two note sets (deduplicate by note `id` if present, else by `text` + `timestamp`), write back to Supabase via `shadow_write_identity(strict=True)` (the round-trip fix from 156 will now persist).
- Defaults to `--dry-run`. Pass `--execute` to apply.
- Output: `docs/feedback/session-157-notes-backfill-report.md` with counts.

Run dry-run first. Surface report to orchestrator. Only run `--execute` if dry-run shows >0 deltas AND nothing surprising. Commit script + report: `feat(session-157): notes backfill from JSON to Supabase metadata (Track A1.2)`.

If dry-run shows 0 deltas (all identities already in sync): commit just the script + a "no-op confirmed" note in the report. Document in commit message that the round-trip fix was applied early enough that no notes were lost in production.

#### Phase A1.3 — Codex audit of 156 commits (~10 min)
Per `.claude/rules/ai-tool-audit.md`:

```bash
codex exec "Audit Session 156 changes for security, data-integrity, and regression risk. Files in scope:
- app/supabase_data.py (shadow_write_identity + shadow_write_identities_batch — notes embedded in metadata)
- core/registry.py (load_from_postgres — notes extracted from metadata)
- scripts/session156_harry_repair_*.py (snapshot, restore, execute)
- scripts/session156_r2_backup_gedcom_sources.py
- scripts/session156_r2_backup_supabase_versions.py (worktree subagent output)
- scripts/migrations/gedcom_v2_schema.sql
- scripts/session156_backfill_gedcom_v2.py
- scripts/session156_fix_detroit_locations.py
- tests/test_session156_notes_roundtrip.py

Specifically check:
1. Notes round-trip: any path where top-level identity['notes'] could leak past the embedding step? Any race condition where a concurrent write loses notes?
2. Harry repair script: any way the snapshot SHA256 verification could be bypassed? Any way the version_id check could pass on stale data?
3. R2 backup scripts: SQL injection risk in the version_number filter? Path traversal in the R2 key construction? Hardcoded secrets?
4. v2 schema migration: any column type narrowing that could lose data? UNIQUE constraint that could prevent legitimate inserts?
5. Detroit fix: audit_log row construction safe against JSON-injection in old_value/new_value?

Output: P0/P1/P2/P3 findings with file:line references. <500 words." </dev/null
```

Save raw output to `docs/session_context/session-157-codex-audit.md` with provenance header per `.claude/rules/ai-tool-audit.md`. If P0/P1 findings: surface to orchestrator for fix-before-Track-B. Commit: `docs(session-157): Codex audit of session 156 commits (Track A1.3)`.

### Subagent #1 return value
- AD-244 commit hash
- NOTES-BACKFILL counts (local-only-notes, Supabase-only-notes, deltas backfilled)
- Codex P0/P1 findings (just titles)
- Worktree path + branch

### Subagent #2 — CI + test isolation (~30 min)

**Worktree setup**: same as Subagent #1.

#### Phase A2.1 — CI-COMPARE-FAIL-156 (~15 min)
`tests/test_compare.py::test_compare_upload_stages_file` PASSES locally but FAILS in CI (post-secrets-upload). CI returns 200 with error-reference page instead of "staged" content.

Investigate:
1. Read the test file. Understand what endpoint it hits and what response it expects.
2. Check `app/upload_routes.py` or wherever `/api/compare/upload` is defined. Look for:
   - Imports that might fail without credentials/insightface installed
   - Environment-dependent branches that differ between local and CI
3. Check `requirements.txt` vs CI's `pip install` — any optional ML deps that the test assumes?
4. Check the CI workflow — does it install all the deps the test needs?

Pick the fix:
- (a) If CI is missing a dependency: add to `requirements.txt` or workflow.
- (b) If the test is fundamentally not runnable in CI: add `@pytest.mark.skipif(os.getenv("CI") == "true")` with a one-line comment citing CI-COMPARE-FAIL-156. Add the test to a "needs-local-ml" mark.
- (c) If the endpoint behavior depends on R2 (which CI doesn't have): mock the R2 client.

Apply the chosen fix. Run `make test-fast` locally. Commit: `fix(session-157): CI-COMPARE-FAIL-156 — <chosen approach> (Track A2.1)`. Push and watch CI run for green.

#### Phase A2.2 — TEST-ISOLATION-156 (~15 min)
4 tests fail under sequential pytest, pass under xdist parallel:
- `tests/test_back_image.py::TestBrowseMediaFilter::test_flip_icon_badge_on_card`
- `tests/test_face_overlays.py::TestOverlayTooltips::test_overlay_has_name_display`
- `tests/test_inline_find_similar.py::TestUnifiedCardsInBrowse::test_browse_cards_use_unified_card`
- `tests/test_discoveries.py::TestDiscoveriesThreeSections::test_help_identify_section_present`

Repro:
```bash
pytest tests/test_back_image.py::TestBrowseMediaFilter::test_flip_icon_badge_on_card tests/test_face_overlays.py::TestOverlayTooltips::test_overlay_has_name_display tests/test_inline_find_similar.py::TestUnifiedCardsInBrowse::test_browse_cards_use_unified_card tests/test_discoveries.py::TestDiscoveriesThreeSections::test_help_identify_section_present -p no:xdist -q --no-header
```

Likely causes: shared state leakage (`_photo_cache`, `_registry_cache`, `_face_data_cache`, `_face_identity_lookup_cache`, `_best_face_cache`). Diagnose:
1. Add `print(id(_photo_cache))` or similar diagnostics at the start + end of each failing test (temporarily).
2. Find which earlier test mutated a shared cache without resetting.
3. Add appropriate `@pytest.fixture(autouse=True)` cache reset to `tests/conftest.py` if missing.

Fix the conftest. Run the failing 4 in sequential mode — must pass. Run `make test-fast` (xdist) — must still pass. Commit: `fix(session-157): TEST-ISOLATION-156 — conftest cache reset (Track A2.2)`.

If diagnosis shows the failures are something other than cache leakage (e.g., test data ordering), document and pick the lightest fix.

### Subagent #2 return value
- CI-COMPARE fix approach + commit hash
- TEST-ISOLATION root cause + commit hash
- `make test-fast` final state
- Worktree path + branch

### Track A merge
After both subagents return: orchestrator runs `./scripts/merge.sh <branch1> <branch2>` from main repo cwd (Lesson 176 guard fires). Resolve any conflicts (unlikely — different files). Push. Verify CI green.

---

## Track B — PRD-063 Day 2

Sequential after Track A merge.

### Phase B1 — Full backfill since cutover (~30 min)

The 156 cutover timestamp was `2026-05-08T04:56:15Z`. Any new `is_current=TRUE` rows added to v1 since then need to land in v2.

```bash
python scripts/session157_full_backfill_gedcom_v2.py --dry-run
```

Write `scripts/session157_full_backfill_gedcom_v2.py`:
- Read `gedcom_individuals` and `gedcom_families` rows where `is_current=TRUE` AND `created_at > '2026-05-08T04:56:15Z'`.
- For each: compute `payload_hash`, INSERT into v2 with `ON CONFLICT (payload_hash) DO NOTHING`.
- Update `last_seen_version` for any individual whose `payload_hash` already exists in v2 but had a higher `version_id` since cutover.
- Output: row counts (new v2 inserts, updates, no-ops).

Verify counts. If new rows added since cutover: surface counts. If 0 (no genealogy session activity): document as "no-op confirmed."

Run with `--execute`. Commit: `feat(session-157): PRD-063 full backfill catching post-cutover rows (Track B1)`.

### Phase B2 — Dual-read helper (~30 min)

Add `app/gedcom_dual_read.py`:
```python
def get_individual(gedcom_id: str) -> dict | None:
    """Read a GEDCOM individual, preferring v2 over v1.

    During the dual-read window (Sessions 157-158), v1 remains
    authoritative for any field not yet in v2 (events, relationships,
    records). For canonical fields (name, birth/death dates+places,
    gender) v2 is preferred — its row count is ~18x smaller and
    queries are faster.

    Returns None if not found in either.
    """
```

Same pattern for `get_family(family_gedcom_id)`. Wire into `app/relationship_routes.py::_load_gedcom_face_links` and any other person-page GEDCOM read path. Keep it surgical — do NOT refactor the whole GEDCOM stack.

Add `tests/test_gedcom_dual_read.py` with 4 cases:
1. Individual exists only in v2 → read from v2.
2. Individual exists in both → v2 wins.
3. Individual exists only in v1 → fallback to v1.
4. Individual exists in neither → returns None.

Commit: `feat(session-157): PRD-063 dual-read helper for v2 with v1 fallback (Track B2)`.

### Phase B3 — Side-by-side query timing (~30 min)

Identify top 5 GEDCOM read paths from production logs (or audit code-side):
1. `_load_gedcom_face_links` (request-path on every page with GEDCOM link)
2. Person page GEDCOM context (`/person/<id>` rendering)
3. `/tree` page (full graph traversal)
4. `/tools/search` GEDCOM lookups (rule-based parser)
5. GEDCOM triage page (admin)

Write `scripts/session157_query_timing.py`:
- For each read path: time 100 iterations against v1 + 100 against v2 (via dual-read helper).
- Output median + p95 latency for each.
- Save to `docs/session_context/session-157-query-timing.md`.

If v2 is faster across the board: dual-read confidence GREEN — Session 158 cutover is safe. If v2 is slower or inconsistent: investigate index gaps, document, recommend either adding indexes in 158 or keeping v1-primary reads for those paths.

Commit: `chore(session-157): PRD-063 dual-read query timing (Track B3)`.

### Phase B4 — Confidence assessment (~15 min)

Write `docs/feedback/session-157-day-2-confidence.md`:
- Backfill status (B1 row counts)
- Dual-read helper test results
- Query timing comparison (B3 numbers)
- Open issues for Session 158 (events/relationships/records — must build before cutover OR refactor read paths)
- Recommendation: PROCEED to 158 cutover OR HOLD for one more session

Commit: `docs(session-157): PRD-063 Day 2 confidence assessment (Track B4)`.

---

## Track E — GEDCOM upload UAT (carry-over from 156)

Sequential after Track B. The new Fox-family GEDCOM file is already at `~/Downloads/gedcom_20260508/Fox_Capeluto_Fogel_Waldorf Family Tree.ged` (17.08 MB, sha256 `f7832541...`) and archived to R2 at `gedcom-source-snapshots/2026-05-08-session-156/`.

### E1 — User confirmation (~5 min)
Confirm the file is the canonical "newest" Fox-family GEDCOM. Path: `~/Downloads/gedcom_20260508/Fox_Capeluto_Fogel_Waldorf Family Tree.ged`. If user has downloaded a newer one since 156, re-archive to R2 and use the new path.

### E2 — Pre-import baseline (~5 min)
Capture:
- `gedcom_versions` row count (was 9 at end of 156)
- Total row counts: `gedcom_individuals`, `gedcom_records`, `gedcom_events`, `gedcom_relationships`, `gedcom_change_log`, `gedcom_families`
- v2 row counts (should equal end-of-156 + B1 deltas)
- Supabase total DB size
- `make test-fast` green

### E3 — Upload via v1 importer (~30 min)
**This is irreversible. Set parallel marker:**
```bash
touch .claude/parallel_session_active
```

Run the existing GEDCOM import path. Verify the canonical command (likely `python scripts/import_gedcom.py --file <path>` or via admin UI POST). Watch for the bloat-related issue (Lesson 163: doesn't scale to 175K+ rows). If the importer hits errors:
- STOP and surface to user
- Snapshot post-error state
- Decide: rollback (R2 archive provides rollback path), patch importer, or fall back to band-aid prune (`1e0b0fbc`)

If import succeeds: capture `gedcom_versions` new row (v10), row counts per child table.

Remove parallel marker:
```bash
rm .claude/parallel_session_active
```

### E4 — 4 verification points (~30 min)

Per user message during 155 closeout:

1. **"Make it easier to upload a new one"**: was the upload more or less reversible than before 156? Did we have a clean backup point if it failed mid-import? Reference the R2 source archive + the v1-row archive from B3.

2. **"Make it easier to understand the changes for a specific family between GEDCOM versions"**: query `gedcom_change_manifest` for v10 vs v9 for the Fox family. Document what changed. Compare to what `gedcom_change_log` shows under v1 (per-row noise).

3. **"Make sure we've fixed the issue of the size growing rapidly"**: measure size delta. **EXPECTED**: under v1 the new version adds ~250-300 MB (full snapshot). Under v2 backfill from B1 (post-import) the new version should add only delta rows. If v2 adds anywhere near v1's growth: regression — escalate.

4. **"Make sure we haven't broken Supabase"**: comprehensive smoke test:
   - `/api/admin/db-size` returns expected values
   - `/health` returns 200 with `supabase: "ok"`
   - Browser-verify (READ-ONLY): person pages, `/tree`, `/tools/search` rule-based parser
   - `pytest tests/test_gedcom_*.py -q --no-header` green
   - `pytest tests/test_data_integrity.py -q --no-header` green

### E5 — UAT writeup + commit (~10 min)

`docs/feedback/session-157-gedcom-upload-uat.md` with all 4 verification outcomes. If any FAIL: document, surface to user, recommend rollback (snapshot exists) or escalation to 158.

Commit: `feat(session-157): GEDCOM upload UAT (Track E)`. Body: 4-line summary of UAT outcomes.

---

## Track Z — Closeout (~30 min)

Mandatory 12-step harness closeout per `.claude/rules/session-defaults.md`:

1. `docs/assessments/session-157-assessment.md` — full self-assessment with AI Tool Usage section.
2. CHANGELOG: bump to v0.99.73. Entry covers Tier 1 + Day 2 + Track E.
3. ROADMAP: add to Recently Completed; remove Session 157 from Planned Sessions.
4. `docs/BACKLOG.md`: close items resolved.
   - AD-244 → CLOSED
   - NOTES-BACKFILL-156 → CLOSED (or NO-OP if 0 deltas)
   - CODEX-AUDIT-156 → CLOSED (P0/P1 fixed before Track B if any)
   - CI-COMPARE-FAIL-156 → CLOSED
   - TEST-ISOLATION-156 → CLOSED
   - GEDCOM-UAT-156 → CLOSED
   - PRD-063-DAY-2-IMPL → CLOSED
   - Add: PRD-063-DAY-3-IMPL (Session 158)
5. `git push origin main`.
6. Browser verify the canonical 6 pages + new GEDCOM-context render (READ-ONLY).
7. `git log origin/main..HEAD` empty.
8. `git status --short` empty.
9. `bash scripts/harness-check.sh` exit 0 (warn-only on doc-cap acceptable).
10. `bash scripts/backup-memory.sh`.
11. Run `/session-review` skill.
12. Codex final-pass audit on all 157 commits (already partially done in A1.3 for 156 commits).

---

## Success gates

| Gate | How to check |
|---|---|
| Phase 157-0 carry verification | All 156 deliverables intact |
| AD-244 entry | `grep "^### AD-244" docs/ml/ALGORITHMIC_DECISIONS.md` |
| Notes backfill complete or no-op confirmed | Report at `docs/feedback/session-157-notes-backfill-report.md` |
| Codex audit pass | `docs/session_context/session-157-codex-audit.md` exists; P0/P1 addressed |
| CI-COMPARE-FAIL fixed | Latest CI run green |
| TEST-ISOLATION fixed | Sequential pytest of the 4 tests passes |
| Day 2 backfill complete | New v2 rows since cutover landed |
| Dual-read helper shipped | `app/gedcom_dual_read.py` + 4 unit tests pass |
| Query timing recorded | `docs/session_context/session-157-query-timing.md` |
| Confidence assessment for Day 3 | `docs/feedback/session-157-day-2-confidence.md` |
| GEDCOM UAT shipped | All 4 verification points pass; writeup committed |
| Codex final audit pass | (recommended, optional if A1.3 was thorough) |
| Full closeout | All 12 harness steps; `git log` + `git status` clean |

## Phase timing estimates

| Track / Phase | Solo-time |
|---|---|
| 157-0 carry verification | 5 min |
| Subagent #1 (AD-244 + notes-backfill + Codex) | 45 min |
| Subagent #2 (CI-COMPARE + TEST-ISOLATION) | 30 min |
| Track A merge | 5 min |
| **Track A total** | **~50 min** (with parallelization) |
| B1 full backfill | 30 min |
| B2 dual-read helper | 30 min |
| B3 query timing | 30 min |
| B4 confidence doc | 15 min |
| **Track B total** | **~1h 45min** |
| E1-E5 GEDCOM UAT | ~80 min |
| Z closeout | 30 min |
| **Total parallel** | **~4h 30min** |

## Codex CLI invocation reminder

```bash
codex exec "<prompt>" </dev/null    # Form A — recommended
codex exec <<< "<prompt>"           # Form B
echo "<prompt>" | codex exec -      # Form C
```

`~/.codex/config.toml`: model = "gpt-5.5", reasoning_effort = "xhigh". DO NOT use `--full-auto`. Diagnosis: `docs/feedback/session-155-codex-cli-diagnosis.md`.

## What to NOT do this session

- DO NOT drop v1 GEDCOM tables. That's Session 158 work, gated on Day 2 dual-read confidence.
- DO NOT pay for Gemini API calls (PRD-LOCATION-001 is its own session with explicit cost authorization).
- DO NOT build `gedcom_records_v2` / `gedcom_events_v2` / `gedcom_relationships_v2` — out of scope; 158 cutover decides whether to backfill or read-bridge.
- DO NOT touch identity rows beyond the notes-backfill (READ-ONLY on Harry Fox / Belle Isle / Albert / Bessie / Irving / Person 3009).
- DO NOT skip Phase E2 baseline measurement — it's how we prove Day 2's storage win is real.
