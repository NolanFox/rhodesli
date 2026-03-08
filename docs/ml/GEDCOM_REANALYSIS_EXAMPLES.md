# GEDCOM Reanalysis — Before/After Examples

**Parent report:** [GEDCOM_REANALYSIS_REPORT.md](GEDCOM_REANALYSIS_REPORT.md)
**Session:** 93 | **Date:** 2026-03-08 | **AD:** AD-211
**Live site:** `https://rhodesli.nolanandrewfox.com`

---

## Aggregate Statistics

| Metric | Value |
|--------|-------|
| Total photos compared | 67 |
| Range narrowed | 40 (60%) |
| Range widened | 20 (30%) |
| Range unchanged | 7 (10%) |
| Location changed | 64 (96%) |
| Year estimate shifted | 42 (63%) |
| Birth year cross-referenced | 25 (37%) |
| Avg range width (before) | 5.5 years |
| Avg range width (after) | 4.5 years |

**Before model:** `gemini-3-flash-preview` (no GEDCOM context)
**After model:** `gemini-3.1-pro-preview` + `first_order` GEDCOM enrichment (AD-159)

Note: Both model upgrade AND GEDCOM data contribute to changes. The model
upgrade alone would improve reasoning; GEDCOM data enables birth-year
cross-referencing that visual analysis cannot achieve.

---

## Example 1: Baby Portrait — 13-year range collapsed to 1 year

**Photo:** [a8a1730722a4cdeb](https://rhodesli.nolanandrewfox.com/photo/a8a1730722a4cdeb)

| | Before | After |
|--|--------|-------|
| **Year** | 1948 | 1946 |
| **Range** | 1942–1955 (13 yrs) | 1945–1946 (1 yr) |
| **Confidence** | medium | **high** |
| **Location** | "Likely US diaspora (NYC, Miami, or Tampa)" | Los Angeles, California |

**Before reasoning:** "High-key lighting and satin backdrop are hallmarks of
mid-century professional baby photography. The smocked gown is a classic style
that fits within the 1940s-1950s window for professional portraits."

**After reasoning:** "The identified subject, Esther Brenda Israel, was born in
August 1945. The infant in the photograph appears to be approximately 3 to 6
months old, firmly placing the date of the portrait in late 1945 or early 1946."

**Why GEDCOM helped:** Baby photos are undatable by visual cues alone — clothing
and studio backdrops are generic across decades. The birth date (Aug 1945)
instantly collapses a 13-year range to 1 year. This is the single largest
precision improvement in the batch.

---

## Example 2: Cultural Lag Correction — Year shifted 17 years

**Photo:** [inbox_facebook-20260210_0_rachel_capouya_capuano_518391136_10172400849010346_1801982505000708581_n](https://rhodesli.nolanandrewfox.com/photo/inbox_facebook-20260210_0_rachel_capouya_capuano_518391136_10172400849010346_1801982505000708581_n)

| | Before | After |
|--|--------|-------|
| **Year** | 1935 | **1952** (+17 yrs) |
| **Range** | 1930–1942 (12 yrs) | 1950–1955 (5 yrs) |
| **Location** | "Likely USA or Rhodes" | Los Angeles, California |

**Before reasoning:** "Finger waves and embroidered collar peaked in the
mid-1930s. The formal studio setting is typical for the era."

**After reasoning:** "The subject (born 1932) appears to be in her late teens
or early twenties. The signature uses her maiden name, suggesting a pre-marriage
official document. Combined with the culturally lagged 1940s styling, the early
1950s is the most probable timeframe."

**Why GEDCOM helped:** The Sephardic community continued wearing 1930s-style
fashion into the 1950s (cultural lag). Without GEDCOM, the model dated the
*fashion*. With GEDCOM, it dated the *person* — born 1932, appearing ~20 = 1952.
This is the largest year shift in the batch and demonstrates why cultural lag
makes visual-only dating unreliable for diaspora communities.

---

## Example 3: Child's Age as Dating Anchor — Location corrected

**Photo:** [a718d5fc861cef12](https://rhodesli.nolanandrewfox.com/photo/a718d5fc861cef12)

| | Before | After |
|--|--------|-------|
| **Year** | 1964 | **1957** (-7 yrs) |
| **Range** | 1961–1967 (6 yrs) | 1956–1959 (3 yrs) |
| **Location** | "Miami or NYC or Rhodes, Greece" | **San Francisco, California** |

**Before reasoning:** "The woman's beehive hairstyle is the most definitive
dating cue, placing the photo firmly in the early to mid-1960s."

**After reasoning:** "The child, likely Jeanne Benveniste (born March 1954),
appears to be approximately 3 to 4 years old, firmly placing the photograph
around 1957-1958."

**Why GEDCOM helped:** Fashion said 1960s, but the child's birth year (1954)
and apparent age (~3-4) pulled the date back to 1957. GEDCOM residential data
also corrected the location from a vague guess to San Francisco.

---

## Example 4: Absence as Evidence — Missing sibling dating

**Photo:** [746dd11e5b4d86a1](https://rhodesli.nolanandrewfox.com/photo/746dd11e5b4d86a1)

| | Before | After |
|--|--------|-------|
| **Year** | 1933 | 1934 |
| **Range** | 1930–1938 (8 yrs) | 1933–1935 (2 yrs) |
| **Location** | "Unknown" | **Asheville, North Carolina** |

**Before reasoning:** "Woman's chin-length wavy bob and children's clothing
suggest early 1930s."

**After reasoning:** "The visual ages of the three children perfectly match the
birth years of Selma (b. 1928), Anita (b. 1931), and Nace (b. 1933). **The
absence of the fourth sibling, Betty Susan (b. 1935), strongly points to before
her birth.**"

**Why GEDCOM helped:** The model used *absence* of a known sibling as evidence.
Three children present, fourth not yet born → photo constrained to 1933-1935.
This type of reasoning is impossible without family tree data.

---

## Example 5: Date Stamp Correction — GEDCOM as error-checker

**Photo:** [6a62687aec225e39](https://rhodesli.nolanandrewfox.com/photo/6a62687aec225e39)

| | Before | After |
|--|--------|-------|
| **Year** | 1962 | **1965** |
| **Range** | 1961–1963 | **1965–1965** (exact) |

**Before reasoning:** "The 'MAY 62' date stamp is the primary evidence."

**After reasoning:** "Definitive physical date stamp of 'MAY 65'. The apparent
age of Betty Capeluto (born 1953, appearing ~11.5 years old) perfectly
corroborates this exact date."

**Why GEDCOM helped:** The old model misread "65" as "62". With GEDCOM, the
new model cross-checked: born 1953, appearing ~11.5 = 1965, not 1962.
GEDCOM served as a **correction mechanism** for OCR errors.

---

## Example 6: Wedding Dating from Life Events

**Photo:** [ba91ea699c0e600f](https://rhodesli.nolanandrewfox.com/photo/ba91ea699c0e600f)

| | Before | After |
|--|--------|-------|
| **Year** | 1952 | **1954** |
| **Range** | 1948–1958 (10 yrs) | 1953–1955 (2 yrs) |
| **Location** | "Unknown" | **Dayton, Ohio** |

**Before reasoning:** "Full-skirted ballgown silhouette places this in the 1950s."

**After reasoning:** "The groom's apparent age aligns with Roland Fox (b. 1930)
in his mid-20s. Genealogical records show a cluster of events for Roland in
June 1954, preceding the birth of his first child in 1956, strongly pointing
to a 1954 wedding."

**Why GEDCOM helped:** Fashion gave a 10-year window. GEDCOM narrowed it to 2
years using birth year + marriage records + first child's birth. Also identified
the city (Dayton, OH) from GEDCOM residential data.

---

## Example 7: Document vs. Physical Copy Date

**Photo:** [inbox_ancestry-20260210_11_David_Raymond_Capouano_-_declaration_of_intention_](https://rhodesli.nolanandrewfox.com/photo/inbox_ancestry-20260210_11_David_Raymond_Capouano_-_declaration_of_intention_)

| | Before | After |
|--|--------|-------|
| **Year** | 1941 | **1947** |
| **Range** | 1940–1941 (1 yr) | 1947–1947 (exact) |

**Before reasoning:** "Document explicitly dates the original declaration to
September 10, 1941. The subject's age is stated as 33."

**After reasoning:** "While the original declaration was sworn on September 10,
1941, this specific physical document bears a certification date of March 13,
1947, and is printed on a form revised in May 1944."

**Why GEDCOM helped:** The old model dated the *event*. The new model
distinguished between the original declaration (1941) and the physical copy
(1947), reading the form revision date as evidence. GEDCOM biographical data
helped contextualize the document's timeline.

---

## Example 8: Havana Discovery via GEDCOM Residential Data

**Photo:** [inbox_b5e8a89e_8_603575434.282777](https://rhodesli.nolanandrewfox.com/photo/inbox_b5e8a89e_8_603575434.282777)

| | Before | After |
|--|--------|-------|
| **Year** | 1950 | **1955** |
| **Range** | 1945–1958 (13 yrs) | 1954–1956 (2 yrs) |
| **Location** | "Miami or Tampa, Florida" | **Havana, Cuba** |

**Before reasoning:** "Combination of white dinner jackets and 'Tiki' aesthetic
strongly points to the post-WWII era in Florida."

**After reasoning:** "The toddler, identified as Betty Capeluto (born Sept
1953), appears to be 1 to 2 years old. The parents' apparent ages match
Moises (born 1905, ~50 here) and Victoria (born 1918, ~37 here)."

**Why GEDCOM helped:** Three birth years independently constrained the date.
GEDCOM residential data revealed the family's connection to Havana, correcting
the assumed Florida location.

---

## Patterns of GEDCOM Value

### When GEDCOM adds the most value:
1. **Children's ages** — Birth years + apparent age = narrow date ranges
2. **Sibling absence/presence** — Family knowledge enables absence reasoning
3. **Cultural lag correction** — Diaspora fashion lags; person-dating beats fashion-dating
4. **Location correction** — Residential data overrides visual guesses
5. **Document contextualization** — Event dates vs. physical copy dates

### When GEDCOM adds less value:
- Photos with no identified faces linked to GEDCOM
- Distant-branch subjects with only name data (no birth years)
- Photos where visual cues already give strong dating (date stamps, newspapers)

### GEDCOM depth → Result quality correlation:
| GEDCOM Depth | Typical Improvement |
|-------------|-------------------|
| Deep (nuclear family, census/vital records) | 5-12 year range reduction |
| Moderate (birth/death years only) | 2-5 year range reduction |
| Sparse (name only) | Minimal — falls back to visual analysis |

---

## References

- **Parent report:** [GEDCOM_REANALYSIS_REPORT.md](GEDCOM_REANALYSIS_REPORT.md)
- **Detail file:** [GEDCOM_REANALYSIS_DETAIL.md](GEDCOM_REANALYSIS_DETAIL.md)
- **AD-211:** GEDCOM batch reanalysis value assessment (ALGORITHMIC_DECISIONS.md)
- **AD-159:** GEDCOM enrichment variant selection (`first_order`)
- **User feedback:** [session-93-user-feedback.md](../session_context/session-93-user-feedback.md)
- **Session assessment:** [session-93-assessment.md](../assessments/session-93-assessment.md)
