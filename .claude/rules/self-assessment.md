# Self-Assessment Protocol (Mandatory)

Every session MUST end with a self-assessment phase. This cannot be
skipped, even if context is running low.

## At Session End
1. Re-read the ORIGINAL prompt from docs/prompts/session_NN_prompt.md
2. For each phase/act in the prompt:
   a. Verify it was completed (grep for expected artifacts)
   b. Verify it was tested (check for curl/browser evidence)
   c. Note any silent deferrals
3. Run the verification gate from the prompt
4. Write docs/session_context/session_NN_assessment.md:
   - What shipped (with evidence)
   - What was deferred (with reason and BACKLOG entry)
   - Red flags (with severity and recommended fix)
   - What the NEXT session should verify FIRST
5. If any red flag is fixable in < 5 min: fix it now
6. If any red flag needs BACKLOG entry: create it with breadcrumb

## Assessment Template
```
# Session NN Assessment
## Shipped
- [x] Phase 0: [description] — Evidence: [file/test/curl result]
## Deferred
- Phase X: [description] — Reason: [why] — BACKLOG: [ID]
## Red Flags
- [severity] [description] — Fix: [what to do]
## Next Session Should Verify
1. [highest priority verification]
```

## UX Feedback Collection
If screenshots were taken during the session:
1. Evaluate each screenshot against the app thesis goals
2. Log issues in docs/session_context/session_NN_ux_evaluation.md
3. P1/P2 issues -> BACKLOG with breadcrumb
4. Quick wins -> note for next session

See: docs/HARNESS_DECISIONS.md HD-015
