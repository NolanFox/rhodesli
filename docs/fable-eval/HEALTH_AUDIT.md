# W1 — Repo + Harness + CI-Reality + Doc-Truth Health Audit

**Synthesis of** `subagents/w1-health.md` (full evidence there). Read-only; every move/delete is
**user-gated** — nothing changed. New-eng-lead framing: map the machine, hand back a staged plan.

## Shape of the machine (one paragraph)
A well-instrumented, heavily-audited solo-maintainer repo whose **process artifacts have outgrown
its product**. The working code is a small minority of a ~20 GB tree dominated by **16 GB of stale
worktrees**, whose size is itself caused by **854 MB of production-data backups accidentally
committed to git** — the same production-data-in-git failure mode the lessons file has cataloged
six times. The safety harness is real (all hooks wired, CI-simulation tooling, allowlisted data
files) but has two decorative layers: permission deny-rules neutered by `bypassPermissions`, and
**three plaintext live credentials** parked in a local settings file. Documentation is the
project's superpower and its biggest tax — the two architecture docs `@`-imported into every
context window describe a JSON-canonical system that stopped existing four months ago.

## Disk map
| Path | Size | Classification |
|------|------|----------------|
| `.claude/` | **16 GB** | 15.9 GB = 17 stale worktrees (~950 MB each). Reclaimable. |
| `rhodesli_ml/` | 3.2 GB | 1.5 GB `checkpoints/` (15 epochs ~99 MB). Mostly reclaimable. |
| `.git/` | 397 MB | size-pack 63.5 MiB; rest = 210 local branches' refs/logs. Partially reclaimable. |
| `app/` | 96 MB | 89 MB `app/static/` crops (load-bearing local; untracked; absent in CI, Lesson 211). |
| `data/` | 60 MB | 14 MB `embeddings.npy` (tracked, load-bearing); ~35 MB `.bak` clutter (reclaimable). |
| `docs/` | 51 MB | 22 MB screenshots + audit trail; load-bearing but unbounded growth. |

## Top 15 issues (ranked impact × effort)

| # | Issue | Evidence | Impact | Effort | Action | Class |
|---|-------|----------|--------|--------|--------|-------|
| 1 | 17 stale worktrees eating 16 GB | `.claude/worktrees/` 16 GB; `git worktree list` 18 entries (sessions 135c/141/167, long merged) | Very high (25% of disk) | Low | `git worktree remove` + `prune` | **user-gated** |
| 2 | **854 MB production-data backups committed to git** (root cause of #1) | `git ls-files \| grep -c data_backup` = 2,051; 3 `data_backup_*` dirs at root | Very high; 7th occurrence of Lessons 56/69/78/85/141 | Med | `git rm -r --cached` + gitignore + move to R2 | **user-gated** |
| 3 | **3 live secrets in plaintext** in `.claude/settings.local.json:71-84` | `SUPABASE_ACCESS_TOKEN=sbp_…`, `RESEND_KEY=re_…`, `R2_SECRET_ACCESS_KEY=9d12…` | High (long-lived keys read into transcripts/backups) | Low | **Rotate all 3 today**, delete cred-bearing allow entries, keep in `.env` | **active** |
| 4 | Permissions wider than needed; deny rules non-enforcing | `settings.json:3` `defaultMode:"bypassPermissions"` neuters rhodes-wiki deny; `settings.local.json` allows `sudo rm:*`,`bash:*`,`curl:*`,`pkill:*` + garbage entries (`Bash(fi)`,`Bash(done)`) | Med-high | Low | Remove `sudo rm:*`/`bash:*`/garbage; implement M8 write-outside-repo hook. **All hooks exist/wired** ✓ | active |
| 5 | **@-imported architecture docs 5mo stale, contradict a Critical Invariant** | `DATA_MODEL.md`+`OVERVIEW.md` ("no relational database", 124 photos/292 identities, "Phase C NOT STARTED") vs Postgres-canonical, 1127/1824, Phase C complete | High — loaded into **every** session, contradicting "Postgres is source of truth" 3 paragraphs up | Low | Rewrite both + `PERMISSIONS.md` to Supabase-canonical | stale-doc |
| 6 | 1.5 GB training checkpoints, 15 near-identical epochs | `rhodesli_ml/checkpoints/date-epoch=00..14` ~99 MB each | Med | Low | Keep best+last, archive rest to R2 | **user-gated** |
| 7 | **BACKLOG.md ~50% stale** | 928 lines (>3× cap); header "v0.99.56, 972 photos, Mar 30" (actual v0.99.89/1127/July); 7 of 15 sampled "Active" items ✅ resolved inline | Med-high — "ONE authoritative backlog" (Lesson 29) untrustworthy | Med | Archive ✅ items, refresh header, split <300 | stale-doc |
| 8 | 210 local branches, 175 already merged | `git branch --merged main \| wc -l` = 175 | Med | Low | `git branch -d` merged (after #1); `git gc` | **user-gated** |
| 9 | **95 docs over the 300-line cap** (own invariant) | ALGORITHMIC_DECISIONS.md **2,942**, SESSION_HISTORY 1,724, BACKLOG 928, HARNESS_DECISIONS 728… | Med — ML rule says "ALWAYS read ALGORITHMIC_DECISIONS" = 2,942 lines into context | Med | Apply `doc-size-enforcement.md` split pattern (per-range sub-files + hub) | active |
| 10 | `.claude/rules/` redundancy: 54 files, ~1.9K lines, 3 overlap clusters | session-end checklist restated in 4 files; /clear discipline in 3; Codex invocation duplicated; transcript-gate threshold appears as both 600 and "was 800" | Med — all load as instructions; overlap = context tax + drift | Med | Consolidate to declared parents; children = 5-line pointers; target ≤30 | active |
| 11 | Stale/mis-marked tests | TEST-DEBT-130 (`test_supabase_data.py` still asserts removed `identity_overrides`); 3 `@slow` tests excluded from BOTH test-fast AND CI (run nowhere); Makefile `lint` misses `rhodesli_ml/` that CI lints (Lesson 209 shape) | Med | Low | Fix TEST-DEBT-130; add rhodesli_ml to Makefile lint; promote/schedule slow tests. Heavy-dep skips = mitigated (Lesson 210) | active |
| 12 | scripts/ 188 files, ≥41 one-shot session scripts | `ls scripts \| wc -l`=188; `scripts/_archive/` convention exists | Low-med | Low | Archive completed one-shots (keep session153_shadow_eval — live per DETROIT-PROMOTE-167) | **user-gated** |
| 13 | data/ `.bak` clutter (~35 MB untracked) | `embeddings_local_backup.npy` 12 MB, `.bak` files; only 20 data/ files tracked (allowlist ✓) | Low | Low | Archive/delete after Supabase parity check (JSON = backup-only) | **user-gated** |
| 14 | docs/ media growth (22 MB screenshots, 336 context, 222 prompts in git) | 1,439 tracked docs files, 51 MB | Low | Med | Retention policy: old screenshots → R2, keep markdown trail | **user-gated** |
| 15 | Dead-code clean; residual monolith | every module imported (only `__init__.py` false positive); `app/page_routes.py` **596 KB** > main.py; leftover `stop-gate.sh.pre-loopbreaker.bak` | Low now | Med | Add page_routes.py to REFACTOR-001; delete `.bak` | active / user-gated |

## Constraint checks
- **Hooks:** all 4 (`stop-gate`, `pre-work-clear-gate`, `post-edit-format`, `post-commit-clear-gate`)
  + `test-gate.sh` exist and are wired. No missing refs. ✓
- **CI reality** (`.github/workflows/test.yml`): lint (ruff incl. rhodesli_ml) → `make test-fast`
  (`-m "not slow"`) → `pytest rhodesli_ml/tests/`. S168 CI-sim tooling present. `make test-full`
  exists but not CI-run (manual pre-deploy gate) and is app-only (no ML suite).
- **Git state:** unpushed commits = this eval's own work (push gated to orchestrator). Remote clean;
  the 210-branch problem is local-only.

## The one high-value cleanup session (recommended sequence)
Worktree prune (#1) → untrack data backups (#2) → **rotate 3 secrets (#3)** → rewrite the two
`@`-imported architecture docs (#5). Reclaims ~18 GB and materially raises every future session's
context signal-to-noise. **All deletions/moves require Nolan's approval — nothing done this run.**
