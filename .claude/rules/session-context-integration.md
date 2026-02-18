# Session Context Integration

When a session planning context file exists at ~/Downloads/session_*_planning_context.md:

1. Move it to docs/session_context/
2. Extract actionable items to their destination files with breadcrumbs:
   - BACKLOG.md: new backlog items with "See docs/session_context/..." references
   - ALGORITHMIC_DECISIONS.md: new AD entries with Context: field
   - ROADMAP.md: session status updates
3. The session context file is the canonical source for research, rejected
   alternatives, and decision rationale. Other harness files POINT to it.
4. This allows future Claude Code sessions to trace back from a BACKLOG item
   or AD entry to the full research and reasoning that produced it.
