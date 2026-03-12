# Session 100 Antigravity Workflow Review

**Date:** 2026-03-12
**Author:** Antigravity
**Context:** Reviewing whether Session 100's direction guarantees a fast, coherent tagging workflow for the Fox Family archive.

## Verdict
The current direction solves the catastrophic request-path delays and route leakage that broke the baseline experience. However, it still models "review" as traditional CMS navigation rather than a high-speed operational loop. **To "speed-run" 600 photos, the user needs batch cluster-confirmation, auto-advance, and the ability to ignore noise.** The current plan, even with the hotfix, still requires too many discrete clicks and route transitions per photo. 

## Bucket 1: `fixed now`
_These are real performance and correctness recoveries that unblock further work._
*   **Person Page Hot Path:** Eliminating the single-request graph traversal drops person page render to < 2s.
*   **Person -> Photo Navigation Context:** Preserving `identity_id` and list context so next/prev traverses the subset, not the whole collection.
*   **Context Leakage within Hotfix Surfaces:** Identify and admin actions successfully retaining their community prefix within the touched routes.
*   **Tree Expand Interaction:** Expanding tree nodes is now instant (~0.25s) thanks to targeted slice loading.

## Bucket 2: `good enough for hotfix / tonight`
_These are viable stopgaps that relieve immediate pain, but are fundamentally not the final UX._
*   **Tree First-Load (Cold):** ~6.4s is a massive improvement over > 60s, but it is still far too slow if the user expects to jump to the tree *during* an active tagging loop. It's acceptable to merge tonight, but the final workflow must decouple tagging speed from tree hydration.
*   **Admin/Share Boundary in the Hotfix:** Making the admin context merely "less confusing" on transitions is a band-aid. True mode separation requires a deeper structural pass.

## Bucket 3: `must land before Session 100 implementation`
_The Session 100 implementation plan MUST include these if the goal is a best-in-class tagging speed-run._
1.  **Batch Cluster Confirmation:** We must build a true "cluster review" UI. The user cannot be forced to tag 15 photos of identical detected faces individually. We need a surface that asks: "Are these 15 faces all John Fox? Yes / No."
2.  **Auto-Advance Loop:** When working through an "Identify Queue", confirming or ignoring a face MUST instantly load the next unresolved face. Dropping the user back out to a gallery list after 1 tag completely destroys the speed-run momentum.
3.  **"Ignore Noise" as a First-Class Action:** A fast workflow is defined by how quickly it removes noise. We must add the ability to bulk-ignore background strangers in dense photos so they exit the tagging queue completely.
4.  **Dense Multi-Face Grid Handling:** Re-iterating from the plan review: a horizontal scroll-snap strip fails on a 20-person group photo. The expanded multi-face UX must wrap into a grid.
5.  **Unified "Review Mode" (Workflow Continuity):** The fragmented `upload review -> identify -> person -> tree` journey forces the user to navigate the architecture rather than their tasks. We need a dedicated "Review Mode" UI overlay or route that stitches these together without making the user manually jump between the public face card and the admin tree view.

## Bucket 4: `can wait for later polish`
_These are legitimate issues from the screenshot audit that we can safely defer to maintain Session 100 velocity._
1.  **Date / Enrichment Ambiguity UI:** Lack of clarity around whether a date is exact or "estimated by Gemini" reduces trust, but it does not physically block the user from tagging a face. We can fix the labels later.
2.  **Full-Site Admin/Share Architecture:** While the tagging loop must have clear admin context, a comprehensive sweep of every other route in the application to enforce strict admin/public mode visual boundaries can wait. 
3.  **Sub-Second Tree First Load:** The 6-second cold load is acceptable if we build a tagging loop that doesn't force the user to load the full tree for every confirmation.

## Summary Conclusion
The Session-100 perf hotfix successfully stopped the bleeding. But the plan for the *tagging interface* must be upgraded from "fix the broken CMS links" to "build a high-volume triage queue." We must insert Batch Cluster Review and Auto-Advance into the Session 100 execution plan before writing more component code.
