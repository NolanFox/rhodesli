# Session 74 Context: Antigravity Migration

## Project Overview

**Rhodesli** is a heritage photo consensus engine for the Jewish community
of Rhodes, Greece. It uses ML (InsightFace face detection/embeddings,
PyTorch CORAL date estimation) to identify people in historical photos.

**Stack:** Python, FastHTML, Supabase (Postgres), Railway deployment,
Cloudflare R2 storage, InsightFace, PyTorch, Gemini API.

**Live site:** rhodesli.nolanandrewfox.com  
**Current stats:** 272 photos, 59 identified people, 666 faces detected,
405 faces in review queue, 202 needing help identification.

---

## Harness Translation to Antigravity Skills

### SKILL 1: rhodesli-harness (`.agent/skills/rhodesli-harness/SKILL.md`)

```markdown
---
name: rhodesli-harness
description: >
  Use this skill for ALL Rhodesli development tasks. Enforces project
  conventions: ALGORITHMIC_DECISIONS.md provenance tracking, session
  documentation, test requirements, and file size limits. Activate
  whenever modifying code, creating files, or making architectural decisions.
---

# Rhodesli Development Harness

## ALWAYS do these things

1. **Read CLAUDE.md first** — it's the project entry point (<80 lines)
2. **Read docs/VISION.md** — understand the WHY before coding
3. **Update ALGORITHMIC_DECISIONS.md** for ANY ML/algorithm change
   - Document: what was chosen, what was rejected, why, source
   - Use AD-NNN format with session number and date
4. **Update HARNESS_DECISIONS.md** for ANY workflow/process change
   - Use HD-NNN format
5. **Run tests before AND after changes:** `pytest tests/ -x -q`
6. **File size limits:**
   - CLAUDE.md: <80 lines
   - ROADMAP.md: <150 lines  
   - No docs file >300 lines
   - Session context files go in docs/session_context/
7. **Commit messages:** Use conventional commits
   - `feat:`, `fix:`, `docs:`, `refactor:`, `test:`
8. **Gatekeeper pattern:** ML outputs are staged as proposals.
   Admin accepts/rejects/corrects before going public.
   Confirmed data feeds back as ML ground truth anchors.

## Do NOT do these things

- Don't use /compact (lossy). Use /clear + re-read from disk.
- Don't claim a feature works without browser verification.
- Don't modify data/ files without understanding the pipeline.
- Don't skip test writing for new features.
```

### SKILL 2: rhodesli-ux-audit (`.agent/skills/rhodesli-ux-audit/SKILL.md`)

```markdown
---
name: rhodesli-ux-audit
description: >
  Use when reviewing or improving Rhodesli UX/UI. The app has two modes:
  admin/contributor mode (internal tool) and sharing mode (public-facing
  for community members). Ensure changes respect this dual-mode architecture.
  Always verify in the browser and take screenshots.
---

# Rhodesli UX Audit Skill

## App Architecture (Two Modes)

### Admin/Contributor Mode
- Face identification inbox (confirm/reject/skip AI matches)
- Photo upload and management
- GEDCOM import and linking
- ML pipeline controls
- Accessed via admin login

### Public/Sharing Mode  
- Person pages (shareable links)
- Photo gallery with face overlays
- Family tree visualization
- Compare tool (upload photo, find matches)
- Timeline, Map, Collections views
- Comments section for community input

## Design System
- **Aesthetic:** "Editorial Archival" — dark theme, elegant, respectful
- **Framework:** FastHTML (server-rendered HTML with HTMX)
- **No React** — vanilla JS, HTMX for interactivity
- **CSS:** Custom CSS, no Tailwind (server-rendered approach)

## Verification Requirements
- ALWAYS test in browser after making changes
- Take screenshots of before AND after states
- Test at minimum: desktop (1440px) and mobile (375px)
- Check dark theme contrast and readability
- Verify HTMX interactions still work after CSS changes

## Known Pain Points
- Face cards have excessive blank space, look dated
- Mobile layout is barely usable (admin bar especially)
- Navigation between admin and public modes is confusing
- Family tree doesn't render relationships correctly
```

### SKILL 3: rhodesli-ml-provenance (`.agent/skills/rhodesli-ml-provenance/SKILL.md`)

```markdown
---
name: rhodesli-ml-provenance
description: >
  Use when making any ML or algorithmic decision in Rhodesli. 
  Tracks all decisions in ALGORITHMIC_DECISIONS.md with full provenance.
  ML plan: date estimation (done) → similarity calibration → LoRA.
  Confirmed birth years are ground truth anchors.
---

# Rhodesli ML Provenance Tracking

## Current ML Pipeline
- Face detection: InsightFace (buffalo_l)
- Face embeddings: ArcFace (512-dim)
- Date estimation: PyTorch CORAL model + Gemini silver labels
- Photo analysis: Gemini API (scene, faces, dates, context)
- Similarity: cosine similarity with Platt scaling calibration

## Decision Tracking Format
Every ML decision gets an AD-NNN entry in docs/ml/ALGORITHMIC_DECISIONS.md:
```
### AD-NNN: [Decision Title]
- **Session:** N | **Date:** YYYY-MM-DD
- **Decision:** What was chosen
- **Alternatives considered:** What was rejected and why
- **Evidence:** Data, benchmarks, or reasoning
- **Status:** Active / Superseded by AD-XXX / Rejected
```

## Ground Truth
- Confirmed birth years from GEDCOM = anchor data
- Active learning + regression gate = core architecture
- ML outputs use Gatekeeper pattern (proposals, not facts)
```

---

## Current Issues to Fix (with Screenshots)

### Issue 1: Face Cards — Terrible UX
**Screenshots:** See uploaded screenshots of the New Matches page.
- Massive blank space around each face card
- Cards look like they're from 2010, not modern
- No visual hierarchy or density
- Mobile is especially bad — one card fills the entire screen
- Confirm/Skip/Reject buttons are enormous relative to content

**Design direction:** Research modern photo identification UIs.
Think: Apple Photos face identification, Google Photos suggestions,
Lightroom face tagging. Dense, efficient, image-forward.

### Issue 2: GEDCOM Linking Broken
**Screenshots:** See person page for Netanel Menashe.
- The linking interface shows partial matches but has NO pagination
- Users must click "Show 15 more (73 remaining)" repeatedly
- Rachel Amato (correct one: b. 1907, Rhodes) is in the GEDCOM
  file at ~/Downloads/gedcom_20260224/Fox_Capeluto_Fogel_Waldorf Family Tree.ged
  but does NOT appear in the system properly
- The Ancestry.com tree shows the correct data (see screenshot)
- The Rhodesli tree view shows Netanel Menashe isolated (no connections)
  even though the GEDCOM has his full family

### Issue 3: Family Tree Completely Broken
**Screenshots:** See the tree page and person tree pages.
- Tree view shows disconnected nodes (Capeluto family separate from Menashe)
- Relationships exist in the GEDCOM but don't render as connections
- The visualization is basic/ugly — just floating boxes
- Compare to Ancestry.com's tree which properly shows:
  - Salomon's grandparents, parents, siblings, children
  - Photos on nodes, dates, click-to-expand

**Research direction:** Look at d3-dag, family-chart by donatso,
modern genealogy tree visualizations. The tree should be:
- Interactive (zoom, pan, click to expand)
- Photos on nodes where available
- Color-coded (in archive vs GEDCOM-only)
- Responsive (works on mobile too)
- Beautiful — this is a heritage project, it should feel special

### Issue 4: Mobile Responsiveness
- Admin bar is hard to see/use on mobile
- Face cards are unusable on mobile
- Navigation is cramped
- Tree visualization doesn't scale
- Compare tool doesn't work well on small screens

### Issue 5: UX Flow Confusion
The app has unclear entry points between:
- Admin reviewing AI matches (internal workflow)  
- Public person pages (shareable)
- Public browsing (photos, collections, timeline, map)
- The "Help Identify" flow for community members
- Tree/Connect/Compare tools

These need clear visual separation and intuitive navigation.

---

## Key Files to Read

| File | Purpose |
|------|---------|
| CLAUDE.md | Project entry point, <80 lines |
| docs/VISION.md | Why this project exists |
| docs/ml/ALGORITHMIC_DECISIONS.md | All ML decisions with provenance |
| docs/HARNESS_DECISIONS.md | Workflow decisions |
| ROADMAP.md | Current priorities |
| BACKLOG.md | Full issue backlog |
| tasks/lessons.md | 75+ lessons learned |
| main.py | FastHTML app entry point |
| templates/ | All HTML templates |
| static/ | CSS, JS, images |
| rhodesli_ml/ | ML pipeline code |
| data/relationships.json | Relationship graph |
| data/gedcom_data.json | Imported GEDCOM data |

---

## GEDCOM File Location

The real GEDCOM file that needs to be imported/verified:
```
~/Downloads/gedcom_20260224/Fox_Capeluto_Fogel_Waldorf Family Tree.ged
```

This contains the Fox/Capeluto/Fogel/Waldorf family tree from Ancestry.com
with hundreds of individuals. Key people who MUST appear correctly:
- Netanel Menashe (b. 1898, d. 1983, Rhodes)
- Rachele (Rachel) AMATO (b. 1907, Rhodes — d. 2002, South Africa)
- Salomon Menashe (their son, b. 1936, d. 2019)
- Rica Sharhon Amato (b. 1870, d. 1963)
- Isaac AMATO (b. 1866, d. 1920)
- Moise Capeluto (b. 1904, d. 1978)
- Betty Capeluto (b. 1953, d. 2021)

---

## Family Tree Research for Agent Reference

### Modern Genealogy Tree Visualizations to Study
1. **Ancestry.com** — see uploaded screenshots for reference
   - Horizontal layout with generations as columns
   - Photos on nodes, dates underneath
   - Click to expand/collapse branches
   - Popup cards on hover with key details
   
2. **family-chart by donatso** (D3.js)
   - Already in the codebase from Session 39
   - Interactive zoom/pan, JSON data format
   - Customizable node content
   
3. **MyHeritage** — clean tree with photo circles
   - Vertical and horizontal layout options
   - Color-coded relationship lines
   - "Smart" matching suggestions

4. **FamilySearch** — enormous tree handling
   - Fan chart, descendancy, pedigree views
   - Works well at massive scale

### Data Science Angle for Tree Visualization
- Network graph approach (D3 force-directed) for relationship strength
- Heat map overlay showing "photo evidence density" per connection
- Timeline integration (show when relationships are active)
- Cluster analysis to highlight well-documented vs. sparse branches

## Architecture Constraint: JS Embedding Rules
- All new JS goes in static/js/ (e.g., static/js/family-tree.js, static/js/mobile-nav.js)
- FastHTML templates inject data via <script>const DATA = {{ data | tojson }}</script> or data- attributes
- HTMX handles all server mutations (POST/PUT/DELETE)
- JS handles only: rendering, animation, gestures, zoom/pan
- No npm, no build step, no framework imports
- Each JS file must be self-contained (no cross-file imports)
