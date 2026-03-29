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
- **Commit:** pending
