# Session 128 Feedback

### FB-001: Face Card Expansion UX — Desktop is Broken
- **Severity:** P1
- **Context:** On desktop, clicking "Faces (N)" on a person card shows tiny face thumbnails that are too small to see details. Text labels are truncated/unreadable. The current implementation just shows small crops inline.
- **Expected behavior:** Clicking "Faces" should trigger a fluid, animated expansion:
  1. The face card smoothly expands to take the full width (and most of the height) of the viewport
  2. Other cards push up/down to make room (not just overlay)
  3. Large face crops appear inside the expanded card — big enough to see facial details
  4. The expansion should feel like a modern, designed animation (not AI slop)
  5. Think of it like a lightbox that grows FROM the card itself, not a separate modal
  6. Similar feel to how Compare should work — expanding, growing, fluid
- **Screenshot:** Provided by user — shows Sam Burd card with 6 tiny face thumbnails
- **Root cause:** Current implementation renders small inline thumbnails with no expansion animation
- **Fix:** BACKLOG — needs Antigravity prompt for CSS/JS animation work. Pattern: card flip/expand animations from modern UI frameworks (Framer Motion style, but CSS-only or minimal JS)
- **BACKLOG:** UX-250 (face card expansion animation)
