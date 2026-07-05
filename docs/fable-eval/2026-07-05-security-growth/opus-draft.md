# Opus draft — Fable eval brief (2026-07-05 run: security/spam + multi-Rhodesli growth)

**Role for Fable:** long-horizon ARCHITECT + read-only site/UX EVALUATOR. Hold the whole product
(code + live site + 170 lessons + the owner's chats/goals) in one coherent model and answer ONE
question: **what is the complete, sequenced body of work to make rhodesli genuinely valuable for
OTHER Rhodes-descended families to use — without it becoming spammy?** Everything else is in
service of that.

## This run's trigger (real, live)
The owner opened `/c/fox-family/admin/pending` and found **51 anonymous "Compare Upload" entries**
of random non-heritage faces (selfies). Root-caused in code by the orchestrator: the PUBLIC
`/tools/compare` face-compare tool (`app/compare_routes.py` `/api/compare/upload`) queues every
anonymous comparison into `pending_uploads` as `status:"pending", uploader_email:"unknown"`. It is
rate-limited (20/hr/IP, in-memory), type/size validated, path-traversal-safe, and anonymous uploads
only QUEUE (never enter the archive). No secret is client-reachable except the public PostHog key.
**This is the public tool working as designed — but it is ALSO the exact spam surface every new
community would be sent through.** A separate independent Codex security audit is running; its
verdict feeds the security section. Fable's job is the PRODUCT/architecture consequence: the
boundary between an ephemeral "compare query" and a real "contribution" is a first-class
trust+growth problem.

## What's already true (do NOT re-derive; build on it)
- **Session 169 fable-eval** (3 days ago, `docs/fable-eval/*`) already: (a) shipped QW-1 photos
  fail-closed cross-community leak fix, QW-2 auth rate limits, QW-3 archive-offline cache fix,
  favicon, Postgres-canonical doc rewrites; (b) produced GROWTH_10X.md with 3 sequenced bets —
  **Bet 1** measure+canonical, **Bet 2** trust: visible contribution status + notify, **Bet 3**
  self-serve archives. Treat those 3 bets as the STANDING plan; your job is to validate, refine,
  re-sequence given the spam finding, and fill gaps — not restate them.
- **Onboarding is BUILT but dormant:** `app/onboarding_routes.py` (`/create-archive`) gated behind
  `SELF_SERVICE_ARCHIVE_ENABLED` (default OFF). `create_personal_archive()` runs on signup.
- **The real multi-tenant blocker:** `_check_admin` (`app/main.py:1972`) checks a GLOBAL
  `ADMIN_EMAILS` list → a new archive owner can SEE their archive but cannot upload/triage it
  (WORKSPACE-006). This is the single gate on Bet 3.
- **The only real external tester (Claude Benatar) churned on silent trust failures**, not missing
  features (Session 169 W3/W4). Retention/trust > features.

## Workstreams for Fable (read-only; cap each; highest-Fable-value first)
- **W-SPAM (new, top):** Design the ephemeral-vs-contribution boundary. Options to evaluate with
  tradeoffs: (a) don't persist anonymous compare uploads to the contribution queue at all; (b)
  separate "compare queries" table/queue from "contributions"; (c) require login OR captcha to
  upload; (d) auto-expire anonymous compare uploads after N days; (e) content-moderation gate before
  an anonymous image is stored to R2 / shown in admin UI. Recommend ONE default + a migration note.
  Tie explicitly to the multi-community invite: what MUST exist before a stranger's front-door
  upload is safe (abuse, content-liability, storage cost, admin review burden).
- **W-MULTITENANT:** Read-only assessment of true multi-community readiness. Grep `/c/<slug>/`,
  CommunityMiddleware, community_id scoping, WORKSPACE-006. Enumerate exactly what breaks when a 2nd
  unrelated family signs up. Produce the concrete gap list + the minimum safe path to flip
  `SELF_SERVICE_ARCHIVE_ENABLED` ON (concierge-pilot posture, not public launch).
- **W-UX (vision-QA, your unique strength):** Evaluate the live site at real desktop + mobile
  viewports THROUGH THE EYES OF A NEW RHODES FAMILY who has never seen it. Landing, /tools/compare,
  a person page, the share preview, help-identify, the growth loop (find→share→recognize→contribute).
  Where does a newcomer get confused, distrust it, or hit a dead end? Screenshot-grounded findings
  with code linkage. (Mobile especially — FB traffic is mobile; app was historically "almost
  unusable" on mobile.)
- **W-TRUST:** Validate/refine Bet 2 (visible contribution status + notify). Is the silent-failure
  class still live in code? What's the smallest slice that makes an anonymous contributor trust that
  their submission was received?
- **W-ROADMAP (the deliverable):** Produce THE sequenced plan: "everything I'd need to make this
  valuable for other Rhodeslis, non-spammy." Ordered, each item with why-it-blocks-growth, rough
  size (S/M/L), acceptance criterion, and dependency. This is what the owner asked for verbatim.
  Separate: (i) do-first safety/spam, (ii) trust/retention, (iii) multi-tenant enablement,
  (iv) polish/SEO. Mark which are already-built-just-needs-enabling vs net-new.

## Exclusion list (read-only eval; write into Fable's brief)
Prod-data mutation · schema/migrations · paid-API spend ( cap this run) · global head/nav/CSS ·
`.claude/` + `~/.claude` edits · frozen files (`core/neighbors.py`, `core/pfe.py`, `data/*`) ·
source-code implementation + commits (that's the SEPARATE gated Phase 2). Browser automation on prod
is READ-ONLY (screenshots/reads only — Lesson 149).

## Output contract (Fable writes to docs/fable-eval/2026-07-05-security-growth/)
SPAM_BOUNDARY_DESIGN.md · MULTITENANT_READINESS.md · UX_NEWCOMER_AUDIT.md (screenshot-grounded) ·
GROWTH_ROADMAP.md (THE sequenced deliverable) · EVALS.md (Fable-leveraged value scorecard).
Use bounded subagents for dives (each → subagents/<scope>.md); synthesize. Verify claims against
tool results; do not trust counts in this brief — re-verify. No fabricated status.
