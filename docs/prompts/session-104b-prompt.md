# Session 104b — Fix Face Tagging (P0 BLOCKER)

**CRITICAL:** Face tagging is broken on production for the Robert Mattatia photos. Claude Benatar (real contributor) cannot identify/name people in the photos. This is THE core feature of the app.

## What's Already Done (Session 104)
- 3 upload pipeline bugs fixed (404, attribution, thumbnails)
- Robert Mattatia photos ingested (2 photos, 20 faces)
- Photos live on production: `/photo/fd745112ad8e4ba2` (Congo), `/photo/2777b7e985c8321f` (Family)
- Gemini deep comparison: 8.5-9/10 confidence same person
- Shareable link: `/compare/result/9e8ab9f4381c`
- Identities synced to Supabase (3433) and JSON (with history key fixed)
- Robert Mattatia identities renamed in both Supabase AND JSON
- New API endpoint: `/api/compare/create-result`

## What's BROKEN (P0)
1. **Face cards on photo page show "Unidentified" with NO name, NO link to person page, NO admin actions**
   - The identities ARE in the JSON file (verified: 3433 including 1922 non-merged)
   - The names ARE set ("Robert Mattatia" for 2 faces)
   - But the photo page still shows "Unidentified" for all faces
   - The face cards are NOT clickable/nameable — no rename or confirm mechanism visible
   - Production supabase status: "skipped" (reads from JSON, not Postgres)
   - Hypothesis: registry cache stale, OR face_id lookup path broken for inbox_ faces

2. **Compare result page only shows one photo** — should show both

## Immediate Fix Tasks

### Phase 1: Diagnose face card rendering
1. Read `app/page_routes.py` photo detail route (~line 3552)
2. Trace face card rendering — how does it find identities for faces?
3. Check `get_identity_for_face(registry, face_id)` on production via JS console
4. Test: does the registry on production contain the Robert Mattatia identities?

### Phase 2: Fix face tagging
1. Fix whatever prevents identity→face link from rendering
2. Verify clicking face card works (opens person page or shows rename actions)
3. Both admin AND contributor paths must work

### Phase 3: Verify + prevent
1. Browser verify both photo pages
2. Add regression test
3. Add Lesson 142

### Phase 4: Claude Benatar UX items
1. Compare result shows both photos
2. Dismiss mechanism for irrelevant faces
3. Interaction logging

## Key Files
- `app/page_routes.py` — photo detail, face cards
- `app/main.py` — `load_registry()`, `get_identity_for_face()`, `_build_caches()`
- `core/registry.py` — `IdentityRegistry.load()`, `list_identities()`
- `docs/user_feedback/FB-171_face_tagging_broken_session104.md`

## Nolan's Directive
"Do not stop until its fixed. No shortcuts. No regressions."
