# Lessons Learned

**READ THIS FILE AT THE START OF EVERY SESSION.**

138 lessons across 6 topic files. Each lesson has a Mistake/Rule/Prevention structure.
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
| 79 | NEVER use manual patch.start()/patch.stop() without try/finally — use ExitStack |
| 80 | Always run tests in venv — `source venv/bin/activate && pytest` |
| 134 | Data integrity CI test needed for CONFIRMED identity face references |

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
| 78 | **Production-local data divergence is the #1 recurring deployment failure** |
| 85 | **Deploy data safety gate — 5th occurrence, triple protection (AD-134)** |
| 94 | **Wait for deploy completion before Chrome verification — 502 corrupts JS state** |
| 117 | **Railway region deprecation silently breaks GitHub deploys — use CLI deploy workaround** |
| 133 | **Supabase/Postgres DATA_SOURCE fallback masks real connection failures** |
| 139 | Supabase free-tier egress is dominated by TTL cache reloads, not user traffic |
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
| 81 | Separate /facecompare from /compare: "front door for strangers" vs "tool for residents" |
| 82 | Community-agnostic language in ML tools enables future expansion to other archives |
| 83 | FastHTML FT elements: use repr() not str() to get full HTML for testing |
| 84 | Museum-quality design for ML demos — editorial feel beats developer utility |
| 90 | Script tags inside `<details>` elements don't execute reliably |
| 91 | Leaflet CDN loading requires polling, not DOMContentLoaded |
| 92 | Subtree computation must include ALL photo people, even disconnected ones |
| 93 | Verify API response data matches what the JS consumer expects |
| 95 | Stale JS closure state after fetch failures — fresh page navigation required |
| 106 | **Over-limit docs must be SPLIT into sub-files, not trimmed — never lose context** |

## Data Safety & Registries — `tasks/lessons/data-lessons.md`

| # | Summary |
|---|---------|
| 25 | Photo ID schemes must be consistent within lookup systems |
| 29 | Maintain ONE authoritative backlog |
| 36 | get_identity() returns a shallow copy — mutate _identities directly |
| 44 | "Skipped" is a deferral, not a resolution — include in clustering |
| 48 | Route handlers must use canonical save functions, not direct .save() |
| 55 | Crop filename formats differ between legacy and inbox |
| 104 | **Batch script outputs must write to the SAME data structure the app reads** |
| 105 | **Supabase sync functions must match actual table schema — mock tests don't catch column mismatches** |
| 116 | **Sidebar counts and API endpoints must read from the SAME data sources** |
| 118 | **Ingest pipeline must ALWAYS set upload_date — CLI and web paths both missed it** |
| 119 | **Merge must deduplicate faces across anchor AND candidate lists — cross-list duplicates slip through** |
| 120 | **Data integrity audit must run after every ingest and before every deploy** |
| 121 | **Batch orphan detection must be batch-wide, not per-file — per-file misses cross-file grouping gaps** |
| 122 | **Canonical registry records must define face existence — derivative artifacts can degrade UI but not erase faces** |
| 123 | **Additive-only shadow sync is not reconciliation — stale rows must be detected and pruned safely** |
| 124 | **Production data repairs need machine-readable unwind artifacts before cleanup** |
| 125 | **Exact archive timestamp ties need a deterministic archival tie-break** |
| 126 | **Admin empty states must preserve first-run ML entry points** |
| 127 | **File-only audit trails are not enough for archival mutation history** |
| 128 | **`user_source` is provenance class, not actor identity** |
| 129 | **Mirrored list builders must share the same metadata contract** |
| 130 | **Request-path GEDCOM search must never full-scan a versioned rich mirror** |
| 131 | **Never claim fixed without production browser verification** |
| 132 | **Confirmed identity workflow needs visual verification gate** |
| 135 | **Notification infrastructure that's never called is the same as no notifications** |
| 136 | **Fire-and-forget Supabase syncs with `except: pass` create invisible data loss** |
| 137 | **Proposals must be regenerated after every upload — stale proposals = invisible new faces** |
| 138 | **Features built but never linked from navigation are invisible to users** |

## ML & Algorithms — `tasks/lessons/ml-lessons.md`

| # | Summary |
|---|---------|
| 27 | Algorithmic decisions need a structured decision log (AD-XXX format) |
| 28 | Use path-scoped rules for domain-specific context |
| 30 | Path-scoped rules can include future planning awareness |
| 33 | Not every decision needs a formal AD entry |
| 41 | Confidence gap > absolute distance for human decision-making |
| 61 | SKIPPED faces must participate in clustering, not just proposals |
| 115 | **Single-linkage union-find creates transitive snowball clusters — use complete-linkage** |

## Harness & Process — `tasks/lessons/harness-lessons.md`

| # | Summary |
|---|---------|
| 72 | Context degradation is real (~20-30% drop) — save prompts to disk, re-read at verification |
| 73 | "Data exists in wrong directory" pattern occurred 3 times — verification gate catches this |
| 74 | Self-reported completion unreliable — external verification (FRC) is mandatory |
| 75 | Harness decisions need provenance tracking (HD-NNN) just like algorithmic decisions |
| 76 | Audits can have blind spots — always audit against ACTUAL PROMPT TEXT, not assumed scope |
| 77 | Trimming docs without verifying destination loses context — always confirm target file has the data before removing |
| 86 | Context overflow in long sessions — subagent results flood orchestrator, need context budget estimation |
| 87 | Subagent commit discipline — every subagent MUST run tests AND commit ALL files before completing |
| 88 | Monolithic app files prevent parallel worktree execution — Tracks touching app/main.py must be sequential |
| 89 | **/clear between acts — REPEAT OFFENDER (Sessions 80+89). Behavioral instructions insufficient.** |
| 96 | Multi-layered rendering pipeline bugs require iterative fix-verify cycles |
| 97 | **Self-assessment must include visual verification evidence — "PASS" without screenshots is theater** |
| 98 | **UUID/ID fields must be validated before write — truncated IDs cause silent cascade failures** |
| 99 | **Session log + INDEX.md update must happen atomically with session completion** |
| 100 | **Planning sessions must create context/prompt/log files BEFORE implementation** |
| 101 | **Subagent work MUST be browser-verified before declaring PASS** |
| 102 | **Behavioral instructions are insufficient — only mechanical enforcement works (Lesson 89 violated twice)** |
| 103 | **Behavioral enforcement failed THREE times — hard block hooks now exit 2 at 3+ commits** |
| 107 | **Session prep must persist all research before writing prompts — prompt is last artifact, not first** |
| 108 | **Performance filters must preserve cross-community matching — never filter confirmed_list by community** |
| 109 | **CommunityMiddleware /api/ skip creates dual-path problem — HTMX URLs must include /c/ prefix** |
| 110 | **Existing data not surfaced is worse than missing data — pipeline output must be UI-verified same session** |
| 111 | **Postgres registry needs TTL cache — reloading 2533 identities per request causes complete feature failure** |
| 112 | **Community-scoped pages must filter ALL sections — GEDCOM triage showed Rhodes people on Fox Family page** |
| 113 | **Cross-community badge must check BOTH communities — identity in both should show no badge, not wrong badge** |
| 114 | **os.getenv("DATA_DIR") ≠ core.config.DATA_DIR on Railway — STORAGE_DIR derivation only in config.py** |
