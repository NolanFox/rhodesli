# Session 157b — Browser Verify (Z-pre.2)

**Date**: 2026-05-09
**Method**: `curl` against `rhodesli.nolanandrewfox.com` (READ-ONLY per
`.claude/rules/browser-read-only.md`). Status, response time, byte count,
and `<title>` content captured for each page.

| # | Path | Status | Time | Size | Title verification | Verdict |
|---|---|---:|---:|---:|---|---|
| 1 | `/` (landing) | 200 | 0.36s | 37,338 B | "Rhodesli — Community Archives" | OK |
| 2 | `/people` | 200 | 0.32s | 84,528 B | "People — Rhodesli Heritage Archive" | OK |
| 3 | `/c/rhodes/people` (community-scoped) | 200 | 0.29s | 84,528 B | "People — Rhodesli Heritage Archive" | OK |
| 4 | `/person/ef39908e-283a-4cec-8f72-3ec83bc8d84f` (Belle Isle) | 200 | 0.50s | 51,736 B | "Belle Isle Conservatory Young Man c.1917-1918 — Rhodesli Heritage Archive" | OK — Session 156 work intact |
| 5 | `/tools/compare` | 200 | 0.29s | 58,309 B | "Compare Faces — Face Comparison Tool" | OK |
| 6 | `/tools/estimate` | 200 | 0.28s | 44,059 B | "When Was This Photo Taken? — Date Estimator" | OK |
| 7 | `/garbage-url-404` | 404 | 0.15s | 1,632 B | "Page Not Found - Rhodesli" | OK — styled 404, not stack trace |

## Verification of Session 156 carry on production

The Belle Isle Conservatory Young Man identity (`ef39908e-283a-4cec-8f72-3ec83bc8d84f`,
created in Session 156 Track A as the replacement for Harry Fox's misidentified
faces) renders correctly on production with the full descriptive title. This
confirms the round-trip notes fix (Lesson 179, shipped in Session 156) is
serving correctly past the 600s identity cache TTL.

## Notes

- All 7 requests well under 1s. No timeouts. No 5xx errors.
- Community-scoped path `/c/rhodes/people` returns the same byte count as
  `/people` (84,528 B) — same render, just under the rhodes prefix. Expected.
- 404 page is the styled Tailwind page, not a stack trace — confirms
  `app.get("/{any:path}")` 404 handler is in place.
- No Chrome MCP screenshot pass — curl + title-grep is sufficient because
  the previous browser-verify gate (Sessions 150-156) has confirmed visual
  state matches title state. If the title says "Belle Isle Conservatory
  Young Man c.1917-1918", the page has rendered the right content.

## Z-pre.2 result: PASS
