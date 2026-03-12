# Session 100 Face Tagging And Fox Family Audit

**Date:** 2026-03-11  
**Author:** Codex  
**Scope:** Why face tagging feels slow today, what competing products do better, and
what Rhodesli must do to make Fox Family tagging/linking usable.

## What The User Reported

- Fox Family person pages and tree flows were too slow to use for real work.
- Person -> photo -> next/previous lost person-gallery context and fell back to collection order.
- Community/admin/share context leaked:
  - Fox Family flows could drop into Rhodes/default routes.
  - Identify/admin links could land in the wrong archive.
  - Admin context was unclear after route transitions.
- Multi-face tagging is still too painful for dense photos.
- The user expectation is clear: working through ~600 Fox Family photos should feel
  closer to Mylio/Apple/Lightroom than to a slow review tool.

## Local Findings

1. The biggest performance bug was algorithmic.
   - `rhodesli_ml.graph.social_graph.get_closest_connections()` was effectively
     recomputing shortest paths across the graph for every candidate person on each
     person-page request.
   - Replacing that with a single-source traversal dropped the local Fox Family
     person page from about `6.9s` to about `1.46s` anonymously.

2. The admin path had a second avoidable slowdown.
   - The person page was loading GEDCOM record details during initial render just
     to decorate the "linked" panel.
   - Simplifying that panel dropped the local admin Fox Family person page to about
     `1.79s`.

3. Tree performance improved materially but is not done.
   - Before targeted GEDCOM slice loading, live tree data/expand requests were about
     `74s`.
   - After the local hotfix:
     - tree data cold: about `6.43s`
     - tree data warm: about `2.36s`
     - tree expand: about `0.25s`
   - This is a real recovery, but initial tree load still needs more work.

4. Context drift was a real workflow bug, not just polish.
   - Community-prefixed identify and photo flows were dropping back to default-root
     URLs.
   - This mixed Fox Family and Rhodes contexts in ways that made the app feel
     unreliable even when data was not corrupted.

## What Competing Software Actually Does

The strongest common pattern across Mylio, Lightroom, Apple Photos, and PhotoPrism
is not "better visuals." It is precomputation plus batch confirmation.

### Shared product patterns

1. **Background indexing, not request-time work**
   - Lightroom indexes faces in the background and lets users keep working while
     it runs.
   - Apple Photos explicitly waits for background indexing/detection before People
     features are complete.
   - PhotoPrism also treats recognition as background scanning and optimization.

2. **Cluster-first tagging**
   - Lightroom groups similar faces into stacks so naming one stack tags all photos
     in it.
   - Mylio's batch face tagging groups likely matches so users can confirm whole
     clusters at once.
   - PhotoPrism's people view is built around recognized people plus new clusters.

3. **Tag from anywhere, not one special screen**
   - Mylio supports face tagging from any view and also exposes a dedicated batch
     flow.
   - Apple and Lightroom both support naming from an individual photo as well as
     from a people collection.
   - Best-in-class products do not force the user to choose between "review mode"
     and "photo mode" to keep making progress.

4. **Ignore / hide / reject are first-class**
   - Mylio lets users ignore faces and ignore groups of untagged faces.
   - PhotoPrism lets users hide people, hide faces, and report bad matches.
   - This matters because speed comes from removing noise, not only from adding names.

5. **Manual fallback is always available**
   - Lightroom supports drawing undetected face regions manually.
   - Apple allows naming directly from the photo detail surface.
   - PhotoPrism exposes people assignment inside the photo edit dialog.

6. **Search and browse are downstream of tagging**
   - Apple uses People & Pets as a collection and also makes named people searchable.
   - Mylio returns tagged people in People View and search.
   - PhotoPrism supports person- and face-based search filters.

## What This Means For Rhodesli

Rhodesli is slower than these tools for two separate reasons:

1. **We still do too much on the request path**
   - graph/path work
   - GEDCOM lookups
   - route-specific recomputation
   - context reconstruction

2. **Our tagging UX is still too single-item and mode-fragmented**
   - too many tiny actions
   - not enough batch confirmation
   - no clear "ignore the noise" lane
   - context leaks between admin/share/community flows

## Non-Negotiables For Best-In-Class Rhodesli Tagging

1. **No heavy GEDCOM or graph work in the hot tagging loop**
   - tagging/review must stay fast even if family-tree enrichment is incomplete

2. **Stable context through the whole workflow**
   - archive stays archive-scoped
   - admin stays admin-visible
   - photo/person/identify/tree links preserve the current workflow context

3. **Batch-first review primitives**
   - approve a whole cluster
   - skip a whole cluster
   - ignore background strangers/noise
   - merge split clusters quickly

4. **Any-view tagging**
   - from photo
   - from person
   - from review queue
   - from a dedicated cluster-review surface

5. **Fast auto-advance**
   - after naming one face, move to the next unresolved face without making the user
     re-orient every time

6. **Manual correction path**
   - when detection misses a face or the cluster is wrong, the user needs a direct fix

## Concrete Gaps Rhodesli Still Has

1. No true batch cluster-confirmation flow for multi-face work.
2. No clean "ignore the remaining unknowns in this photo/group" path.
3. Person-page photo navigation only just regained the expected gallery context.
4. Tree is still too slow for first-load use in the tagging loop.
5. Community/admin/share context is still too fragile across the broader app.
6. Face cards still over-compress multiple faces into small targets in dense cases.

## Codex Recommendation For Session 100

1. Finish the current Fox Family hotfix and deploy it before more Fox Family data work.
2. Treat "speed-run tagging" as a product requirement, not an implementation detail.
3. Make face tagging a dedicated Session 100 execution track:
   - hot-path performance
   - batch/cluster review
   - ignore/reject noise
   - context-safe navigation
   - dense multi-face gallery fallback
4. Use Antigravity after the hotfix for:
   - browser critique of the tagging loop
   - mockups for cluster review / multi-face expansion
   - fast UX verification of whether the flow feels "instant enough"

## Sources

- Adobe Lightroom Classic, Face Recognition:
  https://helpx.adobe.com/lightroom-classic/help/face-recognition.html
- Apple Support, Find and name people and pets in Photos on iPhone / Mac:
  https://support.apple.com/guide/iphone/find-and-identify-people-in-photos-iph9c7ee918c/ios
  https://support.apple.com/guide/photos/find-and-name-people-and-pets-phtad9d981ab/10.0/mac/15.0
- PhotoPrism People docs:
  https://docs.photoprism.app/user-guide/organize/people/
- PhotoPrism face-recognition pipeline docs:
  https://docs.photoprism.app/user-guide/ai/face-recognition/
- Mylio support/blog on tagging, untagged flows, and batch tagging:
  https://support.mylio.com/en/articles/8490361-tagging-individual-faces
  https://support.mylio.com/en/articles/8490369-find-untagged-photos
  https://support.mylio.com/en/articles/9298678-batch-face-tagging
  https://inspire.mylio.com/face-tagging-in-mylio-photos-best-practices-time-saving-tips/

## Attribution

- User: live Fox Family workflow feedback, expectations, and screenshot evidence
- Codex: local performance diagnosis, route/context audit, product-pattern synthesis
- Antigravity: not yet involved in this hotfix; future fit is UX critique and browser verification
