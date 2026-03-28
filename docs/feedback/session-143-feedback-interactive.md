# Session 143 Interactive Feedback — Gemini Quality Review

## FB-008: Photo 3 misidentifies relationship context
- **Severity:** P2 (analysis quality)
- **Photo:** inbox_fox-charlie-001_40_01591_p_13akf5twbc0783_r
- **Issue:** Gemini called it a "50th wedding anniversary" with Esther, but the woman is actually **Rose** (Albert's second wife). Esther died in the late 1960s. The GEDCOM should contain:
  - Esther's death date
  - Albert & Rose's marriage
  - The sequential spouse relationships (Esther → Rose → third wife)
- **Root cause:** Either the GEDCOM context didn't include spouse timelines, or Gemini didn't reason about which wife was alive at the estimated date.
- **The man with the flower/boutonniere** suggests this could be Albert & Rose's wedding, not an anniversary.
- **Roland Fox** is the younger man — he lived in Florida, so his presence in Ohio indicates a special event.
- **Action needed:** Check what GEDCOM context was sent; consider enriching prompt with spouse timeline.

## FB-009: Alternate birth dates not handled well
- **Severity:** P2 (data quality)
- **Issue:** Albert Fox has birth year 1892 (primary, from Russian revision list) AND 1896 (alternate, from one record). Gemini's analyses used ~1896 in some cases. The GEDCOM may have both dates.
- **Context:** This is common for pre-20th-century births — census/immigration docs give approximate ages. The preponderance of evidence + sibling ages confirm 1892.
- **Question:** Does the GEDCOM specify primary vs alternate? Which one does our context builder use?
- **Action needed:** Check GEDCOM parsing for alternate birth dates; default to primary.

## FB-010: Anchor photo temporal refinement (FEATURE IDEA)
- **Severity:** Feature request
- **Concept:** Some photos have narrow, known date bands (e.g., the 1919 Detroit portrait taken before Albert's WW1 enlistment: https://rhodesli.nolanandrewfox.com/c/fox-family/photo/b39d6cbe7fe63fca). These "anchor photos" could refine estimates of nearby photos.
- **Approach:** "Here's a photo we're confident is from 1919. Is the subject younger or older in this other photo? Refine your estimate."
- **User notes:** "This is essentially how I would do it." Maps to PRD-059 temporal co-occurrence.
- **Action:** Consider multi-pass refinement where anchor photos constrain estimates of related photos. Could test via Gemini chatbot first.

## FB-011: Sequential spouse relationships as temporal markers
- **Severity:** Feature request
- **Concept:** Photos with Esther → photos with Rose → photos with third wife form a natural chronological sequence. The system should recognize which spouse appears and use that as a date constraint.
- **Example:** If Rose appears, the photo MUST be after Esther's death (late 1960s) and before Rose's death/Albert's third marriage. This narrows the date window significantly.
- **Action:** Enrich GEDCOM context with spouse timelines; add to Gemini prompt.

## FB-012: Location confidence should reflect source
- **Severity:** P3 (minor)
- **Issue:** Codex noted that locations like "Dayton, Ohio" are inferred from GEDCOM (family residence), not from visual evidence. The confidence should distinguish "visually confirmed" from "biographically inferred."
- **Action:** Consider adding location_source field: "visual" vs "biographical" vs "both".
