---
paths:
  - "app/main.py"
---

# UX Context Rule

Before ANY UX work, read `docs/design/UX_PRINCIPLES.md`.

## Checklist

Before shipping UX changes, verify:

1. **Navigation is bidirectional** — A→B means B→A exists. No dead ends.
2. **Mobile works** — Touch targets ≥44px, text ≥16px, no horizontal overflow
3. **ML metrics are human-readable** — No raw distances/scores shown to non-admins
4. **UI updates without refresh** — HTMX swaps, not full page reloads
5. **Visual language is consistent** — Same component looks the same across sections
6. **Context is accessible** — Photo context is ONE CLICK from any face crop
7. **Entry points behave identically** — Same component from different paths = same behavior

## Anti-Patterns

- Raw ML metrics shown to users (use confidence tiers instead)
- 200+ item scroll with no prioritization (use actionability sorting)
- Dead-end navigation (every screen must have a "back" or "next" action)
- Inconsistent behavior by entry point (see entry-point-testing.md)
- Modals too small for content (use 90vw × 90vh for Compare)
- Actions requiring page refresh (use HTMX partial swaps)

After UX work, update `docs/design/UX_PRINCIPLES.md` with new learnings.
