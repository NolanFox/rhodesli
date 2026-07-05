# Fable evaluation brief — rhodesli multi-Rhodesli growth + trust (2026-07-05)

You are Fable, acting as the long-horizon **architect + live-site evaluator** for rhodesli, a
heritage photo archive for the Jewish community of Rhodes (FastHTML + HTMX + Supabase/Postgres +
Cloudflare R2 + Railway + InsightFace + Gemini; live at https://rhodesli.nolanandrewfox.com).
Hold the whole product in one coherent model and answer the owner's real question:

> "I want to make rhodesli genuinely VALUABLE for OTHER Rhodes-descended families to use — but I
> need to make sure it's not spammy to do so. Lay out everything I'd need to get there."

This is an EVALUATION, read-only. You do not write source code, migrate data, or commit. A separate
gated implementation sprint does that later. Your deliverable is judgment + a sequenced plan +
live-site findings only you can produce.

## What is ALREADY settled (do NOT re-investigate — build on it)

**Security question — CLOSED, verified against code by the orchestrator + an independent Codex audit
(`codex-security.md`):**
- The ~51 anonymous "Compare Upload" pending entries are the PUBLIC `/tools/compare` face-compare
  tool working as designed (`app/compare_routes.py:/api/compare/upload` queues anonymous comparisons
  to `pending_uploads` as `status:"pending", uploader_email:"unknown"`). NOT a breach.
- No live API key/secret is browser-reachable (Supabase service-role, R2, Gemini, session secret,
  ML token are all server-side; the only client-exposed key is the PUBLIC PostHog key, which is
  benign). Two REAL but limited findings were verified: (1) a path-traversal guard is missing on
  `/photos/{filename:path}` + `/uploads/facecompare/` (defense-in-depth; on-disk data files only,
  not env vars); (2) a real `ML_SERVICE_TOKEN` value is committed in
  `docs/session_logs/session-116-log.md` (rotate; internal ML service, repo-read-access only).
- These security fixes are for the implementation sprint, not your run. Take them as GIVEN context.

**Two independent draft evaluations agree** (`opus-draft.md`, `codex-draft.md`) on the core thesis —
treat as your evidence base, VERIFY key facts against tool results, do not merely restate:
- rhodesli is community-AWARE (`/c/<slug>/` routing via `CommunityMiddleware` at `app/main.py:755`,
  `photo_communities`/`identity_communities` join tables, fail-closed scoping from Session 169) but
  NOT safe multi-TENANT.
- The blocking gaps for inviting other families:
  1. **Permission model is global-admin only.** `_check_admin` (`app/main.py:1972`) checks a global
     `ADMIN_EMAILS` list — a new archive owner can SEE their archive but cannot upload/triage it
     (WORKSPACE-006, open). This is THE gate.
  2. **Privacy stored but not enforced.** Self-service creates archives with `privacy="unlisted"`
     (`app/onboarding_routes.py:386`) but `CommunityMiddleware` only checks slug existence, and the
     root lists all communities with no privacy filter (`app/page_routes.py:799`). Private archives
     would be publicly discoverable.
  3. **Compare/contribution boundary is conflated.** An ephemeral "compare my face" query becomes a
     durable pending contribution + R2 object. This is the spam source AND the exact public front
     door a new community is sent through.
  4. **Moderation not archive-scoped end-to-end.** Pending metadata uses `community_id` but the admin
     pending page filters by `community` (`app/admin_routes.py:565`); compare-pending entries carry
     no community id. R2 raw uploads use generic `raw_photos/{filename}`, not archive-scoped prefixes.
  5. **No batch-reject + no age-based expiry** for pending spam (only orphan-staging expiry exists).
  6. **Self-service onboarding is BUILT but flag-gated OFF** (`SELF_SERVICE_ARCHIVE_ENABLED`,
     `app/onboarding_routes.py`). Flipping it today ships create → owner can't triage → dead end.
- Both drafts recommend: **concierge pilot with 1-3 known Rhodes families, NOT broad self-service**,
  after defanging compare + adding owner-scoped moderation.

## YOUR differentiated job (what neither the orchestrator nor Codex could do — they only read code)

### 1. LIVE-SITE NEWCOMER VISION-QA (your highest-value work — the owner asked for exactly this)
Visit the LIVE site at real DESKTOP and MOBILE (~390px) viewports, as a Rhodes-descended person who
has NEVER seen it and just clicked a shared Facebook link. Screenshot-ground every finding and link
it to code. Walk the real growth loop: landing → a shared person/photo page → the share preview →
Help-Identify → /tools/compare → browsing People/Photos/Map/Tree. For each screen judge:
- Does a newcomer understand what this is and trust it in the first 30 seconds?
- Where do they get confused, distrust it, hit a dead end, or bounce?
- Is it mobile-usable (FB traffic is mobile; the app was historically "almost unusable" on mobile)?
- Does the find→share→recognize→contribute loop actually close, or does a contribution vanish
  silently (the failure mode that churned the one real external tester)?
Report to `subagents/` per-scope, synthesize into `UX_NEWCOMER_AUDIT.md`. Every finding: screenshot
path + code file:line + severity + the newcomer-impact. Prod browser automation is **READ-ONLY** —
screenshots/reads/navigation ONLY; never click a data-mutating control (Lesson 149).

### 2. THE SPAM/CONTRIBUTION BOUNDARY DESIGN (`SPAM_BOUNDARY_DESIGN.md`)
Recommend ONE default design for separating ephemeral compare queries from real contributions,
with tradeoffs. Cover: should anonymous compare uploads persist at all? captcha (Turnstile) vs
require-login vs ephemeral-by-default? auto-expiry + R2 lifecycle deletion? content-moderation gate
before an anonymous image is stored/shown? admin batch-reject + quarantine? Tie each to the
multi-community invite: what MUST exist before a stranger's front-door upload is safe (abuse,
content-liability, storage cost, admin review burden). Give the recommended default + a migration note.

### 3. MULTI-TENANT READINESS + THE ROADMAP (`MULTITENANT_READINESS.md` + `GROWTH_ROADMAP.md`)
`GROWTH_ROADMAP.md` is THE deliverable the owner asked for: the complete, SEQUENCED body of work to
reach "safe to invite other Rhodeslis, non-spammy." Group into (i) do-first safety/spam, (ii)
trust/retention, (iii) multi-tenant enablement (owner perms + privacy + scoped moderation +
storage), (iv) polish/SEO/measurement. Each item: title · why-it-blocks-growth · rough size (S/M/L)
· acceptance criterion · dependencies · already-built-vs-net-new. End with a concrete phased plan
(what to do in the next few days vs the next few weeks) and a recommended concierge-pilot playbook
(how to safely onboard the FIRST 1-3 families with the flag still mostly off). Refine — do not just
restate — the two drafts' top-10 and 3 bets; where you disagree with them, say so with evidence.

### 4. EVALS scorecard (`EVALS.md`)
Prove your run's Fable-LEVERAGED value: vision-delta (findings a code-only review missed, with
screenshot evidence), history-delta (lesson × current-code connections), roadmap-ambiguity-delta
(ranked plan with kill criteria), long-horizon completion. numerator/denominator + evidence path +
Evidence-backed/Proxy/Unverified label each. Never claim another model "could not" without a comparator.

## Constraints (read-only eval — bake into your own subagent briefs)
EXCLUDED (do not touch): production-data mutation · schema/migrations · paid-API spend ($0 cap this
run — no Gemini calls) · global head/nav/CSS · `.claude/` + `~/.claude` edits · frozen files
(`core/neighbors.py`, `core/pfe.py`, `data/*`) · source-code implementation + commits (separate
gated phase) · ANY data-mutating browser click on prod (READ-ONLY). Use bounded subagents (2-3 file
reads each, context summarized inline) — you are usage-limit fragile on long unbounded runs. Write
incremental artifacts so nothing is lost. Verify counts against tool results; do not trust this
brief's numbers — re-verify. No fabricated status. Write everything to
`docs/fable-eval/2026-07-05-security-growth/` (+ `subagents/`, + `screenshots/`).
