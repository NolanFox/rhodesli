# Session 80: Fix Everything — Tree, Face Cards, UX Polish + Interactive Walkthrough

Read CLAUDE.md. Read docs/ALGORITHMIC_DECISIONS.md (first 80 lines).
Read docs/session_context/session_79_context.md (if exists).
Read ROADMAP.md. Read BACKLOG.md (first 60 lines).
Read /mnt/skills/public/frontend-design/SKILL.md.
Read docs/session_protocols/interactive.md.
Read docs/VISION.md.

## SESSION TYPE: Hybrid (Autonomous Fixes → Interactive Walkthrough)

**Part 1 (Acts 0–4):** Autonomous fixes. You execute, commit, deploy.
**Part 2 (Acts 5+):** Interactive. Human tests, provides screenshots, you fix.

---

## ABSOLUTE RULES

1. **MANDATORY `/clear` between every Act.** Before starting each new Act, tell the human: "Act N complete. Please run `/clear` now, then say 'Act N+1'." Do NOT proceed until `/clear` is confirmed. This is non-negotiable — context rot has killed multiple sessions.
2. Commit after EVERY Act. Format: `fix(scope): desc` or `feat(scope): desc`.
3. `pytest tests/ -x -q` before every commit. Fix failures before proceeding.
4. Update ALGORITHMIC_DECISIONS.md for every non-trivial decision.
5. No file over 300 lines. Split if approaching limit.
6. `git push origin main` after every Act — Railway deploys on push.
7. After every deploy, run smoke test: `curl -s -o /dev/null -w "%{http_code}" https://rhodesli.nolanandrewfox.com/`
8. **Fixes are not complete until visually verified.** Use subagent with Claude Chrome extension OR wait for human screenshot confirmation.
9. Back up data files before modifying: `cp data/FILE data/FILE.bak.$(date +%s)`

---

## SESSION START — State Check

```bash
cat CLAUDE.md | head -30
git log --oneline -15
pytest tests/ -x -q 2>&1 | tail -5
python3 -c "
import json
ids = json.load(open('data/identities.json'))
if 'identities' in ids: ids = ids['identities']
confirmed = sum(1 for v in ids.values() if isinstance(v,dict) and v.get('status')=='CONFIRMED')
total = len([v for v in ids.values() if isinstance(v,dict)])
print(f'Identities: {total} total, {confirmed} confirmed')
"
echo "--- Data file sizes ---"
wc -l data/identities.json data/relationships.json data/gedcom_matches.json data/annotations.json 2>/dev/null
```

---

## ACT 0: Session 79 Red Flag Cleanup (~10 min)

### 0A: Fix uncommitted data file noise

Session 79 left uncommitted changes to annotations.json, identities.json, relationships.json, gedcom_matches.json from a backfill that silently rewrote JSON key ordering. This creates noisy diffs. Fix:

```bash
# Check current git status
git status

# If there are uncommitted data file changes:
# 1. Check if they're just key reordering (no semantic changes)
git diff data/*.json | head -100

# 2. If purely cosmetic reordering: commit them cleanly
#    with a message that explains they're non-semantic
git add data/*.json
git commit -m "chore(data): normalize JSON key ordering from session 79 backfill

These changes are purely cosmetic JSON key reordering
from the session 79 backfill. No semantic data changes."

# 3. If there ARE semantic changes: investigate and document
```

### 0B: Verify Session 78 remaining red flags

Session 78 claimed "0 red flags" when 6+ existed. Session 79 fixed 3. Enumerate what remains unfixed:

```bash
# Check what session 78 claimed vs reality
cat docs/assessments/session-78-assessment.md 2>/dev/null || echo "No assessment found"
cat docs/assessments/session-79-assessment.md 2>/dev/null || echo "No assessment found"

# Specifically check:
# 1. Compare feature status (deferred 7+ sessions)
# 2. Mobile viewport (was it tested?)
# 3. Skipped tests (were they addressed?)
# 4. Deduplication (was it run?)
grep -r "compare\|dedup\|mobile.*viewport\|skipped.*test" docs/assessments/ 2>/dev/null
```

Document in session log what remains unfixed. Create BACKLOG entries for anything not addressed in this session.

### 0C: Verify GEDCOM match integrity

The gedcom_matches.json had 580 lines changed in session 79, dismissed as "key reordering." Verify the 33 GEDCOM matches from session 49B are intact:

```bash
python3 -c "
import json
matches = json.load(open('data/gedcom_matches.json'))
print(f'Total GEDCOM matches: {len(matches)}')
# Show a sample to verify structure is intact
for k, v in list(matches.items())[:3]:
    print(f'  {k}: {v}')
"
```

If matches are corrupted, restore from the last known good commit.

**Commit:** `chore: session 80 act 0 — red flag cleanup and data verification`

**→ Tell human: "Act 0 complete. Please run `/clear` now, then say 'Act 1'."**

---

## ACT 1: Family Tree Overhaul — Architecture (~25 min)

The current tree shows 13 of 718 people using a CardSvg workaround. 114 disconnected clusters. This Act rebuilds it properly.

### Research: How Ancestry.com's tree works

The tree should behave like Ancestry (see screenshot reference):
- **Start focused:** Show one person + their immediate family (parents, spouse, children, siblings)
- **Expand on demand:** Arrow buttons on each node to load parents/children/siblings
- **Lazy load:** Only fetch data for visible nodes + one level out
- **Search:** Type-ahead search to jump to any person (dropdown doesn't work at 718 people)
- **Click behavior:** Click a node → go to their person page. Separate "focus tree" action to re-center tree on that person.
- **Zoom:** Proper pinch-zoom and scroll-zoom with sensible defaults (fit immediate family in viewport)

### Implementation: Replace current tree with BALKAN FamilyTreeJS or equivalent

**Why BALKAN FamilyTreeJS:** Built-in lazy loading, expand/collapse, zoom/pan, search, photo nodes, custom templates, ancestor expansion. Works with vanilla JS (no React). Free tier available for non-commercial use. Has explicit family tree semantics (pids for partners, fid/mid for parents).

**If licensing is an issue:** Fall back to `donatso/family-chart` (MIT license, D3-based) with manual expand/collapse implementation.

**Architecture decision: API-driven lazy loading**

Create an API endpoint that returns tree data for a specific person + radius:

```
GET /api/tree/data?person_id={uuid}&depth=1
→ Returns: { nodes: [...], links: [...] }
   Only the focal person + their immediate connections
   Each node includes: { id, name, birth_year, death_year, photo_url, 
                          has_parents: bool, has_children: bool, has_siblings: bool }

GET /api/tree/expand?person_id={uuid}&direction=parents|children|siblings
→ Returns: additional nodes + links to merge into existing tree
```

This way we never load all 718 people at once. The tree starts small and grows as the user clicks expand arrows.

### Steps

1. **Install the tree library** (CDN or vendored JS)
2. **Create `/api/tree/data` endpoint** — queries relationships.json and identities.json, returns only the requested person + 1 level of connections
3. **Create `/api/tree/expand` endpoint** — returns additional nodes for a specific direction
4. **Build the tree page:**
   - Search bar at top (type-ahead, searches all 718 people by name)
   - Tree container fills remaining viewport
   - Initial load: centered on the person from URL param (or first confirmed person)
   - Expand arrows on nodes that have hidden connections
   - Click node → navigate to `/person/{id}`
   - Right-click or long-press → "Focus tree on this person" (re-centers)
   - Zoom controls: +/- buttons, scroll wheel, pinch
   - Fit-to-screen button
   - "Show speculative" toggle (hides/shows theory relationships)
5. **Node design:**
   - Photo thumbnail (face crop if available, silhouette placeholder if not)
   - Name
   - Birth-death years
   - Couple connector (side-by-side with spouse)
   - Visual indicator for confirmed vs. speculative connections

### Key technical decisions to log in ALGORITHMIC_DECISIONS.md:
- AD-XXX: Tree library choice and rationale
- AD-XXX: Lazy loading API design — why per-request loading vs. full dump
- AD-XXX: Node click behavior — navigate vs. focus (and how to access both)

**Tests:**
- `/api/tree/data` returns correct structure for a known person
- `/api/tree/expand` returns parents/children/siblings correctly
- Tree page renders without JS errors
- Search returns results for known names

**Commit:** `feat(tree): complete overhaul — lazy loading, search, expand/collapse (AD-XXX)`

**→ Tell human: "Act 1 complete. Please run `/clear` now, then say 'Act 2'."**

---

## ACT 2: Face Card UX — Find Similar Redesign (~20 min)

### The Problem

"Find Similar" currently renders as a badly-formatted vertical column. The face cards in the People section are a broken mix of old and new styles. Multiple faces per identity are not handled well.

### Research first

Before coding, research how these apps handle face comparison/similar faces:
- **Google Photos:** Large hero face, grid of similar faces below
- **Apple Photos:** People album → face grid with counts
- **Excire Foto:** Side-by-side comparison with confidence
- **ImageRanger:** Face crop prominently displayed, metadata secondary

Web search for: "face gallery comparison UX pattern photo management app"

### Find Similar redesign

When "Find Similar" is clicked on a face card:

1. **Hero section (top ~40% of viewport):**
   - The source face image gets LARGE (300-400px)
   - Name, dates, photo count displayed alongside
   - "Back to all faces" button

2. **Similar faces grid (bottom ~60% of viewport):**
   - Responsive grid (3-4 columns on desktop, 2 on mobile)
   - Each result card: face crop (150px+), name/status, distance score, confidence tier (color-coded)
   - Cards are clickable → go to that person's page
   - "Merge Selected" / "Not Same Selected" batch actions (for admin)
   - Lazy-load more results on scroll

3. **The old vertical panel becomes this full-page layout** — not a sidebar

### Face card improvements (global)

1. **Click face photo → go to the full photo** (restore this lost functionality)
2. **Multi-face clusters:** Show face count badge. On the card, show a mini-gallery (2-3 face thumbnails stacked/overlapping) that expands on click
3. **Sharing:** Restore share button on face cards (was removed in redesign). Use Web Share API on mobile, copy-link on desktop.
4. **View All Photos:** Should be a prominent action, not buried under a menu

### People section face cards

The People section (`/?section=confirmed`) has a broken mix of old and new card styles. Fix:

1. Use ONE consistent card component everywhere
2. Card layout priority: face image (dominant, 60%+ of card) → name → status badge → key actions
3. Multi-face handling: show representative face large, count badge, expandable gallery
4. Actions: View All Photos, Find Similar, View in Tree, Public Page — all visible without opening a menu
5. "Return to Inbox" action should be less prominent (admin edge case)

### Implementation approach

Since FastHTML + HTMX is the constraint, use:
- HTMX for dynamic content loading (Find Similar results load via `hx-get`)
- CSS Grid for responsive layouts
- Minimal JS for interactions (expand gallery, zoom)
- If current framework limits gallery interactions: embed a lightweight JS carousel (Swiper.js via CDN) for multi-face galleries

### Tests:
- Find Similar endpoint returns correctly structured data
- Face card renders consistently across People, Review, and individual views
- Multi-face cards show correct count and gallery

**Commit:** `feat(face-cards): find similar redesign + consistent cards everywhere (AD-XXX)`

**→ Tell human: "Act 2 complete. Please run `/clear` now, then say 'Act 3'."**

---

## ACT 3: Compare Feature — Ship or Explicitly Defer with Plan (~15 min)

Compare has been deferred across 7+ sessions. The blocker is InsightFace needing GPU on Railway. This Act either ships a working CPU solution or creates a concrete, time-bound plan.

### Option A: CPU-compatible face comparison (preferred)

Research lightweight CPU face detection/embedding options:
- `mediapipe` Face Mesh (CPU, fast, lower quality but works)
- `dlib` face recognition (CPU, decent quality)
- `onnxruntime` with InsightFace ONNX model (CPU inference, slower but compatible)
- Pre-compute and cache all archive embeddings at deploy time (so compare only needs to compute 1 new embedding)

If any of these work: implement a basic compare flow:
1. User uploads photo
2. CPU-based face detection + embedding extraction
3. Compare against pre-cached archive embeddings
4. Show tiered results

### Option B: Honest deferral with concrete plan

If CPU options aren't viable in this session:
1. Write a CONCRETE plan with timeline (not "research options")
2. Create a BACKLOG entry with specific tasks, estimated hours, and blockers
3. Add a visible "Compare — Coming Soon" message on the Compare page explaining what it will do
4. Log the decision in ALGORITHMIC_DECISIONS.md

**Do NOT just punt this again with vague "research" language.**

**Commit:** `feat(compare): CPU face comparison implementation (AD-XXX)` or `docs: compare concrete plan + coming soon page (AD-XXX)`

**→ Tell human: "Act 3 complete. Please run `/clear` now, then say 'Act 4'."**

---

## ACT 4: Deploy + Smoke Test + Session Log Setup (~10 min)

### Deploy and verify

```bash
git push origin main
# Wait 60 seconds for Railway deploy
sleep 60
curl -s -o /dev/null -w "%{http_code}" https://rhodesli.nolanandrewfox.com/
curl -s -o /dev/null -w "%{http_code}" https://rhodesli.nolanandrewfox.com/tree
curl -s -o /dev/null -w "%{http_code}" https://rhodesli.nolanandrewfox.com/?section=confirmed
```

### Set up interactive session logging

Create `docs/session_logs/session_80_interactive_log.md`:

```markdown
# Session 80 Interactive Testing Log

## Test Matrix
| # | Page/Feature | Action | Expected | Actual | Status | Fix? | Screenshot? |
|---|-------------|--------|----------|--------|--------|------|-------------|
| 1 | Tree | Load initial view | Shows focal person + family | | | | |
| 2 | Tree | Search for person | Type-ahead finds them | | | | |
| 3 | Tree | Click expand arrows | Loads parents/children | | | | |
| 4 | Tree | Click node | Goes to person page | | | | |
| 5 | Tree | Zoom in/out | Smooth, sensible defaults | | | | |
| 6 | People | View face cards | Consistent layout, face dominant | | | | |
| 7 | People | Multi-face identity | Shows gallery, count badge | | | | |
| 8 | People | Click face photo | Goes to full photo | | | | |
| 9 | People | Find Similar | Hero + grid layout | | | | |
| 10 | People | Share button | Web Share or copy link | | | | |
| 11 | Review | Face cards | Same style as People | | | | |
| 12 | Review | Find Similar | Same layout as People | | | | |
| 13 | Compare | Upload photo | Detects faces, shows results | | | | |
| 14 | General | Navigation | All nav links work | | | | |
| 15 | General | Mobile responsive | Cards stack, tree scrolls | | | | |

## UX Issues Found During Testing
| # | Severity | Page | Description | Fixed? | How | Commit |
|---|----------|------|-------------|--------|-----|--------|
```

### Set up automated synthesis

Create `scripts/session_80_synthesize.py`:

```python
"""
Run after interactive testing to analyze session 80 results.
Reads the interactive log and produces a summary.
"""
import re

def synthesize():
    with open('docs/session_logs/session_80_interactive_log.md') as f:
        content = f.read()
    
    # Count results
    pass_count = content.count('| PASS |') + content.count('| ✅ |')
    fail_count = content.count('| FAIL |') + content.count('| ❌ |')
    fix_count = content.count('| Yes |') + content.count('| Fixed |')
    
    # Count UX issues by severity
    p0 = content.lower().count('| p0 |')
    p1 = content.lower().count('| p1 |')
    p2 = content.lower().count('| p2 |')
    
    print(f"""
=== SESSION 80 SYNTHESIS ===
Tests: {pass_count} passed, {fail_count} failed
Fixes applied: {fix_count}
UX issues: {p0} P0, {p1} P1, {p2} P2

Pass rate: {pass_count/(pass_count+fail_count)*100:.0f}% (target: 80%+)

STRENGTHS: Areas where all tests passed on first try
WEAKNESSES: Areas requiring multiple fix cycles
""")
    
    # Identify patterns
    lines = content.split('\n')
    tree_issues = sum(1 for l in lines if 'Tree' in l and ('FAIL' in l or '❌' in l))
    card_issues = sum(1 for l in lines if ('People' in l or 'card' in l.lower()) and ('FAIL' in l or '❌' in l))
    
    if tree_issues > 2:
        print("⚠️  PATTERN: Tree has systemic issues — may need architectural review")
    if card_issues > 2:
        print("⚠️  PATTERN: Face cards have systemic issues — component consistency problem")
    
    print("\nFull log: docs/session_logs/session_80_interactive_log.md")

if __name__ == '__main__':
    synthesize()
```

**Commit:** `chore: session 80 act 4 — deploy + interactive testing infrastructure`

**→ Tell human: "Act 4 complete. Autonomous work is done. Please run `/clear` now, then say 'Act 5 — Interactive'."**

---

## ACT 5+: Interactive Walkthrough (Human-in-the-loop)

### Protocol

1. **Human tests a feature** from the test matrix above
2. **Human reports result:** 
   - If it works: "Test N: PASS" (with optional screenshot)
   - If it fails: describes what's wrong + screenshot
3. **You fix immediately.** Do not defer. Do not move to next test until this one passes.
4. **After fixing:** deploy, tell human to re-test
5. **Loop until human confirms PASS**
6. **Update the interactive log** after every test result
7. **Log UX issues** even on passing tests if something looks off

### UX Bug Detection

When the human provides a screenshot, evaluate it against:
1. Is the face image dominant (60%+ of card area)?
2. Is text readable without squinting?
3. Are clickable elements obvious (not buried in menus)?
4. Is spacing consistent?
5. Does the layout work at this viewport width?
6. Are there visual glitches (overlapping elements, cut-off text, misaligned items)?
7. Does it match the Rhodesli aesthetic (dark theme, heritage feel)?

Log ALL UX observations in the interactive log, even if the test technically passes.

### Fix Protocol

When fixing a bug reported by the human:

```bash
# 1. Identify the issue
# 2. Fix it
# 3. Run tests
pytest tests/ -x -q
# 4. Commit
git add -A && git commit -m "fix(scope): description from human feedback"
# 5. Deploy
git push origin main
# 6. Wait for deploy
sleep 45
# 7. Smoke test
curl -s -o /dev/null -w "%{http_code}" https://rhodesli.nolanandrewfox.com/
# 8. Tell human to re-test
```

**CRITICAL: Do not stop fixing until the human confirms with a screenshot that it works.** If a fix doesn't work, debug further. Do not say "try clearing your cache" unless you've exhausted code-level fixes.

### When all tests pass

1. Update the interactive log with final status
2. Run `python scripts/session_80_synthesize.py`
3. Write `docs/assessments/session-80-assessment.md`:
   - What shipped (with evidence)
   - What was deferred (with BACKLOG entry and concrete plan)
   - Red flags (honest — if something is fragile, say so)
   - Pass rate and patterns from synthesis
   - Strengths and weaknesses analysis
   - What session 81 should verify first
4. Update ROADMAP.md and CHANGELOG.md
5. Final commit and push

---

## VERIFICATION GATE (must pass before session is considered complete)

- [ ] Tree loads with a focal person and their immediate family visible
- [ ] Tree search finds people by name
- [ ] Tree expand arrows load additional family members
- [ ] Tree node click navigates to person page
- [ ] Tree zoom works (scroll wheel + buttons)
- [ ] Face cards are visually consistent across People, Review, and individual views
- [ ] Find Similar shows hero face + responsive grid (not vertical column)
- [ ] Face photo click goes to full photo
- [ ] Multi-face identities show gallery with count
- [ ] Share button works on face cards
- [ ] Compare either works or has concrete "coming soon" with plan
- [ ] All data files committed cleanly (no phantom reordering diffs)
- [ ] Interactive log is complete with all test results
- [ ] Synthesis script has been run and results logged
- [ ] ALGORITHMIC_DECISIONS.md updated for all non-trivial decisions
- [ ] Assessment written honestly (no "0 red flags" unless truly zero)
