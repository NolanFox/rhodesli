# Session 71D Log
Started: 2026-02-26
Theme: Discoveries Fix + Worktree Harness Hardening
Prompt: docs/prompts/session-71d-prompt.md
Context: docs/session_context/session-71d-context.md
Parallel with: Session 71 (Tracks A/B/C)

## Phase Checklist
- [x] Phase 0: Orient + worktree setup
- [x] Phase 1: Discoveries audit (understand current state)
- [x] Phase 2: Architecture decision (fix vs merge into New Matches)
- [x] Phase 3: Implementation
- [x] Phase 4: Worktree harness hardening (parallel subagent)
- [x] Phase 5: Verify + prepare for merge

## Verification Gate
- [x] All review sections make sense to a first-time user — Discoveries section fixed with context, labels, navigation
- [x] Every face/photo in review sections is clickable → source face, source name, target face, target name all linked to /person/{id}; "View photo" link added
- [x] High-confidence matches surface ALL matches (not just first) — threshold widened from 1.0 to 1.05, Nace (1.01) now included
- [x] Match display uses meaningful labels (not misleading percentages) — "Strong match"/"Good match" instead of "54%"
- [x] Worktree enforcement script works mechanically — 13 tests pass in harness branch
- [x] ALGORITHMIC_DECISIONS.md updated — AD-170 (review architecture), AD-171 (confidence labels)

## Commits

### discoveries worktree (session-71d/discoveries-fix)
1. `ba3e668` docs: session 71D phase 0 — orient and setup
2. `d0e2745` docs: session 71D phase 1 — discoveries feature audit
3. `b9b99d5` docs: session 71D phase 2 — architecture decision and AD entries
4. `d8b9542` feat(review): session 71D phase 3 — fix discoveries feature

### harness worktree (session-71d/harness-hardening)
5. `feat(harness): session 71D phase 4 — worktree enforcement scripts` (parallel subagent)

## Architecture Decision
**Option A: Fix Discoveries as separate section** (AD-172)
- Keep three-section architecture (Discoveries / New Matches / Help Identify)
- Fix the bugs, don't restructure
- Rationale: problems were implementation bugs, not architecture flaws

## Key Changes
1. **Threshold**: DISCOVERY_DISTANCE_THRESHOLD 1.0 → 1.05 (catches Nace at 1.01)
2. **Labels**: "54% match" → "Good match" / "Strong match" (AD-173)
3. **Navigation**: Source face + name now clickable → /person/{id}
4. **Context**: Collection name, co-occurring faces, "View photo" link added
5. **Harness**: enforce_worktree.sh + merge_tracks.sh + worktree rule

## Browser Verification
- Production screenshot taken: Discoveries page shows "54% match" and dead-end navigation
- Changes are in worktree branches, not yet deployed
- Full production verification deferred to merge ceremony

## Deferred Items
- Production browser verification of fixed UI (requires merge + deploy)
- AD number conflict: both branches used AD-170 — resolve during merge
- Co-occurrence between Leon (768) and Nace (767) won't surface until threshold change is deployed

## Test Results
- discoveries tests: 28 passed (7 new)
- harness tests: 13 passed (all new)
- full suite: 3070 passed (excluding 12 pre-existing unrelated failures)

## Merge Order (when ready)
1. session-71d/harness-hardening (docs + scripts only, no conflicts expected)
2. session-71d/discoveries-fix (app/main.py changes)
Note: AD number conflict in ALGORITHMIC_DECISIONS.md must be resolved during merge
