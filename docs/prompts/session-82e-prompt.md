# Session 82e Prompt: UX Feature Sprint

**Goal:** Implement the highest-ROI UX features from the Session 82a ideation + 82e planning research. Ship visible, user-facing improvements that serve the app thesis: Help community members identify people, share what they find, and contribute knowledge.

**Context file:** `docs/session_context/session-82e-context.md` — ranked features, technical notes, parallel strategy, mockup references, conflict zones. READ THIS FIRST.

**Version:** v0.84.0 | ~3928 tests | 274 photos | 775 identities | 60 confirmed

---

## Phase 0: Orient (5 min)

1. Read `CLAUDE.md`, `tasks/lessons.md`, `docs/session_context/session-82e-context.md`
2. Set `.claude/current_session.txt` to `82e`
3. Save this prompt to `docs/prompts/session-82e-prompt.md` (already done)
4. Create session log: `docs/session_logs/session-82e-log.md`
5. Verify: `make test-fast` passes, git status clean, on main branch

---

## Phase 1: Mobile Hamburger Fix (Bug Fix — 15 min)

**Problem:** Mobile header nav overlaps content on Timeline/Compare pages. Navigation is broken on small viewports.

**Spec:**
- All top-level navigation links consolidated into a slide-out hamburger menu below 768px
- Hamburger icon in top-right corner (standard 3-line icon)
- Menu slides in from right, overlays content with dark scrim
- Close on: X button, scrim click, or ESC key
- Links: Home, Photos, People, Timeline, Map, Compare, Estimate (same as desktop nav)
- Admin links (if admin): Upload, Admin, Discoveries
- Test: viewport 375px wide renders hamburger, all links accessible

**Files likely touched:** `app/main.py` (nav rendering function)

**Commit:** `fix: mobile hamburger menu for small viewports`

---

## Phase 2: Masonry Photo Grid (Visual Upgrade — 30 min)

**Problem:** Current grid uses `aspect-square` forcing all photos to identical crops, cutting off heads and losing context from archival photos with varying aspect ratios.

**Spec:**
- Replace square-crop grid on `/photos` with CSS columns masonry layout
- Photo dimensions already cached in `photo_index.json` (width/height fields)
- Each photo renders at its natural aspect ratio
- Target: 3 columns desktop, 2 columns tablet, 1 column mobile
- Hover: photo title + face count overlay (existing behavior, preserve it)
- Lazy loading: preserve existing pagination/lazy-load behavior
- No JS library — pure CSS (`column-count` + `break-inside: avoid`)

**Acceptance criteria:**
- [ ] Portrait and landscape photos coexist without cropping
- [ ] Grid fills without large gaps
- [ ] Mobile responsive (1 column below 640px)
- [ ] Existing click-to-photo-detail navigation preserved
- [ ] Face count badges still visible
- [ ] Performance: no layout shift on lazy-load pages

**Files likely touched:** `app/main.py` (photo grid rendering), possibly `app/static/` CSS

**Commit:** `feat: masonry photo grid preserving aspect ratios`

---

## Phase 3: Help Needed Page + Share for Help (Growth Loop — 45 min)

**Problem:** Visitors can browse but have no clear path to contribute. "Help identify this person" is the highest-engagement action for heritage communities but it's not surfaced.

### 3A: Help Needed Page

**Spec:**
- New route: `/help` (public, no auth required)
- Shows top 50 unidentified faces, sorted by face quality (highest first)
- "Unidentified" = identity state `INBOX` or `PROPOSED` with no confirmed name
- Each card: face crop (large), photo thumbnail, "Do you recognize this person?" CTA
- CTA links to `/identify/{identity_id}` (existing page)
- Add `/help` to main navigation (both desktop and mobile hamburger)
- Empty state: "All faces have been identified! Thank you." (aspirational)

### 3B: Share for Help OG Cards

**Spec:**
- On `/identify/{identity_id}` pages, add Open Graph meta tags:
  - `og:title`: "Help identify this person from the Rhodes Jewish community"
  - `og:description`: "This photo is from [collection]. Can you help us identify who this is?"
  - `og:image`: face crop URL (R2 public URL)
  - `og:url`: canonical URL of the identify page
- Add a "Share" button that copies the URL or opens share dialog (Web Share API with clipboard fallback)
- Test: paste URL into Facebook URL debugger format — OG tags render correctly

### 3C: Landing Page Section

**Spec:**
- Add a "Help Us Identify" section to the landing page (below existing content)
- Show 6 random unidentified high-quality faces in a horizontal scroll
- "See All" links to `/help`
- Keep it lightweight — this section should intrigue, not overwhelm

**Acceptance criteria:**
- [ ] `/help` page renders with face cards, quality badges, and CTAs
- [ ] OG meta tags on identify pages include face crop image
- [ ] Share button works (Web Share API or clipboard fallback)
- [ ] Landing page shows "Help Us Identify" section
- [ ] Mobile optimized for all new pages
- [ ] No auth required for any public-facing piece

**Files likely touched:** `app/main.py` (new route, landing page, OG tags)

**Commit:** `feat: Help Needed page + Share for Help OG cards`

---

## Phase 4: Identify Mode Focus State (CSS Enhancement — 15 min)

**Problem:** On photo detail pages with multiple faces, unidentified faces don't stand out. Users don't know which faces need help.

**Spec:**
- On `/photo/{id}` pages, add an "Identify Mode" toggle button (eye icon or similar)
- When active:
  - Background dims (dark overlay, 60% opacity)
  - Identified faces: normal opacity, subtle green border
  - Unidentified faces: bright border, gentle pulse/glow animation (CSS `@keyframes`)
  - Each unidentified face shows a small "?" badge
- Toggle state: persists via CSS class on container (no localStorage needed)
- Admin view: toggle visible by default. Public view: toggle visible if any faces are unidentified
- Accessible: focus-visible outline on toggle, sufficient contrast on badges

**Acceptance criteria:**
- [ ] Toggle button visible on photo pages with unidentified faces
- [ ] Dim + glow correctly distinguishes identified vs unidentified
- [ ] Pulse animation is gentle (not distracting)
- [ ] Works with existing face overlay toggle (admin ON by default)

**Files likely touched:** `app/main.py` (photo page rendering), inline CSS/JS

**Commit:** `feat: Identify Mode focus state on photo pages`

---

## Phase 5: Tests + Verification (20 min)

1. Write tests for each new feature:
   - Mobile hamburger: test nav renders hamburger at mobile viewport
   - Masonry grid: test photos render with aspect ratio styles
   - Help Needed page: test `/help` returns 200 with face cards
   - OG tags: test identify page includes `og:image` meta tag
   - Identify Mode: test toggle renders on photo pages with unidentified faces
2. Run `make test-fast` — all pass
3. Run full test suite: `source venv/bin/activate && pytest tests/ -x -q && pytest rhodesli_ml/tests/ -x -q`

**Commit:** `test: session 82e feature tests`

---

## Phase 6: Deploy + Browser Verification (15 min)

1. `git push origin main` (triggers Railway deploy)
2. Wait for deploy (check Railway status or health endpoint)
3. Verify in Chrome browser (admin logged in):
   - [ ] `/help` page loads with face cards
   - [ ] Mobile hamburger works (resize to 375px)
   - [ ] Photo grid shows masonry layout (varying heights)
   - [ ] Identify Mode toggle works on a photo page
   - [ ] Share button copies URL
   - [ ] OG tags present (inspect source on identify page)
4. Take screenshots to `docs/screenshots/session-82e/`

---

## Phase 7: Session Docs (10 min)

1. Update `docs/ml/ALGORITHMIC_DECISIONS.md` if any ML-adjacent decisions made
2. Update `CHANGELOG.md` with v0.85.0 entry
3. Update `ROADMAP.md` — check boxes, add to Recently Completed
4. Write `docs/assessments/session-82e-assessment.md` per self-assessment protocol
5. Update `docs/session_logs/session-82e-log.md` with final status

**Commit:** `docs: session 82e — assessment, changelog v0.85.0`

---

## Scope Control

**In scope:** Phases 1-7 above (mobile fix, masonry grid, help page, identify mode, tests, deploy, docs).

**Explicitly out of scope for 82e:**
- Missing Info table (#21) — defer to 82f
- Bulk tag confirmation (#30) — defer to 82f
- Click-to-target boxes (#22) — defer to 82f (needs careful SVG work)
- Relational context labels (#19) — defer to 82f (needs GEDCOM query optimization)
- Design direction codification (DD-006) — defer
- Any ML pipeline changes

**If time permits** (all required phases complete + verified):
- Add "Surprise Me" button to landing page (#3) — simple random photo query
- Add quality badges to face cards on Help Needed page

---

## Parallelization Notes

Phases 1-4 all touch `app/main.py`. Per Lesson 88, monolithic app file changes should be **sequential, not parallel**. Recommended order: Phase 1 → Phase 2 → Phase 3 → Phase 4, with commits after each.

If the session runner wants to parallelize, Phase 5 (tests) can run in a worktree after Phase 4 commits, and Phase 7 (docs) can run in parallel with Phase 6 (deploy verification).

---

## Key References

- Feature research: `docs/session_context/session-82e-context.md`
- 82a ideation list: `docs/assessments/session-82a-ideation.md`
- 82a mockups: `docs/assessments/mockups/` (5 PNGs, directional only)
- 82d assessment: `docs/assessments/session-82d-assessment.md`
- Bug catalog: `docs/session_context/session-82d-archaeology.md`
- Session 82 context: `docs/session_context/session-82-context.md`
