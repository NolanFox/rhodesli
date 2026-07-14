# Fable Pass 1 — Rhodesli Re-Engagement Plan (independent draft)

**Author:** Claude Fable 5 (architect), 2026-07-13. Written before seeing Sol's draft.
**Companion:** `sol-pass1.md` (GPT-5.6-Sol, same brief, independent). Adjudication follows.

## Diagnosis — why engagement collapsed

The documentary record says the roadmap and the owner's motivation diverged around Session 157.
Sessions 158a–e, 162, 163, 164 were consumed by Supabase crises and storage migrations. Sessions
168–169 and the 2026-07-05 eval produced *platform* work: security boundaries, growth phases,
multi-tenant readiness. All competent; none of it touched the two loves: **documenting Rhodes
Jewish history** and **identifying family in photos**. Meanwhile every session the owner actually
enjoyed (145, 148, 148c, 152, 153, 166) was an *interactive research session* — a mystery, evidence
from multiple sources, a verdict, and something new known at the end.

Three structural problems made the fun work rare:

1. **Discovery was manual.** The Fox/Heft-style investigations required Nolan present, driving.
   There is no engine that does discovery work while he's at his job.
2. **The FB pipeline's unit economics are wrong.** rhodes-wiki is well-architected but costs ~2
   hours of supervised MCP wrangling per post (permission popups, DOM quirks — Lessons 191–196)
   for one post's content. A person with a day job will never run that loop twice a week.
3. **Face recognition stalled at the label gate, and labeling was framed as a chore.** PRD-038's
   gates are closed for lack of confirmed hard labels — but producing those labels IS the
   identification research he loves. The system never connected the fun to the fuel.

The fix is not more platform. The fix is to make the project'a product *for Nolan* first: an
automated research desk that does discovery overnight and hands him mysteries, evidence, and
publishable history every morning.

## The organizing idea: **The Research Desk**

Every idea below serves one flywheel:

> **Ingest** (photos + testimony, TOS-safe) → **Enrich** (dates, places, OCR, faces) →
> **Investigate** (multi-model case work, overnight) → **Review** (Nolan, 10 min/day, mobile) →
> **Publish** (person narratives, case files, the Rhodesli photo database) →
> **Feed back** (every review = ground truth label → better face rec → better investigations)

Nolan's role changes from *operator* to *editor-in-chief*. Day-over-day progress is structural:
the desk runs nightly whether or not he has energy, and his 10 minutes of review both directs it
and trains it.

## Idea slate

### A. The engine

**A1. Nightly Research Desk** — excitement 10/10.
A scheduled autonomous run (cron or manual kickoff) that each night: (1) selects the top open
question from the case ledger (undated photo, unidentified face with high-value evidence,
unresolved hypothesis), (2) runs the full forensic stack — the already-built
`multimodel_photo_estimate.py` workflow, co-occurrence, Family Cluster Score, GEDCOM anchoring,
embedding neighbors, (3) writes a *dossier* with a verdict + confidence + "next best evidence,"
and (4) queues 5–15 one-tap reviewable proposals. Morning output: a digest page + optional email.
Newly possible: frontier models are now reliable enough to run unsupervised multi-step forensic
reasoning; the multimodel workflow already exists and won a real case (AD-251). Session shape:
perfect — every night produces visible artifacts.

**A2. Case Files — the hypothesis ledger** — excitement 9/10.
Formalize investigations as persistent first-class objects: `/cases/<slug>` with an evidence
ledger (each item: source, claim, weight, provenance), status (OPEN/LEANING/RESOLVED), and a
"what would change our mind" list. Cases are the memory of the research desk; new photos, new
GEDCOM links, new testimony auto-reopen affected cases. The existing open mysteries (Belle Isle
young man, Bessie/3009, person 3299 = Elizabeth Tischler?, Nellie Kubrin confirmation) seed it
on day one. This IS "documenting the history" — each resolved case is a story.

**A3. The Morning Review ritual (mobile-first `/desk`)** — excitement 8/10.
One queue, evidence-rich cards, one-tap accept/reject/not-sure, built for a phone over coffee.
Every action writes ground truth (anchors, negatives, date confirmations) with full audit trail.
This is ALSO the active-learning interface PRD-038 has been waiting for — the label gate opens
as a side effect of the fun part.

### B. Getting to "a whole database of Rhodesli photos" (TOS-safe)

**B1. Screenshot-native ingestion** — excitement 9/10.
Kill the DOM pipeline's friction: Nolan screenshots an FB post (phone, 15 seconds, exactly what
any group member may do), drops it in an inbox (share-sheet → email/Airdrop folder → later an
upload route). A VLM pipeline extracts photo, caption, commenter names, kinship claims →
structured inbox JSON → existing `/admin/rhodes-inbox` flow. No automation touches Facebook at
all — strictly *more* conservative than the current manual-nav rule. Unit cost drops from ~2h to
~1 min per post. This is what makes the photo database grow day-over-day.

**B2. Public-archive connectors** — excitement 8/10.
The database should not depend on FB at all. Institutional sources with clear research/citation
terms: Rhodes Jewish Museum collections, Yad Vashem photo archive, USHMM, JDC Archives, ANU,
UW Stroum Sephardic Studies, JewishGen, Ellis Island/ship manifests, FindAGrave, newspaper
archives (already used for Fox work). One connector playbook per source: fetch/cite/rights
metadata, provenance-first. Each autonomous session ingests one source batch with citations.
Also: mine what we already hold — session docs contain researched-but-unpublished material.

**B3. Verso/caption HTR sweep** — excitement 8/10.
Batch handwriting OCR across all 1,127 photos (and every new ingest) with a frontier multimodal
model. Session 152 found 15+ handwritten names on ONE photo. Extracted names → GEDCOM fuzzy
match → case files. Fully autonomous, cheap, high yield; a classic overnight job.

**B4. The Rhodesli Gazette (give-back loop)** — excitement 7/10.
Monthly auto-drafted "what we learned" post (newly identified faces, a resolved case, one
mystery photo) that Nolan personally posts to the FB group. Inbound comments = new testimony =
new ingestion, with zero scraping. Converts the community into contributors without building
any multi-tenant platform.

### C. Facial recognition, unstalled

**C1. Honest eval harness first** — excitement 7/10 (but it gates everything).
We have ground truth we've never weaponized: 1,824 identities with confirmed anchors, including
brutal hard cases (Fox siblings, cross-age pairs). Build a verification benchmark from it
(pairs + top-K retrieval metrics, per-slice: same-age, cross-age, kin). Every future ML change
is judged by this number, not vibes. One session, pure autonomous work.

**C2. Embedding modernization A/B** — excitement 8/10.
buffalo_l is a 2021-era model. Evaluate 2026 open face stacks (and stronger detectors) against
C1's benchmark at our 3K-face scale; dual-run migration (new embeddings written alongside, UI
reads old until the benchmark says switch). Newly possible: better cross-age/occlusion models;
our scale makes re-embedding trivial (~minutes).

**C3. VLM match court** — excitement 9/10.
Two-stage matching: embeddings for recall (top-K), frontier multimodal model as the precision
judge on borderline pairs — with GEDCOM/temporal context in the prompt (the thing embeddings
can't see). Session 104 already proved the pattern (Gemini caught an InsightFace false negative
from periocular occlusion). Run as a nightly batch on the proposal queue; output goes to the
morning review. This is the highest-leverage accuracy move available at our scale, and it's
API work, not research.

**C4. Constraint-aware candidate slates** — excitement 8/10.
Joint inference over what we already computed: date estimate + GEDCOM birth/death + kinship +
co-occurrence ⇒ "who CAN be in this 1917 Detroit photo, aged 20–30, kin to the confirmed
people in it." Wire Family Cluster Score + temporal co-occurrence (both built, both idle) into
one candidate generator feeding the desk. Turns dormant ML into daily value.

### D. Refresh the substrate

**D1. Model/API registry + refresh** — excitement 6/10 (enabler).
One registry for every model call (Gemini pinned at 3.1-pro-preview today), batch-API pricing,
Anthropic multimodal as a second provider, cost logging per call (already exists for Gemini).
Prereq for A1/B3/C3 at acceptable cost.

**D2. Core-three UX rebuild (photo, person, home), mobile-first** — excitement 7/10.
The pages the desk lands on should be beautiful: editorial/museum quality (Lesson 84), fast on
a phone, one nav system. Scope tightly: three pages + `/desk`, preserve routes/OG/admin. Newly
possible: current models genuinely produce production-quality frontend; this is now cheap.

**D3. Narrative person pages** — excitement 9/10.
Every researched person gets an auto-drafted, provenance-footnoted biography (Fable writes,
Nolan approves per paragraph) synthesized from GEDCOM + photos + case files + testimony. Start
with the Fox/Heft corpus already sitting in session docs — day-one content, zero new research.
This is the visible "documenting history" product, and it's shareable (Gazette fodder).

**D4. Ladino/multilingual testimony layer** — excitement 6/10 (later).
Frontier models now handle Ladino/Judeo-Spanish credibly; translate captions/testimony with
original-text preservation. Unique to this archive's identity. Defer until B1 produces volume.

## Kill list (explicit deprioritizations)

- **Multi-tenant enablement (Growth Phase C), self-service archives, workspace onboarding** —
  right analysis, wrong quarter. Revisit only when the single-archive experience is something
  Nolan himself uses daily.
- **Spam/consent boundary work (Phase A)** — keep exactly two items as hygiene (A1 ephemeral
  compare, ML token rotation: both small); drop the rest from the active queue.
- **pgvector, ML service Phase 5, frontend-framework migration** — stay deferred.
- **rhodes-wiki DOM-parser investment** — superseded by B1 screenshot ingestion; keep the vault
  format and inbox contract (they're good), retire the Chrome-MCP extraction path as primary.

## Top 3 "start Monday" picks

1. **A1+A2 minimal Research Desk:** case ledger table + nightly runner that works ONE case with
   the existing multimodel workflow + a digest page. DoD: wake up to a real dossier on a real
   open case (Belle Isle young man) with reviewable proposals.
2. **B1 screenshot ingestion MVP:** drop-folder → VLM extraction → rhodes-inbox entry. DoD:
   one real FB screenshot becomes a structured inbox entry with photo + names in <2 min.
3. **C1 eval harness + C3 match-court pilot:** benchmark from confirmed anchors; VLM
   adjudication of 50 borderline pairs; measure precision lift. DoD: a number.

## Where I push back on the premise

- "We haven't made progress in facial recognition" — partially false. Calibration (AUC .9577),
  co-occurrence, Family Cluster Score, cross-batch matching all shipped. What's true: the
  *matcher* didn't improve (reranker neutral) because of labels, and the shipped tools were
  never composed into a daily-value loop. The bottleneck is composition + labels, not research.
- "Can't get info off Facebook without TOS risk" — the constraint is real but the conclusion
  ("hard") came from picking the most fragile capture mechanism. A member screenshotting posts
  they can see, on their own phone, is not the thing platforms litigate; the pipeline just has
  to meet the screenshot where it is.
- The growth roadmap isn't wrong — it's premature. Its own concierge-pilot logic applies to
  Nolan first: he is family #1, and the pilot's success bar ("owner uses it without help,
  would show cousins") is exactly what the Research Desk builds.
