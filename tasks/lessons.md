# Lessons Learned

**READ THIS FILE AT THE START OF EVERY SESSION.**

170 lessons across 6 topic files. Each lesson has a Mistake/Rule/Prevention structure.
Detailed content is in `tasks/lessons/` — this file is the index.

---

## REPEAT-OFFENDER FAILURE MODES (read these FIRST)

These patterns have each recurred 3+ times despite individual lessons. The
original lessons are preserved for audit trail but the consolidated pattern
is what you need to internalize.

| Pattern | Occurrences | Canonical lessons | Structural fix |
|---------|-------------|-------------------|----------------|
| **Local↔production data divergence** (split-brain) | 9 | 78, 144, 147, 150, 153 | Supabase single source of truth (AD-135, in progress) |
| **Production-origin files re-added to deploy sync** | 6 | 56, 69, 78, 85, 141 | .gitignore allowlist + AD-134 safety gate |
| **Silent Supabase writes with `except: pass`** | 3 | 123, 136, 153 | Remove fire-and-forget; surface all write failures |
| **Schema drift between code and live Supabase tables** | 3 | 105, 134, 152 | Integration tests against live schema (mock tests insufficient) |
| **Post-write data verification missing (orphans)** | 3 | 145, 146, 154 | Post-mutation integrity checks; structural tests |
| **Batch script outputs don't reach production read path** | 3 | 160, 161, 162 | Pre-flight: verify logging, enrichment, write target before bulk run |
| **Heavy Supabase migrations stall on pooler / OOM** | 3 | 163, 165, 183 | Chunked-write template (≤10K rows per iteration; upsert immediately; never accumulate full dataset). Pre-flight pooler health probe. |
| **Behavioral rules that must be hooks** | 4 | 89, 102, 103, 140, 143 | Transcript-based detection (HD-032); exit 2 to block |
| **Worktree agents don't commit before returning** | 2 | 87, 166, 167 | Orchestrator verifies `git status --porcelain` clean post-return |
| **Non-atomic batch imports leave orphan rows on failure** | 1 (huge) | 199 | Bulk imports MUST be one transaction; failed import = zero rows; structural test proves it |

When you're about to do work adjacent to any of these categories, re-read the
canonical lessons. These are not one-off mistakes — they are structural failure
modes the codebase keeps regenerating.

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
| 145 | photo_faces table must be written alongside photos — READ path queries it, WRITE path must populate it |

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
| 159 | **ALWAYS verify deploy health before ending a session — failed deploy left site down overnight (Session 142)** |
| 160 | **Batch scripts must verify logging on first call — 79 Gemini calls went unlogged to Supabase (Session 142)** |
| 161 | **Batch API calls: verify FULL output quality on first call, not just success — 82 photos ran without GEDCOM context (Session 142)** |
| 162 | **Batch scripts MUST write to Supabase (source of truth), not just local JSON — 84 labels invisible in production for 20h (Session 142)** |
| 163 | **GEDCOM versioned importer doesn't scale to 175K+ rows — change_log crashes, unchanged rows lost on finalize (Session 144)** |
| 164 | **datetime objects from direct DB reads must be serialized before Supabase REST API (Session 144)** |
| 165 | **Supabase views with IS NULL clause include unversioned legacy rows — broke GEDCOM context for ALL batch photos (Session 144)** |
| 183 | **Supabase pooler unreliable for long server-side cursor reads — chunked-write (read+aggregate+upsert one chunk at a time, never accumulate full dataset in memory) is the only reliable pattern for ≥50K-row migrations. Session 158 lost the cutover day after 4 different load approaches all failed (cursor died mid-stream, NULL chunk failed all retries, version_map query failed under pooler degradation, REST accumulator plateaued at 951 MB). See also Lesson 173 (REST `.range()` default page).** |
| 184 | **Zombie idle-in-transaction backends survive client disconnects — Session 158d found 16 backends from 158b's failed cursor backfill idle for 22h holding AccessShareLock. Pre-DDL gate must scan `pg_stat_activity` for old idle-in-transaction sessions; long cursor scripts must set `idle_in_transaction_session_timeout='5min'`.** |
| 185 | **`pg_terminate_backend` on a hot production pool cascades into worker crashes — Session 158d killed 16 zombies, RENAME succeeded, then production went 502 with `x-railway-fallback: true`. Workers held aliases to terminated backends → query failures → crashes → Railway restart loop. Mitigation: redeploy first OR maintenance window; never terminate connections during live traffic.** |
| 186 | **Supabase PostgREST schema cache can get stuck after RENAME + ROLLBACK — Session 158d post-rollback REST returned `PGRST002: Could not query the database for the schema cache` on 3/3 trials across `identities` and `date_labels`. App startup, deploy healthchecks, and cutover scripts ALL depend on REST. `NOTIFY pgrst, 'reload schema'` from psycopg2 did NOT recover it. Fix: restart Supabase PostgREST via dashboard (Settings → API → Restart, or Project → Pause+Resume). Pre-DDL checklist: be ready to dashboard-restart Supabase if PGRST002 appears post-cutover.** |

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
| 141 | **Never git-add production-origin data files — 6th occurrence of deploy-overwrite pattern (Lessons 56→69→78→85→141)** |
| 142 | **Supabase JSONB columns can silently store string-encoded arrays — guard reads AND writes** |
| 144 | **DATA_SOURCE split-brain — ingest writes JSON, production reads Supabase, photos vanish** |
| 146 | **Upload pipeline creates orphaned faces — post-sync identity verification missing** |
| 147 | **Local-production data divergence — 7th occurrence, embeddings sync-back missing** |
| 149 | **NEVER click action buttons on production — browser automation is READ-ONLY. Session 111d: clicked Merge, corrupted two identities** |
| 150 | **Three-source data (local JSON, Railway volume, Supabase) causes recurring split-brain — 8th occurrence. Direct Supabase fix doesn't update Railway volume cache. Need single source of truth.** |
| 151 | **Never cache failure states that disable security/scoping boundaries — cached None for 120s leaked cross-community data** |
| 152 | **Deployed Supabase queries must match actual schema — mock tests don't catch column mismatches (see also 105)** |
| 153 | **Legacy data layers that "just sync" WILL silently corrupt production — 9th occurrence. identity_overrides overwrote correct anchor_ids with stale snapshots for 4 days. 36 faces lost. Fix: structural tests that fail if ANY override layer is re-introduced** |
| 154 | **Merge face transfer must be verified post-write — 10th data integrity occurrence. 175 faces orphaned across 18 identities. Merged sources hidden but faces never transferred to targets. Post-merge verification + structural tests added** |
| 155 | **Data repair scripts must snapshot before EACH step — un-merging created 692 secondary multi-claimed faces requiring a 7th fix step** |
| 156 | **Database mutations need comprehensive audit trail — 11th data integrity occurrence, 691 dangling merges untraceable** |
| 168 | **Automated side effects of admin actions must be audited and guarded — upload rejection silently auto-rejected Person 82863849 (Session 148)** |

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
| 171 | **Genealogical name collisions are common — always verify with primary sources (death certificates, cemetery records), not other Ancestry trees. "Abe Fader" (d.1958) was a different person from Abraham "Al" Fader (d.1984). Cascading error temporarily reversed entire identification hypothesis (Session 148c)** |
| 172 | **Embedding kinship distance is a WEAK identification signal (0.09 gap mother vs non-blood). Event context (corsage, aisle walk, dance partners) is the STRONGEST signal. Cross-collection similarity is useless for in-laws (Session 148c)** |

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
| 140 | **Hooks that exit 0 are advisory only — Claude ignores warnings, must exit 2 to block** |
| 143 | **Hook audit must be exhaustive — partial fixes create false confidence** |
| 148 | **25 commits never pushed — every session must verify git log origin/main..HEAD is empty** |
| 166 | **Worktree agents must commit before returning — uncommitted changes require manual recovery** |
| 167 | **Git lock contention when launching 3+ worktree agents simultaneously — stagger or retry** |
| 169 | **Memory files (~/.claude/projects/) live outside git — must be backed up to .claude/memory_backup/ (Session 148)** |
| 170 | **Fix scripts must write to Supabase (production data store), not just local JSON — Session 147 "fix" never reached production** |
| 173 | **Supabase REST `select(...).execute()` defaults to 1000-row pages — for tables ≥1000 rows you MUST `.range(offset, offset+999)` in a loop or you'll silently process only the first page. Session 154 `resolve_gedcom_context` returned empty for confirmed identities because the `identities` table has 4111 rows and the first 1000 didn't include Albert Fox.** |
| 174 | **Sycophancy guards in retry prompts need teeth — "name a positive supporting feature" is too easy to confabulate around. Require the supporting feature to be a NAMED GEDCOM event (subject + event type + date + place verbatim) or a NAMED visual diagnostic. Session 154 AD-242's CONFIRM path raised confidence on the WRONG NYC answer for photo 02068 from medium→high.** |
| 175 | **Direct Supabase Postgres hostnames (`db.<project_ref>.supabase.co`) are IPv6-only and may be unreachable from many networks. Always use the pooler (`aws-0-<region>.pooler.supabase.com:6543`, username `postgres.<project_ref>`). The pooler region for project `fvynibivlphxwfowzkjl` is us-west-2. Session 154 migration application path.** |
| 176 | **`scripts/merge.sh` silently puts merge commits on the wrong branch when invoked from a worktree cwd. The `git checkout main && git pull origin main 2>/dev/null \|\| true` chain swallows the checkout failure (worktree can't checkout a branch already checked out elsewhere). Session 154 hit this; recovered via reset + re-merge from the primary worktree cwd. The script needs `[ "$(git rev-parse --git-common-dir)" = ".git" ]` pre-check that exits non-zero.** |
| 177 | **`pre-work-clear-gate.sh` allowlist must match actual repo paths, not assumed paths. Session 154 found `$REPO/BACKLOG.md` allowlisted but the actual file is `$REPO/docs/BACKLOG.md` — same gap for `tasks/lessons.md` and `docs/prompts/`. Add a structural test that asserts every session-end artifact path from `session-defaults.md` resolves to an allowlisted entry.** |
| 178 | **Subagent token-budget hazard for multi-phase tasks: Session 154 Track E subagent received 4 phases (E0.5 + E1 + E3 + E4) and ran out of usage tokens at phase 4 (PRD-063 design — the deliverable the user most wanted). Plan token budgets per subagent like time budgets. For a 4-phase task with one large design phase, dispatch as 2 subagents (analysis-track + design-track) instead of one.** |
| 179 | **Identity notes silently dropped via Supabase round-trip since Session 105. `registry.add_note()` writes top-level `identity["notes"]` but `shadow_write_identity` only persisted the `metadata` JSONB column — top-level "notes" key fell through. Every `add_note` call between Sessions 105-156 lost its note on next page render after in-memory cache TTL expired. Session 156 fix: round-trip notes through `metadata.notes` (4 regression tests). Lesson: any field added to in-memory identity dict that isn't explicitly mapped in shadow_write will silently fail to persist with DATA_SOURCE=postgres. Add a structural test that asserts every top-level key on the in-memory identity dict either has an explicit Supabase column OR is preserved inside metadata JSONB.** |
| 180 | **`Agent({isolation: "worktree"})` does NOT isolate filesystem writes when the agent uses absolute paths. Session 156 Track B subagent wrote files to `/Users/nolanfox/rhodesli/scripts/...` (main repo) instead of the worktree at `.claude/worktrees/agent-.../scripts/...`. Files ALSO landed in worktree branch via copy, but pre-merge cleanup of the main-repo untracked duplicates was required. If the worktree-branch and main-untracked versions had differed, we'd have silently committed the wrong version on merge. Mitigation: agent prompts should explicitly require relative paths; harness merge step should warn when files were both untracked-in-main AND in-worktree-commit before letting the merge succeed.** |
| 181 | **GitHub Actions secrets are completely separate from local `.env`. Even when CI workflow YAML correctly references `${{ secrets.X }}`, the secrets won't be set unless someone has manually pasted them in the GitHub web UI OR run `gh secret set X --body "$X" -R repo` from CLI. Session 156 found `total_count: 0` after user said "yes I pasted them" — they hadn't actually clicked save. Confirm via `gh api repos/<owner>/<repo>/actions/secrets` before assuming. Automation: `gh secret set` from sourced `.env` is one command per secret; do this rather than walking users through the web UI.** |
| 182 | **Pre-flight budget canary before parallel subagents — Session 157 lost both Track A subagents to Anthropic's user-level usage limit at launch (returned within 5-10s, 0-2 tokens consumed each, no commits). Failure mode is invisible: agents return cleanly with empty work products. Rule: launch ONE canary first, verify wall-clock ≥30s AND tokens ≥100, only then launch the second in parallel. Subagent prompts must include "On budget exhaustion" instructing honest stop-and-report. Session 157b confirmed the pattern works.** |
| 187 | **PGRST002 schema-cache failure can also be Disk-IO budget exhaustion (refines L186) — Session 158e: dashboard "depleting Disk IO Budget" banner is the ROOT CAUSE; `NOTIFY pgrst` cannot recover it. Fix is to relieve disk pressure (cutover DROP+VACUUM in this case). After 1.3 GB freed, schema cache self-recovered without restart. Always check Supabase dashboard banner FIRST when PGRST002 appears.** |
| 188 | **Cutover scripts must scan `pg_depend` for view dependents BEFORE DROP — Session 158e: `current_gedcom_families` view auto-followed table RENAME (oid-tracked, not text-tracked), blocking DROP TABLE. The `cutover_forward()` had `DROP VIEW IF EXISTS current_gedcom_individuals` but missed the paired families view. Add `pre_drop_dependency_scan()` helper for any cutover-style script.** |
| 189 | **`SUPABASE_ACCESS_TOKEN` (Management API personal access token, sbp_...) needed in .env at project setup, not when broken — Session 158e: PostgREST recovery via Management API needed the token, but it wasn't in .env. User had to generate mid-incident, and the previously generated token was orphaned (Supabase shows value only once). Adds 5-10 min of incident time at the worst possible moment. Generation URL: https://supabase.com/dashboard/account/tokens** |
| 190 | **When production is already 5xx pre-cutover, the cutover IS the fix — don't rollback because of the same 5xx (Session 158e). The "any 5xx → rollback" rule applies only when the cutover *changes* the status from 200 → 5xx. If production is already 502 from a separate root cause that the cutover is designed to address, rolling back locks in the failure. Always capture baseline /health status before cutover and write the abort criteria around the *delta*.** |
| 191 | **Chrome MCP `read_page` returns accessibility tree, NOT raw HTML — Session 160 spent ~2 hours assuming the Session 159 HTML-driven parser pipeline (`extract_fb_post.py` → BeautifulSoup `parse_fb_dom.py`) would consume MCP capture output. It can't. The two valid paths are: (a) save raw HTML out-of-band and feed the HTML parser, OR (b) use `javascript_tool` for structured extraction and a separate inbox builder. rhodes-wiki Session 160 added the second path via `scripts/build_inbox_from_js_extraction.py`. ARCHITECTURE.md §4.1 now documents both. When designing capture-driven systems, verify what your capture primitive actually returns before designing the parser.** |
| 192 | **FB renders post DOM TWICE — once in the modal overlay, once in the underlying feed — when a post URL opens via permalink. JS extraction picks up BOTH, causing every text node to appear doubled (`"X\nX"` form). Always dedupe with a half-mirror check (`text[:n//2] == text[n//2:]`) before persisting comment/caption text. See `scripts/build_inbox_from_js_extraction.py:_dedupe_doubled_text`.** |
| 193 | **Chrome MCP's "Sensitive key" gate over-blocks name fields — Session 160's javascript_tool extraction lost all author_name / fb_id / fb_profile_url fields to MCP's CSRF-token redactor when the values matched its "looks like a session token" heuristic. Workaround: base64-encoding the value ALSO trips the gate (looks like an opaque token). Real workaround: extract names via a SECOND channel (`read_page` accessibility tree) and merge by comment_id. Or: use indirect references (just return FB user IDs from JS, look up names from the read_page output Claude already has).** |
| 194 | **Chrome MCP per-action permission popup on facebook.com fires PER call — Session 160 user got 4-5 popups before frustration. Each `javascript_tool` invocation is treated as a fresh risky action regardless of previous approval. Mitigation: write ONE comprehensive JS extractor that does scroll + extract + sanitize + return in a single call. Plan extraction passes like database transactions — minimize round trips. Session 160's final extractor returned 12 comments + caption + reactions + image metadata in one call.** |
| 195 | **Comments are PRIMARY genealogical source material in Rhodes-Sephardi FB groups, not metadata. Session 160 captured 14 comments on a single post and surfaced via NER: Renee's maiden name (Surmany), her mother's name (Sarah Surmany), four Menasche siblings (Edward + Renee her wife + Simon + Lionel her brothers-in-law per Henry Tarica's neighbor recollection), Rachel/Nathanel Menashe (Edward's relatives), Diana Amato Merdjan (cross-family marriage), Sephardi Shul institutional context, Camillo (community member), April Merdjan's offer of "I have quite a few of them also" (follow-up lead). PERSON-MATCH-001 must NER all comments, not just caption. Treat comments as tier-3-secondary primary sources.** |
| 196 | **JS extraction's `[role=article][aria-label^="Comment by"]` selector misses nested replies — Session 160 captured 12 of 14 comments from Martha Girgenti's FB post; the 2 nested replies (Martha Girgenti's "more digging" reply to David Zen Amoils, Isaac Menashe's "Indeed!" reply to April Merdjan) were structurally outside the top-level article elements. The `depth` calculation via parent-walk returned 0 for everything. Future fix: detect nested replies via `aria-label^="Reply by"` OR by walking sibling articles within an indented container. For Session 160, the 2 missing replies were filled in from user screenshot verification.** |
| 197 | **Living-person dossiers need `living: true` flag in addition to `audience: private` — Session 160 created a person.md for Zeni Menasche (alive in 2026 per Esther Salzman comment "Love to Zeni"). The default `audience: private` gates publish-time redactor, but the `living: true` flag is a SECOND signal that any future move to `audience: public` requires consent OR confirmed-deceased citation. Add to template frontmatter; redactor should refuse to publish ANY dossier with `living: true` regardless of audience field.** |
| 198 | **Partial indexes are silently defeated by `OR <pred> IS NULL` clauses on the indexed column — Session 162 found `current_gedcom_relationships` view filtering `WHERE is_current = true OR is_current IS NULL` against a partial index `WHERE (is_current = true)`. Postgres' planner cannot use the partial index when the WHERE clause includes a predicate the index excludes (NULL rows), so every one of 347,914 calls full-scanned the 872k-row table. Column had 0 NULL values; the defensive clause was over-engineering. Fix in 3 steps: (a) drop `OR ... IS NULL` from the view, (b) ANALYZE to refresh planner stats, (c) SET NOT NULL on the column to structurally prevent re-introduction. Empirical: 754ms → 40.66ms mean (18.6× speedup); sustained disk-read rate 114/sec → 2.7/sec (42× reduction). Codex audit (gpt-5.5/xhigh) ALSO caught two raw-table fallback paths in `app/relationship_routes.py` that re-introduced the same IO leak during PostgREST flake windows — promote raw-table-fallback `is_current` filter check to a Phase 1a-style structural test on any session that adds a partial-index optimization. Whenever you add a partial index, audit all VIEWs + ORM/REST callers that touch the same column and align their WHERE clauses with the index predicate or make the column NOT NULL.** |
| 199 | **Non-atomic batch imports are a bloat factory — Session 163 root-caused a 1.3 GB Supabase DB to the GEDCOM importer committing each entity batch on its own connection (`scripts/import_gedcom_version.py:516`). When a later batch failed, the already-written rows stayed; the version was just marked `failed`. 7 of 9 GEDCOM "versions" were failed retries that each left a full duplicate of ~22K individuals + relationships → ~900 MB of garbage. A test (`test_gedcom_versioning.py:649`) even ASSERTED rows survive a failed import — institutionalizing the bug. Rule: any bulk/multi-entity import MUST be a single transaction (or staging + atomic swap) so failure = ZERO rows. Allocate version numbers + dedup source-hash INSIDE the txn under `pg_advisory_xact_lock` (MAX+1 races). Add a structural test asserting a failed import leaves zero rows, and NEVER write a test that asserts partial rows survive. Codex (gpt-5.5/xhigh) caught this; PRD-064 fixes it.** |
| 200 | **Supabase Free tier has THREE independent limits that fail differently — disk-IO budget (Lesson 198, Session 162), egress (5 GB), and DB SIZE (500 MB, Session 163). A project paused for inactivity → `NXDOMAIN` on the DB host (`Name or service not known`). A project over DB-size → `402 exceed_db_size_quota` on REST/Auth services while the `db` service stays healthy (so the app shows empty data, not an error page). CRITICAL: reducing DB size mid-cycle does NOT lift a Fair-Use restriction — it lifts ONLY via plan upgrade (immediate) or the next billing-cycle reset. "Downgrade to Free" is safe ONLY if DB SIZE < 500 MB — never conflate egress/IO reductions with size (the `project_supabase_egress` memory made exactly this error). Management API SQL endpoint (`POST /v1/projects/{ref}/database/query`) and pooler session-mode (5432) keep working even under a 402 restriction, so cleanup is possible without upgrading; but the public REST API stays 402 until upgrade or reset. Recovery levers: `POST /v1/projects/{ref}/restore` (unpause), pause→resume cycle (does NOT clear a size Fair-Use flag). Prevention: monitor `/health` `supabase` field + Management-API project status; add a keep-alive to prevent inactivity auto-pause; keep DB comfortably < 500 MB with headroom, not at 92%.** |
| 201 | **Versioned-mirror row-multiplication can be mostly failed-import noise, not real history — Session 163: `gedcom_versions` had 9 rows but only 2 `applied` (just 2 distinct source hashes); the other 7 were `failed` retries. Before treating per-version row duplication as precious "history," check `status` provenance (applied vs failed) and distinct source hashes. Most of what looked like version history was garbage. Snapshot to R2 first, then it's safe to delete superseded/failed-version rows.** |
