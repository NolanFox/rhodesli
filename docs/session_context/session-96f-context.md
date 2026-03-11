# Session 96f Context

## Goal
Close the last live UX and metadata regressions surfaced during real admin
testing after the cont12 data reconciliation, so the app is genuinely ready for
day-to-day use across Rhodes and Fox.

## User Feedback To Preserve
- Photo pages and photo modal views do not clearly show who uploaded a photo.
- "Added to archive" is not precise enough; date + time should be visible.
- Upload-date sort still looks wrong on live for recent photos.
- Recent uploads should sort with full timestamp precision, not date-only.
- The path to Gemini analysis is no longer obvious from public/admin photo views.
- Navigation between public share-ready identify pages and admin pages feels worse.
- Upload success CTA "Refresh to see inbox" sends the user to focus mode instead
  of browse mode; it should land on `/?section=to_review&view=browse`.
- Screenshots suggest there may be additional UX gaps around:
  - photo modal metadata density
  - photo detail discoverability
  - inbox visibility after upload
  - admin/public mode switching

## Concrete Screenshots / Examples
- Photo modal missing uploader clarity:
  - `/?section=photos&sort_by=upload_newest`
  - `/photo/7b7b3499b2006f61`
- Sort concern:
  - `fb_rhodes_holocaust_isaac_menashe_collection_*` should appear after the
    newer uploads and before the older Congo uploads according to the user’s
    real upload order.
- Public/admin navigation concern:
  - `/photo/f1ae3676f59943b2`
  - `/identify/a0a845d7-4eca-4255-b741-77ff310dc619`
- Inbox refresh concern:
  - upload confirmation should route to `/?section=to_review&view=browse`

## Working Hypotheses
- The underlying provenance data likely exists, but the UI is not surfacing it
  consistently across photo detail, modal, and public identify views.
- Recent sorting may still be mixing canonical-vs-alias metadata or using a
  timestamp fallback incorrectly on live cache entries.
- Gemini/face-analysis access is probably not gone, but its entry points became
  too implicit after the photo/public view changes.
- Upload success routing likely regressed to the historical focus-mode default.

## Required Outputs
- Code fixes for the reported UX/metadata/navigation issues.
- Clear verification evidence on the specific live paths/screenshots above.
- Harness updates:
  - prompt
  - context
  - session log
  - assessment
  - backlog/lessons if new patterns are found
