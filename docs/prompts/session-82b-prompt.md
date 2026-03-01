# Session 82b: Face Cards Bug Fix + Sharing Consistency
# Tool: OpenAI Codex
# Branch: session-82b/face-cards-fix

---

## SETUP

```bash
git checkout -b session-82b/face-cards-fix
git push -u origin session-82b/face-cards-fix
```

Read these files first (in order):
1. `CLAUDE.md`
2. All files in `.claude/rules/`
3. `docs/session_context/session-82-context.md`
4. `ROADMAP.md`
5. `BACKLOG.md`

Run baseline tests:
```bash
pytest tests/ -x -q
```
Note the count. ALL tests must still pass after every commit.

---

## CONTEXT: WHAT HAPPENED

Face cards underwent a redesign that changed them from compact horizontal cards to large vertical cards. This regression:
1. Made face photos SMALLER (the opposite of what was requested)
2. Added excessive whitespace
3. Broke Find Similar functionality
4. Lost sharing buttons
5. Lost other quick actions

**Your job:** Fix ALL of this. Restore lost functionality. Make face cards work consistently everywhere.

---

## PHASE 1: ARCHAEOLOGY — Find What Was Lost (~10 min)

### 1A: Find the regression commit
```bash
# Find when face cards changed to vertical
git log --oneline --all -- app/main.py | head -50
git log --oneline --all --grep="face card" | head -20
git log --oneline --all --grep="card.*layout\|layout.*card\|vertical\|horizontal" | head -20
```

### 1B: Diff before vs after
Once you find the commit, examine what changed:
```bash
git diff <before-commit>..<after-commit> -- app/main.py | head -500
```

Document:
- What functions/components existed before
- What was removed or changed
- What CSS classes were involved
- What actions (buttons, links) were on each card

### 1C: Catalog current state
```bash
# Find all face card rendering code
grep -n "face.*card\|card.*face\|identity.*card\|FaceCard\|face_card" app/main.py | head -30

# Find all Find Similar code
grep -n "find.*similar\|similar.*find\|FindSimilar" app/main.py | head -30

# Find all share button code
grep -n "share.*button\|ShareButton\|share_button\|Share.*Photo\|Share.*Person" app/main.py | head -30
```

Commit: `docs: session 82b phase 1 — face card archaeology`

---

## PHASE 2: FIX FACE CARD LAYOUT (~15 min)

### Requirements:
1. Face cards should be **horizontal** (not vertical) in admin mode
2. Face photo should be **large and prominent** — it's the most important element
3. **Minimize whitespace** — every pixel should serve a purpose
4. Card should show: face photo, person name (or "Unidentified"), confidence tier, action buttons
5. Action buttons on every card: Find Similar, Share, View Photo, Edit/Tag
6. Cards should be the SAME layout and functionality in EVERY admin section:
   - Inbox
   - People page
   - Needs Help
   - Focus Mode
   - Confirmed identities
   - Any other section

### Implementation:
Create a SINGLE reusable face card component:
```python
def face_card(face_data, mode="admin"):
    """
    Single source of truth for all face card rendering.
    
    mode="admin" — full functionality (find similar, share, edit, tag)
    mode="public" — simplified (share, view photo)
    """
```

ALL sections must use this one component. No separate implementations.

### Test:
```python
def test_face_card_consistency():
    """Every section renders face cards with identical structure."""
    
def test_face_card_has_all_actions():
    """Admin face cards have: find_similar, share, view_photo, edit buttons."""
    
def test_face_card_photo_size():
    """Face photo takes up at least 40% of card width."""
```

Commit: `fix(ui): restore horizontal face cards with consistent layout`

---

## PHASE 3: FIX FIND SIMILAR (~20 min)

### The Core Problem
Find Similar is broken. It either doesn't work, goes to a broken link, or only works for the first image.

### Admin Mode Behavior (REQUIRED):
1. User clicks "Find Similar" on a face card
2. An inline panel animates open BELOW or BESIDE the card
3. The surrounding face cards smoothly rearrange to make room
4. The panel shows similar faces with confidence scores (High/Moderate/Low)
5. Each similar face has actions: [Merge] [Not Same] [Compare Side-by-Side]
6. Clicking anywhere outside the panel or pressing Escape closes it
7. Cards smoothly rearrange back to their original positions
8. **This does NOT navigate to a new URL**

### Public Mode Behavior:
- Find Similar can have its own page at `/person/{id}/similar` or similar
- This page is shareable with its own URL
- It shows similar faces in a grid layout
- This is fine as a separate page for sharing purposes

### Implementation:
```python
def find_similar_panel(face_id):
    """
    HTMX-powered inline panel that loads similar faces.
    hx-get="/api/find-similar/{face_id}"
    hx-target="#similar-panel-{face_id}"
    hx-swap="innerHTML"
    Uses CSS transitions for smooth open/close animation.
    """
```

### Investigate the broken state:
```bash
# Find current Find Similar endpoint
grep -n "find.similar\|similar.*route\|/similar" app/main.py | head -20

# Check if the endpoint returns data
# Test with curl if possible
```

### Test:
```python
def test_find_similar_returns_results():
    """Find similar endpoint returns face matches with confidence scores."""

def test_find_similar_admin_is_inline():
    """Admin find similar renders as inline panel, not page navigation."""

def test_find_similar_public_has_share_url():
    """Public find similar page has shareable URL with OG tags."""
```

Commit: `fix(ux): restore find similar — inline panel for admin, shareable page for public`

---

## PHASE 4: FIX SHARING CONSISTENCY (~10 min)

### Current State:
- People tab: sharing works ✓
- Find Similar: sharing broken ✗
- Other face card sections: inconsistent ✗

### Requirements:
Create a SINGLE reusable share component:
```python
def share_button(entity_type, entity_id, style="icon"):
    """
    Universal share button used on every shareable surface.
    
    entity_type: "photo", "person", "match", "similar"
    entity_id: UUID
    style: "icon" (compact), "button" (icon + text)
    
    Behavior:
    - Desktop: copies URL to clipboard + toast "Link copied!"
    - Mobile: triggers Web Share API if available
    - Consistent icon everywhere (share/arrow-from-box icon)
    """
```

### Apply to:
- [ ] Every face card (admin and public)
- [ ] Every photo card
- [ ] Photo detail page
- [ ] Person page
- [ ] Match comparison page
- [ ] Find Similar results (public page)
- [ ] Timeline entries (if shareable)

### Test:
```python
def test_share_button_on_face_cards():
    """Every face card in admin has a share button."""

def test_share_button_generates_valid_url():
    """Share button generates working public URL."""

def test_share_button_consistent_across_sections():
    """Share button renders identically in inbox, people, needs-help, focus-mode."""
```

Commit: `fix(ux): consistent share button across entire app`

---

## PHASE 5: FIX PHOTOS/FACES TOGGLE PERFORMANCE (~10 min)

### Problem:
On public person pages (`/person/{id}`), switching between Photos and Faces tabs is extremely slow.

### Investigation:
```bash
# Find the toggle implementation
grep -n "photos.*tab\|faces.*tab\|toggle.*photo\|toggle.*face\|tab.*switch" app/main.py | head -20

# Check if it's re-querying the database on every toggle
grep -A 20 "def.*person_page\|person.*route\|/person/" app/main.py | head -50
```

### Likely fixes (try in order):
1. **Lazy loading:** Only load the active tab's content. Load the other tab on first click.
2. **Pre-render both:** Render both tabs on page load, show/hide with CSS (fastest toggle, slightly more initial load)
3. **HTMX partial swap:** Use `hx-get` to load tab content on click, cache after first load
4. **Pagination:** If a person has 50+ photos, paginate instead of loading all at once

### Test:
```python
def test_person_page_tab_switch_performance():
    """Tab switch should complete in under 500ms."""
    
def test_person_page_loads_both_tabs():
    """Both photos and faces tabs render content."""
```

Commit: `perf: fix photos/faces toggle speed on person pages`

---

## PHASE 6: CROSS-SITE FUNCTIONALITY AUDIT (~10 min)

### Verify nothing else is broken:

Check every section for functional face cards:
- [ ] Inbox: face cards render, all actions work
- [ ] People page: face cards render, all actions work
- [ ] Needs Help: face cards render, all actions work
- [ ] Focus Mode: face cards render, all actions work
- [ ] Confirmed identities: face cards render, all actions work
- [ ] Skipped: face cards render, all actions work

Check sharing works from:
- [ ] Photo detail page
- [ ] Person page
- [ ] Match comparison page
- [ ] Find Similar results

Check navigation:
- [ ] Every face card links to the correct person/photo
- [ ] Back button works after every navigation
- [ ] No dead-end pages

Document any issues found. Fix if quick (<5 min each). Otherwise add to BACKLOG.

### Test full suite:
```bash
pytest tests/ -x -q
```

Commit: `test: session 82b cross-site functionality audit`

---

## PHASE 7: DOCUMENTATION + PR (~5 min)

### Update docs:
- `ALGORITHMIC_DECISIONS.md`: Add AD for face card component unification, Find Similar dual-mode (inline admin / page public)
- `CHANGELOG.md`: v0.82b — Face cards restored, Find Similar fixed, sharing unified
- `docs/session_logs/session-82b-log.md`: Session log with planned vs actual
- `docs/session_context/session-82b-assessment.md`: Self-assessment

### Create PR:
```bash
git add .
git commit -m "docs: session 82b complete — face cards + sharing + performance"
git push origin session-82b/face-cards-fix

gh pr create \
  --title "Session 82b: Face Cards Restoration + Find Similar + Sharing Consistency" \
  --body "## Changes

### Face Cards
- Restored horizontal layout with larger face photos
- Single reusable face_card() component used everywhere
- All admin sections now have identical face card UX

### Find Similar
- Admin mode: inline animated panel (no page navigation)
- Public mode: shareable page with its own URL
- Confidence scores displayed on all results

### Sharing
- Single share_button() component used across entire app
- Works on: face cards, photo pages, person pages, match pages, find similar
- Desktop: clipboard copy + toast. Mobile: Web Share API.

### Performance
- Photos/Faces toggle on person pages is now fast

### Tests
- X new tests added
- All existing tests pass

## Evaluation
Claude Code will verify this PR with Chrome before merging." \
  --base main \
  --head session-82b/face-cards-fix
```

---

## CLEANUP

```bash
# Remove any worktrees created during session
git worktree list
# For each worktree: git worktree remove <path>
```

---

## DO NOT:
- Modify ML pipeline code
- Change data files or JSON data
- Skip tests before commits
- Navigate to new URLs for admin Find Similar (must be inline)
- Create separate face card implementations per section
- Delete any existing functionality that works

## EVALUATION CRITERIA (How Codex will be judged):
1. Do ALL face cards look identical across every admin section?
2. Does Find Similar work as an inline panel in admin mode?
3. Does sharing work from every page/card?
4. Is the Photos/Faces toggle fast?
5. Do all pre-existing tests still pass?
6. Were new tests added for every fix?
7. Is there a clean PR ready for review?
8. Were worktrees cleaned up?
