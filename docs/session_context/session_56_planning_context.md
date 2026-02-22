# Session 56 Planning Context — Landing Page Refresh + P1 UX Polish

## Strategic Context

### Goal: Make Rhodesli Shareable
Session 55/55b delivered the ML portfolio piece (similarity calibration). Session 56 is the adoption counterpart: make the app something you're not embarrassed to share when someone asks "what are you building?"

The test: send rhodesli.nolanandrewfox.com to a friend or interviewer. Do they:
1. Immediately understand what this is? (Landing page)
2. Have a clear path to explore? (Entry points)
3. Hit rough edges within 30 seconds? (P1 bugs)

### What's IN SCOPE (Option B1 + B2)

**B1: P1 UX Quick Wins** — Fix the remaining P1 issues that make the app feel unfinished. These are small, high-impact fixes (most <20 min each).

**B2: Landing Page Refresh** — Replace the current landing page with a feature showcase using live data. This is the first thing anyone sees when you share the link.

### What's OUT OF SCOPE (tracked for future sessions)

**B3: Face Compare Standalone (PRODUCT-001)** — Separate FastHTML app at subdomain. Estimated: Session 59. Tracked in BACKLOG.md and ROADMAP.md. Breadcrumbs: AD-117, session_54c_planning_context.md Part 2C.

**Admin/Public UX Unification** — The "two different apps" problem (admin sidebar vs. public top nav). This is a multi-session project. Tracked in BACKLOG.md. Design direction adopted: Progressive Admin Enhancement + thin admin toolbar (from Session 46 research).

**Interactive Upload UX Epic (SSE progressive loading)** — 2-3 session investment. Deferred until after product-ready demo. Tracked in BACKLOG.md. Research done in 54F.

**Docker Image Slimming** — Deferred. Doesn't block anything at current scale.

---

## P1 Issues — Quick Wins List

These are from the UX tracker, post-49D/49E fixes. Estimated times are from the original assessment but treat as rough guides.

### Merge & Identity Management
- **UX-037: Merge direction indicator** (~10 min) — When merging two identities, it's not clear which person is being merged INTO which. Add directional arrow or "Keep A, merge B into A" language.
- **UX-038: Silent 200s on merged IDs** (~10 min) — Visiting a merged person's old URL returns 200 with stale data instead of redirecting to the canonical identity. Should 301 redirect.

### Admin Controls
- **UX-039: Admin controls on /person/ page** (~15 min) — Admin actions (edit name, merge, delete) should be available directly on the person page when logged in as admin, not requiring navigation to a separate admin view.

### Name These Faces Polish
- **UX-073: Enter key submit in name input** (~5 min) — Pressing Enter in the name input should submit the selection, not require clicking a button.
- **UX-074: "Create New" at top of dropdown** (~5 min) — When typing a name that doesn't match existing identities, "Create [typed name]" should be the first option in the dropdown, not buried at the bottom.
- **UX-075: Skip button in sequential mode** (~10 min) — When naming faces sequentially, should be able to skip an unrecognized face and move to the next one.

### Loading & Feedback
- **UX-045: Loading indicator for compare results** (~10 min) — After uploading a photo to /compare, show a spinner while ML processes.
- **UX-046: Loading indicator for estimate results** (~10 min) — Same for /estimate.
- **UX-054: Auto-scroll to results after upload** (~5 min) — After comparison/estimation completes, scroll to the results section.
- **UX-055: Auto-scroll to results after estimate** (~5 min) — Same pattern.

### Estimate Upload UX
- **UX-053: Photo preview before upload** (~10 min) — Show the selected photo immediately after file selection, before uploading. Uses JavaScript FileReader.
- **UX-056: CTAs in estimate results** (~10 min) — After getting date estimation results, show clear next actions: "Estimate Another Photo", "Browse Archive", "Upload to Archive".

### Lazy Loading (Blocks Scale)
- **UX-007: Timeline lazy loading** — /timeline loads all photos upfront. Needs pagination/infinite scroll to scale past 500 photos.
- **UX-018: Photos page lazy loading** — Same for /photos.

### Activity Feed
- **UX-008: Activity feed enrichment** — Current activity feed (if it exists) shows minimal info. Should show recent identifications, new photos added, community activity.

---

## Landing Page Design Direction

### Adopted approach: Feature Showcase with Live Data

From research (Sessions 18, 46, and UX conversations):

**Structure:**
```
[Hero Section]
- Headline: "Preserving the Heritage of the Jewish Community of Rhodes"
- Subtitle: Live stats → "X photographs · Y identified people · Z family connections"
- Primary CTA: "Explore the Archive →"
- Background: Compelling historical photo or subtle collage

[Feature Cards — 2x3 grid]
1. 📸 Browse Photos — "X photos from 9 decades"
2. 👥 People — "Y confirmed identities"
3. 🗺️ Map — "See where photos were taken"
4. 📅 Timeline — "Watch the story unfold"
5. 🌳 Family Tree — "Interactive genealogy"
6. 🔍 Compare — "Upload a photo, find matching faces"

[Community Progress]
- "X faces still need identification — can you help?"
- Progress bar showing identified vs. total
- "Help Identify" CTA

[How It Works]
- 3-step: Upload → AI matches faces → Community confirms
- Brief explanation of ML-powered identification

[Footer]
- About, version, project links
```

**Key principles:**
- All numbers are LIVE (pulled from data at render time, never hardcoded)
- Mobile-first (works at 375px viewport)
- Public view only (no admin chrome)
- Loads fast (no heavy images above the fold)
- Every section has a clear CTA leading deeper into the app

**Anti-patterns to avoid:**
- Static screenshots (go stale)
- Hardcoded numbers (become wrong)
- Admin UI leaking through
- Heavy hero images that slow loading
- Generic "Welcome to our app" language

---

## Items Deferred to Future Sessions (Record of Everything)

| Item | Target Session | Tracked In | Source |
|------|---------------|------------|--------|
| Face Compare Standalone Tier 1 (PRODUCT-001) | 59 | BACKLOG, ROADMAP | AD-117, 54c planning |
| Face Compare Tiers 2-3 | 60+ | BACKLOG | 54c planning |
| Admin/Public UX Unification | 62 | BACKLOG | Sessions 18, 46 |
| Three-mode cognitive framing | 62+ | BACKLOG | Expert review |
| Interactive Upload UX (SSE) | 61 | BACKLOG | 54F research |
| Docker Image Slimming | 63+ | BACKLOG, ROADMAP | Session 56 planned |
| PostgreSQL Migration | 63+ | BACKLOG | Scale planning |
| CI/CD Pipeline | 63+ | BACKLOG | Infrastructure |
| NL Query System (LangChain) | 60+ | BACKLOG | 54c research |
| "Six Degrees" Connection Finder | 60+ | BACKLOG | Options doc |
| Geographic Migration Analysis | 60+ | BACKLOG | Options doc |
| Multi-photo compare upload | 60+ | BACKLOG | 54D feedback |
| Nancy Gormezano beta testing | — | BACKLOG | 49C community |
| DNA matching integration | — | BACKLOG | Leo Di Leyo |
| Institutional partnerships | — | BACKLOG | Data acquisition |

---

## Harness Reminders

- Save prompt to disk, create checkpoint, install compact hooks
- PRD for landing page (Phase 2 is a design+build, worth a lightweight PRD)
- Both test suites: `pytest tests/ -x -q` AND `pytest rhodesli_ml/tests/ -x -q`
- Deploy via git push, verify with `railway logs --tail 50`
- Browser verification via Claude Chrome extension (Playwright fallback)
- **When reviewing screenshots from Claude Chrome: actively look for UX problems, not just "does it render."** Check for: visual hierarchy, mobile responsiveness, loading states, error states, dead-end pages, confusing navigation, inconsistent styling.
- No doc over 300 lines, CLAUDE.md under 80 lines
- Commit per phase, update checkpoint after each
