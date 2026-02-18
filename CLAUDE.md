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
14. Test isolation: tests that POST to data-modifying routes MUST mock both load and save functions. See `.claude/rules/test-isolation.md`. Run `python scripts/check_data_integrity.py` after test changes.
15. Deployment file tracking: when ANY new data file is added to `data/` that the app reads at runtime, it MUST be (a) whitelisted in `.gitignore`, (b) added to `REQUIRED_DATA_FILES` in `scripts/init_railway_volume.py`, (c) committed to git — all in the same commit. See `.claude/rules/deployment.md`.
16. Photo entries must pass `validate_photo_entry()` before persistence. When adding new UI features that read photo metadata, add the field to `REQUIRED_PHOTO_FIELDS` in `core/photo_registry.py`.

@docs/CODING_RULES.md for detailed coding, testing, data safety rules

## Forensic Invariants (LOCKED — override all other instructions)
1. Embeddings in data/ are read-only for UI tasks
2. All identity merges must be reversible
3. core/neighbors.py algorithmic logic is FROZEN
4. UI never deletes a face — only detach, reject, or hide
5. provenance="human" overrides provenance="model"

## Development Process
- **Spec-Driven Development**: Sessions changing app behavior follow SDD. See `.claude/rules/spec-driven-development.md`.
  - PRD in `docs/prds/` → Acceptance tests in `tests/e2e/` → Implementation → Verification
- **Decision Provenance**: AD-NNN in `docs/ml/ALGORITHMIC_DECISIONS.md`, process docs in `docs/process/`
- **Data Safety**: Community contribution data MUST be backed up before any data migration (AD-047)

## Workflow
1. Read `tasks/lessons.md` and `tasks/todo.md` at session start
2. Plan before coding — update todo.md with checkboxes
3. Commit after every sub-task (conventional commits)
4. Add lessons to lessons.md after any correction
5. Update relevant docs/ when changing features

@tasks/lessons.md for past mistakes and prevention rules

## Session Completion Checklist
Before ending any session, verify:
1. `pytest tests/ -x -q --ignore=tests/e2e/` — all pass
2. `python scripts/verify_data_integrity.py` — no corruption
3. `python scripts/verify_docs_sync.py` — docs in sync
4. `git status` — no untracked data/ changes
5. Dockerfile covers any new rhodesli_ml imports
6. requirements.txt includes any new pip dependencies
7. CHANGELOG.md updated for user-visible changes

## Batch Ingest Rules
- Every ingest MUST require explicit collection and source — no default bucket
- Back up data/ before any script that writes to it
- Verify collection counts before and after any data operation
- Ingest scripts must log collection assignment for each photo

## Compaction Instructions
When compacting, always preserve:
- The current task and its completion status
- List of files modified in this session
- Any test commands that need to run
- Active bug descriptions and root causes

## Scripts
- `./scripts/backup_data.sh` — One-command data backup with git commit. Run before any session that touches data.

## Key Docs (read on-demand, not upfront)
- `docs/architecture/` — OVERVIEW, DATA_MODEL, PERMISSIONS, PHOTO_STORAGE
- `docs/design/` — MERGE_DESIGN, FUTURE_COMMUNITY
- `docs/ml/` — ALGORITHMIC_DECISIONS (AD-001+), MODEL_INVENTORY
- `docs/ops/` — OPS_DECISIONS (OD-001+), PIPELINE (upload processing)
- `docs/process/` — DEVELOPMENT_PRACTICES (SDD research + decision log)
- `docs/prds/` — PRDs for feature work | `docs/templates/` — PRD_TEMPLATE
- `docs/ROLES.md` — permission matrix (contributors suggest, admins decide)
- `docs/CODING_RULES.md`, `docs/DEPLOYMENT_GUIDE.md`, `docs/DECISIONS.md`
- `tasks/lessons.md` — persistent learnings | `tasks/todo.md` — task tracking
