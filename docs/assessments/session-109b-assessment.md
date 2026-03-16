# Session 109b Assessment — Cross-Batch Gap Closure

## Shipped
- [x] G1: Recluster Supabase writes — ml_runs + ml_proposals now written from recluster endpoint
- [x] G2: James Fields scenario tests — 3 new tests (same-person cross-batch, family resemblance proposal, collage co-occurrence block)
- [x] G3: match_type column fix — removed from Supabase inserts (column doesn't exist), kept in proposals.json
- [x] G4: Community filter fix — JSON identities don't have identity_communities, callers now match globally
- [x] G5: Recluster executed on production — 1355 matches, 1130 new proposals, 46 grouping merges
- [x] G6: James Fields validated — Person 3474 at distance 0.87, all co-occurrence faces blocked
- [x] G7: Browser verification — proposals sidebar shows 1448 proposals, Similar Identities panel verified
- [x] CI fix — test_form_has_autocomplete_datalist renamed, history key added, recluster timeouts extended
- [x] CI GREEN on latest commit

## Evidence
- Recluster response: `{"cross_batch_matches":1355,"cross_batch_new_proposals":1130,"supabase_proposals_written":1130}`
- Person 28fa8bfa Similar Identities: Person 3474 at 0.87, Person 1c8c316f at 0.84 (co-occurrence blocked)
- Proposals sidebar: 1448 proposals, 922 new matches
- CI: `completed success` on commit 9e03e91
- Screenshots taken: proposals page, person page with Similar Identities

## Performance Impact
- Cross-batch matching runs ONLY during: upload ingest, admin recluster, post-confirm (background thread)
- NEVER runs during normal page loads — zero impact on browsing performance
- Recluster against 3446 identities takes ~60s — admin batch job only, not user-facing

## Deferred (truly out of scope for 109)
- In-app + email notifications for upload matches (CLUSTER-003) — needs notification UI design
- James Fields not yet named/confirmed — that's a user action, not an implementation gap

## Red Flags
- [NONE] All gaps from 109 assessment are closed

## Next Session Should Verify
1. Upload a new photo and verify cross-batch proposals generated automatically
2. Confirm a James Fields identity and verify post-confirm re-matching fires
3. Name James Fields identities (user action, not code)
