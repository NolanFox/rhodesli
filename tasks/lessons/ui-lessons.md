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

### Lesson 90: Script tags inside `<details>` elements don't execute reliably
- **Mistake**: Placed an inline `<script>` tag (Leaflet map init) inside a `<details open>` element via FastHTML's `_field()` wrapper. The script never executed in production, leaving a grey map area. Manual JS execution via console worked fine.
- **Rule**: Never place `<script>` tags inside `<details>` elements. Browsers may not execute them, even when the details element has the `open` attribute. Always place scripts outside collapsible containers.
- **Prevention**: Separate script from content — put the container div (map placeholder) inside `<details>` for layout, but append the init script as a sibling AFTER the `<details>` wrapper. Session 81B.

### Lesson 91: Leaflet CDN loading requires polling, not DOMContentLoaded
- **Mistake**: Used `DOMContentLoaded` as fallback for Leaflet library loading. This fails on HTMX swaps (event already fired) and when the CDN `<script src>` loads asynchronously after the inline script runs.
- **Rule**: When loading third-party libraries from CDN, use a polling approach (`setInterval`/`setTimeout` loop checking for the global) instead of relying on DOM events. Also call `map.invalidateSize()` after creation when the container may have been recently sized.
- **Prevention**: Use `tryInit()` pattern: check `typeof L !== 'undefined'` every 100ms up to 50 attempts (5s timeout). Always add `invalidateSize()` after Leaflet map creation. Session 81B.

### Lesson 92: Subtree computation must include ALL photo people, even disconnected ones
- **Mistake**: `compute_subtree_for_photo()` used BFS to find shortest paths between people in a photo. When a person (Moise Capeluto) had no graph connections to the main family cluster (Victoria/Leon), he was excluded from `path_union`. The tree button showed an empty tree because the focal person wasn't in the returned nodes.
- **Rule**: When computing a subtree for a photo, ALL people identified in the photo must appear in the result set, even if they are graph-disconnected from each other. They share a photo, so they should appear in the tree. Add disconnected people plus their immediate family for context.
- **Prevention**: After computing `path_union`, iterate ALL original `pids` and add any missing ones with their immediate family (spouses, parents, children). Session 81B.

### Lesson 93: Verify API response data matches what the JS consumer expects
- **Mistake**: After fixing the API to return 7 nodes, the tree still showed empty SVG. Investigation revealed the FOCAL person wasn't among the 7 returned nodes — the API returned connecting nodes but not the person the tree was centered on. The JS `buildHierarchy()` BFS starts from the focal person, so if that person is missing, nothing renders.
- **Rule**: When debugging a data pipeline (API → JS rendering), verify not just that data is returned, but that the SPECIFIC data the consumer needs is present. Check: (1) focal/root node exists in response, (2) relationships connect to it, (3) the consumer's traversal algorithm can reach all nodes from its starting point.
- **Prevention**: Add the focal person to the result set explicitly. Test with `console.log(nodeMap)` and verify the focal person ID is a key. Also verify node count matches expected count from API. Session 81B.

### Lesson 95: Stale JS closure state after fetch failures — fresh page navigation required, not just reload
- **Mistake**: During Session 81B Chrome verification, a 502 during deploy transition caused the tree JS (`initRhodesliTree`) to execute with a failed fetch. The function creates closure variables (`svg`, `g`, `allNodes`, `currentPersonId`) that persist. When the deploy finished and I tried to re-trigger tree rendering via `window.location.reload()` and manual JS calls, the old closures retained stale state. The SVG was recreated but data fetching used the corrupted scope.
- **Rule**: In HTMX/SPA apps with closure-heavy JS (D3 visualizations, Leaflet maps, chart libraries), a failed initial load corrupts the closure scope permanently for that page instance. `window.location.reload()` after manual DOM manipulation may not fully reset. Only a fresh page navigation (close tab + open URL, or navigate away and back) guarantees clean JS state.
- **Prevention**: (1) When debugging "feature worked before but now renders empty," check if the initial page load failed (502, network error, CDN timeout). (2) Always test with a fresh tab/navigation, not just reload. (3) Consider adding error recovery to closure-heavy JS: if fetch fails, show an explicit error message with a "Retry" button that re-initializes from scratch. Session 81B.

### Lesson 106: Over-limit docs must be SPLIT into sub-files, not trimmed
- **Mistake**: ML_SERVICE.md grew to 409 lines (limit 300). First instinct was to trim/condense content — consolidating tables, removing code examples, shortening descriptions. This loses valuable context that was carefully written.
- **Rule**: When a doc exceeds 300 lines, split it into a hub doc + sub-files in a subdirectory. The hub doc stays under 300 lines with summaries and links. Sub-files contain the full detail. Never delete content just to meet a line count — restructure instead.
- **Prevention**: (1) Create `docs/.../topic/` subdirectory with detailed sub-files. (2) Rewrite the hub doc with summaries + links to sub-files. (3) All sub-files have a `**Parent:**` link back to the hub. (4) The PostToolUse hook warns when any doc exceeds 300 lines. Example: `docs/architecture/ML_SERVICE.md` → hub + `docs/architecture/ml_service/{API,DEPLOYMENT,PIPELINE,MIGRATION}.md`. Session 94.
