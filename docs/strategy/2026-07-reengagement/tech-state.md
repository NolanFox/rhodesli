# Rhodesli — Technical Capability Inventory (2026-07-13)

**Method:** read-only static analysis of `/Users/nolanfox/rhodesli` and sibling
`/Users/nolanfox/rhodes-wiki`. Live `/health` hit once (GET, read-only). No
writes to app or DB. Sources: `ROADMAP.md`, `docs/ml/ALGORITHMIC_DECISIONS.md`
(2942 lines), `docs/architecture/*`, `docs/fable-eval/2026-07-05-security-growth/`,
`app/*_routes.py`, `rhodesli_ml/`, `scripts/`, `/Users/nolanfox/rhodes-wiki/ROADMAP.md`.

---

## Domain 1 — Facial recognition / ML pipeline

### Embedding model
- **InsightFace `buffalo_l`** (detection `w600k_r50` for recognition), 512-dim
  PFE-style embeddings, cosine/L2 similarity. Singleton loader:
  `core/ingest_inbox.py:340-348` (`name="buffalo_l"`); CLI ingest default at
  `core/ingest.py:90-91,127`. No version bump documented since original
  adoption — `docs/ml/ALGORITHMIC_DECISIONS.md` has no AD entry proposing a
  newer InsightFace model.
- **Scale (live `/health`, 2026-07-13):** 1,824 top-level identities, 4,112
  identities including inbox/proposed, 1,127 photos. `docs/architecture/OVERVIEW.md:92`
  gives an older per-face RAM budget (~2.3 MB / 547 faces) — total face count
  isn't tracked as a single live metric anywhere; closest proxy is
  `photo_faces` row count, not surfaced in `/health`.
- **Storage:** `embeddings.npy` (local, read-only for the web app — regenerated
  only by the local pipeline) mirrored into Supabase `photo_faces` /
  `identities.anchor_ids` / `candidate_ids`. Postgres is canonical since
  Session 112 (AD-232); JSON/`.npy` are cache/backup only
  (`docs/architecture/DATA_MODEL.md:1-20`).

### What's actually wired vs shipped-and-dormant

| Feature | AD | Wired into a user-facing surface? | Evidence |
|---|---|---|---|
| Two-tier auto-clustering | AD-179 (`docs/ml/ALGORITHMIC_DECISIONS.md:2057`) | **YES — live at upload time.** Tier 1 (<0.85) auto-adds to `candidate_ids`, Tier 2 (0.85–1.30, raised by AD-183) surfaces as Discovery. | `core/auto_cluster.py`, `scripts/process_uploads.py` step 5 |
| Isotonic calibration | AD-149/152 | **YES — live in UI.** `neighbor_card()` renders "85% match" from the isotonic model (AUC=0.9577) instead of raw distance. | `rhodesli_ml/similarity_calibration.py`, AD-152 item 5 |
| Prototype-bank longitudinal reranker | PRD-038 Phase 2 | **NO — shadow-only, explicitly rejected for activation.** AD-224 (`ALGORITHMIC_DECISIONS.md:2620`): ran against 470 baseline proposals, produced **0 target/tier/score changes**. Root cause: best variant (`distance_only`) is a monotonic transform of baseline distance at current label count (~95 confirmed identities), so it can't reorder anything; baseline top-1 recall already 99.17%. | `rhodesli_ml/longitudinal_reranker.py`, only referenced from `scripts/cluster_new_faces.py` and `scripts/evaluate_longitudinal_shadow.py` — no `app/` import |
| Family Cluster Score | AD-235 (`ALGORITHMIC_DECISIONS.md:2812`) | **PARTIALLY wired.** Computed by batch script (`scripts/compute_identity_suggestions.py:56,74`, threshold=1.35), surfaced on `app/person_routes.py` (grep hit) as `identity_suggestions`. Not part of the AD-179 auto-clustering pipeline — an orthogonal soft signal, per design. | N=8 confirmed Fox members only; explicitly "won't generalize" per AD |
| Temporal co-occurrence (PRD-059) | Phases 1–4 | **YES for Phases 1-3 (data); Phase 4 (identity inference UI) YES, browser-verified Session 150.** 18 event groups, 391 co-occurrence pairs, 6 inference signals wired with an evidence panel on the person page (`ROADMAP.md` Session 147 entry). | `app/person_routes.py` |
| Active learning queue | `rhodesli_ml/active_learning.py` | **YES — live in cluster review UI.** `app/cluster_review_routes.py:29-254` imports and renders the queue + "learn-same"/"learn-different" actions directly in the admin review flow. | Real wiring, not orphaned |
| Multi-pass Gemini | `rhodesli_ml/multi_pass.py` | **YES but narrow.** Only imported by `app/estimate_routes.py:2141` for `build_anchor_comparison_prompt` — one function of the module used, for the anchor-comparison second-pass refinement (AD-102 progressive refinement design). | Not a general multi-pass pipeline in production, just this one call site |
| Embedding-adapter / LoRA experiment (PRD-038 Phase 4) | AD-222 | **NO — experiment harness only, artifact-save off by default.** Explicitly the "last stop before any backbone LoRA work," gated on holding out identity AND family slices. | `rhodesli_ml/embedding_adapter_experiment.py` |

### Known quality ceilings (from the docs, not inference)
- **Albert/Harry sibling indistinguishability** — ML cannot separate them;
  Session 152-153 resolved via multi-source triangulation (Gemini + Codex +
  local ML), not embedding improvement. Memory:
  `project_fox_sibling_resemblance.md`.
- **Kinship embedding is a weak signal** — Lesson 172: "0.09 gap mother vs
  non-blood... Event context (corsage, aisle walk, dance partners) is the
  STRONGEST signal." AD-235's own gap number confirms this quantitatively:
  Fox-family internal average distance 1.319 vs non-Fox baseline 1.391 — a
  **0.07 gap**, right at the edge of separability.
- **Reranker neutrality is explicitly scale-gated**, not a bug: AD-224 lists
  revisit triggers as (1) Fox triage ≥50 confirmed, (2) ≥200 confirmed total.
  ROADMAP Phase 5 (still open): "collect more Fox-family labels, rerun slice
  gates, and decide whether any matcher change graduates from shadow."
- **PRD-038's real blocker is pair-count/skew, not compute** — AD entry at
  `ALGORITHMIC_DECISIONS.md:2441` states the "main blocker for adapter work is
  pair skew rather than pair count" at the current confirmed-identity scale.

### Eval infrastructure — exists, runs, but thin on golden sets
- `rhodesli_ml/evaluation/` has `embedding_health.py`, `ranking_stability.py`,
  `regression_gate.py` — these run as part of the 725-test ML suite
  (`make test-ml`, CI-covered per Session 168's F6/TEST-MARKER-AUDIT-001).
- **No dedicated `golden*` labeled eval set file exists** anywhere in the repo
  (checked, zero hits) — calibration pairs (348, AD-149) and shadow-eval
  artifacts (`rhodesli_ml/artifacts/longitudinal_shadow`,
  `rhodesli_ml/data/shadow_scores.json`) serve that role ad hoc, produced by
  one-off scripts (`scripts/evaluate_longitudinal_shadow.py`,
  `scripts/session153_shadow_eval.py`) rather than a repeatable eval harness.
- Practical implication: re-running PRD-038 Phase 5 (the open item) requires
  re-deriving the eval slate each time, not `pytest`-invoking a fixed suite.

### Leverage points — Domain 1
1. **Family Cluster Score (AD-235) is the highest-leverage dormant signal** —
   already 0.89 balanced accuracy on N=8, already wired into `person_routes.py`,
   but only validated on one family. Extending to a second family (Capeluto,
   named as the explicit next step in the AD) would validate generalization
   with a script that already exists (`scripts/compute_identity_suggestions.py`).
2. **PRD-038 Phase 5 gate is a data problem, not an engineering problem** — the
   reranker code, eval harness, and shadow-mode wiring are all built and
   idle; it needs more confirmed Fox-family labels, which is exactly the kind
   of task a `/help`-identify growth loop (see Domain 4) would organically
   produce if traffic increased.
3. **`app/estimate_routes.py:2156`** hardcodes `"gemini-2.0-flash"` (marked
   `"Deprecated"` in `rhodesli_ml/gemini_config.py:49-51`) for the anchor-
   comparison second pass, bypassing the centralized `GEMINI_MODEL` config
   that AD-152 mandated everywhere else — a one-line fix with a real accuracy
   upside (see Domain 3).

---

## Domain 2 — Photo ingestion & the Rhodes photo database dream

### Ingestion paths (all four, by friction)
| Path | Trigger | Manual steps | Notes |
|---|---|---|---|
| Local CLI pipeline | `core/ingest.py` / `core/ingest_inbox.py` run by an operator | ~3-4 (collect files → run script → review clustering output → push to prod) | Used for bulk historical ingests, e.g. Charlie Fox 636 photos (Session 96b), Fader 147 photos (Session 146) |
| Web upload (`/upload`, `app/upload_routes.py`) | Any visitor (rate-limited) or logged-in contributor | 1-2 (drop file, optional metadata) — auto-approved for logged-in contributors since Session 104 | Cross-batch matching (PRD-049) runs automatically post-ingest |
| `/tools/compare` anonymous upload | Any visitor | 1 (drop file) — but **silently persists to R2 + `pending_uploads`**, no retention disclosure (UX_NEWCOMER_AUDIT F2, P0) | Logged-in uploads auto-approve straight into the archive — the exact same gap the "51 pending selfies" (per user memory) came from |
| `/admin/rhodes-inbox` (rhodesli side) | Admin only, **local-dev only by design (AD-RID-1)** — 404s on production via a dual gate (Railway env marker + filesystem path) | 1 admin click (Approve) once a rhodes-wiki JSON lands in `~/rhodes-wiki/inbox/pending/` | Session 161. Atomic CAS approve (`UPDATE...WHERE status='pending' RETURNING *` then `os.replace`) — AD-RID-6 |
| rhodes-wiki FB capture → inbox JSON | Human opens FB post, expands comments manually, Claude reads DOM only | 5-6 (open post, expand all comments/replies by hand, Claude runs `extract_fb_post`/JS extractor, validates contract, writes to `inbox/pending/`) | Governed by `fb-tos-rule.md` (below) — deliberately high-friction, one post per session, no automation |

**Total ingestion friction for a single "someone posts an old photo in the FB
group" event, end to end:** open post → expand comments (manual) → Claude
captures DOM (1 call) → build inbox JSON → **admin manually approves on a
local-only dev route** → `/upload` fires → cross-batch matching runs → ML
service or local fallback detects faces. The admin-approval step is the
structural bottleneck: it cannot run on production at all today (AD-RID-1),
so every FB-sourced photo requires the admin to be running rhodesli locally.

### Photo counts
- **Total: 1,127 photos** (live `/health`, 2026-07-13); **1,824 confirmed-tier
  identities**, 4,112 including inbox/proposed.
- **Rhodes community specifically: 498 photos** — cited directly in
  `docs/fable-eval/2026-07-05-security-growth/UX_NEWCOMER_AUDIT.md:74` ("the
  one with 498 photos and a Holocaust memorial mission"). That leaves ~629
  photos across Fox Family, Fader, Charlie Fox Dayton Ohio, and other
  collections — **Fox-lineage collections are still the majority of the
  archive**, not Rhodes, despite Rhodes being the flagship/branded product.
- People-grid counters for Rhodes specifically disagree across surfaces:
  landing page says "142 of 3372 faces identified" / "142 people identified";
  the people grid says "88 people in the archive · 87 named · 765 awaiting"
  (UX_NEWCOMER_AUDIT F7, P1 — a live, unresolved split-brain-count bug, same
  failure class as Lessons 78/144/150).

### rhodes-wiki: exact pipeline state
Per `/Users/nolanfox/rhodes-wiki/ROADMAP.md` (v0.2.0, 243 tests, private repo):
- **Phase A (Scaffold) — COMPLETE.** Phase B (parser stubs) — COMPLETE. **Phase
  C (real FB DOM capture) — COMPLETE** (Session 160: Chrome MCP `javascript_tool`
  + `read_page` accessibility-tree merge, working around Lesson 191/193's MCP
  quirks). **Phase D (person hints v1) — PARTIAL** (kinship NER live via
  `extract_kinship.py`; rhodesli cross-ref still open). **Phase E (rhodesli
  inbox UI) — DONE** (Session 161, described above). **Phase F (dossier
  auto-update) — COMPLETE 2026-06-30**, Session 167 Track E:
  `scripts/update_dossiers_from_approved.py` appends approved-post photo refs
  to a curated `subjects:` frontmatter field, idempotent + atomic + enforces
  the living-person-privacy invariant (Lesson 197: `living: true` MUST be
  `audience: private` or the script refuses to write). **Phase G (wiki
  narrative layer) — STARTED**: one page shipped,
  `wiki/menasche-family-rhodesia.md`. **Phase H (Notion publish) — NOT
  STARTED**, deliberately deferred behind a privacy redactor gate.
- **Committed-pending state:** RHODES-WIKI-004 (dossier auto-update + first
  narrative page) is implemented and tested (249/243 tests — ROADMAP header
  says 243, Session 167 entry says 249, likely from a slightly later count)
  but sits on branch `session-167/rhodes-wiki-004`, **not merged to main** —
  needs a dedicated rhodes-wiki-side session to commit per the cross-repo
  boundary rule (TRACK-E-COMMIT-167).
- **Content volume today is tiny**: 1 inbox post (pending approval), 6 person
  dossiers, 2 places, 1 wiki narrative page. This is a proof-of-pipeline, not
  yet a content engine — one real FB post has gone through the entire loop.
- **FB TOS rule** (`.claude/rules/fb-tos-rule.md`, rhodes-wiki): the user must
  open the post and manually expand every comment/reply; Claude may only click
  inline "View N more" buttons on the already-open post, never navigate,
  never paginate the group feed, never touch reaction/comment-input controls,
  never repeat-poll. This is a hard behavioral ceiling on throughput — there
  is no way to batch-ingest FB posts without a human manually opening and
  expanding each one, by design (litigation-risk avoidance, modeled on the
  hiQ v. LinkedIn / Meta v. Bright Data line).

### Leverage points — Domain 2
1. **The single biggest volume unlock is a production-safe `/admin/rhodes-inbox`.**
   It exists and works, but is deliberately gated to local-dev only
   (AD-RID-1) — meaning the admin must be running rhodesli locally to approve
   any FB-sourced photo. This was an intentional MVP scope cut, not a
   technical wall; making it production-safe (with the same auth model as
   other admin routes) removes the "admin must be at their laptop" bottleneck.
2. **Rhodes is only 498 of 1,127 photos (44%)** — the "photo database dream"
   for Rhodes specifically has a real gap between ambition and content
   volume today; the FB-capture pipeline (rhodes-wiki) is the only channel
   built for community-sourced Rhodes content, and it has processed exactly
   one post end-to-end so far.
3. **Merge RHODES-WIKI-004** (dossier auto-update + narrative layer) — fully
   built and tested, sitting on a branch, one session away from being live in
   the vault.

---

## Domain 3 — Model / API integration currency

### External AI call sites
- **Gemini** — centralized config at `rhodesli_ml/gemini_config.py:12`:
  `GEMINI_MODEL = "gemini-3.1-pro-preview"` (default, Session 61 / AD-139,
  "best reasoning + vision, ARC-AGI-2: 77.1%"), fast tier
  `GEMINI_MODEL_FAST = "gemini-3-flash"` (line 15). Pricing table
  (`gemini_config.py:29-60`) tracks 6 model variants including deprecated
  `gemini-2.0-flash` and `gemini-2.5-*`.
  - **Drift found:** `app/estimate_routes.py:2156` and `:2262` hardcode
    `"gemini-2.0-flash"` directly via `genai.GenerativeModel(...)`, bypassing
    the centralized config for the anchor-comparison progressive-refinement
    call (AD-102). This is the one place AD-152's "no hardcoded model
    strings" rule has drifted.
  - Every call logs to `gemini_api_calls` (AD-152/153) — cost, tokens,
    latency, status, batch_id.
- **ML service** (`ml_service/`) — standalone FastAPI service on Railway
  (TOOLS-002, Sessions 115-118), does face detection/embedding extraction with
  local-InsightFace fallback (`core/ml_client.py`). Not a frontier multimodal
  model — it's the same InsightFace pipeline, just extracted to its own
  process.
- **Codex CLI** (`gpt-5.5`, `xhigh` reasoning) — used for security/code
  audits per session (`.claude/rules/ai-tool-audit.md`), pinned via
  `.claude/rules/codex-model-pin.txt` with a 14-day freshness check in
  `scripts/harness-check.sh`. Not used for photo analysis in the live app —
  audit-only.
- **Fable 5** — used as an `Agent(model:"fable")` subagent for evals/sprints
  and, as of AD-251, as one of three candidate models in the multi-model
  photo-estimate workflow. Not wired into any production route.

### Multi-model photo-estimate workflow (`scripts/multimodel_photo_estimate.py`, AD-251)
- **What it does:** builds ONE fully-GEDCOM-enriched prompt, sends the
  identical prompt + image to three models — Gemini 3.1 Pro (via the
  production `_call_gemini_date_estimate`), Fable 5.0 (via `Agent` subagent),
  Codex gpt-5.5-xhigh (via `codex exec -i image.jpg`) — then a human/Claude
  judges and writes ONE chosen estimate to `date_labels`/`photo_locations`
  with an `analysis_provenance` block; all three candidates + the decision
  live in `docs/experiments/photo-estimates/<photo_id>-<date>/` as git
  artifacts, never in the DB (last-write-wins schema would destroy the
  comparison).
- **Cost/manual-ness:** Gemini call ≈ $0.037/photo (per `gemini_config.py`
  pricing note); Fable/Codex costs aren't logged anywhere (they're
  Anthropic/OpenAI-subscription-based, not per-call metered in this repo).
  It has been run **exactly once**, on one photo (Session 166, Meyer Fox +
  Reva Heft), not batched. `scripts/multimodel_photo_estimate.py` is 294
  lines with clear phase functions (`run_gemini`, `finalize`) but no batch
  driver — running it across N photos today means N manual invocations.
- **Structural provenance**: `operator="claude-code-manual"` +
  `experiment_id LIKE 'manual-%'` distinguishes manual runs from
  `operator="platform"` (default) at the data layer — this is solid and
  reusable infrastructure for any future multi-model comparison work.

### Where a 2026-frontier multimodal model could slot in
1. **Replace the deprecated `gemini-2.0-flash` anchor-comparison call**
   (`app/estimate_routes.py:2156`) with the centralized `GEMINI_MODEL` — same
   architecture, immediate quality lift, near-zero engineering cost.
2. **Batch-run the multi-model estimate workflow** across the ~629 non-Rhodes,
   non-fully-dated photos — the single-photo workflow, cost model, and
   provenance schema already exist (AD-251); it just needs a loop and a
   budget cap (`MAX_COST_DEFAULT` pattern already exists in
   `gemini_config.py:24`).
3. **OCR / caption-language work for rhodes-wiki's deferred translation
   pipeline** (Ladino/Greek/Italian/French/Hebrew, `RHODES-WIKI-LATER` in
   ROADMAP.md) is explicitly not started — a frontier multimodal model with
   strong non-English OCR is the natural unlock, and the `photo-context` /
   `translate-source` skills already scaffold the workflow pattern
   (Gemini-first bulk pass + Fable adjudicator) used elsewhere in this
   user's genealogy tooling.

---

## Domain 4 — UX debt (desktop + mobile)

### Concrete open items (Fable UX_NEWCOMER_AUDIT, 2026-07-05, live-site read-only)
P0 (trust-breaking):
- **F1**: `/c/rhodes/tree` renders the **Fox family's** GEDCOM with zero
  community filter (`app/page_routes.py:10939`, `/api/tree/data` ignores
  `community_slug` except for link generation) — a Rhodes descendant sees
  Meyer Fox / Fader / Newman, no Rhodes Sephardic names at all.
- **F2**: `/tools/compare` stores anonymous uploads to R2 + `pending_uploads`
  with **no retention/privacy disclosure** (`app/compare_routes.py:1664-1704`);
  logged-in uploads **auto-approve straight into the archive** with no review.
- **F3**: Mobile horizontal overflow on `/tools/compare` specifically
  (`scrollWidth=793` at 390px viewport) — the tools-page nav doesn't collapse
  like content-page nav does. This is the exact page FB traffic would land on
  for "upload a photo, see who matches," and it's broken on mobile.

P1 (confusing/dead-end):
- **F4**: platform root (`app/page_routes.py:799`) speaks internal
  session-log language to the public ("Rhodes-by-default ambiguity," calling
  the flagship archive a "demo"); also lists the Fox Family personal archive
  publicly with no privacy filter.
- **F5**: unprefixed `/help` mixes every community's faces (Rhodes helpers
  see Dayton, Ohio faces) — a fail-open-by-design gap from Session 168 that's
  now the wrong default with two real communities live.
- **F6**: **three separate navigation systems** (root nav / archive-landing
  nav / person+tools nav), plus a visibly broken logo collision on the
  person page ("RhodesliPhotos") and mobile root ("RhodesliCompare").
- **F7**: cross-surface identified-count contradictions on the same Rhodes
  community (142 vs 87-88 people; 2,124 vs 765 awaiting) — same failure class
  as the platform's #1 recurring bug (split-brain counts, Lessons 78/144/150),
  now visible on a public page.

P2 (polish/credibility): F8 unmoderated instant-publish comments on
memorial-adjacent pages; F9 empty "AI Reasoning"/"Tags" headers + raw model
names (`gemini-3.1-pro-preview`) leaking into user-facing copy; F10
unfiltered low-quality face crops in the emotional-hook Help-Identify queue;
F11 ambiguous "Photo 1 of 108" scope label.

### Prior mobile complaint (memory, pre-dates this audit)
`feedback_mobile_usability_critical.md`: "App is 'almost unusable' on mobile
— too slow, hard to navigate, can't demo to family members. This is the #1
blocker for community adoption." The Fable audit shows this is **now fixed on
content pages** (landing/person/photo all measure exactly 390px, zero
overflow) but **still broken on the tools pages** (F3) — i.e., partially
resolved, not closed.

### Structural debt
- **`app/main.py` is 8,256 lines** — down from a peak >10,000 via
  REFACTOR-001 (4 phases, Sessions 137/138/141/148b extracted ~3,909 lines
  into `app/components/`), but still a single monolithic file with 22
  sibling `*_routes.py` files (23 total including `main.py` itself) — a
  FastHTML/HTMX inline-template architecture with no separate template layer.
- **Frontend stack**: FastHTML (Python-generated HTML) + HTMX + Tailwind CSS
  via **CDN** (`docs/architecture/OVERVIEW.md` stack table) — no build step,
  no component framework, no client-side state beyond HTMX swaps + a little
  Hyperscript. A "Future Evaluation: Frontend Framework Migration" trigger
  exists in ROADMAP.md (React SPA or Next.js) but is explicitly **NOT YET
  TRIGGERED** (HD-022).

### What a modern rebuild would have to preserve
- **~120+ routes across 23 files** classified by community-routing safety
  audit (PRD-052, Session 115) — auth guards, CSRF origin checks
  (`.claude/rules/route-safety-audit.md`), and the `/c/<community_slug>/`
  prefix convention are load-bearing for the multi-tenant model.
- **OG tag / share-object contract** — person page and photo page are
  explicitly verified as "real share objects" (og:title/description/image/
  type=profile, canonical==og:url) — this is the entire growth-loop
  mechanism (Find → Share → Click → Recognize → Respond per
  `.claude/rules/ux-evaluation.md`) and must survive any rebuild intact.
- **`/sitemap.xml` + `/robots.txt`** (1,267 URLs: 1,127 photo + 136 person +
  tools/help/root, Session 168 G6) and admin surfaces: `/admin/*`,
  `/admin/rhodes-inbox` (local-only gate), `/admin/upload-review`,
  `/admin/ml-health` — none of these are documented in a single inventory
  doc; a rebuild would need to grep all 23 route files to reconstruct the
  full surface.
- **Postgres schema is the real source of truth** (identities, photos,
  photo_faces, date_labels, GEDCOM current-state + R2 history) — a frontend
  rebuild is comparatively low-risk *if* it stays read/write compatible with
  this schema; the risk is entirely in the data layer, not the UI layer.

### Leverage points — Domain 4
1. **F1 (Fox GEDCOM leaking into Rhodes tree) and F2 (compare-upload consent/
   auto-approve)** are P0 trust/legal issues with small, scoped code fixes
   (`app/page_routes.py:10939` needs a community filter; `app/compare_routes.py:1664-1704`
   needs a disclosure string + un-auto-approving logged-in compare uploads) —
   highest ROI-per-line-changed items in the whole inventory.
2. **Collapsing three navs into one** (F6) is pure UI consolidation with no
   data-layer risk — directly addresses both the "unfinished" credibility
   signal and a chunk of the historical mobile-usability complaint.
3. **F3's mobile-overflow fix is copy-paste from the pages that already work**
   — the hamburger-nav pattern exists and functions correctly on
   landing/person/photo; tools pages just never got it.

---

## Executive Summary (~400 words)

Rhodesli's face-recognition core is InsightFace `buffalo_l` (adopted early,
never upgraded) feeding a Postgres-canonical identity graph of 1,824
confirmed identities across 1,127 photos. The pipeline that actually runs in
production is narrower than the roadmap suggests: two-tier auto-clustering
(AD-179) and isotonic score calibration (AD-149) are live and load-bearing;
active learning and temporal co-occurrence (PRD-059) are genuinely wired into
admin UI. But the more sophisticated ML — the prototype-bank longitudinal
reranker (PRD-038) and the embedding-adapter/LoRA harness — sit in shadow
mode by design, explicitly gated on more labeled data (50+ confirmed Fox
identities, or 200+ total) that the project doesn't yet have. The one soft
signal proven to work on real data, Family Cluster Score (AD-235, 0.89
balanced accuracy), is validated on a single family (N=8) and needs a second
family to trust at scale. None of this is broken — it's an honest holding
pattern waiting on volume.

That volume gap is the real story of Domain 2: Rhodes-branded content is only
498 of 1,127 photos (44%) — the archive is still majority Fox-family. The one
channel built to grow Rhodes content organically, the rhodes-wiki
Facebook-capture pipeline, has processed exactly one post end-to-end and its
approval route is deliberately production-disabled (local-dev only), so
every FB-sourced photo currently requires the admin at their laptop. This is
a solvable, scoped gap, not an architecture problem.

Model currency is mostly fine (Gemini 3.1 Pro is centrally configured and
current) with one concrete drift: a deprecated `gemini-2.0-flash` hardcoded
in the date-refinement path. The multi-model estimate workflow (Gemini +
Fable + Codex, AD-251) is well-designed but has run on exactly one photo —
it's a reusable pattern, not yet a pipeline.

The UX debt is the most immediately actionable domain. A fresh, unauthenticated
audit found P0-severity trust breaks live today: the Rhodes archive's family
tree renders the *Fox* family's GEDCOM with no community filter, and the
public compare tool silently stores and (when logged in) auto-approves
uploaded photos into the archive with zero disclosure. Both are small, scoped
code fixes, not rebuilds. Three overlapping navigation systems and a broken
logo collision compound a credibility problem on top of the trust problem.
None of this requires touching the data layer, which is sound and should be
preserved as-is in any future frontend work.

**Top 3 moves, ranked by leverage-per-effort:** (1) fix the F1/F2 trust
breaks; (2) production-enable `/admin/rhodes-inbox` to unblock the FB
content pipeline; (3) grow Fox-family confirmed labels past the PRD-038
reranker gate via the existing `/help` growth loop.
