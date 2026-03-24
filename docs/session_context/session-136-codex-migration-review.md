# Session 136: Codex Migration Review
Date: 2026-03-24

## Bottom Line
I would not trust a "fresh Supabase project" migration if it means replaying repo SQL and reconstructing production by hand.
I would only consider the new-free-org option if it is done as:
1. a live database copy from the current project
2. an explicit Auth migration
3. a hard verification gate before cutover
If the goal is the lowest-risk way to restore service and avoid another integrity incident, upgrading the current project to Pro for at least one month is the better decision.

| Plan | Risk | Verdict |
| --- | --- | --- |
| Upgrade current project to Pro | Low | Best trust-preserving option |
| New free project via live DB copy + auth migration + verification | Medium | Feasible, but non-trivial |
| New free project via repo SQL reconstruction | High | I would not do this |

This review is based on the repo plus official Supabase/Google docs. I did not inspect the live production DB directly and I did not run a migration.

## What The Codebase Says
### Supabase is the source of truth now
- The data layer uses `SUPABASE_URL` plus `SUPABASE_SERVICE_ROLE_KEY` (`app/supabase_data.py:37`).
- Core reads come from Supabase tables, not JSON:
  - `identities` via `IdentityRegistry.load_from_postgres()` (`core/registry.py:1909`)
  - `photos` and `photo_faces` via `PhotoRegistry.load_from_postgres()` (`core/photo_registry.py:381`)
- In `DATA_SOURCE=postgres`, missing core Supabase data becomes a runtime error, not a silent fallback (`app/main.py:150`, `app/main.py:1608`, `app/main.py:4102`).
- Implication: if the new project is missing a required table, view, or column, Rhodesli can hard-fail.

### Auth is separate and project-specific
- App auth depends on `SUPABASE_URL` and `SUPABASE_ANON_KEY` (`app/auth.py:20`).
- Google OAuth uses the current project URL and returns to `SITE_URL/auth/callback` (`app/auth.py:276`).
- Implication: switching projects means new URL, new keys, new provider setup, and redirect/callback changes.

### The checked-in SQL is not safe as a canonical rebuild plan
- `scripts/create_supabase_tables.py` is hardcoded to the old project ref `fvynibivlphxwfowzkjl` (`scripts/create_supabase_tables.py:334`).
- Several script table definitions already disagree with current writer code:
  - `date_labels` / `photo_locations` script definitions do not include the `data` column that the app reads and writes (`scripts/create_supabase_tables.py:40`, `scripts/create_supabase_tables.py:65`, `app/supabase_data.py:888`, `app/supabase_data.py:991`).
  - `person_comments` script uses `comment_text` / `comment_type`, while the app writes `comment` / `author` (`scripts/create_supabase_tables.py:85`, `app/supabase_data.py:1391`).
  - `pending_uploads`, `comparison_results`, `birth_year_estimates`, and `corrections_log` also drift from current app writes (`scripts/create_supabase_tables.py:128`, `scripts/create_supabase_tables.py:147`, `scripts/create_supabase_tables.py:163`, `scripts/create_supabase_tables.py:177`, `app/supabase_data.py:1262`, `app/supabase_data.py:1324`, `app/supabase_data.py:1345`, `app/supabase_data.py:1368`).
- There are conflicting migrations:
  - `photos` has `job_id` in `001_photos_table.sql`, but `create_core_tables.sql` omits it and adds `community_id` (`scripts/sql/001_photos_table.sql:5`, `scripts/sql/create_core_tables.sql:9`).
  - `media_group_id` / `parent_photo_id` are `UUID` in one migration and `TEXT` in another (`scripts/sql/006_media_groups.sql:4`, `scripts/sql/alter_photos_media_group.sql:4`).
  - `identities.state` is constrained too narrowly in `002_identities_table.sql` (`scripts/sql/002_identities_table.sql:5`).
- Implication: "run the SQL files and hope" is high risk.

### The live schema surface is wider than the requested file list
- Additional active runtime dependencies include:
  - `ml_runs` and `ml_proposals` (`app/main.py:2098`, `scripts/migrations/create_ml_run_tables.sql:4`)
  - GEDCOM versioning tables and `current_gedcom_*` views (`app/relationship_routes.py:350`, `app/relationship_routes.py:620`, `app/relationship_routes.py:720`, `scripts/supabase_migration_002_gedcom_versioning.sql:14`, `scripts/supabase_migration_003_gedcom_rich_mirror.sql:84`)
  - `gedcom_face_links`, which is actively read and written but not defined in the requested SQL directory (`app/relationship_routes.py:390`, `app/relationship_routes.py:1272`)
- Implication: a hand-recreated project is likely to miss objects unless you inventory the live DB itself.

### Supabase Storage is not the blocker here
- I found no meaningful use of Supabase Storage in the app path I reviewed. Rhodesli uses Cloudflare R2 for media.
- Implication: the main migration risks are database fidelity, auth configuration, and app cutover, not moving storage buckets.

## Answers
### a. Can we safely use pg_dump/pg_restore between Supabase projects?
Yes, but only if you handle Supabase-managed pieces explicitly.
- Safe:
  - `pg_dump` / restore for app-owned Postgres data is a normal migration path.
  - Supabase also documents Auth-user migration between projects.
- Main gotchas:
  - Default `supabase db dump` behavior is not a full-clone tool:
    - it excludes `auth`, `storage`, and extension-created schemas by default
    - its default output does not include data or roles unless explicitly requested
  - Auth migration is separate and important:
    - Supabase says `auth` users and hashed passwords can be migrated
    - if the new project uses a different JWT secret, existing tokens become invalid
    - changing the JWT secret regenerates the new project's `anon` and `service_role` keys
  - Database-only restore is incomplete:
    - Auth settings and API keys are manual
    - Realtime settings are manual
    - Extensions/settings are manual
  - Full restore into a fresh Supabase project can produce duplicate-object noise for built-in schemas; Supabase says that can be expected in some restore flows.
  - Supabase's "Restore to a new project" dashboard clone path is paid-plan only, so a free-tier migration should assume raw dump/restore rather than a one-click clone.
  - Recreating users manually is risky because Rhodesli stores auth user UUIDs in app data like `communities.owner_id` and notification `user_id` fields (`app/supabase_data.py:1656`, `scripts/sql/session_122_workspace_schema.sql:5`, `scripts/sql/007_notifications.sql:5`).
- Bottom line:
  - `pg_dump` / restore is feasible.
  - A naive dump/restore is not safe.
  - A public-only copy is not enough if you want to preserve users and user UUID continuity.

### b. What is the safest step-by-step migration path?
The safest path is "copy the live database, then manually reconfigure the project-level Supabase settings".
1. Keep the current project untouched as the source of truth.
2. Decide rollback before starting: if migration fails, are you willing to upgrade the old project to Pro immediately?
3. Create the new project in the same region if possible.
4. Decide JWT-secret strategy before cutover.
   - Reuse old JWT secret if you want token continuity.
   - If you change it later, the new `anon` and `service_role` keys regenerate.
5. Prepare the target:
   - confirm required extensions, especially `pg_trgm` (`scripts/migrations/add_gedcom_trigram_index.sql:10`)
   - review non-DB auth settings: Site URL, Redirect URLs, provider config, email templates/SMTP if used
6. Take backup artifacts from the old project:
   - app schema/data dump
   - auth backup
   - table-count and checksum manifests
7. Restore into the new project:
   - app schema/data
   - auth users if you want preserved passwords and stable UUIDs
   - verify required views such as `current_gedcom_*`
8. Manually reconfigure the new project:
   - Google provider
   - redirect allow-list / Site URL
   - any auth/email settings outside the DB
9. Update Railway:
   - `SUPABASE_URL`
   - `SUPABASE_ANON_KEY`
   - `SUPABASE_SERVICE_ROLE_KEY`
10. Update or quarantine scripts that hardcode the old project ref, including:
   - `scripts/create_supabase_tables.py`
   - `scripts/migrate_core_tables.py`
   - `scripts/migrate_complete.py`
   - `scripts/update_email_templates.sh`
11. Restart, verify, and keep the old project plus dumps until burn-in is complete.
- What I would not do:
  - treat repo SQL as the canonical rebuild path
  - manually recreate users unless I had accepted broken UUID continuity

### c. How do we verify nothing broke?
Use three layers.
1. Structure check
   - confirm all required tables, views, and extensions exist
   - hard fail the migration if the schema inventory is incomplete
2. Data fidelity check
   - row counts must match for critical tables:
     - `identities`, `photos`, `photo_faces`
     - `annotations`, `relationships`, `gedcom_matches`
     - `communities`, `photo_communities`, `identity_communities`
     - `gedcom_face_links`, `gedcom_individuals`, `gedcom_events`, `gedcom_relationships`
     - `ml_runs`, `ml_proposals`
   - primary-key sets must match
   - deterministic row hashes should match for critical tables
3. App smoke tests
   - home, person, photo, community pages
   - admin password login
   - Google OAuth
   - password reset
   - identity confirm / merge / note write
   - photo upload
   - GEDCOM search and link/unlink
   - notifications
- Useful local scripts:
  - `scripts/migrate_core_tables.py` for core row-count verification
  - `scripts/reconcile_supabase.py` for some JSON-vs-Supabase checks
  - `scripts/verify_session133.py` for the style of deeper integrity checks worth repeating
- Test suite:
  - `pytest tests/ -x -q`
  - `pytest rhodesli_ml/tests/ -x -q`
  - Important: tests are necessary but not sufficient. Counts, hashes, and smoke tests matter more here.

### d. What about Google OAuth credentials?
Yes. The same Google Cloud project, and usually the same web OAuth client, can be reused.
- What must change:
  - add the new Supabase callback URI in Google Cloud
  - configure the Google provider in the new Supabase project
  - make sure the app's `SITE_URL` / callback URL is on the Supabase redirect allow-list
- Practical advice:
  - keep both old and new Supabase callback URIs on the Google client during migration
  - remove the old one later if you want to clean up

### e. Is there a rollback plan if migration fails?
Yes, but it is weaker than it appears.
- What you can roll back to:
  - the old project plus old Railway vars
- What you cannot roll back to:
  - a working old free-tier project without paying, because the current project is still quota-restricted until April 5, 2026
- Real rollback options:
  1. Best rollback: keep the old project untouched and upgrade it to Pro immediately if the new project fails.
  2. Degraded rollback: set `DATA_SOURCE=json` as an emergency escape hatch and accept the integrity/feature tradeoffs.
  3. Fix-forward only: if you refuse both Pro and JSON fallback, a failed cutover means outage-time repair work on the new project.
- For a trust-sensitive system, I would pre-authorize option 1 before starting.

### f. What is the realistic risk level? Is this worth doing to save $25/month?
My honest answer:
- New free project by manual reconstruction: not worth it.
- New free project by live DB copy: feasible, but still not what I would choose over paying for one month of Pro.
Why:
- the app is already down
- rollback is weak
- the checked-in schema is drifted
- the Session 136 egress fix is estimated at about 3 GB/month but has not been validated in production yet (`docs/session_context/session-136-supabase-migration-research.md:13`)
- if that estimate is wrong, a new free project could hit quota again
Today is March 24, 2026. Service is restricted until April 5, 2026. That is about twelve days of impaired service if you do nothing.
My recommendation:
- upgrade the current project to Pro now
- confirm the egress fixes work in production
- later decide whether to downgrade or do a calmer migration

### g. Alternatives we have not considered
1. Upgrade to Pro now, possibly just for one month.
2. Ask Supabase support for a temporary reset/reactivation/exception.
3. Do the new-project migration, but only as a full DB copy plus auth migration.
4. Wait until April 5, 2026 if downtime is acceptable.
5. Use JSON fallback only as an emergency last resort.
6. Do not spend time reducing stored data; the issue is egress/query behavior, not DB size.
7. Do not expect org transfer to help; it is still the same project, not a fresh database/quota reset.

## Final Recommendation
If you want the most trustworthy plan:
1. Upgrade the current project to Pro immediately.
2. Keep the Session 136 egress fixes.
3. Observe real usage for a short period.
4. Only consider a later move to a new free project when it is a calm optimization task, not outage surgery.
If you insist on the free-project migration:
- use a live database copy
- migrate auth explicitly
- verify counts, hashes, and app flows before cutover
- do not use the repo SQL as the canonical rebuild path

## Sources
Official docs:
- Supabase CLI `db dump`: https://supabase.com/docs/reference/cli/supabase-db-dump
- Supabase "Migrating Auth Users Between Supabase Projects": https://supabase.com/docs/guides/troubleshooting/migrating-auth-users-between-projects
- Supabase "Restore to a new project": https://supabase.com/docs/guides/platform/clone-project
- Supabase "Migrating within Supabase": https://supabase.com/docs/guides/platform/migrating-within-supabase
- Supabase "Restore Dashboard backup": https://supabase.com/docs/guides/platform/migrating-within-supabase/dashboard-restore
- Supabase "Redirect URLs": https://supabase.com/docs/guides/auth/redirect-urls
- Supabase "Login with Google": https://supabase.com/docs/guides/auth/social-login/auth-google
- Google OAuth web-server apps: https://developers.google.com/identity/protocols/oauth2/web-server
Repo evidence:
- `app/supabase_data.py`
- `app/auth.py`
- `core/registry.py`
- `core/photo_registry.py`
- `app/main.py`
- `app/relationship_routes.py`
- `scripts/sql/`
- `scripts/create_supabase_tables.py`
- `scripts/migrations/create_ml_run_tables.sql`
- `scripts/migrations/add_gedcom_trigram_index.sql`
- `scripts/supabase_migration_001.sql`
- `scripts/supabase_migration_002_gedcom_versioning.sql`
- `scripts/supabase_migration_003_gedcom_rich_mirror.sql`
- `docs/session_context/session-136-supabase-migration-research.md`
