# Growth Roadmap — "valuable for other Rhodeslis, without being spammy" (2026-07-05)

The complete, sequenced body of work. Sources: this run's live-site audit (`UX_NEWCOMER_AUDIT.md`,
15 screenshots), boundary design (`SPAM_BOUNDARY_DESIGN.md`), readiness assessment
(`MULTITENANT_READINESS.md`), and both prior drafts (validated, refined, and in three places
corrected). Security items from `SECURITY_VERDICT.md`/`codex-security.md` (path-traversal guard,
ML token rotation) are assumed into Phase A and not re-argued.

**The strategy in three sentences.** The product's share objects (person + photo pages) are already
good enough to grow with — what's missing is that the front door takes photos without consent, the
loop never closes (contributors hear nothing back), and a second family's data would neither stay
private nor stay theirs. Fix the boundary, close the loop, then hand-carry 1-3 known families in
while multi-tenant hardening lands underneath them. Growth mechanics stay non-spammy because every
outreach is personal, consent-first, and reply-driven (see OUTREACH ETHICS).

---

## Phase A — Do-first safety/spam (days; all S unless noted; nothing here blocks on anything)

| ID | Item | Why it blocks growth | Size | Acceptance criterion | Built vs new |
|---|---|---|---|---|---|
| A1 | Ephemeral compare: anonymous `/api/compare/upload` creates NO pending row / R2 object | Consent violation at the exact front door new families are sent through; source of the spam queue | S | Anonymous compare → results, zero durable artifacts; regression test asserts no `pending_uploads` write; existing behavior test updated (`tests/test_community_routing_safety.py:384` is stale) | Mostly built (compare pipeline stays; queueing branch removed) |
| A2 | Explicit "Add to archive" contribute step w/ disclosure + (login OR email+Turnstile) | Converts intent honestly; the consent copy is the spam filter | M | Contribution possible only via the explicit step; copy states review + retention; posts to existing contribution route (`app/compare_routes.py:3355`) | Contribution route built; UI step new |
| A3 | Remove logged-in auto-approve (`app/compare_routes.py:1684`) | Signup widening must not equal archive-write widening | S | Non-(archive-admin) logged-in contributions land in pending; test with a non-admin session | One-line policy change + tests |
| A4 | Pending hygiene: `community_id` on every entry; 30-day expiry sweep for anonymous sources; R2 lifecycle on `uploads/pending/` | Owner-scoped moderation impossible without it; storage/queue rot | S | New entries all carry community_id; unreviewed anonymous entries >30d are deleted (row+staging+R2) | New but small |
| A5 | Batch-reject + one-time cleanup of existing Compare-Upload entries (snapshot first) | Admin queue must start clean for the pilot | S | Queue shows 0 compare-spam; unwind artifact exists | New |
| A6 | Person comments: pending-by-default (admin approve) | Unmoderated instant-publish text on memorial pages is a dignity/liability risk (`app/person_routes.py:2291-2334`) | S | New comments invisible until approved; admin surface lists them | Small change |
| A7 | Security carry-overs: path-traversal guard on `/photos/{filename:path}` + `/uploads/facecompare/`; rotate ML_SERVICE_TOKEN | Table stakes before inviting strangers | S | Guard tests pass; old token dead | New/ops |

## Phase B — Trust & retention: close the loop (days-to-week; the churn killer)

| ID | Item | Why it blocks growth | Size | Acceptance criterion | Built vs new |
|---|---|---|---|---|---|
| B1 | Contribution receipt: every Help-Identify/comment/upload submit returns a visible "received — here's what happens next" state + a status URL (session token; email optional) | The loop's dead stage; the one real external tester churned on silent outcomes; prior evals' Bet 2 — still unbuilt on the live site | M | Anonymous contributor can bookmark a status page showing pending/approved/rejected | Net-new (Resend wired for email) |
| B2 | Notify-on-review (email, opt-in, per-submission) | "They looked at my grandmother's name" is THE retention moment for this audience | S (after B1) | Approve/reject triggers one email to opted-in contributor; unsubscribe honored | Resend built; trigger new |
| B3 | Fix the broken shared navs + logo collision; one nav system (or two: platform vs archive), archive-branded | Three navs + "RhodesliPhotos" collision reads prototype on every shared page (F6) | M | Person/tools pages use the archive-aware collapsing nav; no logo collision at 390px | Rework |
| B4 | /tools/compare mobile overflow fix | FB traffic is mobile; front door requires horizontal scroll (F3, scrollWidth 793 vs 390) | S | docScrollWidth == viewport at 390px on all /tools/* | Fix |
| B5 | Rewrite platform-root copy for humans; drop "demo archive"; feature Rhodes properly | Internal changelog-speak at the first touch (F4) | S | No internal vocabulary; a cold reader can say what the site is in one sentence | Copy |
| B6 | One canonical count definition rendered everywhere (people vs faces vs awaiting) | 142 vs 88 on the same community erodes the genealogist audience's data trust (F7) | S | Landing + people grid agree or label the difference explicitly | Fix |
| B7 | Help-queue curation: quality-sorted crops, community-pure by default | Recognition odds are the loop's conversion rate (F5, F10) | S-M | /c/rhodes/help shows Rhodes-only, quality-sorted faces; root /help groups by archive | Rework |
| B8 | Photo-page polish: hide empty AI sections + internal model names ("gemini-3.1-pro-preview") | Debug vocabulary undercuts the best page (F9) | S | No empty headers; provenance in friendly words | Fix |

## Phase C — Multi-tenant enablement (weeks; sequence within phase matters)

| ID | Item | Why it blocks growth | Size | Acceptance criterion | Depends | Built vs new |
|---|---|---|---|---|---|---|
| C1 | `_check_community_admin` seam on pending-review + approve/reject routes, driven by `communities.admin_emails`/`owner_id` (WORKSPACE-006 minimum slice) | THE gate: owners can't run their own archive (G1) | M | Pilot owner approves/rejects ONLY their archive's uploads; cannot see other queues; global admin unaffected | A4 | Fields built; guard new |
| C2 | Privacy enforcement: root/sitemap/search exclude non-public; middleware access check for private | "Unlisted" archives are on the public front page today (G2, live-proven) | M | Unlisted = link-only; private = members; root shows public only | — | Fields built; enforcement new |
| C3 | Scope rendered data surfaces: tree/map/timeline per-community or honest empty state | /c/rhodes/tree renders the Fox GEDCOM today (G3, live-proven) | M | No archive renders another family's GEDCOM/identities; archives without a tree say so | — | Schema supports it; readers new |
| C4 | Archive-prefixed storage for new uploads + collision-safe photo IDs (hash content or slug-qualified basename) | Cannot offboard/export a family; basename collisions across families (G5) | M-L | New uploads land under `archives/{slug}/`; two archives can upload `scan001.jpg` | A4 | Prefix field built; pipeline new |
| C5 | Owner console v1: pending queue + rename/merge-lite + archive settings on one page | The pilot family's daily surface | M | Owner completes upload→identify→approve cycle without Nolan | C1 | Assemble from existing admin pieces |
| C6 | Cross-archive matching consent: per-archive opt-in flag + invite-copy disclosure | Global ML matching (`app/upload_routes.py:1115-1124`) is a feature for interlinked Rhodes families but must be chosen, not discovered | S-M | Flag respected by cross-batch matching; default off for new archives | C1 | New |
| C7 | Flag-flip readiness review, THEN `SELF_SERVICE_ARCHIVE_ENABLED` | Flip is an event, not a feature | S | C1-C4 green + pilot retro says owners self-serve | C1-C5 | Built (the flag) |

## Phase D — Polish/SEO/measurement (background, continuous)

| ID | Item | Why | Size | Acceptance |
|---|---|---|---|---|
| D1 | Funnel instrumentation: share-click → arrival → help-view → submit → approve (PostHog events exist for some; complete the chain) | Can't tune what you can't see; kill-criteria below need it | S | One dashboard answers "did last week's shares produce contributions?" |
| D2 | Canonical-URL community prefixes (deferred G5 of S168) + og:url consistency | Share/SEO correctness at multi-archive scale | S | Canonical == og:url == prefixed URL |
| D3 | Person-page date/name formatting ("(1908- 1998)" spacing), photo-nav scope label ("of 108 in this collection") | The details a genealogist audience notices | S | Spot-check clean |
| D4 | Landing teaser faces: quality-gated sample | The emotional hook shouldn't lead with a black blob (F10) | S | No unreadable crops in the hero teaser |

---

## Sequenced plan

**Next few days (one focused sprint):** A1→A7 complete + B4 + B5 + A5 cleanup. Rationale: every
item is S/M, none blocks on another phase, and together they make the site safe to *show* — no
consent violation, no spam pipe, no broken mobile front door, no changelog-speak at the entrance.

**Week 2:** B1+B2 (the loop-closer — the single highest-retention investment in the whole plan),
B3, B6-B8, D1. At the end of week 2 the growth loop actually closes: share → recognize →
contribute → *hear back*.

**Weeks 3-5:** C1→C5 in order, D2-D4 alongside. Invite family #1 (see playbook) as soon as C1+C2+C3
are green — the pilot deliberately *precedes* C4/C6 completeness with disclosed caveats.

**Not now (explicitly deferred):** broad self-service (C7 gate), content-moderation ML (volume
trigger in `SPAM_BOUNDARY_DESIGN.md`), contributor-role hierarchy beyond owner/admin, Turnstile on
read paths, multi-GEDCOM merge tooling. Standing Bet-1/2/3 from the Session 169 GROWTH_10X remain
directionally valid; this plan re-sequences them (Bet 2 trust-loop is promoted into Phase B ahead
of all self-serve work) and corrects Bet 3's premise (self-serve is not "enable the flag" — it's
C1-C7).

**Where I disagree with the prior drafts, with evidence:** (1) Codex rank-2 "durable abuse
controls" (CAPTCHA/persistent limits) is over-weighted as a near-term item — once A1 makes compare
ephemeral and A2 gates contribution behind consent+Turnstile, in-memory limits are adequate at
pilot scale; persistent limits are a C-phase hardening, not a blocker. (2) Both drafts' roadmaps
omit rendered-surface scoping entirely (C3) — the live tree leak is a P0 for the *pilot*, because
it's the first page a genealogy-minded pilot family will open. (3) Neither draft lists the loop's
receipt/notify slice as pre-pilot; the churned-tester history (Session 169 W3/W4) says a pilot
without B1/B2 will reproduce the same silent-failure churn with higher stakes — three families,
not one tester.

---

## Concierge-pilot playbook (first 1-3 families, flag OFF)

**Selection:** families already active in the Jews of Rhodes FB group (~2,000 members) who have
(a) a known photo box, (b) one motivated "family historian," and (c) a personal connection to
Nolan or one hop away. One family at a time; the second starts only after the first reaches the
success bar.

**Offer (what they hear):** "I'll build your family's photo archive with you — you keep ownership,
you approve everything, nothing is public until you say so." NOT "please upload your photos to my
platform."

**Mechanics:** Nolan creates the archive row manually (slug, `admin_emails` = the historian,
privacy=unlisted). One 45-minute video call: batch-upload their first 30-80 photos together, watch
face detection group people live (the magic moment), identify 3-5 relatives on the call. Then the
historian gets homework that exercises the loop: share ONE person page into their own family
WhatsApp/email thread — not the FB group — and collect one identification from a relative.

**Success bar (per family, 30 days):** ≥50 photos in; ≥10 people named; ≥1 non-owner relative
contributed an identification; owner triaged ≥1 pending upload without help; owner says they'd
show it to their cousins. **Kill criterion:** if 2 of 3 families stall before 50 photos or the
owners keep routing actions through Nolan after C5 ships, stop scaling and fix the owner console
before family #4 — do not compensate with concierge labor (that's how founders hide product gaps).

**Caveats disclosed up front (until C2/C3/C6 land):** the archive directory currently lists all
archives; the tree feature will show your tree only after per-archive scoping (or stays hidden);
face matching may propose links to other archives' photos and you choose whether that's on.
Putting these in the invite is what makes the pilot honest — and it converts the pilot families
into witnesses that the platform respects boundaries.

---

## OUTREACH ETHICS — the "not spammy" contract

The owner's worry has two halves: the *product* must not generate spam (Phases A/B), and the
*outreach* must not be spam. Rules for the second half:

1. **Personal, individual, reply-shaped.** Every invite is 1:1 to a named person referencing a
   real connection ("your grandmother appears in the Capeluto Tampa collection"), sent from
   Nolan's own account, ending in a question. No bulk messages, no BCC blasts, no group-tagging
   sprees, no DM automation. Hard rule: **no unsolicited contact derived from archive data**
   (never scrape/infer emails from GEDCOMs, obituaries, or FB and cold-mail them).
2. **FB group conduct:** post as a contributing member, not a promoter. Cadence cap: ≤1 rhodesli
   post per 2 weeks, and every post leads with the *content* (a mystery photo, a newly identified
   face, a story) with the link secondary. Answer every comment personally. Never repost the same
   link; never post-and-run.
3. **Consent before spotlight.** Before featuring a living person's name/photo in a share or FB
   post, get a yes from the family member who contributed it. Photos of the deceased: honor any
   family objection within 48h (takedown promise published on the content-policy page from
   `SPAM_BOUNDARY_DESIGN.md` item 5).
4. **Email discipline (product notifications):** transactional only (your submission was reviewed;
   your archive got a contribution) — opt-in at the point of contribution, one-click unsubscribe,
   no digest/newsletter until someone asks for one. Frequency cap: ≤1 notification email per
   contributor per day (batch if needed).
5. **The pilot ask is reciprocal, not extractive.** Frame: "help me test whether this preserves
   *your* family's photos properly" — the family gets a working archive, exportable (C4 makes this
   literally true; until then, promise it and mean it: their originals + metadata on request).
   Never frame it as content acquisition for the platform.
6. **Acceptance criteria for the messaging itself:** (a) a cold reader of any invite can tell in
   one sentence what they're being asked and what they get; (b) every message names why *this*
   person ("no reason you specifically" = don't send); (c) nothing is sent that Nolan wouldn't be
   comfortable having screenshot back into the FB group; (d) zero complaints/"who is this?"
   replies across the pilot — one complaint triggers a copy review before the next invite; (e)
   every notification email has working unsubscribe honored within one send cycle.

**The underlying principle:** growth for this product is *recognition*, and recognition cannot be
spammed into existence — it happens when the right person sees the right face. Optimize for the
density of right-person/right-face moments (shareable person pages, quality-sorted help queues,
closed loops), never for raw impressions.
