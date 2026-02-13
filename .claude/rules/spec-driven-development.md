# Spec-Driven Development (SDD) — Rhodesli Project Rules

## Why This Exists (Feb 2026)

After 24 sessions we learned that:
- 1,800+ unit tests can pass while critical user flows are broken
- Claude Code reliably builds what's specified, but specifications were often absent
- The gap between "endpoint returns 200" and "human can complete the journey" was not being tested
- Feedback → implementation without specification leads to whack-a-mole bug fixing

## The SDD Workflow

Every session that changes application behavior MUST follow these phases:

### Phase 1: PRD (Human reviews before proceeding)
- Location: `docs/prds/[feature-name].md`
- Contains: problem statement, user flows (step by step), acceptance criteria, data model changes, out of scope, priority order
- Template: `docs/templates/PRD_TEMPLATE.md`
- The PRD is the source of truth. Implementation must match the PRD.

### Phase 2: Acceptance Tests (Human reviews before proceeding)
- Write Playwright e2e tests BEFORE any implementation
- Tests describe the user journey from the PRD
- Tests MUST fail initially (they describe behavior that doesn't exist yet)
- Location: `tests/e2e/`
- These tests are the "definition of done"

### Phase 3: Implementation (Claude Code runs, human reviews at end)
- Implement against the acceptance tests
- Auto-approve is acceptable — the spec gates already caught design issues
- Commit after every individual fix (small, atomic commits)
- Unit tests must pass after every commit

### Phase 4: Verification (Human reviews)
- All unit tests pass
- All acceptance tests pass
- Human does a 2-minute smoke test in the browser (incognito + logged in)
- Screenshots captured as evidence

## When SDD Is NOT Required

- Pure documentation/harness changes
- ML pipeline work (has its own workflow in `.claude/rules/ml-decisions.md`)
- Bug fixes where the expected behavior is already well-defined and the fix is < 20 lines
- Dependency updates

## Key Principles

1. **Spec is the source of truth.** If the spec and the code disagree, the spec is right (until the spec is updated).
2. **Review at phase gates, not during implementation.** Don't review every line — review the spec, review the tests, then let Claude Code implement.
3. **Browser tests > unit tests for UX work.** A unit test that verifies an endpoint returns 200 does NOT verify a human can complete the flow.
4. **Never lose real user data.** Claude Benatar's submissions, approved identities, and any community contributions must be preserved across all changes. Back up JSON data files before any migration.
