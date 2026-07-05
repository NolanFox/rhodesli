# Spam / Contribution Boundary Design (2026-07-05)

**Problem, verified in code and on the live page:** `/api/compare/upload`
(`app/compare_routes.py:1664-1700`) turns every anonymous compare query into a durable
`pending_uploads` entry + an R2 object under `uploads/pending/{job_id}/`, while the live page
(`screenshots/desktop-06-tools-compare.jpeg`) discloses none of this. Worse in the other direction:
**logged-in compare uploads are auto-approved into the archive with background ingest**
(`app/compare_routes.py:1684-1704`, `auto_approved: True`) — acceptable while "logged-in" means
the owner's family, incompatible with any widened signup. A second unmoderated public-write surface
exists on person pages: anonymous comments publish instantly (`app/person_routes.py:2291-2334`,
`status:"visible"`, in-memory 5/hr/IP limit). The product already has the right concept elsewhere —
an explicit login-gated contribution route exists (`app/compare_routes.py:3355-3408`) — compare
just doesn't use it.

The conflation is not merely a spam-cleanup nuisance: compare is the exact public front door every
newly invited community will be sent through, and the pending queue it pollutes is the exact queue
a future archive owner will be given. Ship multi-tenant on top of this boundary and every new owner
inherits a spam queue on day one.

---

## Recommended default: **Ephemeral-by-default + explicit contribute step** (with expiry as backstop)

**Design (one sentence):** an anonymous compare is a *query* — processed in memory/staging, result
shown, nothing durable created; becoming a *contribution* requires a deliberate post-result action
("Add this photo to the archive") that carries disclosure, and that action is the only path into
`pending_uploads`/R2.

Concretely:

1. **Compare = ephemeral.** Anonymous `/api/compare/upload` processes and returns matches; staging
   file deleted after response (or ≤24h sweep); NO `pending_uploads` row, NO
   `uploads/pending/` R2 object. The R2 durability rationale in the code comment ("staging alone is
   not safe — Session 100d") applied when compare was a disguised contribution path; it does not
   apply to a query that is *supposed* to be discardable.
2. **Contribute = explicit + disclosed.** After results, show: "Do you want to add this photo to
   the [Archive Name] archive? An admin will review it first." That button posts to the existing
   contribution path (`app/compare_routes.py:3355` route family) and REQUIRES either login or —
   for the anonymous case — email + Cloudflare Turnstile. The consent copy IS the spam filter:
   humans with real family photos click it; drive-by selfie testers don't.
3. **Kill the logged-in auto-approve.** Logged-in contributions go to the pending queue like
   everyone else's (owner/admin of that archive may retain auto-approve for *their own* archive
   only). This must land BEFORE any signup widening; it is one status-string change plus tests.
4. **Every pending entry carries `community_id`** (compare-created entries currently carry none —
   `app/compare_routes.py:1686-1700` dict has no community field — while the admin page filters on
   `u.get("community")`, `app/admin_routes.py:565-576`). Without this, owner-scoped moderation is
   impossible and orphan entries pile up in the root queue forever.
5. **Expiry as backstop, not primary control:** pending entries with `source="Compare Upload"` (and
   any future anonymous contribution) auto-expire after 30 days unreviewed — delete staging + R2
   object + row. Add an R2 lifecycle rule on `uploads/pending/` (30d) so storage cleans itself even
   if app-level sweeps fail. Startup cleanup today only handles orphaned staging dirs
   (`app/main.py:1290-1345`), not valid-but-stale spam.
6. **Admin quarantine + batch ops:** filter by `source`, select-all, bulk reject that also deletes
   R2/staging. One-time cleanup migration for the existing ~51 entries (verify count at runtime;
   snapshot job_ids to an unwind artifact first, per the data-repair protocol).
7. **Person comments get the same boundary:** default new comments to `status:"pending_review"`
   with an admin approve step (or at minimum a profanity/URL heuristic + honeypot + Turnstile-on-
   suspicion). Anonymous text on memorial pages is a dignity liability, not just spam.

## Why not the alternatives (each considered as the *primary* control)

| Option | Verdict | Reasoning |
|---|---|---|
| **Require login to compare** | Reject | Kills the highest-converting anonymous hook; the growth loop needs compare as a zero-friction taste of the magic. Login walls are for contribution, not curiosity. |
| **CAPTCHA on compare itself** | Reject as primary | Adds friction to the query (where we want none) while still writing durable objects; treats symptom. Turnstile belongs on the *contribute* step and auth endpoints only. |
| **Keep queueing, add auto-expiry only** | Reject | Consent problem remains (photos stored without disclosure); admin queue still polluted for 30 days; every new archive owner's first experience is spam triage. |
| **Separate "compare_queries" table** (keep everything, segregated) | Second-best | Preserves a "we might mine these later" archive of query photos — but that is storing strangers' family photos without consent. Only adopt if a real product need for query history emerges, and then with disclosure. |
| **Content-moderation ML gate before storage** | Defer | Right idea at public scale; wrong first dollar now ($0-cap constraint, low volume). Revisit when anonymous contribution volume > ~50/week or the first abusive image appears. The explicit-contribute step already removes ~all of today's junk. |

## What MUST exist before a stranger's front-door upload is safe (the multi-community gate)

1. Ephemeral compare + explicit disclosed contribute (items 1-2) — consent + volume control.
2. Auto-approve removed for non-owner logged-in users (item 3) — otherwise signup == archive write.
3. `community_id` on every pending entry + owner-scoped moderation view (item 4 + WORKSPACE-006) —
   otherwise moderation burden lands on the global admin forever.
4. Expiry + R2 lifecycle (item 5) — storage-cost and data-hygiene floor.
5. Visible content policy: one short page ("what you may upload, who sees it, how to request
   removal") linked from the contribute step — the content-liability minimum for hosting other
   families' photos, and the thing that makes the ask feel respectful rather than extractive.
6. Batch-reject/quarantine tooling (item 6) — the admin-burden escape valve when 1-5 leak.

## Migration note
Order matters: (a) ship ephemeral compare + explicit contribute (route change + UI); (b) stop-write
verified — new anonymous compares create zero pending rows (add a regression test asserting this);
(c) one-time cleanup of existing Compare-Upload pending entries (snapshot → bulk reject → delete R2
`uploads/pending/*` for those job_ids); (d) add expiry sweep + R2 lifecycle rule; (e) only then
schedule owner-scoped moderation work. Steps a-c are S-size each and independent of multi-tenant
work; nothing here blocks on WORKSPACE-006. Watch the known failure classes: the pending store is
local-JSON-first (`app/main.py:2106-2127`) so any cleanup must go through the canonical save path,
not direct file edits (split-brain, Lessons 144/150/153), and the community-routing safety tests
that call compare "temp files only" (`tests/test_community_routing_safety.py:384-407`) are stale
and should be updated with the new contract.
