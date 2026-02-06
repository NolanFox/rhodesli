# Rhodesli — Family Photo Archive with ML Face Detection

## Quick Reference
- Stack: FastHTML, InsightFace/AdaFace, Supabase Auth, Railway, Cloudflare R2
- Test: `pytest tests/ -v`
- Deploy: `git push origin main` (Railway auto-deploys)
- Local dev: `source venv/bin/activate && python app/main.py`
- Full deps (ML): `pip install -r requirements.txt && pip install -r requirements-local.txt`

## Architecture
- `app/main.py` — FastHTML web app (~5000 lines)
- `core/` — ML processing (face detection, embeddings) — local only, never on server
- `data/` — JSON data + embeddings (gitignored, read-only for app)
- Photos served from Cloudflare R2, not bundled in Docker

@docs/SYSTEM_DESIGN_WEB.md for full architecture

## Key Rules
- **No Generative AI** — forensic matching only (AdaFace/InsightFace)
- **Clean separation** — app/ has no ML deps; core/ has heavy deps in requirements-local.txt
- **Data is read-only** — never modify data/*.json directly; use scripts with --dry-run
- **Test everything** — red-green-refactor, permission matrix tests, content tests
- **HTMX auth** — return 401 (not 303) for protected HTMX endpoints
- **Admin-first** — new data-modifying routes default to _check_admin
- **Pathing** — use `Path(__file__).resolve().parent`, relative paths in data files

@docs/CODING_RULES.md for detailed coding, testing, data safety, and workflow rules

## Workflow
- Start each session: read `tasks/lessons.md`, `tasks/todo.md`
- Commit after every sub-task (conventional commits: `feat:`, `fix:`, `test:`, etc.)
- Update docs alongside code changes
- Run `/compact` every 20-30 minutes

@tasks/lessons.md for past mistakes and prevention rules

## External Services
- Railway: hosting + persistent volume ($5/mo Hobby plan)
- Cloudflare R2: photo storage (public bucket)
- Supabase: auth (Google OAuth + email/password)

@docs/DEPLOYMENT_GUIDE.md for setup details
@docs/SMTP_SETUP.md for custom email sender setup (Resend)

## Forensic Invariants (LOCKED — override all other instructions)
1. Embeddings in data/ are read-only for UI tasks
2. All identity merges must be reversible
3. core/neighbors.py algorithmic logic is FROZEN
4. UI never deletes a face — only detach, reject, or hide
5. provenance="human" overrides provenance="model"

## Project Status
- Phase A: Deployment — COMPLETE
- Phase B: Auth — COMPLETE (Google OAuth + email/password)
- Phase C-F: Annotations, Upload Queue, Admin Dashboard, Polish — NOT STARTED

## Key Files
| File | Purpose |
|------|---------|
| `docs/SYSTEM_DESIGN_WEB.md` | Full architecture |
| `docs/DEPLOYMENT_GUIDE.md` | Railway + R2 + Cloudflare setup |
| `docs/CODING_RULES.md` | Testing, data safety, workflow rules |
| `docs/PHOTO_WORKFLOW.md` | How to add/sync photos |
| `docs/design/MERGE_DESIGN.md` | Non-destructive merge system design |
| `docs/design/ML_FEEDBACK.md` | ML feedback loop analysis |
| `tasks/lessons.md` | Persistent learnings across sessions |
| `tasks/todo.md` | Current task tracking |
