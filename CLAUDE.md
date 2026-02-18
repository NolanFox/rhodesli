## Project Roadmap
@ROADMAP.md

Always check ROADMAP.md at session start. When completing ANY task, update ALL THREE:
1. **ROADMAP.md** — `[x]`, date, move to "Recently Completed"
2. **docs/BACKLOG.md** — Status to DONE, add date
3. **CHANGELOG.md** — entry under current version
Run: `python scripts/verify_docs_sync.py`

# Rhodesli — Jewish Heritage Photo Archive

## Quick Reference
- **Stack**: FastHTML, InsightFace/AdaFace, Supabase Auth, Railway, R2
- **Admin**: NolanFox@gmail.com | **Live**: https://rhodesli.nolanandrewfox.com
- **Test**: `pytest tests/ -v --ignore=tests/e2e/` | **Deploy**: push to main
- **Local**: `source venv/bin/activate && python app/main.py`

## Architecture
- `app/main.py` — FastHTML web app | `core/` — ML (local only) | `data/` — JSON (read-only)
@docs/architecture/OVERVIEW.md @docs/architecture/DATA_MODEL.md
@docs/architecture/PERMISSIONS.md @docs/architecture/PHOTO_STORAGE.md

## Rules (Non-Negotiable)
1. Every change gets tests (happy path + failure + regression)
2. Permission changes require route x auth-state matrix tests
3. Never delete data — merges must be reversible
4. No Generative AI — forensic matching only
5. Data read-only — use scripts with --dry-run, never modify data/*.json directly
6. HTMX auth: return 401 (not 303) for protected endpoints
7. Admin-first: new data-modifying routes default to _check_admin
8. No doc >300 lines, CLAUDE.md <80 lines — split if growing
9. Update CHANGELOG.md before ending sessions with user-visible changes
10. ML changes require reading docs/ml/ALGORITHMIC_DECISIONS.md first
11. New algorithmic decisions: AD-XXX format before code is committed
12. JS: global event delegation via data-action — NEVER bind to HTMX-swapped nodes
13. New reference docs need corresponding `.claude/rules/` in same commit
14. Test isolation: mock both load AND save. See `.claude/rules/test-isolation.md`
15. New data files: whitelist .gitignore + REQUIRED_DATA_FILES + git commit together
16. Photo entries must pass `validate_photo_entry()` before persistence
@docs/CODING_RULES.md for detailed rules

## Forensic Invariants (LOCKED)
1. Embeddings read-only for UI | 2. Merges reversible | 3. neighbors.py FROZEN
4. UI never deletes a face | 5. provenance="human" > provenance="model"

## Development Process
- **SDD**: `.claude/rules/spec-driven-development.md` (PRD -> e2e tests -> implement -> verify)
- **Decision Provenance**: AD-NNN, OD-NNN, HD-NNN (see Key Docs below)
- **Session Management**: `.claude/rules/prompt-decomposition.md`, `phase-execution.md`, `verification-gate.md`
- **Feature Reality Contract**: `.claude/rules/feature-reality-contract.md`
- Back up data/ before any migration (AD-047)

## Workflow
1. Read `tasks/lessons.md` and `tasks/todo.md` at session start
2. Plan before coding — update todo.md with checkboxes
3. Commit after every sub-task (conventional commits)
4. Add lessons to lessons.md after any correction

## Session Completion Checklist
1. `pytest tests/ -x -q --ignore=tests/e2e/` | 2. `python scripts/verify_data_integrity.py`
3. `python scripts/verify_docs_sync.py` | 4. `git status` — no untracked data/ changes
5. Dockerfile covers new imports | 6. requirements.txt updated | 7. CHANGELOG.md updated

## Batch Ingest Rules
- Explicit collection + source required | Back up data/ first | Verify counts before/after

## Compaction Instructions
Preserve: current task status, files modified, test commands, active bugs

## Key Docs (read on-demand)
- `docs/architecture/` — OVERVIEW, DATA_MODEL, PERMISSIONS, PHOTO_STORAGE
- `docs/ml/` — ALGORITHMIC_DECISIONS (AD-NNN), MODEL_INVENTORY
- `docs/ops/` — OPS_DECISIONS (OD-NNN), PIPELINE
- `docs/HARNESS_DECISIONS.md` — Workflow/harness decisions (HD-NNN)
- `docs/prds/` — PRDs | `docs/CODING_RULES.md` | `docs/ROLES.md`
- `tasks/lessons.md` — persistent learnings | `tasks/todo.md` — task tracking
@tasks/lessons.md for past mistakes and prevention rules
