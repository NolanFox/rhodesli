# W5 — 10x Growth: Three Compounding Bets (ranked decision)

**Synthesis of** `subagents/w5-growth.md` (full six-avenue evidence base there). The brief asked
for a decision, not a survey. Below are **exactly 3 bets, sequenced so each de-risks the next**:
measure → convert/retain → expand supply. The unifying insight from the evidence: rhodesli's
top-of-funnel (share → preview → browse) is solid, but **the conversion step is invisible and
unmeasured, and the retention step barely exists** — and the one real community tester (Claude
Benatar) churned on *silent trust failures*, not missing features. So we fix measurement + trust
before opening the doors wider.

## Why these three (and the sequencing logic)
- **Measurement (B) blocks honest evaluation of everything** — every PRD-036 success metric is
  currently uncomputable; any bet shipped without it is judged on anecdotes.
- **Trust/retention (E+F) is what the sole real user's churn history actually demands**, and its
  "visible" slice doubles as an engagement feature (notify → return visit).
- **Self-service archives (A) is the founder's north star and the only path to Avenue C's network
  effect** — but it lands on the repo's most-scarred surface (data integrity + upload + Supabase
  limits) and needs the first non-admin write path. Sequenced last, gated behind B+E.
- Rejected as standalone bets: **Cross-community discovery (C)** — worthless until A produces
  communities Nolan doesn't own (folded into Bet 3 as a cheap credibility demo); **rhodes-wiki (D)**
  — highest per-unit cost + TOS/privacy gates + cross-repo friction (compelling but not a *this-quarter*
  10x lever).

---

## BET 1 — Make the growth loop measurable + finish shareability (Avenue B)
**Problem:** PostHog is wired server-side but there is no funnel dashboard — nobody can answer "how
many FB clicks became identifications." A canonical-URL bug (CANONICAL-COMMUNITY-URL-168) lets
search engines index non-Rhodes content under Rhodes URLs, undermining the SEO compounding the
1,267-URL sitemap seeds.
**User flow:** FB member clicks a shared photo → (instrumented) lands → browses → (instrumented)
submits an ID → each step emits a PostHog event; Nolan sees a funnel + share/identify dashboard.
**Acceptance criteria:** (1) canonical tags on `/c/<slug>/` pages include the community prefix and
match `og:url`; (2) PostHog events fire for share-click, page-view-from-share, identify-submit, with
a documented event dictionary; (3) a minimal funnel view (even a saved PostHog insight) exists.
**Risk gates:** no PII in event payloads (privacy-redactor mindset); canonical fix browser-verified
across desktop+mobile on ≥3 community pages (the exact whack-a-mole class of Lesson 109).
**Kill criteria:** if canonical + events ship but 30 days of data show <10 share-originated sessions,
distribution (not the loop) is the bottleneck — stop optimizing the loop, pivot to Bet 3/rhodes-wiki.
**Success metric:** a share→identify conversion rate is computable and baselined within 2 weeks.
**Effort:** ~1.5 sessions (canonical ~0.5 + events/dashboard ~1). **First slice:** the canonical fix
(`fast_app(canonical=False)` + one line in `og_tags()`) + share-click + identify-submit events.

## BET 2 — Close the silent-failure gap: visible contribution status + notify (Avenues E + F)
**Problem:** The single real community tester hit **three consecutive silent failures** (Help
Identify swallowed her submission; the name form couldn't set a display name; Compare 404'd after
5 green checks). Anonymous identify-submissions work but give **zero feedback** — no status, no
"we'll email you," no contribution history. Nothing kills a 2,000-member community's willingness to
contribute like a submission that vanishes. (Note: W3/W4 found live descendants — S-V4 silently
loses person comments; VD-1/VD-2 silently revert writes — so this is code-real, not just UX.)
**User flow:** anonymous visitor recognizes a face → submits with an optional email → immediately
sees "Thanks — your suggestion is pending review" with a cookie-keyed `/my-contributions` page → gets
a Resend email when Nolan approves/responds → returns.
**Acceptance criteria:** (1) every identify/annotation submission persists a visible status the
contributor can re-check; (2) submission never silently fails — a write error surfaces to the user
(directly addresses W3 VD-1/VD-2 + W4 S-V4); (3) email-on-review fires via the already-wired Resend;
(4) anonymous session-ID tracking (WORKSPACE-004) links contributions without forcing signup.
**Risk gates:** rate-limit + input caps on the public write path FIRST (W4 A-RF1 — currently
uncapped); admin review-burden stays bounded (Nolan is sole reviewer); mobile-verified (FB traffic
is mobile; app was "almost unusable" on mobile per memory).
**Kill criteria:** if, after shipping, the review-queue backlog grows faster than Nolan can clear it
(sole-reviewer bottleneck) with no lift in repeat contributions, the constraint is moderation
capacity, not feedback — build lightweight moderation before pushing contribution volume.
**Success metric:** repeat-contribution rate > 0 and "submissions that reach admin review / total
submissions" = 100% (no silent drops), measured via Bet 1's instrumentation.
**Effort:** ~2 sessions (WORKSPACE-004 is "1 session, no deps" per PRD-036; notify loop ~0.5-1).
**First slice:** submission-status persistence + "we'll email you when reviewed" on `/help` + a
cookie-keyed `/my-contributions` page.

## BET 3 — Self-service archives, done without a dead-end (Avenue A, unlocks C)
**Problem:** The create-archive flow is fully built but dormant (`SELF_SERVICE_ARCHIVE_ENABLED` OFF)
because of one honest blocker: `_check_admin` checks a **global** list, so a new archive owner can
*see* their archive but **cannot upload to or triage it** (D4 / WORKSPACE-006). Flipping the flag
today ships create → empty dashboard → stuck. Done right, this is the founder's north star and the
only path to Avenue C's network effect (archives × shared people).
**User flow:** logged-in user clicks "Create your archive" → names it → gets an owner-scoped
dashboard → uploads + triages *their own* archive → (later) a public badge shows when their people
also appear in Rhodes.
**Acceptance criteria:** (1) WORKSPACE-006 owner-scoped permissions on upload+triage routes (the
first non-admin write path — must pass the `route-safety-audit` gates: auth + community-scoping +
fail-closed); (2) upload pipeline verified end-to-end for a non-admin (it has broken 6× for the ONE
existing contributor); (3) flag ON + a CTA on `/` and `/tools`; (4) as a cheap credibility demo,
COMMUNITY-004 public "also appears in N archives" badge cross-linking Rhodes↔Fox.
**Risk gates (hard — this is the repo's scarred surface):** every write route passes the
data-integrity + route-safety skill gates; a **concierge pilot with one real family** (Fader/Benatar
relatives) before any public announcement; Supabase headroom checked (Lesson 200 — DB-size took the
site down twice in June); the W3 VD-1/VD-2/R-1 write-failure-visibility fixes land FIRST so a
stranger's upload can't silently vanish.
**Kill criteria:** if the concierge pilot's one family uploads photos and, after 30 days, produces
zero community engagement (the "empty-room problem"), self-serve archives don't retain — stop before
public launch and refocus on Rhodes depth + rhodes-wiki supply.
**Success metric:** ≥1 non-Nolan-owned archive with ≥1 non-owner identification within 60 days of the
concierge pilot.
**Effort:** ~3 sessions (WORKSPACE-006 2 + flag/CTA/upload-verify 1), + ~1 for the C badge.
**First slice:** WORKSPACE-006 owner-scoped permissions on upload+triage, verified via the
`route-safety-audit` skill, with the flag still OFF.

---

## Compounding dependency chain
```
BET 1 (measure + canonical)  →  makes BET 2 and BET 3 evaluable, fixes SEO compounding
BET 2 (trust: status+notify) →  fixes the churn class; safe precondition for strangers writing (BET 3)
BET 3 (self-serve archives)  →  produces non-Nolan communities → unlocks Avenue C network effect
```
Each bet is shippable on its own and de-risks the next. If the run is cut short, **Bet 1's canonical
fix + two events is the single highest-ROI half-session** — it costs almost nothing and makes every
future growth decision data-driven instead of anecdotal.
