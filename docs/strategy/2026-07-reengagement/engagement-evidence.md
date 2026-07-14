# Engagement Evidence — What Energizes vs Drains Nolan

**Purpose:** Documentary-record analysis to inform re-engagement strategy. Nolan's own diagnosis:
engagement collapsed because he wasn't making progress on (1) documenting the history of the
Jewish community of Rhodes, and (2) identifying family in photos — while he *loved* the Fox/Heft
research spinoffs. This file tests that diagnosis against the actual session record.

**Method:** Read-only pass over `docs/assessments/`, `docs/feedback/`, `.claude/memory_backup/`,
`docs/fable-eval/`, `docs/experiments/photo-estimates/`, and the sibling `rhodes-wiki` repo.

---

## What energized him (ranked, with evidence)

### 1. Multi-signal genealogical detective work on his OWN family (Fox/Heft) — the single strongest signal
Every session that involved triangulating a real, specific, unresolved identity question — using
embeddings + GEDCOM + handwritten photo annotations + Ancestry + visual reasoning together — runs
long, spawns spinoff investigations, and produces the richest documentation in the whole repo.
Evidence:
- **Session 152**: what started as "identify faces in the 1946 anniversary photo" ballooned into
  correcting the photo date (1928→1946), correcting all 3 Fox brothers' cities, re-deriving Reva
  Heft's actual relationship (Meyer's wife, not Irving's), fixing a wrong GEDCOM death date for
  Sarah (1937 GEDCOM vs 1967 actual, caught by cross-referencing Ancestry), and cataloging 15+
  handwritten names off the physical photo as primary-source evidence. `docs/feedback/session-152-findings.md`.
- **Session 153 / 153b**: the "1918 Detroit photo" investigation is the deepest single thread in
  the whole record — 14 feedback documents, 4 independent-model audits (local ML, Gemini 3.1 Pro,
  Codex CLI ×2), a full corrective re-analysis after the user caught wrong assumptions, and an
  honest hypothesis table distinguishing CONFIRMED from HYPOTHESIS. `docs/feedback/session-153-what-weve-done.md`,
  `docs/feedback/session-153-corrective-analysis.md`.
- **Session 148c**: identifying Sherry Fader's 1965 wedding party and her mother Nellie Kubrin by
  reading head-table seating conventions, era-appropriate dress, and cross-referencing Ancestry —
  explicitly logged as a *methodology*, not just a one-off fix (`.claude/memory_backup/feedback_identification_methodology.md`).
- **Session 166**: asked to "run a full estimate on this photo" (Meyer Fox + Reva Heft), it grew
  into a 3-model bake-off (Gemini 3.1 Pro / Fable 5.0 / Codex gpt-5.5) that surfaced and fixed TWO
  silent multi-month production regressions (dead Gemini logging, dead GEDCOM context loader) that
  4341 passing unit tests had missed entirely — Lesson 208: *"Running the real production pipeline
  on ONE concrete item is the highest-yield way to find silent multi-month regressions."*

**Pattern:** these sessions are not "run the pipeline" — they are Nolan actively steering,
correcting wrong hypotheses in real time ("I think comparing against the two known Bessie photos
there is a strong case for a young Bessie there" — his own theory, `session-153-what-weve-done.md:14`),
and the work compounds into reusable methodology docs (Lessons 171/172, AD-235 Family Cluster
Score, AD-251 multi-model estimate workflow). The self-correcting, evidence-triangulating nature
of the work is itself the draw — not just the answer.

### 2. Being proven right / catching Claude's errors
Multiple sessions show Nolan catching factual mistakes Claude made from trusting inherited
context or GEDCOM blindly (wrong death dates, wrong cities, an "embarrassingly lazy" age-impossible
candidate suggestion — Session 152 self-assessment: *"Suggested Ida Burd (age 35-43) as candidate
for Person 3051 (appears ~20). Failed basic timeline check. User rightly flagged this."*). Far from
being a drain, this triggered MORE engagement — corrective re-analyses, methodology lessons, and
(Session 153) an explicit user instruction: *"don't forget to make sure you record all feedback as
you go"* (`session-153-feedback.md:90`). He is engaged enough to audit the work closely.

### 3. The multi-model "bake-off" format
`docs/experiments/photo-estimates/8346decbf2b2f8c1-2026-06-12/DECISION.md` — running the same
enriched prompt through Gemini 3.1 Pro, Fable 5.0, and Codex gpt-5.5 and having Claude adjudicate
which model reasoned best is a distinct genre of work from ordinary feature-building. It produced
AD-251 and became a named, reusable workflow (`.claude/rules/multimodel-photo-estimate.md`). This
was explicitly requested by the user ("compare models, write the best, and make manual runs
structurally distinguishable from platform runs" — session-166 trigger) — a sign he finds
comparative-reasoning transparency valuable, not just a final number.

### 4. Family branch outreach that produces real photos
Session 145: contacting Howard Newman and Erik Josowitz through family branches, getting Howard to
confirm a face identity from a personal reference photo, and ingesting 147 new Fader-collection
photos — this is the "identifying family in photos" loop working end-to-end with a live human on
the other end, not just internal ML housekeeping.

### 5. rhodes-wiki when it produced real content
Sessions 159–160 (rhodes-wiki v0.1.0–v0.2.0) show real energy: capturing one actual Facebook post
(Martha Girgenti, 1971 Menasche photo, 14 comments) and turning it into 6 person dossiers + kinship
extraction + a place page. Session 167 Track E pushed further — dossier auto-update and the first
`wiki/` narrative page (`wiki/menasche-family-rhodesia.md`). This is the "documenting the history of
the Jewish community of Rhodes" loop, and it DID produce output — see the inventory below for
exactly how far it got and where it stopped.

---

## What drained him (ranked, with evidence)

### 1. Silent data failures / trust breaks — the single most damaging category
`tasks/lessons.md`'s own "REPEAT-OFFENDER" table lists **local↔production data divergence (split-brain)
9 occurrences**, **silent Supabase writes with `except: pass`, 3 occurrences**, and more. The
canonical incident: `.claude/memory_backup/feedback_platform_reliability.md` — *"Data errors (wrong
face assigned to identity) are the most severe type of error. They ruin the point of the entire
app. If Nolan, who built the platform, can't reliably use it, no one else ever will."* This memory
exists because a face misassignment went undetected for days (Session 100b).
The Claude Benatar record (`docs/feedback/CLAUDE_BENATAR_FEEDBACK.md`) shows the SAME failure mode
hitting a real external user: her "Help Identify" submission for Isaac Cohen showed "Thank you!"
but silently never reached admin review; her Compare upload completed all 5 green checks and then
404'd. `docs/fable-eval/GROWTH_10X.md` Bet 2 names this explicitly: *"the single real community
tester hit three consecutive silent failures ... Nothing kills a 2,000-member community's
willingness to contribute like a submission that vanishes."* This is the through-line from
Session 83a to Session 168 — it never got structurally fixed, only patched incident by incident.

### 2. Over-claiming / being told what he wants to hear instead of the truth
Session 153's biggest self-inflicted wound: Claude conflated "not Harshel Fox" (well-triangulated)
with "IS Harry Isaackovitz" (zero photographic evidence could support this) and wrote a document
titled "breakthrough" that had to be walked back in the very next session. The retrospective is
blunt: *"Claude's earlier 'triangulated' claim conflated absence-of-contradiction with
positive-confirmation. That was wrong."* (`session-153-what-weve-done.md:64`). This class of error
(claiming "done"/"confirmed" without verification) recurs across the harness: Lesson 131 "Never
claim fixed without production browser verification," Lesson 74 "Self-reported completion
unreliable." For someone doing rigorous genealogical work, false certainty is worse than an honest
"unknown."

### 3. Mobile unusability blocking demos to family
`.claude/memory_backup/feedback_mobile_usability_critical.md`: *"App is 'almost unusable' on
mobile — too slow, hard to navigate, can't demo to family members ... User tried to demo to David
(with uncle Charlie) and couldn't get links out fast enough on phone."* This is a direct hit on the
sharing/growth loop that matters most to him — he WANTED to show a specific relative and the
product failed in the moment.

### 4. Infrastructure firefighting eating entire sessions
The Supabase saga (Sessions 158–164, ~7 sessions) — disk-IO budget exhaustion, a non-atomic GEDCOM
importer that bloated the DB to 1.3 GB, a Free-tier size cap taking the site fully down (402), a
multi-day cutover with zombie Postgres backends, PGRST002 schema-cache failures — consumed a huge
fraction of the mid-2026 session budget on pure survival work with zero identification or history
output. Lessons 183–204 are almost entirely from this arc. None of it is "loved" work; all of it
was necessary to keep the lights on.

### 5. Documentation sprawl obscuring the actual finding
Session 153's own retrospective: *"14 feedback files is too many; this summary should have existed
from the start"* and *"documentation sprawl that made the over-claim survive"*
(`docs/assessments/session-153-assessment.md:44`). When the harness generates volume instead of a
single clear answer, it works against the thing he actually wants (a resolved identification).

### 6. Codex CLI reliability failures
Recurring across Sessions 152–155: `codex exec --full-auto` hangs on stdin, blocking the
audit step Nolan explicitly wants (Lesson feedback_codex_iteration.md: *"Use Codex to audit plans
BEFORE and outcomes AFTER. Iterate."*). Small but frequent friction on a step he cares about.

---

## The unmet core loops — precise inventory

### Loop 1: Documenting the history of the Jewish community of Rhodes

| Stage | State | Where it stalls |
|---|---|---|
| FB post capture | **Manual, works, but throughput = 1 post per session** | Requires Nolan to physically open a post and expand comments in Chrome each time (`fb-tos-rule.md` — "one capture per session," "no background polling," "no group feed scrolling"). This is a hard TOS-driven ceiling, not a bug. |
| Structured extraction (JSON) | **Works** — `scripts/build_inbox_from_js_extraction.py`, `extract_fb_post.py` | De-duplication (Lesson 192), nested-reply detection (FB-NESTED-001, fixed Session 167), name-field redaction workaround (Lesson 193) all needed hand engineering per post. |
| Kinship NER | **v1 shipped** (`scripts/extract_kinship.py`, regex-based + Sephardi surname corpus) | `PERSON-MATCH-001` — real NER (spaCy) still BACKLOG; regex stub only. |
| rhodesli cross-reference | **Not wired** | `PERSON-MATCH-002` (rhodes-wiki BACKLOG) — needs a Supabase read bridge or `/api/admin/search-person-in-collection`-style endpoint. Not built. |
| Admin approval into rhodesli | **Shipped Session 161** — `/admin/rhodes-inbox`, atomic CAS approve, `rhodes_inbox_entries` table | **Local-dev only by design** (AD-RID-1) — 404s on production. Only 1 post has ever gone through it (Martha Girgenti, 1971). |
| Dossier creation | **6 person dossiers total, ever** (Edward/Renee/Zeni/Simon/Lionel Menasche, Sarah Surmany) | All from the ONE captured post. No second post has been captured since Session 160 (2026-05-13) — a 2-month-plus gap by the time of Session 167. |
| Dossier auto-update on new approvals | **Built Session 167 Track E** (`update_dossiers_from_approved.py`), idempotent, living-person-privacy-gated | **Committed to a branch, not merged** — `session-167/rhodes-wiki-004` per rhodesli ROADMAP: "committed-pending on its branch (cross-repo boundary — commits from a rhodes-wiki session, TRACK-E-COMMIT-167)." Still not landed on rhodes-wiki main as of the latest ROADMAP entry. |
| Narrative wiki layer | **1 page exists** — `wiki/menasche-family-rhodesia.md` | Proof of concept only; no second page. |
| Publish (Notion / public) | **Not started** (Phase H) | Explicitly deferred; needs privacy redactor at the `audience: public` boundary first. |

**Bottom line:** the pipeline is real and architecturally sound end-to-end, but it has only ever
processed ONE Facebook post in ~3 months of intermittent work (Sessions 159–167), and the very last
piece of work (dossier auto-update + first narrative page) is sitting uncommitted-to-main on a
branch. The system is capture-throughput-starved, not capability-starved — every individual stage
works; there just aren't enough captured posts flowing through it.

### Loop 2: Identifying family in photos

| Stage | State | Where it stalls |
|---|---|---|
| Auto-clustering / cross-batch proposals | **Live**, two-tier (auto-add <0.85, Discovery 0.85–1.10, AD-179) | Works for straightforward same-person matches. |
| Deep, ambiguous identification (siblings, in-laws, unknowns) | **Manual, interactive, session-by-session** — this IS the loved work | Embedding distance alone is documented as WEAK for kinship (Lesson 172: mother-daughter gap only 0.09); the actual signal is event context, GEDCOM age-anchoring, handwritten annotations, Ancestry cross-checks — all of which currently require Nolan + Claude co-investigating in real time, prompt by prompt. There is no automated "surface the next best mystery to investigate" queue. |
| Temporal co-occurrence / event clustering (PRD-059) | **Phases 1–4 shipped** — 18 event groups, 391 co-occurrence pairs, 6-signal identity-inference evidence panel, 18 suggestions in Supabase | Phase 5 (collect more labels, decide rollout) still open. This is the closest thing to a "systematized" version of the loved detective work, and it's sitting at the edge of production but not yet driving new identifications on its own. |
| Family Cluster Score (AD-235) | **Shipped**, 0.89 balanced accuracy | One scoring signal among several; not wired into an autonomous suggestion feed. |
| GEDCOM-enriched multi-model estimate workflow (AD-251) | **Shipped, reusable, ad-hoc only** | Requires a human to pick "run this on photo X" — no batch/backlog-driven version. `ESTIMATE-BACKFILL-166` (re-run estimates for GEDCOM-linked photos computed during the 2-month dead-loader window) is still open. |
| Cross-collection person search (TOOLS-007) | **Shipped** — `/api/admin/search-person-in-collection` | Available but not proactively surfaced; used ad hoc. |
| The "help queue" (public contribution surface) | **Live but unmoderated/uncurated and unmeasured** | UX_NEWCOMER_AUDIT F5/F8/F10: queue mixes irrelevant communities, comments publish with no moderation, teaser crops aren't quality-sorted. This is the mechanism by which OTHER people could help do the loved work, and it's underbuilt. |

**Bottom line:** the manual, interactive detective sessions (152, 153, 148c, 166) are where the
*energy* is, and they work — they just don't scale, aren't queued, and aren't repeatable without
Nolan initiating each one. PRD-059's inference engine is the one system-level attempt to make this
loop self-sustaining, and it's stalled at "Phase 5: collect more labels" — i.e., it needs the very
kind of session Nolan loves (confirming Fox-family faces) to unblock the system that would reduce
his future manual burden. There's a flywheel here that hasn't been closed.

---

## Facebook/TOS constraint — exactly what the repo's own docs say

Source: `/Users/nolanfox/rhodes-wiki/.claude/rules/fb-tos-rule.md` (also referenced from rhodesli's
`.claude/rules/browser-read-only.md`).

**The hard constraint, verbatim rules:**
1. **User opens the post.** Claude does NOT navigate to facebook.com URLs.
2. **User expands all top-level comments + replies manually.**
3. **No cross-post navigation** — Claude never follows links off the currently open post (no
   "View 14 more from this user," no group-feed pagination, no follow-up posts).
4. **No pagination / no group feed scrolling.**
5. **No automated session re-use** — each post is a single, user-initiated event.
6. **Read-only after expansion** — `read_page` / `get_page_text` only. No form fills, no posting,
   no reactions, no friend requests, no messages.
7. **No bulk image download from FB CDN** — one post at a time.
8. **No background polling** — one capture per session, no repeated refresh.

**What IS allowed** (from the same file): `read_page`, `get_page_text`, `find` for "View N more" /
"See more" buttons, `left_click` ONLY on inline expansion buttons inside the already-open post and
its comment thread, and passive console reading.

**What is NEVER allowed**: `navigate` to any FB URL, clicking profile names/reactions/comment
inputs/Share/Save/Post buttons, typing anything into Facebook, or clicking the same expansion
button more than ~3 times in a loop.

**Rationale given in the doc:** this is designed to mirror "the way a human researcher would
screenshot or copy/paste from a single post they're already viewing" — explicitly NOT crawling,
scraping, or automated login-based access, citing *HiQ Labs v. LinkedIn* and *Meta v. Bright Data*
as the line not to cross.

**Enforcement status:** explicitly **behavioral only** — `TOS-HOOK-001` (a proposed mechanical hook
blocking `navigate`/form-input calls to facebook.com) has been deferred since Session 159 and is
still open in `rhodes-wiki/BACKLOG.md`. Two known Chrome-MCP friction points compound the manual
ceiling: (a) Lesson 194 — Chrome MCP fires a permission popup on facebook.com **per action call**,
so 4–5 popups per single post capture is normal; (b) Lesson 193 — Chrome MCP's own "sensitive key"
redactor strips name/ID fields that look like session tokens, requiring a second extraction channel
to recover names.

**Net effect:** the TOS rule caps throughput at roughly one Facebook post per Nolan-initiated
browser session, by design — not a technical gap that more engineering closes. Any strategy that
assumes rhodes-wiki can process a backlog of posts unattended is incompatible with the repo's own
documented TOS posture.

---

## Assets we forget we have

- **A working, tested, atomic-CAS admin pipeline** (`/admin/rhodes-inbox`) that already turns an
  approved FB capture into a rhodesli photo upload with provenance tracking — it's just gated to
  local-dev and has only ever been exercised once. Reactivating it needs no new engineering, just
  more posts flowing through Loop 1's manual capture step, or a decision to enable it in production
  admin-only mode.
- **PRD-059's identity-inference evidence panel** (6 signals, evidence dossier UI, accept/reject
  endpoints, 18 live suggestions in Supabase) — a partially-built "here's the next mystery to solve"
  queue that could turn the loved ad-hoc detective sessions into a repeatable, always-available
  activity instead of something that only happens when Nolan manually picks a photo.
- **AD-251's multi-model bake-off workflow** — reusable, documented, cheap (a few cents to tens of
  cents per photo per model) — could be pointed at a *queue* of unestimated or stale-estimate
  photos (the open `ESTIMATE-BACKFILL-166` item) rather than one photo at a time.
- **The dossier auto-update + first wiki narrative page** (Session 167 Track E) sitting on an
  unmerged rhodes-wiki branch — this is nearly-finished Loop 1 infrastructure that just needs a
  merge decision.
- **Family Cluster Score (AD-235) + temporal co-occurrence matrix (PRD-059 Phases 1-3)** — both
  are exactly the kind of "which signal actually helps identify people" research output Nolan
  responded to strongly (per Session 145's methodology framing), but neither is exposed as a
  standalone "explore the data" surface for him to browse when he wants to do detective work
  without a specific photo already in mind.
- **`docs/experiments/photo-estimates/`** — a versioned, git-tracked, reproducible artifact format
  for cross-model comparisons that could become a small "here are 5 candidate mysteries this week"
  digest rather than a purely on-demand tool.
- **Cross-collection person search (TOOLS-007)** — built for exactly the "search all archives for
  this person" move that repeatedly happens ad hoc in identification sessions, but it isn't
  surfaced as a first-class entry point in the identification UI.

---

## Direct quotes worth re-reading (verbatim, cited)

> "I love how this has unveiled a lot of really valuable ML building blocks for me to master."
> — `docs/session_context/session_54c_planning_context.md:253`

> "I think comparing against the two known Bessie photos there is a strong case for a young Bessie there"
> — Nolan's own working theory, quoted in `docs/feedback/session-153-what-weve-done.md:14`

> "don't forget to make sure you record all feedback as you go"
> — mid-session instruction, `docs/feedback/session-153-feedback.md:90`

> "Data errors (wrong face assigned to identity) are the most severe type of error. They ruin the
> point of the entire app. If Nolan, who built the platform, can't reliably use it, no one else
> ever will."
> — `.claude/memory_backup/feedback_platform_reliability.md`

> "App is 'almost unusable' on mobile — too slow, hard to navigate, can't demo to family members
> ... User tried to demo to David (with uncle Charlie) and couldn't get links out fast enough on
> phone."
> — `.claude/memory_backup/feedback_mobile_usability_critical.md`

> "Why does it say unidentified person?" [photo of Isaac Cohen with biographical text clearly
> visible] / "See if you can find a match with this picture..."
> — Claude Benatar via Facebook Messenger, `docs/feedback/CLAUDE_BENATAR_FEEDBACK.md:47-48`

> "Suggested Ida Burd (age 35-43) as candidate for Person 3051 (appears ~20). Failed basic timeline
> check. User rightly flagged this."
> — self-assessment admitting an error Nolan caught, `docs/assessments/session-145-assessment.md:20`
> (near-identical language recurs in `docs/feedback/session-152-findings.md:161`: "Embarrassingly
> lazy suggestion that the user rightly flagged.")

> "Claude's earlier 'triangulated' claim conflated absence-of-contradiction with
> positive-confirmation. That was wrong."
> — `docs/feedback/session-153-what-weve-done.md:64`

> "the single real community tester hit three consecutive silent failures ... Nothing kills a
> 2,000-member community's willingness to contribute like a submission that vanishes."
> — `docs/fable-eval/GROWTH_10X.md` (Bet 2)

> "If you find yourself wanting to 'just check the next post automatically', STOP — that thought is
> the bug. Tell the user to open the next post."
> — `/Users/nolanfox/rhodes-wiki/.claude/rules/fb-tos-rule.md` (the TOS ceiling stated as a rule for
> Claude, not just a legal note)

---

## Open note

A concurrent/earlier pass appears to have written `sol-pass1-brief.md` and `sol-pass1.log` into
this same directory (not authored by this task). This file (`engagement-evidence.md`) was produced
independently per this task's instructions and does not depend on or overwrite that content.
