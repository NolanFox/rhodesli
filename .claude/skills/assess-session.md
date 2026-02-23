---
description: "Assess Claude Code session output. Use after a session completes to evaluate quality before proceeding."
disable-model-invocation: true
---
# Session Assessment Protocol

## Read the session output/transcript and evaluate:

### For each phase:
- Status: completed / skipped / partial
- If partial: what was missed and why
- Tests: how many added, total passing

### Red flag checklist:
- [ ] Data stored in JSON instead of Supabase?
- [ ] API calls made without logging model/cost/tokens?
- [ ] Gemini model drift (used Flash when Pro was specified)?
- [ ] ALGORITHMIC_DECISIONS.md not updated after ML changes?
- [ ] Tests skipped or test count decreased?
- [ ] ROADMAP/BACKLOG items silently dropped?
- [ ] Production smoke test not run?
- [ ] /compact used instead of /clear?

### Output format:
```
## Session [N] Assessment
- Duration: X minutes
- Phases: N/N completed
- Tests: +N new, NNNN total passing
- Concerns: [list]
- Follow-up needed: [list]
```
