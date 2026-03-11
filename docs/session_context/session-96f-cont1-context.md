# Session 96f-cont1 Context

## Goal
Close the last live-tested photo/workstation UX gaps after Session 96f so the
archive is genuinely ready for routine Rhodes and Fox tagging work.

## User Feedback To Preserve
- The uploader / archive-entry provenance still does not feel visible enough
  when reviewing photos from the workstation or `/photo/{id}`.
- Upload ordering still feels suspect on recent photos; the UI should make exact
  timestamp ordering legible with date + time, not date-only.
- The path between public/share-ready views and admin/workstation views still
  feels too implicit, especially from identify pages.
- The user wants the upload success CTA to keep landing in browse mode, not
  focus mode.
- The user wants all screenshots and research preserved in the harness so the
  work remains resumable after interruption.
- The user wants future per-photo / per-person edit history with actor
  attribution, ideally backed by Supabase. If the UI is too risky for this pass,
  the requirement must remain explicitly breadcrumbed.

## Concrete Live Examples
- Workstation photos grid:
  - `https://rhodesli.nolanandrewfox.com/?section=photos&filter_collection=&filter_source=&sort_by=upload_newest&media_filter=all`
- Public photo pages:
  - `https://rhodesli.nolanandrewfox.com/photo/7b7b3499b2006f61`
  - `https://rhodesli.nolanandrewfox.com/photo/f1ae3676f59943b2`
- Public identify page:
  - `https://rhodesli.nolanandrewfox.com/identify/a0a845d7-4eca-4255-b741-77ff310dc619`

## Additional UX Notes From Screenshots
- The workstation photo cards currently emphasize source + public link but do
  not surface upload provenance prominently enough for sorting/debugging.
- Some screenshots were taken on `v0.97.10`, which means part of the confusion
  may reflect a pre-`v0.97.11` live state rather than the current head.
- Even so, the user still wants the current UI made more explicit, not merely
  “technically present below the fold.”

## Working Hypotheses
- Provenance data exists but needs to be moved higher in the photo card / photo
  detail information hierarchy.
- The workstation `/` photos view and public `/photos` view still assemble photo
  lists independently, so tie-break metadata like `photo_index_order` can drift.
- The identify-page admin link still prefers focus mode, which is inconsistent
  with the user’s broader request to stay in browse mode when returning to
  active review queues.

## Required Outputs
- Code fixes for the remaining photo provenance / ordering / navigation gaps.
- Targeted verification against the reported URLs plus both required test suites.
- Harness breadcrumbs:
  - prompt
  - context
  - assessment
  - session log
  - backlog / roadmap / lessons updates if new patterns are found
