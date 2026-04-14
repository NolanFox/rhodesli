# Session 148c Context — Resume Fader Collection Fox Search

## Predecessors
- Session 148: Interactive Fader exploration, identified Sherry + Ira, logged 4 FB items
- Session 148b: Overnight sprint — TOOLS-007 built, upload pipeline fixed, main.py refactored, Codex audit done

## What's Been Done
- **Sherry Ann Fader** (37611153-36d1-4f20-9535-d994e1893e13): CONFIRMED, 3+ anchors, merged with bb7d05ba from 18-person group photo
- **Ira Josowitz** (f1fa358b-f3c1-4347-83fb-71f9379abeff): CONFIRMED, identified in same 18-person group photo, GEDCOM-linked
- **21 candidate photos** ranked by embedding distance to Sherry — only the first (18-person group) was reviewed
- **TOOLS-007** now exists: `GET /api/admin/search-person-in-collection` — can search for any person across any collection via API
- **Upload pipeline fixed**: 404 after approval, anonymous attribution, missing thumbnails

## Family Research (from Ancestry)
- **Sherry Ann Fader** (1944-2018): Daughter of Abraham I. Fader (1901-1993) and Nadia Kubrin (1909-1988)
  - 1st marriage: 1965 to Ira Leon Josowitz (NYC, license #4285)
  - 2nd marriage: Jan 1976 to Paul DiPasquale (Lakewood Township, NJ)
  - Children: Erik Alan Josowitz, Michael H
- **Ira Josowitz**: Son of David Josowitz (45) and Anna Josowitz (42)
  - 1940 Census: Brighton 12th Street, Brooklyn
  - Siblings: Renee (16), Greta (12), Ira (6)
- **Abraham I. Fader** (Oki): 1901-1993
- **Nadia Kubrin**: 1909-1988
- **Fox connection**: Sarah Fox married into the Fader family. Erik's great-grandparents include Fox family members.

## Identification Strategy
1. Use wedding photos (1965 first marriage, 1976 second) as temporal anchors
2. Grandparents Abraham (d.1993) and Nadia (d.1988) bracket older photos
3. Look for Fox siblings (Bessie, Sarah, Harry, Sadie, Rachel, Albert, Irving, Jacob) in group photos
4. Multi-face photos are highest value — confirming Sherry/Ira reveals other attendees

## Candidate Photos — Remaining to Review
All URLs relative to `https://rhodesli.nolanandrewfox.com/c/fader-collection`

| # | Dist | Faces | URL | Notes |
|---|------|-------|-----|-------|
| 1 | 0.897 | 1f | /photo/4bb9897005241971 | Wedding — user confirmed as Sherry |
| 2 | 0.906 | 2f | /photo/afac6767bfac5005 | |
| 3 | 0.907 | 1f | /photo/85b66ac12eb916cc | |
| 4 | 0.914 | 2f | /photo/38d906aab85a7477 | |
| 5 | 0.921 | 4f | /photo/97db3387982454f3 | Group — high value |
| 6 | 0.921 | 6f | /photo/496bce2281e8d7b8 | Group — high value |
| 7 | 0.928 | 1f | /photo/3cdd2f418aa8350b | |
| 8 | 0.929 | 1f | /photo/849b3a76dc1aa143 | |
| 9 | 0.936 | 1f | /photo/5597dde7cb5ecd49 | |
| 10 | 0.938 | 2f | /photo/9d164660ad0a7cb6 | |
| 11 | 0.939 | 3f | /photo/eb8e9667c6fbbd2e | Group |
| 12 | 0.939 | 1f | /photo/982f7e511b28778b | |
| 13 | 0.943 | 2f | /photo/e4a8eb380173fc92 | |
| 14 | 0.954 | 8f | /photo/68832ba89824c706 | Group — high value |
| 15 | 0.955 | 2f | /photo/7cd9f8a8924794d6 | |
| 16 | 0.969 | 2f | /photo/0a8b082d356ecc05 | |
| 17 | 0.972 | 2f | /photo/f7a83f1785647269 | |
| 18 | 0.975 | 1f | /photo/89c2fef69b6429bb | |
| 19 | 0.976 | 2f | /photo/cb94862600dad21f | |
| 20 | 0.987 | 18f | /photo/291103717c75045f | DONE — Sherry + Ira confirmed |
| 21 | 0.995 | 1f | /photo/17093d708e2189e6 | |

## Open Issues (from 148)
- **FB-002**: Fader collection has zero Gemini date labels — run batch estimation
- **FB-003**: Cross-batch clustering missed Sherry (embedding sync gap between local/production)
- **FB-004**: No in-app UI for cross-collection search (API exists now via TOOLS-007, UI not wired)

## New Capabilities Available
- **TOOLS-007 API**: Can now programmatically search for any person in any collection
- **Restore button**: Dismissed cards now have restore-to-inbox button
- **Upload pipeline**: Fixed — approvals should work end-to-end now

## Key Files
- `docs/session_logs/session-148-log.md` — full session log with family research + findings
- `scripts/sherry_search.py` — embedding distance search script (reusable for other people)
- `app/identity_routes.py:5143` — TOOLS-007 endpoint
