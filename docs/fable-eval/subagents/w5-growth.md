# W5 — Growth Bets: Evidence Base (research only, no ranking)

**Scope:** Evidence for choosing 3 compounding growth bets. Read-only survey of repo docs,
routes, PRDs, and real-user feedback as of 2026-07-02 (v0.99.89, Session 168).
**Author:** research subagent. A senior agent makes the final ranked decision.

---

## 0. The Facebook-group funnel as it exists today

Distribution channel: "Jews of Rhodes" FB group (~2,000 members). Links are hand-posted by
Nolan; there is no automated posting. What a FB member hits, per `app/page_routes.py`:

- **Entry surfaces** (all public, no account needed): `/` community landing (Rhodes-aware,
  cached, featured photos + stats — line 2414), `/photo/{id}` (line 13160, face overlays, OG
  tags, share/download), `/person/{id}` + NEW `/c/<community>/person/{id}/photos` gallery
  (PRD-065, Session 165 — built specifically because shared person links mis-navigated),
  `/help` (line 4742 — top-50 unidentified faces by quality, "the growth loop: visitor →
  recognize face → share → more visitors", community-scoped as of Session 168 G1/G2/G7),
  `/photos`, `/people`, `/collections`, `/map`, `/timeline`, `/tree`, `/tools/*`.
- **What an anonymous visitor can DO**: browse everything public; submit an identification
  via `/api/identify/{person_id}/respond` (line 5472) — `submitted_by = email or "anonymous"`,
  lands in the annotations system for admin review (fixed Session 83a after a **silent-failure**
  bug found by the one real community tester); use Compare/Estimate tools; share (Web Share
  API + clipboard, share_button() on most surfaces). Admins short-circuit to direct rename+confirm.
- **What they CANNOT do**: upload without login (admin-only in practice; contributor upload
  exists but has broken repeatedly — memory: "Upload broken 6 times"), create an archive
  (flag OFF), see cross-community "also appears in" on public pages (COMMUNITY-004 open),
  track their own contributions (no session tracking — WORKSPACE-004 unbuilt).
- **Preview/SEO plumbing** (fresh, Session 168): OG tags community-aware on landing/help/
  photos; og:image on /tools/compare + /tools/estimate; conditional person og:image;
  `/robots.txt` + `/sitemap.xml` (1,267 URLs). **Open holes**: canonical URL bug
  CANONICAL-COMMUNITY-URL-168 (P2 — `/c/<slug>/` pages emit canonical WITHOUT the community
  prefix, contradicting og:url; search engines can index non-Rhodes content under Rhodes URLs).
- **Measurement**: PostHog is wired server-side (`app/main.py:190-196`, Session 92) and
  `log_user_action` exists, but there is **no funnel/analytics dashboard** (Phase E remaining:
  "analytics dashboard"; FE-080-083 open; PRD-017 explicitly scoped OUT share analytics).
  Nobody can currently answer "how many FB clicks became identifications."

**Funnel bottom line:** top-of-funnel (share → compelling preview → browse) is now solid;
the conversion step (recognize → respond) works but is invisible-by-default and unmeasured;
the retention step (account → contribute again → bring photos) barely exists.

---

## Avenue A — Self-service archives ("Create Your Archive", PRD-060 / TOOLS-006)

**Current state:** More built than the ROADMAP suggests. `app/onboarding_routes.py` (Session
167 Track C) ships the full landing + form + create flow wired to the existing
`create_community()` primitive — but **dormant by triple design**: `SELF_SERVICE_ARCHIVE_ENABLED`
default-OFF (line 53), no nav CTA anywhere, and coming-soon panel when OFF. Codex-audited
(fail-closed slug dedup, per-user cap 3, IP throttle 10/hr, email validation). D1 is DECIDED
per BACKLOG SELF-SERVICE-ARCHIVE-ENABLE-167: "any logged-in user, 3/user cap."
Precursors shipped: WORKSPACE-001 `create_personal_archive()` (Sessions 122+133), community
middleware, ML service upload pipeline with local fallback.

**The honest blocker (D4, `docs/feedback/session-167-track-c-decisions.md`):** `_check_admin`
checks a **global** ADMIN_EMAILS list. A new archive owner can *see* their archive but
**cannot upload to or triage it**. Per-community owner permissions = WORKSPACE-006 (est. 2
sessions, open) — "the first non-admin write path in the app." Without it, flipping the flag
ships a dead-end funnel: create → empty dashboard → stuck.

**Demand evidence:** Direct from Nolan ("key to growth beyond admin-managed communities,"
BACKLOG TOOLS-006, "Source: Nolan feedback post-Session 95"). Claude Benatar: "Other people
uploading photos" (item #7) and item #12 — she actually submitted a photo. Strategic insight
from her thread: "Most people with photos won't bother unless UX is compelling." PRD-035
vision: "Anyone can create a space for their family." No evidence of *unprompted third-party*
demand yet — the demand signal is founder-conviction + 1 engaged family member.

**Effort basis:** Enable-only slice: ~0.5 session (flag + CTA) but dead-end without D4.
Honest v1 = WORKSPACE-006 (2 sess) + flag/CTA + upload-path verification ≈ **3 sessions**.
PRD-060's own estimate: v1 3-4 sessions, full 6-8.

**Risks:** (1) First non-admin write path — the repo's #1 recurring failure class is data
integrity (Lessons 153/154: 175 orphaned faces from merges; 9-11 split-brain occurrences);
opening writes to strangers multiplies exposure. (2) Upload pipeline fragility — broken 6
times for the ONE existing contributor. (3) Supabase free-tier limits (Lesson 200: DB size
took the whole site down twice); every archive adds rows + egress. (4) Empty-room problem:
a new owner uploads 30 photos and gets zero community — retention untested.

**First shippable slice:** WORKSPACE-006 owner-scoped permissions on upload+triage routes →
flip flag → CTA on `/` and `/tools` → one real family (e.g., Fader/Benatar relatives) as
concierge pilot before public announcement.

---

## Avenue B — Shareability / SEO / OG viral loop

**Current state:** The most mature avenue — and the one with explicit strategic backing.
`.claude/rules/session-priorities.md`: "Sharing is the primary growth mechanism — every photo
page is a potential entry point." Shipped: OG tags on all major pages (PRD-017 partial →
Session 168 closed most gaps), share_button() everywhere, public photo/person/gallery pages,
sitemap (1,267 URLs) + robots.txt, person-scoped photo galleries (PRD-065). **Open, cheap
gaps:** canonical-URL bug (CANONICAL-COMMUNITY-URL-168, P2, fix is `fast_app(canonical=False)`
+ one line in `og_tags()`); PRD-013 shareable **collection** pages DEFERRED ("Family members
want to share 'Aunt Vida's photos'" — /collections + /collection/{slug} routes actually exist
at page_routes.py:7810/7921, so the PRD may be closer to done than its DEFERRED status says —
worth verifying); share analytics explicitly out of scope so loop efficacy is unmeasured;
UX-042 (identify page lacks source-photo link, "critical for community onboarding").

**Demand evidence:** Benatar thread drove the entire share architecture (FEEDBACK_INDEX:
"Adoption concerns → DONE: shareable pages + OG meta + share buttons everywhere"). Strategic
insights doc: "Community adoption is the #1 challenge, not technology"; "the 'wow moment'
(Photo Context with face overlays) needs to be the first thing people see." Session 165 built
the person gallery because real shared links misbehaved — proof sharing is actually happening.

**Effort basis:** Remaining work is small: canonical fix (~0.5 sess, needs cross-page browser
verify), collection-share verification/polish (~0.5-1), PostHog funnel events + a tiny share
dashboard (~1). SEO compounding (person pages as long-tail surname search targets) is already
seeded by the sitemap; needs canonical fix to not misfire.

**Risks:** Diminishing returns — most of it is built; the marginal session buys polish, not a
step-change. SEO payoff is slow-compounding and unmeasurable without analytics first. A viral
loop amplifies whatever trust state the site is in (see Avenue E: two full outages in June).

**First shippable slice:** canonical fix + PostHog share/identify funnel events + verify
collection pages — makes every OTHER bet measurable.

---

## Avenue C — Cross-community person discovery

**Current state:** Plumbing exists, product surface doesn't. Shipped: identity_communities
auto-tagging (AD-213/216, COMMUNITY-003), cross-community badges on admin/ML surfaces,
cross-batch matching (PRD-049 — compares new faces against ALL identities), TOOLS-007
`GET /api/admin/search-person-in-collection` (identity_routes.py:5189, **admin-only**).
Open: COMMUNITY-004 "shared person indicator on identity cards" — deferred again in Session
168 as SHARED-PERSON-BADGE-PUBLIC-168 (P3) over an N+1 on the hot public people grid.
PRD-035 names the ultimate vision: "Search for faces across every old photo ever archived."

**Demand evidence:** Weakest direct-demand column. It's founder-vision (PRD-035 user story:
"I can see when a face in my community matches someone in another community") and a genuine
differentiator (PRD-035: "something Google Photos, Amazon Rekognition, and Mylio have failed
to do"). No community member has asked for it — but only 3 communities exist (Rhodes, Fox,
Fader), 2 of them Nolan's own. **This avenue's value compounds multiplicatively with Avenue A**
(archives × shared people = the network effect) and is near-zero standalone.

**Effort basis:** Public badge slice: ~1 session (precompute identity_communities set per
request — the fix is specified in BACKLOG). "Also appears in N archives" person-page section:
~1 session. A public cross-archive face search: multi-session + a **privacy consent model**
PRD-060 explicitly deferred ("Cross-archive person matching (needs privacy consent model)").

**Risks:** Privacy is the big one — surfacing that a face in a private family archive matches
a public Rhodes photo leaks membership. ML false positives shown publicly damage trust
(Gatekeeper pattern exists for admin, not for public surfaces). Value gated on there being
multiple non-Nolan communities, i.e., on Avenue A succeeding first.

**First shippable slice:** COMMUNITY-004 public badge (with the N+1 precompute) + "also
appears in" section on person pages, cross-linking Rhodes↔Fox — demonstrable today with
existing data (e.g., Roland Fox in both, per PRD-035 success metric #6).

---

## Avenue D — rhodes-wiki content pipeline (FB posts → dossiers → archive)

**Current state:** Sibling repo `/Users/nolanfox/rhodes-wiki` v0.2.0 (211 tests, Sessions
159-161 + Track E pending commit as TRACK-E-COMMIT-167). Working: Chrome-MCP FB post capture
→ inbox JSON contract → rhodesli `/admin/rhodes-inbox` (4 routes, Supabase provenance table,
atomic CAS approve → prefills `/upload`). **Local-dev only by design** (AD-RID-1: production
404s). 6 person dossiers exist (Menasche family); first narrative wiki page written but
uncommitted. Deferred: translation pipeline (Ladino/Greek/etc.), Notion publish with privacy
redactor, mechanical FB-TOS hook.

**Demand evidence:** Strong *organic supply-side* evidence — Lesson 195: comments on ONE FB
post yielded a maiden name, four siblings, a cross-family marriage, and April Merdjan's offer
"I have quite a few of them also" (an unprompted photo-contribution lead). This is the only
avenue where the 2,000-member group is *pushing* content at the project. Session 195 lesson:
"Comments are PRIMARY genealogical source material… not metadata."

**Effort basis:** High per-unit cost today: capture is manual (user opens post, expands
comments, 4-5 MCP permission popups — Lesson 194), extraction has known gaps (nested replies
missed — Lesson 196; name-field redaction — Lesson 193). Each ingested post ≈ an interactive
session slice. Publishing wiki pages publicly requires the privacy redactor + living-person
gates (Lesson 197 `living: true`) — unbuilt.

**Risks:** FB TOS exposure (fb-tos-rule.md exists; mechanical hook TOS-HOOK-001 deferred).
Living-person privacy is a hard gate on making any of it public — and *public* pages are
where the growth value is (dossier pages = shareable, searchable content flywheel). Cross-repo
process friction is documented (M8/M12/M13 guard inconsistencies). Throughput won't scale
past ~1 post/session without automation the TOS rule may forbid.

**First shippable slice:** commit Track E (blocked only on a dedicated rhodes-wiki session),
then publish 1-2 redactor-approved narrative pages (e.g., Menasche) with OG tags + links into
rhodesli person pages — a test of whether story pages out-share raw photo pages.

---

## Avenue E — Data-integrity / trust hardening as growth enabler

**Current state:** Enormously improved but with fresh scars. June 2026 alone: site DOWN twice
(Session 163 Supabase 402 quota; 158 cutover 502s). Historical: 175 orphaned faces (L154),
36 faces lost to a stale override layer for 4 days (L153), notes silently dropped for ~50
sessions (L179), GEDCOM enrichment silently dead for ~2 months (L205). Shipped counters:
Supabase single-source-of-truth (PRD-051), 29 anti-reintroduction guards, supabase_monitor +
keep-alive (OPS-002, Session 167), atomic GEDCOM importer (PRD-064), audit_log Phase 1,
/health served-photo count. Open: DATA-009 (stale-row reconcile), DATA-010 (cross-store drift
monitoring), AUDIT-001 remainder (entity timelines on /person + /photo), ENV-001 (no staging
env — every deploy tests in prod).

**Demand evidence:** Direct user mandate — memory `feedback_platform_reliability.md`: "Data
integrity and reliability trump all new features." Benatar's Round-3 feedback was three
consecutive **silent failures** (Help Identify swallowed her submission; name form couldn't
set a display name; Compare returned 404 after 5 green checks) — i.e., the one real community
tester churned on trust bugs, not missing features. Nothing kills a 2,000-member community's
willingness to contribute like a submission that vanishes.

**Effort basis:** Not one project but a posture. Highest-leverage open items: DATA-010 nightly
drift compare (~1 sess), contributor-visible submission status ("your suggestion is pending
review" — closes the silent-failure class from the user's side, ~1 sess, overlaps P2-10
"Help Identify doesn't persist submission state"), staging env (multi-session).

**Risks:** Opportunity cost — pure hardening ships no visible growth; it's an enabler whose
counterfactual (an outage during a viral moment) is invisible when it works. Risk of
over-rotating: the repo already invests heavily here (much of Sessions 154-168).

**First shippable slice:** contributor submission-status persistence + email-on-review
(Resend is wired) — converts trust work into a *visible* engagement loop (notify → return visit).

---

## Avenue F — Low-friction anonymous contribution loop (WORKSPACE-004 + Help Identify polish)

**Current state:** Anonymous identify-submission works (annotations → admin review). Missing:
session tracking, contribution history, "notified when reviewed" (email field exists on the
form but no notification loop back to anonymous contributors), retroactive account linking,
gentle signup push. All specified in PRD-036 (WORKSPACE-004, P4, "1 session, no dependencies").
Mobile matters here: memory `feedback_mobile_usability_critical.md` — app "almost unusable" on
mobile, "Blocks adoption. Trumps new features" (Sessions 124-128+150+168 made major fixes;
unclear if fully resolved — FB traffic is overwhelmingly mobile).

**Demand evidence:** Benatar items #4 ("I don't know how to identify!"), #14-16 (every
non-admin action she tried was blocked or confusing until fixed). PRD-036 thesis: "Never block
the contribution flow — signup is always optional." The FB group's age demographic makes
account-creation friction lethal.

**Effort basis:** WORKSPACE-004 per PRD-036: 1 session, zero dependencies — the cheapest
full avenue in this list. Response-notification loop: ~0.5-1 session (Resend wired).

**Risks:** Spam/abuse on anonymous writes (rate limiting exists); admin review burden scales
with success (Nolan is the sole reviewer — moderation is a Phase E open item).

**First shippable slice:** anonymous session-ID tracking + "we'll email you when reviewed" +
a `/my-contributions` cookie-keyed page.

---

## Dependency graph (what blocks what)

```
B (measure: PostHog funnel + canonical fix)  ── blocks honest evaluation of ALL others
E (trust: submission status, drift monitor)  ── soft-blocks A (strangers writing) and D (public pages)
WORKSPACE-006 (owner permissions, 2 sess)    ── HARD-blocks A being real (D4)
A (self-service archives)                    ── HARD-blocks C's compounding value (needs >1 real community)
                                             ── PRD-060 defers cross-archive matching pending privacy model
C (cross-community discovery)                ── badge slice independent; search slice needs A + privacy PRD
D (rhodes-wiki publish)                      ── blocked by TRACK-E-COMMIT-167 (trivial) + privacy redactor (real)
F (anonymous loop)                           ── independent (PRD-036: "no dependencies"); amplified by B's OG work
Mobile UX                                    ── cross-cutting multiplier on B, F (FB traffic is mobile)
```

## Honest trade-off summary (no winners picked)

- **A** has the most founder conviction and the clearest strategic story, but the thinnest
  proven demand, the hardest open prerequisite (first non-admin write path), and lands on the
  repo's most scarred failure surface (data integrity + upload pipeline + Supabase limits).
- **B** is nearly done; its remaining slices are cheap and make everything measurable — but
  it's optimization of an existing loop, not a new one.
- **C** is the real differentiator and the network effect, yet worthless until A produces
  communities Nolan doesn't own; the badge slice is a cheap credibility demo now.
- **D** is the only avenue where the community is already *pushing* supply (April Merdjan's
  "I have quite a few of them also"), but per-unit cost is high, TOS/privacy gates are real,
  and it's operationally cross-repo.
- **E** is what the sole real user's churn history actually demands, and its "visible" slice
  (submission status + notify) doubles as an engagement feature — but pure hardening has no
  growth optics.
- **F** is the cheapest complete loop (1-2 sessions, zero deps) aimed at the demographic
  reality of the FB group; its ceiling is bounded by admin review capacity.
- **Measurement gap is universal:** every success metric in PRD-036 (signup conversion,
  contribution rate, retention) is currently uncomputable. Any bet chosen without the B
  measurement slice will be evaluated on anecdotes.

## Key evidence paths
- `app/onboarding_routes.py` (flagged-off create flow) · `docs/feedback/session-167-track-c-decisions.md` (D1-D6)
- `docs/prds/060_self_service_archive.md`, `036_workspace_onboarding.md`, `035_multi_community_platform.md`, `013_shareable_collections.md`, `017_sharing_design_system.md`
- `docs/feedback/CLAUDE_BENATAR_FEEDBACK.md` + `FEEDBACK_INDEX.md` (real-user friction + strategic insights)
- `app/page_routes.py` `/` (2414), `/help` (4742), `/api/identify/.../respond` (5472), sitemap (273)
- `docs/BACKLOG.md`: SELF-SERVICE-ARCHIVE-ENABLE-167, CANONICAL-COMMUNITY-URL-168, SHARED-PERSON-BADGE-PUBLIC-168, WORKSPACE-001..006, TOOLS-006a-e
- ROADMAP.md Rhodes-Wiki section + Session 159-161/167 entries · `tasks/lessons.md` (L149, L153-156, L195-197, L200, L205)
