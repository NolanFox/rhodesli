# Rhodesli — Codex Agent Rules

> Auto-generated from CLAUDE.md. Do not edit directly.
> Run `scripts/sync-harness.sh` to regenerate.

See `docs/AGENT_HARNESS.md` for the full tool-agnostic development rules.

---

## Quick Start

```bash
# Setup (run once per environment)
./scripts/setup-worktree.sh

# Or manually:
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Test (run before every commit)
source venv/bin/activate
pytest tests/ -x -q && pytest rhodesli_ml/tests/ -x -q
```

## Project Summary

Rhodesli is a heritage photo archive for the Jewish Community of Rhodes.
FastHTML + HTMX | Supabase/Postgres | Cloudflare R2 | Railway | InsightFace + Gemini.

- **274+ photos**, **775+ identities**, **55 confirmed**
- **~3595 tests** across two suites
- Live: https://rhodesli.nolanandrewfox.com
- Deploy: `git push origin main`

## Key Rules

1. **Postgres is source of truth** for all structured data
2. **Gatekeeper pattern**: ML proposals -> admin review -> confirmed
3. **Two test suites**: `tests/` (app) + `rhodesli_ml/tests/` (ML) — both must pass
4. **Conventional commits**: `[codex] type(scope): description`
5. **Decision tracking**: Update AD/DD/HD/OD logs when changing ML/design/harness/ops
6. **No doc > 300 lines**
7. **Never modify data/ files directly** — use canonical save functions
8. **Admin-only** for all data-modifying features

## Key Files

| File | Purpose |
|------|---------|
| `app/main.py` | FastHTML web app (routes, UI, ~6000 lines) |
| `app/auth.py` | Auth integration, permissions |
| `core/storage.py` | Photo/crop URL generation |
| `data/identities.json` | Identity metadata |
| `data/photo_index.json` | Photo metadata |
| `rhodesli_ml/` | ML package |

## Architecture Invariants

- Embeddings read-only for UI | Merges reversible | `neighbors.py` FROZEN
- UI never deletes a face | `provenance="human"` > `provenance="model"`
- Web requests NEVER run heavy ML (AD-110)
- User data MUST be in Supabase (AD-135)

## Codex-Specific Notes

- Codex runs in a sandboxed environment — network access may be restricted
- Use `./scripts/setup-worktree.sh` for dependency setup
- If venv is missing, create with: `python -m venv venv && source venv/bin/activate && pip install -r requirements.txt`
- Pre-commit: always run both test suites
- No session protocol (/clear, /compact) — those are Claude Code specific
- No hook enforcement — follow commit discipline manually

## Testing Notes

```bash
# Activate venv first (system Python lacks fasthtml/torch)
source venv/bin/activate

# App tests (~2545+)
pytest tests/ -x -q

# ML tests (~306+)
pytest rhodesli_ml/tests/ -x -q

# Both (required before commit)
pytest tests/ -x -q && pytest rhodesli_ml/tests/ -x -q
```

## Data Safety

- Never touch `data/` files directly in tests — use `tmp_path` fixtures
- Scripts default to `--dry-run`, require `--execute` to change data
- Production-origin data (annotations.json) must NOT be in deploy sync lists
- Always sync from production before modifying data pipelines

## References

- Full rules: `docs/AGENT_HARNESS.md`
- ML decisions: `docs/ml/ALGORITHMIC_DECISIONS.md`
- UX decisions: `docs/DESIGN_DECISIONS.md`
- Harness decisions: `docs/HARNESS_DECISIONS.md`
- Ops decisions: `docs/ops/OPS_DECISIONS.md`
- Coding rules: `docs/CODING_RULES.md`
- Lessons: `tasks/lessons.md`
