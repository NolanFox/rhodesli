# Session 152 Prompt — Fox Family Temporal Identification (Interactive)

**Mode:** interactive
**Predecessor:** Session 151 (v0.99.66)
**Baseline:** 4163 app tests

## Orientation
Read: `docs/session_context/session-152-context.md`
Set: `echo "152" > .claude/current_session.txt && echo "interactive" > .claude/session_mode.txt`

## Goal

Interactive identification session focused on the Fox family, specifically the ~1900-1935 era. Use temporal co-occurrence analysis, Gemini event context, and embedding distances to identify unknown faces in photos alongside confirmed Fox siblings (Albert, Esther, Harry, Irving, Sadie, Rachel, Bessie, Meyer).

## Phase 1: Orient on the 1928 Family Gathering (~20 min)

The **1928 family gathering** photo has 63 faces with 6 of 8 Minsk siblings confirmed. This is the Rosetta Stone.

### 1a: View the photo
- Open `inbox_55868a49_6_69835310_4811...` in Chrome browser (find full photo_id from Supabase)
- Navigate to the photo page on production
- Screenshot at desktop width — map the confirmed faces vs unknowns
- Note face positions (who sits next to whom = couples/family units)

### 1b: Run Gemini event context
- Call `/api/admin/analyze-event-context/{photo_id}` on this photo
- Extract: event type, formality, role indicators, couple pairs, parent-child pairs
- This gives us structured relationship data

### 1c: Report to user
- Show the photo with annotations
- List confirmed people and their positions
- Hypothesize about unknown faces based on position, age, and family context
- Ask user for input (they may recognize people)

## Phase 2: Cross-Reference Person 3051 (~15 min)

Person 3051 appears in 5 photos (1919-1927) with both Albert AND Esther. Top recurring companion.

### 2a: View Person 3051's photos
- Browse the 5 photos on production
- Note: who else appears in each photo? What's the setting?

### 2b: Check embedding distance
- Query nearest neighbors for Person 3051 faces
- Compare against confirmed Fox siblings
- Check if 3051 appears in the 1928 family gathering

### 2c: Formulate hypothesis
- Given date range (1919-1927), co-occurrence with Albert+Esther, and appearance:
  - Could be a sibling (Bessie, Sadie, Rachel — all women at that time)
  - Could be a Burd family member (Esther's side)
  - Could be a spouse of a sibling
- Present evidence to user for discussion

## Phase 3: The 1918 Three-Sibling Photo (~15 min)

Photo with Albert + Harry + Irving + 3 unknowns.

### 3a: View and analyze
- Navigate to `inbox_fox-charlie-001_204...`
- Screenshot with face overlays
- Note: 3 unknown faces — ages, genders, positions

### 3b: Cross-reference unknowns
- Check if Persons 3007, 3009, 3010 appear in other photos
- Check embedding distances to confirmed identities
- Consider: if this is ~1918 and in Dayton (Harry's city), unknowns could be Harry's wife Rose Scheckzner, or other local family

### 3c: Present findings to user

## Phase 4: Systematic Scoring (~20 min)

### 4a: Create co_occurrence_pairs table
- SQL migration to create the missing table
- Populate from event grouping data

### 4b: Run identity suggestion scoring
```bash
python scripts/compute_identity_suggestions.py --family fox --dry-run
```
- Review top candidates
- Discuss with user which look promising

### 4c: Execute if user approves
```bash
python scripts/compute_identity_suggestions.py --family fox --execute
```

## Phase 5: Document Findings
- Log all identifications (confirmed or hypothesized) to feedback file
- Update BACKLOG with any follow-up items
- Commit session artifacts

## Key Rules
- **Browser is READ-ONLY on production** — never click action buttons
- **Event context > embedding distance** for identification (Lesson 172)
- **Verify genealogy against primary sources** (Lesson 171)
- **Ask the user** — they know the family, they may recognize faces immediately
- **Don't claim fixed without verification** — all identifications are hypotheses until user confirms
