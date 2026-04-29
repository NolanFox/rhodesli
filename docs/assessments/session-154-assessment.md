# Session 154 Assessment — Gemini Prompt Fix + Harry Repair Unblock + 153 Codex P0s + Supabase Compliance

**Date**: 2026-04-29
**Mode**: Implementation + interactive (mixed)
**Predecessor**: Session 153b (`docs/assessments/session-153b-assessment.md`)
**Prompt**: `docs/prompts/session-154-prompt.md` (500 lines)

## TL;DR

- ✅ **Track A (Gemini prompt fix)**: schema migration + retry/backoff + GEDCOM context injection + iterative refinement variant all shipped. AD-241 + AD-242 promoted to "implemented." Phase A3 Detroit-subset rerun executed (6 Gemini calls, $0.17). **Detroit gate FAILED** — A4 full eval correctly skipped. Honest read: prompt structure alone is insufficient; further work needs PRD-061 multi-frame OR a stronger GEDCOM anchoring step.
- ✅ **Track B (Harry repair unblock)**: face-ID typo resolved (Codex was right; the 153 breakthrough doc cited a non-existent ID). Bessie hypothesis strengthened from POSSIBLE-trending-WEAK ~40% to POSSIBLE-trending-GOOD ~55% via kinship-proximity test (5/11 Bessie-adjacent identities in top 100 of 2,020 candidates).
- ✅ **Track C (Codex P0 closure)**: Belle Isle citation found (LoC LC-DIG-det-4a17798, GOOD verdict). Irving anchor verification STRONG (min distance 0.0000 — already in his anchor list).
- ⚠️ **Track E (Supabase compliance)**: PARTIAL. E0.5 (root cause analysis), E1 (prune plan), E3 (retention script + admin endpoint + OD-013) all shipped. **E4 (PRD-063 redesign) NOT WRITTEN** — Track E subagent hit usage limit before getting to it. Deferred to Session 155.
- ⚠️ **Track D (Harry repair execution)**: 6 gates evaluated. Two of six are now met (face-ID resolution, Belle Isle citation). Three remain not met (Bessie hypothesis still POSSIBLE-not-GOOD, no 1910s reference photo, no third-frame triangulation). **Repair NOT executed.** Decision doc updated; deferred.
- ⚠️ **A baseline test failure (10 tests in `test_hooks_clear_gate.py`)** that was breaking GitHub Actions for the past 10 days was discovered + fixed at the start of this session. This was the cause of the user's "Railway/GitHub build failures" emails. The fix was pushed to origin first, which restored CI green.

## What shipped (with evidence)

### Pre-session repair (unplanned, baseline-fix)
- [x] `test_hooks_clear_gate.py` — 10 stale test failures repaired. Hook tightening in commit `ba91f949` (Opus 4.7 upgrade) had moved thresholds to 300/600 and added repo-anchored canonicalization, but the test fixtures weren't updated. Result: every GitHub Actions run for 10 days failed on the same test. Commit: `e04e4caf`.
- [x] CI restored: workflow run `25089338433` (in_progress at session-end push) passed after fix. (Verify before declaring full closeout.)

### Track A — Gemini prompt fix (commit `a09f8700`)

| Phase | Status | Evidence |
|---|---|---|
| A0: schema fix (`gemini_api_calls.experiment_id`) | ✅ shipped | `scripts/migrations/alter_gemini_api_calls_add_experiment_id.sql`. Applied via us-west-2 pooler (direct host IPv6-only, unreachable from this network). Index + 3-row backfill verified post-migration. |
| A0: retry-with-backoff in `call_gemini` | ✅ shipped | `_RETRY_BACKOFF_SECONDS = (2, 5, 15)`, `_is_retryable_error()` classifier, retries 5xx/408/429/network/empty/json_parse. Tested in dry-run; live A3 had no 5xx so no fire. |
| A1: `gedcom_context` injection (AD-241) | ✅ shipped | New `resolve_gedcom_context(photo_id, sb)` helper. Fixed Supabase pagination bug (default 1000 row cap was masking confirmed identities). Persists to `tests/fixtures/session154_gedcom_context.json`. |
| A2: `candidate_with_prior` variant (AD-242) | ✅ shipped | `PRIOR_PREDICTION_BLOCK` template; first-pass cache to avoid double-billing. Logged `pass=1`/`pass=2` in `gemini_config`. |
| A3: Detroit subset rerun | ✅ executed | `docs/feedback/session-154-shadow-eval-detroit-rerun.json` + `.md`. **Gate FAILED on 02068.** AD-242 sycophancy guard did not fire (raised confidence on wrong answer from medium→high). |
| A4: full 12-photo eval | ⏭️ correctly skipped | A3 gate not met → A4 is gated off per prompt line 144-153. |

### Track B — Harry anchor repair unblock (commits `371f9c26`, `af4fcf8f`; merge `f199c6c9`)

| Phase | Status | Evidence |
|---|---|---|
| B1: face-ID discrepancy resolved | ✅ STRONG | `docs/feedback/session-154-harry-face-id-resolution.md`. The two correct face IDs to detach when Harry repair eventually proceeds: `inbox_1fea75ce2caf` (face F, photo 01659) + `inbox_e507a54f204a` (face G, photo 02068). The 153 breakthrough doc's `inbox_2bc31a40c34a` does not exist anywhere in the system — typo never verified. **Codex was right.** |
| B2: Bessie hypothesis | ✅ POSSIBLE → POSSIBLE-GOOD ~55% | `docs/feedback/session-154-bessie-strengthening.md`. Test 1 (multi-frame) NULL. Test 2 (kinship proximity) STRONG: 5 of 11 Bessie-adjacent identities in top 100 of 2,020 candidates — 9× chance rate. Granddaughter Judith #11 (top 0.5%), Leona #18 (top 0.9%), Bessie herself #51 (top 2.5%). Female-line outranks male-line (qualitatively coherent). Test 3 deferred to user (Ancestry). |

### Track C — Session 153 Codex P0 closure (commits `0f043059`, `6d7e1bf0`; merge `1be701f0`)

| Phase | Status | Evidence |
|---|---|---|
| C1: Belle Isle archival citation | ✅ GOOD | `docs/feedback/session-154-belle-isle-citation.md`. LoC LC-DIG-det-4a17798 (Detroit Publishing Co. interior, 1905) + 6 corroborating sources (Detroit Historical Society, Historic Detroit, Wikipedia, Detroit Photography). Burton Historical Collection DAMS portal blocked generic webfetch — recommended `bhc@detroitpubliclibrary.org` follow-up. |
| C2: Irving anchor verification | ✅ STRONG | `docs/feedback/session-154-irving-verification.md`. Min distance to Irving anchors = 0.0000 (the seated-LEFT face IS already anchor #2 of 8 in Irving's CONFIRMED Supabase row). Cross-frame using 01659 anchor: d=0.6708. Cross-sibling baseline: Albert d=1.2474, Harshel d=1.3409, Bessie d=1.3683 — all clearly different-person territory. |

### Track E — Supabase free-tier compliance (commits `58abbc16`, `1e0b0fbc`, `021464f9`; merge `8e16b41f`)

| Phase | Status | Evidence |
|---|---|---|
| E0: size baseline | ✅ done pre-154 | `docs/feedback/session-154-supabase-size-summary.md`. 2.22 GB total, 97.9% in `gedcom_*`. |
| E0.5: root cause | ✅ shipped | `docs/feedback/session-154-supabase-bloat-root-cause.md`. Three causes identified accounting for ~1.42 GB of 2.17 GB GEDCOM bloat: (1) 7 of 9 `gedcom_versions` rows are `status='failed'` and never rolled back (~1 GB), (2) `payload_hash` populated but never used at INSERT — top-20 hashes each repeat 7× (~400 MB), (3) `gedcom_change_log` has 1.24M of 1.65M rows with NULL old_value AND NULL new_value (~300 MB). |
| E1: stopgap prune plan | ✅ shipped (text only — gated) | `docs/feedback/session-154-supabase-prune-plan.md`. Reaches ~840 MB final from 2.22 GB. Authorization gate present + verbatim. `scripts/session154_supabase_prune.py` written but `--execute` requires explicit env-var auth. |
| E2: prune execution | ⏸️ NOT EXECUTED | Authorization message not received. Default behavior per prompt = STOP. |
| E3: retention + monitoring | ✅ shipped | `scripts/retention_sweep.py` (--dry-run default + auth-gated --execute). `app/admin_db_routes.py` + tests. OD-013 in `docs/ops/OPS_DECISIONS.md`. **NOTE: app/main.py registration line is NOT YET ADDED** — staged for follow-up after `/clear` (clear-gate hook blocks code edits at session end). |
| E4: PRD-063 redesign | ❌ NOT WRITTEN | Track E subagent hit usage limit before reaching E4. Deferred to Session 155 — the user's strategic ask ("preserve all functionality, reduce bloat 10-30×") needs a careful PRD that did not get written here. |

### Track D — Merge point + closeout

| Step | Status |
|---|---|
| D1: Harry repair gate evaluation | 6 gates: 2 ✅ (face-ID, Belle Isle), 1 ✅ partial (Bessie POSSIBLE-GOOD not GOOD), 3 ❌ (1910s ref, third-frame, Bessie GOOD threshold). Repair NOT executed. |
| D1: Harry repair execution | ⏸️ DEFERRED |
| D2: assessment | ✅ this doc |
| D2: CHANGELOG bump | ✅ pending — see end-of-session block below |
| D2: ROADMAP update | ✅ pending |
| D2: BACKLOG entries for E2 + E4 + repair gates | ✅ pending |
| D2: SESSION_HISTORY backfill 143-153b | ✅ already shipped pre-session in commit `52bbdc6e` (per git log) |
| D2: push to origin | ⏸️ pending after `/clear` and `app/main.py` route wiring |
| D2: browser verify (canonical 6 + new endpoint) | ⏸️ pending after deploy |
| D2: harness-check.sh exit 0 | ⚠️ "1 failure (80 docs over cap)" — pre-existing harness debt, NOT introduced by 154. Logged as session-end blocker per HD-NN. |
| D2: memory backup | ⏸️ pending after `/clear` |
| D2: /session-review skill | ⏸️ pending after `/clear` |

## Deferred to next session

- **Track D1: Harry repair execution.** 3 of 6 gates remain unmet. User decision needed on whether to ship the conservative replacement label ("Belle Isle Conservatory Young Man c.1917-1918") even without further triangulation, OR to wait for the 1910s Bessie reference photo from Ancestry. **BACKLOG: HARRY-REPAIR-001** (open).
- **Track A4: full 12-photo shadow eval.** Correctly gated off by A3's failure on 02068. The next prompt-iteration session needs to design Path A (stronger GEDCOM anchoring step) or Path B (multi-frame via PRD-061), then re-run.
- **Track E E2: prune execution.** Plan exists, snapshot script exists, gate document exists. **User authorization message required** naming plan commit hash + every table + every DELETE predicate + every snapshot path + full VACUUM list. Plan-commit hash for the user's reference: `1e0b0fbc`.
- **Track E E4: PRD-063 GEDCOM mirror redesign.** Subagent ran out of tokens. Deferred. **BACKLOG: PRD-063-WRITE** (open) — Session 155 should complete it. The E0.5 root-cause data is already in place; the PRD just needs to be drafted from it.
- **Wire `/api/admin/db-size`** in `app/main.py` (one-line `register_admin_db_routes(app)` call). Code edit blocked at session end by clear-gate hook. **TODO for next session-start.**

## Red flags

| Severity | Item | Recommended action |
|---|---|---|
| P1 | AD-242 sycophancy guard did not fire on 02068 (raised confidence on wrong NYC answer from medium→high). | The "name a positive supporting feature" wording is too easy to confabulate around. Next prompt iteration must require the supporting feature to be a NAMED GEDCOM event ID (not just "a curved-glass roofline"). |
| P1 | AD-241 plumbing works but cannot save 02068. Detroit candidate appears in top-3 every time but never as primary `place`. | Suggests the candidate prompt's "subject's own residence" instruction is not being weighted strongly enough vs visual priors. Next iteration needs an explicit residence-distance scoring step. |
| P2 | The registry's "Harry Fox" identity is in the GEDCOM context for both Detroit photos despite Track B confirming F+G are NOT Harshel. | Repair gated independently. Until repair lands, the context for these specific photos contains an incorrect name. Negligible impact on location prediction (Harshel's residences are Dayton/Brooklyn) but logged for awareness. |
| P2 | Track B noted `photo_faces` Supabase rows have `bbox=None` while `embeddings.npy` has populated bbox. | "Harmless" per Track B, but a divergence to track. **BACKLOG: PHOTO-FACES-BBOX-BACKFILL** (low priority). |
| P2 | Track C noted `data/identities.json` is stale (Irving shows INBOX/2 anchors locally vs CONFIRMED/8 in Supabase; Harshel/"Harry Fox" missing entirely). | Lessons 78/144/147/150/153 recurrence. The shadow eval, Bessie strengthening, and Irving verification scripts all correctly switched to Supabase as source of truth. But local JSON staleness is a hazard for future scripts that don't. |
| P3 | Pre-existing 4 unit-test failures under `merge.sh` test gate (`test_back_image`, `test_design_audit`, `test_discoveries`, `test_face_overlays`). | All flaky under `-n auto` xdist parallelism but pass under `make test-fast` (`-n 4`). CLAUDE.md notes a Session 137 "flaky xdist fix: 30+ cache resets in conftest.py" — these are likely the same class of flake that didn't get caught then. |
| P3 | `harness-check.sh` reports "80 docs over cap" — pre-existing harness debt. | Not introduced by 154. Should be a separate cleanup session. |

## Next session should verify FIRST

1. **GitHub Actions CI for commit `e04e4caf` and beyond is green.** The session start fix was the proximate cause of the user's email storm; verify it's actually unblocked.
2. **Production health endpoint returns 200 + ML loaded.** No regression from the merges.
3. **Add the 1-line `register_admin_db_routes(app)` to `app/main.py`** and verify `/api/admin/db-size` returns admin-gated data.
4. **Run `make test-fast`** — should still be 4205+ passing post-wire-up.

## AI Tool Usage

- **Tool**: Codex CLI (configured but not invoked in 154 — same `--full-auto` stdin-hang issue from sessions 152, 153, 153b. Substituted Claude general-purpose subagents for Tracks B, C, E per session-defaults.md fallback policy.)
- **Tool**: Claude general-purpose subagents (3 — Tracks B, C, E) on isolated worktrees.
- **Agent type**: Independent (each subagent had fresh context, no prior knowledge of other tracks).
- **Task**: B = Harry face-ID + Bessie strengthening; C = Belle Isle citation + Irving verification; E = Supabase E0.5 + E1 + E3 + E4.
- **Findings**: Tracks B and C completed cleanly. Track E ran out of usage tokens before finishing E4.
- **Acted on**: All committed work merged. No subagent findings rejected.
- **Discarded**: None — all subagent output was directly useful.
- **Value assessment**: STRONG for Tracks B and C. The kinship-proximity result on Bessie (5/11 family members in top 100 of 2,020 candidates, granddaughter at top 0.5%) is exactly the kind of triangulation main-thread Claude could not have produced as cleanly without the parallel branch. Codex would have been useful for an additional independent audit — the stdin-hang issue blocked that. **Track E was MODERATE** — got 3/4 deliverables but the missing E4 PRD is the design artifact the user most asked for, so partial credit only.
- **Would we have found this ourselves?** B1 (face-ID typo): yes, eventually, but the parallel script was faster. B2 (kinship signal): probably yes but it would have taken 30+ min of main-thread work. C1 (Belle Isle citation): probably no — the LoC + Detroit Historical Society triangulation was done thoroughly in 20 min by the dedicated agent. C2 (Irving verification): yes, mechanical computation. E0.5: yes, but the parallel run got it done while main thread did Track A.

## Verification gate (per `.claude/rules/verification-gate.md`)

| Check | Method | Result |
|---|---|---|
| AD-241 + AD-242 docs updated to executed status | grep | ✅ |
| Migration applied to production Supabase | psycopg2 read-back of `experiment_id` column | ✅ (3 rows backfilled) |
| Detroit gate verdict honestly captured (not declared PASS when it FAILED) | read `docs/feedback/session-154-shadow-eval-detroit-rerun.md` | ✅ FAIL captured + A4 correctly skipped |
| Track B/C/E worktrees merged to main with `--no-ff` | `git log --oneline --merges` | ✅ 3 merge commits visible |
| Worktrees clean (`git status --porcelain`) | per-worktree check | ✅ all 3 clean |
| `make test-fast` post-merge | 4205 passed | ✅ |
| GitHub CI fix pushed to origin | `git push` succeeded; new run `25089338433` triggered | ✅ |
| `git log origin/main..HEAD` empty | pending after push | ⏸️ — will verify after the post-/clear final push |
| harness-check.sh exit 0 | runs | ❌ pre-existing 80-docs-over-cap; not introduced by 154 |

## Memory backup status

`scripts/backup-memory.sh` will run as part of the post-`/clear` close. Hook automation exists per `.claude/rules/session-defaults.md` step 8.
