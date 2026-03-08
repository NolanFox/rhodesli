# Frontend Framework Migration Assessment

**Last updated:** 2026-03-07
**HD-022 reference:** Session 74 (2026-02-27)
**Status:** NOT YET TRIGGERED

---

## HD-022 Trigger Criteria

From HARNESS_DECISIONS.md HD-022:

> **Review Trigger:** If 3+ components need complex state management,
> or mobile UX still underperforms after Session 74, revisit full
> frontend framework.

---

## Current JS Embed Inventory

### Rich Interactive Components (3rd-party libraries)

| Component | Library | Location | Shared State? |
|-----------|---------|----------|---------------|
| Family tree visualization | D3.js v7 | page_routes.py (tree page) | No -- self-contained SVG |
| Social graph visualization | D3.js v7 | page_routes.py (graph page) | No -- self-contained SVG |
| Location map | Leaflet 1.9.4 | page_routes.py (map page) + main.py (auto-init) | No -- per-element init |
| PostHog analytics | PostHog JS | main.py (global snippet) | No -- fire-and-forget |

### Inline JS Embeds (vanilla JavaScript)

| Purpose | Count | Shared State? |
|---------|-------|---------------|
| Face overlay positioning/toggle | ~5 | No -- per-photo DOM manipulation |
| Photo lightbox navigation | ~3 | No -- local closure state |
| HTMX event handlers | ~8 | No -- event delegation |
| Form interactions (search, filter) | ~6 | No -- local form state |
| CSS animations (card expand, skeleton) | ~4 | No -- CSS-driven |
| Clipboard/share | ~2 | No -- one-shot actions |
| Leaflet auto-init | 1 | No -- scans DOM for data attributes |

**Total: ~43 Script() blocks across 12 route files.**

---

## Trigger Assessment

### Criterion 1: 3+ components needing shared state

**Current count of components needing shared state: 0**

All JS embeds are self-contained:
- D3 tree: receives data via JSON endpoint, renders to SVG, no external state
- D3 graph: same pattern -- independent of tree
- Leaflet map: initialized from data attributes, no cross-component communication
- PostHog: analytics-only, no UI state
- Face overlays: DOM-local, no shared state
- HTMX handlers: event delegation, server is the state manager

The key architectural insight: **HTMX makes the server the single source
of state.** JS embeds only handle rendering and user interaction within
their own DOM subtree. Cross-component communication goes through the
server via HTMX requests.

**Verdict: Trigger NOT met.** Zero components share client-side state.

### Criterion 2: Mobile UX underperforms

Mobile UX has been addressed incrementally:
- Session 82e: Mobile hamburger fix (768px breakpoint)
- Session 85c: CSS animations for card transitions
- Session 82e: Masonry grid with natural aspect ratios
- Tailwind responsive classes throughout

No systematic mobile UX audit has been conducted since Session 74, but
no P1 mobile issues have been reported by the community user (Claude Benatar)
or admin (Nolan).

**Verdict: No evidence of mobile underperformance.**

---

## Why FastHTML + HTMX Remains Appropriate

### Strengths for This Project

1. **Server-authoritative state**: Identity confirmations, merges, and
   annotations are admin-only operations. The server IS the authority.
   Client-side state management adds complexity with no benefit.

2. **No build step**: No npm, no webpack, no bundler. `git push` deploys.
   This is critical for a solo-developer project with 92+ sessions.

3. **Python-native**: All UI generation is Python. Type checking, testing,
   and refactoring use the same toolchain as the backend.

4. **HTMX partial updates**: Face card confirmations, discovery actions,
   and search all use HTMX swaps. The server renders the new HTML fragment.
   This eliminates client-side rendering bugs entirely.

5. **Progressive enhancement**: The app works without JavaScript for all
   read-only operations. JS adds interactivity (tree, map, overlays) but
   is not required for the core browse-and-identify flow.

6. **Test coverage**: 3,522 tests verify server-rendered HTML. A React
   migration would require rewriting all tests AND adding client-side
   testing (Jest, React Testing Library, Playwright).

### Where It Falls Short

1. **Inline JS is untestable**: 43 Script() blocks are not covered by
   unit tests. Only browser verification catches JS bugs.

2. **No JS hot-reload**: Changes to inline JS require server restart.
   Separate .js files would help but are not yet extracted.

3. **Large route files**: page_routes.py at 10,821 lines contains both
   Python rendering and inline JS. Hard to navigate.

4. **Animation limitations**: Complex coordinated animations (e.g.,
   multi-element transitions) are awkward with inline CSS + HTMX.
   Acceptable for current UX but would limit future ambitions.

---

## Potential Future Triggers

These scenarios could trigger the migration:

1. **Real-time collaboration**: If multiple users annotate the same photo
   simultaneously, client-side state sync (WebSockets + React) would
   be needed. Current: single admin, no collaboration.

2. **Complex drag-and-drop**: If face-to-identity assignment becomes
   drag-based (e.g., drag a face crop onto an identity card), vanilla
   JS becomes painful. Current: button-click workflow works fine.

3. **Offline support**: If the app needs to work offline (PWA), client-side
   state management is mandatory. Current: always-online is fine.

4. **Chatbot interface**: If NL Archive Query (PRODUCT-003) needs a
   streaming chat UI with message history, React would be more natural
   than HTMX. This is the most likely near-term trigger.

---

## Recommendation

**Maintain current architecture.** The HD-022 trigger is not met.

If PRODUCT-003 (chatbot) proceeds, evaluate whether it can be a
self-contained JS embed (like the D3 tree) or requires framework-level
state management. If the latter, consider a hybrid approach: React
widget embedded in the FastHTML shell, communicating via API endpoints.

**Do NOT migrate preemptively.** The cost (rewrite 3,500+ tests, rebuild
deploy pipeline, learn new framework) far exceeds the benefit at current
scale and feature set.

---

## Related Documents

- `docs/HARNESS_DECISIONS.md` HD-022 -- Original decision
- `ROADMAP.md` "Future Evaluation: Frontend Framework Migration"
- `docs/architecture/TECH_DEBT.md` -- Inline JS extraction as P3 cleanup
