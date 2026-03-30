# Session 144b Context

**Predecessor**: Session 144 (docs/assessments/session-144-assessment.md)
**Date**: 2026-03-30
**State**: v0.99.55, 3949+ tests, 218/279 Fox photos batch-processed with GEDCOM context

---

## What Session 144 Delivered
- GEDCOM v9 imported: 21,998 individuals, 6,741 families, 107 face links
- Albert's 3 wives linked (Esther, Rose Weiss Baygel Fox, Jean Baumann Kassel Fox)
- AD-234: Spouse timeline, birth date annotation, confirmed identities block
- Geographic data model: multi-candidate location schema + UI rendering
- AD-233: Anchor comparison prompt builder + admin UI button
- Batch: 218/279 Albert+Esther photos processed ($11.99), all with GEDCOM context
- GEDCOM view IS NULL bug FIXED (commit 12c2b90a) — was breaking ALL batch context
- Merge button P0 FIXED (commit fc4f19a1) — 3 bugs, 10 tests
- Person 3772 merged into Albert Fox (199 anchor faces)
- GEDCOM importer --skip-change-log + --prune-old-versions flags
- Batch read-merge-write semantics (preserve human corrections)
- Lessons 163-165 (GEDCOM scale, datetime serialization, view IS NULL)

## What Remains from Session 144

### Must Fix (P0/P1)
- **FB-007 (P1)**: Person page "Sort: Earliest First" broken — photos unsorted despite dropdown
- **0% display bug (P1)**: Family resemblance matches show 0% when calibrator gives 27-32%. Codex found stale/alternate display path.
- **Person 3481 multi-claimed faces**: 3 faces from penny arcade strip claimed by Persons 3481, 3485, 3486 — should all be 3481 only

### Batch Completion
- **61 photos remaining**: 279 total - 218 processed = 61. Budget-limited (~$3.36)
- **2 R2-only photos**: No local file, need download from R2 first
- All results write to Supabase (Lesson 162)

### Geo + Verification
- **Geo dual-write**: New location_primary from batch not written to photo_locations table. Map pins won't update until geocoded.
- **Anchor compare**: Admin UI button built but never browser-verified

## Key Person IDs
- Albert Fox: 85546ebf-75b9-4971-a9d4-b2ce2271bc19 (199 faces)
- Esther Burd Fox: 65207728-9ee6-48c1-be68-a2da23354caf (143 faces)
- Rose Weiss Baygel Fox: 6a1657f4-0df4-4fd4-83ea-860732482421
- Jean Baumann Kassel Fox: 75ceaa7b-0edb-4fcb-8040-6a3a5993fd29
- Person 3481 (unidentified woman): 273ac560-bf13-43f5-8f87-e0f7ec967b2c — most likely Rachel Fox

## Key GEDCOM IDs
- Albert: @I132123840707@ | Esther: @I132126986995@
- Rose: @I132779883868@ | Jean: @I132779883881@
- Rachel Fox: @I132128933061@

## Identity Investigation Findings (Session 144)
- Person 3481: Rachel Fox (55%), Sadie Fox (30%), Esther ruled out (embedding dist 1.34)
- Person 3772: Merged into Albert. Co-occurrence evidence (always with Esther) was decisive.
- Fox family resemblance problem: all siblings equidistant in embedding space (~1.0-1.3)
- Co-occurrence and temporal context beat face recognition for intra-family disambiguation

## User Research: Penny Arcade Photo Strip + Gemini Chat
- Photo 02154 is a penny arcade "sticky-back" strip (3 sequential poses of Albert + unknown woman)
- None of 4 Gemini API runs detected multi-frame format — all described as "6 people"
- Gemini Chat correctly identified it when explicitly asked
- Photo location: likely Coney Island or Bowery penny arcade, NYC, 1910-1915
- 6 feature ideas logged: multi-frame detection, cross-person investigation, recognition failure analysis, investigation notebook, co-occurrence inference, GEDCOM-aided disambiguation

## User Research: Anchor Photo Timeline (Gemini Chat)
- Decoded poster text: "PIONEER MACABEES DETROIT JULY 2X" (Knights of the Maccabees)
- 3-photo chronological ordering established for Albert Fox
- Census-constrained dating: 1910 census (NY) → absence from 1915 census → Detroit window
- Iterative evidence accumulation (census + visual + GEDCOM) dramatically improves estimates

## PRD-059: Temporal Co-Occurrence Analysis (ROADMAP item)
- Phase 1 (batch estimation): 218/279 complete, 61 remaining
- Phase 2 (event grouping): NOT STARTED — cluster photos by date + shared faces
- Phase 3 (co-occurrence matrix): NOT STARTED — frequent companions panel
- Phase 4 (identity inference): NOT STARTED — combine age trajectory + GEDCOM + co-occurrence
- User explicitly wants to start on Phases 2-3 in 144b

## Direct DB Connection
```
SUPABASE_DB_POOLER_HOST=db.fvynibivlphxwfowzkjl.supabase.co
SUPABASE_DB_POOLER_PORT=5432
SUPABASE_DB_USER=postgres
```
