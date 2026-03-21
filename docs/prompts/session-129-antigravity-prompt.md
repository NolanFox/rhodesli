# Session 129 Antigravity — Mobile Responsiveness + Delightful Interactions

You are improving the Rhodesli heritage photo archive. The app uses FastHTML + HTMX + Tailwind CSS with a dark theme (slate-900 background, indigo/amber accents). Your job is TWO things: make mobile usable, and add delightful micro-interactions.

## CRITICAL: Branch First
```bash
git checkout -b session-129/antigravity-mobile
```
**YOU MUST BE ON THIS BRANCH BEFORE ANY EDITS.** Verify with `git branch --show-current`. DO NOT commit to main.

## YOUR FILES (only modify these)
- `app/main.py` — people grid, identity cards, page layout
- `app/page_routes.py` — mobile header, bottom nav, page chrome
- `app/person_routes.py` — person detail page
- `app/browse_routes.py` — photo grid, browse views
- `app/identity_routes.py` — focus mode, action buttons

## DO NOT TOUCH (EVER)
- `core/` — frozen
- `data/` — frozen, never modify
- `tests/` — don't touch existing tests
- `app/auth.py` — never change auth
- `app/rate_limit.py` — new, don't touch
- Never use `--no-verify` on commits
- Never remove `_check_admin` calls or change route paths
- Never change Supabase queries or auth guards
- Never change Python logic — CSS, HTML template, and JS changes ONLY
- NEVER modify `identities.json` or any data file even for "testing"

---

## DELIVERABLE 1: Mobile Responsiveness (PRIORITY 1)

The app is currently "almost unusable" on mobile. Users can't navigate fast enough to demo it. Fix these specific issues:

### 1A. Focus Mode Cards — Too Wide on Mobile
The Focus mode identity card (the big card with face + suggestions) overflows on mobile. Fix:
```
/* Mobile: full width, no horizontal scroll */
@media (max-width: 640px) {
    /* Identity card should be max-width: 100vw with padding */
    /* Suggestion cards should stack vertically, not side-by-side */
    /* Action buttons should be full-width, stacked */
}
```

**Specific changes needed in `app/main.py`:**
- Find the Focus mode card rendering (search for `view=focus` or `focus_card` or `_render_focus`)
- The Similar Identities section: on mobile, each suggestion should be a full-width row, not a card grid
- Action buttons (Merge, Not Same, Compare): on mobile, make them full-width stacked buttons with `w-full` and adequate spacing

### 1B. Touch Targets — Action Buttons Too Small
Find ALL action buttons in the triage flow and ensure they have minimum 44px touch targets:
```python
# BEFORE (too small):
Button("Merge", cls="px-2 py-1 text-xs ...")
# AFTER:
Button("Merge", cls="px-4 py-3 text-sm sm:px-2 sm:py-1 sm:text-xs ...")
```

Apply to these button patterns across ALL files:
- Merge / Not Same / Compare buttons in suggestions
- Skip / Confirm / Reject in speed-run
- Close / Dismiss buttons on modals
- Navigation arrows (prev/next)
- Photos / Faces / Similar / Tree / Profile pill buttons on identity cards

Search pattern: `Button(` with `px-2 py-1` or `px-2.5 py-1` — these are all too small for mobile.

### 1C. Text Readability on Mobile
- Body text: minimum `text-sm` (14px), never `text-xs` (12px) for primary content on mobile
- Labels/badges can stay `text-xs` but add `sm:text-xs text-sm` pattern
- Identity names: `text-lg sm:text-base` (bigger on mobile for readability)
- Distance/match scores: ensure they're readable — `text-sm` minimum

### 1D. Horizontal Overflow Prevention
Add to the page layout wrapper:
```css
body, .main-content {
    overflow-x: hidden;
    max-width: 100vw;
}
```
Search for any element with fixed widths (`w-[600px]`, `min-w-[500px]`, etc.) and add responsive alternatives.

### 1E. Card Spacing on Mobile
- Identity cards in grid: `gap-2 sm:gap-4` (tighter on mobile)
- Face crops in suggestions: `gap-2 sm:gap-3`
- Action button groups: `gap-2 sm:gap-1` (more spacing on mobile for fat fingers)

---

## DELIVERABLE 2: Delightful Micro-Interactions (PRIORITY 2)

These should make the app feel designed and modern, not like AI slop.

### 2A. Page Transition Smoothness
Add to global CSS (in `hdrs` Style element):
```css
/* Smooth HTMX swaps */
.htmx-swapping {
    opacity: 0;
    transition: opacity 200ms ease-out;
}
.htmx-settling {
    opacity: 1;
    transition: opacity 200ms ease-in;
}
.htmx-added {
    opacity: 0;
    animation: fadeSlideIn 300ms ease-out forwards;
}
@keyframes fadeSlideIn {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
}
```

### 2B. Button Press Feedback
ALL buttons should have tactile feedback. Add to global CSS:
```css
button, [role="button"], a.btn {
    transition: all 150ms cubic-bezier(0.4, 0, 0.2, 1);
}
button:active, [role="button"]:active {
    transform: scale(0.97);
}
```

### 2C. Card Hover States
Identity cards should subtly lift on hover (desktop only):
```css
.identity-card {
    transition: all 300ms cubic-bezier(0.4, 0, 0.2, 1);
}
@media (hover: hover) {
    .identity-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px -5px rgba(0,0,0,0.3);
    }
}
```

### 2D. Loading Skeleton Shimmer
For any area that loads via HTMX, add a shimmer animation:
```css
.htmx-indicator, .loading-skeleton {
    background: linear-gradient(90deg, #1e293b 25%, #334155 50%, #1e293b 75%);
    background-size: 200% 100%;
    animation: shimmer 1.5s ease-in-out infinite;
}
@keyframes shimmer {
    0% { background-position: -200% 0; }
    100% { background-position: 200% 0; }
}
```

### 2E. Success/Action Feedback
When a merge/confirm/skip succeeds, the card should animate out:
```css
.action-success {
    animation: slideOutFade 300ms ease-in forwards;
}
@keyframes slideOutFade {
    to { opacity: 0; transform: translateX(30px) scale(0.95); }
}
```
Add class `action-success` to the card wrapper when it's being replaced by HTMX.

### 2F. Scroll-Triggered Face Crop Zoom
Face crops in the grid should have a subtle entrance animation when they scroll into view:
```css
.face-crop-enter {
    opacity: 0;
    transform: scale(0.9);
    transition: all 400ms cubic-bezier(0.4, 0, 0.2, 1);
}
.face-crop-enter.visible {
    opacity: 1;
    transform: scale(1);
}
```
Add a small IntersectionObserver script:
```javascript
document.addEventListener('DOMContentLoaded', () => {
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(e => {
            if (e.isIntersecting) {
                e.target.classList.add('visible');
                observer.unobserve(e.target);
            }
        });
    }, { threshold: 0.1 });
    document.querySelectorAll('.face-crop-enter').forEach(el => observer.observe(el));
});
```

---

## HOW TO APPLY CHANGES

Use Python scripts to do find-and-replace. This is the most reliable method:
```python
with open("app/main.py") as f:
    content = f.read()
content = content.replace("old_pattern", "new_pattern")
with open("app/main.py", "w") as f:
    f.write(content)
```

For CSS additions, find the `Style("""` blocks in `hdrs` and append your CSS.
For JS additions, add new `Script("""...""")` elements in the `hdrs` tuple.

---

## IMPORTANT: DO NOT STOP EARLY

You have a LOT of work to do. This is not a 5-minute task. You should:
1. Start with mobile responsiveness (Priority 1) — this is the most impactful
2. Then add micro-interactions (Priority 2)
3. For EACH file, make ALL the changes, not just 2-3
4. Test by reading the HTML output — grep for your CSS classes to verify they're applied
5. Do NOT commit until you've made changes to ALL 5 files
6. Do NOT say "I'll leave the rest for later" — do it ALL now

**Expected scope: 100-200 line changes across 5 files. If you've only changed 20 lines, you're not done.**

---

## VERIFICATION BEFORE COMMIT

Before committing, verify:
1. `grep -c "py-3\|min-h-\[44px\]" app/main.py` — should show increased touch targets
2. `grep -c "sm:text-xs text-sm\|text-sm sm:text-xs" app/main.py` — mobile text sizes
3. `grep "shimmer\|fadeSlideIn\|slideOutFade" app/main.py` — animation CSS exists
4. `grep "overflow-x: hidden\|max-width: 100vw" app/main.py` — overflow prevention
5. Changes in ALL 5 files, not just 1 or 2

---

## COMMIT (only after ALL changes are made)
```bash
git add app/main.py app/page_routes.py app/person_routes.py app/browse_routes.py app/identity_routes.py
git commit -m "[antigravity] feat(ux): session 129 — mobile responsiveness + micro-interactions

- Mobile touch targets: 44px minimum on all action buttons
- Mobile text: text-sm minimum for readability
- Mobile overflow: overflow-x hidden, max-width 100vw
- Mobile cards: responsive spacing, stacked layouts
- Micro-interactions: HTMX swap animations, button press feedback
- Card hover lift, loading shimmer, success slide-out
- Scroll-triggered face crop entrance animation"
```
