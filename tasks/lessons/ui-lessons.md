# UI, HTMX & Frontend Lessons

Lessons about HTMX patterns, event delegation, FastHTML, CSS, and UX bugs.
See also: `.claude/rules/ui-scalability.md`

---

### Lesson 5: Indentation bugs when wrapping code in conditionals
- **Mistake**: When wrapping a `for` loop body inside `if has_dimensions:`, only the first few lines of the loop body were re-indented. The rest stayed at the outer level, causing them to run once after the loop instead of per-iteration.
- **Rule**: When adding a new conditional wrapper around existing code, verify EVERY line in the block got re-indented. Check the last line of the block specifically.
- **Prevention**: After any indentation change, read the full block end-to-end and confirm the closing lines are at the correct depth.

### Lesson 12: Email clients strip `<style>` blocks — always use inline styles
- **Mistake**: Email template buttons used `class="button"` with styles defined in `<style>` block. Gmail, Outlook, and Apple Mail stripped the `<style>` block, making buttons invisible/unreadable.
- **Rule**: All styling on email `<a>` buttons MUST use inline `style=` attributes.
- **Prevention**: Use `style="display: inline-block; background-color: #2563eb; color: #ffffff !important; ..."` directly on the element.

### Lesson 20: Parallel subagents can safely edit the same file
- **Observation**: 5 agents edited `app/main.py` simultaneously, each touching different functions. All changes merged cleanly because each agent re-reads the file before editing.
- **Rule**: When parallelizing work on a single large file, assign each agent to distinct functions/sections. The Edit tool's unique-string matching prevents conflicts.
- **Prevention**: In task prompts, be explicit about which sections/functions each agent owns.

### Lesson 23: No single doc file should exceed 300 lines
- **Mistake**: `docs/SYSTEM_DESIGN_WEB.md` grew to 1,373 lines / 47.6k chars. Claude Code warned: "Large docs/SYSTEM_DESIGN_WEB.md will impact performance (47.6k chars > 40.0k)". It wasted context window every session.
- **Rule**: Split documentation into focused sub-files (<300 lines each). Use progressive disclosure: CLAUDE.md points to docs, doesn't inline them.
- **Prevention**: Before any doc update, check `wc -l` on the target file. If it's over 250 lines, split before adding content.

### Lesson 24: CLAUDE.md is loaded into every context window — keep it under 80 lines
- **Mistake**: CLAUDE.md grew with inline architecture details that belonged in separate docs.
- **Rule**: CLAUDE.md should be a "project constitution" — rules, key pointers, workflow. Details go in `docs/` files referenced by `@` directives.
- **Prevention**: After editing CLAUDE.md, run `wc -l CLAUDE.md` and verify < 80 lines.

### Lesson 26: CHANGELOG must be updated every session, not retroactively
- **Mistake**: 9+ commits across 3 sessions went without CHANGELOG updates. Had to reconstruct entries retroactively from git log.
- **Rule**: Update CHANGELOG.md before ending any session that includes user-visible changes. Group by version with Keep a Changelog format.
- **Prevention**: Added rule #9 to CLAUDE.md Rules section. The rule already existed in CODING_RULES.md but was buried and not enforced.

### Lesson 34: HTMX ignores formaction — use hx_post on each button
- **Mistake**: Multi-merge form used `hx_post` on `<form>` and `formaction` on buttons. HTMX always used the form's `hx_post`, ignoring `formaction`.
- **Rule**: When a form has multiple submit buttons with different URLs, put `hx_post` on each button with `hx_include="closest form"`.
- **Prevention**: Never use HTML `formaction` attribute with HTMX forms.

### Lesson 35: toggle @checked modifies HTML attribute, not JS property
- **Mistake**: Hyperscript `toggle @checked on <input/>` toggles the HTML attribute, but `FormData` reads the JS `.checked` property. Checkboxes appeared checked but weren't included in form data.
- **Rule**: For checkbox state changes, use property assignment: `set el.checked to my.checked`
- **Prevention**: When controlling checkboxes via Hyperscript, always use property syntax, not attribute syntax.

### Lesson 39: Event delegation is the ONLY stable pattern for HTMX apps
- **Observation**: Lightbox arrows broke 3 times because each fix re-bound to DOM nodes that HTMX later swapped. The permanent fix uses ONE global listener on `document` with `data-action` dispatch.
- **Rule**: ALL JS event handlers in HTMX apps MUST use global event delegation via `data-action` attributes. NEVER bind directly to DOM nodes that HTMX may swap.
- **Prevention**: Added to CLAUDE.md as a non-negotiable rule. Smoke tests verify `data-action` attributes exist.

### Lesson 40: Parallel subagents work well for independent DOM fixes
- **Observation**: 3 subagents fixed BUG-001, BUG-002, and BUG-004 simultaneously, each touching different functions in the same file. All changes merged cleanly. Combined test count went from 663 to 716.
- **Rule**: When UI bugs are in distinct functions, launch parallel subagents. Each should write tests first, then implement, then verify no regression.
- **Prevention**: Use this pattern for future independent UI fixes.

### Lesson 45: Every identity state must have a defined click behavior
- **Mistake**: Lightbox face overlays were plain `<div>` elements for non-highlighted faces — no click handler, no cursor change. Confirmed faces worked because the main photo viewer had logic, but the lightbox used a simpler renderer that skipped interactivity.
- **Rule**: Every face overlay in every view (photo viewer, lightbox, grid card) must have: (1) cursor-pointer, (2) a click handler appropriate for its state, (3) a tooltip showing the identity name.
- **Prevention**: When creating a new face overlay rendering path, copy the interaction pattern from the canonical `_build_photo_view_content()`, don't simplify.

### Lesson 46: Navigation links must derive section from identity state, not hardcode
- **Mistake**: `neighbor_card` and `identity_card_mini` hardcoded `section=to_review` in all links. When skipped faces used Find Similar, clicking a neighbor routed to the empty Inbox instead of the skipped section.
- **Rule**: Use `_section_for_state(identity.get("state"))` for all identity navigation links. Never hardcode a section.
- **Prevention**: Created canonical `_section_for_state()` helper. Grep for `section=to_review` periodically to catch new hardcoded links.

### Lesson 57: FastHTML `cls` is stored as `class` in `.attrs`
- **Mistake**: After creating a FastHTML `Div(cls="...")`, tried to modify via `card.attrs["cls"]` — KeyError. FastHTML maps the `cls` kwarg to `class` in the attrs dict.
- **Rule**: Access `element.attrs["class"]` (not `"cls"`) to read/modify CSS classes on FastHTML elements after creation.
- **Prevention**: Added to `.claude/rules/ui-scalability.md` as a rule.

### Lesson 62: Triage by actionability, not chronology
- **Mistake**: The inbox showed all items sorted by creation date. Admin had to scroll past 60+ unidentified faces to find the one that had an ML match at 0.61 distance — a near-certain identification.
- **Rule**: Sort the inbox by actionability: confirmed matches first (one-click merge), then proposals (high-confidence), then promotions (new evidence), then unmatched. The admin's time is best spent on the highest-confidence actions.
- **Prevention**: Focus mode `_focus_sort_key` now uses 6-tier priority. Triage bar shows counts by category with filter links.

### Lesson 63: Filters must be preserved across all navigation paths
- **Mistake**: Match mode ignored `?filter=` entirely — `_get_best_match_pair()` had no filter parameter. Up Next thumbnails linked to `?current=UUID` without `&filter=X`, so clicking navigated to the unfiltered context. Promotion banners had empty `promotion_context` because grouping code never set it.
- **Rule**: When a filter parameter (`?filter=X`) is active, every UI element must respect it: main content, Up Next thumbnails, action buttons, Skip button, and the decide endpoint. Breaking filter context is disorienting.
- **Prevention**: Match mode now passes filter through the full HTMX chain. `identity_card_mini` accepts `triage_filter` param. Rule added to `.claude/rules/ui-scalability.md`.

### Lesson 64: Toasts inside modals are invisible if z-index is wrong
- **Mistake**: `#toast-container` had `z-50` while `#photo-modal` had `z-[9999]`. Non-admin "Suggest" button in the face tag dropdown POSTed successfully to `/api/annotations/submit`, annotation was saved, toast was returned — but the toast rendered BEHIND the photo modal. User saw "nothing happens."
- **Rule**: Toast container must ALWAYS have the highest z-index in the app — above all modals, overlays, and dropdowns. Any action inside a modal that returns a toast will be invisible if the toast z-index is lower.
- **Prevention**: Z-index hierarchy is now: toast(10001) > guest-modal(10000) > photo-modal(9999). Comment in `photo_modal()` documents the hierarchy.
