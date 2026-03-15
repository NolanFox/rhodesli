# FB-171: Face Tagging Broken for Locally-Ingested Photos (Session 104)

**Reporter:** Nolan + Claude Benatar (via Messenger)
**Severity:** P0 — Core identification workflow broken
**Date:** 2026-03-15

## What's Broken

1. **Face tagging doesn't work** — Claude Benatar cannot click a face on the photo page to name/identify a person. The face cards show "Unidentified" with no mechanism to assign a name. This is THE core feature of the app.

2. **Compare result page only shows one photo** — `/compare/result/9e8ab9f4381c` shows both face crops but only the source photo (Congo group), not the target photo (family group). Inconsistent with other UX patterns.

3. **UX inconsistency** — The way photos and face crops are displayed in compare results doesn't match how they're displayed elsewhere in the app. Should use shared components.

4. **No interaction logging** — No way to know how often users interact with compare results, face cards, photo pages. Need PostHog events.

## Root Cause Analysis

The face tagging broke because:
1. Photos were ingested LOCALLY via `core.ingest_inbox` (CLI)
2. Local ingest creates identities in `data/identities.json` only
3. Production reads from Supabase (DATA_SOURCE=postgres)
4. The identity records for these 20 faces DON'T EXIST in Supabase
5. Without Supabase identity records, the photo page renders face cards as orphans with no identity link → no rename/confirm/dismiss actions available

**This is the ingest→Supabase sync gap.** Every previous ingest was done before the Postgres migration (Session 93). Since then, all new photos have been ingested locally but the local ingest pipeline was never updated to write to Supabase.

## Chain of Related Issues
- Lesson 78: Production-local data divergence (#1 recurring failure)
- Lesson 85: Deploy data safety gate (5th occurrence)
- Lesson 133: Supabase fallback masks connection failures
- Lesson 141: Never git-add production-origin data files
- **NEW: Lesson 142**: Local ingest must write to Supabase when credentials available

## Nolan's Feedback (verbatim)
- "DID You fix face tagging? [...] the fact that you can't get it working is horrible"
- "Do not stop until its fixed. No shortcuts. No regressions."
- "If I were Claude I'd give up and think the app is unusable"
- "I may have to stop working on the project at this pace"
- "Get this done the right way. Do all the planning you need. Follow the harness."
- Compare result: "you are only able to view one of the photos not both photos"
- UX: "inconsistent with how we switch between photos and face crops elsewhere"
- "we should also have logging to know how often users interact with these components"
- Claude Benatar: "I can't identify Robert Mattatia!"
- Claude Benatar: "In this picture we have Congolese men... I don't see the purpose of having them to be identified. It's adding people to your database that we know have no interest here"

## Fix Required
1. Sync all 20 new identities + photo_faces to Supabase so face tagging works
2. Update local ingest pipeline to write to Supabase
3. Verify face tagging works end-to-end on production (browser verified)
4. Fix compare result page to show both photos
5. Add prevention test: no ingest without Supabase sync
