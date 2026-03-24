# Session 136: Planning Agent Migration Review

## Bottom Line
Migration is feasible (~107 minutes, LOW-MEDIUM risk) via pg_dump/pg_restore of the public schema. Old project stays intact as rollback. But if GEDCOM views don't restore cleanly, abort and pay $25.

## Key Findings

### Env vars to update (4 total)
1. `SUPABASE_URL`
2. `SUPABASE_ANON_KEY`
3. `SUPABASE_SERVICE_ROLE_KEY`
4. `DATABASE_URL` (scripts only, not runtime)

### Auth users
- Only 2-3 users. Manual re-registration simpler than migrating auth.users.
- App determines admin by email match (`ADMIN_EMAILS`), not UUID.
- `communities.owner_id` stores auth UUID but WORKSPACE-001 not fully deployed — non-issue.
- Same Google Cloud OAuth credentials work in new project.

### pg_dump approach
```bash
pg_dump --schema=public --no-owner --no-privileges --clean --if-exists \
  -h db.OLD_REF.supabase.co -p 5432 -U postgres -d postgres > rhodesli_dump.sql

psql -h db.NEW_REF.supabase.co -p 5432 -U postgres -d postgres < rhodesli_dump.sql
```

Extensions to enable first: `pg_trgm`, `pgcrypto`

### Verification
1. Row counts per table (pre vs post)
2. Critical data checksums (identities, photos, photo_faces, CONFIRMED count)
3. JSONB anchor_ids integrity check (recurring corruption vector)
4. Production smoke test (health, login, person page, admin bar)

### Step-by-step plan
| Step | Action | Effort | Risk |
|------|--------|--------|------|
| 1 | Create new Supabase org + project | 5 min | LOW |
| 2 | Enable extensions | 5 min | LOW |
| 3 | pg_dump old project | 10 min | LOW |
| 4 | Verify dump has all tables | 10 min | LOW |
| 5 | pg_restore to new project | 15 min | MEDIUM |
| 6 | Verification queries | 10 min | LOW |
| 7 | Configure Google OAuth | 10 min | LOW |
| 8 | Local .env test | 15 min | LOW |
| 9 | Create admin user | 5 min | LOW |
| 10 | Update Railway env vars (CUTOVER) | 5 min | MEDIUM |
| 11 | Verify production | 15 min | LOW |
| 12 | Clean up old callback URL | 2 min | LOW |

**Total: ~107 minutes. Rollback: revert 3 Railway env vars.**

### Recommendation
YES, proceed — but abort and pay $25 if step 5/6 reveals GEDCOM view issues.

## Comparison with Codex Review

| Topic | Codex | Planning Agent |
|-------|-------|----------------|
| Overall recommendation | Pay $25 first | Migration feasible, try first |
| Repo SQL rebuild | HIGH risk, don't do it | Agrees — use pg_dump only |
| pg_dump/restore | Feasible but non-trivial | Feasible, ~1 hour |
| Auth migration | Explicit handling needed | Re-register (only 2-3 users) |
| Rollback | Weak (old project still restricted) | Clean (revert 3 env vars) |
| GEDCOM views | High complexity concern | Abort trigger if views fail |

Both agree: never use repo SQL, use pg_dump of live DB, keep old project as fallback.
