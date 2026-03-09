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

## OD-006: Railway MCP Server for Claude Code Integration
- **Date**: 2026-02-20
- **Session**: 54G
- **Context**: CLAUDE.md rules told Claude Code to use `railway logs` for deploy
  diagnosis, but Claude Code repeatedly ignored this across sessions 54A-54F. The
  rule was unenforceable because it relied on instruction-following rather than
  mechanical enforcement.
- **Decision**: Install Railway MCP Server (`claude mcp add railway-mcp-server --
  npx -y @railway/mcp-server`) to give Claude Code native API access to Railway.
  This makes Railway tools (deploy status, logs, health checks) available as
  first-class MCP tools rather than relying on Claude Code to remember to run
  CLI commands.
- **Why MCP over rules alone**: MCP integrates as a first-class tool that appears
  in the tool list. Rules in CLAUDE.md can be forgotten or deprioritized. MCP tools
  are mechanically available. Railway's own documentation recommends this integration.
- **Token efficiency**: As of Jan 2026, Claude Code auto-defers MCP tools via Tool
  Search. Railway tools load on-demand, not at startup.
- **Status (54H verification)**: NOT LOADED. The `claude mcp add` from 54G did NOT
  persist — `~/.claude.json` mcpServers is empty, `.mcp.json` only has Playwright.
  npm cache has ownership issue (`/Users/nolanfox/.npm` needs `sudo chown -R 501:20`).
  No `.claude/hooks/` directory exists either, so the post-deploy hook fallback is
  also not functional. **Current enforcement: `railway logs` CLI command only.**
  To fix: (1) `sudo chown -R 501:20 /Users/nolanfox/.npm`, (2) `claude mcp add
  railway-mcp-server -- npx -y @railway/mcp-server`, (3) restart Claude Code session.
- **Alternatives rejected**:
  - (1) Just adding more CLAUDE.md rules — already proven ineffective across 4+
    sessions (54A, 54B, 54D, 54F all failed to use `railway logs`)
  - (2) Railway Skills packages (less maintained than official MCP server)
  - (3) Manual log checking (defeats automation purpose)
- **Configuration**: Stored in `~/.claude.json` under project-scoped mcpServers.
  Available after Claude Code session restart.
- **Verification**: `claude mcp list` should show `railway-mcp-server`. If not
  present, re-run: `claude mcp add railway-mcp-server -- npx -y @railway/mcp-server`
- **Breadcrumbs**: Session 54F (didn't use railway logs despite rule),
  HARNESS_DECISIONS.md HD-012, CLAUDE.md deployment section

## OD-008: Dev vs Production Environment Separation
- **Date**: 2026-03-09
- **Session**: 95b
- **Context**: Sentry error fired from local dev machine (Nolans-MBP-2) for `_load_corrections_log`
  circular import (PYTHON-ASGI-7). Dev errors pollute production error stream — makes it hard to
  distinguish real user-facing issues from development noise.
- **Current state**: Sentry initializes whenever `SENTRY_DSN` is set (including `.env` on dev laptop).
  Environment tag defaults to `"production"` unless `SENTRY_ENVIRONMENT` is explicitly set.
- **Immediate fix**: Add `SENTRY_ENVIRONMENT=development` to local `.env`. This tags local errors
  as "development" in Sentry so they can be filtered out. Zero code change needed.
- **Medium-term**: Consider NOT initializing Sentry at all in local dev — only when `RAILWAY_ENVIRONMENT`
  is set. This prevents dev noise entirely but loses visibility into local crashes.
- **Long-term**: Full dev/staging/prod environment split with separate Railway projects, separate
  Sentry DSNs, and separate Supabase projects. This is standard practice and would naturally solve
  the problem. See BACKLOG.md for ENV-001.
- **Breadcrumbs**: Session 95b Sentry error discussion, BACKLOG.md ENV-001

## OD-009: Observability Data Retention & Long-Term Storage
- **Date**: 2026-03-09
- **Session**: 95b
- **Context**: Nolan asked whether Sentry/PostHog preserve data in perpetuity on free tiers, and
  whether we need to archive to our own database for long-term storage.
- **Current retention limits**:
  - **Sentry (Developer plan)**: 90-day event retention. Issues persist but individual events age out.
  - **PostHog (free tier)**: 1-year retention for events. Generous for current scale.
- **Decision**: No immediate action needed — 90 days of Sentry + 1 year of PostHog covers our
  current needs. If we need longer retention:
  - Option A: Export via API (Sentry REST API, PostHog batch export) to Supabase table
  - Option B: Upgrade Sentry/PostHog tiers (costs money)
  - Option C: Log critical errors to `gemini_api_calls`-style Supabase table (already have the pattern)
- **Recommendation**: When error patterns matter for ML model improvement or recurring bug tracking,
  add a lightweight `error_log` Supabase table. For now, Sentry's 90-day window + issue persistence
  is sufficient — we rarely need to analyze errors older than 90 days.
- **Breadcrumbs**: Session 95b observability discussion, BACKLOG.md OBS-001
