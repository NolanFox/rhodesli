# Session 135 Feedback — Interactive Triage

Session mode: interactive
Started: 2026-03-22

## Summary
| FB ID | Title | Severity | Category | Status |
|-------|-------|----------|----------|--------|
| FB-001 | Similar Identities broken on New Matches page | P0 | ML/Matching | IN PROGRESS |
| FB-002 | Load More on Similar Identities very slow | P1 | Performance | BACKLOG |
| FB-003 | Manual Search results missing embedding distance | P1 | UX | BACKLOG |
| FB-004 | Photo lightbox arrows cycle through all photos, not cluster photos | P1 | UX | BACKLOG |
| FB-006 | Compare modal left arrow jumps from 2/8 to 7/8 | P1 | UX | IN PROGRESS |
| FB-007 | Distance 0.00 is confusing — why aren't they in the same cluster? | P2 | UX clarity | BACKLOG |
| FB-008 | Override button lacks context — can't see what you'd be overriding | P1 | UX | BACKLOG |
| FB-009 | Compare modal needs visual indicator for active side | P2 | UX | BACKLOG |

---

## Entries

### FB-001: Similar Identities broken on New Matches page
- **Severity:** P0
- **Context:** Person 3779 has 8 faces that are clearly Esther Burd Fox. But in New Matches Focus view, the Similar Identities panel shows Person 1153 (56%, dist 0.94) as top match instead of Esther Burd Fox (121 faces, CONFIRMED). Meanwhile, Esther Burd Fox's OWN Similar Identities correctly shows Person 82863543 at 70% (dist 0.77). The algorithm works from the confirmed side but not from the unidentified side.
- **Screenshot:** Screenshots 1-4 (New Matches) vs 6-8 (Esther's page)
- **Root cause:** TBD — investigating
- **Fix:** IN PROGRESS

### FB-002: Load More on Similar Identities very slow
- **Severity:** P1
- **Context:** When clicking "Load More" to see additional similar identities, response is very slow. Should load almost instantly.
- **Root cause:** TBD
- **Fix:** BACKLOG

### FB-003: Manual Search results missing embedding distance
- **Severity:** P1
- **Context:** When searching for a person by name in Manual Search, results show name and face count but no embedding distance. Distance is critical for triage decisions.
- **Root cause:** TBD
- **Fix:** BACKLOG

### FB-004: Photo lightbox arrows cycle through all photos, not cluster photos
- **Severity:** P1
- **Context:** When viewing a photo in the lightbox overlay from a cluster (e.g., 8 Esther Burd photos), clicking left/right arrows cycles through ALL 630+ Fox Family photos instead of just the ~8 photos in the current cluster. Major time sink — user has to click out and click back in for each photo.
- **Root cause:** Lightbox navigation scope not limited to current context
- **Fix:** BACKLOG

### FB-006: Compare modal left arrow jumps from 2/8 to 7/8
- **Severity:** P1
- **Context:** In Compare Faces modal (Photos tab), Person 3779 shows "2 of 8". Clicking left arrow jumps to "7 of 8" instead of "1 of 8". Photo 1 is unreachable. Right arrow works correctly (2→3→...→8). Left arrow works from 8 down to 2 but then jumps to 7.
- **Root cause:** TBD — likely off-by-one or modular arithmetic bug in photo navigation
- **Fix:** IN PROGRESS

### FB-007: Distance 0.00 is confusing — why aren't they in the same cluster?
- **Severity:** P2 (UX clarity)
- **Context:** User confused by Dist: 0.00 between Person 3779 and Esther Burd Fox. The faces ARE identical (shared face IDs from data integrity issue). Need better messaging — "These identities share the same faces" rather than showing a misleading distance metric.
- **Root cause:** Multi-claimed faces data integrity issue. The distance is technically correct (0.0 = identical embeddings) but confusing without explanation.
- **Fix:** BACKLOG — improve messaging for shared-face matches

### FB-008: Override button lacks context — can't see what you'd be overriding
- **Severity:** P1
- **Context:** When merge is blocked due to co-occurrence (same person in same photo), Override button appears but provides no way to SEE which photo has the co-occurrence or compare the two detections. User has to guess. Should show a one-click preview of the co-occurring photo with both face detections highlighted before committing to override.
- **Root cause:** Override button is a blind action with no preview
- **Fix:** BACKLOG — needs PRD for co-occurrence preview UX

### FB-009: Compare modal needs visual indicator for active side
- **Severity:** P2
- **Context:** In Compare Faces modal, left/right arrows cycle photos for one side. User wants visual embossing/highlighting to indicate which side is "active" (which side's photos the arrows will cycle). Could be a glow, border highlight, or subtle depth effect on the active panel.
- **Root cause:** No active-side indicator in compare modal UX
- **Fix:** BACKLOG
