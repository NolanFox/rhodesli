# Session 128 Antigravity — Face Card Expansion Animation

You are improving the face card UX on the Rhodesli heritage photo archive People grid. The app uses FastHTML + HTMX + Tailwind CSS with a dark theme (slate-900 background, indigo/amber accents).

## CRITICAL: Branch First
```bash
git checkout session-128/antigravity-polish
```
You should already be on this branch. Verify with `git branch --show-current`.

## YOUR FILES (only modify these)
- `app/main.py` — the people grid rendering (where face cards live)

## THE PROBLEM

On the People grid (`/c/{community}/?section=confirmed`), each person card has a "Faces (N)" button that shows face thumbnails. Currently, clicking it shows tiny inline thumbnails that are too small to see facial details. The text labels are truncated. It looks like AI slop.

## WHAT WE WANT

When a user clicks "Faces (N)" on a person card, the card should **expand dramatically with a fluid animation**:

### The Expansion Animation
1. **The card grows**: The clicked card smoothly expands to take the **full width of the grid area** (spanning all columns). It should grow from its current position — not jump or teleport.
2. **Other cards reflow**: Cards above/below smoothly push apart to make room. This happens naturally with CSS grid/flexbox when the card changes size.
3. **Faces appear large**: Inside the expanded card, face crops display at **w-24 h-24 minimum** (ideally w-32 h-32) — large enough to actually see facial details and expressions.
4. **Smooth transition**: Use `transition-all duration-500 ease-out` on the card. The expansion should feel like a "breathing" motion — organic, not mechanical.
5. **Collapse**: Clicking "Faces" again (or a close button) smoothly collapses back to the original card size.

### Technical Approach — CSS Grid + JavaScript

The People grid likely uses a CSS grid or flex layout. Here's the approach:

**Option A: Grid column-span (preferred)**
```css
/* Normal card */
.person-card {
    transition: all 500ms cubic-bezier(0.4, 0, 0.2, 1);
}

/* Expanded card — spans all columns */
.person-card.expanded {
    grid-column: 1 / -1;  /* span full width */
    z-index: 10;
}
```

**Option B: If not using CSS grid**, use JavaScript to:
1. Get the card's current position with `getBoundingClientRect()`
2. Apply `position: fixed` briefly at the exact same position
3. Animate to `width: 100%; left: 0;` using CSS transitions
4. After animation, switch to `position: relative; grid-column: 1 / -1;`

### Face Display Inside Expanded Card
```
+-------------------------------------------------------------+
|  [Large Name]  CONFIRMED  [Close x]                          |
|                                                               |
|  +------+  +------+  +------+  +------+  +------+           |
|  |      |  |      |  |      |  |      |  |      |           |
|  | Face |  | Face |  | Face |  | Face |  | Face |           |
|  |  1   |  |  2   |  |  3   |  |  4   |  |  5   |           |
|  |      |  |      |  |      |  |      |  |      |           |
|  +------+  +------+  +------+  +------+  +------+           |
|  "Good"    "Good"    "Excl"    "Good"    "Fair"              |
|                                                               |
|  [Photos]  [Similar]  [Tree]  [Profile]                      |
+-------------------------------------------------------------+
```

- Face crops: `w-28 h-28 sm:w-32 sm:h-32 rounded-2xl object-cover shadow-lg`
- Quality labels: full text visible, `text-sm` not `text-[10px]`
- Wrap faces in a flex container: `flex flex-wrap gap-4 justify-center`
- The card background gets a subtle highlight: `ring-2 ring-indigo-500/30`

### JavaScript (use event delegation)
```javascript
// MUST use event delegation — HTMX swaps kill direct bindings
document.addEventListener('click', function(e) {
    const facesBtn = e.target.closest('[data-action="toggle-faces"]');
    if (!facesBtn) return;

    const card = facesBtn.closest('.person-card');
    if (!card) return;

    // Collapse any other expanded card first
    document.querySelectorAll('.person-card.expanded').forEach(c => {
        if (c !== card) c.classList.remove('expanded');
    });

    card.classList.toggle('expanded');
});
```

Add `data-action="toggle-faces"` to the Faces button.
Add class `person-card` to each card wrapper.

### CSS (add as a Style element in hdrs or inline)
```css
.person-card {
    transition: all 500ms cubic-bezier(0.4, 0, 0.2, 1);
}
.person-card.expanded {
    grid-column: 1 / -1;
    z-index: 10;
}
.person-card .faces-expanded {
    display: none;
    opacity: 0;
    transition: opacity 300ms ease-in;
}
.person-card.expanded .faces-expanded {
    display: flex;
    opacity: 1;
}
.person-card .faces-compact {
    display: flex;
}
.person-card.expanded .faces-compact {
    display: none;
}
```

### What This Replaces
Find the current faces rendering (the small inline thumbnails shown when "Faces (N)" is clicked). The current implementation likely uses HTMX to swap in face thumbnails. Replace it with:
1. **Always render both views** — compact (small count badge) and expanded (large face grid)
2. Use CSS to toggle between them based on the `.expanded` class
3. This avoids any HTMX swap lag — pure CSS, instant feel

### Design Details
- **Easing**: `cubic-bezier(0.4, 0, 0.2, 1)` — Google Material motion curve, feels natural
- **Duration**: 400-500ms for the card expansion, 200-300ms for face opacity fade-in (staggered so faces appear AFTER card has mostly expanded)
- **Shadow**: Expanded card gets `shadow-2xl shadow-black/50` — lifts off the page
- **Close button**: Top-right corner of expanded card, `x` with `hover:bg-slate-700 rounded-full p-1`
- **Background dim**: Optional but nice — other cards get `opacity-50` when one is expanded

## REFERENCE: What Makes It Feel "Designed" (Not AI Slop)
1. **Easing curves** — never use `linear` or plain `ease`. Use `cubic-bezier(0.4, 0, 0.2, 1)` or `ease-out`.
2. **Staggered timing** — card expands first (400ms), then faces fade in (200ms delay + 200ms duration)
3. **Subtle ring/glow** on the expanded card — `ring-2 ring-indigo-400/20`
4. **Consistent rounding** — `rounded-2xl` on everything
5. **Motion feels organic** — starts fast, decelerates at the end (ease-out)
6. **One thing moves at a time** — don't animate everything simultaneously

## DO NOT TOUCH
- `core/` — frozen
- `data/` — frozen, never modify
- `tests/` — don't touch existing tests
- Never use `--no-verify` on commits
- Never remove `_check_admin` calls or change route paths
- Never change Supabase queries or auth guards
- Never change Python logic beyond HTML/CSS/JS template changes

## IMPORTANT CONTEXT
The People grid is rendered in `app/main.py`. Search for the function that renders person cards in the grid. It's likely called something like `_render_person_card`, `_person_card`, `_identity_card`, or similar. The grid itself may be rendered by `_render_people_grid`, `_browse_people`, or the `/browse` route handler.

The "Faces (N)" button currently triggers an HTMX swap. You need to find:
1. The button that says "Faces (N)"
2. The target element where face thumbnails appear
3. The endpoint that returns the face thumbnails

Then modify the rendering so BOTH compact and expanded views are always in the HTML, toggled by CSS class.

## COMMIT
```bash
git add app/main.py
git commit -m "[antigravity] feat(ux): session 128 — face card expansion animation"
```
