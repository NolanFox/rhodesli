# Rhodesli — Antigravity Agent Rules

> Auto-generated from CLAUDE.md. Do not edit directly.
> Run `scripts/sync-harness.sh` to regenerate.

See `docs/AGENT_HARNESS.md` for the full tool-agnostic development rules.

---

## Project Summary

Rhodesli is a heritage photo archive for the Jewish Community of Rhodes.
FastHTML + HTMX | Supabase/Postgres | Cloudflare R2 | Railway | InsightFace + Gemini.

- **274+ photos**, **775+ identities**, **55 confirmed**
- **~3595 tests** across two suites
- Live: https://rhodesli.nolanandrewfox.com
- Deploy: `git push origin main`

## Setup

```bash
./scripts/setup-worktree.sh
# Or manually:
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Key Rules

1. **Postgres is source of truth** for all structured data
2. **Gatekeeper pattern**: ML proposals -> admin review -> confirmed
3. **Two test suites**: `tests/` (app) + `rhodesli_ml/tests/` (ML) — both must pass
4. **Conventional commits**: `[antigravity] type(scope): description`
5. **Decision tracking**: Update AD/DD/HD/OD logs when changing ML/design/harness/ops
6. **No doc > 300 lines**
7. **Never modify data/ files directly** — use canonical save functions
8. **Admin-only** for all data-modifying features

## Testing

```bash
source venv/bin/activate
pytest tests/ -x -q          # ~2545+ app tests
pytest rhodesli_ml/tests/ -x -q  # ~306+ ML tests
```

Both must pass before every commit. Use `tmp_path` fixtures, never touch `data/` directly.

## Key Files

| File | Purpose |
|------|---------|
| `app/main.py` | FastHTML web app (routes, UI, ~6000 lines) |
| `app/auth.py` | Auth integration, permissions |
| `core/storage.py` | Photo/crop URL generation |
| `rhodesli_ml/` | ML package |

## Architecture Invariants

- Embeddings read-only for UI | Merges reversible | `neighbors.py` FROZEN
- UI never deletes a face | `provenance="human"` > `provenance="model"`
- Web requests NEVER run heavy ML (AD-110)
- User data MUST be in Supabase (AD-135)

## Data Safety

- Never touch `data/` files directly
- Scripts default to `--dry-run`, require `--execute`
- Production-origin data must NOT be in deploy sync lists

## References

- Full rules: `docs/AGENT_HARNESS.md`
- ML decisions: `docs/ml/ALGORITHMIC_DECISIONS.md`
- Coding rules: `docs/CODING_RULES.md`
- Lessons: `tasks/lessons.md`
