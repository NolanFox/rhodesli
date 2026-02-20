# UX Audit Framework

**Created:** Session 53 (2026-02-20)
**Updated:** Session 54 (2026-02-20)

## What This Directory Contains

| File | Purpose |
|------|---------|
| **UX_ISSUE_TRACKER.md** | Master list of ALL UX issues with dispositions. This is the source of truth. |
| PRODUCTION_SMOKE_TEST.md | Results from systematic curl-based route testing (Session 53). |
| UX_FINDINGS.md | Route-by-route UX assessment from production audit. |
| FIX_LOG.md | Detailed fix documentation for each resolved issue. |
| PROPOSALS.md | Prioritized improvement proposals with session targets. |
| REGRESSION_LOG.md | Regressions found during cross-feature verification. |

## How to Use

### UX_ISSUE_TRACKER.md (The Master List)
Every UX issue identified from any source must appear here with:
- **Unique ID** (UX-NNN)
- **Source** (which audit file, session, or user report)
- **Disposition** (FIXED, PLANNED, BACKLOG, DEFERRED, REJECTED)
- **Session** (which session will/did address it)

### Adding New Issues
1. Add to UX_ISSUE_TRACKER.md with the next available UX-NNN ID
2. Include the source (which file, session, or report)
3. Set initial disposition (usually BACKLOG or PLANNED)
4. If fixing in this session, add to FIX_LOG.md after implementation

### Updating Dispositions
When an issue is resolved:
1. Update UX_ISSUE_TRACKER.md disposition to FIXED with session number
2. Add fix details to FIX_LOG.md
3. Update PROPOSALS.md if the issue was listed there

### Running a Production Smoke Test
```bash
PROD_URL="https://rhodesli-production.up.railway.app"
# Test all public routes
for route in / /timeline /compare /people /photos /collections /map /tree /connect /estimate /about /activity; do
  echo -n "$route: "
  curl -s -o /dev/null -w "%{http_code} %{time_total}s" "$PROD_URL$route"
  echo
done
```
Log results in PRODUCTION_SMOKE_TEST.md and check against UX_ISSUE_TRACKER.md.

## Breadcrumbs
- ROADMAP.md references this directory
- CLAUDE.md Key Docs does not (too granular) — access via ROADMAP.md
- HD-008 (docs/HARNESS_DECISIONS.md) — production smoke test as session prerequisite
- HD-009 — HTMX indicator CSS dual-selector rule
