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
