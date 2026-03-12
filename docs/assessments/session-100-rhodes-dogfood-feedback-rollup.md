# Session 100 Rhodes Dogfood Feedback Rollup

## Purpose
Preserve the long queued Rhodesli dogfooding feedback so it survives handoffs, compaction, and later audit.

## Core User Goal
Use Rhodes confirmed people to rapidly:
- identify missing GEDCOM links
- inspect supporting photos
- attach missing source provenance
- confirm or dismiss facial matches

Current reality: the workflow is still too brittle and slow for reliable day-to-day use.

## High-Priority Failures Reported

### 1. Metadata save appears broken on photo pages
- On photo pages, editing `Collection`, `Source`, or `Source URL` appears to do nothing.
- Refresh drops the entered values.
- This is data-loss territory because it trains the user not to trust the save path.
- Preserve this concrete Facebook source URL for regression testing:
  - `https://www.facebook.com/groups/546890742472923/posts/947943075701019`

### 2. Person -> photo flow can land on the wrong photo
- User reported cases where opening a person and then clicking through to a photo lands on a photo where that person is not actually tagged.
- Concrete examples:
  - Rica Revah
  - Jacob Cohen
  - Jacob Franco
- This is confidence-breaking because it makes the archive look internally inconsistent.

### 3. Photo overlays obscure critical caption/provenance text
- The lower-left `x/y identified · collection` overlay can cover meaningful inscriptions.
- The lower-right identified/unidentified legend also competes for space.
- `Hide Faces` is not discoverable enough and does not fully solve the obstruction.

### 4. Image-overlay labeling can disagree with people cards
- User reported a face shown as unidentified on-image while the same person is already identified in the people list below.
- This is one of the most serious trust breaks in the current UX.

### 5. Confirmed-people workflow lacks filtering
- User wanted to review confirmed Rhodes people and find those missing GEDCOM links.
- The page has sort controls but no filtering for:
  - missing GEDCOM link
  - linked vs unlinked
  - other workflow-relevant states

### 6. Link Tree affordance is still awkward
- `Link Tree` on the people cards is easy to miss.
- It jumps to a person page rather than opening an inline or clearly guided linking flow.
- The `#gedcom` anchor behavior appears brittle because it dropped the user at the top.

### 7. People-in-photo layout quality is poor
- User called out broken spacing/gaps in the `People in this photo` section.
- The layout feels visually unstable and makes interpretation harder.

### 8. Dismissed/declined faces need explicit state handling
- User noted `Unidentified Person 863` as an example of a declined/dismissed face.
- They are not asking to always remove dismissed faces.
- They do want the UI to communicate dismissed state clearly enough that confidence is preserved.

### 9. Source-provenance capture at upload is too weak
- Bulk Facebook imports make it painful to attach post URLs one by one.
- Retroactively finding the right post is slow and costly.
- Upload and post-upload review need a lower-friction provenance path.

## Screenshot-Specific Notes Captured
- Rhodes confirmed people page should support a GEDCOM-linking sweep.
- Rica Revah person -> photo flow exposed provenance-save issues and photo-text obstruction.
- Facebook-sourced photo example showed:
  - text obscured by overlays
  - multiple unidentified faces
  - provenance/source editing friction
- Jacob Cohen/Jacob Franco examples suggest the person-photo join or surfaced route context can still be wrong in at least some flows.

## Relationship To Session 100 Scope
These are not out-of-scope polish notes. They directly affect:
- adoption
- tagging speed
- provenance trust
- merge confidence
- community/admin usability

## Current Status
- Preserved here for execution and audit.
- Not all items are fixed yet.
- Highest-priority execution order:
  1. photo metadata save path
  2. person -> photo mismatch
  3. overlay labeling disagreement
  4. confirmed-people filtering / GEDCOM linking ergonomics
  5. provenance capture improvements at upload/review

## Attribution
- User: full Rhodes dogfooding report, screenshots, exact provenance example, workflow goals
- Codex: rollup, prioritization, and execution mapping
