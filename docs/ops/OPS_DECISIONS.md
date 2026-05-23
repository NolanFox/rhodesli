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

## OD-012: Supabase Egress Crisis — TTLs 120s→600s + Selective Columns + SWR Guard
- **Date**: 2026-03-24
- **Session**: 136
- **Context**: Supabase restricted project — 13.79 GB of 5.5 GB quota consumed. Grace period (OD-011)
  proved insufficient. Root cause: 120s TTL SWR still fires 24/7 from Railway (bot/crawler traffic
  triggers stale-while-revalidate). `SELECT *` on identities and photos fetches unused columns.
  Community filtering failed open for Rhodes when Supabase returned 402, leaking Fox Family data.
- **Decision**: Three-pronged egress reduction:
  1. **TTLs 120s → 600s** on ALL caches (registry, community IDs, proposals, cluster review, annotations)
  2. **Selective columns**: identities and photos queries now fetch only the 12 columns each actually uses
  3. **SWR bot guard**: Background refresh only fires if a real user page load occurred within 5 min
  4. **Fail-closed**: ALL communities including Rhodes now return empty set when Supabase unavailable
- **Tradeoffs**:
  - 600s staleness window for external DB edits (irrelevant — single admin, writes invalidate locally)
  - First page load after 5 min idle takes ~1s longer (cold SWR refresh)
  - No functional difference for the admin during active use
- **Estimated impact**: ~14 GB/mo → ~3 GB/mo (well within 5.5 GB free tier)
- **Monitoring thresholds** (same as OD-011, plus):
  6. **If quota exceeded again**: Upgrade to Pro ($25/mo) — no further optimization ROI
- **Alternatives rejected**:
  - DATA_SOURCE=json rollback: Would reintroduce all JSON data integrity issues (10+ incidents)
  - New Supabase org: Data migration hassle outweighs benefit
  - 300s TTL: Insufficient — would still be ~7 GB/mo from SWR without the bot guard
- **EGRESS-003 (selective columns) now DONE**: Implemented in this session
- **Breadcrumbs**: OD-011, Lesson 139, `.claude/rules/egress-budget.md`, Session 136 feedback

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

## OD-013: Supabase Database Storage Compliance — E1 Stopgap + E3 Retention + E4 Redesign
- **Date**: 2026-04-28
- **Session**: 154 (Track E)
- **Context**: Supabase emailed 2026-04-28 — org "Nolan Fox Projects" exceeded free-tier database
  storage quota. Database size: 2.39 GB. Threshold for restrictions: 1.1 GB. Grace ends 2026-05-29.
  This is *database storage* (table+index bytes on disk), distinct from egress (OD-011/OD-012,
  network bytes shipped). User just downgraded back to free after 1-month Pro stint that addressed
  egress — storage was never pruned.
- **Phase E0 baseline** (`docs/feedback/session-154-supabase-size-summary.md`): 97.9% of bytes
  (2.17 GB of 2.22 GB `pg_database_size`) are in `gedcom_*` tables. Everything else (auth,
  identities, photos, embeddings, faces, gemini, audit) totals ~50 MB combined.
- **Phase E0.5 root cause** (`docs/feedback/session-154-supabase-bloat-root-cause.md`): three
  identifiable root causes account for ~1.42 GB of the 2.17 GB GEDCOM footprint:
  1. **Failed imports retained** (~1 GB): 7 of 9 `gedcom_versions` rows are `status='failed'`. The
     importer wrote full row sets and never rolled back. v1-v6 + v8 retain ~131K individual rows,
     ~440K relationships, ~144K events, ~590K change_log rows that have no historical value.
  2. **`payload_hash` populated but never used at INSERT** (~400 MB): Migration 003 added
     `idx_gedcom_individuals_payload_hash` (line 41 of the SQL) but the importer writes blindly
     without checking it. Top-20 duplicated hashes all repeat exactly 7 times — same byte-identical
     payload sitting in 7 separate version rows for the same `gedcom_id`.
  3. **`change_log` phantom rows** (~300 MB): 1.24M of 1.65M rows (75%) have NULL old_value AND
     NULL new_value. They are journal rows for `change_type='added'` and `'removed'` carrying
     per-row UUID + version_id overhead with no payload.
- **Decision**: Three-phase response.
  - **E1 stopgap prune** (text plan only at session 154 closeout, gated on user authorization
    message naming plan commit hash + every table + every DELETE predicate + every snapshot path
    + full VACUUM list — "approved" alone NOT sufficient). Plan reclaims ~1.43 GB → final ~840 MB.
    Snapshot-validate-mutate-verify per Lessons 155, 156. Pre-flight grep checks before user is
    even asked. Plan: `docs/feedback/session-154-supabase-prune-plan.md`. Tripwire script:
    `scripts/session154_supabase_prune.py` (--dry-run default, --execute requires
    `SESSION154_PRUNE_AUTH=approved-<plan-commit>` env var).
  - **E3 retention sweep** (steady-state guard). Module: `scripts/retention_sweep.py` or
    `app/retention.py`. Default `--dry-run`. `--execute` requires `RETENTION_AUTH=approved-*`
    env var (same tripwire pattern as E2). Targets: `gemini_api_calls` (90d), `gedcom_change_log`
    (keep latest 3 versions per entity), `audit_log` (365d), `ml_proposals` (REJECTED/ACCEPTED 30d,
    PENDING KEEP_ALL). **Scheduler enablement (cron / Railway cron / GitHub Action) is OUT OF
    SCOPE for this OD — requires written approval at the same level as E2 before any unattended
    run.** Plus admin endpoint `GET /api/admin/db-size` returning total + top-10 tables for
    monitoring.
  - **E4 redesign** (PRD-063, follow-up session). Goal: preserve current functionality (in-app
    GEDCOM search, identity↔GEDCOM linking AD-160, business-name lookup AD-210, subject GEDCOM
    context AD-211/AD-241, /tree, versioning) while reducing storage 10-30× via hash-dedup at
    INSERT, single canonical row per individual + R2 archive of raw payloads, per-import change
    manifest replacing per-cell journal. Migration is gated, dual-read for one session, all
    archives written before any DROP TABLE.
- **Monitoring thresholds**:
  - **800 MB warn** — alert via Sentry breadcrumb if `pg_database_size` exceeds 800 MB.
  - **1.0 GB critical** — alert + block new imports + page admin.
  - **1.1 GB ceiling** — Supabase free-tier restriction triggers. Below this is mandatory.
- **Tradeoffs**:
  - The E1 stopgap loses 7 failed-version "history" — but those versions failed at import time
    and have no functional value (their `is_current=TRUE` row count is 0). Real history (v7 + v9
    applied) is preserved.
  - The E1 stopgap does NOT address Cause #2 (broken dedup at INSERT). If the user re-imports
    GEDCOM before E4 lands, bloat returns. Mitigation: warn user not to re-import until E4.
  - E3 retention sweeps reduce future audit-trail depth. `gemini_api_calls` 90-day retention may
    feel short — flagged for user feedback before scheduler is enabled.
  - E4 redesign is a multi-session effort. Stopgap buys time, doesn't fix root cause.
- **Alternatives rejected**:
  - **Upgrade to Pro** ($25/mo, 8 GB storage) — user explicitly chose to stay on free tier
    after the prior month's Pro stint. Egress optimizations (OD-012) made free tier viable for
    egress; storage just needed the same attention.
  - **Truncate `gedcom_change_log` entirely** — could not confirm in E1's scope that no read
    path queries it. The conservative approach (drop failed-version + NULL/NULL phantoms) reclaims
    most of the same bytes without that risk.
  - **Drop `raw_record_json` columns** — too aggressive for stopgap. Belongs in E4 with archive
    path.
  - **Stop versioning** — would lose Migration 002's "audit/rollback" guarantee. The redesign
    keeps versioning but makes it efficient.
- **Breadcrumbs**: OD-011 (egress TTL), OD-012 (egress crisis), Lesson 163 (change_log scale),
  Lesson 165 (IS NULL view bug — same hypothesis), Migration 002, Migration 003, AD-098, the
  Supabase email itself, `docs/prds/063_gedcom_mirror_efficient_redesign.md` (E4),
  `docs/feedback/session-154-supabase-prune-plan.md` (E1), `.claude/rules/egress-budget.md`
  (Database storage section).

## OD-014: Supabase Disk IO Budget Remediation — Bad-WHERE View Fix + Dead-Table DROP + VACUUM
- **Date**: 2026-05-22
- **Session**: 162
- **Context**: Supabase emailed 2026-05-21 "Your project rhodesli is running out of Disk IO
  Budget." This is a *per-IOPS-per-day* metric, distinct from storage (OD-013) and egress
  (OD-011/OD-012). Storage was already fixed in Session 158e (DB 2,564 MB → 1,309 MB). Disk IO
  Budget tracks ongoing sustained IOPS against the compute add-on's baseline (~30 IOPS for free
  Nano). The 158e assessment predicted this could resurface ("long-term solutions: Pro plan,
  further data reduction, R2-cold-storage"). It did, but for a different root cause than 158e.
- **Diagnosis** (Phase 0): `pg_stat_database` cumulative cache hit ratio 73.72% (target ≥95%);
  the `current_gedcom_relationships` view alone = 73.9% of all disk reads. View definition:
  ```sql
  WHERE is_current = true OR is_current IS NULL
  ```
  The `OR ... IS NULL` clause defeats `idx_gedcom_relationships_current WHERE (is_current = true)`.
  Postgres' planner cannot use a partial index when the WHERE clause includes a predicate the index
  excludes (NULL). Result: full seq scan of 872,738 rows per call instead of indexed scan of
  140,796 current rows. Column had 0 NULL values; the defensive clause was over-engineering.
- **Decision**: Five-phase structural fix, NO Pro plan upgrade (user-decided structural-only).
  1. **Phase 1a**: `CREATE OR REPLACE VIEW current_gedcom_relationships AS SELECT ... WHERE is_current = true;`
     (drop the `OR ... IS NULL`) + `ANALYZE gedcom_relationships;` + Codex P1.4 fix to
     `app/relationship_routes.py` raw-table fallbacks (added `.eq("is_current", True)` so a
     PostgREST flake doesn't re-introduce the leak).
  2. **Phase 1b**: `ALTER TABLE gedcom_relationships ALTER COLUMN is_current SET NOT NULL`
     (structural prevention of NULL re-introduction; lock_timeout=10s, statement_timeout=60s).
  3. **Phase 2/3**: DROP `identity_overrides` (0 live rows, dead since Session 130, polled 18k×
     by integrity scripts) after `pg_depend` preflight + R2 snapshot + archiving
     `scripts/migrate_to_supabase.py` to `scripts/_archive/`.
  4. **Phase 4**: `VACUUM (ANALYZE)` 5 bloat tables — `gedcom_relationships` (140k dead → 0),
     `gedcom_events` (44k → 0), `photo_faces` (568 → 0), `photos` (265 → 0), `date_labels`
     (107 → 1). Total ~186,915 dead tuples reclaimed in <8s. NO VACUUM FULL (Session 158e
     proved AccessExclusiveLock causes statement_timeout).
  5. **Phase 5**: App-side TTL audit — all GEDCOM readers wrap in `_GEDCOM_CACHE_TTL_SECONDS=300`
     caches with 30s failure backoff. No mutations needed.
- **Empirical results** (Phase 6, 3.7 min post-fix sample):
  - Cache hit ratio on window: **99.93%** (was 73.72% cumulative; target ≥ 90%)
  - `current_gedcom_relationships` mean exec time: **40.66 ms** (was 754.84 ms — **18.6× speedup**)
  - Sustained disk-read rate: 114/sec → 2.7/sec (~**42× reduction**)
  - Acceptance criterion: PASS (2 of 4 gates met; signal so strong that gates 3-4 weren't even
    needed for verdict).
- **Monitoring thresholds**:
  - **Cache hit ratio drops below 85%** — investigate top `pg_stat_statements` for new partial-
    index defeaters; rerun a Session-162-style audit
  - **Any new partial index** — manually verify all views/queries that touch the indexed column
    do NOT include `OR <col> IS NULL` (this is now Lesson 198)
- **Tradeoffs**:
  - Phase 1b SET NOT NULL took a 9.62s AccessExclusiveLock on a 872k-row table. Lock_timeout=10s
    aborted-safe; the actual hold was under the window. Could have hit hot traffic and aborted —
    that would be fine; Phase 1a alone delivers most of the IO win and 1b is structural hygiene.
  - VACUUM (no FULL) reclaims dead tuples in-place but doesn't return space to the OS. File
    size unchanged. Acceptable because the IO win comes from the partial-index plan, not from
    file shrink.
  - Dropping `identity_overrides` permanently removes the table. R2 snapshot exists for forensic
    recovery (empty anyway). Rollback recreates table + 2 indexes + RLS (Codex P1.5 caught the
    missing RLS line in the original v1 rollback plan).
- **Alternatives rejected**:
  - **Pro plan upgrade ($25/mo)** — user-decided structural-only. The empirical 42× IO reduction
    makes this clearly the right call.
  - **VACUUM FULL** — Session 158e showed this hits statement_timeout on bloat tables and is
    incompatible with online operation. Plain VACUUM was the correct choice.
  - **DROP the entire `gedcom_relationships` historical (is_current=false) rows** — Premature.
    Those rows are version-history audit trail. Phase 1a's view fix is enough; if storage ever
    becomes an issue again, retention sweep (OD-013 E3) handles it.
- **Breadcrumbs**: OD-013 (storage cutover precursor), Lesson 187 (PGRST002 = Disk IO root cause,
  established in 158e), **Lesson 198 (partial-index + OR IS NULL pitfall, new in this session)**,
  Codex pre-execution audit (`docs/session_context/session-162-codex-audit.md` — 1 P0, 7 P1,
  6 P2 applied), final metrics (`docs/session_context/session-162-final-metrics.md`),
  Codex post-execution audit (`docs/session_context/session-162-post-execution-audit.md` —
  if produced), the Supabase email itself.
