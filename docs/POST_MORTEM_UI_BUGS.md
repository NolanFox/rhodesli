# Post-Mortem: Command Center UI Bugs

## Summary
6 bugs discovered after implementing Command Center UI.
Root cause: Interactive elements were built but not integration-tested.

## Bug Analysis

### Bug 1: Upload Button → Method Not Allowed
- **What happened:** Sidebar link goes to `/upload`, returns 405 Method Not Allowed
- **What was tested:** Button renders with correct styling ✓
- **What was NOT tested:** Clicking the button → page loads ✗
- **Gap:** Route at line 3047-3048 only accepts POST (`async def post(...)`); sidebar link sends GET request. No GET handler exists for the upload page.

### Bug 2: View Full Photo → Stuck Loading
- **What happened:** Modal shows "Loading..." forever after clicking "View Full Photo"
- **What was tested:** Button renders with correct href ✓
- **What was NOT tested:** Endpoint actually returns content ✗
- **Gap:** `identity_card_expanded` uses `hx_get=f"/api/photo/{main_photo_id}/context"` (line 929), but this endpoint doesn't exist. The correct endpoint is `/photo/{photo_id}/partial` (line 2303).

### Bug 3: Face thumbnails not clickable
- **What happened:** Small face images in Focus mode (the 6-face preview grid) can't be clicked
- **What was tested:** Images render with correct URLs ✓
- **What was NOT tested:** Click handlers exist ✗
- **Gap:** `face_previews` are plain `Img` elements (lines 863-868) with no click handlers, buttons, or links. Built for visual display only, not interaction.

### Bug 4: Find Similar → Anchor navigation fails
- **What happened:** URL has `#identity-xxx` but page doesn't scroll to that identity
- **What was tested:** Anchor URL generated correctly ✓
- **What was NOT tested:** Target element actually exists ✗
- **Gap:** `neighbor_card` uses `href=f"#identity-{neighbor_id}"` with hyperscript `scrollIntoView` (line 1472-1476). But in Focus Mode, only ONE identity is rendered - the target `#identity-{neighbor_id}` element doesn't exist on the page because neighbors aren't rendered in Focus Mode.

### Bug 5: Up Next thumbnails not clickable
- **What happened:** Can't click "Up Next" queue thumbnails to jump to that person
- **What was tested:** Thumbnails render with correct images ✓
- **What was NOT tested:** Click handlers exist ✗
- **Gap:** `identity_card_mini` (lines 960-983) returns a plain `Div` with an `Img` inside - no click handlers, no `hx-get`, no buttons. Same issue as Bug 3: built for display, not interaction.

### Bug 6: Skip goes to wrong person
- **What happened:** After Skip, shows 4th person in queue instead of 2nd
- **What was tested:** Skip action successfully changes state ✓
- **What was NOT tested:** Next person matches visual queue order ✗
- **Gap:** Two sorting algorithms that appear identical but have different inputs:
  - `render_to_review_section` (line 995-998) sorts `to_review` by face count and takes first 10
  - `get_next_focus_card` (line 1149-1152) fetches a FRESH list from registry and sorts by face count
  - The fresh list may have different items (e.g., the skipped item is excluded) which changes the relative ordering of remaining items
  - Also: both use `sorted()` which creates a new list, but if there are ties in face count, the order depends on original list order which may differ

## Root Cause Pattern

All bugs share a common pattern: **"Renders correctly" was assumed to mean "Works correctly"**

| Bug | What Rendered | What Failed |
|-----|---------------|-------------|
| 1 | Upload button | Click → page load |
| 2 | View Photo button | Click → photo loads |
| 3 | Face thumbnails | Click → any action |
| 4 | Anchor links | Navigate → scroll/show |
| 5 | Queue thumbnails | Click → any action |
| 6 | Visual queue order | Backend ordering match |

## Lessons Learned

1. **Every clickable element must be tested end-to-end** - rendering is not enough
2. **"Renders correctly" ≠ "Works correctly"** - the gap between visual and functional is where bugs hide
3. **Visual order must match backend logic** - when displaying a queue, the next item shown must match what the backend returns
4. **New code using existing endpoints must verify those endpoints exist** - copying patterns from other code can reference non-existent endpoints
5. **Focus Mode vs Browse Mode creates navigation complexity** - anchor links that work in Browse Mode fail in Focus Mode because elements don't exist

## Contributing Factors

1. **No manual testing of the new UI** before merging - only syntax checking and server startup
2. **Copy-paste patterns** from other parts of codebase without verifying endpoints
3. **Assumed FastHTML components** (like `Img`, `Div`) would work the same as interactive elements
4. **Two separate code paths** for displaying (render_to_review_section) and advancing (get_next_focus_card) without shared ordering logic

## Prevention Protocol

See `docs/INTERACTION_TESTING_PROTOCOL.md` for the testing protocol to prevent these issues.
