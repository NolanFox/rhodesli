# Rhodesli Development Practices

## Evolution of Our Approach

### Phase 1: Monolithic Prompts (Sessions 1-16)
- Single large prompts describing all work for a session
- Verification: unit tests only
- Problem: tests passed but UX broke. "1,200 tests passing" became a false signal.

### Phase 2: Parallelized Prompts with Manual Testing (Sessions 17-22)
- Track-based organization (A: bugs, B: features, C: UX, etc.)
- Added Playwright screenshots for visual verification
- Problem: still reactive — fixing bugs as found rather than specifying behavior upfront

### Phase 3: Spec-Driven Development (Session 24c onward)
- PRD → Acceptance Tests → Implementation → Verification
- Phase gates replace line-by-line review
- Playwright e2e tests as "definition of done"
- Research basis: see below

## Research: Why This Matters (Feb 2026)

### The Vibe Coding Problem
A December 2025 CodeRabbit analysis of 470 GitHub PRs found AI co-authored code
had ~1.7x more major issues than human-written code, with elevated logic errors
and security vulnerabilities.

The METR randomized controlled trial (July 2025) found experienced developers
were 19% slower with AI tools despite believing they were 20% faster.

The pattern: AI dramatically increases code output velocity while making
verification harder. Without structured specification, bugs compound faster
than they're caught.

### Spec-Driven Development
SDD separates planning from execution. Instead of reviewing every edit,
you review at structured phase gates. This was formalized by multiple
teams in late 2025 / early 2026:

- Wataru Takahashi (Jan 2026): "Reduce Approval Overhead & Context Switching
  with Sub-Agents" — phase gates replace per-edit review
- Thoughtworks (Dec 2025): "A specification should explicitly define external
  behavior — input/output mappings, preconditions, state machines"
- Addy Osmani: "The spec file persists between sessions, anchoring the AI
  whenever work resumes"
- Alex Opalic (Jan 2026): "The spec becomes the source of truth... a Pin
  we can use if something went wrong during implementation"

### Key Insight for Rhodesli
Our specific failure mode: endpoint-level unit tests (returns 200, JSON is valid)
passing while the rendered HTMX UI is broken (forms don't submit, modals loop,
state doesn't persist visually). Browser-level e2e tests are the only way to
catch this class of bug.

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-02-13 | Adopt SDD for all UX work | 24 sessions of evidence that unit tests alone miss UX bugs |
| 2026-02-13 | PRDs required before implementation | Prevents whack-a-mole bug fixing, gives Claude Code complete context |
| 2026-02-13 | Playwright e2e as definition of done | Bridges gap between "endpoint works" and "human can use it" |
| 2026-02-13 | Phase gates over per-edit review | Reduces approval fatigue, maintains quality through upfront planning |
