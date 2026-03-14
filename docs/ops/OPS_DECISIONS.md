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

## OD-010: Railway Region Deprecation Deploy Fix
- **Date**: 2026-03-10
- **Session**: 96e-cont5
- **Context**: Railway deprecated `us-west1` region. After the deprecation, all GitHub-triggered
  deploys silently switched from DOCKERFILE builder to RAILPACK, ignoring `railway.toml`. Deploys
  stuck in QUEUED indefinitely. The banner said "automatically modified to ignore deprecated regions"
  but the actual effect was much broader — the entire build config was lost.
- **Root cause**: Railway's GitHub integration stopped reading `railway.toml` during the region
  migration. The service-level settings (which default to RAILPACK/auto-detect) took over. The CLI
  (`railway deploy`) still reads `railway.toml` locally and sends the correct config.
- **Evidence**: Deploy metadata comparison:
  - GitHub deploy: `builder: "RAILPACK"`, no `configFile`, no `dockerfilePath`, no `healthcheckPath`
  - CLI deploy: `builder: "DOCKERFILE"`, `configFile: "railway.toml"`, `dockerfilePath: "Dockerfile"`, `healthcheckPath: "/health"`
- **Fix applied**:
  1. Immediate: `railway deploy` from CLI to get site running
  2. Region updated: us-west1 → us-west2 in Railway Settings
  3. Dashboard builder setting did not persist during the incident — setting Dockerfile in
     Settings → Build reverted to Railpack on every deploy. This may be caused by Railway's
     "Deployment slowness" incident (status.railway.com, 2026-03-10 11:19 AM) rather than a
     permanent bug. Retry after incident resolves.
- **Current deploy method**: `railway deploy` from project root works reliably during incidents.
  GitHub auto-deploy via `git push` may break during Railway infrastructure incidents (deploys
  stuck in QUEUED, builder reverting to Railpack). Retry GitHub deploys after incident resolves.
  The CLI reads `railway.toml` locally and sends correct config every time.
- **Diagnosis checklist** (if deploys break again):
  1. `mcp__railway-mcp-server__list-deployments` with `json: true`
  2. Check `builder` field — should be `"DOCKERFILE"`, if `"RAILPACK"` → broken
  3. Check for `configFile: "railway.toml"` — present = good, absent = GitHub integration broken
  4. Workaround: `railway deploy` from project root
- **Breadcrumbs**: Lesson 117 in tasks/lessons/deployment-lessons.md

## OD-011: Supabase Egress Budget — TTL Tuning + Monitoring Thresholds
- **Date**: 2026-03-14
- **Session**: 100e (ad-hoc)
- **Context**: Supabase free plan (5GB egress/month) exceeded at 5.5GB. Root cause: 30s TTL on
  registry cache reloads 380KB per cycle. Combined with 60s community cache and heavy dev sessions
  (Sessions 96-100), egress spiked. Supabase granted one-time grace period until April 13, 2026.
- **Decision**: Bump registry TTL from 30s to 120s, community IDs TTL from 60s to 120s. This
  reduces egress from these caches by 4x and 2x respectively. Other caches (face alignment,
  GEDCOM, community lookup) already at 300s — left unchanged.
- **Tradeoffs**:
  - Admin changes now take up to 2 minutes to propagate to other browser sessions (was 30s)
  - Single-admin app — admin sees their own changes immediately (local cache invalidated on write)
  - Community users are read-only browsers — 2-minute staleness is invisible
  - Under constant traffic, 120s TTL = ~7.8 GB/month for identities alone — still over free tier
    but normal traffic is bursty, not constant. Dev sessions are the primary driver.
- **Egress budget analysis** (per full table fetch):
  | Table | Size | TTL | Fetches/hr | GB/month (24/7) |
  |-------|------|-----|------------|-----------------|
  | identities | 380 KB | 120s (was 30s) | 30 | 7.8 |
  | community_ids | ~50 KB | 120s (was 60s) | 30 | 1.1 |
  | photos | 436 KB | 120s | 30 | 9.0 |
  | photo_faces | 293 KB | 120s | 30 | 6.0 |
  | face_alignment | varies | 300s | 12 | ~1.0 |
  | gemini_api_calls | 1.49 MB | on-demand | varies | varies |
  Note: These are WORST CASE (constant traffic). Real traffic is bursty — dev sessions only.
- **Monitoring thresholds** (revisit this decision when ANY of these trigger):
  1. **Multi-admin**: When more than 1 admin user exists, 120s staleness becomes visible. Revisit TTL
     or implement write-through cache invalidation.
  2. **Table growth**: When identities table exceeds 1MB per fetch (~9000 rows), consider incremental
     sync (fetch only rows with updated_at > last_fetch) or ETag-based conditional requests.
  3. **Concurrent users**: When sustained concurrent users exceed 10, constant-traffic egress model
     applies. At 10 users x 120s TTL x ~1.1MB total per cycle = ~24 GB/month -> Pro plan required.
  4. **gemini_api_calls growth**: At 1.49MB and growing, this table will become the largest. If the
     estimate tool gets traffic, add TTL caching or paginated/filtered fetches.
  5. **Supabase egress alert**: If Supabase sends another quota warning, upgrade to Pro ($25/mo,
     250GB egress) — the ROI of further optimization drops below $25/mo of engineering time.
- **Future optimizations** (BACKLOG items):
  - EGRESS-001: ETag/conditional fetch — only download when data actually changed
  - EGRESS-002: Incremental sync — fetch only rows newer than last fetch timestamp
  - EGRESS-003: Selective column fetch — don't load full rows when only IDs needed
- **Alternatives rejected**:
  - 300s TTL: Too stale for admin UX when managing identities
  - ETag caching: Supabase REST API doesn't natively support ETags on table queries; would need
    custom RPC function. Over-engineered for current traffic.
  - Pro plan upgrade: Would solve it but doesn't fix the inefficiency. Worth doing when concurrent
    users reach 10+.
- **Breadcrumbs**: Lesson 139 (tasks/lessons/deployment-lessons.md), BACKLOG.md EGRESS-001/002/003,
  `.claude/rules/egress-budget.md`

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
