# Browser Audit Protocol

Applies when: Claude Code drives a browser autonomously to test
routes, interactions, and UX quality.

## Before Starting
Read these files in order:
1. CLAUDE.md (always)
2. docs/session_context/session_49b_browser_automation_context.md
3. The active session log
4. BACKLOG.md

## Browser Tool Selection (Dual-Path)

### Try Claude in Chrome FIRST
- Handles OAuth auth automatically (uses logged-in session)
- Connection test: navigate to app URL + screenshot
- If "Browser extension not connected": troubleshoot max 3 min
  (see context file for steps), then fall back

### Fallback: Playwright MCP
- `claude mcp add playwright npx @playwright/mcp@latest`
- Fresh browser — PAUSE for human to log in manually
- Restrict to 4 tools: browser_navigate, browser_snapshot,
  browser_click, browser_take_screenshot
- Avoid the other 22 tools (decision paralysis)

### Log which tool was used

## Per-Route Audit Sequence
1. Navigate to route
2. Screenshot → docs/browser_audit/screenshots/
   Naming: [session]_[route]_[state].png
3. Check console for JS errors
4. Test every interactive element
5. Evaluate UX (hierarchy, consistency, dead ends, first-time user)
6. Check accessibility (alt text, headings, labels)
7. Log findings immediately to audit document

## Context Management
- Budget: ~5 routes per context window
- Group routes by function, /clear between groups
- Screenshots save to disk (never embed in context)

## Output Files
- Audit: docs/browser_audit/session_NNN_ux_audit.md (max 300 lines)
- Recommendations: docs/browser_audit/session_NNN_ux_recommendations.md
- Screenshots: docs/browser_audit/screenshots/

## Completion: Synthesis Pass
After /clear, read all findings and:
1. Create prioritized recommendations (P1-P4)
2. Update ISSUES_LOG.md, BACKLOG.md (bidirectional breadcrumbs)
3. Verify breadcrumbs with grep check
4. Print summary report

## Breadcrumbs
- docs/session_protocols/INDEX.md → this file
- docs/session_context/session_49b_browser_automation_context.md
- docs/browser_audit/README.md
- HARNESS_DECISIONS.md → HD-015
