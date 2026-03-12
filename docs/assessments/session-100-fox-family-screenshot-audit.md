# Session 100 Fox Family Screenshot Audit

**Date:** 2026-03-11  
**Author:** Codex  
**Purpose:** Preserve the user's screenshot-driven UX feedback and map each issue to
current hotfix status or follow-up work.

## Workflow The User Was Trying To Do

1. Open a Fox Family person page.
2. Browse that person's photos.
3. Click into a photo.
4. Move through the next relevant photos quickly.
5. Tag/link people to the tree.
6. Jump between admin review, public/share surfaces, and family-tree context without
   losing archive scope.

The current app broke that flow in multiple places.

## Screenshot-Derived Findings

### 1. Tree page looked broken, then loaded extremely slowly
- Observed:
  - blank tree viewport for a long time
  - controls felt dead
  - eventual render still felt clumsy
- Root cause:
  - tree endpoints were loading far too much GEDCOM data on demand
- Status:
  - **Partially fixed in current branch**
  - targeted GEDCOM slice loading and community-prefixed tree API calls are in place
  - local timings are much better
- Still open:
  - first-load tree data is still too slow to feel "instant"
  - tree UX polish and interaction clarity still need a dedicated pass

### 2. Person page load was too slow to be usable
- Observed:
  - Fox Family person page could take ~15s in real use
- Root cause:
  - repeated graph work on request path
  - admin-only GEDCOM decoration on initial render
- Status:
  - **Substantially improved in current branch**
  - local person page timing dropped to about `1.46s` anonymous and `1.79s` admin
- Still open:
  - live deploy needs verification against real data and browser conditions

### 3. Person -> photo navigation lost person context
- Observed:
  - clicking from a person page into a photo landed on a full photo page
  - next/previous then moved through the collection, not that person's ordered gallery
- Status:
  - **Fixed in current branch**
  - person photo links now carry `identity_id` + `sort_by`
  - photo prev/next preserves that context

### 4. Community scope was being dropped in Fox Family flows
- Observed:
  - Fox Family routes could fall back to Rhodes/default routes
  - public identify/admin links could leave the archive the user started in
- Status:
  - **Partially fixed in current branch**
  - tree, person, photo, and identify flows now preserve community prefix in the
    main touched routes
- Still open:
  - broader cross-app audit is still needed outside the hotfix surfaces

### 5. Admin vs share mode was confusing
- Observed:
  - clicking a face from a photo could drop the user into a public identify page
  - admin context became ambiguous
  - "View in Admin Queue" behavior felt unreliable
- Status:
  - **Improved in current branch**
  - identify/admin links now stay inside the current community
  - admin success links preserve community
  - admin bar is restored on the touched photo/identify/person surfaces when relevant
- Still open:
  - overall mode distinction still needs a more deliberate product pass

### 6. Multi-face photos were too painful to work through
- Observed:
  - dense photos still require too much tiny-click work
  - the user cannot "speed run" through 600 photos at an acceptable pace
- Status:
  - **Not solved by the hotfix**
- Required follow-up:
  - true batch/cluster tagging
  - ignore/noise suppression
  - better multi-face expanded gallery
  - auto-advance through unresolved faces

### 7. Date / "earliest" ordering felt misleading
- Observed:
  - user could not tell whether Gemini/date estimation had run
  - "earliest" ordering felt untrustworthy when enrichment was missing
- Status:
  - **Open**
- Required follow-up:
  - explicit labeling of what the sort is using
  - better visibility into missing AI/date enrichment
  - probably a safer default for sparse metadata cases

### 8. Upload review -> identify -> person -> tree workflow was too fragmented
- Observed:
  - user could not move fluidly between review sections and archive surfaces
  - archive/admin/share distinctions were not clear enough during work
- Status:
  - **Open as a Session 100 workflow problem**
- Required follow-up:
  - dedicated speed-run review design
  - better continuity between queue, photo, person, identify, and tree

## What Is Fixed Now Versus Later

### Fixed or substantially improved in the current branch
- person/photo next-prev context
- main Fox Family community-prefix leaks in touched routes
- identify/admin links staying inside the current archive
- person-page request-path performance
- tree expand speed

### Still needs follow-up after the hotfix
- tree first-load speed
- multi-face batch tagging UX
- date/enrichment transparency
- full admin/share/community mode architecture across all routes
- true "speed-run tagging" flow

## Why This Matters

The screenshots were not just aesthetic critique. They revealed three separate product
failures:

1. **Performance failure**: too much work on request-time hot paths
2. **Context failure**: route transitions dropping archive/mode state
3. **Workflow failure**: no truly efficient batch tagging loop

Session 100 has to address all three, not just the visual layer.

## Attribution

- User: screenshots, workflow descriptions, concrete examples from Fox Family
- Codex: screenshot audit, root-cause mapping, hotfix status evaluation
- Antigravity: not yet involved in this screenshot audit
