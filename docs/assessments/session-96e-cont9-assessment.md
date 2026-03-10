# Session 96e-cont9 Assessment

## Shipped
- [x] Phase 0: Deploy verification — deployed via Railway CLI, confirmed DOCKERFILE builder
- [x] Phase 1 (partial): Resync ran — 109 orphan faces repaired, upload sort verified, Person 2973 skipped via API
- [x] Phase 2a: Root cause found — `sync_from_supabase_on_startup()` blindly replaces identities from Supabase, reverting manual volume fixes on every restart
- [x] Phase 2a fix: Timestamp-based comparison — only apply Supabase overrides when newer than JSON. All state changes logged. Commit `dc92d22`.
- [x] Phase 2c: Post-ingest orphan face guard — `process_single_image()` validates all faces have identities after ingest, creates emergency INBOX identities for orphans
- [x] 2 new tests for timestamp-based override skipping (29/29 pass)
- [x] Continuation prompt written for cont10

## Verified in Browser
- Upload sort (newest first): PASS — Congo Benatar, Halfon, FB Holocaust photos at top
- Admin focus view loads: PASS — face crop, Confirm/Skip/Reject buttons visible
- Person 2973 page loads: PASS (but still showed CONFIRMED from stale Supabase override — skipped via API)
- Resync endpoint: PASS — 109 orphan faces repaired, 938 photos synced, 3168 identities synced

## Deferred (Railway incident)
- Phase 1 (remaining): Full browser verification after new deploy — Railway deploying slowly
- Phase 2b: Full audit of all state-change paths (documented, not yet enforced)
- Phase 3: Communities E2E verification
- Phase 4: Upload pipeline E2E test
- Phase 5: Session outputs (partial — this assessment + cont10 prompt only)
- Data integrity audit script: background agent was building it, unverified

## Red Flags
- [HIGH] Railway incident caused 15+ min deploy times, app was 502 during transition
- [MEDIUM] Person 2973 fix requires deploy to land — fix is committed but not yet serving
- [LOW] Background data integrity audit agent result unverified

## Root Cause Analysis: Person 2973
- `sync_from_supabase_on_startup()` at `app/supabase_data.py:326` did `identities[identity_id] = override_data` without checking timestamps
- Any CONFIRMED state synced to Supabase would be re-applied on every restart, even after manual revert
- Fix: compare `updated_at` timestamps, skip if JSON is newer, log all state changes

## Lessons
- **Lesson 118**: Startup sync must compare timestamps — blind overwrite from Supabase undoes manual volume fixes (Person 2973 bug). Always use `updated_at` comparison.
- **Lesson 119**: 109 orphan faces found in production — the gap between photo_index.save() and identity_registry.save() in ingest pipeline creates orphans on crash. Post-ingest validation is mandatory.

## Next Session Should Verify
1. Deploy `6847f566` is live and serving (or trigger new deploy)
2. Run resync after deploy
3. Person 2973 stays SKIPPED after restart (timestamp fix working)
4. Create Identity works on orphan-repaired faces
5. Fox Family community E2E
6. Review data integrity audit script if it was created
