# Fox Triage Round 2 — 2026-03-14 Session 101 Phase 6

Nolan drives triage. Claude fixes or logs.

## Feedback Items

### FB-120: GEDCOM search very slow (~1 minute)
- **Severity:** P2 (performance)
- **Context:** After confirming Person 3659 (10 faces, Albert Fox), the GEDCOM "Link to Family Tree" panel loaded but search took ~1 minute to return results for "Albert Fox" (196 results)
- **Root cause:** Supabase ILIKE query on multiple columns (name, given_name, surname) with OR filter across 21K GEDCOM records. "Fox" is a very common surname. The `load` trigger auto-fires on panel open.
- **Fix:** BACKLOG — needs Postgres index on GEDCOM name columns, or text search, or debounce/lazy-load
- **BACKLOG:** UX-077

### FB-121: Save Name + Link to Tree are confusing separate actions
- **Severity:** P1 (UX confusion)
- **Context:** User must (1) type name, (2) click Save Name, (3) search GEDCOM, (4) click Link — but these should be unified
- **Fix:** FIXED — GEDCOM Link now auto-renames identity to GEDCOM name when identity still has auto-generated name. OOB swap updates name input field with green border. User just needs to Link and the name is set.
- **Files changed:** `app/relationship_routes.py` (api/gedcom/link endpoint)

### FB-122: Charles Fox lost his name (DATA REGRESSION)
- **Severity:** P0 (data integrity)
- **Context:** "Charles Fox" (previously 68 faces) appeared on the Fox Family People page as "Person 2986" (44 faces). The name existed only in production Postgres, not in local identities.json. During session 101 triage operations, save_registry() likely overwrote the Postgres name.
- **Root cause:** Production-local data divergence (Lesson 78 recurring). The non-blocking Postgres sync (Phase 4, commit ba8443f) may have contributed — background thread could fail silently.
- **Fix:** FIXED — renamed via production API to "Charles Fox". Now has 54 faces after merge.
- **Prevention needed:** save_registry() should NEVER overwrite a named identity with an auto-generated name. Need a guard in the Postgres sync path.
- **BACKLOG:** DATA-017

### FB-123: Person 2795 — unmerged confirmed cluster (11 faces)
- **Severity:** P2 (data quality)
- **Context:** Person 2795 (98772230) is CONFIRMED with 11 faces from the Charles Fox Collection but has no name and no GEDCOM link. May be a split from Charles Fox during earlier triage, or a separate person. Nolan mentioned "Esther Burd has a second unmerged one."
- **Fix:** NEEDS DECISION — Nolan should review the face crops on the person page and decide if it should merge into Charles Fox, Esther Burd, or remain separate as a new person.
- **URL:** /c/fox-family/person/98772230-f4a2-4a10-b6cf-36d915e29225

### FB-125: Photo links in speed-run exit community context
- **Severity:** P2 (UX)
- **Context:** Face crop links in speed-run use `href="/photo/..."` without `/c/fox-family/` prefix. Clicking a face takes user to Rhodes community photo page instead of Fox Family context. Header shows "Rhodesli" not "Fox Family Archive".
- **Fix:** BACKLOG — speed-run face links should use community-prefixed URLs
- **BACKLOG:** UX-079

### FB-126: Speed-run shows document photos (not portraits)
- **Severity:** P3 (data quality)
- **Context:** Claude Benatar collection naturalization document (Bohor Sabatai Soriano) appeared in speed-run. InsightFace detected the small passport photo on the document. These document-embedded faces clutter the triage queue.
- **Fix:** BACKLOG — could filter by face quality/size threshold, or flag document-type photos during ingest
- **BACKLOG:** DATA-018

### FB-128: Batch cluster validation page 404 + not wired to nav
- **Severity:** P2 (feature invisible)
- **Context:** The batch cluster validation page (PRD-040) route is `/admin/cluster-batch` but was expected at `/admin/cluster-validation`. Also, it's not linked from any sidebar or admin nav — Lesson 138 recurring (features built but never linked from navigation).
- **Fix:** BACKLOG — add to admin sidebar, consider renaming route
- **BACKLOG:** UX-080

### FB-129: Rhodes community photos appear in Fox Family speed-run
- **Severity:** P1 (data quality)
- **Context:** Photo `community-batch-20260214_23_claude_benatar_collection_victor_bohor_sabatai_soriano` has collection="Jews of Rhodes: Family Memories & Heritage" but was ingested as part of community-batch-20260214 which is mapped to Fox Family. The naturalization document keeps appearing in Fox Family triage.
- **Root cause:** Original community-batch ingest included Rhodes photos alongside Fox photos. The `identity_communities` table maps identities to communities based on which photos their faces come from, so Rhodes identities got Fox Family membership.
- **Fix:** BACKLOG — need community re-assignment script to move community-batch photos to correct community based on collection field. Or allow admin to reassign photos between communities.
- **BACKLOG:** DATA-019

### FB-127: Similar Identities panel very slow (5-10s)
- **Severity:** P2 (performance)
- **Context:** Clicking "Similar" on Esther Burd Fox card takes 5-10 seconds to load. Neighbor computation scans all embeddings (~3400+ identities). Blocks triage flow.
- **Fix:** BACKLOG — precompute neighbor lists during save, or cache results with TTL, or limit scan to same community
- **BACKLOG:** PERF-005

### FB-132: Features built but never wired to navigation (RECURRING — Lesson 138)
- **Severity:** P0 (process / product)
- **Context:** Nolan's concern: "After this triage session, we're never going to see this again. It doesn't sync into the UX, I won't know it exists, and we built it for no reason." This is the 3rd+ occurrence of Lesson 138.
- **Affected pages (known):**
  - `/admin/cluster-batch` — not in sidebar or any nav
  - Possibly others — need full audit of routes vs. sidebar links
- **Root cause:** Sessions build features to spec but don't wire them into the nav because the sidebar code is a separate concern. No test or check verifies "every admin route has a nav entry."
- **Prevention:** Add a test that enumerates all `/admin/*` routes and verifies each has at least one `href` pointing to it from the sidebar or another admin page. Flag unwired routes as failures.
- **BACKLOG:** UX-083 (nav audit + wiring), TEST-001 (unwired route detection test)

### FB-137: Identify Mode is purely cosmetic — doesn't change click behavior
- **Severity:** P1 (UX broken promise)
- **Context:** "Identify Mode" button on photo page only toggles CSS classes (highlights unidentified faces with pulse animation). Clicking a face STILL navigates to `/identify/{face_id}`. The button implies a mode change but delivers nothing functional. This is misleading.
- **Root cause:** Session 82e built Identify Mode as a visual highlight only (focus state, pulse animation, "?" badges). Never wired face clicks to an inline tagging panel.
- **Fix:** Identify Mode should intercept face clicks and open an inline panel (name input + merge search + confirm) anchored to the clicked face, WITHOUT navigating away.
- **BACKLOG:** UX-088

### FB-141: Speed Loop tags don't save — assignments not persisting
- **Severity:** P0 (data loss / broken feature)
- **Context:** Tagged multiple faces with names in Speed Loop mode. The loop advances to the next face, but assignments are NOT persisting. Only Roland Fox (pre-existing tag) shows as identified. All other faces remain "Unidentified" with dashed borders after tagging. The feature is fundamentally broken — it looks like it works but silently drops data.
- **Impact:** Admin time wasted. Worse than not having the feature — it creates false confidence that work was saved.
- **BACKLOG:** BUG-001 (critical)

### FB-140: Speed Loop tag search shows cross-community identities unsorted
- **Severity:** P2 (UX confusion)
- **Context:** On a Fox Family photo, typing "Albert" shows "Albert Cohen" (Rhodes, 1 face) above "Albert Fox" (Fox Family, 10 faces). The search is not community-scoped or community-prioritized. Confusing when trying to tag faces in a family photo — unrelated people from other communities clutter the results.
- **Fix:** Filter to current community, or sort community matches first with "From [other community]" badge on cross-community results (same pattern as speed-run suggestions).
- **BACKLOG:** UX-091

### FB-139: Speed Loop face bounding boxes misaligned + tag panel floating wrong
- **Severity:** P1 (visual / usability)
- **Context:** Speed Loop mode (`?seq=1`) shows face bounding boxes shifted left of actual faces. The tag input panel floats disconnected from the highlighted face. The whole overlay coordinate system appears broken — boxes don't align with faces in the photo. Makes it look broken and unusable even though the functionality works.
- **Root cause:** Likely CSS positioning issue — bounding box coordinates calculated from original image dimensions but rendered at a different scale. Or the photo container's offset isn't accounted for.
- **BACKLOG:** UX-090

### FB-138: Speed Loop exists but is nearly unreachable
- **Severity:** P1 (discoverability)
- **Context:** The Speed Loop (`?seq=1`) is exactly the inline photo tagging UX Nolan wants — photo full-size, face highlighted, name input anchored to face, "Ignore Stranger" to skip. But: (1) "Start Speed Loop" button didn't trigger navigation on click, (2) no path from cluster speed-run to speed loop, (3) "Identify Mode" should link to this or BE this. The tool exists but is buried behind a broken button.
- **Fix:** Wire "Identify Mode" to activate Speed Loop. Add "Tag faces in this photo" link from cluster speed-run when clicking source photo. Fix the "Start Speed Loop" button click handler.
- **BACKLOG:** UX-089

### FB-136: No merge or admin tools on /identify/ page
- **Severity:** P2 (UX gap)
- **Context:** `/identify/{face_id}` page shows "Can you identify this person?" with a face crop and source photos. But for an admin, there's no merge search, no name input, no way to assign the face to an existing identity. Only the public "help identify" CTA. Admin should see the same enrichment tools available in speed-run (merge search, name, GEDCOM link).
- **BACKLOG:** UX-087

### FB-134: Clicking face in photo goes to public identify page, not admin tag flow
- **Severity:** P1 (UX / workflow break)
- **Context:** On the photo page (group photo, 18 faces), clicking a face bounding box navigates to `/identify/{face_id}` — the public "Can you identify this person?" page. For an admin doing triage, this should open an inline tagging panel (name + merge search) directly on the photo, not navigate away.
- **Workaround:** Click "Identify Mode" button first, then click faces for inline tagging
- **Root cause:** Default face click is designed for public users (help identify flow), not admin triage. No mode-aware behavior.
- **Fix:** When admin is on photo page, face clicks should open inline admin tag panel. Or at minimum, "Identify Mode" should be auto-enabled for admins.
- **BACKLOG:** UX-085

### FB-135: No connected flow between speed-run, photo context, and face tagging
- **Severity:** P0 (product / workflow)
- **Context:** Nolan's workflow: speed-run → sees interesting cluster → clicks face to see full photo → wants to label all faces in photo → clicks face → gets dumped to public identify page → lost context, no way back to speed-run. Each transition drops you into a different disconnected part of the app.
- **Desired flow:** Speed-run ↔ photo context ↔ inline face tagging should be seamless. Should be able to: (1) view source photo from speed-run, (2) label faces inline on the photo, (3) return to speed-run where you left off.
- **This is the highest-impact UX gap in the triage workflow.** The tools exist individually but aren't connected.
- **BACKLOG:** UX-086

### FB-133: Photo-first identification is better for group photos
- **Severity:** P2 (product insight)
- **Context:** Large family photo (18 faces, 1 identified as Roland Fox) from Charles Fox Dayton Ohio Collection. Nolan's insight: for group photos with lots of context, it's easier to label everyone within the photo rather than reviewing clusters one at a time. You can see who's standing next to whom.
- **Current support:** Photo page has "Identify Mode" and "Start Speed Loop (17 unidentified)" button. This flow exists but is separate from the speed-run cluster workflow.
- **Product direction:** Consider a "Photo-first triage" mode: show photos sorted by face count, let admin label everyone in context, then move to next photo. Complements cluster-based speed-run for different use cases.
- **BACKLOG:** UX-084

### FB-131: Truncated UUIDs shown beneath cluster cards are confusing
- **Severity:** P3 (UX clutter)
- **Context:** Batch validation cards show "Person 2941" (readable) but also "fe6bad06-778..." (truncated UUID) beneath it. The UUID adds no value for admin users and creates confusion — some cards appear to have "normal integer IDs" while others look like "SHA hashes". All IDs are UUIDs; the integer is just the suffix from "Unidentified Person NNNN".
- **Fix:** Remove the truncated UUID from the card display. Only show "Person NNNN" or the actual name.
- **BACKLOG:** UX-082

### FB-130: Batch cluster validation page — not useful in current form
- **Severity:** P1 (UX / product direction)
- **Context:** Page shows 1164 clusters all pre-selected with "Confirm Selected (1164)" button. Each card shows only 1 face — you CANNOT validate a cluster from one photo. Dangerous one-click confirm-all.

#### Origin trail
- **FB-13 (Session 100e):** Nolan's original feedback was that speed-run confirm-only is low value (P0). The suggestion was: "Sort INBOX by face count, show grid, let admin select-all + deselect bad ones (like Google Photos album creation). Mass-confirm in one click."
- **PRD-040** (`docs/prds/040_batch_cluster_validation.md`): Written by Session 100f. Specified the grid concept correctly, including: "Cards can be **expanded to show all face crops** (click to enlarge)" (Step 2). Also specified admin sidebar link and post-confirm "Name these people →" flow.
- **Session 100f implementation:** Built the grid, checkboxes, filters, and batch confirm. BUT skipped the critical "expand to show all faces" feature from Step 2. Also never wired to sidebar (violating PRD Step "Entry Point" and Lesson 138).
- **Result:** The implementation hit acceptance criteria on paper but missed the core UX need. A 1-face card cannot be validated — the whole point is seeing the cluster.

#### Nolan's product direction (Session 101 Phase 6)
- This page is NOT useful for bulk uploads (636 Fox photos) — too many to scan in a grid
- Potentially useful for SMALL incremental uploads (a dozen photos):
  - Use case 1: After upload, validate that new faces joined correct clusters
  - Use case 2: After re-running ML (cloud or local), validate new cluster proposals
- MUST show ALL faces in the cluster — one face is not validation
- The deeper question: does incremental clustering even work reliably on production?
  - `_background_ingest()` triggers clustering (PRD037-001, Session 96b)
  - But given recurring data issues (FB-122 name loss, production-local divergence), the pipeline's reliability is unproven
  - Need to audit: what actually happens when you upload 12 photos to Fox Family today?

#### What went wrong in the build chain
1. FB-13 was valid product feedback with a clear vision
2. PRD-040 captured the vision correctly, including "expand to see all faces"
3. Implementation skipped the hardest/most important part (multi-face expand)
4. No nav wiring (Lesson 138 — 3rd+ occurrence)
5. No browser verification of the finished feature against the original FB-13 intent
6. Session 100g assessment marked PRD-040 as complete without validating usability

#### Recommendations
- Do NOT invest more in this page until incremental clustering is audited (PIPELINE-001)
- If revived: show all faces per card (expandable or inline), don't pre-select, require minimum interaction before bulk confirm
- Wire to nav or remove — invisible features are worse than missing features
- **BACKLOG:** UX-081 (rethink or remove), PIPELINE-001 (audit incremental clustering reliability)

### FB-143: Enrichment panel doesn't show existing GEDCOM link after merge
- **Severity:** P2 (UX confusion)
- **Context:** After merging 8 faces into Esther Burd Fox (who is already GEDCOM-linked), the enrichment panel still shows "Link to Family Tree" with a search field as if she's not linked. The "Linked" badge only appears if you manually search "Esther Burd" in the GEDCOM search. The panel should detect the existing link and show "Already linked to: Esther Burd (b. 1900 — d. 1966)" immediately, with an option to change/unlink.
- **Fix:** After merge, reload GEDCOM link status for the target identity and render `_person_gedcom_link_section` (which shows "Linked to Family Tree" with unlink button) instead of `_gedcom_link_panel` (which shows the search).
- **BACKLOG:** UX-092

### FB-142: Keyboard shortcuts may cause accidental actions + need usage logging
- **Severity:** P2 (data safety / analytics)
- **Context:** Nolan rarely uses keyboard shortcuts (Y/N/S/D/Z) and is more concerned about accidental presses — e.g., pressing Y while typing something else could confirm a cluster unintentionally. Unclear if anyone uses hotkeys vs. clicking buttons.
- **Requirements:**
  1. **Log input method** — every action must record whether it was triggered by keyboard shortcut or button click
  2. **Log undo patterns** — track when users confirm then immediately undo (signal of accidental action)
  3. **Analytics** — PostHog events for keyboard vs button usage, undo frequency, time-between-actions
  4. **Consider:** disable hotkeys when text input is focused (already may be done but verify), add confirmation for keyboard shortcuts, or make them opt-in
- **Broader principle:** "Everything should be logged and nothing should be lost. Ever."
- **BACKLOG:** OBS-002 (action method logging), DATA-020 (comprehensive audit trail)

### FB-124: Merge search can't find people with lost names
- **Severity:** P2 (UX)
- **Context:** When searching "charles" in the merge search during speed-run, "No matches found" because Charles Fox's name had been wiped to "Unidentified Person 2986". The identity appeared in Suggested Matches but not in search.
- **Fix:** Already fixed by restoring name. Broader fix: merge search should also search by identity ID number (e.g., "2986") as a fallback.
- **BACKLOG:** UX-078
