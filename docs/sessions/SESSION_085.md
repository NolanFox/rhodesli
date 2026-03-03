# Session 85: Fix Compare — End-to-End Functional Validation

Started: 2026-03-03
Prompt: docs/prompts/session-85-prompt.md
PRD: docs/prds/025_compare_functional_rebuild.md
Context: docs/session_context/session-85-context.md

## Phase Checklist
- [ ] Phase 0: Orient
- [ ] Phase 1: Diagnose + Architecture Plan
- [ ] Phase 2: Unify Compare Upload with Main Upload Pipeline
- [ ] Phase 3: Compare Against Specific Person (Search + Per-Face Scores)
- [ ] Phase 4: Fix Compare Result Page — Interactive Shareable View
- [ ] Phase 5: Tests + Regression Check
- [ ] Phase 6: Deploy + Browser Verification
- [ ] Phase 7: Session Docs

## Predecessor Verification (Session 84)
- [ ] Help Identify expansion panel spans full width
- [ ] Public Similar link still works
- [ ] Merge/Not Same from inline panel update correctly

## Phase 0: Orient
- Session number set to 85
- Prompt, PRD, and context read
- Current compare page loads (200)
- Current compare result 28f18514d9d3: shows "22% Similar" against Laura Franco Capelluto, flat list
- Confirmed: result page lacks uploaded photo, no per-face context

## Verification Gate
- [ ] All phases re-checked against original prompt
- [ ] Feature Reality Contract passed
