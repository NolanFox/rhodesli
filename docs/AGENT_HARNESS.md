# Rhodesli — Tool-Agnostic Development Rules

Auto-generated canonical reference for all AI coding tools.
Source of truth: `CLAUDE.md`. See `docs/HARNESS_DECISIONS.md` HD-019.

---

## Project Identity

Rhodesli is a heritage photo archive for the Jewish Community of Rhodes.
ML-powered face detection identifies people across 274+ historical photos.
Live: https://rhodesli.nolanandrewfox.com

## Tech Stack

| Component | Technology |
|-----------|------------|
| Framework | FastHTML (Python) — inline HTML, no templates |
| Styling | Tailwind CSS (CDN) + HTMX + Hyperscript |
| Database | Supabase/Postgres (source of truth for structured data) |
| Auth | Supabase Auth (Google OAuth + email/password) |
| Photo Storage | Cloudflare R2 (public bucket) |
| ML | InsightFace (face detection) + Gemini (photo analysis) |
| Hosting | Railway (Docker + persistent volume) |
| Deploy | `git push origin main` triggers Railway auto-deploy |

## Key File Paths

| File | Purpose |
|------|---------|
| `app/main.py` | FastHTML web app (~6000 lines, routes + UI) |
| `app/auth.py` | Supabase auth, User model, permission helpers |
| `core/storage.py` | Photo/crop URL generation (local vs R2) |
| `core/photo_registry.py` | PhotoRegistry class (photo_index.json CRUD) |
| `data/identities.json` | Identity metadata, face assignments, states |
| `data/photo_index.json` | Photo metadata, face-to-photo mapping |
| `data/embeddings.npy` | Face embeddings (512-dim, read-only for UI) |
| `rhodesli_ml/` | ML package (date estimation, training, analysis) |

## Testing

Two test suites, both MUST pass before any commit:

```bash
source venv/bin/activate
pytest tests/ -x -q          # ~2545+ app tests
pytest rhodesli_ml/tests/ -x -q  # ~306+ ML tests
```

- MUST activate venv first (system Python lacks fasthtml/torch)
- Never reduce test count below previous session's count
- Every change gets tests: happy path + failure mode + regression case
- Test isolation: use `tmp_path` fixtures, never touch `data/` directly

## Commit Discipline

- Conventional commits: `feat:`, `fix:`, `test:`, `refactor:`, `docs:`, `chore:`
- Multi-tool attribution: `[tool-name] type(scope): description`
  - `[claude] feat(ml): add similarity calibration`
  - `[codex] fix(upload): handle timeout`
  - `[cursor] refactor(auth): simplify permission check`
- Run BOTH test suites before every commit
- Commit after every sub-task (small, atomic commits)

## Architecture Invariants

1. **Postgres is source of truth** for all structured data (not JSON files)
2. **Gatekeeper pattern**: ML outputs are proposals, admin reviews, then confirmed
3. **Confirmed data = ground truth** anchors for training
4. **Embeddings read-only** for UI; merges reversible; `neighbors.py` FROZEN
5. **UI never deletes a face**; `provenance="human"` > `provenance="model"`
6. **Web requests NEVER run heavy ML** (AD-110 Serving Path Contract)
7. **Admin-only** for all data-modifying features until moderation exists

## Decision Tracking

When changing code in these areas, you MUST update the corresponding log:

| Area | File | Format |
|------|------|--------|
| ML / algorithms | `docs/ml/ALGORITHMIC_DECISIONS.md` | AD-NNN |
| UX / design | `docs/DESIGN_DECISIONS.md` | DD-NNN |
| Harness / workflow | `docs/HARNESS_DECISIONS.md` | HD-NNN |
| Ops / deploy | `docs/ops/OPS_DECISIONS.md` | OD-NNN |

Each entry must include: what was chosen, alternatives rejected, why, session number.

## ML Pipeline Rules

- ML outputs are proposals, not facts
- Admin confirms/rejects proposals (Gatekeeper)
- Confirmed data feeds back as ground truth anchors
- Cost per API call must be logged
- Model version must be logged per API call
- Read `ALGORITHMIC_DECISIONS.md` before modifying any ML code

## Data Safety

- Never modify `data/*.json` or `data/*.npy` directly
- Route handlers must use canonical save functions (`save_registry()`, etc.)
- Scripts must default to `--dry-run`, require `--execute` to change data
- User-entered data MUST be in Supabase (AD-135)
- Never overwrite user data with ML predictions
- Production-origin data (annotations.json) must NOT be in deploy sync lists

## Documentation Limits

- No single doc file > 300 lines
- CLAUDE.md < 80 lines
- Split monoliths early

## Deployment

- Deploy: `git push origin main` (Railway auto-deploys)
- Dockerfile must COPY every package the web app imports at runtime
- Essential data files must be in BOTH git tracking AND `REQUIRED_DATA_FILES`
- Production smoke test: `python scripts/production_smoke_test.py`

## Files You Must NOT Edit Without Coordination

- `CLAUDE.md` — main agent only, adapters reference it
- `ROADMAP.md`, `CHANGELOG.md`, `SESSION_LOG.md` — main agent only
- `data/embeddings.npy` — modified only during face detection pipeline
- `core/neighbors.py` — FROZEN, do not modify
