# Session 156 Log

**Date**: 2026-05-08
**Mode**: Implementation
**Predecessor**: Session 155
**Successors planned**: 157 (PRD-063 Day 2), 158 (PRD-063 Day 3 cutover)
**Critical deadline**: 2026-05-29 (Supabase free-tier 1.1 GB ceiling)

## Phase checklist

- [x] **Phase 156-0**: Recovery verification (all 7 Session 155 artifacts on origin/main)
- [x] **Track A**: Harry Fox repair (option c) executed on production
  - [x] A1: gates verified
  - [x] A2: pre-snapshot committed (`efb9ac1b`)
  - [x] Notes round-trip fix (mid-session discovery, `49298a76`)
  - [x] A3+A4: detach + create new identity + provenance + GEDCOM candidate + audit_log (`dd7b617f`)
  - [x] A5: structural tests pass (12), Supabase queries verify, browser verify (post-TTL)
- [x] **Track B**: PRD-063 Day 1 (worktree subagent)
  - [x] B1: PRD verified at canonical path (221 lines)
  - [x] B2: R2 backup of new Fox-family GEDCOM source (main thread, `96403306`)
  - [x] B3: 9 versions archived to R2 + reversibility test (`2d484c99`)
  - [x] B4: v2 schema applied (`a47344f9`)
  - [x] B5: initial backfill (`562129b6`) — 21,998 individuals + 6,741 families + 9 manifest rows
  - [x] Merge: worktree branch → main (`5bab77fd`)
- [x] **Track C**: CI secrets uploaded (5 of 5) via `gh secret set`. Verified `total_count: 5`. New CI failure (CI-COMPARE-FAIL-156) is unrelated.
- [x] **Track F**: Location-correctness UAT
  - [x] F1: photos identified (Detroit 02068+01659; Asheville `3192877a90a174e9` user-confirmed)
  - [x] F2/F3: bugs found — 02068 stored as NYC, 01659 as generic US
  - [x] F4: manual Detroit fix with audit_log (`ed226a72`)
  - [x] F5: Asheville already correct
- [-] **Track E**: GEDCOM upload UAT — DEFERRED to Session 157
- [x] **Phase 156-D**: Closeout (assessment + CHANGELOG + ROADMAP + BACKLOG, `e3f34acc`)

## Verification gate results

| Gate | Method | Result |
|---|---|---|
| Recovery from 155 timeouts complete | Phase 156-0 ls/grep | ✅ PASS |
| Harry repair shipped | Direct Supabase query | ✅ PASS (anchors 7→5, version 13→14, audit_log row) |
| New identity created | Direct query + browser | ✅ PASS (state=INBOX, 2 anchors, metadata.notes count=1, GEDCOM candidate) |
| Provenance note visible | Browser /person/ef39908e | ✅ PASS (15 "Belle Isle"/"originally misidentified" matches in HTML) |
| PRD-063 at canonical path ≤ 300 lines | wc -l | ✅ PASS (221 lines) |
| R2 .ged source backup | Roundtrip test | ✅ PASS (size + sha256 match) |
| R2 versioned data backup | Reversibility on v9 | ✅ PASS (21,228 rows parity) |
| v2 schema applied | to_regclass | ✅ PASS (3 tables) |
| Initial backfill complete | COUNT(*) | ✅ PASS (21,998 + 6,741 + 9) |
| Detroit location fix | Direct query + audit_log | ✅ PASS (both photos at lat 42.3314 conf=high) |
| Asheville location | Direct query | ✅ PASS (already correct) |
| CI secrets uploaded | gh api | ✅ PASS (total_count: 5) |
| CI green | gh run | ⚠️ PARTIAL — secrets unblocked, new test failure (CI-COMPARE-FAIL-156, unrelated) |
| `make test-fast` | xdist parallel | ✅ PASS (4246 passed) |
| `git log origin/main..HEAD` | git | ✅ EMPTY (all pushed) |
| `git status` | git | ✅ EMPTY |

## Commits this session (10)

| Hash | Description |
|---|---|
| `efb9ac1b` | A2: pre-repair snapshot of Harry Fox identity |
| `49298a76` | fix: round-trip identity notes through Supabase metadata JSONB (4 regression tests) |
| `dd7b617f` | A: Harry Fox repair (detach 2 anchors, create new identity, provenance, GEDCOM candidate, audit_log) |
| `96403306` | B2: R2 backup GEDCOM .ged source files |
| `2d484c99` | B3: R2 backup current Supabase versioned data (9 versions) |
| `a47344f9` | B4: PRD-063 v2 schema build (3 tables) |
| `562129b6` | B5: PRD-063 initial backfill to v2 tables |
| `ed226a72` | F4: Detroit location corrections for 2 Belle Isle photos |
| `5bab77fd` | merge: worktree-agent-a70ad4cbcba751574 (Track B branch into main) |
| `e3f34acc` | docs: closeout — assessment + CHANGELOG v0.99.72 + ROADMAP + BACKLOG |
| `25606a3d` | docs: add CI-COMPARE-FAIL-156 BACKLOG entry |

## Mid-session discoveries

1. **Notes round-trip pre-existing bug**: `add_note()` writes top-level `identity["notes"]` but `shadow_write_identity` only persists `metadata` JSONB. Notes have been silently lost on Supabase round-trip since Session 105. Fixed (commit `49298a76`) with 4 regression tests. Backfill follow-up logged (NOTES-BACKFILL-156).
2. **Worktree isolation gap**: Track B subagent wrote files to main repo paths instead of worktree paths despite `isolation: "worktree"`. Pre-merge `cmp` verified content was byte-identical to worktree branch versions; cleanup before merge proceeded normally. Logged as WORKTREE-ABS-PATH-LEAK.
3. **GitHub secrets actually empty**: User initially said secrets were pasted but `gh api repos/.../actions/secrets` returned `total_count: 0`. Walked user through `gh secret set` automation; all 5 uploaded directly from local `.env`.
4. **Detroit location bug confirmed**: photo 02068 stored as "New York City"; 01659 stored as generic "United States". Both manually fixed with audit_log + evidence chain.
5. **CI-COMPARE-FAIL-156**: After secrets unblocked test_identity_suggestions, a different test (test_compare_upload_stages_file) revealed a CI-environment-specific failure — passes locally, fails in CI. Logged for follow-up.

## Concurrency resilience (R1-R9)

R1-R9 from session prompt all satisfied:
- R1 marker file held only during A3-A4 irreversible window
- R2 optimistic concurrency: pre-flight verified Harry version_id=13 immediately before A3
- R3 Track B additive-only confirmed (READ-ONLY on v1; CREATE TABLE only; INSERT with ON CONFLICT DO NOTHING)
- R4 GEDCOM link coordination: confidence=0.3 + linked_by=session-156-candidate disambiguation
- R5 audit log namespace: all rows use user_email="session-156" + metadata.session_id="156"
- R6 pre-flight ran before A3
- R7 user did not cancel
- R8 R2 namespace `2026-05-08-session-156` (no collisions)
- R9 no genealogy session interference detected

## AI tool usage

**Track B subagent** (Claude Opus 4.7 general-purpose, fresh worktree context):
- Independent (no prior context)
- Task: B1+B3+B4+B5 PRD-063 implementation
- All 4 phases delivered, structured per-phase return
- Value: STRONG — parallel work cut session time from ~5h sequential to ~3h
- Flagged 2 issues correctly: pre-existing test isolation gap + worktree-abs-path observation

**Codex CLI**: NOT used in 156. Codex audit deferred to Session 157 first commit (CODEX-AUDIT-156 BACKLOG).

## Follow-ups for Session 157

In priority order:
1. AD-244 entry (PRD-063 schema design) referencing merged commits B3/B4/B5
2. CODEX-AUDIT-156 (independent audit of 156 changes)
3. NOTES-BACKFILL-156 (delta-write any local-only notes to Supabase metadata)
4. Re-verify CI green after CI-COMPARE-FAIL-156 fix (or skipif decision)
5. Track E (GEDCOM upload UAT) — new GEDCOM is in R2 already (B2)
6. PRD-063 Day 2: full backfill + dual-read confidence check
7. PRD-LOCATION-001 — iterate Gemini prompt on Detroit photos
8. GEDCOM-V2-OTHER-TABLES — decide v2 strategy for events/relationships/records
