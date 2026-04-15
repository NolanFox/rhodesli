# Session 152 — Fox Family Temporal Identification (Interactive)

**Mode:** Interactive identification
**Predecessor:** Session 151 (v0.99.66)
**Context:** `docs/session_context/session-152-context.md`

## Orientation

Read at session start:
- `docs/session_context/session-152-context.md` — full research, working-set tables, identity IDs
- `tasks/lessons.md` — Lessons 171-172 (genealogical verification, event context > embeddings)
- `docs/session_context/session-149-context.md` — event context methodology
- `ROADMAP.md` current state

Set session:
```bash
echo "152" > .claude/current_session.txt
echo "interactive" > .claude/session_mode.txt
source venv/bin/activate
```

---

## Goal

Interactive identification session focused on the Fox family, ~1900-1935 era. Identify unknown faces in photos alongside confirmed Fox family anchors (Albert, Esther, Harry, Irving, Sadie, Rachel, Bessie, Meyer).

**Signal hierarchy** (strongest to weakest):
1. Event context (corsage, aisle walk, head table position)
2. Temporal + geographic context (Dayton=Harry, Detroit=Irving, NY=Albert)
3. Co-occurrence patterns (recurring companions across photos = family)
4. GEDCOM age matching (1894 Minsk birth years vs estimated ages)
5. Human testimony (user recognizes people)
6. Embedding distance (WEAK for siblings — Albert/Harry indistinguishable)

**Hard elimination rules:**
- Two people in the SAME photo cannot be the same person
- If Person X appears alongside Bessie in a photo, X is NOT Bessie
- Confirmed identities in the same photo eliminate each other as candidates

---

## Phase 1: Orient on the 1928 Family Batch (~20 min)

The `inbox_55868a49` batch contains 10 photos from a Fox family event (~1928). The largest single photo has **28 faces** with Irving + Sadie confirmed and 26 unknowns.

### Key photos in this batch:
| Photo ID | Faces | Confirmed |
|----------|-------|-----------|
| `inbox_55868a49_10_28056399_10208529366551876_3169584793595629898_n` | 28 | Irving, Sadie |
| `inbox_55868a49_6_69835310_481178612663039_7889927619368452096_n` | 9 | (check) |
| `inbox_55868a49_7_6d133ec0-d5c5-4186-aecf-7d24fcd5e28c` | 11 | (check) |

### 1a: View the 28-face photo
- Navigate to the photo page in Chrome browser (READ-ONLY)
- Screenshot — map confirmed faces vs unknowns
- Note face positions (who sits next to whom = couples/family units)

### 1b: Run Gemini event context
- Call `POST /api/admin/analyze-event-context/{photo_id}` on the key photos
- Extract: event type, formality, couple pairs, parent-child pairs

### 1c: Report to user
- Show photo with annotations
- List confirmed people and their positions
- Hypothesize about unknowns based on position, age, family context
- **Ask user** — they may recognize people

Save notes to `docs/feedback/session-152-findings.md`. Commit. **/clear.**

---

## Phase 2: Cross-Reference Person 3051 (~15 min)

**Identity ID:** `307a92a6-5e08-4faa-99bc-6c0ea48ce621`
**State:** INBOX, 5 faces
**Appears in 5 photos (1919-1927)** alongside both Albert AND Esther.
**NOT in the 1928 group photo** — so cannot be eliminated by same-photo rule.

### Working set:
| Photo ID | Year | Faces |
|----------|------|-------|
| `inbox_fox-charlie-001_607_02155_p_13akf5twbc3556` | 1919 | 2 |
| `inbox_fox-charlie-001_219_02044_p_13akf5twbc3226` | 1920 | 2 |
| `inbox_fox-charlie-001_220_02152_p_13akf5twbc1989` | 1920 | 4 |
| `inbox_fox-charlie-001_609_02064_p_13akf5twbc3595_r` | 1920 | 4 |
| `inbox_fox-charlie-001_201_02165_p_13akf5twbc3436` | 1927 | 6 |

### 2a: View Person 3051's photos
- Browse each photo on production (READ-ONLY)
- Note: who else appears? Setting? Age/gender of 3051?

### 2b: Check embedding distance
- Query nearest neighbors for Person 3051
- Compare against confirmed Fox siblings
- Check: is 3051 male or female? Young or old? This constrains candidates.

### 2c: Formulate hypothesis
- 3051 is NOT in the 1928 photo, so they could still be Bessie/Sadie/Rachel
- But first check gender/age — if male, could be a Burd brother or friend
- If female + right age for a Fox sister, cross-reference GEDCOM birth years
- Present evidence to user for discussion

Save notes. Commit. **/clear.**

---

## Phase 3: The 1918 Three-Sibling Photo (~15 min)

**Photo ID:** `inbox_fox-charlie-001_204_02068_p_13akf5twbc3600`
**6 faces:** Albert, Harry, Irving + 3 unknowns

### Unknown identity IDs:
- Person 3007: `121c9aa7-ed47-4adc-97a0-46588d5c24de`
- Person 3009: `63a1c0c1-aed2-4429-9e54-9dfae1b099d4`
- Person 3010: `ee0f3026-1459-4cf1-b184-538acf11131d`

### 3a: View and analyze
- Navigate to photo page on production (READ-ONLY)
- Screenshot with face overlays
- Note unknowns: ages, genders, positions relative to the three brothers

### 3b: Cross-reference unknowns
- Do Persons 3007/3009/3010 appear in other photos?
- Check embedding distances to confirmed identities
- ~1918 likely Dayton (Harry's city) — unknowns could be Rose Scheckzner (Harry's wife), or siblings/friends

### 3c: Present findings to user

Save notes. Commit. **/clear.**

---

## Phase 4: Systematic Scoring (~20 min)

**BLOCKER:** `co_occurrence_pairs` Supabase table doesn't exist. This blocks Signal 2 (co-occurrence) in identity suggestions.

### 4a: Create co_occurrence_pairs table
- SQL: `CREATE TABLE co_occurrence_pairs (identity_a uuid, identity_b uuid, shared_photo_count int, PRIMARY KEY (identity_a, identity_b))`
- Populate from `scripts/event_grouping.py` output

### 4b: Run identity suggestion scoring
```bash
python scripts/compute_identity_suggestions.py --family fox --dry-run
```
- Review top candidates with user

### 4c: Execute if user approves
```bash
python scripts/compute_identity_suggestions.py --family fox --execute
```
- Verify suggestions appear on person pages in browser

Commit. **/clear.**

---

## Phase 5: Document Findings + Session Close
- Finalize `docs/feedback/session-152-findings.md` with all identifications
- Assessment: `docs/assessments/session-152-assessment.md`
- CHANGELOG, ROADMAP
- Memory backup

## Key Identity IDs (reference)
| Person | Identity ID | Anchors |
|--------|-------------|---------|
| Albert Fox | `85546ebf-75b9-4971-a9d4-b2ce2271bc19` | 197 |
| Esther Burd Fox | `65207728-9ee6-48c1-be68-a2da23354caf` | 143 |
| Harry Fox | `d74cb556-6d42-460a-842a-3ca61e6e0e7b` | 7 |
| Irving Israel Fox | `7e6aae2b-2b7f-49d3-8e14-1c65a93f9bb6` | 8 |
| Sadie Fox Levine | `a235e626-cb5e-4b03-877f-f1b5b113e7d0` | 4 |
| Rachel Fox Newman | `f41dff7b-ec6e-4d24-ab41-bd20df3e8b51` | 3 |
| Bessie Fox | `b4a43575-931a-442f-a00d-3fcdf5d80b8a` | 2 |
| Meyer Fox | `8d113864-1927-4cb7-a27e-6f99e5f90a1a` | 2 |
| Person 3051 | `307a92a6-5e08-4faa-99bc-6c0ea48ce621` | 5 (INBOX) |

## Key Rules
- **Browser is READ-ONLY on production** — never click action buttons (Lesson 149)
- **Event context > embedding distance** for identification (Lesson 172)
- **Verify genealogy against primary sources**, not Ancestry trees (Lesson 171)
- **Ask the user** — they know the family, they may recognize faces immediately
- **Hard elimination** — same-photo co-occurrence = different people
- Esther is Albert's WIFE (in-law), not a Fox sibling. Meyer is the FATHER.
