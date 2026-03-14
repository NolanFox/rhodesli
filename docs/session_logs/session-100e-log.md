# Session 100e Log — Fox Family Triage Sprint
Started: 2026-03-14 00:42
Prompt: docs/prompts/session-100e-prompt.md

## Phase Checklist
- [x] Phase 0: Orient — health OK, current_session set
- [-] Phase 1: Nolan Triages
- [ ] Phase 2: Real-Time Fixes
- [ ] Phase 3: Post-Triage Analysis
- [ ] Phase 4: Session Closeout

## Triage Progress
| # | Identity | Faces | Action | Notes |
|---|----------|-------|--------|-------|
| 1 | Person 2986 | 44 | PENDING | Charles Fox (Roland's brother) — all look correct |

## Feedback Log

### FB-1: Can't see all faces in cluster (P1)
- **Issue:** "+36" overflow — only 8 faces visible, can't verify if cluster is pure (e.g. Albert Fox mixed in with Charles Fox)
- **Impact:** User can't confidently confirm without seeing all faces
- **Fix:** Expand all faces or add scrollable gallery view

### FB-2: Crops not clickable to source photo (P1)
- **Issue:** No way to click a face crop to see the full source photo for context
- **Impact:** Can't verify ambiguous faces against full photo

### FB-3: No way to name or GEDCOM-link from speed-run (P1)
- **Issue:** After confirming, no prompt to name the person or link to GEDCOM record
- **Impact:** Confirmed clusters stay as "Unidentified Person NNNN" — requires separate workflow to name

### FB-4: Workflow unclear (UX)
- **Issue:** User doesn't know what order to do things — confirm first then name? Name first?
- **Current state:** Speed-run only does confirm/reject, naming is a separate step

### FB-5: No merge capability in speed-run (P1)
- **Issue:** When a cluster is the same person as one already confirmed, no way to merge in-flow
- **Impact:** User must do a separate merge pass after triage — doubles the work
- **Fix:** Add "Merge with..." button that searches existing identities, or auto-suggest matches

### FB-6: Age-based cluster splitting (P2 — ML)
- **Issue:** Same person at different ages creates separate clusters (e.g. Charles Fox x3)
- **Impact:** More clusters to review, more merges needed
- **Related:** PRD-038 longitudinal face modeling (rollout gates still closed)

### FB-7: Speed-run workflow unclear (P1 — UX)
- **Issue:** User doesn't know what the intended workflow is — confirm then name? Where to merge?
- **Impact:** Confusion, hesitation, reduced triage speed
- **Fix:** Add brief workflow guide at top of speed-run page, or post-confirm prompt

### FB-8: Counter changes during triage (known UX-063)
- **Observed:** "0 of 222" → "1 of 251" after first confirm
- **Known issue:** UX-063 in BACKLOG

### FB-9: Confirm (Y) very slow response — possible double-accept (P0)
- **Issue:** Pressing Y has noticeable lag, feels unresponsive. User clicked multiple times thinking it didn't register.
- **Impact:** May have accidentally confirmed clusters without reviewing them. Speed-run is unusable if not fast.
- **Risk:** Accidental confirmations with no review trail
- **Fix needed:** (1) Optimistic UI — immediately show "confirming..." and advance, (2) debounce to prevent double-fire

### FB-10: No history of previous actions in speed-run (P1)
- **Issue:** No way to see what was previously confirmed/rejected in this session
- **Impact:** Can't catch accidental accepts, can't review triage decisions
- **Fix:** Add a collapsible "Recent actions" sidebar or footer showing last N actions with undo

### FB-11: PRD-038 not wired into clustering (P1 — investigate)
- **Issue:** User expected longitudinal face modeling to reduce age-based cluster splits
- **Status:** PRD-038 phases 0-4 shipped (Session 97), but rollout gates still closed
- **Investigate:** Why isn't the reranker active? What's blocking graduation?

### FB-13: Speed-run confirm-only flow is low value (P0 — PRODUCT)
- **Issue:** Confirming clusters just says "yes, same person" but doesn't identify WHO. No naming, no GEDCOM link, no merge with existing. The real work is still ahead.
- **Impact:** Hours of triage produces confirmed clusters that still need a second pass to name, link, and merge. Low ROI on admin time.
- **Better UX — batch confirm:** Sort INBOX by face count, show grid, let admin select-all + deselect bad ones (like Google Photos album creation). Mass-confirm in one click. Way faster for "is this a valid cluster?" validation.
- **Better UX — enriched speed-run:** Speed-run becomes valuable when it also lets you: (1) name the person inline, (2) search + merge with existing identity, (3) GEDCOM link, (4) see suggested matches from longitudinal model. Without these, it's just a cluster validation tool.
- **Decision needed:** Is the speed-run worth further investment, or should we pivot to the batch-select approach for cluster validation + a separate enrichment flow for naming/linking?

### FB-12: Face crops too small, too much wasted space (P1)
- **Issue:** Faces are tiny thumbnails with vast empty space around them. Screen real estate not used well.
- **Impact:** Hard to visually verify faces, especially ambiguous ones
- **Fix:** Larger crops, or full-width scrollable row, or grid that fills the card

### FB-14: Counter going DOWN is confusing — no sense of progress (P1)
- **Issue:** Total count changes: 222→251→250→247→246. User has no idea how many they've reviewed.
- **Impact:** Feels like you're going backwards. Demoralizing, no sense of accomplishment.
- **Fix:** Show "X confirmed / Y skipped / Z rejected" cumulative stats, not a moving denominator

### FB-15: Can't verify potential false positive without source photo context (P1)
- **Issue:** One Esther Burd face (zoomed screenshot) might be wrong but user can't tell without seeing the full photo
- **Impact:** User forced to either blindly confirm or skip every ambiguous cluster
- **Fix:** Clickable crops → source photo (same as FB-2), or hover-to-preview

### FB-16: Unknown person — unclear what to do (P1 — UX)
- **Issue:** Person 3131 (7 faces) — user thinks it's the same person but doesn't know who. Confirm? Skip? What's the right action?
- **Impact:** Workflow doesn't guide the user. "Confirm" means "same person" but doesn't require identifying them.
- **Fix:** Clarify what each action means. Confirm = valid cluster (same person, even if unnamed). Skip = unsure. Add tooltip or guide text.

### FB-17: Still way too slow — needs to feel instantaneous (P0)
- **Issue:** Despite perf fix, still noticeable lag. Should be near-zero latency.
- **Impact:** Makes the tool painful for batch work
- **Fix:** Optimistic UI — show "Confirmed!" animation immediately, advance to pre-fetched next card, server processes in background

### FB-18: No visual feedback on action — did it work? (P1)
- **Issue:** Press Y, then... what? Card eventually changes but no immediate confirmation
- **Fix:** Instant animation (card slides out, next slides in), confirmation toast/flash

### FB-19: Undo not discoverable — Z exists but unclear (P1)
- **Issue:** Undo button exists but user doesn't know how to go back. Z key not obvious.
- **Impact:** Accidental confirms with no recourse
- **Fix:** Make undo more prominent, show "Undo: Confirmed Person 2986 (Z)" with identity context

### FB-20: Accidental double-Y with no awareness (P0)
- **Issue:** Lag → user presses Y twice → may confirm TWO clusters unknowingly
- **Impact:** Silent data quality degradation. Worse than wrong — invisible.
- **Fix:** (1) Debounce, (2) action queue with visual feedback, (3) recent actions visible at all times

### FB-21: Design for real users — Claude Benatar, community power users (PRODUCT)
- **Issue:** Current UX only works for Nolan (who knows the people). Need to think about: non-technical contributor, community admin starting their own archive
- **Impact:** Can't scale beyond Nolan without simpler, more guided flows
- **Direction:** Easy to explain, self-evident workflows. Batch validation for admins, guided enrichment for domain experts.

## Triage Stats
| Cluster | Identity | Faces | Action | Person | Notes |
|---------|----------|-------|--------|--------|-------|
| 1 | Person 2986 | 44 | CONFIRMED | Charles Fox | All correct |
| 2 | Person 3594 | 14 | CONFIRMED | Charles Fox (older) | Same person, different age |
| 3 | Person 2988 | 12 | CONFIRMED | Esther Burd (Fox) | Roland's mother, married Albert Fox |
| 4 | Person 2795 | 11 | CONFIRMED | Esther Burd (older) | Same person, different age |
| 5 | Person 2988 | 12 | CONFIRMED | Esther Burd | May have 1 false positive face — needs photo context to verify |
| 6 | Person 2941 | 8 | CONFIRMED? | Esther Burd? | Nolan confirmed but uncertain about one face |
| 7 | Person 3131 | 7 | PENDING | Unknown | Looks like same person but user can't identify who — needs context |

## Fixes Deployed
(none yet)

## Verification Gate
- [ ] All phases re-checked against original prompt
- [ ] Feature Reality Contract passed
