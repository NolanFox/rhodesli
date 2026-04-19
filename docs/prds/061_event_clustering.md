# PRD-061: Community-Scoped Event Clustering

**Status:** Specified (Session 153b planned; Session 155+ implementation)
**Author:** Session 153b (Claude + Nolan)
**Date:** 2026-04-19
**Priority:** P2 — ship AFTER PRD-059 Phase 4 is fully closed out
**Source:** `docs/feedback/session-153-event-clustering-research.md` (research agent af0449b5, 191 lines)
**Session reference:** Planned in Session 153b Phase 6; implementation targeted Session 155+

## Problem Statement

Each photo identification analysis today starts fresh. Shared outfits, backdrops, filename proximity, and same-day signals are visible to a human reviewer but never persisted as structured evidence. The canonical failure: three Charlie Fox photos (`02068_p_13akf5twbc3600.jpg`, `91b6f6b296e93a60`, `01659_p_13akf5twbc5249.jpg`) depict the same Belle Isle Conservatory visit (1917–1918, same 3 men, same suits) — but the archive has no mechanism to group them. This signal has been lost across multiple identification sessions.

Consequence: Nolan re-derives same-event context by hand each time he opens a new unidentified face. At 1121 photos and climbing, this is unscalable. Per the research agent: if event context narrows the candidate pool from "everyone in family" to "people present at this specific event," per-hour identification rate plausibly 2–3x.

## User Stories

- **As an admin identifying a new face**, I want to see "this face's events" not just "this face's photos" so that unknown companions can be triangulated against the other people at the same gathering.
- **As an admin browsing a person page**, I want to see "Esther appears in 17 events" and drill into each event's full photo set + companions.
- **As an admin viewing a photo page**, I want an "Event #42 (Belle Isle, ~1918)" badge with "5 other photos →" so that I don't lose the shared-event signal when jumping between photos.
- **As an admin**, I want to merge/split event groups when the heuristic gets it wrong, so that the persisted signal stays trustworthy.

## Proposed Solution (Tiered)

### Tier 1 — Rule-Based Fusion (MVP, this PRD)

Extend `scripts/event_grouping.py` community-wide. For each pair `(A, B)` within the same 5-year bucket, compute a same-event probability via weighted fusion:

```
score = 0.5 * shared_identity_count_normalized
      + 0.2 * clothing_jaccard
      + 0.2 * location_text_match
      + 0.1 * filename_proximity
```

Complete-linkage clustering (Lesson 115) within bucket. Threshold into four bands: **definitely same** (≥0.85), **probable** (0.60–0.84), **possible** (0.40–0.59), **unrelated** (<0.40).

Weights calibrated on a 30-pair labeled validation set (10 same, 10 same-venue-different-day, 10 different). Ship only if calibration hits ≥85% precision on same-event calls.

**Signals (all already available):**
- Shared identities from `photo_faces × identities` (strongest; PRD-059 Phase 2 exploits this today)
- `clothing_notes` from Gemini `date_labels.data.clothing_notes` (free-text Jaccard on tokenized wardrobe tokens)
- `location_estimate` / `scene_description` from Gemini (literal string match, case-insensitive, stop-worded)
- Filename proximity within same source collection (per-collection opt-in; default off for non-Charlie collections)

**Canonical positive control:** Photos `02068`, `91b6f6b296e93a60`, `01659` MUST cluster as a single event at Tier 1 ship. This is the acceptance tripwire.

### Tier 2 — CLIP Scene Embeddings (Follow-up, NOT this PRD)

Reserve for a separate session after Tier 1 is ≥2 weeks in production with admin feedback. Reuses `core/temporal.py`'s vendored CLIP ViT-B/32 (already loaded at startup — no new deps). One-shot 512-dim scene vector per photo, stored in `photo_scene_embeddings`. Cosine distance adds a scene-similarity signal to Tier 1's weighted fusion.

Deferred because:
1. CLIP was trained on modern web images; sepia/B&W scan performance is unknown. Needs empirical validation on a 50-pair labeled subset before committing.
2. Apple's published work explicitly warns clothing is only a same-event signal **within a date range**, not across — and scene embeddings may over-cluster "all beach photos." Complete-linkage with a high threshold is the mitigation, but that's a second PRD's worth of calibration.

### Tier 3 — Gemini Pairwise Adjudication (Admin tie-breaker only)

NOT a pipeline — O(N²) cost = ~$25k at current scale. Reserved as an admin button for borderline pairs in the 0.40–0.60 "possible" band. Logged to `gemini_api_calls` per AD-152. Budget: ~$4/year at realistic click volume. Out of scope for v1.

## Data Model

### New Supabase table: `events`

| column | type | notes |
|---|---|---|
| `event_id` | uuid PK | generated server-side |
| `community_id` | text | FK to `communities.id`; scoping per Lesson 108/112 |
| `display_name` | text nullable | human-assigned; `Event #42` placeholder when null |
| `date_range_start` | int | year, inclusive |
| `date_range_end` | int | year, inclusive |
| `confidence` | numeric | 0.0–1.0 from weighted fusion |
| `evidence_signals` | jsonb | `{shared_identity_count, clothing_jaccard, location_match, filename_proximity}` |
| `admin_confirmed` | boolean | default false; true when admin presses "confirm event" |
| `created_at` | timestamptz | |
| `updated_at` | timestamptz | |

### New Supabase table: `photo_events`

| column | type | notes |
|---|---|---|
| `photo_id` | text | FK to `photos.photo_id` |
| `event_id` | uuid | FK to `events.event_id` |
| `assignment_confidence` | numeric | 0.0–1.0; may differ from event-level confidence for peripheral photos |
| `admin_override` | boolean | true if admin manually attached/detached |
| PK | `(photo_id, event_id)` | a photo MAY belong to multiple events in rare cases (e.g., reunion spanning days) |

### Photo read-path augmentation

`photo_index.json` and the Supabase `photos` table do NOT add an `event_id` foreign key in v1 — the many-to-many relationship in `photo_events` handles it. The photo page template reads event membership via a new helper `get_photo_events(photo_id)` that hits the `photo_events` join with a TTL cache (120s, same pattern as existing registry caches).

### Rollback path

`events` and `photo_events` are additive. No existing table is touched. Feature-flag `EVENT_CLUSTERING_ENABLED=false` at rollback; the UI surfaces check this env flag and skip rendering event badges.

## Acceptance Criteria (Quantitative)

1. **Validation gate passed**: 30-pair labeled validation set achieves ≥85% precision on same-event pairwise calls. If below, do not ship; recalibrate weights or widen year bucket.
2. **Positive control**: Belle Isle trio (`02068`, `91b6f6b296e93a60`, `01659`) clusters as one event with confidence ≥0.85.
3. **Coverage**: All photos with `date_labels.best_year_estimate` populated receive event membership (or explicit `event_id=NULL` with reason "insufficient signal"). No silent drops.
4. **Latency**: Event assignment recomputation for 1121 photos completes in <60s offline; photo page render with event badge adds <50ms.
5. **UI surfaces live**:
   - Event badge on `/c/{community}/photo/{id}` ("Event #42 (Belle Isle, ~1918) — 5 other photos →")
   - Event-member expansion on `/c/{community}/person/{id}` ("Esther appears in N events")
   - Admin-only event merge/split buttons on event detail view
6. **Audit trail**: Every admin-initiated event merge or split writes an `audit_log` row (AD-225, AUDIT-001) with `actor`, `action`, `event_id`, `affected_photo_ids`, `reason`.
7. **PRD-059 Phase 4 integration**: Signal 2 (co-occurrence frequency) upgrades to use `photo_events` groupings instead of raw photo co-occurrence. Companion-by-event is strictly a superset signal.
8. **Community scoping**: Event assignment is scoped to a single community. Cross-community event linking is explicitly out of scope (separate PRD).

## Dependencies

- **BLOCKING: PRD-059 Phase 4 closure** must land first (browser verify, rejected-list UX, batch execute). Per research agent recommendation § 8: "Ship after PRD-059 Phase 4 is fully closed out. Then event clustering becomes the natural next rung." This is the #2 priority, not #1.
- **No new infrastructure** required for Tier 1. CLIP in `core/temporal.py` already vendored (Tier 2 only).
- **No new deps** — Tier 1 is pure Python + Supabase + existing Gemini fields.

## Algorithmic Decision Entries Required

Before any implementation code (per `.claude/rules/ml-development.md`):

- **AD-236:** Same-Event Scoring — Weighted Rule-Based Fusion (Tier 1). Rationale, rejected alternatives (CLIP-only, Gemini-pairwise adjudication), per-community weight calibration, 30-pair validation gate.
- **AD-237:** Event Entity Persistence — Supabase as source of truth vs derived-on-read. Rationale: event membership must be admin-editable (merge/split) and audit-logged, which requires persistent rows.
- **AD-238:** Deferred — CLIP Scene Embeddings for Same-Event (Tier 2). Document reopen trigger: ≥50-pair labeled set available AND Tier 1 in production ≥2 weeks with admin feedback that scene signal is missing.

## Out of Scope (v1)

- **CLIP scene embeddings** — Tier 2, separate PRD post-validation.
- **Cross-community events** — Charlie Fox + another descendant may both have Aunt Sadie's 1935 wedding. Community scoping first (Lesson 108, 112). Cross-community event linking is a separate PRD.
- **Gemini pairwise event adjudication as a pipeline** — cost-prohibitive at 628k pairs. Admin tie-breaker button only, reserved for Tier 3.
- **Auto-naming events** ("Belle Isle 1918") — v1 uses `Event #N` placeholder. Gemini-extracted `event_context` is stored as evidence, not promoted to display_name without admin confirm.
- **Full spatio-temporal learning** — no model training. Rule-based fusion only.
- **EXIF-based grouping** — historical scans have no reliable EXIF capture time (research agent § 2).

## Known Failure Modes (from research agent § 5)

| Failure | Mitigation |
|---|---|
| Belle Isle annually (Fox visits same venue 1918 AND 1925) | Require year agreement ±3 to enter candidate pool; clothing Jaccard splits them. |
| Studio repeat outfits across days | Weight clothing down when Gemini `photo_type == "studio_portrait"`. |
| Signal-poor singletons (1 face, no Gemini yet) | Emit `confidence="low"` or singleton event — acceptable. |
| Gemini hallucinates specific venues | Store venue as evidence field, never as truth. Require admin confirm before promoting to `display_name`. |
| Filename proximity is Charlie-specific | Per-collection opt-in flag. Default off. |
| Harry/Albert sibling false same-event | Known limitation (CLUSTER-QUALITY-001). Event clustering does not claim to fix sibling disambiguation — co-occurrence just narrows the candidate pool. |
| Upstream contamination into PRD-059 Phase 4 | Event membership passed to Phase 4 as evidence-with-confidence, never as hard constraint. Phase 4 already handles weighted signals. |

## Reference Existing Work

- `scripts/event_grouping.py` — current Phase 2 implementation, Esther/Albert scoped; generalize to community-wide.
- `rhodesli_ml/data/event_groups.json` — existing 18 groups across 246/554 dated photos (Esther/Albert scope).
- `core/temporal.py` — CLIP ViT-B/32 vendored and loaded at startup (Tier 2 reuse).
- `core/grouping.py` — complete-linkage + negative_ids pattern; event clustering inherits this.
- PRD-011 (Life Events & Context Graph) — schema ancestor from Session 91, never implemented. This PRD subsumes it for the event-clustering dimension.
- PRD-059 — Temporal co-occurrence (Phases 1–4). Phase 4 Signal 2 upgrades to use `photo_events`.
- `docs/ml/ALGORITHMIC_DECISIONS.md` — AD-005 (complete linkage), AD-048/231 (Gemini full preset), AD-235 (Family Cluster Score).
- Lesson 115 — single-linkage snowball; must use complete-linkage.
- Lesson 172 — event context > embedding distance for identification.

## Research Sources (external)

Per research agent § Sources:
- Apple — Recognizing People in Photos Through Private On-Device ML (two-pass design: clothing within event, face across)
- Cooray & O'Connor — ACM TOMM temporal event clustering
- Suh & Bederson — SAPHARI event-based clustering + clothing recognition
- Dai et al. — Family Member Identification WACV 2015
- Roboflow — CLIP + UMAP embedding clustering
- TMG — Scene detection on 2M historical press photos

Apple is the closest existence proof. Their design explicitly maps to Rhodesli: clothing is a same-event signal **within a date range**, face identity is the cross-event signal. This PRD's Tier 1 is the rule-based subset of their production system.

## Priority vs Backlog (honest take)

From research agent § 8:

- **Not the #1 priority on the board.** PRD-059 Phase 4 closure, WORKSPACE onboarding, mobile polish, and recurring data-integrity issues all outrank a new feature.
- **But the single largest unshipped signal** for identifying unknown faces in the Fox archive. If the next 20 hours of Nolan's triage time go into identifying Esther/Albert companions (current focus), Tier 1 plausibly 2–3x's per-hour identification rate.
- **Hard skepticism trigger**: if after 2 more identification sessions Nolan still says "I keep losing same-event signal," ship Tier 1 immediately. If he stops mentioning it, defer to Q3.

## Related

- `docs/feedback/session-153-event-clustering-research.md` — foundation research (191 lines)
- `docs/feedback/session-153-feedback.md` FB-005 — user-raised gap
- PRD-059 Phase 4 (temporal co-occurrence identity inference)
- PRD-011 (Life Events & Context Graph, superseded for events dimension)
- CLUSTER-QUALITY-001 (Harry/Albert sibling resemblance; event clustering does not claim to fix this)
