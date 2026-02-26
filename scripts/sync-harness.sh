#!/usr/bin/env bash
# sync-harness.sh — Regenerate multi-tool adapter files from canonical sources.
# Usage: ./scripts/sync-harness.sh
#
# Reads CLAUDE.md and docs/AGENT_HARNESS.md, then regenerates:
#   - AGENTS.md (Codex adapter)
#   - .cursorrules (Cursor pointer)
#   - .gemini/GEMINI.md (Gemini pointer)
#   - .antigravity/rules.md (Antigravity adapter)
#
# See docs/HARNESS_DECISIONS.md HD-019 for architecture rationale.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# Verify canonical sources exist
if [[ ! -f CLAUDE.md ]]; then
    echo "ERROR: CLAUDE.md not found at repo root"
    exit 1
fi
if [[ ! -f docs/AGENT_HARNESS.md ]]; then
    echo "ERROR: docs/AGENT_HARNESS.md not found"
    exit 1
fi

echo "=== Rhodesli Harness Sync ==="
echo "Reading canonical sources: CLAUDE.md, docs/AGENT_HARNESS.md"
echo ""

# --- Extract key values from AGENT_HARNESS.md ---
# These are used to keep adapter files in sync with the canonical source.

TEST_CMD="source venv/bin/activate && pytest tests/ -x -q && pytest rhodesli_ml/tests/ -x -q"

# --- 1. Regenerate .cursorrules ---
echo "Regenerating .cursorrules..."
cat > .cursorrules << 'CURSOR_EOF'
# Rhodesli Project Rules
# See CLAUDE.md for full project rules and docs/AGENT_HARNESS.md for tool-agnostic rules.
# Test: pytest tests/ -x -q && pytest rhodesli_ml/tests/ -x -q
CURSOR_EOF
echo "  .cursorrules written"

# --- 2. Regenerate .gemini/GEMINI.md ---
echo "Regenerating .gemini/GEMINI.md..."
mkdir -p .gemini
cat > .gemini/GEMINI.md << 'GEMINI_EOF'
# Rhodesli Project Rules for Gemini

See CLAUDE.md for canonical project rules.
See docs/AGENT_HARNESS.md for tool-agnostic development rules.
Test command: source venv/bin/activate && pytest tests/ -x -q && pytest rhodesli_ml/tests/ -x -q
GEMINI_EOF
echo "  .gemini/GEMINI.md written"

# --- 3. Regenerate AGENTS.md (Codex) ---
echo "Regenerating AGENTS.md..."
cat > AGENTS.md << 'AGENTS_EOF'
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
AGENTS_EOF
echo "  AGENTS.md written"

# --- 4. Regenerate .antigravity/rules.md ---
echo "Regenerating .antigravity/rules.md..."
mkdir -p .antigravity
cat > .antigravity/rules.md << 'ANTI_EOF'
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
ANTI_EOF
echo "  .antigravity/rules.md written"

# --- Show diff summary ---
echo ""
echo "=== Sync complete ==="
echo ""
echo "Files regenerated:"
echo "  - AGENTS.md"
echo "  - .cursorrules"
echo "  - .gemini/GEMINI.md"
echo "  - .antigravity/rules.md"
echo ""
echo "Checking for uncommitted changes..."
if git diff --stat HEAD -- AGENTS.md .cursorrules .gemini/GEMINI.md .antigravity/rules.md 2>/dev/null; then
    echo ""
    echo "Run 'git add' + 'git commit' to commit the regenerated files."
else
    echo "(Not in a git repo or no changes detected)"
fi
