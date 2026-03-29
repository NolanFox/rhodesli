# Session 144: Gemini Output Quality Comparison

**Photo**: `inbox_fox-charlie-001_391_02154_p_13akf5twbc3552_r`
**URL**: `https://rhodesli.nolanandrewfox.com/c/fox-family/photo/inbox_fox-charlie-001_391_02154_p_13akf5twbc3552_r`
**Description**: Formal studio portrait of 6 young adults (3 men, 3 women), 1910s clothing

## 4 Gemini API Calls on This Photo

| Run | Date | GEDCOM | Face Coords | Year | Confidence | Location |
|-----|------|--------|------------|------|------------|----------|
| 1 (Session 142) | Mar 27 | No | ? | ? (no response_summary) | ? | ? |
| 2 (Session 143) | Mar 28 | No | Yes | 1915 | high | ? |
| 3 (Session 144 canary 1) | Mar 29 AM | No | Yes | 1918 | high | Unknown |
| 4 (Session 144 canary 2) | Mar 29 PM | **YES** | Yes | 1915 | high | New York, NY |

## Run 3 vs Run 4: Key Differences (WITHOUT vs WITH GEDCOM)

### Date Estimate
- **Run 3 (no GEDCOM)**: 1918, high confidence
- **Run 4 (with GEDCOM)**: 1915, range 1912-1918, high confidence
- **Delta**: 3 years earlier, with explicit range added

### Location
- **Run 3**: "Unknown" — no location could be determined from visual alone
- **Run 4**: "New York, New York" (medium confidence)
  - Candidate 1: New York (biographical — family in NY in 1910s)
  - Candidate 2: Dayton, Ohio (low — some siblings there by 1910)
- **Delta**: GEDCOM residential history enabled location inference impossible from visual alone

### Reasoning
- **Run 3**: Pure visual analysis (clothing, collars, hairstyles → 1910s)
- **Run 4**: Visual + biographical: "Given the family's residence in New York during this period, the fashion is likely contemporary rather than lagged"
- **Delta**: GEDCOM context resolved the "cultural lag" ambiguity. Without it, Gemini had to guess whether 1910s fashion meant the photo was taken in 1910s (contemporary) or 1920s (lagged). GEDCOM data about NY residence confirmed contemporary.

### Face Analysis
- Both runs: 6 faces with age/gender/description
- Run 4 ages: 22F, 20M, 24F, 22M, 20F, 18M
- Clothing descriptions more specific in Run 4 (mentions "ruffled trim", "flat forehead curls")

### Scene Description
- Run 4: "formal black and white studio portrait of six young adults, three men and three women, arranged with one woman seated in the center"
- Detailed arrangement description not available from Run 3

## Claude Code Assessment

**Quality improvement**: MODERATE-STRONG
- Date shifted 3 years but stayed within same decade (1910s) — both reasonable
- Location inference is the BIG win — impossible without GEDCOM, now has a plausible answer
- "Cultural lag" resolution is valuable — confirms clothing is contemporary, not delayed adoption
- The range (1912-1918) is properly calibrated

**Concerns**:
- Run 2 (Session 143, no GEDCOM) also said 1915 — so the date improvement may be Gemini variance, not GEDCOM
- Run 3 said 1918 without GEDCOM, Run 4 said 1915 with — 3 years is within noise for clothing dating
- The 92 face links (vs 107) means some photos won't get GEDCOM even though links exist

## Questions for User Review
1. Is this the Fox sibling group photo? If so, which siblings are pictured?
2. Does the 1912-1918 range align with family knowledge?
3. Is "New York" the right location for this group in this era?
4. The GEDCOM context mentioned "Bessie and Harry were in Dayton by 1910" — is that accurate?
