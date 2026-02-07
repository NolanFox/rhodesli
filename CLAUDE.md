# Rhodesli — Jewish Heritage Photo Archive

## Quick Reference
- **Stack**: FastHTML, InsightFace/AdaFace, Supabase Auth, Railway, Cloudflare R2
- **Admin**: NolanFox@gmail.com (only admin)
- **Live**: https://rhodesli.nolanandrewfox.com
- **Test**: `pytest tests/ -v`
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
| File | Purpose |
|------|---------|
| `docs/architecture/OVERVIEW.md` | System architecture |
| `docs/architecture/DATA_MODEL.md` | JSON schemas |
| `docs/architecture/PERMISSIONS.md` | Permission matrix |
| `docs/architecture/PHOTO_STORAGE.md` | Photo URL and storage paths |
| `docs/CODING_RULES.md` | Testing, data safety, workflow rules |
| `docs/DEPLOYMENT_GUIDE.md` | Railway + R2 + Cloudflare setup |
| `docs/PHOTO_WORKFLOW.md` | How to add/sync photos |
| `docs/SMTP_SETUP.md` | Custom email sender setup (Resend) |
| `docs/design/MERGE_DESIGN.md` | Non-destructive merge system design |
| `docs/design/FUTURE_COMMUNITY.md` | Planned community features (not yet built) |
| `docs/ml/ALGORITHMIC_DECISIONS.md` | ML algorithmic decision log (AD-001+) |
| `docs/ml/MODEL_INVENTORY.md` | Current ML models and upgrade path |
| `docs/DECISIONS.md` | Finalized architectural decisions |
| `docs/ops/OPS_DECISIONS.md` | Deployment, Railway, R2 decisions |
| `tasks/lessons.md` | Persistent learnings across sessions |
| `tasks/todo.md` | Current task tracking |
