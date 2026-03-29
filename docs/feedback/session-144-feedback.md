# Session 144 Interactive Feedback

## FB-001: GEDCOM search location ambiguity
- **Severity:** P1
- **Context:** User searching for Dora Burd in GEDCOM link panel. Display showed "b. 1895 · d. 1974 · Kiev, Russia" — location appears associated with death date, not birth. Dora was born in Kiev Gubernia but died in Dayton.
- **Root cause:** Birth place was appended to life_span array without label, positioned after death year. Death place was never shown at all.
- **Fix:** FIXED — birth place now grouped with birth year ("b. 1895, Kiev, Russia"), death place grouped with death year ("d. 1974, Dayton, Ohio"). Uses comma within event, dot-separator between events.
- **Screenshot:** User-provided screenshot showing ambiguous display
- **Commit:** pending

## FB-002: Face Analysis should show person name instead of "Face 0"
- **Severity:** P1
- **Context:** Photo page for Albert Fox shows "Face 0: Age ~21, Male — Young man with dark hair..." when we know Face 0 is Albert Fox. Should show "Albert Fox:" instead.
- **Root cause:** face_analysis rendering used face_index directly without looking up identity.
- **Fix:** FIXED — Added face_index→identity name mapping lookup in `_build_ai_analysis_section()`. Falls back to "Face N" for unidentified faces.
- **Screenshot:** User-provided screenshot showing "Face 0" label
- **Commit:** 98250390

## FB-003: Gemini Anchor Research — Pioneer Maccabees Discovery
- **Severity:** Enhancement (feature ideation)
- **Context:** User conducted multi-photo timeline analysis with Gemini Chat. Decoded poster text ("PIONEER MACABEES DETROIT JULY 2X"), cross-referenced with 1910/1915 census data, established 3-photo chronological ordering for Albert Fox.
- **Feature ideas extracted:** See `docs/feedback/session-144-gemini-anchor-research.md`
- **Key takeaway:** Iterative human+AI evidence accumulation (census + visual details + GEDCOM) produces dramatically better date estimates than single-image analysis
- **BACKLOG items:** ANCHOR-002, DETAIL-001, EVIDENCE-001, AGING-001, SOCIAL-001, EVIDENCE-002

## FB-006: Merge button broken on Find Similar + Manual Search
- **Severity:** P0
- **Context:** User on person page for Person 3772 (/c/fox-family/person/483e124f-9440-47cd-8de0-fbbd86b852a3). Clicking "Merge" button next to Albert Fox in Find Similar results does nothing. Same for Merge in Manual Search results — button appears clickable but no action.
- **Screenshots:** User provided 2 screenshots showing both merge surfaces non-functional
- **Root cause:** TBD — investigating
- **Fix:** IN PROGRESS
