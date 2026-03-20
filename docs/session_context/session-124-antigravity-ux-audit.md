# Antigravity UX Audit — Session 124

## Priority 1: Mobile Touch Target Violations (`app/main.py:414-415`)
**Problem:** The mobile drawer close button is only ~32x32px, failing the 44px minimum touch target threshold for iOS/Android, leading to frustrating mis-clicks for users from Facebook.
**Fix:** Inflate the touch area using padding and negative margins to keep visual balance.
```python
# Before
'<button onclick="closeMobileNav()" class="text-slate-400 hover:text-white p-1" type="button" aria-label="Close menu">' +
'<svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6" ...'

# After
'<button onclick="closeMobileNav()" class="text-slate-400 hover:text-white p-3 -mr-2 -mt-2" type="button" aria-label="Close menu">' +
'<svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6" ...'
```

## Priority 1: Triage Action Buttons Unusable on Mobile (`app/cluster_review_routes.py:321`)
**Problem:** The admin individual face "Confirm" and "Reject" buttons use `py-1.5` globally. On phones, these are under 30px high, making them impossible to tap reliably.
**Fix:** Apply responsive padding making them touch-friendly (44px) on mobile but dense on desktop.
```python
# Before
cls="px-3 py-1.5 text-xs font-medium bg-emerald-700 hover:bg-emerald-600 "

# After 
cls="px-4 py-3 sm:px-3 sm:py-1.5 text-sm sm:text-xs font-medium bg-emerald-700 hover:bg-emerald-600 "
```

## Priority 2: Missing Clear Value Proposition on Landing (`app/page_routes.py:604`)
**Problem:** The hero subtitle "A heritage photo archive" is passive and doesn't instruct visitors what to do or why they are there.
**Fix:** Replace the static title with an actionable directive.
```python
# Before
P(subtitle, cls="text-lg text-amber-200/70 max-w-2xl mx-auto mb-8"),

# After
P("We need your help identifying faces in the Jewish Community of Rhodes. Select an archive below.", 
  cls="text-xl md:text-2xl text-amber-100/90 font-medium max-w-3xl mx-auto mb-10"),
```

## Priority 2: Primary CTA Blending (`app/page_routes.py:570`)
**Problem:** "Help Identify Faces" blends in with secondary buttons. It needs to command visual attention to drive the core interaction loop.
**Fix:** Add hover scaling and an ambient glow to signal interactivity.
```python
# Before
cls="inline-flex items-center justify-center px-6 py-3 bg-amber-500 hover:bg-amber-400 text-slate-950 rounded-lg font-semibold transition-colors",

# After
cls="inline-flex items-center justify-center px-6 py-3 bg-amber-500 hover:bg-amber-400 text-slate-950 rounded-lg font-semibold transition-all shadow-[0_0_15px_rgba(245,158,11,0.4)] hover:scale-105 active:scale-95",
```

## Priority 3: Keyboard Shortcuts Lack Discoverability (`app/cluster_review_routes.py:1884`)
**Problem:** Speed-run triage already supports keyboard shortcuts internally (e.g. `actionMap = {'y': 'speed-confirm'}`) and appends "(Y)" to button text. However, plain text parens blend in, making users think they must click. 
**Fix:** Wrap the shortcut hint in a distinct `<kbd>` styling element so it explicitly looks like a keyboard input.
```python
# Before
"Confirm All (Y)",

# After
Span("Confirm All ", NotStr("<kbd class='ml-1 px-1.5 py-0.5 rounded border border-white/20 bg-white/10 text-[10px] font-mono'>Y</kbd>")),
```

## Priority 3: Excessive Facial Thumbnails Scrolling (`app/person_routes.py:428`)
**Problem:** Thumbnails are fixed at `w-32 h-32` on desktop, which restricts horizontal density and forces long scroll lengths. 
**Fix:** Convert to responsive aspect-ratio blocks within a CSS grid instead of fixed-width elements.
```python
# Before
cls="w-28 h-28 sm:w-32 sm:h-32 rounded-lg object-cover border-2 border-slate-700 hover:border-emerald-500/50 transition-colors",

# After
cls="w-full aspect-[1/1] rounded-lg object-cover border-2 border-slate-700 hover:border-emerald-500/50 transition-colors",
```

## Priority 4: Disorganized Person Detail Grids (`app/person_routes.py:461`)
**Problem:** Face crops are rendered in an unstructured layout using flex layout heuristics. For identities with 50+ faces, this causes jagged misalignment across rows.
**Fix:** Apply strict CSS Grid cols formatting to the outer container. (Note: Assuming `Div(*face_gallery_items...)` is built later in the response, apply this to the wrapper).
```python
# Before (Implicit flex parent/div array wrap)
Div(*face_gallery_items, cls="flex flex-wrap gap-4 mt-4")

# After
Div(*face_gallery_items, cls="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-3 mt-4")
```

## Priority 4: Missing Emptystate for Unidentified Anchors (`app/person_routes.py:564`)
**Problem:** When rendering the social graph "Often appears with", profiles missing a photo render a harsh `?` that mimics a corrupted image link.
**Fix:** Calm the UI by indicating intentional metadata absence using a dashed silhouette.
```python
# Before
Div(Span("?", cls="text-lg text-slate-500"), cls="w-12 h-12 rounded-full bg-slate-800 border-2 border-slate-700 flex items-center justify-center")

# After
Div(cls="w-12 h-12 rounded-full bg-slate-800/50 border border-slate-700 border-dashed flex items-center justify-center opacity-70")
```

## Priority 5: Over-reliance on "Developer Tool" Slate Colors (`app/page_routes.py:757`)
**Problem:** The platform root background gradient uses harsh slate/blue tones (`#08111f`, `#0c1630`), evoking SaaS dashboard aesthetics instead of the emotional warmth required for a genealogy web archive.
**Fix:** Swap out the cool blues for deep, warm stone/sepia tones.
```python
# Before
body { background: linear-gradient(180deg, #08111f 0%, #0c1630 48%, #0a1222 100%); overflow-x: hidden; }

# After
body { background: linear-gradient(180deg, #1c1917 0%, #292524 48%, #1c1917 100%); overflow-x: hidden; }
```

## Priority 5: Lack of Micro-animations on Triage Confirmations (`app/cluster_review_routes.py:325`)
**Problem:** HTMX out-of-band swaps instantly vaporize elements from the DOM (`hx_swap="outerHTML"`). In speed-run, this creates harsh flashing snapping effects causing cognitive strain over hundreds of decisions.
**Fix:** Smooth the deletion morphologically using HTMX swapping classes native to the library.
```python
# Before
hx_swap="outerHTML",

# After
hx_swap="outerHTML swap:300ms",
cls="... htmx-swapping:opacity-0 htmx-swapping:scale-95 transition-all duration-300"
```
