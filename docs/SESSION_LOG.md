# Session 96f-cont1 Log — Provenance Visibility + Browse-Safe Admin Return
## Mission: close the last live-tested photo provenance, ordering, and public/admin navigation gaps after Session 96f
## Started: 2026-03-11
## Version: v0.97.12
## Assessment: docs/assessments/session-96f-cont1-assessment.md

### Phase 1: Continuation Capture
- [x] `docs/session_context/session-96f-cont1-context.md` created with the new live-tested continuation scope
- [x] `docs/prompts/session-96f-cont1-prompt.md` created so the continuation remains resumable after interruption
- [x] Preserved the user's concrete follow-up reports:
  - provenance still too hidden on photo cards and photo pages
  - upload ordering still felt suspect without visible full timestamps
  - public/share-ready vs admin/workstation handoff still too implicit
  - per-entity timeline / actor attribution requirement must remain breadcrumbed

### Phase 2: Product Fixes
- [x] `app/main.py`: added a shared provenance helper and surfaced provenance summaries directly on workstation photo cards
- [x] `app/browse_routes.py` + `app/page_routes.py`: public `/photos` now threads `uploaded_by` and `photo_index_order` through its photo payloads and cards
- [x] `app/main.py` + `app/browse_routes.py` + `app/page_routes.py`: upload-date sorting now stays deterministic across both workstation and public photo lists
- [x] `app/page_routes.py`: photo-detail provenance moved higher in the metadata stack and reuses the shared wording
- [x] `app/page_routes.py` + `app/person_routes.py`: admin return links from public identify/person pages now point to community-aware browse-mode queue URLs
- [x] Timeline/actor-attribution requirement preserved in backlog rather than dropped during the UX cleanup

### Phase 3: Verification
- [x] Targeted regression slices:
  - `pytest tests/test_upload_provenance.py tests/test_photo_sorting.py tests/test_session83a_gaps.py -q` -> `43 passed`
  - `pytest tests/test_internal_photo_links.py tests/test_photo_sort_controls.py tests/test_upload_cache_invalidation.py tests/test_discovery_layer.py -q` -> `133 passed`
- [x] Full required gate:
  - `pytest tests/ -x -q` -> `4110 passed, 7 skipped`
  - `pytest rhodesli_ml/tests/ -x -q` -> `566 passed`
- [x] Live `/health` -> `200`, `1932` active identities, `939` photos, ML ready
- [x] Live HTML verified:
  - `/photos?sort_by=upload_newest` shows new provenance summaries on public photo cards
  - `/?section=photos&sort_by=upload_newest` shows the same provenance summaries plus the corrected tied-photo order
  - `/photo/f1ae3676f59943b2` shows uploader timestamp with time
  - `/photo/7b7b3499b2006f61` shows explicit archive-import wording with timestamp

### Phase 4: Documentation + Lessons
- [x] `docs/assessments/session-96f-cont1-assessment.md`
- [x] `CHANGELOG.md` updated with `v0.97.12`
- [x] `ROADMAP.md` updated with `v0.97.12` closeout entry
- [x] `docs/BACKLOG.md` status line refreshed to the verified current build
- [x] Lesson `129` added in `tasks/lessons/data-lessons.md` and indexed in `tasks/lessons.md`
- [x] No repo data files staged into Session 96f-cont1; the separate local `data/identities.json` delta remained untouched

### Predecessor
- Session 96f (`v0.97.11`) closed the larger live UX + audit hardening pass
- Session 96f-cont1 finished the smaller but still user-visible provenance/order/navigation follow-up discovered during continued live use

### Key Commits
- `622bf81` `[codex] docs(session): add 96f-cont1 prompt and context`
- `c14fcc8` `[codex] fix(ux): surface provenance and browse-safe admin links`
