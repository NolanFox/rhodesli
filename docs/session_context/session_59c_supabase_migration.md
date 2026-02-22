# Session 59C: Supabase Migration — User Data Safety

## Strategic Rationale
See AD-135, DATA-001 in docs/ISSUES_LOG.md. This is the #1 operational risk
in the project. 5 data loss incidents documented, hours of manual re-entry
lost each time. The triple safety gate (AD-134) is a band-aid.

## What Moves to Supabase
- Identity confirmations (state, confirmed_by, confirmed_at)
- Identity name assignments (name, assigned_by)
- Merges (merge_from, merge_to, decided_by, decided_at)
- Annotations (text, author, approved, approved_by)
- GEDCOM match decisions (gedcom_id, identity_id, decision)
- Birth year corrections (identity_id, corrected_year, source)
- Match responses (person_a, person_b, response, responder)

## What Stays in JSON + Git
- photo_index.json (ML-generated metadata)
- embeddings.npy (ML artifact)
- Base identity proposals (ML-generated, pre-confirmation)
- Face crop coordinates and paths

## Supabase Project
- ID: fvynibivlphxwfowzkjl
- Current tables: auth only (see docs/SUPABASE_AUDIT.md)
- Keepalive: needs robust mechanism (pauses after 7 days inactivity)
- Auth: Google OAuth + email/password, configured and working
- Existing schema design: docs/design/FUTURE_COMMUNITY.md

## Migration Strategy
1. Create Supabase tables matching schemas above
2. Write one-time migration: JSON → Supabase
3. Verify counts match (critical — no data loss in migration)
4. Update app write paths: user actions → Supabase
5. Update app read paths: Supabase → render (with JSON fallback)
6. JSON becomes a read cache, rebuilt periodically
7. Remove user-data files from Docker bundle entirely
8. init_railway_volume.py no longer touches user data

## Acceptance Criteria
- All user data in Supabase tables
- App reads/writes user data from Supabase
- Deploy does NOT touch user data
- JSON fallback works if Supabase is temporarily down
- All existing tests pass
- New tests verify Supabase persistence

## Risks
- Supabase pausing (keepalive must be robust)
- Network latency (JSON cache for reads)
- Migration data integrity (count verification)

## Breadcrumbs
AD-134, AD-135, DATA-001, Lessons 43/56/69/78/85,
docs/design/FUTURE_COMMUNITY.md, BACKLOG BE-040-042
