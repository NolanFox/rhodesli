# Session 152 — Fox Family Temporal Identification (Interactive)

**Mode:** Interactive identification
**Predecessor:** Session 151 (v0.99.66)
**Context:** `docs/session_context/session-152-context.md`

## Orientation

Read at session start:
- `docs/session_context/session-152-context.md` (full research, photo inventories, identity IDs)
- `tasks/lessons.md` — especially Lessons 171-172 (genealogical verification, event context > embeddings)
- `~/.claude/projects/-Users-nolanfox-rhodesli/memory/feedback_fox_family_relations.md` (1894 Minsk sibling list)
- `~/.claude/projects/-Users-nolanfox-rhodesli/memory/feedback_identification_methodology.md`

Set session:
```bash
echo "152" > .claude/current_session.txt
echo "interactive" > .claude/session_mode.txt
source venv/bin/activate
```

---

## Goal

Interactive identification session focused on the Fox family, specifically the ~1900-1935 era photos. Use temporal co-occurrence analysis, Gemini event context, and embedding distances to identify unknown faces alongside confirmed Fox siblings (Albert, Esther, Harry, Irving, Sadie, Rachel, Bessie, Meyer).

**Signal hierarchy** (strongest → weakest):
1. Event context (corsage, aisle walk, head table → role)
2. Temporal + geographic context (Dayton=Harry, Detroit=Irving, NY=Albert)
3. Co-occurrence patterns (recurring companions = family)
4. GEDCOM age matching (1894 Minsk birth years vs estimated ages)
5. Human testimony (user recognizes people)
6. Embedding distance (WEAK for siblings — Albert/Harry indistinguishable)

---

## Phase 1: Orient on the 1928 Family Gathering (~20 min)

The **1928 family gathering** has 63 faces with 6 of 8 Minsk siblings confirmed. This is the Rosetta Stone.

**Photo ID:** `inbox_55868a49_0_IMG_9727`

**Confirmed faces (13):** Meyer Fox (2), Albert Fox (2), Irving Fox (2), Sadie Fox Levine (2), Rachel Fox Newman, Bessie Fox, Jack Fox (2), Rebecca Reva Heft Fox, Jacob Edward Levine, Leonard Larry Fox, Molly Saperstein

**~40 unidentified faces** — likely includes spouses, children, extended family.

### 1a: View the photo
- Navigate to `/c/rhodes/photo/inbox_55868a49_0_IMG_9727` in Chrome browser
- Screenshot at desktop width — map confirmed faces vs unknowns
- Note face positions (who sits next to whom = couples/family units)

### 1b: Run Gemini event context
- Use `scripts/batch_event_context.py --limit 1` on this photo, or
- Call the admin endpoint directly for structured output
- Extract: event type, formality, couple pairs, parent-child pairs

### 1c: Report to user
- Show the photo with annotations
- List confirmed people and their positions
- Hypothesize about unknown faces based on position, age, family context
- **Ask user** — they may recognize people immediately

**Commit notes. /clear.**

---

## Phase 2: Cross-Reference Person 3051 (~15 min)

**Identity ID:** `307a92a6-5e0e-4d60-9e5e-e3c82a2ef1b3`
**State:** INBOX, 5 faces
**Appears in 5 photos (1919-1927)** alongside both Albert AND Esther — top recurring companion.

**Photos:**
- `inbox_fox-charlie-001_219` (1920)
- `inbox_fox-charlie-001_607` (1919)
- `inbox_fox-charlie-001_220` (1920)
- `inbox_fox-charlie-001_201` (1927)
- `inbox_fox-charlie-001_609` (1920)

### 2a: View Person 3051's photos
- Browse each photo on production
- Note: who else appears? What's the setting? Age/gender of 3051?

### 2b: Check embedding distance
- Query nearest neighbors for Person 3051
- Compare against confirmed Fox siblings (especially Bessie, Sadie, Rachel)
- Check if 3051 appears in the 1928 family gathering

### 2c: Formulate hypothesis
- Given 1919-1927 range + co-occurrence with Albert+Esther:
  - Could be sibling (Bessie? Sadie? Rachel?)
  - Could be Burd family (Esther's side)
  - Could be spouse of a sibling
- Present evidence to user for discussion

**Commit notes. /clear.**

---

## Phase 3: The 1918 Three-Sibling Photo (~15 min)

**Photo ID:** `inbox_fox-charlie-001_204_02068_p_13akf5twbc3600`
**6 faces:** Albert Fox, Harry Fox, Irving Fox + 3 unknowns

### 3a: View and analyze
- Navigate to photo page on production
- Screenshot with face overlays
- Note: 3 unknown faces — ages, genders, positions relative to brothers

### 3b: Cross-reference unknowns
- Persons 3007, 3009, 3010 — do they appear in other photos?
- Check embedding distances to confirmed identities
- Consider: ~1918, likely Dayton (Harry's city) → unknowns could be Rose Scheckzner (Harry's wife), other local family, or friends

### 3c: Present findings to user

**Commit notes. /clear.**

---

## Phase 4: Systematic Scoring (~20 min)

**BLOCKER:** The `co_occurrence_pairs` Supabase table doesn't exist yet. Phase 4 of PRD-059 needs it for the co-occurrence scoring signal.

### 4a: Create co_occurrence_pairs table
- SQL migration: `(identity_a uuid, identity_b uuid, shared_photo_count int)`
- Populate from event grouping data (`scripts/event_grouping.py` output)
- This unblocks Signal 3 (co-occurrence) in identity suggestions

### 4b: Run identity suggestion scoring
```bash
python scripts/compute_identity_suggestions.py --family fox --dry-run
```
- Review top candidates with user
- Discuss which look promising

### 4c: Execute if user approves
```bash
python scripts/compute_identity_suggestions.py --family fox --execute
```
- Verify suggestions appear on person pages in browser

**Commit. /clear.**

---

## Phase 5: Document Findings + Session Close
- Log all identifications (confirmed or hypothesized) to feedback file
- Update BACKLOG with follow-up items
- Assessment: `docs/assessments/session-152-assessment.md`
- CHANGELOG, ROADMAP, SESSION_HISTORY
- Memory backup

## Key Rules
- **Browser is READ-ONLY on production** — never click action buttons (Lesson 149)
- **Event context > embedding distance** for identification (Lesson 172)
- **Verify genealogy against primary sources**, not Ancestry trees (Lesson 171)
- **Ask the user** — they know the family, they may recognize faces immediately
- **Don't claim identified without user confirmation** — all are hypotheses until confirmed
