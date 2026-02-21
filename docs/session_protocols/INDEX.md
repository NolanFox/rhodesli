# Session Protocols Index

When starting a session, identify the session type and read the
relevant protocol file BEFORE beginning work. Each protocol defines
logging locations, context files to read, /clear cadence, and
completion criteria.

## Session Types

| Type | Trigger | Protocol File |
|------|---------|---------------|
| Standard | Default for all coding/feature sessions | (use existing .claude/rules/) |
| Interactive | Human at computer reporting what they see; OR prompt says "interactive" / "walkthrough" / "guided" | docs/session_protocols/interactive.md |
| Browser Audit | Autonomous browser-driven UX testing; OR prompt says "browser audit" / "UX audit" / "crawl the site" | docs/session_protocols/browser-audit.md |
| Overnight | Long-running autonomous; OR prompt says "overnight" / "run while I sleep" | docs/session_protocols/overnight.md |

## How This Works
1. CLAUDE.md points here (1 hop)
2. This index routes to the right protocol (2 hops)
3. Protocol files point to relevant context files (3 hops max)

## Adding New Session Types
When a new session type emerges:
1. Create docs/session_protocols/[type].md (max 150 lines)
2. Add a row to the table above with trigger keywords
3. Add breadcrumb to HARNESS_DECISIONS.md (HD-NNN)
4. Keep this INDEX under 60 lines

## Breadcrumbs
- CLAUDE.md → this file
- HARNESS_DECISIONS.md → HD-015
- Each protocol file → relevant context files, .claude/rules/
