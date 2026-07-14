# Rhodesli Re-Engagement Deep Dive — Sol, Pass 1

**Date:** 2026-07-13  
**Recommendation:** Stop treating Rhodesli as a nearly finished platform. Turn it into a **Daily Discovery Engine**: every autonomous session should advance one historically meaningful case, leave structured evidence behind, and make the archive visibly richer.

## Executive thesis

Rhodesli does not need another readiness phase. It needs a production system for the work Nolan loved: take a difficult photo, combine faces, family structure, dates, places, testimony, and outside sources, then end with a defensible discovery and a better historical record. The Fox/Heft investigations were not side quests; they were the product prototype.

The operating flywheel should be:

> consented evidence intake → high-value case selection → exhaustive retrieval and graph context → independent multimodel investigation → adversarial adjudication → human gate → casefile/story publication → one targeted witness question → new evidence

The unit of progress is no longer commits, tests, uploads, or model calls. It is:

- an identity confirmed, corrected, or sharply narrowed;
- a sourced historical claim added or contradicted;
- a photo connected to an event, family, place, or date;
- a high-value question delivered to the one person likely to answer it; or
- a reusable casefile whose evidence makes the next investigation easier.

This is not a rejection of the existing architecture. Rhodesli already has most of the substrate: 1,127 photos, 1,824 identities, calibrated face similarity, GEDCOM links, two-tier clustering, and a live site (`ROADMAP.md:4-18`). It even has a structured `identification_investigations` table with references, methodology, candidates, signals, outcomes, and bonus identifications (`scripts/migrations/create_identification_investigations.sql:1-60`). The strategic error is what the substrate has been pointed at.

## 1. Diagnosis: why engagement collapsed

1. **The output drifted away from discovery.** The July roadmap is dominated by safety, growth, multi-tenant infrastructure, polish, and autonomous hardening (`docs/fable-eval/2026-07-05-security-growth/GROWTH_ROADMAP.md:18-84`; `ROADMAP.md:176-180`). Those are competent platform tasks, but Nolan's reward signal is a newly understood person or photograph. The prior plan optimized the conditions around the product before repeatedly producing the product's core experience.

2. **The evidence supply chain was built around its highest-friction step.** Rhodes-wiki's real ingestion path requires Nolan to open a post, expand comments, invoke a one-shot JavaScript extractor, and separately handle images (`/Users/nolanfox/rhodes-wiki/docs/ARCHITECTURE.md:465-505`). Lessons record four or five permission dialogs, missed nested replies, and the fact that comments—not posts—held the genealogical value (`tasks/lessons.md:260-266`). Worse, current Meta terms separately prohibit automated collection without permission. This is not a scalable or comfortably TOS-safe foundation.

3. **The ML program optimized scores inside a shortlist rather than new discovery.** The shipped prototype-bank reranker changed zero of 470 predictions; the baseline was already 99.17% top-1 on that easy subset, and the design could not retrieve a candidate absent from the baseline top five (`docs/ml/ALGORITHMIC_DECISIONS.md:2618-2627`; `docs/ml/RERANKER_REVIEW_103.md:24-57`). Calibration and shadow deployment were sound, but they did not create a stream of surprising identifications.

4. **Autonomous sessions were measured by technical completion, not historical delta.** One real one-photo multimodel run produced substantive historical work *and* exposed silent Gemini logging and dead GEDCOM context that thousands of tests missed (`ROADMAP.md:176-180`; `tasks/lessons.md:284`). That is the correct shape of a side-project session: a visible artifact plus incidental system improvement.

5. **The system has investigative components, not an investigative workspace.** The public photo page is already described as museum-quality, but evidence and growth actions are fragmented and several high-value workflows remain unverified on mobile (`docs/fable-eval/SITE_VISION_AUDIT.md:8-19,38-56`). Fixing isolated surfaces cannot reproduce the feeling of conducting a case.

## 2. Product operating model: the Discovery Ledger

Before the idea slate, institute one shared ledger. Every autonomous run receives a `case_id` and must append machine-readable artifacts to the existing investigation record: inputs and provenance, model claims with citations, candidate identities, contradictions, requested human decisions, cost/time, and final historical delta. No model may silently overwrite another model or a human conclusion; this extends the existing compare-without-overwrite rule (`docs/ml/ALGORITHMIC_DECISIONS.md:912-927`) and gatekeeper architecture.

Make the harness roles asymmetric. **Opus orchestrates** the queue, budgets, dependencies, and acceptance checklist; **Sol researches and implements** the archive tools and primary case analysis; **Fable judges architecture and challenges conclusions**; **Gemini is the specialist visual extractor/date-place investigator**. A model never grades its own work, and Opus advances a case only when the required artifact—not a self-reported completion message—exists. That constraint follows a recurring harness lesson: self-reported completion is unreliable (`tasks/lessons/harness-lessons.md:13-16`).

The daily dashboard should show only six counters: cases advanced; accepted claims; identities confirmed/corrected; photos linked to an event/person; witness answers received; dollars per accepted claim. Test count remains a quality constraint, not the product scoreboard.

## 3. Idea slate

### A. Industrialize the Fox/Heft magic

#### 1. The Nightly Photo Investigation Factory

- **What:** A provider-neutral case runner that selects one high-value unresolved photo, assembles the full evidence packet, gives it independently to three investigator models, runs a fourth adjudication/red-team pass, and stages a casefile for Nolan the next morning. It writes to the existing investigations schema, not a new pile of markdown.
- **Two loves:** It simultaneously develops the photo's history and advances named face hypotheses. Every accepted claim improves both the public archive and future matching context.
- **New now:** GPT-5.6 Sol supports image input, structured output, long context, and agentic tool use; Gemini supports large multimodal contexts and batch jobs; Fable 5 is a strong independent long-horizon challenger. The repo already proved same-prompt comparison useful and found Fable best on one anchor case (`docs/ml/ALGORITHMIC_DECISIONS.md:2929-2942`).
- **1–2h session:** Add or improve one bounded case recipe, run it on one real production photo, and leave a complete review packet plus one visible archive delta.
- **Excitement: 10/10.** This makes the loved work the normal nightly output rather than an occasional research spinoff.

#### 2. Event Reconstruction Engine

- **What:** Infer the event before forcing individual identities: cluster photos by visual setting, clothing, attendees, source album, approximate date, and location; then jointly solve who could have attended. An anniversary, wedding, school class, funeral, voyage, or association meeting becomes the unit of reasoning.
- **Two loves:** Events yield history even when a face remains unknown, while shared attendance and age constraints radically narrow face candidates.
- **New now:** Modern VLMs can compare contact sheets and reason over timelines; Rhodesli now has temporal co-occurrence, GEDCOM context, and 1,000+ photos to make cross-photo inference useful (`ROADMAP.md:72-95`).
- **1–2h session:** Build one event bundle of 3–10 photos and produce an attendee matrix, date/place range, contradictions, and next-best identity question.
- **Excitement: 9.5/10.** It converts isolated photos into recoverable community history and creates compounding constraints.

#### 3. Evidence-Backed Biography Compiler

- **What:** Turn accepted case claims into a living dossier: short narrative, dated life events, family links, name variants, photo appearances, quoted/paraphrased testimony, uncertainty, and open leads. Every sentence carries a source and confidence; living-person material stays private by default.
- **Two loves:** A biography is the historical payoff of identification, and the dossier supplies age, kinship, geography, and aliases for future identification.
- **New now:** Long-context models can synthesize heterogeneous evidence without flattening provenance when constrained to a claim ledger. The Menasche prototype shows that one photo and 14 comments can become a substantial family and institutional story (`/Users/nolanfox/rhodes-wiki/wiki/menasche-family-rhodesia.md:21-30,48-87`).
- **1–2h session:** Advance one person's dossier from raw evidence to five sourced claims, one narrative paragraph, and three unresolved questions.
- **Excitement: 9/10.** It makes each face feel like a recovered life, not a label in a classifier.

#### 4. The Skeptical Historian Agent

- **What:** A mandatory adversarial pass that tries to disprove the leading conclusion: checks impossible ages and locations, distinguishes evidence from inference, searches for same-name collisions, proposes the strongest alternative, and identifies what evidence would change the verdict.
- **Two loves:** It makes stories defensible and protects face identification from confident narrative momentum.
- **New now:** Cheap independent challenger runs and structured judge protocols make red-teaming routine. This directly addresses the Detroit failure where retries increased confidence in the wrong New York conclusion (`tasks/lessons.md:247`; `docs/ml/ALGORITHMIC_DECISIONS.md:2779-2805`).
- **1–2h session:** Red-team one existing “solved” case and either certify it with explicit constraints or reopen it with a decisive next test.
- **Excitement: 9/10.** Finding a consequential correction can be as thrilling as finding a name.

#### 5. Research-Value Scheduler

- **What:** Rank the next case by expected historical unlock, not random backlog order: unresolved faces, centrality in family/event graphs, strength of anchors, contradiction risk, witness availability, novelty, and likelihood of yielding several downstream links.
- **Two loves:** It deliberately chooses photos where one answer reveals the most history and identities.
- **New now:** The archive has enough graph structure and stored suggestions to estimate downstream value; agents can execute the selected bounded job unattended. Existing identity suggestions already combine six signals, but family configuration is still Fox-specific (`scripts/compute_identity_suggestions.py:1-17,53-68`).
- **1–2h session:** Score the backlog, inspect the top ten, and complete the top case; the accepted result updates future scores.
- **Excitement: 8.5/10.** Side-project time stops being consumed by deciding what to work on.

#### 6. One-Question Witness Packets

- **What:** At the end of a case, generate one highly targeted, context-rich question for the person most likely to know: annotated crop, candidate names, why the question matters, and a one-tap answer/voice-note link. Never send automatically.
- **Two loves:** Testimony documents lived history and provides high-value identity labels that models cannot infer safely.
- **New now:** The evidence graph can choose the smallest discriminating question; multimodal models can make a clear annotated packet; modern coding agents can produce the mobile review flow in a bounded session.
- **1–2h session:** Create and manually approve one packet, send it through an already-consented channel, and attach the response to the case ledger.
- **Excitement: 9/10.** It turns research dead ends into specific human collaborations instead of generic “help identify” appeals.

### B. Rescue the photo supply without betting the project on Facebook automation

#### 7. “Research Drop” — Consent-First Source Intake

- **What:** A mobile-first intake bundle for a contributor or post author: original photo, reverse side, album context, approximate date/place, permalink, pasted caption/comments, contributor identity, reuse permission, and private/public audience. Accept a share link, upload, email forward, or zipped bundle; hash and deduplicate immediately.
- **Two loves:** It captures the photo *and* the surrounding human history in a form suitable for identification.
- **New now:** VLMs can transcribe backs, normalize names, detect multiple images, and propose structured claims from user-supplied material; coding agents can build resilient ingestion adapters quickly. Rhodes-wiki already defines a rich inbox contract with comments, image metadata, person hints, and handoff state (`/Users/nolanfox/rhodes-wiki/docs/ARCHITECTURE.md:293-398`).
- **1–2h session:** Process one real contributor bundle end-to-end and leave a provenance-complete inbox item plus a reviewable Rhodesli draft.
- **Excitement: 9.5/10.** It restarts the database flywheel while making contributors partners rather than extraction targets.

#### 8. Facebook Author-Export Importer

- **What:** Import a user's own Meta “Download/Export Your Information” JSON or HTML archive offline, show a local preview, and let the user explicitly select posts, comments, and media to donate. Do not log into Facebook, crawl a group, use cookies, or call a hidden endpoint.
- **Two loves:** It recovers a consenting author's captions and conversations alongside their photos, creating both narrative facts and identity evidence.
- **New now:** Structured parsers plus VLM fallback can normalize changing export formats; all model work occurs after the user supplies the archive. Meta documents exports of one's own information and group activity, but notes that another person's shared material may be absent ([Facebook export help](https://www.facebook.com/help/212802592074644), [export-content limits](https://www.facebook.com/help/326826564067688)).
- **1–2h session:** Parse one redacted sample export into the inbox contract, with an explicit selection/consent receipt and no network access to Facebook.
- **Excitement: 7.5/10.** Not glamorous, but it can unlock years of owner-authored source material legally and repeatably.

#### 9. Source-Rescue Campaigns, Not Scraping Campaigns

- **What:** Publish a weekly “mystery with a purpose” card from an existing case and ask the post author, group admin, or family steward to contribute the original and relevant thread under clear reuse terms. Offer a private research result in return. Track response and conversion per case.
- **Two loves:** The public hook is a real historical question; every response can add originals, testimony, and labels.
- **New now:** The factory can produce polished case cards, translations, and personalized contributor requests automatically, while Nolan approves the small number worth sending.
- **1–2h session:** Generate one card and one tailored request from a live case, secure approval, and stage the received evidence through Research Drop.
- **Excitement: 8.5/10.** It turns the archive's discoveries into an ethical acquisition engine.

#### 10. Front/Back/Voice Mobile Scan Station

- **What:** A phone flow for photographing the front, back, album page, and surrounding labels; it dewarps, extracts handwriting, asks for a 30-second spoken memory, and immediately shows candidate people/events for review.
- **Two loves:** The back and voice note preserve history; instant candidates make the scanning session an identification session.
- **New now:** Strong image understanding, speech transcription, and client-side quality checks can give useful feedback before an elder or album leaves the room.
- **1–2h session:** Ship and screenshot-test one vertical slice—front/back capture through a single staged photo record—on desktop and a real mobile viewport.
- **Excitement: 9/10.** It makes family visits productive and captures context that is otherwise permanently lost.

#### 11. Archival Provenance and Original-Fidelity Manifest

- **What:** Give every asset a content hash, source chain, rights/audience state, derivative relationships, resolution history, and “best known original” status. Detect when a Facebook-sized image is only a lead and automatically request the scan.
- **Two loves:** Reliable provenance strengthens historical claims; better originals improve face detection and matching.
- **New now:** Perceptual hashes, OCR, image-quality models, and agent-generated contributor requests make provenance active rather than clerical.
- **1–2h session:** Reconcile one duplicate family of assets, designate the original, and propagate the source chain into its casefile.
- **Excitement: 7.5/10.** Quiet infrastructure, but every later discovery becomes more defensible and every face crop gets better.

**Boundary:** The current JavaScript DOM extractor should not be marketed as TOS-safe. Meta's current terms prohibit automated data collection without prior permission, with separate automated-collection terms requiring express written permission ([Meta Terms](https://www.facebook.com/legal/terms), [Automated Data Collection Terms](https://www.facebook.com/legal/automated_data_collection_terms)). The durable design is contributor-supplied evidence, author exports, and admin/author consent—not a cleverer crawler. This is a product-risk recommendation, not legal advice.

### C. Make face recognition produce discoveries at 3,000-face scale

#### 12. Retrieval 2.0: Exhaustive, Age-Conditioned Identity Search

- **What:** Replace “rerank the baseline top five” with exhaustive exact search across every face and identity prototype, including age-bin prototypes, reciprocal-neighbor evidence, cluster exemplars, and a graph-aware candidate expansion. At ~3,000 faces, brute-force experiments are an advantage, not a performance problem.
- **Two loves:** It is explicitly designed to surface previously unseen identity links; age/event constraints convert those links into historically plausible hypotheses.
- **New now:** The archive now has longitudinal identities, calibrated distances, dates, families, and enough reviewed cases to build hard evaluation slices. Existing cross-batch work already generated 1,355 proposals and revealed father/son ambiguity (`docs/ml/ALGORITHMIC_DECISIONS.md:2639-2648`).
- **1–2h session:** Run one frozen-snapshot variant against the baseline, review its top 20 *new* candidates, and preserve wins/failures as labels.
- **Excitement: 10/10.** Unlike the neutral reranker, it is allowed to find something the old system never proposed.

#### 13. Champion/Challenger Face-Embedding Bake-Off

- **What:** Evaluate buffalo_l against two or three modern, locally runnable face-recognition checkpoints under one frozen harness: identity-held-out, family-held-out, decade gap, occlusion, low resolution, children, profile, and same-family false positives. Keep current embeddings until a challenger wins on discovery-relevant hard slices.
- **Two loves:** Better cross-age retrieval finds relatives across decades; rigorous family-held-out tests prevent attractive but false genealogical stories.
- **New now:** Autonomous agents can reproduce preprocessing, cache embeddings, run ablations, and write failure galleries cheaply. The repo's own audit says the actual model is buffalo_l and some model documentation drifted (`docs/ml/current_ml_audit.md:9-17`).
- **1–2h session:** Add one challenger or one hard slice, run it on the fixed corpus, and publish a visual error gallery plus a go/kill result.
- **Excitement: 8.5/10.** A real model contest is worthwhile; a fashionable model swap without this harness is not.

#### 14. Quality-Aware Multi-Crop Face Ensembles

- **What:** For difficult faces, combine original/aligned, tighter/looser, grayscale, contrast-normalized, and resolution-aware embeddings; weight them by pose, blur, occlusion, and detector quality. Never use generative face restoration as identification evidence.
- **Two loves:** It recovers usable evidence from historically important poor photos while preserving the integrity of the original image.
- **New now:** Quality-conditioned inference is cheap at this corpus size, and agents can build failure-specific ensembles rather than one global preprocessing recipe.
- **1–2h session:** Target one failure class, run a bounded crop ensemble, and review only newly promoted candidates with source crops visible.
- **Excitement: 8/10.** It can unlock the hard photos everyone cares about without hallucinating pixels.

#### 15. Calibrated Evidence Fusion, Not a Single Similarity Score

- **What:** Learn a transparent posterior over candidate identity using face distance, rank/margin, age feasibility, co-occurrence, event, family-cluster score, GEDCOM geography, testimony, source reliability, and missingness. Return contributions and contradiction flags; do not auto-confirm.
- **Two loves:** Historical facts become first-class identification signals, and every accepted identity makes later historical inference stronger.
- **New now:** Rhodesli already has most signals independently: isotonic face calibration reached AUC 0.9577 (`docs/ml/ALGORITHMIC_DECISIONS.md:1672-1679`), and Family Cluster Score reached 86% recall/90% precision on a tiny initial set (`docs/ml/ALGORITHMIC_DECISIONS.md:2812-2828`). The opportunity is disciplined fusion with identity/family-held-out validation.
- **1–2h session:** Add or recalibrate one signal on frozen labels, inspect the cases whose ranking changes, and promote only explainable improvements to shadow mode.
- **Excitement: 9.5/10.** This is where genealogy and computer vision stop being separate projects.

#### 16. Active Learning by Historical Unlock

- **What:** Ask Nolan to label the comparison or candidate whose answer is expected to unlock the most cases—not simply the pair nearest a threshold. Reward breaking ambiguous clusters, separating relatives, spanning decades, and resolving central event attendees.
- **Two loves:** Each small review decision is selected for maximum downstream identities and historical connections.
- **New now:** An offline diversity-aware review queue already exists conceptually (`docs/ml/ALGORITHMIC_DECISIONS.md:2549-2572`); graph centrality and case-value estimates can now improve its objective.
- **1–2h session:** Generate a 10-decision queue, time the review, then report how many cases/edges each answer unlocked.
- **Excitement: 8.5/10.** Ten minutes of human judgment can steer hours of autonomous discovery.

### D. Refresh the investigator stack, then make it compete

#### 17. A Living Multimodal Model League

- **What:** Replace hardcoded provider names with a versioned investigator contract and golden case suite. Run a scout, two independent investigators, and a judge; score factual claims, citation correctness, age/date intervals, identity ranking, abstention, cost, latency, and correction under adversarial evidence. Route each task to the current winner.
- **Two loves:** The league measures historical research and face-hypothesis quality on actual Rhodes cases, not generic benchmarks.
- **New now:** The current official choices include GPT-5.6 Sol for frontier visual/agentic work ([OpenAI model page](https://developers.openai.com/api/docs/models/gpt-5.6-sol)), Gemini 3.5 Flash as a stable high-throughput multimodal model and Gemini 3.1 Pro Preview for detailed work ([Gemini models](https://ai.google.dev/gemini-api/docs/models)), plus Fable 5 as an independent architecture/judgment path ([Anthropic announcement](https://www.anthropic.com/news/claude-fable-5-mythos-5)). Gemini Batch offers 50% cost for non-urgent jobs ([Batch API](https://ai.google.dev/gemini-api/docs/batch-api)).
- **1–2h session:** Add one model/version or one golden case, run the league, and update routing only if the evidence changes. First remove the anchor-comparison route's hardcoded legacy `gemini-2.0-flash` (`app/estimate_routes.py:2153-2156,2262`) and the orchestration script's fixed three-model assumptions (`scripts/multimodel_photo_estimate.py:152-200`).
- **Excitement: 9/10.** Frontier improvement becomes a continuously harvested asset instead of a periodic migration project.

#### 18. Research Tools for Agents, Not Bigger Prompts

- **What:** Give investigators narrow tools: query a person's dated photo appearances, render a contact sheet, traverse family/event edges, search approved sources, compare face crops, inspect image metadata, and write cited claims. The orchestrator assigns bounded hypotheses; models do not receive an undifferentiated data dump.
- **Two loves:** Tools let agents substantiate history and test identity hypotheses against the entire local archive.
- **New now:** Programmatic tool calling and multi-agent orchestration are now first-class in current frontier APIs; the repo's full evidence often exists but previously failed to reach the model—only 17 of 136 estimates initially received enriched GEDCOM context (`docs/ml/ALGORITHMIC_DECISIONS.md:1770-1785`).
- **1–2h session:** Add one read-only evidence tool and prove on one case that it changes or appropriately strengthens a conclusion, with the tool trace stored.
- **Excitement: 9/10.** This converts models from articulate guessers into archive-native investigators.

### E. Rebuild the experience around detective work

#### 19. The Detective Desk

- **What:** One responsive investigation surface: deep-zoom photo and face strip; candidates with comparable crops; event/date/place timeline; GEDCOM and co-occurrence graph; testimony/source excerpts; model disagreements; contradiction panel; and a fixed gatekeeper action bar. Desktop uses a resizable split view; mobile turns the same state into a swipeable evidence stack.
- **Two loves:** Historical research and identification become one coherent act instead of separate admin pages.
- **New now:** Coding models are now strong enough to implement and visually verify a bounded frontend island rapidly. The data model already supports investigations, references, candidate rankings, signal summaries, and outcomes (`scripts/migrations/create_identification_investigations.sql:16-60`).
- **1–2h session:** Improve one complete case interaction from evidence load through staged decision, and require before/after desktop and mobile screenshots plus a real production-like record.
- **Excitement: 10/10.** This is the interface that makes Nolan want to open Rhodesli after work.

#### 20. Publishable Casefiles and Open Mysteries

- **What:** Convert approved private investigations into elegant public story modules: what the photo shows, what is known, how it is known, uncertainty, connected people/photos, and one useful open question. Keep living-person and restricted evidence private; expose conclusions without model plumbing.
- **Two loves:** Every identification becomes documented history, and every open mystery can attract precise new identity evidence.
- **New now:** The existing public photo presentation is already strong (`docs/fable-eval/SITE_VISION_AUDIT.md:8-19`); structured case ledgers let models draft consistent narratives and citations without inventing a second CMS.
- **1–2h session:** Publish one approved casefile, validate it on desktop/mobile, and generate its contributor-safe mystery card.
- **Excitement: 9/10.** The visible database grows in depth after every investigation, which is the progress Nolan actually wants to see.

#### 21. Autonomous “Museum Pass” UX Repair

- **What:** Give a coding agent one real journey and two viewport contracts per session. It reproduces the defect, implements the smallest coherent repair, captures screenshots, and verifies the real backing data—not mocks alone. Prioritize Detective Desk, intake, compare, and case publication.
- **Two loves:** It removes friction exactly where history is entered or identities are decided.
- **New now:** Visual computer-use models can inspect layouts and iterate, but the harness must demand screenshot evidence; the repo has repeatedly learned that a browser-reported pass without screenshots is theater (`tasks/lessons/harness-lessons.md:54-57`).
- **1–2h session:** One journey ends observably better on desktop and mobile, with before/after evidence and no unrelated redesign.
- **Excitement: 7.5/10.** It makes frontend work satisfying because each repair unlocks a real research action.

## 4. Kill list: stop paying for optionality before discovery

1. **Deprioritize broad multi-tenant platform work.** Pause the generic workspace/tool suite (`WORKSPACE-002` through `006`, broad community self-service) until three non-Fox/Rhodes families complete ten investigations through a concierge version. Current roadmap completion percentages are not evidence of repeat demand (`ROADMAP.md:97-131`). Keep isolation/privacy invariants, not platform expansion.

2. **Deprioritize analytics, SEO, counters, and funnel polish.** Instrument the six discovery-ledger outcomes, but do not spend a phase optimizing visitors before the archive repeatedly produces a story worth returning for. The prior growth bets led with analytics/SEO and trust surfaces (`docs/fable-eval/GROWTH_10X.md:26-68`).

3. **Kill automated Facebook DOM extraction as a critical path.** Freeze crawler/extension sophistication absent Meta's written permission. Maintain a manual evidence-packet fallback, but invest in Research Drop, owner exports, author/admin consent, and source-rescue outreach.

4. **Stop PRD-038 Phase 5 as “collect more labels and rerun the same reranker.”** The architecture cannot discover outside the top-five shortlist and produced zero changed predictions (`docs/ml/ALGORITHMIC_DECISIONS.md:2618-2627`). Spend the next ML cycle on Retrieval 2.0; reuse the labels there.

5. **Deprioritize pgvector and scale infrastructure.** At roughly 3,000 embeddings (`ROADMAP.md:263`), exhaustive local comparison is cheap and scientifically useful. Add vector infrastructure when measured latency or corpus size requires it, not because it completes a platform diagram.

6. **Deprioritize a generic chatbot, natural-language explorer, and standalone tool marketplace.** They mediate access to an archive that is not yet deep enough. First make agents produce accepted casefiles; later, chat can read the resulting claim graph.

7. **Do not launch a framework-wide frontend rewrite.** The roadmap itself says the migration trigger has not fired (`ROADMAP.md:121-123`). Build the Detective Desk and intake as coherent islands in the current system, extracting components only where the workflow forces it.

8. **Move security from “phase” to interrupt lane.** P0 auth, consent, privacy, data-loss, and cross-tenant faults preempt everything. Routine hardening gets a bounded maintenance budget. Security is a survival constraint, not the source of weekly motivation.

9. **Stop indiscriminate batch re-analysis.** No photo gets an expensive frontier pass without a named hypothesis, evidence packet, expected historical unlock, and a destination in the Discovery Ledger. The Detroit case shows that another confident pass can compound an error rather than resolve it (`docs/ml/ALGORITHMIC_DECISIONS.md:2779-2805`).

## 5. Top three: start Monday

### Monday 1 — Produce the first Nightly Investigation casefile

Choose one unresolved, high-value photo with at least one confirmed/GEDCOM-linked anchor and at least one unknown or disputed person. Opus gives the same full evidence contract independently to Gemini 3.1 Pro, GPT-5.6 Sol, and Fable 5; Opus reconciles the returned artifacts, while Fable's separate Skeptical Historian pass attacks the leading conclusion. Nolan reviews only the disagreements and proposed database changes.

**First-session definition of done:** one real `identification_investigations` record; immutable model candidates and tool traces; a cited claim ledger; a leading identity/date/place conclusion with strongest alternative; three decisive next actions; cost/time recorded; and at least one staged, visibly rendered story or identity delta. Nothing auto-confirms. Verify the actual stored record and rendered case, not merely test output.

### Monday 2 — Run Retrieval 2.0 against a frozen production snapshot

Build no new learned model initially. Compare current baseline retrieval with exhaustive all-face/all-identity search, age-bin identity prototypes, reciprocal-neighbor evidence, and quality-aware multi-crop scoring. Evaluate decade-gap, child/adult, occlusion, profile, and family-held-out slices; then manually inspect only candidates the baseline never surfaced.

**First-session definition of done:** one reproducible report with Recall@1/5/20 and same-family false-positive rate by hard slice; a visual gallery of the top 20 novel candidate pairs; at least ten plausible new review items or an explicit kill result; and all human decisions returned as reusable training/evaluation labels. No production threshold changes.

### Monday 3 — Prove Research Drop on the existing Menasche source packet

Use the existing Menasche material as the first consent/provenance-shaped bundle: original/front/back if available, source permalink, pasted caption and comments, author/contributor, reuse/audience choice, content hash, extracted people/claims, and handoff preview. The aim is to prove the contract without touching Facebook.

**First-session definition of done:** one bundle round-trips into the rhodes-wiki inbox schema and a Rhodesli review draft; duplicates are detected; every claim points to supplied evidence; private/public audience is explicit; the approval view works at a mobile viewport; and the run makes zero automated Facebook requests. End with a reusable contributor request template for the missing original or context.

These three should run as a loop, not parallel programs: Research Drop supplies better evidence; Retrieval 2.0 proposes cases; the Investigation Factory resolves and publishes them; published mysteries recruit the next Research Drop.

## 6. Where I disagree with the premise

1. **Facial recognition has not failed scientifically; it has failed to cash out as discovery.** Isotonic calibration at AUC 0.9577, cross-batch proposal generation, temporal co-occurrence, and Family Cluster Score are real progress (`ROADMAP.md:72-95`; `docs/ml/ALGORITHMIC_DECISIONS.md:1672-1679,2812-2828`). The mistake is judging the program by model sophistication while users experience only confirmed names. Change the objective and retrieval architecture before declaring the stack stagnant.

2. **More photos and more users are not prerequisites for months of valuable work.** The current 1,127-photo archive and roughly 3,000 embeddings are large enough for event reconstruction, longitudinal retrieval, family false-positive analysis, and dozens of casefiles. Supply matters, but the existing backlog is already an under-mined research corpus.

3. **Facebook friction is not only a tooling problem.** The desire for a seamless extractor conflicts with platform terms and with the privacy/provenance obligations of family testimony. A “better scraper” would not solve consent, rights, missing originals, living-person sensitivity, or source quality. The correct product move is to redesign acquisition around willing stewards.

4. **Frontier multimodal models will not make autonomous historical conclusions safe.** Three models disagreed on the 1946 anchor photo, and historical context—not visual confidence alone—broke the tie (`docs/ml/ALGORITHMIC_DECISIONS.md:2732-2742`). The system should autonomously assemble, test, and stage evidence; humans remain the gate for identity and publication.

5. **A full-site UX rebuild is too broad.** The public photo experience is already strong. The high-return rebuild is the missing investigative cockpit and intake path, followed by end-to-end mobile verification. Repainting every page would reproduce the same drift under a more attractive banner.

6. **“A whole database of Rhodesli photos” should not be defined by photo count.** A complete archive is a graph of originals, appearances, events, places, claims, sources, contradictions, rights, and unanswered questions. Ten deeply connected photos can recover more history than a thousand context-free Facebook downloads.

## Final bet

For the next 30 days, Rhodesli should make one promise: **Nolan wakes up to one case worth opening.** If the system can produce 20 reviewed casefiles, five defensible identity confirmations/corrections, 50 sourced historical claims, three reconstructed events, and five useful witness responses, re-engagement will not require motivation tricks. The archive itself will be changing fast enough to pull him back.

If it cannot, do not add tenants, tools, or traffic. Inspect the failed cases, improve the evidence and retrieval loop, and run it again.
