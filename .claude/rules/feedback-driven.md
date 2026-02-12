---
paths:
  - "app/main.py"
  - "docs/design/**"
  - "docs/feedback/**"
---

# Feedback-Driven Development

## At Session Start
- Read docs/feedback/FEEDBACK_INDEX.md
- Check if any active feedback items relate to this session's work
- Prioritize feedback-related fixes alongside feature work

## At Session End
- Update FEEDBACK_INDEX.md status for any feedback items addressed
- If new feedback was received, add it to the index with linked files
- If a decision was made that affects feedback (e.g., AD-037 enhancement decision), update the linked files AND the index

## Principles
- User feedback > developer assumptions
- Weight recent feedback more heavily (the app evolves)
- Don't over-index on one person's opinion, but early users have outsized insight
- Strategic feedback (adoption, engagement) is as valuable as UX feedback
- Every feedback item should trace to either: a completed fix, a planned fix, or a documented decision not to fix (with reasoning)
