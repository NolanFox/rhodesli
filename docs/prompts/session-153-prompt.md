# Session 153 — Fox Family Identification (Continuation)

**Mode:** Interactive identification
**Predecessor:** Session 152 (findings in `docs/feedback/session-152-findings.md`)
**Context:** This is a continuation of Session 152's Fox family temporal identification work.

## Orientation

Read at session start:
- `docs/feedback/session-152-findings.md` — ALL Session 152 findings including corrections and Person 3051 analysis
- `tasks/lessons.md` — Lessons 171-172 + new lessons from Session 152
- `ROADMAP.md` current state

**CRITICAL: Session 152 Corrections (do NOT repeat these errors):**
1. Albert Fox lived in **Dayton, Ohio** (1923-1990). NOT NY/FL.
2. Harry Fox lived in **Los Angeles** (1935+). NOT Dayton.
3. Irving Fox lived in **Los Angeles** (1940+). NOT Detroit.
4. Rebecca (Reva) Heft = **Meyer Fox's wife** (Irving's MOTHER). NOT Irving's wife.
5. Sarah Fox died **Oct 1967** in Miami Beach. NOT 1937. GEDCOM death dates can be wrong — always cross-reference Ancestry.
6. **All 8** surviving adult Fox siblings were alive in 1946.
7. Never suggest candidates that fail basic age/timeline checks.
8. Always verify GEDCOM data against Ancestry before stating family relationships.

Set session:
```bash
echo "153" > .claude/current_session.txt
echo "interactive" > .claude/session_mode.txt
source venv/bin/activate
```

---

## Remaining Work from Session 152

### Phase 3: The 1918 Three-Sibling Photo
**Photo ID:** `inbox_fox-charlie-001_204_02068_p_13akf5twbc3600`
**6 faces:** Albert, Harry, Irving + 3 unknowns

**Unknown identity IDs:**
- Person 3007: `121c9aa7-ed47-4adc-97a0-46588d5c24de`
- Person 3009: `63a1c0c1-aed2-4429-9e54-9dfae1b099d4`
- Person 3010: `ee0f3026-1459-4cf1-b184-538acf11131d`

Tasks:
- View photo on production (READ-ONLY)
- Check if unknowns appear in other photos
- Check embedding distances to confirmed identities
- ~1918 context: Albert, Harry, Irving all in NYC/Brooklyn area at this time
- Unknowns could be: Rose Scheckzner (Harry's wife), Esther Burd (Albert's wife), siblings, friends
- Cross-reference with GEDCOM — verify who was in NYC in 1918

### Phase 4: Systematic Scoring
**BLOCKER:** `co_occurrence_pairs` Supabase table doesn't exist.

Tasks:
- Create `co_occurrence_pairs` table in Supabase
- Populate from event grouping data
- Run `python scripts/compute_identity_suggestions.py --family fox --dry-run`
- Review top candidates with user
- Execute if approved

### Person 3051 — Open Item
**Status:** INCONCLUSIVE from Session 152.
- User's theory: one of Esther's Burd sisters (Dora or Fannie)
- Embeddings reject both (~1.4 distance), but embeddings are weak for relatives
- No co-occurrence elimination possible
- Outlier face `inbox_0aa9d6ebcbd2` in cluster needs visual verification
- **Action:** Ask user to visually compare face crops, or research other Burd relatives on Ancestry

### Key Identity IDs (reference)
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
| Dora Burd Shane | `0ea528ac-01c0-451e-8089-24cae46c8e6a` | 5 |
| Fannie Burd | `475b2111-2928-4dab-880b-b6d227a3e353` | 3 |
| Person 3051 | `307a92a6-5e08-4faa-99bc-6c0ea48ce621` | 5 (INBOX) |

### Corrected Fox Sibling Geography
| Sibling | Birth | Death | City (1920s) | City (1940s+) |
|---------|-------|-------|-------------|--------------|
| Bessie | ~1884 | ? | ? | ? |
| Sarah | ~1879 | Oct 1967 Miami Beach | ? | Miami Beach, FL |
| Harry | 1882 | Jul 1979 LA | Dayton → NYC | Los Angeles |
| Sadie | ~1888 | ~1966 | ? | ? |
| Rachel | 1891 | Jul 1965 | ? | ? |
| Albert | ~1896 | Feb 1990 Dayton | NYC → Dayton (1923) | Dayton |
| Irving | 1898 | Jun 1985 Venice LA | NYC/Brooklyn | Los Angeles (1940) |
| Jack | ~1901 | May 1957 | ? | ? |

### Key Rules (carry forward)
- **Browser is READ-ONLY on production** (Lesson 149)
- **Event context > embedding distance** for identification (Lesson 172)
- **Verify genealogy against Ancestry**, not just GEDCOM (Lesson 171, reinforced Session 152)
- **Age/timeline checks FIRST** before suggesting any candidate
- Esther is Albert's WIFE (in-law), not a Fox sibling. Meyer is the FATHER.
- Ancestry tree ID: `162873127` (Fox/Capeluto/Fogel/Waldorf Family Tree)
