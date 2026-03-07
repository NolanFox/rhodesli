# Session 91b Context: Finish What 91 Didn't

**Predecessor**: Session 91 (6 parallel worktree tracks — PRD backlog + platform foundation)
**Date**: 2026-03-07
**Origin**: Post-session audit found significant gaps between claimed and actual completion.

## What Session 91 Actually Shipped vs. Claimed

Session 91 claimed all 6 tracks "SHIPPED" but an honest audit reveals:

| Feature | Claimed | Reality |
|---------|---------|---------|
| **PRD-028 Notifications** | SHIPPED | UI skeleton only. Supabase tables never created. Event triggers never wired into save_registry(). Bell icon renders but always shows 0. |
| **PRD-011 Life Events** | SHIPPED | Routes exist, tables never created. /events shows 0 events. Seed script never run. |
| **PRD-027A R2 Backup** | SHIPPED | Scripts exist with tests. Likely functional. |
| **PRD-029 Photo Backs** | SHIPPED | Media group API + browse filter added. Works. |
| **PRD-027 B/C Postgres Read** | SHIPPED | Code exists, DATA_SOURCE flag exists. Only tested with mocks, never against real Supabase. |
| **GlobalPersonID** | SHIPPED | SQL files exist. Tables never created. |
| **Observability** | SHIPPED | Packages in requirements.txt. SENTRY_DSN/POSTHOG_API_KEY not set on Railway. |

### Root Cause
Session 91 wrote SQL schema files but **never executed them against Supabase**. The assessment acknowledges this as a "[MEDIUM] red flag" but the session summary says "SHIPPED" anyway. The Feature Reality Contract was not honestly applied — "data exists" (SQL file in git) is not "app loads it" (table exists in Supabase).

### Notification Triggers — Completely Missing
`create_identity_confirmed_notification()` exists in notification_routes.py (line 152) but is **never called** from anywhere. The acceptance criteria said "Confirming an identity creates a notification" — this does not work. The function uses a placeholder user_id `"00000000-0000-0000-0000-000000000000"`.

### Supabase Access
The user confirmed: Supabase MCP or CLI is available and has been used before. Connection details are in .env:
- `SUPABASE_URL=https://fvynibivlphxwfowzkjl.supabase.co`
- `DATABASE_URL=postgresql://postgres:...@db.fvynibivlphxwfowzkjl.supabase.co:5432/postgres`
- `SUPABASE_SERVICE_ROLE_KEY` is available

SQL files to execute (in order):
1. `scripts/sql/create_communities.sql`
2. `scripts/sql/seed_rhodes_community.sql`
3. `scripts/sql/create_global_person_links.sql`
4. `scripts/sql/create_life_events.sql`
5. `scripts/sql/007_notifications.sql`
6. `scripts/sql/alter_photos_media_group.sql`
7. `scripts/sql/create_core_tables.sql` (if photos/identities/photo_faces tables don't already exist)

---

## Victor Capeluto / Leon's Restaurant — Collection Name Overindexing (AD-209)

### Problem
Photo 3192877a90a174e9 shows Victor and Victoria Capeluto in front of "LEON'S RESTAURANT." Session 90c's AD-204 fix added collection name as a STRONG location signal:

```
IMPORTANT: The collection name often indicates the geographic origin of photos.
For example, "Tampa Collection" strongly suggests photos were taken in or near Tampa.
Use this as corroborating evidence alongside visual and biographical analysis.
```

This is **wrong**. The photo is in the "Nace Capeluto Tampa Collection" because Nace lived in Tampa and that's where the photos were stored. But the photo was taken in **Asheville, NC** — where Leon Capeluto actually lived and ran his restaurant (1928-1940).

### GEDCOM Ground Truth
From `docs/session_context/session_81_asheville_prompt.txt`:
- **Leon Capeluto**: Residence 1928-1940 at 33 Elizabeth Street, Asheville, NC. Occupation: 1930 in Asheville.
- **Victoria Capuano**: Residence 1930-1940 at 33 Elizabeth Street, Asheville, NC. After 1940: Tampa, FL.
- Children born in Asheville: Selma (1926), Anita (1931), Nace (1933)
- Later children: Vida (1945, NYC), Betty (1950, Miami)

So Leon's Restaurant was in Asheville. The family moved to Tampa after 1940. The collection name reflects where Nace (born 1933 in Asheville) ended up, not where the photos were taken.

### Correct Mental Model
- **Collection name** = where photos were FOUND/STORED (provenance of the collection)
- **Collection name != photo location** — family photos travel with the family
- A "Tampa Collection" can contain photos from Rhodes, Asheville, NYC, Miami, etc.
- Collection name tells you about the collector, not the content

### Required Fix
1. Change the Photo Metadata Context prompt to treat collection as WEAK provenance context
2. Explicitly tell Gemini: "Collection name indicates who had these photos, NOT where they were taken"
3. Ensure visual evidence + GEDCOM residence data outweigh collection name
4. Create eval test: Leon's Restaurant photo should return Asheville, not Tampa
5. Create additional eval cases to prevent over-correction (e.g., a photo that IS in Tampa shouldn't be pushed away from Tampa just because we downweighted collection)

### Eval Strategy
- **Positive case**: Leon's Restaurant → Asheville (visual "LEON'S RESTAURANT" + GEDCOM Leon lived in Asheville)
- **Negative case**: Any Tampa photo where visual evidence also says Tampa → should still say Tampa
- Test that the prompt change doesn't regress other photos

---

## Other Gaps to Address

### 1. Wire Notification Triggers
`create_identity_confirmed_notification()` in notification_routes.py needs to be called from:
- `save_registry()` in app/main.py when identity state changes to CONFIRMED
- Need to resolve the placeholder user_id — use the actual uploader or admin who triggered the action

### 2. Run Seed Scripts
- `scripts/seed_life_events.py` — creates 6 historical Rhodes community events
- Verify /events page shows them after table creation

### 3. AD Entries
AD-206, AD-207, AD-208 were promised but never written to ALGORITHMIC_DECISIONS.md.

### 4. Railway Env Vars
- SENTRY_DSN — user needs to create Sentry project, but we should document what's needed
- POSTHOG_API_KEY — same

### 5. Browser Verification
Session 91 browser verification was superficial ("page loads"). Need to verify:
- /notifications: bell icon shows count after creating a test notification
- /events: page shows events after table creation + seeding
- Notifications actually created when identity is confirmed
