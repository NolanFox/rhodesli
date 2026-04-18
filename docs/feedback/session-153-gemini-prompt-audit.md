# Session 153 — Gemini Prompt Audit (Detroit/Belle Isle Misidentification)

**Date:** 2026-04-18
**Photo:** `inbox_fox-charlie-001_204_02068_p_13akf5twbc3600`
**File:** `raw_photos/02068_p_13akf5twbc3600.jpg`
**Subject:** Three Fox siblings (Albert bottom-right) in front of distinctive arched-window conservatory.
**Ground truth:** Anna Scripps Whitcomb Conservatory (Belle Isle, Detroit, MI), c. 1916-1918.
**Production output:** "New York, New York" (medium confidence)
**Reference transcript:** `docs/feedback/session-144-gemini-detroit-transcript.md`

---

## Phase 1 — Audit of the prior auto-run prompt

The most recent successful production call:

| Field | Value |
|---|---|
| `created_at` | 2026-03-29T17:00:57Z |
| `model_used` | gemini-3.1-pro-preview |
| `call_type` | batch_full_extraction |
| `request_surface` | scripts.batch_gemini_for_person |
| `preset` | full |
| `prompt_variant` | full_gedcom+faces |
| `prompt_tokens` | 8,271 |
| `completion_tokens` | 1,932 |
| `cost_usd` | $0.040 |
| `latency_ms` | 19,950 |
| `status` | success |

Total of 3 calls in `gemini_api_calls` for this photo (2026-03-27 error, 2026-03-28 success same NY result, 2026-03-29 success NY result). All used the same prompt template.

### What was sent
- **Image:** target photo only (`02068_p_13akf5twbc3600.jpg`). NO reference portrait.
- **Prompt length:** 33,085 chars across 12 extraction sections.
- **GEDCOM context (22,588 chars):** Full residence timelines for Albert + Meyer + Rebecca + siblings (Israel, Jack, Bessie, Harry, Sara, Tina). Includes the critical line `1917: Detroit, Michigan, USA` and `1917-1918: Detroit, Wayne, Michigan, USA` for Albert; also Israel had `1917: Detroit, Michigan, USA`.
- **Face coordinates:** 6 InsightFace bboxes provided.
- **Location section instructions:** rich prose covering visual analysis, biographical cross-reference, business-name match, immigration-vs-residence disambiguation, and "list 3 candidates" — but no scaffold for ranked architectural elimination.
- **Output schema:** generic JSON object with `location.candidates[]` allowed.

### What Gemini returned
Primary: `New York, New York` (medium). Visual evidence: "*strongly resembles the Enid A. Haupt Conservatory at the New York Botanical Garden in the Bronx*" — wrong building. Detroit was correctly listed as candidate #2 but downgraded to **low** confidence with reasoning that mis-weighted family presence ("strong family presence in NY during the estimated late 1910s timeframe") even though Albert himself was in Detroit during that exact window per the same GEDCOM timeline.

The same `location` block also appears nested inside `date_estimation` — a schema bug where the model duplicated the field. The persisted `location_estimate` in `date_labels` for this photo is `"New York, New York"`.

---

## Phase 2 — Gap table vs the user's successful Gemini chat

| Feature in user's successful prompt | Present in our auto-run? | Impact |
|---|---|---|
| Biographical timeline ("1917 Detroit at 74 Delmar St", military service in France, Cincinnati marriage, Dayton thereafter) | PARTIAL — GEDCOM data sent but as raw residence dump, not a narrative; no explicit "was in Detroit during this window" hypothesis | HIGH — model picked NY because "family in NY" outweighed Albert's own Detroit residence |
| Reference portrait at known later date for age calibration | NO | HIGH — model anchored on candid-photo conservatory shape, not on Albert's age |
| Explicit ask for 2-3 candidate buildings with elimination reasoning | PARTIAL — schema allowed `candidates[]` but prompt did not force comparison | HIGH — Gemini listed candidates but didn't pit them against each other |
| Diagnostic architectural feature ask (fanlight, junction, palm fronds) | NO | HIGH — without forced diagnostic features, model picks first matching shape |
| Specific ask "describe building first, then identify" (ROUND 1) | NO | MEDIUM — Gemini described architecture incidentally, not as a first step |
| Multi-round dialog or flattened scaffold | NO — single shotgun prompt with 12 sections | HIGH — the user's win came from staged rounds that Gemini itself acknowledged narrowed the answer |
| Architect / opening year cross-check | NO | LOW — secondary confirmation |
| Citing archival photo source | NO | LOW — production setting doesn't need this |
| Geographic priority hint ("Albert was Midwest-based 1917-1923 except military") | NO — GEDCOM includes both Brooklyn (parents) and Detroit (Albert) without weighting | HIGH — model defaulted to the parent residence (NY) instead of the subject residence (Detroit) |

The structural gap: **our prompt sends data to Gemini and asks "what's the location?". The user's prompt sends data and says "compare 2-3 candidates and eliminate".**

---

## Phase 3 — Replication attempts

All 3 attempts logged to `gemini_api_calls` with `experiment_id=session153_1776550350`, `request_surface=scripts.session153_experiments`, `call_type=experiment_location_identification`, and `attempt_label` differentiating each.

### Attempt 1 — biographical timeline only (no reference portrait, no scaffold)
- Sent: target image + narrative biographical timeline (Albert in Detroit Jun 1917, France 1918-Apr 1919, Cincinnati May 1920, Dayton 1923+)
- Asked: identify location, list 3 candidates with confidence
- **Result: Brooklyn, New York — Brooklyn Botanic Garden Laboratory Building (high confidence)**
- Detroit listed as candidate #3 (low) — refuted on architectural grounds
- Gemini hallucinated "WWI honorable discharge lapel buttons" to justify post-war Brooklyn 1919 dating
- VERDICT: WORSE than production — even more confidently wrong

### Attempt 2 — biographical timeline + reference portrait
- Sent: target + Albert reference (`01559_p_13akf5twbc5217_r.jpg`) + narrative timeline
- Asked: identify location, 3 candidates with diagnostic features
- **Result: Detroit, MI — Belle Isle Aquarium and Conservatory (high confidence)**
- Diagnostic features: light masonry + arched windows + attached glass conservatory + palm fronds
- NY downgraded to low ("primarily an all-glass structure, lacks the masonry building")
- Cost: ~$0.04
- VERDICT: CORRECT

### Attempt 3 — full three-round scaffold from transcript
- Sent: target + reference + narrative timeline + the candidate hint list (Belle Isle, Dayton Soldiers' Home, NYBG)
- Asked: ROUND 1 describe architecture, ROUND 2 propose 2-3 candidates with supports/refutes, ROUND 3 pick + eliminate runner-up + biographical alignment
- **Result: Anna Scripps Whitcomb Conservatory, Detroit, Michigan (high confidence)**
- Round 1 named the diagnostic junction (limestone pavilion + glass wing + curved eaves + palm fronds inside)
- Round 2 directly compared Belle Isle, NYBG (Haupt), and Dayton Soldiers' Home
- Round 3 eliminated NYBG specifically: "*lacks the heavy, solid limestone walls and deep classical arches visible on the left side of the photo*"
- Best year: 1917 (range 1916-1918)
- Cost: ~$0.05
- VERDICT: CORRECT and explainable — matches the user's transcript almost word-for-word

| Attempt | Location returned | Correct? | Confidence | Notes |
|---|---|---|---|---|
| Production (3/29) | New York, NY | NO | medium | Listed Detroit as low candidate |
| Attempt 1 | Brooklyn, NY | NO | high | Got worse with timeline alone |
| Attempt 2 | Detroit, MI (Belle Isle) | YES | high | Reference portrait + narrative timeline = win |
| Attempt 3 | Detroit, MI (Belle Isle) | YES | high | Three-round scaffold = clean reasoning trail |

---

## Recommended permanent change to batch Gemini prompt

Adopt the **Attempt 3 (three-round scaffold)** for the `location` extraction section of the `full` and `identification` presets in `rhodesli_ml/gemini_extraction.py`. Concretely:

1. **Reorder location section** to require sequential rounds: (a) describe architecture, (b) propose 2-3 candidates with supports/refutes, (c) pick + eliminate runner-up.
2. **Require diagnostic features** — at least 2 named architectural details that distinguish the chosen building from the runner-up.
3. **Add a "subject-weighted geography" hint** when GEDCOM context exists: when assigning candidates, weight each subject's own residence at the photo date over their parents' or other relatives' residences.
4. **Pass a reference portrait** in `_call_gemini_*` paths whenever a confidently-dated same-subject photo exists for the primary identified person. (Build a helper `get_reference_portrait(identity_id, target_date_range)` that returns the closest-dated CONFIRMED face crop.)
5. **Keep candidates schema mandatory** (already present) but enforce minimum 2 candidates with `feature_supporting` AND `feature_refuting` fields.

Estimated cost delta per photo: $0.04 → ~$0.05 (extra reasoning tokens), ~25% increase. Worth it given the 0% → 100% accuracy lift on this case.

Logging open question: the current `_RESPONSE_SCHEMA_FRAGMENTS["location"]` at gemini_extraction.py L506-518 omits `candidates` from the enforced schema even though the prose schema asks for it. Tighten both prose AND response_schema.

Backlog candidate (non-blocking): after wiring (1)-(5), re-run all 246 dated batch photos with location confidence < high to see how many get upgraded. Gate via `--shadow` mode that writes to `gemini_api_calls` only, then a second pass after admin review writes to `date_labels`.

---

## Data integrity confirmation

- `date_labels` for this photo: **NOT modified**. Last `updated_at` is 2026-03-28T14:05:08Z (the original batch run). `location_estimate` still reads `"New York, New York"` and is preserved verbatim.
- `gemini_api_calls`: 3 new rows added (attempt1/2/3) all tagged `experiment=true`, `request_surface=scripts.session153_experiments`, `experiment_id=session153_1776550350`.
- No production data tables (photos, identities, photo_faces) touched.
- `experiment_id` and `attempt_label` make all 3 rows easy to find/delete if desired:
  `DELETE FROM gemini_api_calls WHERE gemini_config->>'experiment_id' = 'session153_1776550350'`.
