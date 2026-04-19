# Session 153 — Event-Clustering Feature Research

**Status:** Research-only. No code/data changes. Nolan to review before any PRD.
**Question:** Is "photos-from-the-same-event" auto-grouping worth building, and what would it take?
**Trigger:** Confirmation that `02068_p_13akf5twbc3600.jpg`, `91b6f6b296e93a60`, and `01659_p_13akf5twbc5249.jpg` are the same Belle Isle 1917–1918 event (same 3 men, same outfits). Repeated cross-session loss of this signal.

---

## 1. Internal State — what we already have

### Already in production
- **`scripts/event_grouping.py`** (PRD-059 Phase 2) — runs on Esther/Albert photos only. Produces `rhodesli_ml/data/event_groups.json` (14,674 lines, 18 groups, 15 multi-photo).
- **Algorithm today** — NOT 5-year-window union-find as originally speced. Current impl:
  1. Fixed 5-year buckets (1915–1919, 1920–1924…) based on `best_year_estimate`
  2. Within each bucket, union-find photos that share ≥1 identified identity (Lesson 115 — moved off ±2-year sliding window to avoid snowball).
  3. Output: `photo_ids[]`, `date_range`, `identified_faces`, `unidentified_faces`, `all_face_ids`.
- **Co-occurrence matrix** — 391 pairs across 102 identities, rebuilt from photo_faces × identities. Backs "Frequent Companions" panel.
- **Gemini "full" preset** (AD-048, AD-231) — already extracts `scene_description`, `controlled_tags`, `clothing_notes`, `visible_text`, `location_estimate`, `group_composition`, `face_analysis[].estimated_age`, `event_context`, `relationship_inference` (added Session 151). 554 dated photos in Supabase `date_labels`.
- **`core/temporal.py`** — CLIP ViT-B/32 (`laion2b_s34b_b79k`) already vendored for era classification (1890–1910 / 1910–1930 / 1930–1950). **Infra for visual embeddings exists** — we just don't use it for scene similarity.
- **`core/grouping.py`** — union-find w/ complete-linkage, co-occurrence block. Not directly usable for events but the patterns (complete-linkage, negative_ids) carry over.

### Close but unfinished
- **PRD-011 (Life Events & Context Graph)** — stub from Session 91, planned event type + participants + location + date schema. **Never implemented.** Would be the persistent home for event entities.
- **PRD-059 Phase 4** — identity inference engine; Signal 2 (co-occurrence) already uses event groups, so the plumbing is warm.
- **`core/event_recorder.py`** — misleading name; just a JSONL audit log for user actions. Not related.

### Gaps
- Event grouping is **scoped to 2 target identities** (Esther, Albert). 875 other photos have no event membership.
- **No scene/visual embedding** is stored per photo. CLIP could be invoked, but nothing persists embeddings.
- **No event entity table** — groups live in a JSON blob, regenerated end-to-end per run; no event_id stable across runs, no UI surface, no admin merge/split.
- Gemini's `event_context` is text-only; not parsed into a structured key (e.g., "Belle Isle 1918").

---

## 2. External state-of-the-art (skeptical read)

| System | Approach | Relevance |
|---|---|---|
| **Apple Photos "Moments"** | Two-pass: (1) upper-body embedding within same time/location moment; (2) face embedding across moments. Clothing signal explicitly restricted to same-moment because "clothing consistency is useful signal only within the same event timeframe." | Direct match. Validates the "same outfit = same event" heuristic, and warns against applying it cross-event. |
| **Google Photos** | Time + GPS + scene-similarity fusion; curated best-shots per event. Depends on EXIF. | **Doesn't transfer.** Historical scans have no GPS, no reliable EXIF capture time. |
| **Academic: Cooray & O'Connor 2005 / Graham et al.** (ACM TOMM) | Multi-scale temporal similarity + content (color histogram) fusion. Unsupervised. Works with date/time metadata. | Partial — temporal axis is estimated, not observed. Fusion approach is the right template. |
| **SAPHARI (Suh & Bederson, 2007)** | Event-based clustering + clothing-based person recognition for semi-auto annotation; assumes same-day same-clothes. | Closest prior art to what Nolan is asking for. Established that clothing helps within events, not across. |
| **Dai et al. WACV 2015 "Family Member Identification from Photo Collections"** | Consistency constraints (same-person-once-per-image, role consistency) for holistic family identification. | Useful framing for Phase 4 identity inference, but same-event grouping is a preprocessing step. |
| **Immich / PhotoPrism / DigiKam** | Face clustering (DBSCAN variants). **No dedicated event clustering** surfaced in documentation — they rely on EXIF time. | Open-source bar is low; we would be ahead, not behind. |
| **CLIP + UMAP embedding clustering** (Roboflow, Voxel51, 2025) | CLIP scene embeddings cluster intuitively by setting/activity; UMAP for exploration. | **Practical Tier-2 path.** CLIP is already in our deps. |
| **TMG 2024, Probing Historical Image Contexts (JOCCH)** | Scene detection + transfer learning on digitized historical press archives. 2M photos / 250k events. | Validates the approach scales — but they had human-curated event metadata for training. |

**Takeaway:** Apple is the closest existence proof. Their two-pass design (clothing within event, face across) maps cleanly to ours if we can bootstrap "events." They explicitly say clothing alone is **not** a same-event signal across dates — studio shoots, repeat outfits, etc. This matches Nolan's own skepticism.

---

## 3. Signal inventory

| Signal | Have today? | Per-pair cost | Strength | Failure mode |
|---|---|---|---|---|
| Shared identities (≥2 confirmed) | Yes (photo_faces + identities) | O(1) | **Strong** — this is what PRD-059 already exploits | Weak for singleton-person photos; siblings that look alike still confound |
| Estimated year (Gemini `best_year_estimate`) | Yes, 554 photos | O(1) | Medium — ±2y noise is normal | ~25 photos currently with 0% or wildly off estimates |
| Clothing notes (Gemini `clothing_notes`, free text) | Yes | O(1) text match | Medium **within ±1y** | Repeat wardrobes, formal wear reuse |
| Scene description / location_estimate (Gemini) | Yes | O(1) text match | Medium — "Belle Isle Conservatory" matches exactly in the trigger case | LLM hallucinates specific venues; "beach" matches every beach photo |
| Controlled tags | Yes | O(1) set overlap | Weak-medium | Too coarse (e.g., "outdoor, group") |
| Visual scene embedding (CLIP) | **Infra exists, not stored** | ~50ms/photo local, negligible at 1k scale | Medium-strong for venue/composition match | All beach/studio photos cluster together |
| Face embedding co-occurrence (unidentified faces) | Yes (InsightFace 512-dim) | O(F×F) per group | Strong once ≥2 faces overlap | Harry vs Albert problem (CLUSTER-QUALITY-001) |
| Filename sequence (Charlie Fox `02068_p_*`) | Yes | trivial | **Strong in this one collection** | Brittle — breaks on any non-Charlie scan; number ≠ chronology everywhere |
| EXIF | No (scans) | — | N/A | Absent |
| Human annotations / event_context free text | Yes, sparse | text match / Gemini parse | Strong when present | Present on <5% of photos |
| Gemini "same event?" pairwise call | Feasible | ~$0.04/pair @ 3.1 Pro | Strongest per-pair | O(N²) scaling kills it above ~100 photos |

---

## 4. Three-tier feasibility

### Tier 1 — Rule-based fusion (1 session)
**What:** Extend `event_grouping.py` community-wide. For each pair `(A, B)` in the same 5-year bucket, compute a same-event probability:
```
score = w1·shared_identity_count + w2·clothing_jaccard + w3·location_match + w4·filename_proximity
```
Threshold into (definitely same / probable / possible / unrelated). Store in `photo_events` table with `event_id`, `confidence`, `evidence_signals{}`.
- **Cost:** 1 session, zero API spend, ~100 LOC.
- **Coverage:** 554 dated photos today, auto-extends as `date_labels` grows.
- **Accuracy estimate:** ~70–80% precision on Fox subset based on PRD-059 Phase 2 hit rate. **No new failure modes.**
- **Deliverable unlock:** "This photo belongs to Event #42 (Belle Isle, 1917–1918)" badge on photo page; admin merge/split events; feeds Phase 4 Signal 2 at higher resolution.

### Tier 2 — Add CLIP scene embedding (2 sessions)
**What:** Run `core/temporal.py`'s CLIP model (already loaded at startup for era classification) over every photo, store 512-dim scene vector in Supabase `photo_scene_embeddings`. Use cosine distance as an additional signal in Tier 1's score. Complete-linkage threshold (Lesson 115).
- **Cost:** ~50ms × 1121 photos = 1 min one-shot local job; ~2 MB storage. Retraining not required — CLIP is frozen. Adds ~200ms to upload path (acceptable, or move to ML service — TOOLS-002 already deployed).
- **Accuracy estimate:** Apple's architecture is the proof — scene + face is robust. Risk: CLIP trained on modern web images; may under-perform on sepia/BW scans. **Validate on 50-pair labeled subset before committing.**
- **Deliverable unlock:** Catches same-venue photos without shared identities (e.g., solo shots in the same Belle Isle conservatory); enables "photos taken in same place" query.

### Tier 3 — Gemini-multimodal pairwise adjudication (targeted only)
**What:** For admin-flagged borderline pairs, pass both images to Gemini 3.1 Pro with prompt "Are these the same event? Explain signals." Log to `gemini_api_calls` per AD-152.
- **Cost:** $0.04/call × realistic ~100 admin clicks/year = $4/year. **Fine as a precision tool, terrible as a pipeline.** O(N²) over 1121 photos = ~628k pairs × $0.04 = $25k, not happening.
- **Use:** Tie-breaker when Tier 1+2 score is in the 0.4–0.6 band AND admin is actively reviewing. Not a batch job.

### Recommendation
**Ship Tier 1 first.** The marginal evidence gain over what PRD-059 Phase 2 already computes is large (extends Esther/Albert logic to the whole archive, introduces persistent event entities, adds clothing/location signals). Defer Tier 2 until we have a 50-pair labeled set to measure CLIP's contribution honestly. Keep Tier 3 as an admin button, not a pipeline.

---

## 5. Where this breaks (honest failure modes)

| Failure | Probability | Mitigation |
|---|---|---|
| **Belle Isle annually:** Fox family visits same conservatory in 1918 AND 1925. Outfits differ, people partly overlap. | Medium — we know Fox had Detroit base. | Require year agreement ±3 to enter candidate pool; clothing signal splits them. Same-event score drops when clothing_jaccard low. |
| **Studio repeat outfits:** Formal portrait sittings over multiple days in same suit. | Low for family photos, higher for professional portraits. | Weight clothing signal down when Gemini `photo_type == "studio_portrait"`. |
| **Signal-poor singletons:** Photo with 1 face, no Gemini analysis yet. | High today (Gemini covers 554/1121). | Tier 1 produces `confidence="low"` or singleton group — fine. |
| **Cross-collection same event:** Charlie Fox + another descendant both have Aunt Sadie's 1935 wedding. | Medium. | Event assignment should be **community-scoped** first (Lesson 108, 112). Cross-community event linking is a separate PRD — do NOT conflate. |
| **Harry/Albert in same event:** Both appear; ML says "Albert × 2." | Already known (CLUSTER-QUALITY-001). | Event clustering makes this **worse** in one direction (both flagged as same event member) but **better** in another (temporal co-occurrence + companion analysis narrows it). Don't promise this fixes sibling disambiguation. |
| **Gemini hallucinates specific venues:** "Belle Isle Conservatory" may not actually be Belle Isle. | Medium — Gemini 3.1 Pro is confident even when wrong (AD-051). | Store venue as evidence, not truth. Require human confirm before making it an anchor. |
| **Every beach looks alike (CLIP Tier 2):** Cosine distance 0.2 between all beach photos. | High if we adopt CLIP naively. | Use CLIP **only as tiebreaker within year bucket**, never as primary signal. Complete-linkage with high threshold. |
| **Filename proximity is Charlie-specific:** `01659_*` and `02068_*` are 400 apart but same event. Doesn't work for Rhodes or Fader. | Known. | Treat as a per-collection opt-in signal. Default off. |

---

## 6. Value for Rhodesli specifically

- **1121 photos total, ~636 Charlie Fox, ~196 Esther, ~165 Albert** (with heavy overlap).
- Photos that would benefit **today** (Gemini-dated + Fox family): ~250. Over next 6 months (finishing Gemini coverage): ~1000.
- User workflow unlocked:
  1. Photo page: "This photo is part of Event #42 (Belle Isle, ~1918). 5 other photos →"
  2. Person page: "Ester appears in 17 events, click to expand each event's photo set and companions."
  3. **Identification spread:** Nolan's core hypothesis — "if we know the men in photo A are Fox brothers, new women in photo B (same event) are likely Fox in-laws." This is concretely what Phase 4 Signal 2 wants. Event granularity > photo granularity here.
  4. Uncovered events: photos that cluster together but contain NO identified person → prompt for collective identification.

**Risk of wrong grouping:**
- False-positive event merge → admin looks at Belle Isle 1918 pics, sees a 1925 photo bleeding in. Low damage (visual inspection catches this). Mitigable by admin event-split UI.
- False-negative (same event not grouped) → status quo. No damage, just lost opportunity.
- **Upstream contamination risk:** if event membership feeds Phase 4 identity suggestions, a wrong event group propagates to wrong identity suggestions. Mitigation: treat event membership as **evidence with confidence**, never as a hard constraint. Phase 4 already does this for other signals.

---

## 7. Recommended next step

**PRD-061: Community-Scoped Event Clustering (Tier 1)** — 1-session implementation.

Core elements the PRD must specify:
1. **Schema:** new `events` and `photo_events` tables in Supabase; `event_id`, `community_id`, `date_range`, `confidence`, `evidence_signals{}`, `admin_confirmed bool`, `created_at`.
2. **Algorithm:** 5-year window + weighted fusion (shared_identity 0.5, clothing_jaccard 0.2, location_text_match 0.2, filename_proximity 0.1). Tune weights on a 20-pair labeled set before shipping. Complete-linkage within bucket.
3. **UI:** event badge on photo page; admin can "split event" or "merge events"; read-only for non-admin in v1.
4. **Integration with PRD-059 Phase 4:** Signal 2 (co-occurrence) upgrades to use `photo_events` instead of raw photo pairs — higher signal, fewer false pairs.
5. **Out of scope for v1:** CLIP scene embeddings (Tier 2), cross-community events, Gemini pairwise calls, auto-naming events ("Belle Isle 1918") — v1 uses `Event #N` only. Human renaming allowed.
6. **Validation gate:** hand-label 30 pairs (10 same, 10 same-venue-different-day, 10 different). Tier 1 must hit ≥85% precision on same-event calls before shipping.
7. **Rollback path:** feature-flag `EVENT_CLUSTERING_ENABLED`; `photo_events` is additive, no existing data touched.

### AD entries required before code (per ml-pipeline.md rule):
- **AD-236:** Same-Event Scoring — Weighted Rule-Based Fusion (Tier 1). Rationale, rejected alternatives (CLIP-only, Gemini-pairwise), per-family weight calibration.
- **AD-237:** Event Entity Persistence — Supabase as source of truth. Rationale vs. derived-on-read.
- **AD-238:** Deferred — CLIP Scene Embeddings for Same-Event. Document why deferred, reopen trigger.

---

## 8. Open question — priority vs existing backlog

**Honest take: this is NOT the highest-priority item on the board.** Stress-testing against current ROADMAP:

- **PRD-059 Phase 4** — already deployed, 18 suggestions pending. Finishing the loop (browser verify, rejected-list UX) is higher ROI because it directly uses data we already computed.
- **WORKSPACE-001/002/003** — blocks community growth. Unblocks onboarding. Higher user-facing leverage.
- **COMMUNITY-017** — routing safety; security-adjacent.
- **Mobile polish / TOOLS-005 / TOOLS-006** — Nolan has repeatedly said mobile is "almost unusable" and that blocks adoption (feedback_mobile_usability_critical).
- **Data integrity** — Lessons 153–156 are 10+ occurrences. Still the #1 recurring failure category.

**Where event clustering wins:** it is the **single largest unshipped signal** for identifying unknown faces in the Fox archive. If the next 20 hours of Nolan's triage time are going to go into identifying unknown companions of Esther/Albert (current focus of Sessions 143–148), event clustering at Tier 1 plausibly 2–3x's the per-hour identification rate — because it narrows the candidate pool from "everyone in family" to "people present at this specific event." That's a concrete, measurable win.

**Recommendation:** Don't ship next. Ship **after** PRD-059 Phase 4 is fully closed out (browser verify, rejected list UX, batch execute). Then event clustering becomes the natural next rung. In the meantime, write PRD-061 and collect the 30-pair validation set so when we ship, we're calibrated.

**Hard skepticism:** If after 2 more identification sessions Nolan still says "I keep losing same-event signal," ship Tier 1 immediately. If he stops mentioning it, defer to Q3.

---

## Sources

- [Apple — Recognizing People in Photos Through Private On-Device ML](https://machinelearning.apple.com/research/recognizing-people-photos)
- [Cooray & O'Connor — Temporal event clustering for digital photo collections (ACM TOMM)](https://dl.acm.org/doi/10.1145/1083314.1083317)
- [Suh & Bederson — SAPHARI: Semi-automatic photo annotation with event-based clustering + clothing recognition](https://www.sciencedirect.com/science/article/abs/pii/S095354380700015X)
- [Dai et al. — Family Member Identification from Photo Collections (WACV 2015)](http://dhoiem.cs.illinois.edu/publications/dai_disney_wacv2015.pdf)
- [Google Patents US8189880B2 — Interactive photo annotation based on face clustering](https://patents.google.com/patent/US8189880B2/en)
- [Life Gallery — event detection in a personal media collection](https://link.springer.com/article/10.1007/s11042-016-3576-y)
- [TMG — Scene detection on 2M digitized historical press photos](https://tmgonline.nl/articles/10.18146/tmg.815)
- [Probing Historical Image Contexts (JOCCH 2024)](https://dl.acm.org/doi/10.1145/3631129)
- [Roboflow — Embeddings + clustering with CLIP + UMAP](https://blog.roboflow.com/embeddings-clustering-computer-vision-clip-umap/)
- [Voxel51 — Visual Kinship Recognition with Families in the Wild](https://medium.com/voxel51/visual-kinship-recognition-with-the-families-in-the-wild-computer-vision-dataset-b37d8ddbcf14)

## Internal references

- `docs/prds/059_temporal_co_occurrence.md` (PRD-059, Phases 1–4)
- `docs/prds/011_life_events_context_graph.md` (PRD-011, schema ancestor, never shipped)
- `scripts/event_grouping.py` (current Phase 2 implementation)
- `rhodesli_ml/data/event_groups.json` (18 groups, Esther/Albert only)
- `core/temporal.py` (CLIP ViT-B/32 already vendored)
- `core/grouping.py` (complete-linkage pattern)
- `docs/ml/ALGORITHMIC_DECISIONS.md` — AD-005 (complete linkage), AD-048/231 (Gemini full preset), AD-235 (Family Cluster Score)
- Lesson 115 (single-linkage snowball), Lesson 172 (event context > embedding for identification)
