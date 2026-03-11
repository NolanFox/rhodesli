# Session 96f-cont1 Prompt

## Mission
Finish the live-tested photo UX cleanup after Session 96f without introducing
new regressions.

## Open Issues

1. Photo provenance still is not prominent enough.
   - Make uploader / archive-entry timing visible where admins naturally look.
   - Prefer exact timestamps with time, not date-only summaries.

2. Photo upload ordering still needs end-to-end consistency.
   - Ensure workstation and public photo lists both carry the archival
     tie-break metadata needed for stable upload-date sorting.

3. Public/admin navigation should be more explicit.
   - Keep the public/share-ready path.
   - Make the admin/workstation return path discoverable and browse-oriented.

4. Preserve the audit/history requirement.
   - The longer-term ask for person/photo activity timelines must remain wired
     into the harness and roadmap/backlog even if not shipped in this pass.

## Required Approach
- Make small, reviewable commits and push each one.
- Avoid destructive data changes.
- Keep all reasoning and live-testing findings breadcrumbed in the harness.
- Run both required suites before calling the session done:
  - `pytest tests/ -x -q`
  - `pytest rhodesli_ml/tests/ -x -q`
