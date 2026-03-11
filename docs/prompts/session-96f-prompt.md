# Session 96f — Live UX Closeout After Data Reconciliation

## Mission
Resolve the last live UX and metadata regressions surfaced during real admin
testing so Rhodesli is actually ready for routine use.

## Reported Issues

1. Upload provenance is not surfaced clearly enough.
   - Show who uploaded a photo anywhere a user/admin reasonably expects it.
   - Show archive-added timestamp with time, not just date.

2. Upload-date newest sorting still looks wrong on live.
   - Recent photos do not appear in the expected order.
   - Investigate timestamp precision, canonical-vs-alias metadata, and cache behavior.

3. Gemini analysis / face-analysis access is too hard to find.
   - User cannot easily navigate from photo views to the place where analysis happens.
   - Confirm the Gemini-related experience is still intact after recent changes.

4. Admin/public navigation regressed.
   - There should be an easy way to move between share-ready public identify pages
     and the richer admin view for the same face/photo.

5. Upload success CTA routes to the wrong inbox mode.
   - "Refresh to see inbox" should land on:
     `/?section=to_review&view=browse`
   - It should not dump the user into focus mode.

6. Mutation attribution is incomplete.
   - Determine who made the observed local renames for:
     - `531c8221-a115-4bdd-ac96-bd930a27135b` -> `Jenny israel`
     - `44ee07e0-bc1c-4839-9ee3-149e9ef349db` -> `Emily israel`
   - Preserve the exact supporting evidence in a machine-readable artifact.
   - Make the future audit trail more durable: Supabase-backed, resilient to
     community middleware, and not dependent on local-only log files.
   - If full person/photo timeline UI is too risky for this pass, add it to the
     roadmap/backlog explicitly instead of leaving it implied.

## User-Supplied Live Examples
- Photos page: `https://rhodesli.nolanandrewfox.com/?section=photos&filter_collection=&filter_source=&sort_by=upload_newest&media_filter=all`
- Photo detail: `https://rhodesli.nolanandrewfox.com/photo/7b7b3499b2006f61`
- Uploaded example: `https://rhodesli.nolanandrewfox.com/photo/f1ae3676f59943b2`
- Public identify: `https://rhodesli.nolanandrewfox.com/identify/a0a845d7-4eca-4255-b741-77ff310dc619`

## Required Approach
- Preserve harness breadcrumbs and keep findings resumable.
- Make small commits and push each one.
- Verify the exact live paths called out by the user, not just local assumptions.
- Document any new UX/data-contract lessons discovered.

## Session Outputs
- `docs/session_context/session-96f-context.md`
- `docs/assessments/session-96f-assessment.md`
- `docs/SESSION_LOG.md`
- Any relevant backlog / lessons updates
