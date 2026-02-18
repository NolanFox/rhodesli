# Harness Decision Provenance

Triggers: When modifying any file in .claude/rules/, CLAUDE.md,
or docs/session_logs/.

All harness engineering decisions are documented with full provenance
in docs/HARNESS_DECISIONS.md (HD-NNN format).

When making harness changes, ALWAYS:
1. Document what was chosen
2. Document what alternatives were considered and why rejected
3. Include the session number and date
4. Add breadcrumbs to the relevant rule files
5. Update both HARNESS_DECISIONS.md AND the specific rule/doc
