# Session 102 Context — Performance, Speed Loop Fixes, Navigation Wiring, and Triage Sprint

**Predecessor:** `docs/session_context/session-101-context.md`
**Feedback source:** `docs/feedback/2026-03-14-fox-triage-round2.md` (22 items, FB-120–FB-141)
**Current state:** v0.99.3 → targeting v1.0.0, 4276 tests, 941 photos, 3412 identities, ~86 confirmed

---

## What Happened in Session 101

Session 101 (Phase 6 = triage sprint with Nolan) produced 22 new feedback items. The fixes from Sessions 100f/101 (Phases 1–5) worked — enrichment panel reorder, GEDCOM auto-rename, merge confirmation, cross-community badges, cache repopulation — but exposed a deeper set of issues:

1. **Speed Loop is fundamentally broken** — assignments don't persist (FB-141, BUG-001). The most critical bug in the app right now.
2. **Site is too slow** — GEDCOM search takes ~1 minute (FB-120), Similar panel 5–10s (FB-127). Users feel it every action.
3. **Speed Loop exists but is disconnected** — broken "Start Speed Loop" button (FB-138), no path from speed-run → photo context → face tagging (FB-135), bounding boxes misaligned (FB-139).
4. **Data leaking across communities** — Rhodes photos in Fox Family speed-run (FB-129), Charles Fox lost his name during triage ops (FB-122).
5. **Batch cluster validation is not useful** — pre-selects 1164 clusters, shows 1 face each, dangerous confirm-all (FB-130).
6. **Navigation dead ends** — clicking face goes to public identify page (FB-134), no admin tools there (FB-136), no connected path back.

---

## Priority Order (from Nolan)

1. **PERFORMANCE** — site is too slow, speed mode doesn't feel fast. #1 blocker.
2. **DATA INTEGRITY** — Speed Loop doesn't save (BUG-001), name loss pattern (Charles Fox, FB-122), cross-community data contamination (FB-129).
3. **NAVIGATION / FLOW** — no connected path between speed-run ↔ photo context ↔ face tagging.
4. **Speed Loop fixes** — alignment, saves, discoverability, community scoping.
5. **Batch validation rethink or removal**.
6. **Triage sprint with Nolan** (last phase — real-time fix/log session).

---

## The 22 Feedback Items, Organized by Theme

### Theme A: Performance (Blocking, P0/P1)

| ID | Severity | Summary | Root Cause |
|----|----------|---------|------------|
| FB-120 | P2 | GEDCOM search ~1 minute for "Albert Fox" | ILIKE scan on 21K rows, no index, auto-fires on panel open |
| FB-127 | P2 | Similar Identities panel 5–10s | Full embedding scan on ~3400+ identities, no community scope |

**Root cause (FB-120):** `/api/gedcom/search` runs an ILIKE OR across `name`, `given_name`, `surname` on 21,809 rows with no index. "Fox" returns 196 results. The panel fires immediately on load. Fix: Postgres GIN trigram index on GEDCOM names, plus debounce / min-char-count before firing.

**Root cause (FB-127):** `neighbors_sidebar` (or similar endpoint) does full pairwise embedding scan. With 3412+ identities and 941+ photos this is a full distance computation. No community-scoped shortcut. Fix: limit scan to same-community faces first, then expand; or precompute neighbor lists during save.

**BACKLOG refs:** PERF-005 (similar panel), UX-077 (GEDCOM speed). New: PERF-006 (GEDCOM index).

---

### Theme B: Speed Loop Broken (P0 — Data Loss)

| ID | Severity | Summary |
|----|----------|---------|
| FB-141 | P0 | Speed Loop tags don't save — all assignments silently dropped |
| FB-139 | P1 | Face bounding boxes misaligned, tag panel floating disconnected |
| FB-138 | P1 | "Start Speed Loop" button didn't trigger navigation |
| FB-140 | P2 | Tag search shows cross-community identities unsorted |

**Root cause (FB-141):** The Speed Loop (`?seq=1`) tag assignment endpoint is either not being called, or the save path is broken. The loop ADVANCES (visual feedback) but the identity is not updated. This is the same silent-fail pattern as DATA-014 (Supabase sync failures with `except: pass`). Investigation needed: what does the tag POST endpoint do, what does it return, where does the save fail?

**Files to check:**
- `app/page_routes.py` — the `?seq=1` photo route and tag assignment handler
- The POST route that handles the inline name tag submission on the photo page
- `save_registry()` call — does it actually run? Does it check for success?

**Root cause (FB-139):** CSS coordinate mismatch — bounding box positions calculated from original image dimensions but rendered at a different display scale. The photo container's `offsetLeft/offsetTop` may not be accounted for in the overlay positioning JS. Similar to the bbox overlap bug from Session 100b (DOGFOOD-001), but for the speed loop overlay specifically.

**Root cause (FB-138):** "Start Speed Loop" button likely has a broken `href` or `onclick`. The `?seq=1` URL itself works (Nolan verified the flow once inside it). The entry point is broken.

**BACKLOG refs:** BUG-001 (critical save bug), UX-089 (discoverability), UX-090 (bbox alignment), UX-091 (search community scoping).

---

### Theme C: Navigation / Connected Flow (P0 Product Gap)

| ID | Severity | Summary |
|----|----------|---------|
| FB-135 | P0 | No connected path: speed-run ↔ photo context ↔ face tagging |
| FB-134 | P1 | Clicking face in photo → public identify page, not admin tag flow |
| FB-137 | P1 | Identify Mode is purely cosmetic — doesn't change click behavior |
| FB-136 | P2 | No merge/admin tools on /identify/ page |
| FB-138 | P1 | Speed Loop entry point broken |
| FB-133 | P2 | Photo-first identification is better for group photos |

**Root cause (FB-135):** Each part of the triage workflow (speed-run, photo page, identify page) was built independently. No "back to speed-run" context is passed through the chain. Speed-run links go to `?from=admin` (added in 101) but there's no return path.

**Desired connected flow:**
```
speed-run card → (click face crop) → photo page with Speed Loop active
photo page → (tag face inline) → return to speed-run at same position
speed-run → (click person link) → person page with admin context
person page → (back) → speed-run (not browser back — explicit link)
```

**Root cause (FB-137):** "Identify Mode" was built in Session 82e as visual-only (pulse animation, "?" badges). It was always intended to enable inline tagging but that was never implemented. FB-138 and FB-137 point to the same gap: Speed Loop IS the inline tagging UX that Identify Mode should activate.

**Implementation direction:**
- Identify Mode button → activates `?seq=1` Speed Loop (or redirects to it)
- Face clicks in Speed Loop → open inline tag panel anchored to the face (not navigate away)
- "Tag faces in this photo" CTA in speed-run enrichment panel → opens photo in Speed Loop mode
- Speed Loop completion → return to speed-run with `?after_photo={photo_id}` param

**BACKLOG refs:** UX-085, UX-086, UX-087, UX-088, UX-089.

---

### Theme D: Data Integrity (P0/P1)

| ID | Severity | Summary |
|----|----------|---------|
| FB-122 | P0 | Charles Fox lost name during triage (REGRESSION — DATA-017) |
| FB-129 | P1 | Rhodes community photos in Fox Family speed-run |
| FB-123 | P2 | Person 2795 — unnamed CONFIRMED cluster, needs decision |
| FB-124 | P2 | Merge search can't find people with lost names |

**Root cause (FB-122):** `save_registry()` Postgres shadow write (non-blocking, Session 101 Phase 4) may silently overwrite a named identity with the local registry's auto-generated name if local and production were out of sync. The prevention rule: **never overwrite a non-auto-generated Postgres name with an auto-generated local name**. The sync function needs a guard: `if local_name.startswith("Unidentified") and postgres_name != local_name: skip name field in upsert`.

**Root cause (FB-129):** Community-batch ingest (2026-02-14, Charlie Fox photos) accidentally included Rhodes-community photos (collection="Jews of Rhodes: Family Memories & Heritage"). The `identity_communities` table mapped these identities to Fox Family because the batch was tagged Fox. Fix: re-assign based on `collection` field, or build admin photo re-assignment UI.

**BACKLOG refs:** DATA-017 (already in BACKLOG), DATA-018, DATA-019. New: DATA-020 (Postgres name protection guard).

---

### Theme E: Batch Cluster Validation Rethink (P1)

| ID | Severity | Summary |
|----|----------|---------|
| FB-130 | P1 | Page not useful — 1164 pre-selected clusters, 1 face each, dangerous confirm-all |
| FB-128 | P2 | Page 404s at expected URL + not wired to any nav |
| FB-131 | P3 | Truncated UUIDs beneath cluster cards |

**Product direction (from FB-130):**
- Do NOT invest more in this page until PIPELINE-001 (incremental clustering audit) is done
- If revived: show ALL faces per cluster (expandable/inline), don't pre-select, require min interaction before bulk confirm
- Wire to nav OR remove — Lesson 138 (3rd+ occurrence)
- For Session 102: either fix nav wiring + multi-face display, or remove the page entirely

**BACKLOG refs:** UX-080 (nav wiring), UX-081 (rethink/remove), PIPELINE-001 (clustering audit). New: TEST-002 (unwired route detection test, FB-132).

---

### Theme F: Already Fixed in Session 101

| ID | What was fixed |
|----|---------------|
| FB-121 | GEDCOM Link auto-renames identity — unified save+link action |
| FB-122 | Charles Fox name restored via production API |
| FB-125 | Noted but in BACKLOG (UX-079) |

---

## Cross-References to Existing BACKLOG Items

| FB Item | BACKLOG ID | Status |
|---------|-----------|--------|
| FB-120 (GEDCOM slow) | UX-077 → rename to PERF-006 | OPEN |
| FB-121 (save+link unified) | — | FIXED Session 101 |
| FB-122 (name loss prevention) | DATA-017 (existed for Galante) → DATA-020 new | OPEN |
| FB-123 (Person 2795) | — | NEEDS DECISION |
| FB-124 (merge search) | UX-078 | OPEN |
| FB-125 (photo links community) | UX-079 | OPEN |
| FB-126 (document photos) | DATA-018 | OPEN |
| FB-127 (similar panel slow) | PERF-005 | OPEN |
| FB-128 (batch page 404) | UX-080 | OPEN |
| FB-129 (Rhodes in Fox) | DATA-019 | OPEN |
| FB-130 (batch not useful) | UX-081, PIPELINE-001 | OPEN |
| FB-131 (UUIDs on cards) | UX-082 | OPEN |
| FB-132 (nav audit) | UX-083, TEST-002 | OPEN |
| FB-133 (photo-first triage) | UX-084 | OPEN |
| FB-134 (face click → public) | UX-085 | OPEN |
| FB-135 (no connected flow) | UX-086 | OPEN |
| FB-136 (no admin on /identify/) | UX-087 | OPEN |
| FB-137 (Identify Mode cosmetic) | UX-088 | OPEN |
| FB-138 (Speed Loop unreachable) | UX-089 | OPEN |
| FB-139 (bbox misaligned) | UX-090 | OPEN |
| FB-140 (search cross-community) | UX-091 | OPEN |
| FB-141 (Speed Loop doesn't save) | BUG-001 | OPEN — **CRITICAL** |

---

## Root Cause Analysis: The Core Three Problems

### Problem 1: Performance
Every operation reloads from Supabase (120s TTL) AND from JSON (atomic file read). With 3412 identities at ~380KB, every merge/save/rename is:
- JSON parse (~3412 identities)
- Supabase upsert (background thread, may queue up)
- GEDCOM search = separate ILIKE scan on 21K rows
- Similar panel = full embedding distance scan

**Fix targets:**
- GEDCOM: GIN trigram index + min 3 chars before firing
- Similar: community-scoped scan first, precompute top-N neighbors on save
- Registry: verify 120s TTL is being HIT (not bypassed) on all endpoints

### Problem 2: Speed Loop Save Bug (BUG-001)
The Speed Loop (`?seq=1`) visually advances but silently drops assignments. This is the worst kind of bug — it looks like it works. The save path likely has an uncaught exception (Lesson 136: `except: pass` on Supabase syncs creates invisible data loss), or the tag POST endpoint updates a different data structure than what's displayed.

**Investigation steps:**
1. Add logging around the Speed Loop tag POST handler
2. Verify `save_registry()` is called and returns without error
3. Check if the display reads from a different source than the save path writes to
4. Test: tag a face, immediately reload the photo page, check if identity state changed

### Problem 3: Navigation Disconnection
Each piece of the triage system was built by a different session for a different spec. Speed-run (Sessions 100c/f), Speed Loop (Session 82e + Photo page), Identify Mode (Session 82e), batch validation (Session 100f) — none were designed to connect to each other.

**Minimum viable connected flow:**
```
Speed-run → view source photo (existing: crop links open photo in new tab)
Photo page → "Tag faces" = Speed Loop mode (NEW: Identify Mode → activates ?seq=1)
Speed Loop → tag face → continue (FIX: save bug) + "Done with photo → back to speed-run"
Speed-run → person card → person page (existing: ?from=admin added in Session 101)
Person page → "Back to Review" → speed-run at position (NEW: explicit back link)
```

---

## Architectural Decisions Needed

### AD-NNN: Speed Loop Save Path Fix
- **Decision:** Where is the authoritative save in the Speed Loop tag flow?
- **Context:** FB-141 shows saves aren't persisting. Need to audit the tag POST handler.
- **Risk:** Fix could inadvertently affect non-Speed-Loop face tagging if they share a handler.

### AD-NNN: Identify Mode → Speed Loop Unification
- **Decision:** Should "Identify Mode" button become the Speed Loop entry point?
- **Context:** FB-137 shows Identify Mode is cosmetic-only. FB-138 shows Speed Loop is the right UX but unreachable. They should be the same thing.
- **Options:** (A) Identify Mode button navigates to `?seq=1` (simplest). (B) Identify Mode activates an HTMX overlay that mimics Speed Loop inline (no navigation). Option A is faster and reuses tested code.

### AD-NNN: Batch Validation Page — Fix or Remove
- **Decision:** Invest in fixing batch validation (multi-face expand + nav wiring) or remove it?
- **Context:** FB-130 shows the current implementation is not useful and potentially dangerous. PIPELINE-001 (clustering reliability audit) is a prerequisite for making this valuable.
- **Recommended:** Remove the page from nav (it's already unwired), mark it DEFERRED in BACKLOG with PIPELINE-001 as dependency. Don't invest until clustering is audited.

---

## Files Likely Modified in Session 102

- `app/page_routes.py` — Speed Loop tag save bug, face click behavior, Identify Mode wiring
- `app/cluster_review_routes.py` — Speed Loop → speed-run return path, performance improvements
- `app/relationship_routes.py` — GEDCOM search index / debounce
- `app/main.py` — Similar panel community scoping, Postgres name protection guard
- `core/registry.py` — name protection in shadow sync path
- `tests/test_page_routes.py` — Speed Loop save tests
- `tests/test_cluster_review_routes.py` — navigation flow tests
- SQL migration — GIN trigram index on gedcom_individuals name columns

---

## Parallelization Plan

Three independent tracks that can run simultaneously:

**Track A: Performance** (worktree `session-102/perf`)
- GEDCOM GIN trigram index + min-char debounce
- Similar panel community-scoped scan
- Verify TTL cache hits on all hot endpoints
- Log timing before/after on all three

**Track B: Speed Loop Save + Alignment** (worktree `session-102/speed-loop`)
- Investigate and fix BUG-001 (tag assignments not persisting)
- Fix FB-139 (bbox misalignment in Speed Loop)
- Fix FB-138 (broken "Start Speed Loop" button)
- Fix FB-140 (community-scoped tag search)

**Track C: Navigation Wiring** (worktree `session-102/nav`)
- Identify Mode → Speed Loop activation (FB-137 + FB-138)
- Photo page: face click → admin tag panel when admin (FB-134)
- Speed Loop → "Back to review queue" return link (FB-135)
- Add admin tools to /identify/ page (FB-136)
- Fix community URL prefixes on speed-run face links (FB-125, UX-079)

**Merge order:** B first (fixes the P0 data loss), then C (navigation depends on B working), then A (independent, can merge at any point). Final phase: deploy + triage sprint with Nolan.

---

## Data Integrity Rules for This Session

- **NEVER** overwrite a non-auto-generated name in Postgres shadow sync (FB-122 prevention)
- **EVERY** save in Speed Loop must be verified with a test that reloads and checks state
- **NO** community data contamination — verify Fox Family speed-run only shows Fox Family photos after DATA-019 fix
- **AUDIT** DATA-019 fix: re-assign community-batch-20260214 photos to correct community based on `collection` field BEFORE the triage sprint

---

## Known Risks

- **Speed Loop save fix** could break non-Speed-Loop tagging if handlers share code — test both paths
- **Identify Mode change** could break public Identify Mode UX if not guarded by `is_admin`
- **GEDCOM index migration** requires a Supabase SQL migration — test locally first
- **Community re-assignment (DATA-019)** could move photos that are correctly in Fox Family — verify collection field values before running
- **Batch validation removal** — if Nolan decides to keep it, need multi-face expand + nav wiring in same session

---

## Deferred from Session 101 (Not for Session 102)

- FB-126 (document photos in triage) — DATA-018, BACKLOG
- FB-123 (Person 2795 unnamed cluster) — NEEDS NOLAN DECISION, not code
- FB-133 (photo-first triage mode) — UX-084, future PRD
- PIPELINE-001 (incremental clustering audit) — prerequisite for batch validation revival

---

## Post-Session 102 Breadcrumbs

- Session 102 should update `docs/session_context/session-102-context.md` (this file) with:
  - What was fixed vs deferred
  - New BACKLOG items from triage sprint
  - Lessons learned
- ROADMAP.md: add Session 102 to Recently Completed, mark work items
- BACKLOG.md: add FB-120 through FB-141 as numbered items, mark fixed ones DONE
- CHANGELOG.md: v1.0.0 if Speed Loop save + Performance + Navigation all ship
