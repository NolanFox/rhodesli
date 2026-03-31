# Session 145 Context: Family Research Intake + Temporal Identity Inference

**Predecessor**: Session 144b (docs/session_context/session-144b-context.md)
**Date**: 2026-03-30
**Mode**: Interactive
**State**: v0.99.57, 3980+ app tests, PRD-059 Phases 1-3 complete

---

## What Session 144b Delivered
- 3 P1 bug fixes (sort, 0% display, data repair)
- Batch completion: Albert 196/196, Esther 141/141 (100% coverage)
- PRD-059 Phase 2+3: 17 event groups, 391 co-occurrence pairs
- Geo dual-write: 541 map pins (97.7%)
- SEC-001 filter hardening, FB-005 Needs Name filter
- DATA-AUDIT-001 (23 anchors promoted) + DATA-AUDIT-002 (52 merges flattened)

## Session 145 Goals
1. **Rachel branch intake** — Nolan contacted Rachel Fox's descendants, received responses
2. **Sarah branch intake** — Nolan contacted Sarah's descendants, received responses
3. **PRD-059 Phase 4** — Identity inference combining new family intelligence with temporal/co-occurrence data

## Key Identity Context
- Person 3481 (unidentified woman in penny arcade strip with Albert): most likely Rachel Fox (55%)
- Rachel (Ray Ronya) Fox: @I132128933061@, b. Oct 1891
- Rose Rachel Fox: b. 25 April 1892 (may be same person or different sibling — resolve during intake)
- Albert Fox: 85546ebf-75b9-4971-a9d4-b2ce2271bc19 (199 faces)
- Esther Burd Fox: 65207728-9ee6-48c1-be68-a2da23354caf (143 faces)

## GEDCOM Ambiguity: Rachel vs Rose Rachel
- Session context references both "Rachel (Ray Ronya) Fox" (b. Oct 1891) and "Rose Rachel Fox" (b. 25 April 1892)
- 7-month gap in birth dates suggests conflicting records or different people
- Must resolve during family research intake

---

## Phase 1: Rachel Branch Findings

### Contacts
1. **Sara Ashley Newman Murray** (via iMessage) — Rachel's great-granddaughter (Howard's daughter)
2. **Howard B Newman** (via email + text) — Rachel's grandson (Bernard's son, b. 1952)
3. **Ken (Kenneth) Newman** (via text, cc'd by Howard) — Rachel's grandson (Bernard's son, b. 1956)
4. **Bruce Heiden** (mentioned by Howard) — Rachel's grandson (Edwin W Heiden's son, b. 1951)

### Family Tree (from Ancestry screenshot)
- **Rachel (R) Fox (Fuks)** 1889-1965 married **Aaron H (A) Newman (N)** 1882-1944
- Children of Rachel & Aaron:
  - Natalie (T) Newman 1911-2003
  - Sandy (S) Newman 1912-2002
  - Edwin W Heiden 1912-1974
  - Elizabeth L Newman 1915-2004
  - Paul Newman 1923-2007
  - Helene Kirsch (dates unknown)
  - Bernard (B) Newman 1919-1995 (married Minnie Garfinkel)
- Bernard's children: Bruce Alan Heiden (1951-), Nancy K Shimer, Kenneth Newman (1956-), Alan Newman, **Howard B Newman (1952-)**
- Howard married Marilyn D Angel (1959-), children: Matthew B Murray (1988-), **Sara Ashley Newman (1984-)**

### GEDCOM Ambiguity RESOLVED
- Ancestry tree: Rachel (R) Fox (Fuks) **1889-1965**
- GEDCOM @I132128933061@: Rachel (Ray Ronya) Fox, b. **Oct 1891**
- Howard's statement: "She passed the next summer [1965] from congestive heart disease at a very old 72" → birth ~**1893**
- Rose Rachel Fox (b. 25 April 1892): likely SAME PERSON with conflicting records
- **Conclusion**: All three references are the same Rachel. Birth dates range 1889-1893 (typical immigrant record variance). Death: summer 1965, CHD.

### Key Finding: Person 3481 Hypothesis WEAKENED
- **Howard Newman**: "I am almost certain that the woman in the pictures is not my grandmother"
- This reduces the Rachel hypothesis for Person 3481 from 55% to ~15-20%
- However, Howard is working from a 1960s memory of an elderly Rachel — young Rachel (~1915) might look different enough that he can't confirm
- Howard forwarded to cousin Bruce Heiden and Ken Newman for additional input

### Reference Photos Obtained
1. **IMG_2593**: Rachel and Howard at Howard's bar mitzvah, **September 1964** (Rachel age ~72-75)
2. **Grandma and Paul.jpg**: Rachel and her son Paul Newman, **circa 1950** (Rachel age ~58-61)
- Both photos uploaded to Rhodesli and Rachel faces merged into single identity

### Additional Intelligence
- Sara Newman Murray: "They really resemble my father!!!" (re: penny arcade photo) — family resemblance signal
- Howard's father Bernard mentioned Dayton Foxes were in **liquor distribution** (Nolan: Albert was a grocer, possibly also liquor)
- Howard's family knew about cousins in Dayton and LA (confirming Fox family geographic spread)
- Ken Newman may have more photos (Howard: "my cousin Ken probably has much more")

### Open Leads
- Bruce Heiden and Ken Newman may provide additional input on Person 3481
- Ken Newman likely has more Rachel/Fox family photos
- Sara checking if Howard has old Fox family photos

## Deep Analysis: Fox Family Identity Clusters

### Embedding Distance Matrix (Rachel + Person 4044 MISSING — production only)

**Confirmed Fox siblings — internal distances:**
| Pair | Distance |
|------|----------|
| Charles ↔ Roland | 0.93 |
| Albert ↔ Harry | 1.11 |
| Albert ↔ Irving | 1.13 |

**Unidentified persons — average distance to confirmed Fox family:**
| Person | Avg→Fox | Closest | Distance | Assessment |
|--------|---------|---------|----------|------------|
| 3299 | 1.29 | Bessie | 0.97 | STRONGEST — borderline same-person |
| 82863528 | 1.30 | Bessie | 1.07 | Strong Bessie cluster |
| 82863536 | 1.30 | Albert | 1.18 | Moderate — male Fox line |
| 4044 | 1.34 | Bessie | 1.23 | Weak-moderate |
| 3481 | 1.43 | Sadie | 1.37 | Very weak — NOT Fox relative |
| 3378 | 1.40 | Irving | 1.36 | Very weak |

### GEDCOM Discoveries

**"Ervin Fox" = Irving Israel Fox** (@I132128488728@, b. 10 Jan 1898, d. 16 Jun 1985)
- Person 82863536 was labeled "Ervin Fox's sister Sadie" by a Fox cousin
- Nolan compared with confirmed Sadie (naturalization form) and says NOT Sadie
- Remaining candidates: Rachel or Bessie

**Bessie Fox birth year ambiguity:**
- @I132128502300@: Bessie (Basya Minya) Fox (Fuks), b. abt 1884
- @I132332301866@: Bessie Fox Fuchs, b. Jan 1892
- If 1884: age 91-93 in Person 3299's photos (1975/77) — very unlikely
- If 1892: age 83-85 in Person 3299's photos — plausible!
- 0.51 distance (85% match) between 3299 and Bessie = essentially same-person

**Person 3299 photo dates:** 1975 and 1977 (both color photos of elderly woman)

**Person 4044 photo dates:**
- 02064: 1920, subject ages 18-24
- 02146: 1930, subject ages 30-48
- 01556: 1954, subject ages 30-60
- Nolan suspects the 1954 photo face may not match the younger faces

### Family Cluster Approach (Research-Backed)
- Kinship verification is well-established (FIW dataset, ArcFace ~78% baseline)
- Aggregate evidence from multiple family members stronger than pairwise
- "Family Cluster Score" valid as soft signal for admin review
- Risk: endogamy false positives in tight Jewish community

### Nolan's Working Hypotheses
- Person 82863536 = Rachel Fox Newman
- Person 3299 = Bessie Fox (if birth year allows)
- Person 82863528 = Bessie Fox
- Person 4044 = Bessie Fox (uncertain — 1954 photo may be different person)
- Person 3481 = NOT Rachel, NOT a Fox relative (embedding evidence + Howard testimony)

## Phase 2: Sarah Branch Findings

*(To be filled during interactive session)*

## Phase 3: Temporal Analysis

*(To be filled during interactive session)*
