# Session 149 Context — Gemini Event Analyzer + Investigation Schema

## Predecessor
- Session 148c: Interactive Fader identification. Methodology learnings documented.
  - Context: `docs/session_context/session-148c-context.md`
  - Learnings: `docs/session_context/session-148c-learnings.md`
  - Investigation JSON: `docs/session_context/session-148c-investigation.json`
  - API schema proposal: `docs/session_context/session-148c-api-schema-proposal.md`

## What Prompted This Session
Session 148c identified Abraham Al Fader and Nellie Kubrin in the Fader collection through manual photo analysis. The strongest identification signal was **event context** (corsages, aisle walks, dance partners, head table seating), not embedding similarity. The session produced a structured investigation JSON and proposed a Supabase schema for storing investigations. This session implements both:
1. A Gemini-powered event context analyzer to automate the strongest signal
2. The `identification_investigations` Supabase table to store investigation data

## Feature 1: Gemini Event Context Analyzer (FEATURE-F1)

### What It Does
Given a photo (with optional known people and face bounding boxes), ask Gemini to analyze:
- **Event type**: wedding ceremony, wedding reception, party, funeral, casual gathering, portrait, street/outdoor, etc.
- **Role indicators**: corsage (mother of couple), boutonniere (father), veil (bride), yarmulke (Jewish ceremony), party hats, formal/informal dress
- **Estimated era**: decade from clothing, hairstyles, photo technology (B&W, Polaroid, color)
- **Estimated ages**: per-face age estimates (requires face bbox coordinates in prompt)
- **Relationship signals**: who stands next to whom, body language, couple posture, parent-child positioning

### How It Fits Existing Architecture
- **Gemini integration exists**: `rhodesli_ml/gemini_estimate.py` handles Gemini API calls for date/location estimation. Same pattern extends to event context.
- **Prompt manifests exist**: `rhodesli_ml/prompt_manifest.py` defines versioned prompt templates. Add a new `EVENT_CONTEXT` template.
- **Face bbox available**: InsightFace detection provides bounding boxes. These can be included in the Gemini prompt so it knows where faces are.
- **API call logging exists**: `gemini_api_calls` table logs every call with prompt, response, model, cost.
- **AD-139**: Gemini 2.5 Pro already wired to Estimate tool. Same model for event context.

### Key Design Decisions Needed
1. **Batch vs on-demand**: Run on all photos at upload time? Or on-demand when investigating?
2. **Output schema**: What structured fields does the Gemini response need? Should mirror the `date_labels` pattern (JSONB stored per-photo).
3. **Cost control**: Each vision call ~$0.01-0.05. Batch on 147 Fader photos = ~$2-7.
4. **Integration with identification workflow**: How does event context feed into the investigation UI?

### Existing Gemini Patterns to Follow
- `rhodesli_ml/gemini_estimate.py`: `estimate_photo_date_location()` — sends photo + prompt, parses structured response
- `rhodesli_ml/prompt_manifest.py`: versioned prompts with `PROMPT_VERSION` tracking
- `app/estimate_routes.py`: UI integration, API call logging to `gemini_api_calls`
- `scripts/batch_gemini_for_person.py`: batch execution pattern

### CRITICAL Research Finding: Most of This Already Exists
Session 148c research revealed that `rhodesli_ml/gemini_extraction.py` already provides:

| Capability | Status | Location |
|-----------|--------|----------|
| Date estimation | EXISTS | `date_estimation` field |
| Face ages | EXISTS | `face_analysis[].estimated_age` + `subject_ages` |
| Clothing/era | EXISTS | `clothing_era` field |
| Group composition type | PARTIAL | `group_composition.type` (limited taxonomy: formal_portrait/candid/ceremony/group_photo) |
| Face coordinates in prompt | EXISTS | `build_extraction_prompt()` accepts `face_coordinates` |
| GEDCOM context | EXISTS | Already wired for biographical cross-referencing |
| Role indicators (corsage, veil) | NOT EXTRACTED | `clothing_notes` is free-text, not structured |
| Relationship inference | NOT EXTRACTED | `group_composition.arrangement` is brief string |

**Approach:** Extend the existing single-call architecture with two new extraction sections (`event_context` + `relationship_inference`), NOT build a new system. This adds ~$0.005/photo to the existing ~$0.037/photo cost.

**Model:** `gemini-3.1-pro-preview` (current default). Flash at ~$0.01/photo for quick mode.

## Feature 2: Identification Investigations Table (DATA-FMT-001)

### Schema Proposal
Full proposal at `docs/session_context/session-148c-api-schema-proposal.md`. Key columns:

```sql
CREATE TABLE identification_investigations (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    session_id text NOT NULL,
    target_name text NOT NULL,
    target_birth_year integer,
    target_death_year integer,
    target_relationship text,        -- e.g. "Mother of Sherry Ann Fader"
    target_gedcom_id text,
    known_references jsonb,          -- known people with identity_ids + centroids
    methodology jsonb,               -- ordered steps taken
    candidates jsonb NOT NULL,       -- per-candidate: face_ids, distances, confidence, decision
    clusters jsonb,                  -- embedding clusters found
    signals_used jsonb,              -- which signals and their assessed strength
    outcome text,                    -- CONFIRMED / CANDIDATE / NOT_FOUND
    confirmed_identity_id text,      -- links to identities table
    also_identified jsonb,           -- bonus finds
    community_id uuid,
    collection_name text,
    notes text,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);
```

### Research Findings on Schema
- Single-table JSONB design is correct for O(100) rows with complex nested data
- `confirmed_identity_id` should be `text` not `uuid` to match `identities` table
- Write pattern should follow `log_gemini_api_call()`: dict construction, try/except, logger warning
- Read pattern should follow `get_gemini_call_summary()`: guard, select, return dict
- No TTL cache needed (write-once, admin-only queries)
- Links to `gemini_api_calls` via optional `investigation_id` FK (added to gemini_api_calls later)

### Migration Steps
1. Run CREATE TABLE in Supabase SQL editor
2. Backfill Session 148c data from `session-148c-investigation.json`
3. Add `log_identification_investigation()` + `get_investigations()` to `app/supabase_data.py`
4. Wire into future investigation sessions

## Cross-Feature Integration
The two features connect: when the Gemini Event Analyzer runs on a photo, its output (event type, role indicators, age estimates) becomes input for the identification investigation workflow. The investigation table stores which Gemini calls were used and what they revealed.

## What's Out of Scope
- Investigation Workflow UI (FEATURE-F4) — separate session
- Cross-Photo Person Tracker (FEATURE-F3) — separate session
- Genealogical Cross-Reference (FEATURE-F5) — separate session
- Name Collision Detector (FEATURE-F6) — separate session
- Batch execution on entire Fader collection — deferred until event analyzer is validated

## Key Files
- `rhodesli_ml/gemini_estimate.py` — existing Gemini integration
- `rhodesli_ml/prompt_manifest.py` — prompt templates
- `app/supabase_data.py` — Supabase read/write helpers
- `app/estimate_routes.py` — existing Gemini UI routes
- `docs/session_context/session-148c-investigation.json` — data to backfill
- `docs/session_context/session-148c-api-schema-proposal.md` — full schema proposal
- `docs/session_context/session-148c-learnings.md` — methodology learnings
