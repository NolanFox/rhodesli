# Session 51: Quick-Identify from Photo View

## Session Identity
- **Previous session:** Session 50 (estimate overhaul, Gemini upgrade, v0.50.0)
- **Goal:** Add inline face identification from the photo view page —
  click any "Unknown" face, type a name, done. No page navigation.
- **Time budget:** ~35 min
- **Priority:** HIGHEST — this is the #1 community-driven feature.
  Carey Franco identified 8 people in one Facebook comment; entering
  those names currently requires navigating to each face's identify
  page individually. This feature makes that a 2-minute task.

## CONTEXT

### Why This Feature Matters

During Rhodesli's first community sharing on Facebook (Feb 18-19):
- Carey Franco posted: "Top left is Albert and Eleanore Cohen.
  Morris and Ray Franco my aunt and Uncle. Molly and Herman Benson
  my aunt and uncle. Right is my mother and father Belle and
  Isaac Franco" — 8 identifications in ONE comment
- Howie Franco identified his father Isaac Franco and uncle Morris
- Stu Nadel confirmed a face match

Entering Carey's 8 names currently requires:
1. Go to photo page
2. Click first Unknown face → navigates to /identify/{id}
3. Search for or create an identity name
4. Navigate back to photo
5. Repeat 7 more times

With Quick-Identify:
1. Go to photo page
2. Click first Unknown face → inline name input appears ON the photo
3. Type "Albert Cohen" → autocomplete → confirm
4. Input moves to next face or click another → repeat
5. All 8 names entered without leaving the page

### Architecture Decision
Quick-Identify is admin-only for now. Community members will use
the existing /identify/{id} page and suggestion flow (annotation
engine from Phase C). This keeps the scope manageable and avoids
building a second approval flow.

## KEY PHASES

### Phase 0: Orient
### Phase 1: PRD-021 Quick-Identify
### Phase 2: Inline Name Input Component
### Phase 3: Autocomplete with Existing Identities
### Phase 4: Submit Flow (create/merge identity)
### Phase 5: Multi-face "Name These Faces" mode
### Phase 6: Verification gate
### Phase 7: ROADMAP + BACKLOG + changelog

## CRITICAL CONSTRAINTS
- DO NOT modify identity data files directly
- DO NOT break the existing identify flow (/identify/{id} must still work)
- DO NOT break confirmed face click behavior (still → /person/{id})
- Admin-only feature (gated behind auth check)
- Use SAME code paths as existing identity management
- HTMX out-of-band swaps for updating overlays + thumbnails
