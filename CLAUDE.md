@ROADMAP.md

# Rhodesli — Heritage Photo Archive for the Jewish Community of Rhodes

## Stack
FastHTML + HTMX | Supabase/Postgres | Cloudflare R2 | Railway | InsightFace + Gemini

## Quick Reference
- **Admin**: NolanFox@gmail.com | **Live**: https://rhodesli.nolanandrewfox.com
- **Test**: `source venv/bin/activate && pytest tests/ -x -q` + `pytest rhodesli_ml/tests/ -x -q`
- **Deploy**: `git push origin main`

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
@tasks/lessons.md for past mistakes and prevention rules

## Key Docs (read on-demand)
- `docs/ml/ALGORITHMIC_DECISIONS.md` — All ML decisions (AD-NNN)
- `docs/ops/OPS_DECISIONS.md` — Ops decisions (OD-NNN)
- `docs/HARNESS_DECISIONS.md` — Workflow decisions (HD-NNN)
- `docs/prds/` — Product requirement docs
