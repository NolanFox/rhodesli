# Rhodesli: Project Backlog

**Version**: 49.0 — March 15, 2026
**Status**: ~4357 tests passing, v0.99.6, 941 photos, 3412 identities, 95 confirmed
**Live**: https://rhodesli.nolanandrewfox.com

---

## Current State Summary

Rhodesli is an ML-powered family photo archive for the Rhodes/Capeluto Jewish heritage community. It uses InsightFace/AdaFace PFE with Euclidean distance metrics, FastHTML for the web layer, Supabase/Postgres for auth and structured data, Railway for hosting, and Cloudflare R2 for photo storage. Admin: NolanFox@gmail.com (sole admin). 95 sessions have delivered deployment, auth, core UX, ML pipeline, stabilization, share-ready polish, ML validation, sync infrastructure, family tree, social graph, map, timeline, compare tool, sharing design system, feature audit polish, match page polish, year estimation tool, community bug fixes, estimate page overhaul, Postgres migration, observability (Sentry/PostHog/Resend), GEDCOM integration, auto-clustering, and ~4283 tests across 299 photos, 894 identities (69 confirmed). Community sharing live on Jews of Rhodes Facebook group (~2,000 members).

---

## Active Bugs

### P0 — Fox Family Unusable (Session 96c-cont4 + 96d) — ALL FIXED in Session 96d
- ~~**COMMUNITY-007**: Fox Family sidebar counts not community-scoped~~ FIXED (Session 96d) — proposals.json read + community filter
- ~~**COMMUNITY-008**: Fox Family bottom nav bar uses bare URLs~~ FIXED (Session 96d) — community_url_prefix on all nav links
- ~~**COMMUNITY-009**: Upload Review + GEDCOM triage pages not discoverable~~ FIXED (Session 96d) — already in sidebar, verified
- ~~**COMMUNITY-010**: Proposals not surfaced in Fox Family sidebar~~ FIXED (Session 96d) — sidebar reads proposals.json
- ~~**COMMUNITY-011**: Cluster review page not community-scoped~~ FIXED (Session 96d) — proposals filtered by community identity set
- ~~**COMMUNITY-012**: To Review section shows flat faces without proposal info~~ FIXED (Session 96d) — badge shows "Matches [Name] (XX%)"
- ~~**COMMUNITY-013**: Admin page headers show "Rhodesli" instead of community name~~ FIXED (Session 96d) — admin headers use community name
- ~~**COMMUNITY-014**: Cross-community photos/faces have no community indicator~~ FIXED (Session 96d) — "From [Community Name]" badges on neighbor_card + discovery cards

### P1 — Community Link Scoping
- **COMMUNITY-015**: Internal photo/person links don't include community prefix — clicking a photo from Fox Family browse navigates to `/photo/{id}` (Rhodes context) instead of `/c/fox-family/photo/{id}`. Requires updating hundreds of `href=f"/photo/{id}"` references across all route files. Source: Session 96d browser verification.

### P1 — Default Community Routing Risk (COMMUNITY-017)
- **COMMUNITY-017**: Root URL `/` defaults to Rhodes community. External users (not Rhodes/Fox family members) who visit the site and upload photos would accidentally add them to the Rhodes archive. As we scale to more communities and share tools more widely (e.g., `/tools/estimate`), this becomes a real risk. **Needs**: (1) Community selector on first visit or signup, (2) Neutral landing page at `/` that doesn't default to any community, (3) Upload requires explicit community selection if user belongs to multiple or none. **Scope**: Architectural — ties into WORKSPACE-001 (personal archive auto-creation) and WORKSPACE-005 (community discovery page). Must be solved before wider sharing. Source: Session 96e-cont5 user feedback.

### P2 — Missing Embeddings (EMBED-001)
- ~~**EMBED-001**: Reduced from `124` missing embeddings to `2` archival face records after local InsightFace rerun regenerated 130 embeddings.~~ FIXED (Session 96e-cont12) — the final `2` archival records were crop-matched back to current detections and embedded. Final local audit reports `0` missing embeddings. Root cause was registry/artifact drift plus staged-upload publication gaps.

### P2 — Batch-Wide Orphan Detection (INGEST-001)
- **INGEST-001**: `process_directory()` does per-file orphan checks but not a batch-wide sweep. Cross-file grouping by `create_inbox_identities()` can leave faces unlinked that per-file checks don't catch. Fix: Add post-batch orphan sweep in `process_directory()` after all files processed. Source: Session 96e-cont10 root cause analysis, Lesson 121.

### P1 — Shadow Reconcile Automation (DATA-009)
- **DATA-009**: Supabase backfills/shadow syncs are additive-only, so audited corrective snapshots can still leave stale rows behind. Session 96e-cont12 had to export and prune `112` stale identity rows manually. Fix: add a dry-run-first `--prune-stale` reconcile mode that emits a checked-in diff artifact before deleting anything. Source: Session 96e-cont12 production reconciliation.

### P1 — Cross-Store Drift Monitoring (DATA-010)
- **DATA-010**: We still lack automatic detection when volume JSON, Postgres shadow tables, and derived artifacts drift apart. Fix: nightly snapshot compare of counts + hashes across identities, photos, face counts, and embedding coverage, with an artifact written for review and alerting on divergence. Source: Session 96e-cont12 root-cause analysis.

### P1 — Canonical Actor Attribution & Entity Timelines (AUDIT-001)
- **AUDIT-001**: Identity registry history still stores `user_source` (e.g. `approved_name_suggestion`) rather than a durable actor email/user_id, and person/photo pages still lack an entity-level history timeline. Session 96f follow-up fixed the file-only logging gap by dual-writing `log_user_action()` to Supabase and started logging photo metadata edits + rename routes with actor data, but canonical per-entity attribution is still incomplete. Needs: (1) actor fields on canonical registry/photo mutation records, (2) Supabase-backed read path for audit history, (3) admin timeline UI on `/person` and `/photo`, (4) optional public contributor page. Source: Nolan feedback + Session 96f attribution review.

### P1 — Annotation Approval State Drift (AUDIT-002)
- **AUDIT-002**: During the Session 96f attribution review, the matching `name_suggestion` annotations for the observed `Jenny israel` / `Emily israel` renames still showed `status=pending_unverified` with null `reviewed_by/reviewed_at`, even though registry history, `audit_log.json`, and `user_actions.log` all showed approval events. Fix: investigate annotation replay/sync/reapproval semantics, reconcile existing rows, and add an integrity check that flags approval-state mismatches. Source: `docs/assessments/session-96f-attribution-findings.json`.

### P0 — Speed Loop Tag Save (BUG-001) — FIXED Session 102
- ~~**BUG-001**: Speed Loop tag assignments silently dropped. Face lookup cache not cleared after Postgres save path.~~ FIXED (Session 102) — `46f259e` clears face lookup cache in Postgres save path. Browser verified: pending count decremented after Ignore Stranger action. Source: FB-141, Session 101 triage.

### P1 — Rhodes Photos in Fox Family (DATA-019) — FIXED Session 102
- ~~**DATA-019**: Community-batch-20260214 included Rhodes-community photos alongside Fox Family photos, causing them to appear in Fox Family speed-run.~~ FIXED (Session 102) — community reassignment script. Browser verified: "Bohor Sabatai Soriano" absent from Fox Family people. Source: FB-129.

### P1 — Postgres Name Overwrite (DATA-020) — FIXED Session 102
- ~~**DATA-020**: Non-blocking Postgres shadow sync could overwrite production name ("Charles Fox") with local auto-generated name ("Unidentified Person 2986").~~ FIXED (Session 102) — guard skips name field when local is auto-generated and Postgres has a real name. Source: FB-122.

### P2 — Unwired Route Detection (TEST-002) — FIXED Session 102
- ~~**TEST-002**: No test to detect admin routes without navigation entries.~~ FIXED (Session 102) — `test_unwired_admin_routes_detection` with explicit skip list. Source: FB-132, Lesson 138.

### P2 — Test Ordering Flakiness (TEST-001)
- ~~**TEST-001**: 31 tests fail in full suite but pass individually.~~ FIXED (Session 96e-cont12 closeout) — cache/env leakage fixtures were tightened, calibration early stopping was stabilized, and the final `/timeline` empty-filter failure was closed. Full suite now passes: `4098` app + `566` ML.

### P1 — Upload Pipeline Bugs (UPLOAD-002)
- **UPLOAD-002**: Two bugs found in upload pipeline (Session 96e-cont5): (1) Rhodes community excluded from `photo_communities` tagging — uploaded photos invisible in community-scoped Photos view despite "success" message. FIXED. (2) Supabase sync after ingest loads from Postgres (old data) instead of JSON (new data) when DATA_SOURCE=postgres — new photos never reach Supabase. FIXED. Both bugs mean uploads appeared successful but photos were invisible. Root cause: pipeline written for DATA_SOURCE=json, not updated for Postgres migration.

### P1 — Proposals API Incomplete
- **COMMUNITY-016**: `/api/proposed-matches` only reads `registry.list_proposed_matches()`, not `proposals.json`. Sidebar counts include both sources (via `_compute_sidebar_counts`), so Fox Family shows "17 Proposals" in sidebar but "No pending proposals" in content. Fix: API endpoint must also read proposals.json, same as sidebar does. Source: Session 96e-cont4 browser verification.

### P2 — Session 102 Gaps (2026-03-15)
- ~~**PERF-007**: Similar panel results not community-scoped~~ FIXED (Session 103) — find-similar and speed-run suggestions now filter by community, same-community first. Source: Session 102 audit.
- ~~**TEST-003**: DATA-019 community reassignment script lacks automated test.~~ FIXED (Session 103) — 2 tests in `tests/test_session102_gaps.py`. Source: Session 102 audit.
- ~~**TEST-004**: DATA-020 Postgres name protection guard lacks dedicated unit test.~~ FIXED (Session 103) — 3 tests in `tests/test_session102_gaps.py`. Source: Session 102 audit.
- ~~**OBS-003**: FB-142 keyboard vs button `input_method` tracking not implemented.~~ FIXED (Session 103) — `input_method` parameter added to 6 speed-run routes + 4 tests. Source: Session 102 prompt Phase 3.

### P0 — Upload Pipeline + Contributor UX (2026-03-15)
- **UPLOAD-003**: Upload pipeline broken AGAIN — approved photo leads to 404 dead link (`/photo/inbox_efea638c_0_unknown_1`). Compare Upload loses user attribution (shows "anonymous"). No thumbnails for 2/3 pending uploads. This is the 6th upload regression. Fix: end-to-end audit of upload → staging → R2 → Postgres → photo page pipeline. Consider removing approval gate for contributor uploads (auto-approve logged-in users). File: `app/upload_routes.py`, `app/admin_routes.py`, upload processing pipeline. Effort: ~2-3h. Source: FB-170, Claude Benatar real-world failure.
- **UX-077**: Compare tool not self-explanatory for contributors — Claude Benatar couldn't figure out how to use `/tools/compare` and fell back to Messenger. Logged-in Compare uploads should auto-save to archive. Fix: guided UX flow, clearer instructions, auto-save for authenticated users. File: `app/compare_routes.py`, `/tools/compare` page. Effort: ~2h. Source: FB-170.
- **UX-078**: No clear "is this the same person?" workflow for community members — the core use case that Rhodesli exists to serve has no obvious entry point. Contributors should be able to upload two photos and get a clear answer. File: Compare tool UX redesign. Effort: ~3h. Source: FB-170, Claude Benatar interaction.

### P1 — Session 103 Triage (2026-03-15)
- **FB-161**: Dismissed/skipped identities re-appear in speed-run queue — Skip action logs but doesn't track reviewed IDs; offset-based queue regenerates and re-shows skipped items. Fix: track reviewed identity IDs per speed-run session (client-side hidden field or server-side session set) and exclude from `_get_speed_run_clusters()`. File: `app/cluster_review_routes.py`. Effort: ~30 min. Source: Session 103 triage.

### P2 — Session 103 Triage (2026-03-15)
- **FB-149**: Post-merge enrichment too slow — after merging into named+tree-linked person, panel still shows suggested matches/name input instead of auto-advancing. Fix: detect merge-into-complete-identity and skip enrichment, auto-advance to next cluster. File: `app/cluster_review_routes.py` merge handler. Effort: ~45 min. Source: Session 103 triage.
- **FB-151**: Suggestion name truncated in Speed Loop — "Roland F..." not enough to decide. Fix: show full name or at least first+last. File: `app/cluster_review_routes.py` `_speed_run_cluster_card()`. Effort: ~10 min. Source: Session 103 triage.
- **FB-152**: No way to inspect suggested match from Speed Loop — can only confirm/reject blind, no "let me look first" flow. Fix: make suggestion thumbnails link to person page (new tab). File: `app/cluster_review_routes.py`. Effort: ~10 min. Note: Partially fixed by FB-150 P0 fix (thumbnails now link to person page). Source: Session 103 triage.
- **FB-154**: Finding identity by number too hard — 7 steps to reach a specific identity. Fix: add `/person/{id}` direct URL that auto-detects community, or add global admin search. File: `app/page_routes.py`. Effort: ~30 min. Source: Session 103 triage.
- **FB-155**: "View in Admin Queue" link missing community prefix (COMMUNITY-015) — URL is `/?section=...` should be `/c/{slug}/...`. Systemic issue needing sweep of all internal links. File: multiple route files. Effort: ~2h (systemic). Source: Session 103 triage. Related: COMMUNITY-015.
- **FB-156**: Workstation search for identity by number returns no results — search only shows first 150 cards, doesn't match "Person 4066". Fix: add numeric ID matching to search, or increase result limit. File: `app/browse_routes.py` search endpoint. Effort: ~20 min. Source: Session 103 triage.
- **FB-157**: Identity cards in manual search/similar panel have no clickable link to person page — thumbnail and name should link to `/c/{slug}/person/{id}`. File: `app/browse_routes.py` neighbor card rendering. Effort: ~15 min. Source: Session 103 triage.
- **FB-158**: Manual search results show no distance/match score — similar panel shows "83% match" but manual search results have no score. Fix: add distance/confidence display to search result cards. File: `app/browse_routes.py`. Effort: ~15 min. Source: Session 103 triage.
- **FB-163**: No community badge on tag search results — cross-community results shown without community indicator. Fix: add community badge to tag-search result rows. File: `app/identity_routes.py` tag-search endpoint. Effort: ~15 min. Source: Session 103 triage.
- **FB-164**: "Go to Face Card" link goes to current face, not search result — clicking search result should navigate to that person's face card. File: `app/identity_routes.py` tag-search endpoint. Effort: ~15 min. Source: Session 103 triage.
- **FB-165**: Speed-run cluster cards need face crop ↔ source photo toggle — can't see source photo context (who else is in frame). Fix: add photo preview toggle (P key or click) showing source photo with face highlighted. File: `app/cluster_review_routes.py` `_speed_run_cluster_card()`. Effort: ~1h. Source: Session 103 triage.
- **FB-166**: GEDCOM link results need more context — search returns name+dates but no family tree context (parents, spouse, children) or relationship path. Fix: add inline family preview before Link action. File: `app/page_routes.py` GEDCOM search. Effort: ~2h. Source: Session 103 triage.
- **FB-167**: GEDCOM birth year inconsistency (1891 vs 1889) — data quality issue in GEDCOM import, multiple date records not clarified. Fix: show all date variants with source attribution. File: GEDCOM import pipeline. Effort: ~1h. Source: Session 103 triage.

### P1 — Community Middleware Audit (2026-03-16)
- **MIDDLEWARE-001**: Systematic audit of all data-modifying routes that use `request.state.community`. CommunityMiddleware defaults to Rhodes when no `/c/{slug}/` prefix — has caused data-in-wrong-community 7+ times. Audit upload, match, merge, annotate, cluster-review routes. File: app/main.py CommunityMiddleware + all route files. Effort: ~1h. Source: Session 107 — James Henry Fields upload bug. See `docs/session_context/session-107b-context.md`.

### P1 — Approvals UX (2026-03-16)
- **APPROVAL-001**: Batch select checkboxes on approvals page — port pattern from pending uploads (select all, floating action bar). File: `app/admin_routes.py`. Effort: ~1h. Source: Session 107 user feedback.
- **APPROVAL-002**: ~~Show submission timestamp on approval cards~~ — DONE (Session 107b). `_format_submitted_at()` renders relative time on each card.
- **APPROVAL-003**: ~~Auto-confirm identity on approve~~ — DONE (Session 107b). Checkbox "Also confirm this person" (default checked), wired to `registry.confirm_identity()`.
- **APPROVAL-004**: ~~Store annotation_id in rename history~~ — DONE (Session 107b). `rename_identity()` accepts optional `annotation_id` stored in event metadata.
- **APPROVAL-005**: ~~Person page suggestion provenance~~ — DONE (Session 107b). `_name_provenance_line()` shows who suggested + when approved (admin only).
- **APPROVAL-006**: Email digest/batching for approval notifications — currently sends N individual emails for N approvals. Needs PRD. Source: Session 107 user feedback.
- **APPROVAL-007**: ~~Anonymous pending upload auto-expiry~~ — DONE (Session 107b). Startup cleanup marks entries expired when staging dir gone + older than 24h.
- **APPROVAL-008**: Person page full audit trail — all name changes with actor + timestamp, not just approved suggestions. Effort: ~1h. Source: Session 107b prompt.
- **APPROVAL-009**: Approvals page consistent UX with pending uploads — select, action bar, keyboard shortcuts. Effort: ~1-2h. Source: Session 107b prompt.

### P2 — Session 106 User Triage (2026-03-16)
- **FB-004**: Consistent face crop ↔ source photo toggle across all views — currently some views show crop only, some show source photo. Need a consistent pattern (click to toggle, or always show both). File: multiple route files. Effort: ~2h. Source: Session 106 triage. See `docs/session_context/session-106-feedback.md`.
- **FB-005**: Raw internal IDs shown to users — identity cards display hex IDs like "4ffef472" or numbers like "3980" instead of "Unknown Person" or clean sequential labels. File: `app/main.py` identity card rendering. Effort: ~30 min. Source: Session 106 triage. See `docs/session_context/session-106-feedback.md`.
- **FB-009**: Compare search dropdown persists after person selection — after selecting a person (e.g., Morris Shane), the search dropdown and results list remain visible. Should collapse/clear after selection. File: `app/compare_routes.py`. Effort: ~20 min. Source: Session 106 triage. See `docs/session_context/session-106-feedback.md`.
- **FB-010**: Compare tool shows all communities — searches across ALL communities. No way to filter by community. At scale (hundreds of communities) this becomes unusable noise. Fix: default to current community, add community filter dropdown. File: `app/compare_routes.py`. Effort: ~1h. Source: Session 106 triage. See `docs/session_context/session-106-feedback.md`.
- **FB-012**: Compare tool UX doesn't help reach identification conclusions — tool shows data but doesn't guide user to a verdict. Consider: summary verdict, mutual match indicator, "likely same person" / "unlikely" with explanation. File: `app/compare_routes.py`. Effort: ~2h. Source: Session 106 triage. See `docs/session_context/session-106-feedback.md`.

### P1 — Session 100b Dogfood (2026-03-13)
- ~~**DOGFOOD-001**: Confirmed faces show "Needs review" on bbox overlap~~ FIXED (Session 100b) — show identity name for confirmed faces
- ~~**DOGFOOD-002**: Photo metadata save silently loses data~~ FIXED (Session 100b) — duplicate routes removed, page_routes.py with logging now active
- **DOGFOOD-003**: Person → photo flow can land on wrong photo — Examples: Rica Revah, Jacob Cohen. Needs investigation of photo_id resolution in person gallery. Source: Session 100 dogfood feedback.
- **DOGFOOD-004**: Photo overlays obscure caption/provenance text — Lower-left overlay covers inscriptions. Need below-image placement or dismissability. Source: Session 100 dogfood feedback.
- **DOGFOOD-005**: Confirmed-people filtering missing — Can't filter by GEDCOM link status, linked vs unlinked. Source: Session 100 dogfood feedback.
- **DOGFOOD-006**: Link Tree affordance awkward — Button easy to miss, #gedcom anchor unreliable. Source: Session 100 dogfood feedback.
- **DOGFOOD-007**: Dismissed/declined faces lack explicit state — UI doesn't communicate dismissed state clearly. Source: Session 100 dogfood feedback.
- **DOGFOOD-008**: Source provenance capture at upload too weak — Bulk Facebook imports need lower-friction URL attachment. Source: Session 100 dogfood feedback.
- **DOGFOOD-009**: Session 99 variant="session99" creates code duplication — Decision needed: keep or discard legacy. Source: Session 100b audit.

### P1 — Visual Confirmation Gate (DATA-011)
- **DATA-011**: Admin must see the actual face crop before confirming an identity. Currently possible to confirm orphan/wrong faces without visual verification. Fix: add a visual gate in the admin confirm workflow that renders the face crop and requires explicit approval. Source: Session 100b dogfood. Priority: P1.

### P1 — Data Integrity CI for CONFIRMED Identities (DATA-012)
- **DATA-012**: Automated test that every CONFIRMED identity's anchor_ids exist in both embeddings.npy and photo_index.json face_to_photo. Run in CI and pre-deploy. Prevents orphan face references from reaching CONFIRMED state. Source: Session 100b dogfood. Priority: P1.

### P1 — Contributor Activity View by Email (UX-061)
- **UX-061**: Admin needs to see all submissions from a specific contributor in one place. Currently no way to filter annotations/uploads by contributor email. Needed for follow-up conversations with testers. Fix: add contributor filter on /admin/approvals and /admin/audit, or dedicated /admin/contributors page. Source: Session 100d — Nolan couldn't find what lil_lover_52388@yahoo.com had submitted.

### P1 — Proposals Supabase Sync (DATA-013)
- **DATA-013**: Proposals are JSON-only (not in Supabase). No backup if Railway volume is lost. proposals.json was last generated 2026-03-10 with only 17 proposals. Fix: (1) Add proposals table to Supabase, (2) sync on generation, (3) add staleness warning in UI when proposals are >24h old. Source: Session 100d data integrity audit.

### P1 — Silent Supabase Sync Failures (DATA-014) — MOSTLY FIXED (Session 105/105b)
- **DATA-014**: Shadow writes now log at ERROR level. save_registry/save_photo_registry postgres paths use strict=True (synchronous). photo_faces written alongside photos. Remaining: registry.py history events and user action logging still have silent failures. Source: Session 100d audit, fixed Session 105/105b.

### P1 — Dead Sync Functions (DATA-015) — FIXED Session 105b-cont
- ~~**DATA-015**: `sync_birth_year_estimate()` and `sync_person_comment()` in supabase_data.py are defined but never called from any app route.~~ FIXED (Session 105b-cont) — `sync_birth_year_estimate()` wired into admin birth year accept route (`admin_routes.py`). `sync_person_comment()` wired into comment save path (`person_routes.py`). Structural tests verify both remain wired. Source: Session 100d data integrity audit.

### P1 — Proposal Regeneration After Upload (DATA-016)
- **DATA-016**: After new photos are uploaded and processed, proposals.json is NOT automatically regenerated. Admin must manually run `cluster_new_faces.py`. This means new uploads don't produce ML match suggestions until a manual step happens. Fix: auto-regenerate proposals after upload processing completes, or add a "Regenerate Proposals" button in admin UI. Source: Session 100d — proposals stale since March 10.

### P1 — Recently Confirmed View in Speed-Run (UX-067)
- **UX-067**: After confirming clusters in speed-run mode, there's no way to see what you just confirmed. Confirmed identities disappear from the queue and are mixed into the general People list. Need: "Recently Confirmed" section on the cluster review page showing the last N confirmations with undo capability. Source: Session 100d — Nolan confirmed proposals but couldn't find them afterward.

### P1 — Tree First-Load Performance (PERF-002)
- **PERF-002**: Family tree cold load is ~6.4s. Needs to feel instant. Profile D3 rendering, GEDCOM data fetch, and node count. Consider lazy loading branches or caching the initial render. Source: Session 100 Fox Family audit.

### P1 — Multi-Face Batch Tagging UX (UX-062)
- **UX-062**: Dense photos with 10+ faces require too many tiny clicks. No per-photo batch confirmation flow exists — each face must be tagged individually. Need: batch select faces on a photo, assign all to one identity, or confirm all detected groupings at once. Source: Session 100 Fox Family face tagging audit.

### P2 — Date Ordering Transparency (UX-060)
- **UX-060**: Users should understand why photos are ordered the way they are. Add sort indicator or explanation (e.g., "Sorted by upload date" label, or sort toggle). Source: Session 100 dogfood issue #16. Priority: P2.

### P2 — Fox Family Missing R2 Crops (CROP-001)
- **CROP-001**: Some Fox Family face crops show as grey boxes / "?" because the crop file was never uploaded to R2 during ingest. Root cause: R2 upload in background ingest may have failed silently, or crops were generated with a naming mismatch. Fix: audit missing crops, regenerate from raw photos, upload to R2. onerror fallback added in Session 100d-cont. Source: Session 100c assessment.

### P2 — Speed-Run Progress Count Instability (UX-063)
- ~~**UX-063**: Speed-run progress bar shows different totals (222, 30, 251) as state changes shift the cluster pool.~~ FIXED (Session 100f) — replaced with cumulative progress counter ("5 confirmed / 2 skipped / 1 rejected / 214 remaining"). Total snapshotted on page load.

### Session 100e Fox Family Triage Feedback (FB-1 through FB-21)

- ~~**FB-1**: Can't see all faces in cluster — "+36 more" overflow hides most faces~~ FIXED (Session 100f) — all faces shown in scrollable grid, no cap
- ~~**FB-2**: Crops not clickable to source photo~~ FIXED (Session 100f) — each crop links to source photo in new tab
- ~~**FB-3**: No way to name or GEDCOM-link from speed-run~~ FIXED (Session 100f) — post-confirm enrichment panel with name input and GEDCOM link button
- ~~**FB-4**: Workflow unclear — no guidance for new users~~ FIXED (Session 100f) — instructional text added at top of speed-run and batch pages
- ~~**FB-5**: No merge capability in speed-run~~ FIXED (Session 100f) — merge search typeahead in post-confirm enrichment panel
- **FB-6**: Age-based cluster splitting — clusters with mixed ages need splitting before confirm. ML problem, requires PRD-038 Phase 5 (more Fox-family labels + slice gate data). Source: Session 100e triage.
- ~~**FB-7**: Speed-run workflow unclear~~ FIXED (Session 100f) — same as FB-4, workflow guide added
- **FB-8**: Keyboard accessibility beyond Y/N/S/D — Tab navigation, screen reader labels needed for non-keyboard-native users. Source: Session 100e triage. BACKLOG: UX-068.
- ~~**FB-9**: Confirm (Y) very slow response — possible double-accept~~ FIXED (Session 100f) — 300ms Y key debounce + next-card pre-fetch
- ~~**FB-10**: No history of previous actions in speed-run~~ FIXED (Session 100f) — recent actions sidebar showing last 10 actions with undo
- **FB-11**: PRD-038 longitudinal reranker not wired into clustering — rollout gates closed pending more labeled data. Not actionable until Phase 5 evidence collected. Source: Session 100e triage.
- ~~**FB-12**: Face crops too small, too much wasted space~~ FIXED (Session 100f) — crops sized to 112px in speed-run, 80px minimum in batch grid
- ~~**FB-13**: Speed-run confirm-only flow is low value — batch select is faster~~ FIXED (Session 100f) — batch cluster validation page shipped (PRD-040)
- ~~**FB-14**: Counter going DOWN is confusing — no sense of progress~~ FIXED (Session 100f) — cumulative progress counter with snapshot total
- **FB-15**: Can't verify potential false positive without source photo context — clickable crops (FB-2) partially addresses. Full source photo preview panel deferred. Source: Session 100e triage. BACKLOG: UX-069.
- ~~**FB-16**: Unknown person — unclear what to do~~ FIXED (Session 100f) — workflow guide text explains confirm/reject/skip/dismiss
- ~~**FB-17**: Still way too slow — needs to feel instantaneous~~ FIXED (Session 100f) — next-card pre-fetch via hidden HTMX request + 300ms debounce
- **FB-18**: No visual feedback on action — did it work? — optimistic UI pre-fetch helps but full loading skeleton deferred. Source: Session 100e triage. BACKLOG: UX-070.
- ~~**FB-19**: Undo not discoverable — Z exists but unclear~~ FIXED (Session 100f) — undo banner with full context ("Undo: Confirmed Person X — N faces (Z)")
- **FB-20**: Optimistic UI for instant feedback — pre-fetch implemented, full optimistic pattern (slide animation, server confirmation) deferred. Source: Session 100e triage. BACKLOG: UX-071.
- **FB-21**: Design for real users (Claude Benatar, community power users) — workflow guides added (FB-4/7/16). Full Benatar-oriented UX audit deferred. Source: Session 100e triage. BACKLOG: UX-072.

### P1 — Fox Triage Feedback (FB-100 through FB-119) — 2026-03-14
See `docs/feedback/2026-03-14-fox-triage-feedback.md` for full details. P1 items:
- **FB-100**: No cross-community badge on speed-run suggestions (extends COMMUNITY-014)
- **FB-103**: Merge from speed-run silently fails / no confirmation
- **FB-104**: Enrichment flow order wrong — should be merge → name → GEDCOM, not name → merge
- **FB-105**: Performance very slow on merge/similar/rename (related to PERF-002)
- **FB-106**: Speed-run person links go to public page instead of admin
- **FB-110**: No GEDCOM linking from speed-run enrichment panel
- **FB-113**: "Under Review" badge contradicts CONFIRMED state on public person page

P2 items: FB-101, 102, 107, 108, 109, 111, 114, 115, 116, 117. See feedback doc for details.

### P2 — Speed-Run Source Photo Preview (UX-069)
- **UX-069**: Full source photo preview panel in speed-run for verifying false positives. Clickable crops (FB-2) partially addresses but hover-to-preview or inline source photo would be better. Source: Session 100e FB-15.

### P2 — Speed-Run Processing Indicator (UX-070)
- **UX-070**: Full loading skeleton / processing indicator for speed-run actions. Pre-fetch helps but visual feedback that an action was processed is still weak. Source: Session 100e FB-18.

### P2 — Speed-Run Optimistic UI (UX-071)
- **UX-071**: Full optimistic UI pattern — slide current card out immediately on action, show pre-fetched next card, confirm server-side in background, revert on failure. Source: Session 100e FB-20.

### P2 — Speed-Run Accessibility (UX-068)
- **UX-068**: Keyboard accessibility beyond Y/N/S/D — Tab navigation between cards, screen reader labels, focus management. Source: Session 100e FB-8.

### P2 — Real User Design Audit (UX-072)
- **UX-072**: Full UX audit from the perspective of non-technical users (Claude Benatar, community power users starting new archives). Self-evident workflows, not just keyboard shortcuts. Source: Session 100e FB-21.

### P1 — Data Integrity CI Test for CONFIRMED Faces (PERF-003)
- **PERF-003**: anchor_ids on CONFIRMED identities must reference valid face_ids in both embeddings.npy and photo_index.json. Add a CI test that validates this invariant on every commit — broken anchors cause silent face display failures. Source: Lesson 134, Session 100 audit. Priority: P1.

### P1 — Tree First-Load Profiling (PERF-004)
- **PERF-004**: Tree page first-load is ~6.4s — need to profile and identify the bottleneck (Railway cold start? DOM size? Supabase GEDCOM query? D3 rendering?). Related to PERF-002 but focused on diagnosis rather than solution. Source: Session 100 audit. Priority: P1.

### P1 — Per-Photo Multi-Face Batch Tagging (UX-073)
- **UX-073**: Holocaust collage and similar dense photos have 11+ faces requiring individual tagging. Need a per-photo batch confirm flow where admin can see all detected faces on a single photo and confirm/name them in one pass. Complements UX-062 (general batch tagging) with photo-centric workflow. Source: Session 100 audit. Priority: P1.

### P2 — Correct-Date Route Duplication (UX-074)
- **UX-074**: Two routes handle the same date correction POST, creating ambiguity about which is canonical. Consolidate into a single route. Source: Session 100b-cont. Priority: P2.

### P2 — Face Cards Tiny Click Targets on Dense Photos (UX-075)
- **UX-075**: Face cards on photos with many detected faces have very small click targets, making identification difficult on mobile and imprecise on desktop. Need minimum touch target size (44x44px per WCAG) or zoom-on-hover. Source: Face tagging audit. Priority: P2.

### P2 — Speed-Run Reject Doesn't Visibly Advance (UX-076)
- **UX-076**: Speed-run reject fires undo banner correctly ("Rejected") but the card doesn't visibly advance to the next cluster — appears unchanged to the user. Confirm (Y) and Skip (S) advance correctly. Source: Session 100g browser verification. Priority: P2.

- **UX-077**: Speed-run progress counter format — 100f assessment documents cumulative format ("5 confirmed / 2 skipped / 1 rejected / 214 remaining") but production shows simple "29 clusters reviewed" count. Verify whether detailed format activates only during active session or if implementation doesn't match spec. Source: Session 100g browser verification. Priority: P2.

### P2 — Solomon Galante Empty Anchor IDs (DATA-017)
- **DATA-017**: Identity for Solomon "Solly" Galante exists but has empty anchor_ids — no displayable face. Needs investigation: was the face detached? Is there a merge chain issue? Source: Session 100b-cont3 assessment.

### P2 — Admin vs Share Mode Distinction (UX-064)
- **UX-064**: No deliberate product distinction between admin workstation mode and public share/contributor mode. The same sidebar shows different items per role, but the overall mode is not communicated clearly. Non-admin users may not understand they're in a limited view. Source: Session 100 Fox Family audit.

### P2 — Upload to Tree Workflow Fragmentation (UX-065)
- **UX-065**: No fluid navigation between upload review → identify → person → tree → back. Admin workflow requires jumping between disconnected pages. Need: breadcrumb trail or "next step" prompts that guide through the review pipeline. Source: Session 100 Fox Family audit.

### P2 — Date/Enrichment Transparency (UX-066)
- **UX-066**: Users can't tell if Gemini date estimation or GEDCOM enrichment has been run on a photo. "Earliest" sort feels untrustworthy without knowing the data source. Fix: show enrichment status badges on photo cards. Source: Session 100 Fox Family audit.

### P0 — Blocks Core Workflow
- ~~**UX-036**: Merge button 404~~ FIXED (Session 49D)
- ~~**UX-070-072**: Name These Faces broken on /photo/ pages~~ FIXED (Session 49D)
- ~~**UX-044/052**: Compare/Estimate upload messaging~~ FIXED (Session 49D/49E)

### P1 — Significant Friction
- ~~**UX-103**: Full-bleed photo view has no CTAs, overlays, or metadata~~ FIXED (Session 68)
- ~~**UX-037**: Merge direction unintuitive~~ FIXED (Session 86) — hx_confirm on all merge buttons with both identity names
- ~~**UX-038**: Operations on merged-away IDs return 200 silently~~ FIXED (Session 86b) — POST guards with HX-Redirect to canonical
- ~~**UX-039**: No admin controls on /person/ page~~ FIXED (Session 86) — inline rename, confirm/skip/reject, merge search
- **UX-042**: /identify/{id} shareable page has no link to source photo (critical for community onboarding)
- **UX-045-046**: No loading indicator + no auto-scroll on compare upload results
- ~~**UX-053**: Estimate upload: no photo preview~~ FIXED (Session 86b)
- **UX-054-055**: Estimate upload: no loading indicator, no auto-scroll
- ~~**UX-056**: Estimate upload: no CTAs (dead end)~~ FIXED (Session 86b)
- ~~**UX-057**: Estimate upload: file input doesn't reset~~ FIXED (Session 86b)
- **UX-080**: 404 page unstyled — Tailwind not loading
- **UX-081**: About page missing navbar
- **UX-092**: Birth year Save Edit race condition (click interference)

### P1 — From Session 69 UX Review
- ~~**UX-108**: "Heritage Archive" subtitle fails WCAG AA contrast~~ FIXED (Session 70)
- ~~**UX-109**: "To Review" color inconsistent — amber vs blue~~ FIXED (Session 70)

### P2 — From Session 69 UX Review
- ~~**UX-110**: Discovery card identity names truncated at 120px~~ FIXED (Session 70, 200px + tooltips)
- ~~**UX-111**: Discovery confidence badge no tooltip~~ FIXED (Session 70)
- ~~**UX-112**: "Confirm as {name}" button overflow~~ FIXED (Session 70, truncation + tooltip)
- ~~**UX-113**: Discovery empty state blank div~~ FIXED (Session 70, "All discoveries reviewed!")

### P2 — From Session 70
- **UX-114**: Collection dropdown `onfocus="this.select()"` is fragile — keyboard nav doesn't trigger onfocus. Replace with placeholder text or proper select component. Source: Session 69 BUG-3 fix fragility.

### P2 — From Session 67 UX Review
- ~~**UX-104**: Compare "Compare Selected Faces" button disabled state~~ VERIFIED (Session 70, already implemented)
- ~~**UX-105**: Missing "Help Identify" CTA for all-unidentified photos~~ FIXED (Session 70, amber styling)
- **UX-106**: Inconsistent contribution CTA phrasing ("Do you know?" vs "Can you help?")
- **UX-107**: "Identified" badge on person page has no tooltip or explanation

### COMPARE-002: Real-Time Compare Upload (Concrete Plan, AD-187)
- **Status**: DEFERRED — blocked by AD-007 (no ML deps in production)
- **What works now**: Archive-face comparison (pre-computed embeddings). Upload queues to R2 for batch.
- **What's needed**: GPU on Railway OR ONNX export of InsightFace compatible with PFE embeddings
- **Estimated effort**: 2-3 sessions once blocker clears
- **Steps**: (1) Export InsightFace to ONNX, (2) Add onnxruntime-cpu to production, (3) Single-face inference on upload, (4) Cosine distance vs cached embeddings
- **Trigger**: Railway GPU support announcement OR compatible lightweight model

### Deferred from Earlier Audits (Medium/Low)
- **M2**: Compare file input lacks preview feedback
- **L1**: Login inputs missing `autocomplete` attribute
- **L2**: Tailwind CDN development warning
- **L3**: Landing stats counter shows 0 before scroll
- **Pre-existing**: `test_nav_consistency` `/map` state pollution (passes in isolation)

Full tracker: [docs/ux_audit/UX_ISSUE_TRACKER.md](../docs/ux_audit/UX_ISSUE_TRACKER.md) — 100 issues total

### Session 95 Post-Ship (Nolan Feedback, 2026-03-09)

- **ROUTE-001: Deprecate /facecompare → redirect to /tools/compare** — ~~`/facecompare` redirects needed.~~ **DONE** (post-Session 95). 301 redirects from `/facecompare` → `/tools/compare` and `/facecompare/result/{id}` → `/compare/result/{id}`. Step 2 remaining: remove `match_facecompare_routes.py` once confirmed no external links depend on API endpoints. Source: Nolan feedback post-Session 95.

- **TOOLS-005: Estimate v2 — GEDCOM upload + text context + geography retry** — Allow users to upload a GEDCOM file or provide additional text context to enrich the Gemini date estimation prompt. Add a "Refine with more info" button on results page that accepts geography hints for retry. Builds on existing enrichment pipeline (`rhodesli_ml/enrichment/`). **Priority: P2** — v2 iteration on `/tools/estimate`. Source: Nolan feedback post-Session 95. See also: PRD-034 (`docs/prds/034_standalone_tool_suite.md`).

- **TOOLS-006: Self-service archive creation (community upload onboarding)** — Enable non-admin users to create their own community archive and upload photos. Current state: Fox Family archive exists at `/c/fox-family` but is empty and upload is admin-only. Needed: (1) "Create Your Archive" public flow (community creation + first upload in one journey), (2) per-community upload permissions (community admin vs site admin), (3) onboarding UX for first photos. This is essentially PRD-035 Phase 2 multi-tenant upload. **Priority: P2** — key to Fox Family kickoff and future growth. Source: Nolan feedback post-Session 95. See also: PRD-035 (`docs/prds/035_multi_community_platform.md`).

- **TOOLS-007: Deep Comparison (Gemini-augmented face analysis)** — When ML face comparison is inconclusive (distance > 1.10), let users request a "Deep Analysis" where they provide contextual information (names, dates, locations, relationships) and Gemini performs forensic-style analysis combining visual features with historical context. Prototype in Session 104: Gemini 3.1 Pro scored 8.5/10 confidence on a pair ML scored 1.27 (false negative due to hat/glasses occlusion). Cost: <$0.01 per comparison. Workflow: Upload two photos → ML comparison → "Deep Analysis" button → user context form → Gemini forensic report → shareable result. **Priority: P1** — differentiating feature for heritage archives, proven effective. Source: Nolan idea Session 104. See: `docs/user_feedback/robert_mattatia_gemini_comparison_104.md`.

- **TOOLS-008: ML vs Gemini reliability research** — Systematic comparison of InsightFace embedding distance vs Gemini visual analysis for historical photo matching. Need to understand: (1) when does each method fail? (2) what's the false positive/negative rate for each? (3) can they be combined into a hybrid confidence score? (4) what does the literature say about LLM-based face comparison vs traditional embeddings? Session 104 showed Gemini succeeds where ML fails (occlusion), but we don't know if Gemini has higher false positive rates. **Priority: P2** — informs TOOLS-007 design. Source: Nolan feedback Session 104.

- **OBS-002: Contributor action logging** — Need end-to-end logging to reconstruct exactly what a contributor did in the app. Gaps: Compare tool uploads, page navigation, upload flow steps, error encounters. Currently only log_user_action covers admin actions. Need: PostHog event tracking for contributor flows (compare upload, upload page, approval status checks). **Priority: P1** — cannot iterate on Claude Benatar's feedback without knowing what he actually did. Source: Nolan feedback Session 104.

- **UPLOAD-001: Bulk photo import (Google Drive / local folder)** — User has 636 photos from Uncle Charlie (Fox family, digitized by cousin David) in Google Drive + Google Photos. Current web upload caps at 200 files per batch. Common use case: scanning services digitize entire collections as small JPGs (~5MB each). **Options**: (A) Local pipeline — download to folder, run `core.ingest_inbox` in batches, upload to R2, push to production. (B) Web upload in 3-4 batches of 200. (C) Google Drive API integration — paste shared folder link, app fetches + processes. Option A is fastest for immediate need. Option C is the long-term product feature for community self-service. **Priority: P1** — blocks Fox Family archive population. **Immediate action**: Run local pipeline for Charlie Fox photos. **Future**: Build Google Drive import as part of TOOLS-006. Source: Nolan feedback Session 96.

- **COMMUNITY-001: Community data scoping (PRD-035 Phase 1 gap)** — ~~Session 95 shipped community middleware but did NOT scope the actual data.~~ **PARTIALLY FIXED (Session 96)**: Photos section, sidebar counts (upload page), and admin bar now community-scoped. **Remaining gaps**: About page shows Rhodes-specific content when accessed from Fox Family sidebar (`/about` hardcodes Rhodes history). `/tools/estimate` photo picker shows Rhodes photos (by design — tools are cross-community). **Status: ~70% DONE**. Source: Nolan feedback post-Session 95, fixed Session 96.

- **COMMUNITY-002: Workspace switcher UX** — Admin users who manage multiple communities need a way to switch between them from within the app. Like Slack's workspace sidebar or Notion's workspace dropdown. Should show in the sidebar/nav: current workspace name + dropdown to switch. Notifications should be cross-workspace (user-level, not community-level). **Priority: P1** — blocks practical multi-community admin workflow. Source: Nolan feedback post-Session 95. See: PRD-035 (`docs/prds/035_multi_community_platform.md`).

---

## Recent Sessions (v0.79.1 — 2026-02-28)

- **Session 77** (v0.79.1): Compare Rebuild Follow-up. Pair compare enriched with cross-photo face summaries and archive best-hit matches (AD-181). Compare uploads auto-queued to admin pending review (AD-182). Golden test suite in tests/test_compare.py. ~3752 total.

- **Session 76a** (v0.79.0): Auto-Clustering + Discoveries Redesign + Face Cards. Two-tier auto-clustering pipeline (AD-179). Discovery log as ML audit trail. Discoveries page two-tier layout. Browse cards face-dominant (200px min). Backfill: 0 Tier 1, 7 Tier 2, 652 no match. 15 new tests + 4 regression fixes. ~3742 total.

- **Session 65d** (v0.71.0): Disk Space Fix + GEDCOM Versioning + Harness. Disk: .dockerignore saves ~400MB, startup cleanup, backup pruning (AD-162). All 3 uploads verified in Chrome browser. GEDCOM temporal versioning: version tracking, field-level diffs, enrichment queue, current_* views (AD-163). Stop hook + enhanced eval script. 30 new tests. ~3553 total.
- **Session 65c** (v0.70.0): Upload Fix (MANDATORY) + Verification Sweep + Harness. Root cause: subprocess OOM from double model loading (AD-161). Fix: thread shares hybrid models. All 3 upload surfaces verified in production. GEDCOM linking verified end-to-end (6/6 PASS). Harness: assessment mandate, prompt template, eval script. ~3475 tests.
- **Session 65b** (v0.69.0): GEDCOM Linking UX + Enrichment Fix. Production verification (5/6 PASS). GEDCOM ↔ Identity linking with fuzzy Sephardic search (AD-160). Enrichment pipeline: first_order variant for full family context (AD-159 fix). API call logging: gemini_config + response_summary now populated. 28 new tests. 3521 total.
- **Session 65a** (v0.68.0): Upload Fix + Compare Overhaul + UX Polish. Upload subprocess death detection + timeout. Two-photo face comparison (/compare/pair). Face overlay toggle. Prompt fidelity audit (AD-159). 24 new tests. ~3493 total.
- **Session 64** (v0.67.0): Verify, Migrate, Harden. Harness hardening (5 skills, 3 rules, 3 hooks). Face alignment → Supabase. gemini_api_calls tracking. Centralized model config. Combined pipeline. Calibrated scores in UI. Recalibration hooks wired. AD-152. ~50 new tests. ~3450 total.
- **Session 63** (v0.66.0): Close the Gaps, Calibrate, Re-Run. Real photo face alignment (3/3 pass). GEDCOM Supabase import (21,809 individuals, 145,574 relationships). Similarity calibration (AUC=0.9577, 348 pairs). Recalibration hooks. AD-149/150/151. 29 new ML tests. ~3402 total.
- **Sessions 57-62** (v0.59.0-v0.65.0): CORAL production, MLflow, Face Compare Tier 1, Supabase migration, Gemini refinement, SSE upload, face alignment. See [docs/roadmap/SESSION_HISTORY.md](../docs/roadmap/SESSION_HISTORY.md).
- **Sessions 49B-56** (v0.55-v0.58): Similarity calibration, ONNX serving, landing page refresh, UX fixes, GEDCOM import. See [docs/roadmap/SESSION_HISTORY.md](../docs/roadmap/SESSION_HISTORY.md).

---

## Session 78 Outstanding Items (2026-02-28)

### GEDCOM Sync Follow-up
- [ ] **GEDCOM-007: Verify production tree count after deploy** — Local data/relationships.json has ~1,019 relationships (19 UUID + 1,000 GEDCOM). Supabase may only have the 19 UUID ones. After Session 78 deploy, verify /tree shows ~718 people, not just 24 confirmed identities. Source: docs/session_context/session-78-context.md.

### Compare Full Rebuild
- [ ] **COMPARE-001: Complete compare UX rebuild** — Session 77 (Codex) implemented ~25% of the original 8-phase compare prompt: archive context + auto-queue + golden tests. Remaining: full UX redesign of compare flow, upload pipeline reliability, mobile optimization, standalone compare product vision. Source: docs/session_context/session-78-context.md.
- [x] **FB-013: Compare button in Similar Identities broken** — DONE (Session 108b). Fixed: added compare_modal() to person page.
- [x] **FB-014: Photo Context modal missing "View Photo" link** — DONE (Session 108b). Fixed: renamed "Public Page" to "View Photo", made prominent.
- [x] **FB-015: Sidebar search doesn't find photos by filename** — DONE (Session 108b). Fixed: /api/search now searches photo filenames too.
- [ ] **COMPARE-002: Community-scoped compare with archive-add fallback** — "Find this person" workflow: upload reference photo → match against community faces → show matches with confidence → if not found, offer to add to archive. Triggered by David Fox/James Fields use case (Session 108). Depends on TOOLS-002 (ML service) or could work with existing on-device ML. See: docs/session_context/session-108-ux-brief.md, TOOLS-003.

### Route Error Investigation
- [ ] **BUG-004: Verify /connect and /map stability** — Both routes had 500 errors in earlier sessions (Sessions 40-41). /map depends on PhotoRegistry.get_photo() and geocoded data. /connect depends on D3.js social graph. Verify both return 200 in production after deploy, check for ISEs under edge cases (missing data, bad IDs). Source: Session 78 Track 7 prompt.

### Cross-Batch Clustering (PRD-049, Session 108 analysis)
- [ ] **CLUSTER-001: Cross-batch matching core** — New `core/cross_batch_matching.py`. Compare new faces against ALL existing identities (not just CONFIRMED). Community-scoped, co-occurrence-aware. Source: PRD-049, Session 108 clustering analysis.
- [ ] **CLUSTER-002: Wire cross-batch into upload pipeline** — After within-batch grouping in `_background_ingest()`, run cross-batch matching. Write proposals to ml_proposals + proposals.json. Source: PRD-049 Phase 2.
- [ ] **CLUSTER-003: Wire cross-batch into admin recluster** — `/api/admin/recluster` triggers cross-batch for ALL INBOX faces. Source: PRD-049 Phase 3.
- [ ] **CLUSTER-004: Post-confirm re-matching** — After confirming an identity, re-run proposals against that new confirmed anchor. Source: PRD-049 Phase 4.
- [ ] **CLUSTER-005: Upload match notifications** — Notify uploader when their photos match existing people. In-app notification + optional email via Resend. Source: PRD-049.
- [ ] **CLUSTER-006: Merge monitoring dashboard** — Flag identities with high internal face variance, undo rate tracking, identities with 10+ faces. Source: Session 108 user feedback.

### Per-Identity Adaptive Thresholds
- [ ] **ML-098: Per-identity adaptive thresholds for auto-clustering** — Current auto-clustering uses global thresholds (Tier 1 < 0.85, Tier 2 < 1.10). Per-identity thresholds based on within-cluster distance variance could improve precision. Big Leon's within-cluster max may exceed 1.10, meaning Tier 2 misses valid matches for high-variance identities. Requires per-identity distance stats from threshold analysis. Source: AD-179, docs/prds/024_auto_clustering.md "Out of Scope".

---

## Session 60B Findings (2026-02-22)

### ML — Progressive Refinement Completion (P1)
- [x] **ML-090: Fix enriched prompt gap** — DONE (Session 61). `call_gemini()` now accepts `prompt` parameter, `run_refinement()` passes enriched prompt. AD-139.
- [ ] **ML-091: Real 3-photo validation** — Run refinement on top photo (inbox_b5e8a89e_9, 19 facts, existing label 1950s, birth year math says 1940s). ~$0.10.
- [ ] **ML-092: Results-to-web bridge** — Script/endpoint to merge refinement_results.json into date_labels.json for admin review. Currently no connection to web app.
- [ ] **ML-093: Full 41-photo batch run** — After prompt gap fixed and validated. ~$1.31.
- [x] **ML-094: Write AD-136/137/138** — DONE (Session 61). AD-139-142 also added. See ALGORITHMIC_DECISIONS.md.
- [ ] **ML-095: CORAL retroactive run** — Run local model on all 271 photos, compare to Gemini labels. Free independent validation.

### ML — Longitudinal Face Modeling (P1) — PRD-038 | Session 97 foundation shipped
- [x] **Phase 0: Eval repair + scorer-path unification** — Mixed-schema eval scripts repaired, the golden set rebuilt, and `core/auto_cluster.py` plus `scripts/cluster_new_faces.py` now share one scorer core. See AD-217, `docs/prds/SDD-038_longitudinal_face_modeling.md`.
- [x] **ML-110: Quality-aware prototype scoring** — Bare best-linkage has been replaced by a prototype-bank scorer and offline prototype report. See AD-217, AD-220.
- [x] **ML-111: Multifeature reranker** — Temporal, quality, kinship-risk, and community features now flow into the shadow reranker. Rollout gate remains closed pending stronger slice wins. See AD-217, AD-220.
- [x] **ML-112: Active learning in review UX** — Uncertain-pair labeling now lives in the review surface with diversity caps, reversible labels, and audit trail coverage. See AD-221.
- [x] **ML-113: Longitudinal feature builder** — Year-gap, age compatibility, prototype spread, and identity-span style features are in the shadow reranker path. See AD-217, AD-220.
- [x] **ML-114: Adapter / LoRA experiment** — Gated adapter experiment harness shipped; rollout remains blocked until slice evidence improves. See AD-222.
- [x] **ML-115: Local recalibration hygiene** — Production hooks are write-only; local recalibration is explicit, tested, and status-visible. See AD-219.
- [x] **ML-116: Historical decade stratification superseded** — The old "best face per decade" idea is retired in favor of the prototype-bank approach.
- [ ] **ML-117: Rollout gate tuning with fresh Fox-family labels** — Re-run Phase 2 and Phase 4 after more confirmed life-stage examples land in the app.
- [ ] **ML-118: Prompt/state lineage migration rollout** — Apply `prompt_manifests`, `calibration_pairs`, and related lineage schema changes in Supabase and expand coverage across remaining Gemini callers.
- [ ] **ML-119: State-event coverage matrix** — Build the cross-app mutation/logging matrix so every significant app state transition is replayable and attributable.
- [ ] **ML-SCALE-001: Queued cloud extraction trigger plan** — Move offline scoring / retraining to queued cloud workers when local runtime, new-face volume, identity/embedding scale, or admin-concurrency thresholds justify it. See AD-217, `docs/architecture/ML_SERVICE.md`.
- **Context**: Nolan noted that Roland Fox has many photos across life stages (Fox Family collection). Current multi-anchor best-linkage helps (more anchors = better min-distance) but we're leaving improvement on the table. Google Photos does temporal clustering, active learning, metadata fusion. See research in session-96e-cont6 assessment.

### UX Improvements (from Production Review)
- [ ] **UX-120: Help Identify mode for non-admin users (P1)** — Primary community use case requires admin intervention. Let logged-in users suggest names for unidentified faces → admin approval queue. See `docs/session_logs/session_60b_ux_review.md`.
- [ ] **UX-121: Contribution instructions page (P2)** — /contribute page explaining: how to identify faces, submit photos, report errors. Community members arrive from Facebook links.
- [ ] **UX-122: Person page family context (P2)** — 19 relationships exist in data but aren't visible. Show family connections, timeline of appearances.
- [ ] **UX-123: Mobile photo overlay readability (P2)** — Photos with 12+ faces have overlapping labels. CSS media query for reduced label size or tap-to-show.
- [ ] **UX-124: People page search/filter (P2)** — No search input on /people page.

### Face Alignment (Session 62)
- [-] **FA-001: Batch face alignment for all 271 photos** — 127/271 aligned (Session 63/64). 144 rate-limited, retry ready: `python scripts/run_combined_pipeline.py --retry-failed results/batch_alignment_20260223_023456.json`
- [x] **FA-002: Face alignment + GEDCOM context integration** — DONE (Session 64). Combined pipeline includes GEDCOM curated context. `scripts/run_combined_pipeline.py` with `--no-gedcom` flag to disable.
- [ ] **FA-003: Mobile UI refinement for face description cards** — Cards may overlap on small screens with many faces. Needs CSS media queries. Source: Session 62 prompt 6B.
- [ ] **FA-004: Auto-trigger face alignment on new photo upload** — After upload + face detection, auto-run alignment if GEMINI_API_KEY available. Source: Session 62 prompt 6B.
- [x] **FA-005: Production test face alignment** — DONE (Session 63). 3 photos tested, 100% success, $0.03. Source: Session 62 Phase 5 deferred.

### GEDCOM Integration (Session 61C, AD-147/148)
- [x] **GEDCOM-001: Supabase GEDCOM tables** — DONE (Session 63). 4 tables created via psycopg2: gedcom_individuals (21,809), gedcom_events (40,140), gedcom_relationships (145,574), gedcom_face_links (61). Source: Session 61C, AD-147/148.
- [x] **GEDCOM-002: Admin GEDCOM link review UI** — DONE (Session 65b). Fuzzy search with Sephardic surname variants. Auto-enriches birth/death on link. Unlink with soft delete. AD-160.
- [x] **GEDCOM-006: GEDCOM temporal versioning** — DONE (Session 65d). Version tracking, field-level diffs, enrichment queue, current_* views. AD-163. Migration: scripts/supabase_migration_002_gedcom_versioning.sql. Import: scripts/import_gedcom_version.py.
- [ ] **GEDCOM-003: GEDCOM enrichment in upload flow** — When a face is identified and has a GEDCOM link, show enriched analysis popup with genealogical context (birth year, relationships, life events). Status: OPEN. Source: Session 61C, AD-147/148.
- [ ] **GEDCOM-004: "Analysis improved because..." UX feature** — Show users what GEDCOM context added vs visual-only analysis. Side-by-side or inline comparison of results with and without genealogical enrichment. Status: OPEN. Source: Session 61C, AD-147/148.
- [ ] **GEDCOM-005: Batch re-analysis with GEDCOM enrichment** — Re-run all 271 photos with first_order GEDCOM variant (fixed from curated in Session 65b). Leverage linked GEDCOM data to improve date estimation and identity confidence. Status: OPEN, pipeline fix shipped. Source: Session 61C, AD-147/148, AD-159.

### Similarity Calibration (Session 63, AD-149/150)
- [ ] **CAL-001: Community "reject" UX** — Enable explicit non-match pair collection from admin/user rejections. Feeds recalibration hooks (AD-150). Critical for calibration model improvement. Source: Session 63 Phase 9.
- [ ] **CAL-002: Active learning — surface uncertain pairs** — Find face pairs near the decision boundary (P(match) 0.4-0.6) and surface them for admin labeling. Maximizes information gain per label. Source: Session 63 Phase 9.
- [ ] **CAL-003: Calibration drift monitoring dashboard** — Admin page showing calibration model version, AUC trend, threshold history, pair count growth. Alert on drift >0.1. Source: Session 63 Phase 9.
- [ ] **CAL-004: Wire calibrated probabilities to compare UI** — Replace raw cosine similarity display with calibrated P(match) + confidence label (High/Medium/Low/Unlikely). Source: Session 63 AD-149.

### Data Layer (Session 64, AD-152)
- [ ] **DATA-002: Create Supabase tables** — Run `scripts/sql/create_face_gemini_alignments.sql` and `scripts/sql/create_gemini_api_calls.sql` in Supabase. Required for Supabase-first data layer to function. Source: Session 64.
- [ ] **DATA-003: Run alignment migration** — Execute `python scripts/migrate_alignments_to_supabase.py --execute` after tables created. Migrates 127 alignment records from JSON to Supabase. Source: Session 64.
- [ ] **DATA-004: Retry 144 rate-limited photos** — Run `python scripts/run_combined_pipeline.py --retry-failed results/batch_alignment_20260223_023456.json`. Requires GEMINI_API_KEY. Estimated cost: ~$4 at $0.028/photo. Source: Session 64.
- [ ] **DATA-005: Nightly R2 backup for critical JSON/NPY files** — Upload identities.json, photo_index.json, embeddings.npy, date_labels.json, photo_locations.json to R2 nightly. Closes "total data loss" risk. ~0.5 session. Source: PRD-027.
- [x] **DATA-006: Shadow writes for all identities + photo_index** — DONE (Session 90b). Tables created, backfill script exists, save_registry() and save_photo_registry() fire-and-forget to Supabase. Backfill on production pending.
- [x] **DATA-007: Full Postgres migration (triggered)** — Core tables created (identities, photos, photo_faces), data backfilled, DATA_SOURCE=postgres flipped on Railway. Session 93. Supplementary tables also migrated (date_labels, photo_locations, birth_year_estimates). Source: PRD-027.

### PRD Backlog — Session 91
- [-] **NOTIFY-001: PRD-028 Contributor Notifications P0** — In-app notification center, bell icon, identity confirmation trigger, auto-clustering match trigger. Origin: Claude Benatar feedback ("how does someone know if there's a match?"). PRD: `docs/prds/028_contributor_notifications.md`.
- [-] **DATA-008: PRD-027 Phase A R2 Nightly Backup** — scripts/backup_to_r2.py + scripts/restore_from_r2.py. Closes "total data loss" risk. PRD: `docs/prds/027_data_migration.md`.
- [-] **EVENT-001: PRD-011 Life Events & Context Graph** — Event model (Supabase tables), CRUD routes, photo/person/timeline integration. Flesh out stub PRD first. PRD: `docs/prds/011_life_events_context_graph.md`.
- [-] **MEDIA-001: PRD-029 Photo Backs Completion** — Media group API, Front/Back label, browse "Has back" filter, card badges. Completes work started in Session 90b. PRD: `docs/prds/029_photo_back_and_media_groups.md`.
- [ ] **BACKLOG-FLAKY-001: 8 order-dependent tests marked xfail** — Root cause: FastHTML route module loading order varies by test execution order. Proper fix needs test isolation (fresh TestClient per test or route order reset). Source: Session 90c.

### Face Card Consolidation (Session 82b gap, deferred 82f)
- [ ] **UX-204: Unify face card rendering** — 14+ inline face card rendering locations in app/main.py use bespoke code. Consolidate into reusable `face_card()` component. Major refactor. Source: 82b Phase 2, 82d assessment.

### Magnifying Glass Inspect Mode (PRD-041)
- [ ] **UX-205: Magnifying glass / lens inspect mode** — Heritage photos contain small faces in group shots (30-person weddings, classroom photos). Current zoom is binary click-to-scale(2) on compare crops only (`app/compare_routes.py:5450`). The photo lightbox has scroll-wheel and pinch-to-zoom (`app/page_routes.py:5595`) but no lens cursor — users must zoom the whole image and lose spatial context. Community members identifying faces in crowded photos cannot inspect detail without losing their place.
  - **Surfaces (priority order):** (1) Compare modal face crops — replace click-to-zoom with lens. (2) Photo lightbox — full-photo inspection with face bbox context. (3) Speed-run cluster review — 80x80px thumbs need inspect (`app/cluster_review_routes.py:1406`). (4) Identity card face gallery — browse grid, person page (`app/main.py:face_card()` line 8331).
  - **Implementation:** Pure CSS `background-image` + `background-position` lens with Hyperscript pointer tracking. A circular `<div>` follows the cursor showing 2-3x magnified region. Same image URL as `<img>` src (browser-cached, no extra fetch). Reusable `lens_image(src, alt, cls, zoom_factor=3, lens_size=150)` FastHTML component replaces raw `Img()` on lens-enabled surfaces. No React, no external library.
  - **Interaction:** Desktop: hover shows lens, click toggles sticky mode, `L` key toggles lens in compare/speed-run. Mobile: long-press (300ms) activates, drag to inspect, release dismisses. Pinch-to-zoom (existing) remains as fallback. Progressive enhancement: `@media (hover: hover)` gates desktop lens; images render normally without JS.
  - **Phases:** (1) `lens_image()` component + compare modal — 1-2h. (2) Photo lightbox integration — 2-3h. (3) Speed-run thumbnail inspect — 1h. (4) Identity card gallery — 1h. Total: ~1 session.
  - **Risks:** Large R2 photos (3000x4000px) may jank on mobile — mitigated by using browser-cached src. HTMX swap may destroy lens state — mitigated by event delegation (Lesson 39). Touch conflict with scroll — mitigated by 300ms long-press threshold.
  - **Dependencies:** Benefits from UX-204 (face card unification) but can proceed independently.
  - **PRD:** `docs/prds/041_magnifying_glass_inspect.md`
  - **Source:** Session 100 Codex research item #6, Antigravity plan review ("lens is primary workflow requirement, not polish"), Magic UI Lens pattern reference.

### 82c Gemini Branch Merge (Session 82c, stranded)
- [ ] **ML-100: Merge session-82c/gemini-rerun to main** — Branch has 14 commits of Gemini enrichment pipeline work (Asheville litmus test, batch pipeline, Gatekeeper integration). Blocked by: AD numbering conflict (branch AD-194 vs main AD-194), 82a artifacts on branch need removal. Requires deliberate merge session with conflict resolution. Source: Session 82c.

### UX Features (Session 82a ideation, deferred 82f)
- [ ] **UX-201: Missing Info Table View** — Admin view listing identities with missing metadata (no birth year, no GEDCOM link, no photos). ~30-45 min. Needs PRD. Source: 82a #21.
- [x] **UX-202: One-Click Bulk Tag Confirmation** — DONE (Session 100c). Speed-run cluster review with confirm-all/reject-all. PRD-039.
- [ ] **UX-203: Relational Context Labels** — Show GEDCOM relationships ("mother of X") on face cards. Requires Supabase GEDCOM query per identity. ~45-60 min. Source: 82a #19.

### Standalone Tool Suite (PRD-034) — Session 94
Community-agnostic versions of Rhodesli's ML tools, serving as top-of-funnel and portfolio pieces. Master PRD: `docs/prds/034_standalone_tool_suite.md`.

- [ ] **TOOLS-001: Date + Location Estimator Standalone** — Extract Gemini pipeline (`rhodesli_ml/gemini_config.py`, `rhodesli_ml/gemini_extraction.py`, `app/estimate_routes.py`) into standalone product. Engine ready, zero blockers. Includes evidence cards (AD-142) + Leaflet maps. Revenue model: free (3/month), Pro ($9.99/month), API ($0.10/photo). GEDCOM upload as premium upsell. 2-3 sessions. Source: PRD-033, PRD-034.
- [ ] **TOOLS-002: ML Service Extraction + Automated Pipeline** — Extract InsightFace into separate FastAPI service. Eliminates laptop as single point of failure (pipeline has run only 6 times in 4 months). Adds: upload webhook → detect → embed → cluster → notify. Scheduled batch: nightly recalibration + re-clustering. Unblocks TOOLS-003 (face compare). 3-4 sessions. Source: `docs/architecture/ML_SERVICE.md` (reframed Session 94), PRD-034. **Key finding:** 7 pipeline scripts exist but 9/10 steps are manual CLI commands that never run. Only face detection (step 4) is automated on Railway.
- [ ] **TOOLS-003: Face Compare Real-Time** — With ML service (TOOLS-002) running, wire real-time embedding into `/facecompare` upload flow. Web app sends photo to ML service, gets 512-dim vector, compares against archive. Calibrated scoring via AD-149. Replaces ONNX export approach (simpler, also solves operational dependency). 1-2 sessions after TOOLS-002. Source: PRD-031, PRD-034.
- [ ] **TOOLS-004: NL Query + Chatbot** — Wire `parse_query_intent()` prototype to Supabase queries. Build conversational UI with progressive refinement (PRODUCT-006 vision from Session 81). 3-5 sessions. Source: PRD-032, PRD-034.
- [ ] **TOOLS-005: Unified Product Identity** — Shared domain, design system (DD-001 archival aesthetic), Supabase auth, Stripe billing, PostHog analytics across all standalone tools. Enables cross-tool funnel analysis. Source: PRD-034.

**Existing code & artifacts:**
| Artifact | Location |
|----------|----------|
| Face Compare routes (shipped) | `app/match_facecompare_routes.py` |
| Compare v2 stub | `app/compare_v2_routes.py` |
| Face Compare tests (34+) | `tests/test_facecompare.py` |
| Gemini engine | `rhodesli_ml/gemini_config.py`, `rhodesli_ml/gemini_extraction.py` |
| Evidence card UI | `app/estimate_routes.py` |
| NL query parser | `rhodesli_ml/nl_query/` |
| ML service architecture + pipeline audit | `docs/architecture/ML_SERVICE.md` |
| Pipeline scripts (7 total, manual) | `scripts/download_staged.py`, `scripts/push_to_production.py`, etc. |
| Key decisions | AD-110, AD-117, AD-131, AD-132, AD-133, AD-139, AD-142, AD-149, AD-192, AD-201 |
| Design principles | Lesson 81 (separate tools), Lesson 82 (community-agnostic), Lesson 84 (museum-quality) |

### Workspace & Onboarding (PRD-036) — Session 95b
Self-service workspace and contribution UX. Vision PRD: `docs/prds/036_workspace_onboarding.md`.

- [ ] **WORKSPACE-001: Personal archive auto-creation** — Auto-create `"{first_name}'s Archive"` community on signup. Add `owner_id`, `is_personal`, `privacy` columns to communities table. 1 session. Source: PRD-036.
- [ ] **WORKSPACE-002: Sharing mode UX** — Lighter interaction mode for community members (browse + Help Identify + share). Distinct from admin mode. 1-2 sessions. Depends: WORKSPACE-001. Source: PRD-036.
- [ ] **WORKSPACE-003: Add photos to community** — Share personal photos into community archives with Gatekeeper approval. New `community_photo_shares` table. 1-2 sessions. Depends: WORKSPACE-001. Source: PRD-036.
- [ ] **WORKSPACE-004: Anonymous contributions** — Session-tracked suggestions from anonymous visitors. Email capture optional. Link to account on signup. 1 session. Source: PRD-036.
- [ ] **WORKSPACE-005: Community discovery page** — `/communities` public directory with search. Join button for membership. 1 session. Source: PRD-036.
- [ ] **WORKSPACE-006: Per-community permissions** — Viewer/member/admin roles per community. `community_members` table with role enforcement in middleware. 2 sessions. Source: PRD-036.

### Architecture
- [ ] **ARCH-001: Rhodesli-specific hardcoding** — 171 references to "Rhodes/Jewish/Ladino/Sephardic" in app/main.py. Heavy refactoring needed for multi-community. See `docs/session_logs/session_60b_ux_review.md` Broader Scope section.

---

## From Community Sharing Feedback (Session 49C)

### Quick-Identify from Photo View — DONE (Session 51, v0.51.0)
P0 tag dropdown was already implemented. Session 51 added P1 sequential
"Name These Faces" mode: admin clicks button → auto-advances through
unidentified faces left-to-right with progress tracking. See PRD-021.

### Batch Identity Entry from External Source — PARTIALLY DONE (Session 51)
"Name These Faces" sequential mode covers the left-to-right naming
use case. Remaining: bulk text paste ("Albert Cohen, Morris Franco,
Ray Franco") auto-assigned to faces. Deferred to future session.
See: docs/session_context/session_49C_community_feedback.md

### Facebook Integration Research (LOW priority)
The sharing -> comment -> identification loop works manually but is
friction-heavy. Research: can we create a bot or integration that
monitors tagged posts and pulls identifications back into the system?
Alternatively: shareable photo pages with inline commenting that
feeds back to the admin review queue.
See: docs/session_context/session_49C_community_feedback.md

---

### Estimate Page Remaining (PRD-020 P1/P2)
- [ ] Search/filter by collection, date range
- [ ] Date correction flow — "Know the date?" → Gatekeeper pattern
- [ ] Deep CTAs: "View in archive", "Help identify", "Explore era"
- [ ] Auto-run Gemini on uploaded photos when API key configured

---

## Immediate Priority (Next 1-2 Sessions)

- [x] **Quick-Identify**: Inline face naming on photo page — DONE (Session 51)
- [x] **Batch Identity Entry**: "Name These Faces" sequential mode — DONE (Session 51)
- [ ] **OPS-001**: Custom SMTP for branded "Rhodesli" email sender
- [ ] **FE-040-043**: Skipped faces workflow for non-admin users
- [x] **PRODUCT-001: Face Compare Standalone — Tier 1**: Museum-quality /facecompare page. Session 59, v0.61.0. AD-131/132/133.

## Near-Term (3-5 Sessions)

- [x] **Gemini 3.1 Pro integration**: Wired to Estimate upload (Session 52). Updated to 3.1 Pro (Session 61, AD-139).
- [ ] **ML-075: Batch Gemini Run on 271 Photos**: Run date estimation on all existing photos. Deferred from Session 52.
- [ ] **ML-096: Run compare_models.py with --photos 20**: Flash vs Pro A/B comparison on 20 photos (~$0.62). Needs Nolan approval. (Session 61)
- [ ] **ML-097: Run full 271-photo re-analysis with 3.1 Pro**: After ML-096 validates quality. Needs cost approval. (Session 61)
- [-] **PRD-015 v2**: Face alignment via coordinate bridging — design complete (AD-144), integrated with unified extraction (AD-143). Implementation TODO. Session 53 design → Session 61B update.
- [x] **Gemini unified extraction architecture**: AD-143, rhodesli_ml/gemini_extraction.py, 16 tests. Session 61B.
- [x] **PRD-023 Stage 1**: Similarity calibration — isotonic regression (better than Platt). AUC=0.9577, 348 pairs. Session 63, AD-149. Stage 2 (LoRA) deferred.
- [x] **Progressive refinement**: Pipeline fully wired — enriched prompt now sent to Gemini. Session 60 (AD-138) + Session 61 (ML-090 fixed).
- [ ] **UX-130**: Homepage visitor experience — non-admin landing page with CTAs (P2). Source: Session 61B UX evaluation.
- [ ] **UX-131**: Photo page admin tools below evidence — collapse behind toggle (P2). Source: Session 61B UX evaluation.
- [ ] **UX-132**: Homepage "Compare a Face" CTA for non-admin visitors (P2). Source: Session 61B UX evaluation.
- [x] **FE-041**: "Help Identify" mode for non-admin users — DONE 2026-03-01 (Session 82e). /help page, Identify Mode toggle, OG cards for sharing.
- [ ] **DOC-001**: Portfolio documentation — Technical writeup of ML pipeline (InsightFace → CORAL → isotonic calibration → Gemini alignment → GEDCOM enrichment). Session 66. AD-158.
- [ ] **ML-070**: LoRA fine-tuning — Fine-tune InsightFace final layers on confirmed identity pairs. Needs 50-100+ confirmed pairs. Stage 2 of PRD-023. Session 67+. AD-158.
- [ ] **BE-031-033**: Upload moderation queue with rate limiting
- [ ] **ROLE-006**: Email notifications for contributors
- [ ] **ML-053**: Multi-pass Gemini for low-confidence re-labeling
- [ ] **BE-015-016**: Geographic data model + temporal date handling
- [ ] **FE-061-063**: Quick Compare, batch confirmation, browser performance audit
- [ ] **Overnight ML pipeline** — `scripts/ml_pipeline.py` with modes: overnight (full pipeline), interactive (quick), validate (re-check compare results). See session 54B context.
- [ ] **Playwright MCP integration** — Browser-based production testing. `.mcp.json` configured, needs first test run.
- [ ] **UX-134**: Mobile landing page horizontal overflow — `test_mobile_landing_page[chromium]` fails with 405px overflow (scrollWidth=780, clientWidth=375). Pre-existing, confirmed across multiple sessions. Source: Session 82e.
- [ ] **COMMUNITY-001: Nancy Gormezano Beta Test**: Engage Nancy as first non-family beta tester. Source: Session 49C community thread.
- [ ] **Production smoke test in CI** — Auto-run `scripts/production_smoke_test.py` on deploy
- [x] **ML-070: MLflow Integration — CORAL Training**: MLflow Model Registry + Promotion Pipeline. Session 58, v0.60.0. AD-130.
- [ ] **PRODUCT-002: Face Compare Tier 2 — Shared Backend**: Shared comparison engine between standalone and Rhodesli. Rhodesli path adds: archive identity matching, upload persistence, date context, contribute-to-archive flow. Public path: compare and discard. See AD-117, docs/session_context/session_54c_planning_context.md Part 2C.

## Medium-Term

- [ ] **OPS-002**: CI/CD pipeline (automated tests, staging, deploy previews)
- [ ] **OPS-004**: Error tracking (Sentry)
- [ ] **QA-005-007**: Mobile viewport tests, UX walkthroughs, performance benchmarking
- [ ] **AN-022**: Cross-reference genealogy databases (Ancestry, FamilySearch, JewishGen)
- [ ] **DOC-010-013**: In-app help, about page, admin guide, contributor onboarding
- [ ] **FE-080-083**: Client-side analytics and admin dashboard
- [ ] **ROLE-004**: Family member self-identification ("That's me!" button)
- [x] **Admin/Public UX Unification**: Admin bar + quick-identify inline flow — Session 60, v0.63.0
- [ ] **Confidence scores per identification**: Show which results are ground truth vs provisional. Genealogy-specific differentiation. (Source: Expert review, Session 54)
- [ ] **Identity voting / community verification**: Let users confirm/reject ML matches. Improves embeddings over time. (Source: Expert review, Session 54)
- [ ] **Processing Timeline UI**: Per-photo status display for trust restoration. (Source: Expert review, Session 54. See AD-111)
- [ ] **Observability over unit tests**: Prioritize integration tests, per-photo processing timelines, job status visibility. (Source: Expert review, Session 54. See AD-110)

## Medium-Term — New Products & ML (Session 54c)

- [ ] **ML-071: MLflow — Gemini Prompt Tracking**: Track how different Gemini API prompts yield better/worse photo context extraction over time. Log prompt text, model version, output quality metrics per run. See AD-116, docs/session_context/session_54c_planning_context.md Part 1B.
- [ ] **ML-072: MLflow — Local vs Web ML Benchmarking**: Compare InsightFace local inference vs API-based face comparison. Track latency, accuracy, cost per comparison. See AD-116, docs/session_context/session_54c_planning_context.md Part 1B.
- [ ] **PRODUCT-003: NL Archive Query MVP (LangChain)**: Natural language interface: "Show me photos from the 1930s with people who look like [uploaded face]." Chain: face detection → embedding search → date filtering → NL response. Prerequisites: similarity calibration + CORAL + stable identity matching. Estimated 2-3 sessions once prerequisites met. See AD-118, docs/session_context/session_54c_planning_context.md Part 1B.
- [ ] **PRODUCT-004: Historical Photo Date Estimator Standalone**: Upload historical photo → estimate when taken using CORAL model. Genuinely novel — no existing tool offers this. Prerequisite: CORAL model trained and validated. Could combine with face comparison in shared "faces" tool site. See docs/session_context/session_54c_planning_context.md Part 2D.

### Upload UX Remaining (from Session 60 SSE Epic)
- [ ] Face-by-face progressive rendering + overlay animations
- [ ] asyncio.Queue for concurrent upload serialization

## Long-Term

- [ ] **BE-040-042**: PostgreSQL migration (JSON won't scale past ~500 photos)
- [ ] **ML-030-032**: Model evaluation (ArcFace, ensemble, fine-tuning)
- [ ] **GEN-001+**: Multi-tenant architecture (if traction)
- [ ] **AI-001/003-005**: Auto-caption, photo restoration, handwriting OCR, story generation
- [ ] **GEO-003**: Community-specific context events (diaspora cities)
- [ ] **GEO-004: Geographic Migration Analysis**: Combine Gemini-extracted locations with GEDCOM data to trace family migration patterns (Rhodes → diaspora cities). Source: Session 54c planning.
- [ ] **KIN-001**: Kinship recalibration post-GEDCOM (19 relationships now available)
- [ ] **Session 43**: Life Events & Context Graph (event tagging, richer timeline)
- [ ] **PRODUCT-005: Face Compare Tier 3 — Product Grade**: User accounts, saved comparisons, API access, batch comparison. Post-employment priority. See AD-117.
- [ ] **PRODUCT-006: Interactive Photo Chatbot**: Conversational interface for photo analysis — user provides context, chatbot cross-references GEDCOM data, progressive refinement. Demonstrated by Asheville case study (Session 81). Each user input documented as metadata, feeds back to improve estimates. Source: Session 81 Nolan feedback, `docs/session_context/session_81_context.md` §5.
- [ ] **GRAPH-001: "Six Degrees" Connection Finder**: Graph traversal showing shortest path between any two people in the archive via photos, family, events. Novel feature. Source: Session 54c planning.
- [ ] **ML-080: DNA Matching Integration**: Explore DNA-based family matching as complement to face comparison. Community interest from Leo Di Leyo (Facebook). Source: Session 49C community feedback.
- [ ] **PARTNER-001: Institutional Partnership**: Museum/archive collaboration for expanded photo access and academic credibility. Source: Session 49C community feedback.
- [ ] **UX-110: Three-Mode Cognitive Framing**: Explore/Investigate/Curate modes with progressive complexity. Adopted conceptually, not yet built. Source: Session 50 planning.

---

## Execution Phases

### Phase A: Stabilization — COMPLETE (2026-02-08)
All 9 bugs fixed. 103+ new tests. Event delegation pattern established.

### Phase B: Share-Ready Polish — MOSTLY COMPLETE (2026-02-06 to 2026-02-19)
Landing page, search, mobile, sync, photo viewer, timeline, compare, sharing, year estimation, estimate overhaul.
Remaining: OPS-001 (branded email).

### Phase C: Annotation Engine — COMPLETE (2026-02-10 to 2026-02-13)
Photo/identity annotations, merge safety, GEDCOM, suggestion lifecycle.

### Phase D: ML Feedback & Intelligence — MOSTLY COMPLETE (2026-02-09 to 2026-02-19)
Threshold calibration, golden set, date estimation pipeline, Gemini 3.1 Pro wired to Estimate upload, ML on Railway.
Remaining: ML-053 (multi-pass Gemini), FE-040-043, progressive refinement, batch Gemini run on 271 photos.

### Phase E: Collaboration & Growth — IN PROGRESS
Contributor roles done. Community sharing live. Quick-Identify + "Name These Faces" done (Session 51). Remaining: Help Identify mode, upload moderation, notifications.

### Phase F: Scale & Generalize — FUTURE
PostgreSQL migration, CI/CD, model evaluation, multi-tenant.

### Harness Engineering — BACKLOG
- [ ] HARNESS-001: Evaluate Ralph Wiggum for overnight runs after 3+ sessions with verification gate (see HD-001)
- [ ] HARNESS-002: Consider native Tasks system for sessions with independent phases (see HD-001)
- [ ] HARNESS-003: Build session log analyzer script for docs/session_logs/*.md patterns (see HD-005)
- [ ] HARNESS-004: `run_session.sh` — manual test only, not a numbered session phase. Script splits prompts at `## PHASE` markers and runs each as separate `claude -p` invocations. Cannot be tested from within a Claude session (nested `claude -p` not supported). Session 67 Phase 5 created it, Session 68 Phase 5 confirmed it cannot run inside Claude. Needs manual validation outside a session. See `scripts/run_session.sh`, HD-018.

---

## Infrastructure & Observability (Session 95b)

- [ ] **ENV-001**: Dev/staging/prod environment separation — Separate Sentry DSNs, Railway projects, Supabase instances for each environment. Immediate: add `SENTRY_ENVIRONMENT=development` to local `.env`. Medium-term: disable Sentry in local dev (only init when `RAILWAY_ENVIRONMENT` set). Long-term: full environment split. Source: Session 95b Sentry error discussion. See OD-008.
- [ ] **OBS-001**: Observability data retention strategy — Sentry free tier retains events 90 days, PostHog free tier 1 year. If longer retention needed: export to Supabase `error_log` table via API, or upgrade tiers. Not urgent at current scale. Source: Session 95b discussion. See OD-009.
- [ ] **OBS-002**: Error classification (dev vs production) — Tag errors with source context. Dev errors should be filterable/excludable from production dashboards. Immediate fix: `SENTRY_ENVIRONMENT` tag. Source: Session 95b Nolan feedback.
- [ ] **PERF-002**: Admin workflow performance audit — Admin reports sluggishness. Investigate: Railway hobby plan cold starts / single dyno latency, full-page reloads on routes that could use HTMX partial swaps, large DOM rendering (3400+ identities in memory), Supabase query latency on uncached paths. Profile with PostHog session recordings or browser DevTools. Separate from PERF-001 (test speed) — this is runtime UX latency. Source: Session 100e Nolan feedback, OD-011 discussion.
- [ ] **EGRESS-001**: ETag/conditional fetch for Supabase cache reloads — Only download tables when data has changed. Requires custom Supabase RPC function (e.g., `SELECT md5(string_agg(updated_at::text, ','))`) to compare hashes. Would reduce egress by ~95% for read-heavy patterns. Trigger: when sustained concurrent users > 5 or egress approaches 80% of plan limit. Source: OD-011.
- [ ] **EGRESS-002**: Incremental sync for large tables — Fetch only rows with `updated_at > last_fetch_timestamp` instead of full table reload. Most impactful for identities (3413 rows) and photo_faces (2638 rows). Trigger: when any cached table exceeds 1MB. Source: OD-011.
- [ ] **EGRESS-003**: Selective column fetch — Replace `select("*")` with `select("col1,col2,...")` in cache reload queries. Quick win that doesn't require architectural changes. Source: OD-011.

---

## Sub-Files

| File | Content |
|------|---------|
| [docs/backlog/COMPLETED_SESSIONS.md](backlog/COMPLETED_SESSIONS.md) | All completed session history (Sessions 1-46) |
| [docs/backlog/FEATURE_MATRIX_FRONTEND.md](backlog/FEATURE_MATRIX_FRONTEND.md) | Bugs + Front-End/UX items (Sections 1-2) |
| [docs/backlog/FEATURE_MATRIX_BACKEND.md](backlog/FEATURE_MATRIX_BACKEND.md) | Backend + ML + Annotations + Infra (Sections 3-6) |
| [docs/backlog/FEATURE_MATRIX_OPS.md](backlog/FEATURE_MATRIX_OPS.md) | Testing + Docs + Roles + Vision (Sections 7-10) |
