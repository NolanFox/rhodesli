## Project Roadmap
@ROADMAP.md

Always check ROADMAP.md at the start of every session to understand current priorities.
When starting tasks: ROADMAP.md — change `[ ]` to `[-]`, add start date.
When completing ANY task, update ALL THREE:
1. **ROADMAP.md** — check the box `[x]`, add date, move to "Recently Completed"
2. **docs/BACKLOG.md** — find the matching item ID, change Status to DONE, add date in Notes
3. **CHANGELOG.md** — add entry under current version (create new section if needed)

A task is NOT complete until all three files are updated.
After updating docs, run: `python scripts/verify_docs_sync.py`

# Rhodesli — Jewish Heritage Photo Archive

## Quick Reference
- **Stack**: FastHTML, InsightFace/AdaFace, Supabase Auth, Railway, Cloudflare R2
- **Admin**: NolanFox@gmail.com (only admin)
- **Live**: https://rhodesli.nolanandrewfox.com
- **Test**: `pytest tests/ -v --ignore=tests/e2e/`
- **E2E Test**: `pytest tests/e2e/ -v` (requires Playwright + Chromium)
- **Deploy**: push to main (Railway auto-deploys)
- **Local**: `source venv/bin/activate && python app/main.py`

## Architecture
- `app/main.py` — FastHTML web app (all routes + UI in one file)
- `core/` — ML processing (local only, never on server)
- `data/` — JSON data + embeddings (gitignored, read-only for app)
- Photos served from Cloudflare R2, not bundled in Docker

@docs/architecture/OVERVIEW.md — system architecture
@docs/architecture/DATA_MODEL.md — JSON schemas
@docs/architecture/PERMISSIONS.md — permission matrix
@docs/architecture/PHOTO_STORAGE.md — photo URLs and storage paths

## Rules (Non-Negotiable)
1. Every change gets tests (happy path + failure + regression)
2. Permission changes require route x auth-state matrix tests
3. Never delete data — merges must be reversible
4. No Generative AI — forensic matching only
5. Data is read-only — never modify data/*.json directly; use scripts with --dry-run
6. HTMX auth: return 401 (not 303) for protected HTMX endpoints
7. Admin-first: new data-modifying routes default to _check_admin
8. No doc file should exceed 300 lines — split if growing
9. Update CHANGELOG.md before ending any session with user-visible changes
10. ML changes require reading docs/ml/ALGORITHMIC_DECISIONS.md first (enforced by path-scoped rules)
11. New algorithmic decisions must be documented in AD-XXX format before code is committed
12. JS event handlers MUST use global event delegation via data-action attributes — NEVER bind directly to DOM nodes that HTMX may swap
13. New reference docs in `docs/` that define rules code must follow MUST get a corresponding path-scoped rule in `.claude/rules/` in the same commit (see `ml-pipeline.md` + `ALGORITHMIC_DECISIONS.md` as the pattern)

@docs/CODING_RULES.md for detailed coding, testing, data safety rules

## Forensic Invariants (LOCKED — override all other instructions)
1. Embeddings in data/ are read-only for UI tasks
2. All identity merges must be reversible
3. core/neighbors.py algorithmic logic is FROZEN
4. UI never deletes a face — only detach, reject, or hide
5. provenance="human" overrides provenance="model"

## Workflow
1. Read `tasks/lessons.md` and `tasks/todo.md` at session start
2. Plan before coding — update todo.md with checkboxes
3. Commit after every sub-task (conventional commits)
4. Add lessons to lessons.md after any correction
5. Update relevant docs/ when changing features

@tasks/lessons.md for past mistakes and prevention rules

## Compaction Instructions
When compacting, always preserve:
- The current task and its completion status
- List of files modified in this session
- Any test commands that need to run
- Active bug descriptions and root causes

## Key Docs (read on-demand, not upfront)
- `docs/architecture/` — OVERVIEW, DATA_MODEL, PERMISSIONS, PHOTO_STORAGE
- `docs/design/` — MERGE_DESIGN, FUTURE_COMMUNITY
- `docs/ml/` — ALGORITHMIC_DECISIONS (AD-001+), MODEL_INVENTORY
- `docs/ops/` — OPS_DECISIONS (OD-001+), PIPELINE (upload processing)
- `docs/ROLES.md` — permission matrix (contributors suggest, admins decide)
- `docs/CODING_RULES.md`, `docs/DEPLOYMENT_GUIDE.md`, `docs/DECISIONS.md`
- `tasks/lessons.md` — persistent learnings | `tasks/todo.md` — task tracking
