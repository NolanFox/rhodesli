# Session 152 Context — Fox Family Temporal Identification

**Predecessor:** [Session 151](../assessments/session-151-assessment.md)
**Date:** 2026-04-14
**Mode:** Interactive identification

## What Prompted This Session

User wants to focus on Fox family identification using temporal co-occurrence analysis, specifically targeting the ~1900-1935 era photos where Esther and Albert appear with unidentified family members. The Fader collection batch is on hold pending new photos from another family branch.

## The Fox Family (1894 Minsk Revision List)

Meyer Fuks (father) had 8 children:
1. **Basya-Minya (Bessie)** — CONFIRMED, 2 anchors
2. **Sora-Dvoura (Sarah)** — NOT IN SYSTEM (likely deceased before photo era, or no known photos)
3. **Geshel-Lazar (Harry)** — CONFIRMED, 7 anchors. Lived in **Dayton, Ohio**.
4. **Shima (Sadie)** — CONFIRMED, 4 anchors. Married **Jacob Edward Levine**.
5. **Ronya (Rachel)** — CONFIRMED, 3 anchors. Married **Aaron Newman**.
6. **El'ya (Albert)** — CONFIRMED, 197 anchors. Lived in **New York → Florida**.
7. **Yisra'el (Irving)** — CONFIRMED, 8 anchors. Married **Rebecca Reva Heft**. Lived in **Detroit, Michigan**.
8. **Yakov (Jacob)** — NOT IN SYSTEM (limited photos?)

Spouses (NOT siblings): Rose Scheckzner = Harry's wife. Aaron Newman = Rachel's husband. Harry Onifater = Sarah's husband. Jacob Levine = Sadie's husband.

## Key Anchor Photos

### The 1928 Family Gathering (THE ROSETTA STONE)
- **Photo ID:** `inbox_55868a49_6_69835310_4811...`
- **63 faces** — the largest Fox family photo
- **Confirmed:** Meyer Fox (2), Albert Fox (2), Irving Fox (2), Sadie Fox Levine (2), Rachel Fox Newman, Bessie Fox, Jack Fox (2), Rebecca Reva Heft Fox (Irving's wife), Jacob Edward Levine (Sadie's husband), Leonard Larry Fox, Molly Saperstein
- **~40 unidentified faces** — likely includes spouses, children, and extended family
- **6 of 8 Minsk siblings present** (missing only Harry and Sarah)
- **Year estimate:** 1928

### The 1918 Three-Sibling Photo
- **Photo ID:** `inbox_fox-charlie-001_204_02068...`
- **6 faces:** Albert, Harry, Irving + 3 unknowns (Persons 3007, 3009, 3010)
- **Significance:** Three brothers together, ~1918, likely in Dayton or New York

### Person 3051 — Top Recurring Companion
- **5 photos** spanning 1919-1927 alongside both Albert AND Esther
- **State:** INBOX, not yet identified
- **Hypothesis:** Likely a sibling (Bessie? Sadie? Rachel?) or Burd family member
- **Photos:** fox-charlie-001_219, _607, _220, _201, _609

## Available Tools and Infrastructure

### Ready to Use
- **Event grouping script:** `python scripts/event_grouping.py` — groups photos by temporal proximity + shared faces
- **Gemini event context:** `POST /api/admin/analyze-event-context/{photo_id}` — extracts event type, roles, relationships
- **Identity suggestion UI:** Panel on person page with 6 signal bars, accept/reject/needs-more
- **Batch scoring:** `python scripts/compute_identity_suggestions.py --family fox` (5/6 signals working)
- **Face comparison:** Admin compare endpoint, embedding distances via neighbors API

### Blocking Items
- **co_occurrence_pairs table NOT created** — Phase 4 can't compute co-occurrence signal without it
- Need to create table + populate from event_groups.json

## Identification Methodology (Lesson 172)

**Signal hierarchy (strongest to weakest):**
1. **Event context** — corsage, aisle walk, head table position → role identification
2. **Temporal + geographic context** — Dayton = Harry's family, Detroit = Irving's, NY = Albert's
3. **Co-occurrence patterns** — recurring companions across multiple photos = family
4. **GEDCOM age matching** — known birth years from 1894 Minsk list vs estimated ages in photos
5. **Human testimony** — David Fox identified Albert; family members can confirm others
6. **Embedding distance** — WEAK for siblings (Albert/Harry indistinguishable), useful for same-person-across-photos

## 33 Early Photos with Fox Siblings + Unidentified Faces

Full inventory from data analysis:
- 1915-1918: 8 photos (mostly Esther alone + unknowns, plus the 3-sibling photo)
- 1918-1920: 12 photos (Esther + unknowns in large group settings)
- 1920-1927: 10 photos (Esther + unknowns, Person 3051 appears 5 times)
- 1928: The family gathering (63 faces)
- 1930-1931: 3 photos (Charles, Leona, Esther + unknowns)

## Approach

### Phase 1: Orient on the 1928 Family Gathering
- View the photo in Chrome browser (READ-ONLY)
- Map which faces are confirmed vs unknown
- Use face positions + Gemini event context to infer roles (who sits together = couples?)

### Phase 2: Cross-Reference Person 3051
- View Person 3051's 5 photos
- Check embedding distance to confirmed Fox siblings
- Check if 3051 appears in the 1928 group photo
- Formulate hypothesis (which sibling or family member?)

### Phase 3: The 1918 Three-Sibling Photo
- View the photo with Albert, Harry, Irving + 3 unknowns
- Analyze unknowns — are they siblings? Spouses? Friends?
- Cross-reference unknowns against the 1928 group

### Phase 4: Systematic Identification Candidates
- Run compute_identity_suggestions.py in dry-run to see current scores
- Create co_occurrence_pairs table and populate it
- Re-run with full signal strength
- Review top candidates with user

## Infrastructure Status (from research agents)

### PRD-059 Phase 4 — Identity Inference Signals
6 signals, weighted sum → 0.0-1.0 composite score:

| Signal | Weight | Status |
|--------|--------|--------|
| Family Cluster Score (AD-235) | 0.25 | IMPLEMENTED |
| Co-Occurrence Frequency | 0.10 | BLOCKED — needs `co_occurrence_pairs` table |
| Age Trajectory Consistency | 0.20 | IMPLEMENTED |
| GEDCOM Relationship Match | 0.10 | IMPLEMENTED |
| Human Testimony | 0.30 | STUB (hardcoded) |
| Source Provenance | 0.05 | STUB (hardcoded) |

### BLOCKER: Missing `co_occurrence_pairs` Supabase Table
- Script `scripts/compute_identity_suggestions.py` expects this table
- Without it, Signal 3 returns 0 for all candidates
- Fix: CREATE TABLE + populate from `scripts/event_grouping.py` output
- Estimated: 30 min

### Current Identity Suggestions
- 18 rows in `identity_suggestions` table from Session 147
- Average confidence was low (0.288) because co-occurrence signal was missing
- After creating the table + re-running, confidence should improve to 0.5+

### Admin Endpoints Available
| Endpoint | Purpose |
|----------|---------|
| `POST /api/admin/analyze-event-context/{photo_id}` | Gemini event context extraction |
| `GET /api/compare` | Find similar faces across archive |
| `POST /api/compare/vs-person` | Compare upload against specific person |
| `POST /api/admin/ml-compare` | Extract embeddings from photo |

### Embedding Neighbor API
- `core/neighbors.py` (FROZEN) — `find_nearest_neighbors()`, `find_similar_faces()`
- Confidence tiers: STRONG (<0.80), POSSIBLE (<1.05), SIMILAR (<1.15)
- **Warning:** siblings score 0.96-1.12 (within POSSIBLE range) — not diagnostic for Fox family

## Key Risks
- **Albert/Harry confusion** — ML cannot distinguish them (biological, not bug)
- **Context degradation** — interactive sessions are long; use /clear between phases
- **READ-ONLY on production** — never click action buttons (Lesson 149)
- **Verify genealogical data** — don't trust other Ancestry trees (Lesson 171)
- **co_occurrence_pairs table missing** — blocks full-strength identity scoring
