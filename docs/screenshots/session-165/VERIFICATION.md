# Session 165 — Production Browser Verification (Phase 4, READ-ONLY)

**Date**: 2026-06-10 · **Deploy**: live (commit `d7ad0cc6`) · **Method**: Chrome MCP (admin logged in) + authoritative rendered-HTML curl checks (Lesson 53).

## Acceptance criteria — all PASS in production

| Check | Result |
|-------|--------|
| `/c/fox-family/person/{Harry}/photos` returns 200 + "Photos of Harry Fox" OG/title | PASS |
| Person page Share button targets `/person/{id}/photos` | PASS |
| Photo viewer with `identity_id`: counter is person-scoped | PASS — "Photo 4 of 5" |
| Arrows cycle ONLY Harry's photos | PASS — neighbors `6dfdc694…`, `6aaa8d4c…` (both in set) |
| Old FB-004 leak target `24c06d3f876d34a5` NOT a neighbor | PASS — 0 occurrences in rendered HTML |
| "Viewing Harry Fox in this photo" context banner (amber VIEWING, not rose alarm) | PASS |
| Anonymous gallery shows NO admin review language ("Needs review"/"Conflicting face assignment") | PASS — 0 occurrences (anonymous curl) |
| Inline keyboard/touch nav scripts XSS-hardened (json-serialized URLs) | PASS — `var prevUrl = "…&sort_by=date_asc"` |

## Screenshots captured (Chrome MCP, admin session)
- `ss_5995vybfj` — `/person/{Harry}/photos` gallery: "Harry Fox · Appears in 5 photos · 2 collections", Share button present.
- `ss_6863swrtg` — photo viewer `a58504ab20bbb741?identity_id=…`: amber "VIEWING — Viewing Harry Fox in this photo" banner, "Back to Harry Fox" breadcrumb, Harry's face highlighted.

(The Chrome extension stores screenshot binaries internally; the rendered-HTML curl
checks above are the authoritative verification per Lesson 53 — "verify production
bugs by fetching rendered HTML, not local data".)
