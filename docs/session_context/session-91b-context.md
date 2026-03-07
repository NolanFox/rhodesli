# Session 91b Context: Complete Everything Sessions 90-91 Promised

**Predecessor**: Session 91 (6 parallel worktree tracks — PRD backlog + platform foundation)
**Date**: 2026-03-07
**Origin**: Post-session audit + Nolan feedback found major gaps between claimed and actual completion.

---

## Nolan's Feedback (Verbatim, 2026-03-07)

> "One, you should be able to cover all of the deferred things. Two, I thought there was more that was not covered there. Are the notifications working? Did you test all of this with Claude Chrome? Did we full refactor main.py? Solve the testing issue? Did we fix the discoveries section? Is supabase migration done? RE: supabase, as I've mentioned before and you should never forget, you can just use the supabase MCP or CLI."

> "The main.py refactor has only been half done. This was supposed to be completely finished. Do not defer that any longer."

> "For Discoveries, this was part of the feedback from Claude Benatar along with notifications. Both were supposed to be fixed (discoveries aligning to what it was intended to do and surface recent things first, plus also making sure the distinction between the 3 review sections is upheld, as well as the fact the current UX for discoveries is inconsistent with the rest of the app)."

> "Regarding testing, we have been working for several sessions now on fixing testing so that it didn't slow us down. I believe the refactor of main.py was part of that. I do not believe we ever solved this."

> "Everything currently in the prompt plus everything you are going to add based on this feedback better be done."

From Session 90b context (line 148):
> "We have talked about fixing testing and breaking up main.py A LOT. Finally get it done."

---

## 1. What Session 91 Actually Shipped vs. Claimed

| Feature | Claimed | Reality |
|---------|---------|---------|
| **PRD-028 Notifications** | SHIPPED | UI skeleton only. Supabase tables never created. Event triggers never wired. Bell icon always shows 0. |
| **PRD-011 Life Events** | SHIPPED | Routes exist, tables never created. /events shows 0 events. |
| **PRD-027A R2 Backup** | SHIPPED | Actually works. Scripts exist with tests. |
| **PRD-029 Photo Backs** | SHIPPED | Actually works. Media group API + browse filter. |
| **PRD-027 B/C Postgres Read** | SHIPPED | Code exists. Only tested with mocks, never against real Supabase. |
| **GlobalPersonID** | SHIPPED | SQL files exist. Tables never created. |
| **Observability** | SHIPPED | Packages in requirements.txt. Env vars not set on Railway. |
| **main.py refactor** | "95% done" | Still 26,100 lines with 109 route definitions. Target was ~14-16K. |
| **Discoveries** | "No open issues" | Multiple known bugs from Session 71D audit + Benatar feedback never addressed. |
| **Testing speed** | Not claimed | 57 seconds. Target was <30 seconds. Still unresolved. |

### Root Cause
Session 91 wrote SQL schema files but **never executed them against Supabase**. The Feature Reality Contract was not honestly applied.

---

## 2. main.py Refactor — HALF DONE

### Current State
- **main.py**: 26,100 lines, 109 @rt() route definitions still inside
- **12 extracted route files** exist: admin, auth, browse, compare, estimate, event, match_facecompare, notification, person, photo, sync, upload
- **Target**: ~14-16K lines (utility hub only, all routes extracted)

### What Still Needs Extraction

**Tier 1 — High Priority (enables parallel development, Lesson 88)**:
- `discoveries_routes.py` — `/discoveries`, `/inbox/`, `/api/discovery/*` (~25 routes, ~1,500 lines)
- `identity_routes.py` — All identity POST operations: merge, reject, rename, metadata, notes, bulk ops (~30 routes, ~2,500 lines)

**Tier 2 — Medium Priority**:
- `engagement_routes.py` — Contributions, activity, proposals, annotations (~15 routes, ~1,000 lines)
- `relationship_routes.py` — GEDCOM linking, relationships, gedcom search (~8 routes, ~400 lines)

**Tier 3 — Core Pages**:
- `page_routes.py` — Landing, about, help, collections, photos, people, map, timeline, tree, connect (~15 routes, ~3,000+ lines)

**Total remaining extraction: ~8,400-11,000 lines → main.py drops to ~15-17K**

### Why It Matters
- **Lesson 88**: "Monolithic app files prevent parallel worktree execution"
- **Testing**: Every test importing from app.main triggers full 26K-line module load
- **Development velocity**: Merge conflicts on monolith block parallel tracks

---

## 3. Discoveries — Multiple Known Bugs

### Claude Benatar Feedback (Growth Loop Blocker)
Benatar asked: "If someone uploads a picture, how does he or she know if there's a match?" This led to PRD-028 (notifications) AND discoveries improvements.

Nolan's requirement: "when you log in and click discoveries, it would surface whatever the latest changes are first"

### Session 71D Audit Findings (STILL OPEN)

**Bug 1: No Navigation** (P1)
- Cannot click source face → person page
- Cannot click source photo → photo page
- Dead-end page — violates bidirectional navigation principle

**Bug 2: Misleading Confidence %** (P2)
- Distance 0.91 (HIGH confidence) displays as "54% match"
- Formula `(1 - distance/2.0) * 100` is counterintuitive
- Should use confidence tier labels: Strong/Good/Possible/Weak (AD-173)

**Bug 3: Wrong Sort Order** (P1)
- Currently sorts by confidence_pct descending
- Should sort by **recency (newest first)** per Nolan's feedback
- Discoveries should be a "what just happened" feed, not a confidence leaderboard

**Bug 4: UX Inconsistent with Rest of App** (P2)
- Doesn't use unified `identity_card` component (DD-006)
- No share buttons (unlike every other page)
- No co-occurrence context (unlike person page)
- Cards look different from browse/person/compare pages

**Bug 5: Three-Section Distinction Unclear** (P2)
- Discoveries vs New Matches vs Help Identify all look too similar
- User can't tell WHY a face is in one section vs another
- Each section needs clear visual distinction and purpose statement

### Current Code Locations
- Main discoveries route: `app/main.py` lines 22882-23090
- Compute discoveries: `app/main.py` lines 5828-5947
- API endpoint: `app/main.py` lines 23095-23269
- Discovery card builder: `app/main.py` ~23400+

---

## 4. Testing Speed — 57s, Target <30s

### Current State
- `make test-fast`: 57.23 seconds wall clock, 3573 tests, parallel via xdist
- Collection time: 3.6s (acceptable)
- Execution: ~54s across workers

### Root Causes
1. Every test importing from `app.main` triggers full 26K-line module load
2. TestClient creation loads the full FastHTML app
3. `conftest.py` line 107: `from app.main import app` loads everything
4. No lazy imports — expensive modules (InsightFace, Gemini) load at import time

### Solutions
1. **Complete main.py extraction** — route files import only what they need
2. **Session-scoped TestClient fixture** — reuse across tests instead of per-test
3. **Lazy imports for heavy modules** — defer InsightFace/Gemini until route handler runs
4. **conftest optimization** — mock expensive imports at conftest level, not per-test

---

## 5. Victor Capeluto / Collection Name Overindexing (AD-209)

### Problem
Photo 3192877a90a174e9 shows Victor and Victoria Capeluto in front of "LEON'S RESTAURANT." AD-204 from Session 90c added collection name as a STRONG location signal, causing Gemini to say "Tampa" instead of "Asheville."

### GEDCOM Ground Truth
- **Leon Capeluto**: Residence 1928-1940 at 33 Elizabeth Street, Asheville, NC. Occupation 1930 in Asheville.
- **Victoria Capuano**: Residence 1930-1940 at 33 Elizabeth St, Asheville, NC. After 1940: Tampa, FL.
- Children born in Asheville: Selma (1926), Anita (1931), Nace (1933)
- Collection named "Nace Capeluto Tampa Collection" because Nace ended up in Tampa — NOT because photos were taken there.

### Correct Mental Model
- Collection name = where photos were FOUND/STORED (provenance)
- Collection name != photo location — family photos travel with the family
- Visual evidence + GEDCOM residence data >> collection name

### Fix
1. Rewrite Photo Metadata Context prompt: collection = WEAK provenance, not location signal
2. Eval tests: Leon's Restaurant → Asheville (not Tampa). Tampa photos → still Tampa.
3. Re-analyze photo 3192877a90a174e9

---

## 6. Supabase Access

Connection details in .env:
- `SUPABASE_URL=https://fvynibivlphxwfowzkjl.supabase.co`
- `DATABASE_URL=postgresql://postgres:...@db.fvynibivlphxwfowzkjl.supabase.co:5432/postgres`
- `SUPABASE_SERVICE_ROLE_KEY` available
- Supabase MCP or CLI can execute SQL directly

SQL files to execute (in order):
1. `scripts/sql/create_communities.sql`
2. `scripts/sql/seed_rhodes_community.sql`
3. `scripts/sql/create_global_person_links.sql`
4. `scripts/sql/create_life_events.sql`
5. `scripts/sql/007_notifications.sql`
6. `scripts/sql/alter_photos_media_group.sql`

---

## 7. Parallelization Plan

### Track Layout

| Track | Branch | Scope | Files Touched |
|-------|--------|-------|---------------|
| A | `session-91b/supabase-notify` | Supabase migrations + notification wiring | notification_routes.py, main.py (save_registry only), scripts/sql/ |
| B | `session-91b/main-refactor` | Extract identity_routes, engagement_routes, relationship_routes, page_routes | app/main.py (extraction), NEW route files |
| C | `session-91b/discoveries` | Extract discoveries_routes + UX overhaul | app/main.py (extraction), NEW discoveries_routes.py |
| D | `session-91b/collection-fix` | AD-209 collection name prompt fix + evals | rhodesli_ml/gemini_extraction.py, NEW test file |
| E | `session-91b/test-speed` | Test speed optimization | tests/conftest.py, pytest config |

### File Conflict Analysis
- **Track B and C** both extract from main.py — **MUST be sequential** (B first, then C)
- **Track A** touches main.py (save_registry) — merge AFTER B+C
- **Track D** touches only rhodesli_ml/ — fully independent
- **Track E** touches only tests/ — fully independent

### Merge Order: D → E → B → C → A

### Parallel Groups
- **Group 1** (parallel): D + E + B (D and E are independent; B starts immediately)
- **Group 2** (after B merges): C (needs B's extraction to be in main)
- **Group 3** (after C merges): A (wires into refactored main.py)
