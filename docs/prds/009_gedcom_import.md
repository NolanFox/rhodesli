# PRD: GEDCOM Import + Relationship Graph

**Author:** Nolan Fox
**Date:** 2026-02-15
**Status:** Approved
**Session:** 35

---

## Problem Statement

The archive has 46 confirmed identities with ML-estimated birth years (3 HIGH, 6 MEDIUM, 23 LOW confidence). We lack: precise birth/death dates, marriage dates, parent-child relationships, spousal relationships, and place-of-origin data. This information exists in GEDCOM files that family members maintain.

Importing GEDCOM data:
- Replaces ML birth estimates with known dates (32 identities have only ML guesses)
- Enables family relationship graph (currently zero relationship data exists)
- Unlocks "how are two people connected" queries (foundation for Session 38)
- Provides ground truth for ML calibration
- Foundation for multi-community expansion (each community imports their tree)

## Who This Is For

| Role | Value |
|------|-------|
| Admin (Nolan) | Import his family tree to enrich identities |
| Family members | See accurate dates and relationships on person pages |
| Future communities | Upload their own GEDCOM to bootstrap their archive |
| ML pipeline | Ground truth birth years replace ML estimates |

---

## User Flows

### Flow 1: GEDCOM Upload (Admin)
1. Admin navigates to /admin/gedcom-upload
2. Sees file upload form with instructions
3. Uploads a .ged file
4. System parses the file, shows summary: "Found N individuals, M families"
5. System proposes matches: "N potential matches with archive identities"
6. Admin clicks "Review Matches" to go to /admin/gedcom-matches

### Flow 2: Match Review (Admin)
1. Admin sees list of proposed matches, sorted by confidence
2. Each row shows: GEDCOM person (name, dates, places) | Archive identity (name, ML estimate)
3. Admin clicks [Confirm Match] — GEDCOM data enriches the identity
4. Admin clicks [Not Same Person] — match dismissed
5. Admin clicks [Skip] — deferred for later
6. After all matches reviewed, summary shows enrichment stats

### Flow 3: Timeline Views Enriched Data
1. User views /timeline with a person filter
2. Person with GEDCOM birth year shows exact age: "Age 32"
3. Person with only ML estimate shows approximate: "Age ~32"
4. Person page shows GEDCOM data: birth/death dates, places, relationships

### Flow 4: Co-occurrence Graph (Automatic)
1. System builds co-occurrence graph from existing photo data
2. Any photo with 2+ identified people creates edges
3. Graph stored for future "six degrees" feature (Session 38)
4. No user action required — computed from existing data

---

## Features

### Feature 1: GEDCOM Parsing

Parse GEDCOM 5.5.1 files using `python-gedcom` library.

Extract per individual:
- Name (given + surname, normalized from `/Surname/` format)
- Birth date + place
- Death date + place
- Gender
- Marriage date(s) + place(s) (from FAM records)
- Parent-child relationships (FAMC/FAMS pointers)
- Spousal relationships

Handle messy dates:
- `ABT 1905` → year=1905, modifier="about", confidence=MEDIUM
- `BEF 1910` → year=1909, modifier="before", confidence=LOW
- `AFT 1890` → year=1891, modifier="after", confidence=LOW
- `BET 1890 AND 1900` → year=1895, modifier="between", confidence=MEDIUM
- `15 MAR 1895` → year=1895, month=3, day=15, confidence=HIGH
- `1895` → year=1895, confidence=HIGH
- `(Stillborn)` → skip (phrase, not parseable)

### Feature 2: Identity Matching

Layered matching strategy:

**Layer 1 — Exact Name Match:**
- Normalize both sides: lowercase, strip prefixes ("Big"), strip suffixes
- Use surname_variants.json for cross-variant matching (Capeluto = Capuano)
- Match: GEDCOM "Leon Capeluto" → Archive "Big Leon Capeluto"

**Layer 2 — Fuzzy Name + Date Match:**
- Levenshtein distance on normalized names
- If birth years within 10 years → boost confidence
- Threshold: combined score > 0.7

**Layer 3 — Unmatched:**
- GEDCOM individuals with no archive match stay in "gedcom-only" pool
- Available for future matching when new photos are added

All matches are PROPOSED — admin must confirm each one.

### Feature 3: Data Enrichment on Confirm

When admin confirms a match:
- `birth_year`: GEDCOM value written to identity metadata (source: "gedcom")
- `death_year`: added from GEDCOM
- `birth_place`: added from GEDCOM
- `death_place`: added from GEDCOM
- `birth_date_full`: full date if available (e.g., "15 MAR 1895")
- `death_date_full`: full date if available

ML estimates preserved in `birth_year_estimates.json` (not deleted).
Identity metadata shows GEDCOM value as primary, ML as fallback.

### Feature 4: Relationship Graph

After GEDCOM import and matching, build relationship graph.

Schema: `data/relationships.json`
```json
{
  "schema_version": 1,
  "relationships": [
    {
      "person_a": "identity_uuid_1",
      "person_b": "identity_uuid_2",
      "type": "parent_child",
      "source": "gedcom",
      "gedcom_family_id": "F001",
      "created_at": "2026-02-15T..."
    }
  ],
  "gedcom_imports": [
    {
      "filename": "capeluto_tree.ged",
      "imported_at": "2026-02-15T...",
      "individuals_count": 150,
      "families_count": 45,
      "matches_confirmed": 12
    }
  ]
}
```

Relationship types: `parent_child`, `spouse`

### Feature 5: Photo Co-occurrence Graph

Built from existing photo data (no GEDCOM required).

Schema: `data/co_occurrence_graph.json`
```json
{
  "schema_version": 1,
  "edges": [
    {
      "person_a": "identity_uuid_1",
      "person_b": "identity_uuid_2",
      "shared_photos": ["photo_id_1", "photo_id_2"],
      "count": 2
    }
  ],
  "generated_at": "2026-02-15T..."
}
```

---

## Acceptance Criteria

```
TEST 1: GEDCOM parser handles valid file
  - Parse test_capeluto.ged fixture
  - Assert: individuals extracted with names and dates

TEST 2: Messy dates parsed correctly
  - Parse "ABT 1905" → year=1905, modifier="about"
  - Parse "BEF 1910" → year=1909, modifier="before"
  - Parse "BET 1890 AND 1900" → year=1895, modifier="between"
  - Parse "15 MAR 1895" → year=1895, month=3, day=15

TEST 3: Relationships extracted
  - Parse test GEDCOM with FAM records
  - Assert: parent-child and spouse relationships returned

TEST 4: Identity matching proposes matches
  - Given GEDCOM "Leon Capeluto b.1903"
  - And archive identity "Big Leon Capeluto"
  - Assert: match proposed with score > 0

TEST 5: Confirmed match enriches identity
  - Confirm a GEDCOM-to-identity match
  - Assert: identity birth_year updated to GEDCOM value

TEST 6: ML estimates preserved after enrichment
  - After GEDCOM enrichment
  - Assert: birth_year_estimates.json unchanged

TEST 7: Relationship graph created
  - After import with confirmed matches
  - Assert: data/relationships.json has parent-child entries

TEST 8: Co-occurrence graph created
  - Build from existing photo data
  - Assert: edges exist for photos with 2+ identified people

TEST 9: Admin UI shows pending matches
  - Navigate to /admin/gedcom-matches
  - Assert: proposed matches displayed with confirm/reject buttons

TEST 10: Timeline uses GEDCOM birth year when available
  - Person with GEDCOM birth year
  - Assert: shows exact age (no ~ prefix)
```

---

## Data Model Changes

### Identity metadata — new allowlisted keys
- `birth_date_full` (string): Full GEDCOM date (e.g., "15 MAR 1895")
- `death_date_full` (string): Full GEDCOM date
- `gender` (string): "M", "F", or "U"

### New data files
- `data/relationships.json`: Family relationship graph
- `data/co_occurrence_graph.json`: Photo co-occurrence graph
- `data/gedcom_matches.json`: Pending/confirmed/rejected GEDCOM matches

---

## Technical Constraints

- Library: `python-gedcom` v1.1.0 (GPL v2, acceptable for this project)
- Custom date parser needed (library returns raw date strings)
- Large GEDCOM files (10,000+ individuals) — only match against archive identities
- GEDCOM names use `/Surname/` format — normalization required
- surname_variants.json already handles Sephardic transliterations
- Privacy: living individuals (no death date, born after ~1930) — no special filtering needed for this family archive

## Out of Scope

- Multi-user GEDCOM uploads (admin-only for now)
- GEDCOM export (generating .ged from archive data)
- Automatic re-matching when new photos are added
- GEDCOM merge (combining multiple GEDCOM files)
- Six degrees UI (Session 38 — but data layer built now)
- Kinship recalibration with GEDCOM relationships (Session 39)
- Geocoding places (Session 37)
- Database migration

## Priority Order

1. GEDCOM parser + date handling (foundation for everything)
2. Co-occurrence graph (free data, no GEDCOM needed)
3. Identity matcher (the hard part)
4. Data enrichment + relationship graph
5. Admin UI (upload + match review)
6. Timeline integration (display enriched data)
