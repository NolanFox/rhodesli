# Session 96f-cont1 Assessment

## Verdict
PASS.

This file is the canonical human-readable summary for Session 96f-cont1.
It closes the remaining live-tested photo provenance, upload-ordering, and
public/admin navigation gaps that were still visible after Session 96f.

- Required gates are green:
  - `pytest tests/ -x -q` -> `4110 passed, 7 skipped`
  - `pytest rhodesli_ml/tests/ -x -q` -> `566 passed`
- Targeted regression slices are green:
  - `pytest tests/test_upload_provenance.py tests/test_photo_sorting.py tests/test_session83a_gaps.py -q` -> `43 passed`
  - `pytest tests/test_internal_photo_links.py tests/test_photo_sort_controls.py tests/test_upload_cache_invalidation.py tests/test_discovery_layer.py -q` -> `133 passed`
- Live app is current and healthy:
  - `/health` -> `200`, `1932` active identities, `939` photos, ML ready
  - production HTML reflects the new provenance summaries on both
    workstation and public photo cards
- No repo data files were changed in 96f-cont1.
  - No destructive data work was performed.
  - The separately dirty local `data/identities.json` delta was intentionally
    excluded from this continuation.

## What Closed

| Area | Root Cause | Fix |
|------|------------|-----|
| Workstation photo-card provenance | The workstation photos grid carried source/public-link metadata but did not surface uploader/archive-entry provenance where admins were actually sorting and debugging | Added a shared provenance helper and rendered provenance summaries directly on workstation photo cards |
| Public `/photos` metadata drift | The public photo list still built its own photo payload without threading through `uploaded_by` and `photo_index_order`, so it could drift from workstation behavior | Public `/photos` now carries the same provenance/tie-break metadata and renders the same provenance summary pattern |
| Exact-timestamp tie ordering | The earlier tie-break fix had not been propagated through every photo-list builder | Both public and workstation upload-date sorts now use archival `photo_index.json` insertion order when timestamps tie exactly |
| Photo-detail provenance hierarchy | Provenance existed but was visually buried too low in the photo detail stack | Moved the provenance line higher and standardized its wording through a shared helper |
| Public/admin handoff clarity | Public identify/person pages still pointed admins back into implicit/focus-oriented flows | Admin return links are now community-aware browse-mode queue links anchored back to the relevant entity |

## Live Verification

Direct production checks after the `c14fcc8` push:
- `https://rhodesli.nolanandrewfox.com/photos?sort_by=upload_newest`
  - public photo cards show provenance summaries such as:
    - `Uploaded Mar 11, 2026 at 2:52 PM UTC`
    - `Archive entry Mar 10, 2026 at 5:53 PM UTC`
    - `Uploader not recorded for this import`
- `https://rhodesli.nolanandrewfox.com/?section=photos&filter_collection=&filter_source=&sort_by=upload_newest&media_filter=all`
  - workstation photo cards now show the same provenance summaries
  - the tied March 10 import group now orders deterministically as:
    - `f1ae3676f59943b2`
    - `96eedab294d9e28a`
    - `51af15958c325349`
    - `a0edc4a0ddcbb54d`
    - `7b7b3499b2006f61`
    - `f0ecd2c69241c4dc`
    - `b971b34eeed322ae`
    - `d2642d16f5f0139c`
- `https://rhodesli.nolanandrewfox.com/photo/7b7b3499b2006f61`
  - public photo detail shows explicit historical-import wording with time
- `https://rhodesli.nolanandrewfox.com/photo/f1ae3676f59943b2`
  - public photo detail shows uploader attribution with full timestamp

Admin-only return-path behavior was verified by automated tests:
- identify-page admin links now use community-aware browse-mode queue URLs
- person-page admin links now use community-aware browse-mode queue URLs

## User Feedback Preserved

96f-cont1 was driven directly by live product testing:
- provenance still felt too hidden on photo cards and photo pages
- upload-date ordering was still hard to trust without visible time-of-day
- public/share-ready and workstation/admin paths still felt insufficiently
  connected
- the user wanted the longer-term person/photo activity timeline requirement
  preserved in the harness, not silently dropped

Those reports are preserved in:
- `docs/session_context/session-96f-cont1-context.md`
- `docs/prompts/session-96f-cont1-prompt.md`

## Remaining Follow-Up

No blocking regressions remain from the 96f-cont1 scope.

Longer-term work explicitly preserved:
- `AUDIT-001`: canonical actor attribution + entity timelines on `/person` and
  `/photo`
- `DATA-009`: automate stale-row prune-safe reconciliation
- `DATA-010`: automated cross-store drift monitoring

## Lessons Created

- **Lesson 129**: mirrored list builders must share the same metadata contract

## Related Artifacts

- Session context:
  - `docs/session_context/session-96f-cont1-context.md`
- Session prompt:
  - `docs/prompts/session-96f-cont1-prompt.md`
- Session log:
  - `docs/SESSION_LOG.md`
- Changelog entry:
  - `CHANGELOG.md` (`v0.97.12`)
- Roadmap entry:
  - `ROADMAP.md`
- Backlog:
  - `docs/BACKLOG.md`
- Lessons:
  - `tasks/lessons/data-lessons.md`
  - `tasks/lessons.md`
