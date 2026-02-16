# GEDCOM Import Guide

How to import genealogical data from GEDCOM files into the Rhodesli archive.

## Prerequisites

- Python virtual environment activated (`source venv/bin/activate`)
- `python-gedcom` installed (`pip install python-gedcom`)
- Current data synced from production (`python scripts/sync_from_production.py`)

## Quick Start

```bash
# Preview matches (dry run — no changes)
python scripts/import_gedcom.py path/to/family.ged

# Execute import (writes gedcom_matches.json + co_occurrence_graph.json)
python scripts/import_gedcom.py path/to/family.ged --execute

# Also build co-occurrence graph (optional, from existing photo data)
python scripts/import_gedcom.py path/to/family.ged --execute --build-cooccurrence
```

## What the Import Does

1. **Parses** the GEDCOM file — extracts individuals (names, birth/death dates, places, gender) and families (parent-child, spouse relationships)
2. **Matches** GEDCOM individuals to existing archive identities using layered strategy:
   - Layer 1: Exact name + surname variant matching (uses `data/surname_variants.json`)
   - Layer 1b: Maiden name matching (e.g., GEDCOM "Victoria Cukran" → archive "Victoria Cukran Capeluto")
   - Layer 2: Fuzzy name matching (Levenshtein ≤ 2) + birth year proximity bonus
3. **Saves** match proposals to `data/gedcom_matches.json` (all proposals start as "pending")
4. **Builds** relationship graph from GEDCOM families cross-referenced with confirmed matches
5. **Optionally builds** co-occurrence graph from existing photo data

## Admin Review Workflow

After import, go to `/admin/gedcom` in the web UI to:

1. **Review** each match proposal (GEDCOM individual ↔ archive identity)
2. **Confirm** correct matches — writes birth/death years, places, gender to identity metadata
3. **Reject** incorrect matches — removes from proposal list
4. **Skip** uncertain matches — keeps for later review

## Output Files

| File | Description |
|------|-------------|
| `data/gedcom_matches.json` | Match proposals with scores and status |
| `data/relationship_graph.json` | Family relationships (parent-child, spouse) |
| `data/co_occurrence_graph.json` | Photo co-appearance edges |

## GEDCOM Date Handling

The parser handles all standard GEDCOM 5.5.1 date formats:

| Format | Example | Confidence |
|--------|---------|------------|
| Exact | `12 MAR 1903` | HIGH |
| Year only | `1903` | HIGH |
| Approximate | `ABT 1903` | MEDIUM |
| Before/After | `BEF 1950` / `AFT 1900` | MEDIUM |
| Range | `BET 1900 AND 1910` | LOW |
| Interpreted | `INT 1903 (about 1903)` | MEDIUM |
| From/To | `FROM 1900 TO 1910` | LOW |

## Matching Strategy (AD-074)

The matcher uses `data/surname_variants.json` (13 Sephardic transliteration groups) to expand surname matching. Key innovation: **maiden name matching** — if GEDCOM has "Victoria Cukran" and the archive has "Victoria Cukran Capeluto", the matcher recognizes "Cukran" as a maiden name component.

Match scores range from 0.0 to 1.0:
- **1.0**: Exact name match + close birth year (≤5 years)
- **0.92–0.97**: Surname variant match + maiden name match
- **0.87**: Surname variant match + given name match, larger birth year gap
- **< 0.80**: Fuzzy matches (Levenshtein distance), lower confidence

## Enrichment Fields

When a match is confirmed, these fields are written to identity metadata:

| Field | Source | Example |
|-------|--------|---------|
| `birth_year` | GEDCOM birth date | `1903` |
| `death_year` | GEDCOM death date | `1982` |
| `birth_place` | GEDCOM birth place | `"Rhodes, Ottoman Empire"` |
| `death_place` | GEDCOM death place | `"Miami, FL"` |
| `gender` | GEDCOM sex | `"M"` or `"F"` |
| `birth_date_full` | GEDCOM raw date | `"12 MAR 1903"` |
| `death_date_full` | GEDCOM raw date | `"15 JUN 1982"` |

## Person Page Integration

After importing and confirming matches, the person page (`/person/{id}`) shows a **Family** section with Parents, Children, Spouse, and Siblings — all derived from the relationship graph and cross-linked to other person pages.

## Decision Provenance

- **AD-073**: GEDCOM parsing — custom date parser over library defaults
- **AD-074**: Identity matching — layered name + date strategy
- **AD-075**: Graph schemas — dual graph architecture
- **AD-076**: GEDCOM enrichment — source priority for identity metadata
