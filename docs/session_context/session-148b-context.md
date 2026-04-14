# Session 148b Context — Overnight Implementation Sprint

## Predecessor
- Session 148: Interactive Fader Collection Fox Search + P0 auto-rejection fix
- Session 147: PRD-059 Phase 4 (identity inference signals, evidence panel, accept/reject)

## What 148 accomplished
- P0 fix: Person 82863849 restored, auto-rejection hardened (only INBOX), audit logging added
- Memory system hardened: 6 lost files recovered, git backup, protection rule
- Lessons 168-170 added
- Fader identification started: Sherry Ann Fader + Ira Josowitz confirmed in 18-person group photo
- 3 new issues logged: FB-002 (no Fader date labels), FB-003 (embedding sync gap), FB-004 (no cross-collection search)

## What 148b should accomplish
Overnight sprint on backlog items. User explicitly said: "Do not give up. Do not defer."

### Priority 1: Session 147 deferred items
- Browser verify evidence panel on production (Chrome plugin, admin logged in)
- Rejected list UX: restore buttons in dismissed section cards (~15 min)

### Priority 2: Fader collection enablement
- Run Gemini batch date estimation on all 147 Fader photos (FB-002)
- This directly enables the Fader identification work resuming in 148c

### Priority 3: REFACTOR-001 Phase 4
- main.py still at 8,930 lines — extract photo routes to app/photo_routes.py
- PRD-056, DD-017 exist. Follow pattern from Phases 1-3 (components, cards, nav).

### Priority 4: Upload pipeline audit (UPLOAD-003)
- 6th regression. End-to-end audit of upload → staging → R2 → Postgres → photo page
- Fix the specific bugs: 404 after approval, anonymous attribution, missing thumbnails

### Priority 5: FB-003/010 Merge auto-confirm (PRD-058)
- Merge should auto-confirm + advance to next person in focus mode
- PRD-058 written in Session 141

### New ideas from 148
- TOOLS-007: "Search for [Person] in [Collection]" admin tool — the core missing UX for cross-collection work. Generalize scripts/sherry_search.py into an admin endpoint.
- Fader date estimation is prerequisite for temporal bracketing identification strategy
- The sherry_search.py pattern (centroid → ranked distances) should be a reusable admin API

## Key constraints
- Browser automation is READ-ONLY on production (Lesson 149)
- Gemini batch MUST write to Supabase (Lesson 162), not just local JSON
- Gemini batch MUST verify logging on first call (Lesson 160)
- Gemini batch MUST include face bounding box coordinates (memory: feedback_gemini_face_coordinates.md)
- main.py refactoring must not break any routes — test before and after
- All work needs tests (happy path + failure + regression)

## Files to read
- `docs/prds/056_main_py_refactoring.md` — REFACTOR-001 plan
- `docs/prds/058_merge_auto_confirm.md` — PRD-058
- `app/admin_routes.py` — upload pipeline
- `app/upload_routes.py` — upload routes
- `rhodesli_ml/batch_gemini.py` — batch estimation script pattern
