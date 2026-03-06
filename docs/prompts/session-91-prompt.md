# Session 91: Full Postgres Migration + Platform Foundation

**Context**: `docs/session_context/session-91-context.md`
**Predecessor**: Session 90b (sorting fix, main.py refactor, Supabase shadow writes, performance)

## Problem Statement

Rhodesli's core data still lives as JSON files on a Railway volume. Session 90b started shadow writes; Session 91 completes the migration and lays the architectural foundation for multi-collection support.

This session has two goals:
1. **Complete the Supabase migration** — flip reads to Postgres, eliminate JSON as source of truth
2. **Lay platform foundation** — GlobalPersonID schema, Sentry, PostHog, structured logging

After this session, the codebase should be ready for a second collection (Fox family photos) and ML service extraction in Session 92+.

## Session Protocol
- Set `.claude/current_session.txt` to `91`
- Read `tasks/lessons.md` and `tasks/todo.md` at start
- Commit after every act, `/clear` between acts
- Use Claude Chrome for ALL frontend verification
- Run `/session-review` at session end
- Screenshots to `docs/screenshots/session-91/`

---

## Dependencies on Session 90b

This prompt assumes Session 90b shipped:
- [ ] Supabase tables created (`photos`, `identities`, `photo_faces`, `date_labels`, `photo_locations`)
- [ ] Shadow write functions in `app/supabase_data.py`
- [ ] Backfill script (`scripts/backfill_supabase.py`) run successfully
- [ ] main.py refactored (< 15,000 lines)

**If any of these are incomplete**, Act 1 must finish them before proceeding. Adjust the parallelization plan accordingly.

---

## Parallelization Plan

**Phase 1** (Acts 0-1): Sequential on main — orient + verify 90b state + fix gaps
**Phase 2** (Acts 2-5): Parallel worktree subagents:
- Track A: Postgres read path flip (worktree: `session-91/postgres-reads`)
- Track B: GlobalPersonID + community schema (worktree: `session-91/multi-tenant`)
- Track C: Sentry + PostHog + structured logging (worktree: `session-91/observability`)
- Track D: ROADMAP + BACKLOG + architecture docs update (worktree: `session-91/docs`)
**Phase 3** (Act 6): Merge all tracks, browser verify, assessment

**File conflict analysis**:
- Track A touches `core/registry.py`, `core/photo_registry.py`, `app/supabase_data.py`, `app/main.py` (imports) — merges FIRST
- Track B touches `scripts/sql/` (new files), `app/supabase_data.py` (new functions) — merges AFTER Track A
- Track C touches `app/main.py` (middleware init), `requirements.txt` — merges AFTER Track A
- Track D touches docs only — independent, can merge anytime
- **Merge order**: D first (docs only), then A (core), then B (schema), then C (observability)

---

## Act 0: Orient (5 min)

1. Read this prompt, context file, `tasks/lessons.md`
2. Read `docs/assessments/session-90b-assessment.md` (or log if no assessment)
3. Verify current state: `git log --oneline -5`, `git status`, test suite passes
4. Set `.claude/current_session.txt` to `91`
5. Create `docs/session_logs/session-91-log.md` with phase checklist
6. **Verify 90b deliverables** — check each dependency listed above

---

## Act 1: Complete 90b Gaps (if any) (15 min)

If any 90b deliverable is incomplete, finish it here. Specifically:

### 1a. Verify Supabase Tables Exist
Run the backfill script if not already run. Verify record counts match JSON:
- `photos` table: should have ~296 rows
- `identities` table: should have ~777 rows
- `photo_faces` table: should have ~982 rows

### 1b. Verify Shadow Writes Are Working
1. Make a test identity change (rename a PROPOSED identity)
2. Check that the change appears in both JSON AND Supabase
3. Revert the test change

### 1c. If Tables Don't Exist Yet
Create them using the SQL from `docs/session_context/session-91-context.md` or the scripts from Session 90b. The schema should include:

```sql
-- Core tables (if not created by 90b)
CREATE TABLE IF NOT EXISTS photos (
    photo_id TEXT PRIMARY KEY,
    path TEXT NOT NULL,
    source TEXT,
    collection TEXT,
    source_url TEXT,
    upload_date TIMESTAMPTZ,
    width INTEGER,
    height INTEGER,
    face_count INTEGER,
    uploaded_by TEXT,
    community_id UUID,  -- nullable, for future multi-tenant
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS identities (
    identity_id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    display_name TEXT,
    state TEXT NOT NULL DEFAULT 'INBOX',
    anchor_ids JSONB DEFAULT '[]',
    candidate_ids JSONB DEFAULT '[]',
    negative_ids JSONB DEFAULT '[]',
    metadata JSONB DEFAULT '{}',
    version_id INTEGER DEFAULT 1,
    merged_into UUID,
    community_id UUID,  -- nullable, for future multi-tenant
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS photo_faces (
    face_id TEXT PRIMARY KEY,
    photo_id TEXT NOT NULL REFERENCES photos(photo_id),
    identity_id UUID REFERENCES identities(identity_id),
    bbox JSONB,
    det_score NUMERIC(6,4),
    quality NUMERIC(6,4),
    embedding float4[],  -- 512-dim vector
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS date_labels (
    photo_id TEXT PRIMARY KEY REFERENCES photos(photo_id),
    estimated_decade TEXT,
    best_year_estimate INTEGER,
    confidence TEXT,
    model_used TEXT,
    labeled_by TEXT,
    raw_response JSONB,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS photo_locations (
    photo_id TEXT PRIMARY KEY REFERENCES photos(photo_id),
    lat NUMERIC(10,7),
    lng NUMERIC(10,7),
    location_name TEXT,
    location_estimate TEXT,
    confidence TEXT,
    geocoded_from TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

Commit: `feat(data): complete Supabase table setup + backfill`

---

## Act 2: Launch Parallel Tracks (5 min)

**After Act 1 is committed**, launch 4 parallel worktree subagents.

### Track A: Postgres Read Path Flip

**Worktree**: `session-91/postgres-reads`
**Goal**: IdentityRegistry and PhotoRegistry read from Supabase instead of JSON.

**Implementation plan**:

1. **Feature flag**: Add `DATA_SOURCE` env var (`json` or `postgres`, default `json`)
2. **IdentityRegistry adapter**:
   - New method `load_from_postgres(cls)` in `core/registry.py`
   - Queries `identities` table, constructs same in-memory dict structure
   - Falls back to JSON if Supabase unavailable
   - Wire into `load()`: if `DATA_SOURCE=postgres`, use Postgres path
3. **PhotoRegistry adapter**:
   - New method `load_from_postgres(cls)` in `core/photo_registry.py`
   - Queries `photos` + `photo_faces` tables
   - Reconstructs `_photos` dict and `_face_to_photo` mapping
4. **Embeddings**:
   - For now, keep reading `embeddings.npy` from disk (too complex to migrate vectors in this session)
   - Add TODO comment for future pgvector migration
5. **Date labels + photo locations**:
   - Read from `date_labels` and `photo_locations` Supabase tables
   - Replace JSON file reads in `app/main.py` and `app/estimate_routes.py`
6. **Remove JSON writes for identity/photo changes**:
   - When `DATA_SOURCE=postgres`, `save_registry()` writes ONLY to Supabase (not JSON)
   - `save_photo_registry()` writes ONLY to Supabase
   - JSON files become export-only artifacts
7. **Startup sync**:
   - When `DATA_SOURCE=postgres`, skip `sync_from_supabase_on_startup()` (Supabase IS the source)
   - When `DATA_SOURCE=json` (default), keep existing behavior

**Critical invariants to preserve**:
- `neighbors.py` is FROZEN — must still receive same embedding data format
- Co-occurrence validation still works (face_to_photo mapping)
- Optimistic concurrency (version_id) still works
- All admin actions (confirm, merge, rename, detach, reject) still work

**Tests**:
- New: Test `load_from_postgres()` returns same structure as `load()` from JSON
- New: Test `save_registry()` with `DATA_SOURCE=postgres` writes to Supabase
- Update: All existing tests should pass with `DATA_SOURCE=json` (default)
- New: Integration test that round-trips identity through Postgres

**Acceptance**: With `DATA_SOURCE=postgres` on Railway, app loads identities + photos from Supabase. With `DATA_SOURCE=json`, everything works as before (zero regression).

### Track B: GlobalPersonID + Community Schema

**Worktree**: `session-91/multi-tenant`
**Goal**: Add multi-tenant schema foundation. No runtime changes yet.

1. **Create `communities` table** (SQL in `scripts/sql/create_communities.sql`):
   ```sql
   CREATE TABLE IF NOT EXISTS communities (
       id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
       slug TEXT UNIQUE NOT NULL,
       name TEXT NOT NULL,
       description TEXT,
       admin_emails TEXT[],
       r2_prefix TEXT NOT NULL,
       config JSONB DEFAULT '{}',
       created_at TIMESTAMPTZ DEFAULT now(),
       updated_at TIMESTAMPTZ DEFAULT now()
   );
   ```

2. **Create `global_person_links` table** (SQL in `scripts/sql/create_global_person_links.sql`):
   ```sql
   CREATE TABLE IF NOT EXISTS global_person_links (
       id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
       global_person_id UUID NOT NULL,
       community_id UUID NOT NULL REFERENCES communities(id),
       identity_id UUID NOT NULL,
       link_type TEXT NOT NULL,  -- 'gedcom', 'ml_proposal', 'human_confirmed'
       confidence NUMERIC(5,4),
       linked_by TEXT,
       evidence JSONB,  -- supporting data for the link
       created_at TIMESTAMPTZ DEFAULT now(),
       updated_at TIMESTAMPTZ DEFAULT now(),
       UNIQUE(community_id, identity_id)
   );

   CREATE INDEX IF NOT EXISTS idx_gpl_global ON global_person_links(global_person_id);
   CREATE INDEX IF NOT EXISTS idx_gpl_identity ON global_person_links(identity_id);
   CREATE INDEX IF NOT EXISTS idx_gpl_community ON global_person_links(community_id);
   ```

3. **Seed Rhodes community**:
   ```sql
   INSERT INTO communities (slug, name, description, admin_emails, r2_prefix)
   VALUES ('rhodes', 'Jewish Community of Rhodes',
           'Heritage photo archive for the Sephardic Jewish community of Rhodes',
           ARRAY['NolanFox@gmail.com'], 'raw_photos/')
   ON CONFLICT (slug) DO NOTHING;
   ```

4. **Add `community_id` to existing tables** (if not already added in Act 1):
   - `ALTER TABLE identities ADD COLUMN IF NOT EXISTS community_id UUID REFERENCES communities(id);`
   - `ALTER TABLE photos ADD COLUMN IF NOT EXISTS community_id UUID REFERENCES communities(id);`
   - Backfill: `UPDATE identities SET community_id = (SELECT id FROM communities WHERE slug = 'rhodes') WHERE community_id IS NULL;`
   - Same for `photos`

5. **Write PRD-029: Multi-Collection Architecture** (`docs/prds/029_multi_collection.md`):
   - Problem: Single-community architecture limits growth
   - Solution: Community-scoped data + GlobalPersonID for cross-linking
   - Schema (above)
   - Migration plan for existing data
   - Out of scope: RLS policies, ML service extraction, UX changes

6. **Tests**: Verify SQL runs without error. Verify backfill populates community_id.

**Acceptance**: Tables exist. Rhodes community seeded. All existing identities + photos have `community_id` set. PRD-029 written.

### Track C: Observability — Sentry + PostHog + Logging

**Worktree**: `session-91/observability`
**Goal**: Add error tracking, analytics, and structured logging.

#### Sentry (Error Tracking)
1. Add `sentry-sdk` to `requirements.txt`
2. In app startup (main.py or wherever the ASGI app is created):
   ```python
   import sentry_sdk

   if os.environ.get("SENTRY_DSN"):
       sentry_sdk.init(
           dsn=os.environ["SENTRY_DSN"],
           environment=os.environ.get("SENTRY_ENVIRONMENT", "production"),
           traces_sample_rate=0.1,  # 10% of transactions for performance
           send_default_pii=False,  # Heritage app — faces are PII
       )
   ```
3. Do NOT wrap in SentryAsgiMiddleware yet (FastHTML may not be standard ASGI). Test first.
4. Add `SENTRY_DSN` to Railway env vars (user will do this manually).

#### PostHog (Analytics)
1. Add PostHog JS snippet to the base HTML template (the `<head>` section in main.py):
   ```python
   def _posthog_script():
       key = os.environ.get("POSTHOG_API_KEY", "")
       if not key:
           return ""
       return Script(f"""
           !function(t,e){{var o,n,p,r;e.__SV||(window.posthog=e,e._i=[],e.init=function(i,s,a){{function g(t,e){{var o=e.split(".");2==o.length&&(t=t[o[0]],e=o[1]),t[e]=function(){{t.push([e].concat(Array.prototype.slice.call(arguments,0)))}}}}(p=t.createElement("script")).type="text/javascript",p.crossOrigin="anonymous",p.async=!0,p.src=s.api_host+"/static/array.js",(r=t.getElementsByTagName("script")[0]).parentNode.insertBefore(p,r);var u=e;for(void 0!==a?u=e[a]=[]:a="posthog",u.people=u.people||[],u.toString=function(t){{return"$posthog_obj$"+(t?t:"posthog")}},u._i=e._i,u.init=function(){{return e.init.apply(u,arguments)}},n=0;n<["capture","identify","alias","people.set","people.set_once","register","register_once","unregister","opt_out_capturing","has_opted_out_capturing","opt_in_capturing","reset","isFeatureEnabled","onFeatureFlags","getFeatureFlag","getFeatureFlagPayload","reloadFeatureFlags","group","capture","getGroups","setPersonProperties","resetGroups"].length;n++)g(u,["capture","identify","alias","people.set","people.set_once","register","register_once","unregister","opt_out_capturing","has_opted_out_capturing","opt_in_capturing","reset","isFeatureEnabled","onFeatureFlags","getFeatureFlag","getFeatureFlagPayload","reloadFeatureFlags","group","capture","getGroups","setPersonProperties","resetGroups"][n]);e._i.push([i,s,a])}},e.__SV=1)}}(document,window.posthog||[]);
           posthog.init('{key}', {{api_host: 'https://us.i.posthog.com', person_profiles: 'identified_only', respect_dnt: true}});
       """)
   ```
2. Add `POSTHOG_API_KEY` to Railway env vars (user will create PostHog account + get key).
3. Do NOT add `posthog-python` yet — client-side JS is sufficient for now.

#### Structured Logging
1. Add `structlog` to `requirements.txt`
2. Configure in app startup:
   ```python
   import structlog

   structlog.configure(
       processors=[
           structlog.contextvars.merge_contextvars,
           structlog.processors.add_log_level,
           structlog.processors.TimeStamper(fmt="iso"),
           structlog.dev.ConsoleRenderer()  # Use JSONRenderer() in production
       ],
       wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
   )
   ```
3. Do NOT convert existing `logging.getLogger()` calls — just configure structlog to work alongside stdlib.
4. Use structlog for NEW code going forward.

**Tests**:
- Verify Sentry init doesn't crash when DSN not set
- Verify PostHog snippet renders when key is set, absent when not
- Verify structlog configures without errors

**Acceptance**: `sentry-sdk` and `structlog` in requirements.txt. Sentry init gated on env var. PostHog snippet gated on env var. Structured logging configured. No runtime errors when env vars are absent.

### Track D: Documentation Updates

**Worktree**: `session-91/docs`
**Goal**: Update ROADMAP, BACKLOG, architecture docs with new strategic direction.

1. **Update ROADMAP.md**:
   - Add new items from Nolan's conversation:
     - GlobalPersonID schema (mark as in-progress if done this session)
     - ML service extraction (future, with reference to context file)
     - Second collection onboarding (future)
     - Standalone tooling product (future)
     - Chatbot research interface (future)
   - Update Phase F status
   - Add Session 91 to "Recently Completed" (after session ends)

2. **Update BACKLOG.md**:
   - Add `PLATFORM-001`: GlobalPersonID schema — link to PRD-029
   - Add `PLATFORM-002`: ML service extraction — standalone FastAPI service for face embedding/comparison
   - Add `PLATFORM-003`: Second collection onboarding (Fox family photos)
   - Add `PLATFORM-004`: Standalone Gemini tooling product
   - Add `OPS-005`: Sentry error tracking integration
   - Add `OPS-006`: PostHog analytics integration
   - Add `OPS-007`: Structured logging (structlog)
   - Update `DATA-007` status based on migration progress
   - Update `GEN-001` with concrete architecture from context file

3. **Update architecture docs**:
   - `docs/architecture/OVERVIEW.md` — update data layer description to reflect Postgres migration
   - `docs/architecture/DATA_MODEL.md` — add Supabase table schemas, note JSON is deprecated
   - Create `docs/architecture/MULTI_TENANT.md` — GlobalPersonID design, community schema, R2 organization

4. **Update ALGORITHMIC_DECISIONS.md**:
   - AD-XXX: GlobalPersonID schema design (3 linking mechanisms: GEDCOM, ML, human)
   - AD-XXX: Postgres as source of truth (DATA_SOURCE feature flag)
   - AD-XXX: Observability stack (Sentry + PostHog + structlog)

5. **Update `docs/roadmap/FEATURE_STATUS.md`**:
   - Phase F items: check boxes for Postgres migration, Sentry, PostHog
   - Add multi-tenant items

6. **Update `docs/roadmap/SESSION_HISTORY.md`**:
   - Add Session 91 entry

**Acceptance**: All docs updated with breadcrumbs. New BACKLOG items have IDs and references. ROADMAP reflects new strategic direction.

---

## Act 3: While Subagents Run — Deploy Verification (15 min)

While parallel tracks execute, verify the current production state:

1. **Browser verify** with Claude Chrome:
   - Landing page loads
   - Photos page: sorting works (if fixed in 90b)
   - Upload page works
   - Compare page works
   - Person page loads
2. **Check Railway logs** for any errors since last deploy
3. Document any issues found for fixing

---

## Act 4: Merge Tracks + Resolve Conflicts (20 min)

1. Check all subagent branches for completion
2. **Merge order**: Track D (docs) FIRST, then Track A (postgres reads), then Track B (multi-tenant schema), then Track C (observability)
3. Use `./scripts/merge.sh session-91/docs session-91/postgres-reads session-91/multi-tenant session-91/observability`
4. Run `make test-fast` after each merge
5. Resolve conflicts

---

## Act 5: Deploy + Verify (15 min)

1. **Set Railway env vars** (document what needs to be set manually):
   - `DATA_SOURCE=json` (keep JSON for initial deploy — flip to `postgres` after verification)
   - `SENTRY_DSN` (user will create Sentry project)
   - `POSTHOG_API_KEY` (user will create PostHog project)
2. `git push origin main` to deploy
3. Wait for deploy completion (Lesson 94)
4. **Browser verify**:
   - App loads correctly with `DATA_SOURCE=json`
   - No Sentry/PostHog errors in console
   - All pages load
5. **Manual flip test** (if time permits):
   - Set `DATA_SOURCE=postgres` on Railway
   - Verify app loads identities + photos from Supabase
   - Verify admin actions work (confirm an identity, check Supabase)
   - If any issues, flip back to `DATA_SOURCE=json`
6. Save screenshots to `docs/screenshots/session-91/`

---

## Act 6: Assessment + Final Docs (10 min)

Standard mandatory outputs:

1. Write `docs/assessments/session-91-assessment.md`
2. Update `docs/session_logs/session-91-log.md`
3. Update `CHANGELOG.md` — new version entry
4. Verify all breadcrumbs from Track D
5. Verify all tests pass (`make test-fast`)

---

## Acceptance Criteria

### Must Ship
- [ ] Supabase tables exist with backfilled data from JSON
- [ ] `DATA_SOURCE` feature flag works (`json` = existing behavior, `postgres` = reads from Supabase)
- [ ] IdentityRegistry loads from Postgres when `DATA_SOURCE=postgres`
- [ ] PhotoRegistry loads from Postgres when `DATA_SOURCE=postgres`
- [ ] `communities` table exists with Rhodes community seeded
- [ ] `global_person_links` table exists (empty, schema ready)
- [ ] All existing identities + photos have `community_id` set to Rhodes
- [ ] `sentry-sdk` + `structlog` in requirements.txt
- [ ] Sentry init gated on `SENTRY_DSN` env var
- [ ] PostHog JS snippet gated on `POSTHOG_API_KEY` env var
- [ ] PRD-029 (Multi-Collection Architecture) written
- [ ] ROADMAP + BACKLOG updated with new strategic items
- [ ] All tests pass
- [ ] Browser verified via Claude Chrome

### Should Ship
- [ ] Date labels + photo locations read from Supabase when `DATA_SOURCE=postgres`
- [ ] Architecture docs updated (OVERVIEW, DATA_MODEL, new MULTI_TENANT.md)
- [ ] AD entries for GlobalPersonID, Postgres migration, observability stack

### Deferred (Session 92+)
- [ ] Embeddings migration to pgvector (keep as .npy for now)
- [ ] ML service extraction (separate FastAPI service)
- [ ] Second collection onboarding (Fox family photos)
- [ ] Postgres RLS policies (not needed until second community)
- [ ] Chatbot research interface
- [ ] Standalone tooling product
- [ ] `SentryAsgiMiddleware` (need to test FastHTML ASGI compatibility first)

## Key Skills to Use

- `/simplify` — after implementation acts
- `/session-review` — at session end (mandatory)
- Claude Chrome — for ALL frontend verification
- Worktree subagents — for parallel tracks

## Non-Goals

- UX redesign or new features
- ML pipeline changes
- Running ML on photos
- Full multi-tenant runtime (just schema + seed)
- Removing JSON files from repo (keep as fallback)

## Risk Mitigation

**Biggest risk**: Postgres read path serves stale or empty data.
**Mitigation**: `DATA_SOURCE` feature flag defaults to `json`. Only flip to `postgres` after manual verification. Can flip back instantly.

**Second risk**: Shadow writes diverge from JSON.
**Mitigation**: Consistency check script comparing JSON record counts vs Supabase counts. Run before flipping.
