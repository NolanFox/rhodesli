# Session 100 Rhodes Workflow Gap Audit

**Date:** 2026-03-12  
**Author:** Codex  
**Status:** Active execution guide

## Purpose

Convert the accumulating Rhodes/Fox dogfooding feedback into a bounded execution
order so Session 100 finishes as a workflow recovery effort, not a loose series
of UI patches.

## Key Observation

The remaining issues cluster into five workflow families:
1. community/public context leakage
2. confirmed-people / GEDCOM triage ergonomics
3. person -> photo trust and provenance
4. similar / merge / clustering confidence
5. mobile and collection-view polish

Treating these as unrelated bugs risks more regressions than it saves.

## Current State After The First Continuation Fixes

Already addressed in code:
- photo metadata reads now prefer the canonical loaded registry in Postgres mode
- public photo footer/CTA links preserve community prefixes
- context identity is highlighted on photo pages
- person cards surface richer trust states
- photo overlays moved off the bottom caption area
- unresolved review groups now surface in Upload Review

Still open:
- confirmed people lack workflow filters for GEDCOM sweeps
- `Link Tree` remains too indirect and the `#gedcom` landing is brittle
- person -> photo flows still need more trust verification
- similar/merge flows remain too easy to fall out of admin/community context
- cluster quality and dismissed-face affordances still need stronger handling
- mobile collection swipe works again but still feels second-class

## Execution Order

### Slice 1. Confirmed-People + GEDCOM Sweep
Goal:
- make Rhodes confirmed people operable for “who still needs GEDCOM linking?”

Required:
- filter or focused triage by GEDCOM-linked vs unlinked
- fix the `Link Tree` landing behavior
- keep the user in a fast review context

Why first:
- this directly unlocks the user’s stated Rhodes work loop
- it reduces time spent drilling into wrong pages

### Slice 2. Person -> Photo Trust Repair
Goal:
- ensure clicking from a person into a photo preserves context and does not look
  internally contradictory

Required:
- verify person gallery only links to truly relevant photos
- verify the viewed person is visually and semantically clear on the photo page
- tighten provenance/source editing confidence

Why second:
- this is the route where several “major trust break” reports landed

### Slice 3. Similar / Merge / Cluster Triage
Goal:
- make “Find Similar” and cluster review feel actionable instead of detached

Required:
- preserve community/admin context end-to-end
- ensure full-page similar flows are usable for admin merge/reject work
- improve surfaced state for dismissed/negative examples
- investigate cluster false negatives in Fox and Rhodes examples

Why third:
- the user is explicitly trying to merge and validate identities right now

### Slice 4. Community/Public Context Harmonization
Goal:
- stop archive context from collapsing back to Rhodes/global pages on share-safe
  routes

Required:
- audit remaining bare `/people`, `/photos`, `/identify`, `/` handoffs on
  public/community surfaces
- make cross-community moves explicit instead of accidental

Why fourth:
- some of this is already partially repaired, but it needs a systematic pass

### Slice 5. Mobile And Share Polish
Goal:
- keep the now-working flows from feeling amateur or brittle on mobile/share
  surfaces

Required:
- review swipe mechanics on collection pages
- verify OG/share previews for high-value collection/community routes
- tighten remaining dense-photo layout issues

Why fifth:
- important, but lower leverage than the workflow blockers above

## Known Example Anchors

Use these when reproducing:
- Rica Revah:
  - `/person/8431131f-02aa-4fd2-be40-6a76e12a9bf3`
  - `/photo/e8b2bcc3e6000161?identity_id=8431131f-02aa-4fd2-be40-6a76e12a9bf3`
- Jacob Cohen:
  - `/person/167c0251-3941-4f9c-9c08-4c8a9cd5aaa6`
  - `/photo/d5bc8746012a6da3?identity_id=167c0251-3941-4f9c-9c08-4c8a9cd5aaa6`
- Roland Fox:
  - `/c/fox-family/person/ae0b181b-db55-4c3e-853d-0fdc904a1000`
- Tree:
  - `/c/fox-family/tree?person=a0a845d7-4eca-4255-b741-77ff310dc619`
- Collection/mobile swipe:
  - `/collection/vida-capeluto-nyc-collection`

Important user correction:
- in the Rica Revah photo flow, the mistagged person is Jacob Franco

## Safety Rules For Remaining Session 100 Work

1. Prefer route-local fixes and explicit tests over broad helper churn.
2. Any change affecting public/community navigation must add a context test.
3. Any change affecting photo/person trust must add a regression test anchored
   to the exact failure mode.
4. If a feedback item implies a broader workflow redesign, update the PRD/SDD
   companion docs before shipping code.

## Attribution

- User: Rhodes and Fox workflow dogfooding, screenshots, priority order
- Codex: execution grouping, sequencing, and repo-grounded follow-up plan
