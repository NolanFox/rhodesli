# Lessons Learned

**READ THIS FILE AT THE START OF EVERY SESSION.**

71 lessons across 6 topic files. Each lesson has a Mistake/Rule/Prevention structure.
Detailed content is in `tasks/lessons/` — this file is the index.

---

## Auth & Permissions — `tasks/lessons/auth-lessons.md`

| # | Summary |
|---|---------|
| 6 | Auth should be additive (public default), not restrictive |
| 7 | Auth guards must pass through when auth is disabled |
| 8 | Supabase Management API can automate "manual" config |
| 9 | Supabase has TWO types of API keys — use the legacy JWT |
| 10 | Facebook OAuth requires Business Verification — impractical for small projects |
| 11 | HTMX silently follows 3xx redirects — use 401 + beforeSwap for auth |
| 13 | Supabase recovery email redirects to Site URL by default — use redirect_to |
| 15 | Permission regressions are the most dangerous bugs — test route x auth matrix |
| 18 | Supabase sender name requires custom SMTP |
| 19 | Default to admin-only for new data-modifying features |
| 22 | Upload permissions should be admin-only until moderation exists |

## Testing & TDD — `tasks/lessons/testing-lessons.md`

| # | Summary |
|---|---------|
| 1 | Test ALL code paths, not just the obvious one |
| 2 | Regressions require before/after comparison |
| 3 | "It compiles" is not "it works" — test every UI state |
| 4 | Staff engineer approval test — would they approve this PR? |
| 14 | Every UX bug in manual testing is a missing automated test |
| 16 | Testing should not be a separate phase — TDD always |
| 17 | HTMX endpoints behave differently than browser requests — test both |
| 21 | Test assertions must match current UI, not historical UI |
| 37 | Test data must match the actual schema exactly |
| 38 | Read the code before assuming a bug exists |
| 51 | Tests that POST to data-modifying routes MUST mock BOTH load AND save |
| 52 | "Restore original" is not isolation — history and version still change |
| 58 | Test assertions must match CORRECT behavior, not historical behavior |

## Deployment & Infrastructure — `tasks/lessons/deployment-lessons.md`

| # | Summary |
|---|---------|
| 31 | Infrastructure decisions are as important as algorithmic ones |
| 32 | .gitignore and .dockerignore serve different purposes |
| 42 | Token-based API auth is simpler than session cookies for machine-to-machine |
| 43 | Production and local JSON files are completely separate — sync first |
| 47 | Documentation drift is invisible until it's severe |
| 49 | A push-to-production API is essential for the ML pipeline |
| 50 | Downloaded files should match the existing directory convention |
| 53 | Verify production bugs by fetching rendered HTML, not local data |
| 54 | Essential data files must be in BOTH git tracking AND REQUIRED_DATA_FILES |
| 56 | Blind push-to-production overwrites admin actions — merge first |
| 59 | Optional data files need explicit sync, not just bundling |
| 60 | Empty proposals means clustering wasn't re-run, not a UI bug |
| 65 | push_to_production.py must run AFTER ingest completes |
| 66 | identities.json "history" key is REQUIRED — ingest_inbox doesn't write it |
| 67 | sync push must invalidate ALL in-memory caches |
| 68 | Multiple community uploads may come in separate batches |
| 69 | Production-origin data must NEVER be in deploy sync lists |
| 70 | Dockerfile must COPY every package the web app imports at runtime |
| 71 | has_insightface check must probe actual deferred imports |

## UI, HTMX & Frontend — `tasks/lessons/ui-lessons.md`

| # | Summary |
|---|---------|
| 5 | Indentation bugs when wrapping code in conditionals — check every line |
| 12 | Email clients strip `<style>` blocks — always use inline styles |
| 20 | Parallel subagents can safely edit the same file |
| 23 | No single doc file should exceed 300 lines |
| 24 | CLAUDE.md is loaded into every context window — keep it under 80 lines |
| 26 | CHANGELOG must be updated every session, not retroactively |
| 34 | HTMX ignores formaction — use hx_post on each button |
| 35 | toggle @checked modifies HTML attribute, not JS property |
| 39 | Event delegation is the ONLY stable pattern for HTMX apps |
| 40 | Parallel subagents work well for independent DOM fixes |
| 45 | Every identity state must have a defined click behavior |
| 46 | Navigation links must derive section from identity state, not hardcode |
| 57 | FastHTML `cls` is stored as `class` in `.attrs` |
| 62 | Triage by actionability, not chronology |
| 63 | Filters must be preserved across all navigation paths |
| 64 | Toasts inside modals are invisible if z-index is wrong |

## Data Safety & Registries — `tasks/lessons/data-lessons.md`

| # | Summary |
|---|---------|
| 25 | Photo ID schemes must be consistent within lookup systems |
| 29 | Maintain ONE authoritative backlog |
| 36 | get_identity() returns a shallow copy — mutate _identities directly |
| 44 | "Skipped" is a deferral, not a resolution — include in clustering |
| 48 | Route handlers must use canonical save functions, not direct .save() |
| 55 | Crop filename formats differ between legacy and inbox |

## ML & Algorithms — `tasks/lessons/ml-lessons.md`

| # | Summary |
|---|---------|
| 27 | Algorithmic decisions need a structured decision log (AD-XXX format) |
| 28 | Use path-scoped rules for domain-specific context |
| 30 | Path-scoped rules can include future planning awareness |
| 33 | Not every decision needs a formal AD entry |
| 41 | Confidence gap > absolute distance for human decision-making |
| 61 | SKIPPED faces must participate in clustering, not just proposals |
