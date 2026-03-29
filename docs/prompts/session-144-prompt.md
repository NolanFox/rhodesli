# Session 144: GEDCOM Re-Import + Context Enrichment + Geographic Data + Batch Completion

## Context
Session 143 completed 275/279 Fox photo batch but revealed GEDCOM context gaps and geographic data limitations.
See `docs/session_context/session-144-context.md` for full predecessor context.
AD-233 (anchor refinement), AD-234 (GEDCOM enrichment).

## Approach: PRD/SDD where applicable
- Phase 0 (GEDCOM import): Infrastructure — no PRD needed
- Phase 1 (context enrichment): PRD-059 extension — update existing PRD with spouse timeline spec
- Phase 2 (geographic data model): Needs brief design doc — new data model for multi-candidate locations
- Phase 3 (batch re-run): Operational — no PRD needed
- Phase 4 (anchor prototype): PRD-059 Phase 4 — extend PRD with anchor spec

## Phase 0: Orient + GEDCOM Re-Import (SEQUENTIAL — must complete first)

### 0a: Orient
```bash
echo "144" > .claude/current_session.txt
source venv/bin/activate && make test-fast
```
- Read past GEDCOM import lessons in `tasks/lessons.md`
- Read previous import code and any issues documented in AD entries
- Snapshot existing GEDCOM data counts BEFORE import

### 0b: Import GEDCOM
- Source: `~/Downloads/gedcom_20260328/`
- **CRITICAL**: Preserve existing GEDCOM face links (76 links mapping identities to GEDCOM records)
- Verify before: count individuals, families, face links
- Run import
- Verify after: counts should increase or stay same, face links preserved
- **Codex audit**: After import, have Codex verify data integrity

### 0c: Link Albert's Wives
- Find Rose Weiss in GEDCOM → rename identity to "Rose Weiss Baygel Fox"
- Find Jean Baumann in GEDCOM → rename identity to "Jean Baumann Kassel Fox"
- Create GEDCOM face links for both
- Verify Albert now has 3 spouse families in GEDCOM

### 0d: Verification Gate
- Albert has 3 spouses linked with marriage dates
- Esther's death date (Jun 11, 1966) is in the data
- Rose and Jean have correct names
- All 76+ existing face links preserved
- **Codex audit**: Verify all links

## Phase 1: GEDCOM Context Enrichment (AD-234)

### 1a: Spouse Timeline Block (P0)
- File: `rhodesli_ml/gedcom_context.py`
- For each identified person, emit chronological spouse timeline:
  ```
  SPOUSE TIMELINE for Albert Fox:
  1. Esther Burd — married May 6, 1920 (Hamilton, OH) — died Jun 11, 1966 (Dayton, OH)
     PHOTOS WITH ESTHER: must be 1920-1966
  2. Rose Weiss Baygel — married [date] — died [date]
     PHOTOS WITH ROSE: must be after Jun 1966
  3. Jean Baumann Kassel — married [date] — died [date]
     PHOTOS WITH JEAN: must be after Rose's death
  ```
- Tests: verify timeline output for Albert with all 3 spouses
- **Codex audit**: Review the context builder changes

### 1b: Birth Date Resolution (P1)
- File: `rhodesli_ml/importers/gedcom_parser.py`
- Handle primary vs alternate birth dates
- In context: "Born: Jan 15, 1892 [primary, 17 sources]; alternate: abt 1896 [1 source]"
- Instruct Gemini: "Use primary birth date for age calculations"

### 1c: Structured Relationship Blocks (P1)
- Wire `verified_facts` parameter in batch and interactive callers
- Output CONFIRMED IDENTITIES and KNOWN RELATIONSHIPS as structured blocks
- Tests for structured output format

### 1d: Verification + Codex Audit
- Run context builder for Albert photo → verify spouse timeline present
- Run context builder for Esther photo → verify death date present
- **Codex audit**: Full review of Phase 1 code changes

## Phase 2: Geographic Data Model Expansion

### Design: Multi-Candidate Location Storage
Current: `location_estimate` is a single string. Gemini often considers multiple locations.
Need: Primary location (for map pin) + candidates (for manual review).

**Proposed schema for `date_labels.data` JSONB:**
```json
{
  "location_primary": {
    "place": "Hamilton, Ohio, USA",
    "confidence": "high",
    "source": "biographical",
    "lat": 39.3995,
    "lng": -84.5613
  },
  "location_candidates": [
    {"place": "Dayton, Ohio, USA", "confidence": "medium", "source": "biographical", "reasoning": "Albert and Esther lived in Dayton after marriage"},
    {"place": "Detroit, Michigan, USA", "confidence": "low", "source": "visual", "reasoning": "Similar backdrop to confirmed Detroit photos"}
  ],
  "location_source_type": "biographical|visual|both",
  "location_estimate": "Hamilton, Ohio, USA"
}
```

**Key principles:**
- `location_primary` is the best guess — shown on map, used for filtering
- `location_candidates` preserves ALL alternatives for manual review
- `location_source_type` distinguishes visual evidence vs GEDCOM inference vs both
- `location_estimate` stays as backward-compatible string
- Geocoding (lat/lng) applied to primary; candidates geocoded lazily
- UI: show primary on map + "Other possible locations" expandable section

**For the oval portrait example (with spouse timeline):**
- Previous: "New York, New York or Detroit, Michigan" (ambiguous string)
- After enrichment: Primary = "Hamilton, Ohio" or "Dayton, Ohio" (where Albert and Esther lived when married ~1920). Candidates = [Detroit, New York]

### Implementation:
1. Update Gemini prompt to request structured location with primary + candidates + source type
2. Update batch script to parse and store new format
3. Update photo page template: primary on map + expandable candidates
4. Update map view to use `location_primary.lat/lng` for pins
5. Backward compatible: existing labels with string `location_estimate` still render
6. Tests for new format parsing + backward compat
7. **Codex audit**: Review schema design and backward compatibility

## Phase 3: Batch Re-Run (SEQUENTIAL — after Phase 1+2)

**Order of operations** (maximize coverage, highest value first):
1. **Never-run photos first** — photos with Esther/Albert that have zero date_labels (get them SOME data)
2. **4 timeout retries** — from Session 143 batch (see if they succeed this time)
3. **83 Session 142 photos** — upgrade to full enrichment with spouse timeline + evidence + reasoning + structured geo

For each sub-batch:
- Verify first result quality before continuing (Lesson 161)
- Check: GEDCOM context with spouse timeline present? Evidence? Reasoning? Structured location?
- All results write to Supabase immediately
- **Codex audit**: Review batch output quality after each sub-batch completes

## Phase 4: Anchor Photo Refinement Prototype (AD-233)

### Data Expansion for Anchor Support
**New fields in `date_labels.data`:**
```json
{
  "anchor_comparisons": [
    {
      "anchor_photo_id": "inbox_fox-charlie-001_204_02068...",
      "anchor_date": "1918",
      "anchor_confidence": "high",
      "comparison_result": "subject_older_in_current",
      "estimated_gap_years": 2,
      "refined_date": "1919-1920",
      "comparison_evidence": "Jawline more defined, facial fullness...",
      "model": "gemini-3.1-pro-preview",
      "compared_at": "2026-03-28T..."
    }
  ],
  "date_refinement_history": [
    {"pass": 1, "estimate": 1919, "confidence": "high", "method": "single_image"},
    {"pass": 2, "estimate": 1920, "confidence": "high", "method": "anchor_comparison", "anchor": "02068..."}
  ]
}
```

**Preservation guarantees:**
- Original single-image estimate NEVER overwritten — stored in refinement_history pass 1
- Anchor comparisons are additive (append to array)
- Each comparison stores full provenance (model, timestamp, evidence)
- All prompt text and full response stored in gemini_api_calls

### Implementation (if time permits):
1. Multi-image Gemini call in `rhodesli_ml/multi_pass.py`
2. Admin UI: "Compare with anchor" button on photo page
3. Test with Albert Fox oval portrait (anchor = Detroit group)
4. Compare API result to Gemini Chat Session 143 result

## Codex Audit Strategy (MANDATORY — built into every phase)

| After Phase | Codex Scope | Block on P0/P1? |
|-------------|------------|-----------------|
| Phase 0d | GEDCOM import integrity, face link preservation | Yes |
| Phase 1d | Context builder code, spouse timeline correctness | Yes |
| Phase 2 | Schema design, backward compat, migration safety | Yes |
| Phase 3 (each sub-batch) | Output quality spot-check, Supabase verification | Yes for first |
| Phase 4 | Multi-image call safety, data preservation | Yes |
| Prompt audit | Codex reviews THIS prompt before execution | Yes — first action |
| Final | Full session audit — security, tests, data integrity | Yes |

## Parallelization Plan
| Track | Phase | Dependencies |
|-------|-------|-------------|
| Sequential | Phase 0 (GEDCOM import) | Must complete first |
| Sequential | Phase 1 (context enrichment) | Depends on Phase 0 |
| Parallel | Phase 2 design doc | Can draft while Phase 1 implements |
| Sequential | Phase 3 (batch re-run) | Depends on Phase 1+2 |
| Parallel | Phase 4 (anchor prototype) | Can start after Phase 1 |

## Key Constraints
- **GEDCOM import is destructive** — snapshot before, verify after
- **DO NOT re-run batch before GEDCOM enrichment** — waste of API calls
- **DO NOT lose existing face-to-GEDCOM links** during import
- **Gemini 3.1 Pro**: 250 RPD on Tier 1. 87 photos fits in one day.
- **Geographic data**: Primary location MUST be set for map display; candidates preserved
- **All data additive** — never overwrite, always append/enrich
- **Prompt + response preservation**: All Gemini calls logged to gemini_api_calls with full text
- Follow batch-data-pipeline.md for all outputs
- Browser verify after every phase
- Codex audit after every phase — block on P0/P1 findings
