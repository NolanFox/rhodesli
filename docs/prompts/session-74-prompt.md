# Session 74: Rhodesli UX Overhaul — Antigravity Multi-Agent Execution

## Session Identity
- **Number:** 74
- **Tool:** Google Antigravity (Gemini 3.1 Pro)
- **Mode:** Plan Mode for all agents
- **Parallelization:** 5 concurrent agents on git worktrees
- **Previous session:** 73 (Claude Code)

---

## GLOBAL INSTRUCTIONS (paste into EACH agent conversation)

Before starting work, read these files to understand the full project:

```
Read CLAUDE.md
Read docs/VISION.md
Read docs/ml/ALGORITHMIC_DECISIONS.md (scan for patterns)
Read docs/HARNESS_DECISIONS.md
Read ROADMAP.md
Read BACKLOG.md
Read tasks/lessons.md (scan for recurring issues)
Read main.py (understand the FastHTML app structure)
Read all files in templates/ (understand every page)
Read all files in static/css/ (understand the design system)
Read all files in static/js/ (understand client-side behavior)
```

**Harness rules (non-negotiable):**
- Run `pytest tests/ -x -q` before AND after ALL changes
- Use conventional commits: `feat:`, `fix:`, `docs:`, etc.
- Update ALGORITHMIC_DECISIONS.md for any ML/algorithm change
- Update HARNESS_DECISIONS.md for any workflow change
- No file >300 lines in docs/
- Take browser screenshots before AND after every UX change
- Record browser video for complex interaction changes

**This is a heritage preservation project.** The aesthetic should be
warm, respectful, modern, and photo-forward. Think museum quality
meets modern web — not generic SaaS.

---

# ═══════════════════════════════════════════
# AGENT 1: FACE CARD REDESIGN
# Worktree: rhodesli-face-cards
# Branch: session-74-face-cards
# ═══════════════════════════════════════════

## Mission

The face card component used throughout the app (New Matches inbox,
person pages, Help Identify) looks terrible. It has massive blank
space, no visual density, and looks like a 2010-era web app.

## Research Phase (use the browser to study these)

Navigate to each of these in the browser and take notes:
1. **Apple Photos** face identification UI — dense, clean, image-forward
2. **Google Photos** face grouping suggestions — minimal chrome, big faces
3. **Lightroom** face tagging — efficient grid, quick accept/reject
4. **Pinterest** card layout — masonry grid, elegant hover states
5. **Dribbble** search for "photo identification UI" or "face tagging interface"

Take screenshots of the best examples you find.

## Current State Analysis

1. Navigate to `rhodesli.nolanandrewfox.com/?section=to_review&view=browse`
2. Screenshot the current face card layout (desktop AND mobile)
3. Identify every pixel of wasted space
4. Document exactly what CSS classes and templates control the cards

## Implementation

Design and build a new face card component that:

### Desktop (>768px)
- **Grid layout:** 3-4 cards per row, tight spacing (8-12px gaps)
- **Card anatomy:** Large face crop (60-70% of card), name/cluster below,
  action buttons as a compact row or hover overlay
- **Visual hierarchy:** Face is dominant. Metadata is secondary.
- **Quality badge:** Small, unobtrusive (corner pip, not a banner)
- **Actions:** Confirm ✓ / Skip ⏸ / Reject ✗ as icon buttons
  (not large text buttons that waste half the card)
- **INBOX badge:** Tiny tag, not a huge colored label

### Mobile (<768px)
- **2 columns** of face cards (not 1 giant card per screen)
- **Swipe gestures** if possible (swipe right = confirm, left = reject)
  OR at minimum compact tap targets
- **Bottom sheet** for details instead of inline expansion
- **Face crop fills most of the card** — no wasted space

### Interaction Polish
- Smooth transitions when confirming/rejecting (card slides out)
- Loading skeleton states
- Keyboard shortcuts for power users (j/k navigate, y confirm, n reject)
- Batch mode option: "Confirm all in this cluster"

## Verification

After implementation:
1. Start dev server, open browser
2. Navigate to the new matches page
3. Screenshot desktop at 1440px, 1024px, 768px, 375px widths
4. Verify the grid is dense, faces are prominent, actions are accessible
5. Test confirm/reject flow — does the card animate out smoothly?
6. Compare your screenshots to the current state screenshots
7. Create an Artifact walkthrough showing before vs. after

## Files to Modify
- `templates/` — card components
- `static/css/` — card styles, responsive breakpoints
- `static/js/` — card interactions, swipe handling
- `main.py` — any route changes needed

Commit: `feat(ux): session 74 — redesigned face cards for density and modern aesthetic`

---

# ═══════════════════════════════════════════
# AGENT 2: GEDCOM LINKING + PAGINATION FIX
# Worktree: rhodesli-gedcom-fix
# Branch: session-74-gedcom
# ═══════════════════════════════════════════

## Mission

GEDCOM linking is broken in two ways: (1) the real family tree GEDCOM
is not fully imported, and (2) the linking UI has no pagination.

## Step 1: Verify GEDCOM Import

The GEDCOM file at `~/Downloads/gedcom_20260224/Fox_Capeluto_Fogel_Waldorf Family Tree.ged`
must be fully parsed and imported. Check:

```bash
# Count individuals in the GEDCOM file
grep -c "^0.*INDI" ~/Downloads/gedcom_20260224/Fox_Capeluto_Fogel_Waldorf\ Family\ Tree.ged

# Compare to what's in the system
python -c "import json; d=json.load(open('data/gedcom_data.json')); print(f'Individuals in system: {len(d.get(\"individuals\", []))}')"
```

If the counts don't match, re-import the GEDCOM. Key verification:
these people MUST exist with correct data:
- Rachele (Rachel) AMATO — b. 20 Jul 1907 Rhodes, Turkey — d. 31 Oct 2002 Sea Point, South Africa
- Netanel Menashe — b. 1898 — d. 1983
- Salomon Menashe — b. 1936 — d. 2019
- Isaac AMATO — b. 1866 — d. 1920
- Rica Sharhon — b. 1870 — d. 1963

## Step 2: Fix the Linking UI

The current "Link to Family Tree" interface on person pages:
- Shows 4 matches then "Show 15 more (73 remaining)"
- User must click repeatedly to find the right person
- NO search, NO pagination, NO filtering

Replace with:
1. **Search-first:** Text input that filters matches in real-time as you type
2. **Pagination:** Show 10 per page with prev/next and page numbers
3. **Better ranking:** Prioritize by name similarity + date overlap
4. **Quick preview:** Show key dates and places inline so you can identify
   the right person without clicking into each one
5. **Fuzzy matching:** "Natenel" should match "Netanel", "Rachel" should
   match "Rachele"

## Step 3: Verify Linked Data Flows to Tree

After linking Netanel Menashe to his GEDCOM record:
1. Navigate to his person page → Family Tree Link section
2. Verify it shows "Linked to Family Tree: Netanel Menashe (b. 1898 — d. 1983)"
3. Navigate to /tree?person={his-id}
4. Verify his family connections appear (wife Rachel Amato, son Solomon, etc.)
5. Screenshot all of this

## Verification
- Open browser, go to person page for someone unlinked
- Test the new linking UI: search, paginate, link
- Verify the link persists and shows correctly
- Test on mobile too

Commit: `fix(gedcom): session 74 — GEDCOM re-import, linking pagination and search`

---

# ═══════════════════════════════════════════
# AGENT 3: FAMILY TREE VISUALIZATION OVERHAUL
# Worktree: rhodesli-tree-viz
# Branch: session-74-tree
# ═══════════════════════════════════════════

## Mission

The family tree visualization is completely broken. Trees don't connect
even when relationships exist in the GEDCOM. The rendering is ugly.

## Research Phase (use the browser)

Visit these sites and study their tree implementations:
1. **Ancestry.com** — note the layout, interaction patterns, node design
2. **MyHeritage.com** — note the different view options (family, pedigree)
3. **FamilySearch.org/tree** — note how they handle massive trees
4. Search Dribbble/Behance for "family tree visualization design"
5. Look at the `family-chart` library by donatso on GitHub

Screenshot the best designs you find. Create a research Artifact
comparing approaches.

## Current State Analysis

1. Navigate to rhodesli.nolanandrewfox.com/tree
2. Screenshot — note the disconnected nodes
3. Navigate to /tree?person={netanel-menashe-id}
4. Screenshot — note only a single isolated node appears
5. Read data/relationships.json and data/gedcom_data.json
6. Understand WHY the tree isn't connecting (data issue vs rendering issue?)

## Design Goals

The new tree should:

### Visual Design
- **Warm, archival aesthetic** — not clinical/corporate
- Sepia-tinted photo circles on nodes (where photos exist)
- Placeholder silhouettes for people without photos
- Subtle connecting lines (not harsh black — try warm gray or gold)
- Date ranges under each name (b. 1898 – d. 1983)
- Color distinction: people IN the photo archive (warm border) vs
  GEDCOM-only (subtle gray border)

### Interaction
- Click node → expand/collapse that branch
- Click node → popup card with key details + link to person page
- Zoom and pan (mouse wheel + drag)
- "Focus on" dropdown to center on a specific person
- "Show speculative" toggle (already exists, make it work)

### Layout Options
Consider implementing:
- **Pedigree view** (ancestors of one person going up)
- **Descendancy view** (descendants of one person going down)
- **Full graph view** (everyone, force-directed or hierarchical)

### Data Science Angle
Add one novel visualization element:
- **Photo density overlay:** nodes with more photos in the archive are
  visually larger or more prominent. This highlights where the archive
  is rich vs. where it has gaps.
- OR **Timeline lane:** a horizontal timeline at the bottom showing
  when each person lived, with the tree above. This gives generational
  context at a glance.

### Mobile
- Simplified view: pedigree/linear format on mobile
- Pinch-to-zoom support
- Tap node → full-screen detail card

## Implementation

1. Diagnose why current relationships aren't rendering
2. Fix the data pipeline (GEDCOM → relationships.json → tree API → D3)
3. Rebuild the tree visualization using D3.js or family-chart
4. Implement the new design
5. Test with real data — the Menashe/Amato/Capeluto families should
   all appear connected

## Verification

1. Open /tree — the "Everyone" view should show connected families
2. Open /tree?person={netanel-menashe-id} — should show his full tree:
   parents (if available), wife Rachel Amato, son Solomon, etc.
3. Screenshot both desktop and mobile
4. Record a browser video of navigating the tree
5. Compare to the Ancestry.com screenshots to verify data accuracy

Commit: `feat(tree): session 74 — family tree visualization overhaul with archival aesthetic`

---

# ═══════════════════════════════════════════
# AGENT 4: MOBILE RESPONSIVE OVERHAUL
# Worktree: rhodesli-mobile
# Branch: session-74-mobile
# ═══════════════════════════════════════════

## Mission

Mobile is barely usable. The admin bar is hard to see, face cards
don't work, navigation is cramped, and most features break on small screens.

## Comprehensive Mobile Audit

Test EVERY page on the site at 375px width (iPhone SE) and 390px (iPhone 14).
Use the browser dev tools responsive mode.

Pages to test:
1. `/` — landing/home
2. `/photos` — photo gallery
3. `/people` — people list
4. `/?section=to_review` — admin inbox (New Matches)
5. `/person/{id}` — person detail page
6. `/photo/{id}` — photo viewer with face overlays
7. `/tree` — family tree
8. `/timeline` — timeline
9. `/map` — map view
10. `/compare` — compare/upload tool
11. `/connect` — social graph
12. `/collections` — collections list
13. Any collection detail page
14. `/estimate` — date estimation

Screenshot every page. Create an Artifact catalog of all mobile issues.

## Priority Fixes

### Admin Bar (P0)
- The admin navigation bar is cramped and barely visible on mobile
- Redesign as: hamburger menu OR bottom tab bar OR collapsible drawer
- Must include: quick access to New Matches count, key admin actions
- Should be easily dismissible when in "sharing" mode

### Navigation (P0)
- Implement a proper mobile nav pattern:
  Option A: Bottom tab bar (Photos, People, Tree, More)
  Option B: Slide-out drawer with section headers
  Option C: Collapsible header with search
- Whatever you choose, test it and verify it's intuitive

### Content Layout (P1)
- All text should be readable without horizontal scrolling
- Images should scale to container width
- Tables should be horizontally scrollable
- Forms should be touch-friendly (min 44px tap targets)

### Touch Interactions (P1)
- All interactive elements need adequate tap target size (44x44px min)
- No hover-only interactions (they don't work on mobile)
- Swipe gestures where appropriate (photo galleries, face cards)

## Verification

For EVERY fix you make:
1. Open the browser at 375px width
2. Navigate to the affected page
3. Screenshot before and after
4. Test all interactive elements (buttons, links, dropdowns)
5. Verify no horizontal scrolling occurs
6. Record a browser video of the full mobile navigation flow

Commit: `fix(mobile): session 74 — comprehensive mobile responsive overhaul`

---

# ═══════════════════════════════════════════
# AGENT 5: COMPREHENSIVE UX AUDIT + FLOW FIX
# Worktree: rhodesli-ux-audit
# Branch: session-74-ux-audit
# ═══════════════════════════════════════════

## Mission

Audit the entire UX flow of the application. The app currently confuses
even its creator (who is also the admin). Map every user journey, identify
confusion points, and fix the navigation/information architecture.

## Phase 1: Map the App

Navigate through EVERY page as both admin and public user.
Create an Artifact: a complete sitemap showing:
- Every page URL
- What role can access it (public / admin)
- What actions are available on each page
- How you navigate FROM each page TO other pages

## Phase 2: Identify the Two Modes

The app has two fundamental modes that need clear separation:

### Mode 1: Admin/Contributor (Internal Tool)
- Reviewing AI face matches (confirm/reject/skip)
- Uploading new photos
- Linking people to GEDCOM records
- Managing identities (merge, dismiss, edit)
- Viewing ML pipeline status

### Mode 2: Public/Community (Heritage Sharing)
- Browsing photos by collection, person, date, location
- Viewing person pages with photos and relationships
- Using the Compare tool to identify unknown people
- Exploring the family tree
- Leaving comments and memories
- Using "Help Identify" to contribute knowledge

## Phase 3: Navigation Redesign

Current problems:
- The sidebar has both admin and public items jumbled together
- "New Matches" (admin) sits next to "People" (public)
- The "REVIEW" / "LIBRARY" / "BROWSE" / "ADMIN" sections in the
  sidebar are unclear groupings
- It's not obvious how to switch between admin and public views

Design a clearer navigation that:
1. **Separates admin from public** — either:
   - A toggle/switch at the top ("Admin Mode" / "Community Mode")
   - Separate navigation layouts per mode
   - Admin features behind a gear/settings icon
2. **Groups related features logically**
3. **Makes the "Help Identify" flow prominent** for community visitors
4. **Reduces cognitive load** — fewer items visible at once

## Phase 4: Implement Top Priority Fixes

Based on your audit, implement the top 5-10 most impactful changes.
For each change:
1. Write what you're changing and why
2. Implement the change
3. Test in browser (desktop AND mobile)
4. Screenshot before and after
5. Create a walkthrough Artifact

## Phase 5: Generate UX Recommendations

Create a prioritized list of ALL UX improvements you identified,
even ones you didn't implement. Save as `docs/UX_AUDIT_SESSION_74.md`:

```
## UX Audit Findings — Session 74

### Implemented (this session)
1. [Description] — [Screenshot artifact reference]
2. ...

### Recommended (Priority 1 — next session)
1. [Description] — [Rationale]
2. ...

### Recommended (Priority 2 — future)
1. [Description] — [Rationale]
2. ...

### Design Direction Notes
[Your observations about the overall design language, 
consistency issues, and opportunities for improvement]
```

## Verification

Walk through the complete user journey for:
1. **Admin flow:** Login → See new matches → Confirm a face → View person page
2. **Public flow:** Land on site → Browse photos → Click a face → See person page → View tree
3. **Help Identify flow:** Receive shared link → View person → Leave a comment
4. **Compare flow:** Upload a photo → See matches → Confirm/correct

Record browser videos of each flow.

Commit: `feat(ux): session 74 — comprehensive UX audit with navigation redesign`

---

## POST-SESSION: Harness Documentation

Whichever agent finishes first should also:

1. Create `docs/session_context/session-74-context.md` (copy from the
   context file provided)
2. Create `docs/session_logs/session_74_log.md` with:
   - What each agent accomplished
   - What was deferred
   - Lessons learned about using Antigravity vs Claude Code
3. Update BACKLOG.md with any new issues discovered
4. Update ROADMAP.md if priorities shifted

---

## IMPORTANT: Gemini-Specific Instructions

Because you (Gemini 3.1 Pro) have a much larger context window than
Claude, you have a unique advantage on this project:

1. **Read the ENTIRE codebase** before starting. Don't just read the
   files I listed — explore. Understand the data flow end-to-end.
2. **Read ALL tests** — they document expected behavior better than prose.
3. **Read ALL docs/** — there are 75+ lessons learned in tasks/lessons.md
   that encode failure patterns. Learn from them.
4. **Use the browser aggressively** — this is where you shine vs Claude Code.
   Don't just test your changes — explore the existing app, find bugs
   you weren't explicitly told about, and fix them.
5. **Generate visual artifacts** — screenshots, browser recordings,
   before/after comparisons. These are your evidence trail.
6. **Be opinionated about design** — you can see the screenshots.
   Don't just implement what's described — improve on it if you
   have a better idea. Show your work with browser screenshots
   and explain your reasoning.
