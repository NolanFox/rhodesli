# Interactive Session Protocol

Applies when: A human is at their computer, navigating the app,
and reporting what they see. Claude Code guides, fixes, and logs.

## Before Starting
Read these files in order:
1. CLAUDE.md (always)
2. The active session log (check docs/session_context/ for latest)
3. BACKLOG.md (know what's already tracked)
4. Any session-specific context file mentioned in the prompt

## Core Rules

### Logging
- ALL findings go to the session log file, NOT conversation memory
- Categorize: Critical / Notable / Cosmetic
- Format: `- [ ] ROUTE: Description [BACKLOG: yes/no]`
- Data changes (ML accepts/rejects) → "Data Changes" for provenance

### Context Window Management
- Run /clear after each major section
- After /clear: re-read CLAUDE.md + session log file
- Budget: one section per context window
- Git commit before every /clear

### Fix-vs-Log Decision
- Trivial (<2 min, obvious): fix in real time, commit
- Everything else: log and move on
- NEVER fix complex things mid-walkthrough

### Human Communication
- When human says "that looks wrong": ask what specifically they see
- Guide page by page — give URL and what to expect
- One page at a time

### Completion
- Update session log with section summary
- Commit with descriptive message
- Tell human to run /clear

## Session Infrastructure
- Session logs: docs/session_context/session_NNx_interactive_log.md
- Issues: docs/ISSUES_LOG.md (persistent, cross-session)
- Decisions: ALGORITHMIC_DECISIONS.md (for ML/data decisions)

## Breadcrumbs
- docs/session_protocols/INDEX.md → this file
- HARNESS_DECISIONS.md → HD-015
- .claude/rules/verification-gate.md (run at session end)
- docs/browser_audit/ (if combined with browser audit)
