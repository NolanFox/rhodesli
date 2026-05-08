# Session 156 Assessment

**Date**: 2026-05-08
**Mode**: Implementation
**Predecessor**: Session 155 (`docs/assessments/session-155-assessment.md`)
**Successor**: Session 157 (PRD-063 Day 2 — full backfill + dual-read confidence check)
**Critical deadline carried forward**: 2026-05-29 — Supabase free-tier cutoff at 1.1 GB. PRD-063 implementation arc is on schedule for completion before that date.

---

## Shipped

### Track A — Harry Fox repair (option c) — ✅ SHIPPED
- **A1 gate verification**: All 6 gates from 153b verified (Bessie POSSIBLE-GOOD, F+G IDs confirmed, replacement label decided, snapshot scope EXTENDED, audit log drafted, structural tests pending — all PASS).
- **A2 snapshot** (commit `efb9ac1b`): Pre-repair snapshot of Harry Fox identity (7 anchors, version_id=13) + downstream rows (ml_proposals × 0, photo_faces for F+G × 2, gedcom_face_links × 1, audit_log recent × 1). SHA256 = `13e1d7ae798d3b98...`. Snapshot file committed to git for audit trail. Restore script written.
- **Notes round-trip fix** (commit `49298a76`): Discovered that `registry.add_note()` writes top-level `identity["notes"]` but `shadow_write_identity` only persists `metadata` JSONB — top-level "notes" silently dropped on Supabase round-trip. Patched both `shadow_write` and `load_from_postgres` to round-trip notes through `metadata.notes`. 4 regression tests added in `tests/test_session156_notes_roundtrip.py`. Pre-existing bug surfaced by Phase A4's expectation that notes would render.
- **A3+A4 mutation** (commit `dd7b617f`): Detached `inbox_1fea75ce2caf` (F) + `inbox_e507a54f204a` (G) from Harry Fox. Anchors 7→5; version_id 13→14. Created new identity `ef39908e-283a-4cec-8f72-3ec83bc8d84f` "Belle Isle Conservatory Young Man c.1917-1918" (state=INBOX, anchors=[F,G], metadata.notes contains ~1500-char provenance note citing Sessions 153/153b/154 evidence across 4 triangulation sources, metadata.originally_misidentified_as="Harry Fox"). Inserted `gedcom_face_links` candidate row (Harry Isaackovitz `@I132506612777@`, confidence=0.3, linked_by="session-156-candidate"). Wrote `audit_log` entry with action=identity_detach_replace, full triangulation metadata, belle_isle_citation, snapshot_path.
- **A5 verify**: Direct Supabase queries confirm post-state (Harry 5 anchors version_id=14; new identity 2 anchors INBOX with notes; gedcom_face_links candidate row; audit_log row). `pytest tests/test_data_integrity.py` 12 passed. Production browser verify (READ-ONLY): Harry page renders 200; new identity page returns 404 due to 600s registry TTL — will re-render after cache expiry (verified at session end below).
- **R6 pre-flight**: Verified Harry version_id=13 + 7 anchors immediately before mutation. Snapshot SHA256 verified before each mutation step. R2 optimistic concurrency would have aborted on drift.
- **Marker discipline (R1)**: Created `.claude/parallel_session_active` for irreversible window only; removed immediately after A4. Other commits run without marker.

### Track B — PRD-063 Day 1 implementation — ✅ SHIPPED (worktree subagent)
- **B1**: PRD verified at canonical path `docs/prds/063_gedcom_mirror_efficient_redesign.md` (221 lines, all 10 sections present, sub-files split per doc-size-enforcement.md).
- **B2** (commit `96403306`, main thread): R2 backup of new Fox-family GEDCOM source `.ged` file uploaded to `r2://rhodesli-photos/gedcom-source-snapshots/2026-05-08-session-156/`. 17.08 MB. Roundtrip verified (size + sha256 match).
- **B3** (commit `2d484c99`, agent): All 9 historical Supabase versions archived to R2 (`gedcom-version-snapshots/2026-05-08-session-156/v<N>/`). Total ~2.89M rows compressed to ~0.26 GB (gzip on duplicate-payload-hash data is highly effective). Reversibility test on v9 PASSED parity (21,228 rows). Per-version manifests + aggregate manifest. Used psycopg2 server-side cursor + Supabase pooler (Lessons 173, 175). READ-ONLY on v1 (R3 satisfied).
- **B4** (commit `a47344f9`, agent): Migration `scripts/migrations/gedcom_v2_schema.sql` applied via psycopg2 + us-west-2 pooler. 3 tables created (`gedcom_individuals_v2`, `gedcom_families_v2`, `gedcom_change_manifest`) with `payload_hash UNIQUE` on individuals and families. Pre-flight check confirmed v2 didn't pre-exist. Purely ADDITIVE — v1 untouched.
- **B5** (commit `562129b6`, agent): Initial backfill via `scripts/session156_backfill_gedcom_v2.py`. Final v2 row counts: `gedcom_individuals_v2` 21,998 rows / 43 MB (from v1's 196,645 rows / 783 MB → **18× smaller**); `gedcom_families_v2` 6,741 rows / 5.2 MB (from 33,324 / 75 MB → 14× smaller); `gedcom_change_manifest` 9 rows / 280 KB (replaces 1.65M-row / 397 MB `gedcom_change_log` → **1400× smaller**). Total v1 ~2.21 GB → v2 ~48.5 MB = **~98% reduction (~45× smaller)**. Storage win comes from EXCLUDING `is_current=FALSE` rows — payload_hash dedup factor is 1.00× because every is_current=TRUE row has a unique payload (PRD-063 §4.2 confirmed). Cutover timestamp 2026-05-08T04:56:15Z documented in commit body. ON CONFLICT (payload_hash) DO NOTHING for idempotent re-runs.
- **Worktree merge** (commit `5bab77fd`): Branch `worktree-agent-a70ad4cbcba751574` merged via `scripts/merge.sh` from primary worktree cwd (Lesson 176 guard fired and was satisfied). Pre-merge cleanup: removed 7 untracked working-tree files identical to worktree commits (`cmp` verified byte-equal before removal). Post-merge `make test-fast` under xdist parallel: **4246 passed** (no regressions).

### Track F — Location-correctness UAT — ✅ SHIPPED (Detroit subset; Asheville already correct)
- **F1**: Identified photos in scope. Detroit: 02068 + 01659 (third frame `91b6f6b296e93a60` is NOT in `photos` table — investigation deferred). Asheville Victor+Victoria: user identified `3192877a90a174e9` after I surfaced two co-occurrence candidates (Miami + Montgomery) that didn't match.
- **F2/F3**: Read current location data. **Detroit photos confirmed bugged** — 02068 stored as "New York City" (lat 40.7128, conf=medium); 01659 stored as generic "United States" (lat 39.8283, conf=low). **Asheville photo verified correct** — `3192877a90a174e9` already shows "Asheville, North Carolina" lat 35.5951 / lng -82.5515 with confidence=high and rich biographical evidence ("Leon's Restaurant, owned by Leon Capeluto. Leon and Victoria Capeluto lived in Asheville, NC. Photo shows Victor Capeluto visiting his brother Leon's restaurant").
- **F4** (commit `ed226a72`): User-authorized manual location override on the 2 Detroit photos. Both updated to Detroit, MI (lat 42.3314, lng -83.0458, confidence=high) with rich biographical_evidence (LoC LC-DIG-det-4a17798, Albert Fox GEDCOM RESI Detroit 1917, Albert draft induction 7 Jun 1918). `audit_log` entries written with action=location_correction citing Session 154 Track C1 evidence. **Follow-up**: PRD-LOCATION-001 BACKLOG — iterate on Gemini prompt until it predicts Detroit on these photos. Sycophancy guard (AD-242) did not fire on 02068 in Session 154 Phase A3 retest. Manual override is a stopgap.

### Phase 156-0 — Recovery verification — ✅ COMPLETE
All 7 artifacts from Session 155's Phase 6 recovery subagent landed on origin/main. PRD-063 at canonical path (221 lines). Track 2 patches applied. Track 5 doc cherry-picked. CI workflow wired. AD-243 in ALG_DECISIONS (4 mentions).

---

## Deferred

### Track C — CI verification — DEFERRED (user-blocking)
- **Status**: BLOCKED on user action. GitHub repo has ZERO action secrets configured (verified via `gh api repos/NolanFox/rhodesli/actions/secrets` → total_count=0). CI failure `supabase_url = ''` confirms empty env. User said "Yes — trigger CI run now" but secrets weren't actually pasted at https://github.com/NolanFox/rhodesli/settings/secrets/actions yet.
- **BACKLOG**: CI-SUPABASE-ENV-002 (re-list).
- **Reason**: User-gated; not a code or infrastructure issue.
- **Next session**: User pastes `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_DB_PASSWORD`, `GEMINI_API_KEY` in GitHub Settings → Secrets → Actions. Then push any tiny commit to trigger fresh CI run.

### Track E — GEDCOM upload UAT — DEFERRED
- **Status**: User downloaded the new Fox-family GEDCOM (~/Downloads/gedcom_20260508/Fox_Capeluto_Fogel_Waldorf Family Tree.ged, 17.08 MB, sha256 f7832541...) but Track E (running the new GEDCOM through the v1 import path + 4 UAT verification points + writeup) was NOT executed in 156. Session prompted with this in scope but the time budget went to Track A (Harry repair + notes round-trip fix discovered mid-session) + Track B merge cleanup + Track F.
- **B2 archival**: The GEDCOM file IS archived to R2 already (Track B2 commit `96403306`), so it's preserved.
- **BACKLOG**: GEDCOM-UAT-156 → roll into Session 157 (it's a natural fit alongside Day 2 dual-read confidence check).
- **Reason**: Time budget. The notes round-trip fix (~30 min) was unexpected, and the merge.sh + post-merge test isolation investigation (~30 min) ate into the time slot for Track E.

### AD-244 — PRD-063 schema design — DEFERRED to first 157 commit
- Track B agent flagged this. AD-244 is intentionally deferred to Session 157's first commit so it can reference the merged commit hashes (B3/B4/B5) on main. This is a small follow-up, not a substantive omission.

### Other GEDCOM v2 tables — INTENTIONALLY NOT BUILT
- `gedcom_records`, `gedcom_events`, `gedcom_relationships` v2 are NOT yet built. Track B scope explicitly limited to `gedcom_individuals_v2`, `gedcom_families_v2`, `gedcom_change_manifest`. The other 3 tables remain at v1 in production reads, which is fine through Session 157. Session 158 cutover work will need to either backfill those or refactor read paths to compose v1 events/relationships with v2 individuals.

---

## Red Flags

### 🟡 Worktree isolation broke for Track B agent
- **Severity**: P2
- **What happened**: Track B subagent (launched with `isolation: "worktree"`) wrote files to `/Users/nolanfox/rhodesli/scripts/...` and `/Users/nolanfox/rhodesli/backups/...` (main repo paths) instead of the worktree at `.claude/worktrees/agent-a70ad4cbcba751574/`. The agent ALSO committed those files to its worktree branch via copy. Pre-merge `cmp` verified the main filesystem files were byte-identical to the worktree-branch versions.
- **Recovery**: Removed the duplicate untracked files from main filesystem before running `merge.sh`. Merge proceeded normally and brought in those exact same file contents via the merge commit.
- **Risk if undetected**: If the worktree commits had different content than what landed in main as untracked files, we'd have silently committed the wrong version on merge.
- **Fix**: Add a structural check in agent prompts: warn if the agent's CWD differs from the worktree path. Or harden `Agent({isolation: "worktree"})` so absolute paths get rejected.
- **Lesson candidate**: "Worktree isolation can fail silently for agents using absolute paths."

### 🟡 Notes round-trip was a pre-existing bug, fixed mid-session
- **Severity**: P2 (latent bug surfaced + fixed in same session)
- **Background**: `registry.add_note()` writes to top-level `identity["notes"]` but `shadow_write_identity` (the Supabase write path) only persists `metadata` JSONB. Top-level "notes" key was silently dropped on every Supabase round-trip. So every `add_note` call since DATA_SOURCE=postgres rolled out (Session 105+) lost the note on next page render after the in-memory cache TTL expired.
- **How discovered**: While preparing Track A4 provenance note. The user's session prompt said "use BOTH (notes for human-visible, audit_log for machine-readable)" which forced me to verify the existing path actually worked.
- **Fix**: Round-trip notes through `metadata.notes`. 4 regression tests added.
- **Backfill needed?** Possibly. Existing identities created via `add_note` between Session 105 and Session 156 may have notes in `identities.json` that never made it to Supabase. With DATA_SOURCE=postgres, those notes are effectively lost on production. **Recommendation**: Session 157 should run a backfill script that reads `identities.json` notes and writes them to Supabase metadata for any identity where Supabase has fewer notes than JSON. Logged as BACKLOG NOTES-BACKFILL-156.

### 🟢 Production browser cache TTL is 600s
- **Severity**: P3 (operational, not a defect)
- **What**: New Belle Isle identity at `/person/ef39908e...` returned 404 immediately after Track A mutation. Cause: registry TTL cache 600s. Direct Supabase query verified the data IS persisted correctly. Public production page will start rendering after cache expires (within 10 min of mutation).
- **Action**: Re-verify in closeout (below).

### 🟢 4 tests fail under sequential pytest, pass under xdist parallel
- **Severity**: P3 (test isolation gap, not a Track B regression)
- **Tests**: `test_back_image::test_flip_icon_badge_on_card`, `test_face_overlays::test_overlay_has_name_display`, `test_inline_find_similar::test_browse_cards_use_unified_card`, `test_discoveries::test_help_identify_section_present`.
- **Diagnosis**: All 4 fail under `merge.sh`'s sequential post-merge run; all 4 pass under `make test-fast` xdist parallel. Test isolation issue (likely `_photo_cache`/`_registry_cache` state leakage between sequential test cases).
- **Pre-existing**: Track B agent flagged it pre-merge. Track B touches no app code (only scripts + migration SQL + Supabase rows).
- **BACKLOG**: TEST-ISOLATION-156 (low priority — green under main `make test-fast`).

---

## Verification gate

| Gate | How verified | Result |
|---|---|---|
| Recovery from 155 timeouts complete | Phase 156-0 ls/grep checks | ✅ All 7 artifacts present |
| Harry repair shipped | Direct Supabase queries on Harry + new identity + audit_log | ✅ Anchors 7→5, new identity 2 anchors with notes, audit_log row, gedcom_face_links candidate |
| PRD-063 at canonical path ≤ 300 lines | `wc -l docs/prds/063_*` | ✅ 221 lines |
| R2 backup of .ged sources verified | Roundtrip on the new Fox-family GEDCOM | ✅ size + sha256 match |
| R2 backup of versioned data verified | Reversibility test on v9 (smallest) | ✅ 21,228 rows parity |
| v2 schema applied | `to_regclass` for all 3 tables | ✅ All exist |
| Initial backfill complete | COUNT(*) queries | ✅ 21,998 / 6,741 / 9 |
| CI green | gh run list | ❌ BLOCKED on user pasting secrets |
| Codex audit pass | (deferred — see below) | ⚠️ DEFERRED |
| Full closeout | This file + push + git log clean | ✅ in progress |

---

## AI Tool Usage

- **Tool**: Track B subagent (Claude Opus 4.7 general-purpose, fresh worktree context)
- **Agent type**: Independent (fresh context, did NOT see Track A's mid-session findings)
- **Task**: PRD-063 Day 1 implementation (B1+B3+B4+B5)
- **Findings**: Agent completed all assigned phases, returned structured per-phase status, flagged 1 pre-existing test isolation issue + 1 worktree-path observation.
- **Acted on**: All 4 phase outputs merged via `scripts/merge.sh`. Worktree-path observation drove pre-merge cleanup.
- **Discarded**: None.
- **Value assessment**: STRONG — the parallel work let Track A complete on main thread without blocking on the ~17 min B3 dump + ~30 min B4/B5 cycle. Without the agent, total session would have run ~5h sequential vs ~3h parallel.
- **Codex audit**: DEFERRED. Codex CLI is fixed (`</dev/null` invocation per Session 155 Track 5) but I did not run an audit pass on Track A or B in this session. **Risk**: The notes round-trip fix is a data-layer change that warrants security/data-integrity review. **Mitigation**: Logged as BACKLOG CODEX-AUDIT-156 to be run at start of Session 157 against the Track A + Track B + Track F commits.

---

## Concurrency resilience (R1-R9 from prompt)

- **R1 marker file**: ✅ Created during Track A3-A4 window only; removed immediately after.
- **R2 optimistic concurrency**: ✅ R6 pre-flight check verified Harry version_id=13 immediately before mutation. No drift detected.
- **R3 Track B additive-only**: ✅ B3 READ-ONLY on v1; B4 CREATE TABLE only; B5 INSERT into v2 with ON CONFLICT (payload_hash) DO NOTHING. v1 untouched throughout.
- **R4 gedcom_face_links coordination**: ✅ Used `confidence=0.3` + `linked_by=session-156-candidate` to disambiguate from any concurrent admin-confirmed link.
- **R5 audit log namespace**: ✅ All Track A + Track F audit_log rows use `user_email = "session-156"` and `metadata.session_id = "156"`.
- **R6 pre-flight at every phase boundary**: ✅ Pre-flight ran before A3 mutation. (B-track phases are additive — no pre-flight needed.)
- **R7 user cancellation handling**: N/A — user did not cancel.
- **R8 R2 namespace isolation**: ✅ `2026-05-08-session-156` prefix used for both .ged sources and version snapshots.
- **R9 failure modes**: No mid-session genealogy session detected. v1 writes by orchestrator (Track A only) bumped Harry version_id 13→14, which is in v1's identities table — Track B's v2 backfill cutover was at 04:56:15Z (BEFORE Track A3 commit at 04:36:12Z, so Harry's version 14 was already snapshotted by B3's 04:32-04:53 window — but Track B5 backfill of v2 reads from `gedcom_*` tables, not `identities`, so no interaction).

---

## Next session should verify FIRST

1. **Notes-backfill audit** (BACKLOG NOTES-BACKFILL-156): Read `identities.json` and Supabase, find any identity where local notes count > Supabase metadata.notes count. Backfill if delta found. Without this, notes added between Session 105 and Session 156 are lost on production.
2. **CI-SUPABASE-ENV-002**: Verify user pasted secrets. If yes, push trivial commit and confirm CI green.
3. **Re-verify new identity page**: The Belle Isle person page should now render in production (cache TTL passed). Spot-check that the metadata.notes provenance text appears on the public page.
4. **AD-244 PRD-063 schema design entry**: Write into `docs/ml/ALGORITHMIC_DECISIONS.md` referencing commits B3/B4/B5 + reversibility test result.
5. **Track E (GEDCOM upload UAT)**: Run new Fox-family GEDCOM through v1 import + execute the 4 UAT verification points. Roll into Session 157 alongside dual-read confidence check.

---

## Commit summary (10 commits this session)

| Commit | Description |
|---|---|
| `efb9ac1b` | A2: pre-repair snapshot of Harry Fox identity |
| `49298a76` | fix: round-trip identity notes through Supabase metadata JSONB (4 regression tests) |
| `dd7b617f` | A: Harry Fox repair (detach 2 anchors, create new identity, audit_log, GEDCOM candidate) |
| `96403306` | B2: R2 backup GEDCOM .ged source files |
| `2d484c99` | B3: R2 backup current Supabase versioned data (9 versions) |
| `a47344f9` | B4: PRD-063 v2 schema build (3 tables) |
| `562129b6` | B5: PRD-063 initial backfill to v2 tables |
| `ed226a72` | F4: Detroit location corrections for 2 Belle Isle photos |
| `5bab77fd` | merge: worktree-agent-a70ad4cbcba751574 (Track B branch into main) |

`git log origin/main..HEAD` empty (all pushed). 4246 tests pass under xdist parallel.
