@ROADMAP.md

# Rhodesli — Heritage Photo Archive for the Jewish Community of Rhodes

## Stack
FastHTML + HTMX | Supabase/Postgres | Cloudflare R2 | Railway | InsightFace + Gemini

## Quick Reference
- **Admin**: NolanFox@gmail.com | **Live**: https://rhodesli.nolanandrewfox.com
- **Deploy**: `git push origin main`

## Testing
- Per-commit: `make test-fast` (<30s, unit tests, parallel via pytest-xdist)
- Pre-deploy: `make test-full` (all tests, parallel)
- ML tests: `make test-ml` (rhodesli_ml/ package)
- Merge branches: `./scripts/merge.sh branch1 [branch2...]`
- Parallel sessions: create `.claude/parallel_session_active` to block main commits

## Critical Invariants
- Postgres is source of truth for all structured data (not JSON files)
- ML outputs use Gatekeeper pattern: proposals -> admin review -> confirmed
- Confirmed data feeds back as ground truth anchors
- Embeddings read-only for UI | Merges reversible | neighbors.py FROZEN
- UI never deletes a face | provenance="human" > provenance="model"
- Every change gets tests (happy path + failure + regression)
- No doc >300 lines, CLAUDE.md <80 lines

## Architecture
@docs/architecture/OVERVIEW.md @docs/architecture/DATA_MODEL.md
@docs/architecture/PERMISSIONS.md @docs/architecture/PHOTO_STORAGE.md

## Domain Rules
See `.claude/rules/ml-development.md` — ML code modification protocol
See `.claude/rules/data-layer.md` — Postgres-first data architecture
See `.claude/rules/session-protocol.md` — Session execution discipline
See `docs/CODING_RULES.md` for detailed coding, testing, data safety rules

## Session Protocol
See `.claude/skills/session-run.md` — Overnight/autonomous execution
See `.claude/skills/deploy-verify.md` — Deploy + production smoke test

## Workflow
1. Read `tasks/lessons.md` + `tasks/todo.md` at session start
2. Commit after every sub-task (conventional commits)
3. Use /clear between phases (NEVER /compact — blocked by hook)
4. Set `.claude/current_session.txt` at session start
@tasks/lessons.md for past mistakes and prevention rules

## Hook Enforcement (Deterministic, .claude/settings.json)
- **Stop**: Blocks session end until: assessment exists + clean git
- **PreToolUse (Bash)**: Runs `make test-fast` before git commit; blocks main commits during parallel sessions
- **PostToolUse (Edit|Write)**: AD reminder for ML/core file edits
- **PostToolUse (Bash)**: Test reminder after git commit/merge
- **UserPromptSubmit**: Parallelization reminder
- **PreCompact**: Warning (manual) + recovery (auto)
NOTE: /compact banned by convention (use /clear instead).

## Mandatory Session Outputs
Every session MUST produce before final commit:
1. `docs/assessments/session-NNx-assessment.md` — Self-evaluation of every phase
2. Updated `SESSION_LOG.md` — Running log (archived to `docs/session_logs/` at session end)
3. Updated `ALGORITHMIC_DECISIONS.md` — All decisions with provenance
4. Updated `CHANGELOG.md`, `ROADMAP.md`, `BACKLOG.md`

## Browser Verification Rule
All UX changes MUST be verified in production browser before session ends.
- Primary: Claude Chrome browser plugin (admin is logged in)
- Fallback: Playwright with Supabase API auth
- "Auth required" is NOT a valid reason to skip browser verification
- Screenshots saved to `docs/screenshots/session-NNx/`

## Key Docs (read on-demand)
- `docs/ml/ALGORITHMIC_DECISIONS.md` — All ML decisions (AD-NNN)
- `docs/ops/OPS_DECISIONS.md` — Ops decisions (OD-NNN)
- `docs/HARNESS_DECISIONS.md` — Workflow decisions (HD-NNN)
- `docs/DESIGN_DECISIONS.md` — UX/design decisions (DD-NNN)
- `docs/prds/` — Product requirement docs
