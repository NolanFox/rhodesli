# Infrastructure & Operations Decisions

This document records deployment, infrastructure, and operational decisions for Rhodesli.
**Claude Code: Read this file before modifying Dockerfile, railway.toml, deployment scripts, or storage code.**

## OD-001: Hybrid Deployment Model
- **Date**: 2026-02-06
- **Context**: Railway supports two deploy methods: `git push` (GitHub webhook) and `railway up` (CLI).
- **Decision**:
  - `git push` = CODE changes only (fast, lightweight, no data files)
  - `railway up` = DATA SEEDING only (uploads local photos/embeddings/JSON to build context)
- **Why**: GitHub repos cannot host GBs of photos. The CLI bypasses git to upload data directly.
- **Risk**: Running `git push` after a fresh volume creation results in an EMPTY site (0 photos, 0 identities) because git doesn't contain data files.
- **Affects**: All deployment workflows, Dockerfile, railway.toml.

## OD-002: The Ignore File Split (.gitignore vs .dockerignore)
- **Date**: 2026-02-06
- **Context**: How to keep the git repo light while ensuring deployments have all data?
- **Decision**:
  - `data/` and photo directories ARE in `.gitignore` (keeps repo fast)
  - `data/` and photo directories MUST NOT be in `.dockerignore` (allows CLI upload to include them)
- **Why**: `.dockerignore` filters files BEFORE the build context is sent. If data is dockerignored, `railway up` silently strips it, causing the "0 Photos" bug.
- **Catastrophic if violated**: Site deploys successfully but shows no photos, no identities — looks completely broken with no error messages.

## OD-003: R2 File Resolution via Embeddings
- **Date**: 2026-02-06
- **Context**: How does the app know which photos exist in R2 without calling the R2 API?
- **Decision**: Use `data/embeddings.npy` as the local file index. If an entry exists in embeddings, the app assumes the corresponding file exists in R2 and generates the URL deterministically.
- **Why**: R2 `list_objects` API is slow and costs per-request. Embeddings already contain all face metadata including filenames.
- **Constraint**: `embeddings.npy` MUST be deployed to production. It is infrastructure, not just ML data.
- **Affects**: `core/storage.py` (URL generation), deployment pipeline.

## OD-004: R2 Direct Serving (No Python Proxy)
- **Date**: 2026-02-06
- **Context**: Should images be served through a Python route or directly from R2?
- **Decision**: ALL images served directly from R2 public URL. No Python proxy routes.
- **Why**: Python proxy would bottleneck on Railway's single dyno. Direct R2 serving is CDN-fast and costs nothing for egress.
- **Rule**: NEVER create a Python route that reads and serves image bytes. Always generate the public URL string and let the browser fetch directly.
- **Affects**: All image rendering in templates, `core/storage.py`.

## OD-005: Nuclear Reset Protocol (Zombie Volume Fix)
- **Date**: 2026-02-06
- **Context**: Railway volumes can get stuck with a `.initialized` flag but empty data.
- **Decision**: Documented reset procedure:
  1. Set Railway Custom Start Command: `rm -f /app/storage/.initialized && python scripts/init_railway_volume.py && python app/main.py`
  2. Deploy
  3. Clear the custom command after success
- **Why**: The init script checks for `.initialized` and skips setup if it exists, even if data is actually empty.
- **Affects**: Railway deployment, `scripts/init_railway_volume.py`.
