---
paths:
  - "app/main.py"
---

# UI Scalability Rules

## Grammar
1. **Always use singular/plural**: `f"{count} face{'s' if count != 1 else ''}"`. Never hard-code plural ("faces", "photos", "identities").

## Collections Display
2. **Collections carousel**: Use horizontal scroll (`overflow-x-auto`) for 5+ collections, grid for fewer. This pattern scales to any number of collections.
3. **FastHTML attribute access**: Use `element.attrs["class"]` (not `element.attrs["cls"]`) to modify CSS classes on FastHTML elements after creation.

## Event Delegation (CRITICAL)
4. **ALL JS event handlers MUST use global event delegation** via `data-action` attributes on `document`. NEVER bind directly to DOM nodes that HTMX may swap (Lesson #39).

## Photo/Face Display
5. **Face overlays must be interactive in ALL views** (photo viewer, lightbox, grid card) with cursor-pointer, click handler, and tooltip (Lesson #45).
6. **Navigation links must derive section from identity state** using `_section_for_state()`, never hardcode `section=to_review` (Lesson #46).

## Filter Consistency Across Views
7. **When a filter parameter (`?filter=X`) is active, ALL UI elements must respect it**: main content, Up Next, pagination, prev/next arrows. ALL navigation links must preserve it in the URL. When the filtered set is exhausted, show "All reviewed" instead of leaking other items. Never render navigation controls that point outside the filtered set (Lesson #63).
8. **Match mode must pass filter through the full chain**: initial `hx_get`, action buttons (`hx_post`), Skip button, and decide endpoint all propagate `&filter=X`.
