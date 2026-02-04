# Interaction Testing Protocol

## Purpose
Prevent bugs where UI elements render but don't work.

This protocol was created after discovering 6 bugs in the Command Center UI where elements rendered correctly but failed when clicked. See `POST_MORTEM_UI_BUGS.md` for details.

## Core Principle

> **"Renders correctly" ≠ "Works correctly"**

Every interactive element must be tested end-to-end, not just visually.

---

## After ANY UI Change

### Step 1: Enumerate All Interactive Elements

List every element that can be:
- **Clicked** (buttons, links, images, cards)
- **Typed into** (inputs, textareas)
- **Toggled** (checkboxes, switches, dropdowns)
- **Dragged** (drag-and-drop zones)

### Step 2: Test Each Element End-to-End

For each interactive element:
1. **Click/interact** with it
2. **Verify** the EXPECTED behavior occurs
3. **Document** in checklist (PASS/FAIL)

Common failure modes:
- Link goes to non-existent route (404)
- Link uses wrong HTTP method (405)
- HTMX targets non-existent element
- JavaScript/Hyperscript references missing element
- Endpoint returns wrong content type

### Step 3: Test Navigation Flows

1. Can user get from A to B to C?
2. Can user get BACK from C to B to A?
3. Do URLs update correctly?
4. Do anchor links (`#section`) work?
5. Does browser back/forward work?

### Step 4: Test State Changes

1. Does action update the UI immediately?
2. Does action persist on refresh?
3. Does action update counts/badges in sidebar?
4. Does "next item" match visual queue?

---

## Checklist Template

For each new feature, fill this out:

```markdown
## Feature: [Name]
Date: [YYYY-MM-DD]
Branch: [branch-name]

### Interactive Elements

| Element | Action | Expected Result | Status |
|---------|--------|-----------------|--------|
| Upload button | Click | Upload page loads | [ ] |
| View Photo button | Click | Photo modal opens | [ ] |
| Face thumbnail | Click | Photo modal opens with face highlighted | [ ] |
| Confirm button | Click | Identity confirmed, next shows | [ ] |
| Skip button | Click | Identity skipped, next shows | [ ] |
| Reject button | Click | Identity rejected, next shows | [ ] |
| Find Similar button | Click | Neighbors panel loads | [ ] |
| Neighbor card | Click | Navigates to that identity | [ ] |
| Up Next thumbnail | Click | That identity loads in focus | [ ] |

### Navigation Flows

| Flow | Steps | Status |
|------|-------|--------|
| Home → Upload → Home | Click Upload, then sidebar Inbox | [ ] |
| Focus → Browse → Focus | Click View All, then Focus | [ ] |
| Confirm 3 items | Confirm, verify next shows, repeat | [ ] |

### State Persistence

| Action | UI Updates | Persists on Refresh | Counts Update |
|--------|------------|---------------------|---------------|
| Confirm | Card changes | Yes | [ ] |
| Skip | Card moves | Yes | [ ] |
| Reject | Card moves | Yes | [ ] |

### Edge Cases

- [ ] Empty state (no items to review)
- [ ] Single item (no "Up Next" queue)
- [ ] Last item (after action, shows empty state)
```

---

## Route Verification Checklist

Before adding any interactive element that calls a route:

1. **Verify route exists**
   ```bash
   grep -n "@rt.*{route}" app/main.py
   ```

2. **Verify HTTP method matches**
   - `<a href>` sends GET
   - `hx-get` sends GET
   - `hx-post` sends POST
   - `<form method="post">` sends POST

3. **Verify endpoint returns correct content**
   - HTML partial for HTMX
   - Full page for navigation
   - JSON for API calls

4. **Verify HTMX target exists**
   ```bash
   grep -n 'id="target-id"' app/main.py
   ```

---

## Common Patterns That Fail

### Pattern 1: Link to POST-only route
```python
# BUG: Link sends GET, route only handles POST
A("Upload", href="/upload")  # 405 Error

@rt("/upload")
async def post(files):  # Only POST handler
    ...
```
**Fix:** Add GET handler or use form submission

### Pattern 2: HTMX targets non-existent element
```python
# BUG: In Focus mode, #identity-xxx doesn't exist
Button(hx_get="/api/neighbors", hx_target="#identity-xxx")
```
**Fix:** Check if target exists, fallback to navigation

### Pattern 3: Display-only elements
```python
# BUG: No click handler
Img(src=crop_url, cls="w-16 h-16")  # Can't click
```
**Fix:** Wrap in Button or A with click handler

### Pattern 4: Different ordering logic
```python
# BUG: Visual queue uses Sort A, backend uses Sort B
# Visual: [Alice, Bob, Carol]
# After Skip Alice, backend returns Carol (not Bob)
```
**Fix:** Ensure all code paths use identical sorting

---

## Quick Smoke Test (2 min)

After ANY UI change, test these critical paths:

1. [ ] Click sidebar "Upload Photos" → Upload page loads
2. [ ] Click "View Full Photo" → Photo appears in modal
3. [ ] Click Confirm → Next identity appears
4. [ ] Click Skip → Next identity appears (matches visual queue)
5. [ ] Click Up Next thumbnail → That identity loads
6. [ ] Click Find Similar → Neighbors appear

If ANY fail, stop and fix before merging.
