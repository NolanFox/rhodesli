# Browser Automation — READ-ONLY on Production

Triggers: Before ANY use of mcp__claude-in-chrome__computer with action left_click,
or mcp__playwright__browser_click.

## ABSOLUTE RULE

Browser automation on production (rhodesli.nolanandrewfox.com) is **READ-ONLY**.

### ALLOWED on production:
- Screenshots (computer action=screenshot)
- Reading page content (read_page, get_page_text)
- Reading network requests (read_network_requests)
- Reading console messages (read_console_messages)
- Navigating to pages (navigate)
- JavaScript that READS data (querySelector, getAttribute, etc.)
- Scrolling, hovering, zooming

### NEVER ALLOWED on production:
- Clicking buttons that modify data (Merge, Confirm, Reject, Skip, Save, Upload, Override, Tag, Delete, Undo)
- Filling forms that submit data
- Clicking any button with hx-post, hx-put, hx-delete attributes
- JavaScript that calls fetch() with POST/PUT/DELETE methods
- ANY action that creates, modifies, or deletes data

### Why this exists (Session 111d catastrophe):
Claude clicked the Merge button on production while debugging an HTMX issue.
Two real identities were incorrectly merged. User had to manually verify the
repair. This violated the Critical Invariant: "UI never deletes a face."

### If you need to test an interaction:
1. Read the button's hx-post URL and attributes — that's sufficient for debugging
2. Ask the user to click the button while you watch the network response
3. Use curl with test data in a non-production context
4. Write a unit test that mocks the endpoint

### Enforcement:
This rule is behavioral — there is no mechanical hook that blocks browser clicks.
If you find yourself thinking "I'll just click this to test..." — STOP.
That thought is the bug. Read the DOM instead.

See: Lesson 149 in tasks/lessons.md
