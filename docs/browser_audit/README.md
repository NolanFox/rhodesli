# Browser Audit Documentation

Contains findings from automated browser-based UX audits.
Each session produces:
- Screenshots of every audited page (screenshots/)
- Detailed findings document (session_XXX_ux_audit.md)
- Prioritized recommendations (session_XXX_ux_recommendations.md)

## Harness Connections (bidirectional breadcrumbs)
- Critical/Notable issues -> docs/ISSUES_LOG.md
- Actionable items -> BACKLOG.md (with breadcrumbs back here)
- Design decisions -> ALGORITHMIC_DECISIONS.md
- Session narrative -> docs/roadmap/SESSION_HISTORY.md

## File Size Rules
- Each audit document: max 300 lines (per harness rules)
- If audit exceeds 300 lines, split by route group
- Screenshots: PNG, referenced by relative path in markdown
