# Sol critique — round 2

**Date:** 2026-07-13  
**Role:** Critic, not plan author

## 1. Verdict on the four-track Research Desk

**AGREE-WITH-CHANGES.**

The four tracks are a good map of the territory and a bad way for one person to execute it. If they become four active workstreams, this program will reproduce the exact failure it is meant to fix: impressive infrastructure, many half-finished surfaces, and no reliable historical payoff.

Required changes:

1. **Treat the tracks as lanes, not parallel programs.** The WIP limit is one live case plus one enabling task. Track 1 owns the critical path. Track 2 and Track 4 contribute the minimum evidence contract and review surface needed by that case. Track 3 gets one bounded candidate-generation session, then waits until the case loop works.
2. **Move the model/provider registry out of “The stage.”** Routing, budgets, retries, schemas, and model-version logging are engine concerns. Track 4 should contain only human-facing review and publication.
3. **Split “connector” into three legally different operations:** discover a lead, retain/analyze evidence privately, and republish an asset or claim. Permission for one is not permission for the others. The rights state must be machine-enforced, not a prose note.
4. **Cap the morning product at one dossier and at most three human decisions.** “5–15 one-tap proposals” is queue bankruptcy disguised as convenience. The dossier can contain many observations; only the few decisions that materially advance the case should enter Nolan's queue.
5. **Set a hard per-run budget and degrade gracefully.** Default target: no more than $2 before human opt-in. Use a cheap scout and one principal investigator; invoke the expensive challenger only for disagreement, high-value cases, or audit sampling. The proposed three investigators plus a fourth adjudicator should not be the default.
6. **Replace the 30-day scorecard.** Twenty reviewed casefiles is incompatible with a month that also has to build the factory. A credible pilot bar is: six reviewed dossiers, at least three judged worth opening, median review under 15 minutes, at least one accepted historical delta in three cases, two consecutive clean unattended runs, and measured cost under the declared cap. Twenty is a later throughput target, not a launch target.

## 2. Rulings on contested points

### 2.1 Public-archive connectors: **REBUT the “biggest gap” claim; ACCEPT a narrower source-discovery lane**

Sol did underweight systematic external research. That is a real gap. But “publicly searchable,” “citable,” “machine-accessible,” and “reusable in Rhodesli” are not synonyms. Most of Fable's list is useful for targeted research and unusable as an autonomous ingestion source. The biggest immediate gap is still the case/evidence/review contract. Connectors cannot rescue a factory that cannot produce or cheaply review one good casefile.

Source-by-source ruling:

| Source | Feasibility and rights reality | Ruling |
|---|---|---|
| Rhodes Jewish Museum / RJHF | The collection is mission-aligned and likely uniquely rich, but the site presents a collection, not a documented public API or open reuse license. Much material came from family contributors, so the institution's ability to display it does not automatically grant Rhodesli reuse or face-analysis rights. | **Partnership target, not scraper.** Ask for a metadata export, cross-linking agreement, and explicit item-level analysis/publication terms. This could be the highest-value relationship on the list. |
| Yad Vashem | Rich for Holocaust-era Rhodes leads, transport history, names, and some photos. Records carry archival signatures, sources, and credits, often to third parties. I found no documented public bulk API or blanket reuse license. | **Targeted lead/citation source only** until Yad Vashem grants an export or reuse path. Do not bulk-copy images or run face analysis merely because the catalog is public. |
| USHMM | Excellent catalog and item-level download/licensing workflow, but rights vary by item and may include donor, privacy, publicity, and contractual restrictions. Its current terms also prohibit using Museum content to train, fine-tune, or otherwise develop ML/AI systems without written consent. ([rights guidance](https://www.ushmm.org/collections/ask-a-research-question/rights-and-reproductions), [terms](https://www.ushmm.org/copyright-and-legal-information/terms-of-use)) | **Metadata links and manual research are feasible. Automated VLM/face processing or republication requires item review and, conservatively, written permission.** Not a bulk connector. |
| JDC Archives | Genuinely relevant: its finding aids include Rhodes communal records. But publication/reproduction permission is one-time, may carry fees, web photos are limited to 72 dpi, and reuse requires new permission. ([JDC terms](https://archives.jdc.org/our-collections/terms-and-conditions-for-uselicense/)) | **Finding-aid and lead connector at most.** Request documents for named cases; do not mirror batches. It is more promising for historical claims than for expanding the face-photo corpus. |
| ANU Museum | Rich in Rhodes diaspora community and family-tree material, including user-generated trees. Its terms explicitly say a user may not create another database from ANU's database and restrict copying/publication absent permission. ([ANU terms](https://dbs.anumuseum.org.il/skn/en/c6/e18493717/%D7%90%D7%95%D7%93%D7%95%D7%AA/Terms_of_Use)) | **Manual research only unless ANU authorizes an integration.** Particularly unsafe as an automated genealogy import because user-generated trees are evidence leads, not ground truth. |
| UW Stroum / UW Digital Collections | Technically the best candidate: CONTENTdm exposes machine-readable endpoints, and the collection contains Rhodes-born performers and Rhodes-family oral histories. Rights are still item-specific; a Rhodes item I checked is marked “Copyright Not Evaluated” and directs permission inquiries to the program. ([example record](https://digitalcollections.lib.washington.edu/digital/collection/p16786coll3/id/3301/)) | **Build a metadata/link proof of concept only.** Preserve the RightsStatements URI and never assume the media itself is republishable. This is a plausible first institutional discovery adapter. |
| JewishGen | Valuable for finding names and records, weak as photo supply. Its own interfaces deliberately block broad result retrieval to deter data mining, and component datasets have separate donor/transcriber copyrights. ([JOWBR FAQ](https://www.jewishgen.org/databases/Cemetery/JOWBR_FAQ.htm)) | **Human query tool, not connector.** Seek collaboration or a sanctioned export for a narrowly defined Rhodes project. |
| Ellis Island / ship manifests | The Statue of Liberty-Ellis Island Foundation's terms prohibit incorporating its heritage documents and records into another database. NARA is the cleaner source: federal records are often public domain, but catalog coverage is incomplete and passenger records remain restricted for 75 years. ([Foundation terms](https://kiosk-dtdev.statueofliberty.org/terms-of-use), [NARA access](https://www.archives.gov/research/immigration/passenger-arrival.html), [NARA rights](https://www.archives.gov/global-pages/privacy.html)) | **Use NARA for targeted records and links.** Do not build against the Foundation site. Expect manual ordering or partner-site gaps, not nightly autonomous supply. |
| Find a Grave | It is an Ancestry service. Current Ancestry terms prohibit access that exceeds normal human use, prohibit using service content with ML/AI, limit external use, and require permission for more than a small number of even public-domain photos/documents. ([Ancestry terms, §§1.3 and 2.2](https://www.ancestry.com/c/legal/termsandconditions)) | **Manual lead source only. No connector and no automated image analysis.** A memorial contributor's photo is not ownerless. |
| Newspapers | “Newspapers” is not one rights class. Newspapers.com is covered by the same restrictive Ancestry terms. By contrast, Library of Congress Chronicling America has an official API and material the Library believes public-domain or free of known restrictions, with item caveats. ([API](https://www.loc.gov/apis/additional-apis/chronicling-america-api/), [rights](https://www.loc.gov/collections/chronicling-america/about-this-collection/rights-and-access/)) | **Chronicling America is the best first real connector.** Newspapers.com remains manual. Coverage and OCR quality mean this will enrich cases, not replace paid/local newspaper research. |

So: accept “approved-source research” as a gap, reject “institutional archives are TOS-clean bulk supply.” The first source work should be a rights registry plus one Chronicling America or UW metadata adapter, not nine connectors.

### 2.2 HTR/verso sweep exemption: **ACCEPT-WITH-CONDITIONS**

Fable is right that literal transcription is evidence extraction, not historical conclusion generation. It need not have a named identity hypothesis. It still needs an artifact, budget, and review destination. “Extraction” does not make a 1,127-item frontier run automatically useful.

The repository weakens the proposed sweep as stated. The local `data/photo_index.json` snapshot contains no populated `back_image` fields, while `rhodesli_ml/data/date_labels.json` already has 359 analyzed photos and 164 non-null `visible_text` strings. Production may differ, but the first task is an inventory: which backs actually exist, which fronts already have OCR, and which assets have never been analyzed. A “verso sweep” cannot read backs that were never captured.

The exemption should be:

- hash/idempotency based: never re-run a completed asset/model/prompt tuple;
- cheap first pass, with a hard corpus budget (start at $20, not “frontier by default”);
- verbatim transcription, language/script, bounding region, and uncertainty only—no auto-normalized person, date, or kinship claim;
- a 50-image stratified pilot before corpus scale, including blank fronts, known inscriptions, poor handwriting, and Solitreo;
- promoted to human review only when text is likely genealogically useful or two passes disagree;
- written to an evidence-extraction ledger, never directly to confirmed metadata.

At a plausible batch shape of 2,000 input tokens and 1,000 output/thinking tokens per image, 1,127 images on Gemini 3.5 Flash Batch would be about **$6.76** at current rates; three orientations/crops would be about **$20.28**. API spend is not the main risk. If just 10% produce review candidates, 113 items at 2–5 minutes each create **3.8–9.4 hours** of human work. The promotion threshold matters more than the OCR bill.

### 2.3 Screenshot-native Research Drop: **ACCEPT as a private lead type; REBUT it as archive-ready ingestion**

Manual screenshots avoid automated Facebook collection. They do not create publication rights, contributor consent, an original-quality photo, or permission to disclose commenters' words and names to model providers.

A screenshot may enter Research Drop only with:

- `capture_method=screenshot`, capture time, source permalink, capturing member, visible author/commenter names, and the group/audience context;
- `rights_state=unknown` and `audience=private_research` by default;
- a prominent “lead quality, not archival original” state; no face embedding or public photo record from a UI crop unless separately authorized;
- author/steward consent and a request for the original image before public use;
- multiple ordered frames where comments are involved, with explicit detection of truncation, overlays, missing replies, and duplicate frames;
- a policy for redacting living-person data before third-party model calls when it is not necessary to the case.

This is still worth building. Fifteen-second capture can restart intake. But “a member may screenshot it” answers only the capture-mechanism question. It does not answer copyright, privacy, fidelity, or downstream-use questions.

### 2.4 Mining session docs: **ACCEPT as lead recovery; REBUT “day-one publishable”**

Session docs are a map of prior work, not a historical source. They mix model-authored prose, user statements, transient production observations, copied source snippets, uncited conclusions, and sometimes superseded errors. Publishing a biography because an internal session document says it is true would launder model memory into apparent evidence.

Mine them for:

- named unresolved cases and candidate identities;
- source URLs, archive identifiers, quotes that need source recovery, and witness names;
- contradictions between sessions;
- claims marked “researched” but absent from the structured ledger.

Every recovered claim must then point to the original source, be rechecked, receive a rights/audience state, and pass the same human gate as new research. The Fox/Heft material is excellent seed data precisely because Nolan can recognize errors quickly; it is not zero-research publication inventory.

## 3. Attack: five likely failure modes

### 1. The review queue becomes the new unlabeled-face backlog

Twenty casefiles at Fable's 5–15 proposals each produce **100–300 decisions**. Even at an unrealistically brisk 2–5 minutes per evidence-bearing decision, that is **3.3–25 hours**. The promised 10 minutes on 20 mornings supplies only **3.3 hours**, enough for 40–100 decisions. At the median—10 proposals, 3 minutes each—the program creates 10 hours of review and budgets 3.3.

The failure will not look dramatic. Nolan will skip two mornings, the queue will stop feeling current, and accepting a claim will become cleanup. Enforce the three-decision cap and expire/re-rank stale proposals; never measure success by proposals generated.

### 2. Multi-model unit economics drift from “cheap nightly” to a real subscription-sized bill

At current list prices, GPT-5.6 Sol is $5/$30 per million input/output tokens, Gemini 3.1 Pro is $2/$12 under 200k, and Fable 5 is $10/$50. ([OpenAI models](https://developers.openai.com/api/docs/models), [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing), [Fable pricing](https://platform.claude.com/docs/en/about-claude/pricing))

For an 80k-input/12k-output case:

- Sol: **$0.76**;
- Gemini 3.1 Pro: **$0.304** standard or **$0.152** batch;
- Fable 5: **$1.40**;
- a Fable judge reading 120k and producing 12k: **$1.80**.

That is **$4.11–$4.26 per night** before orchestration, search/tools, failed calls, and retries; 20 runs cost **$82–$85**. A 200k-input/20k-output case plus a 260k-input Fable judge is about **$8.84** before overhead, or **$177** for 20 runs. Fable also uses always-on adaptive thinking and a tokenizer that its docs say emits roughly 30% more tokens for the same text, so hand estimates will systematically understate spend.

The fix is routing, not merely logging: cheap extraction/scouting, one principal, conditional challenger, cached immutable packets, and a hard stop that produces a partial casefile rather than retrying through the budget.

### 3. The harness produces broken mornings often enough to destroy trust

A run has roughly twelve failure points: selection, production snapshot, asset fetch, evidence assembly, three provider calls, adjudication, schema validation, durable write, render, and notification. Even granting an independent **98%** success rate per point, end-to-end success is `0.98^12 = 78.5%`. At **95%**, it is `0.95^12 = 54.0%`. Over 20 runs, that means roughly **4–9 broken mornings**. Provider outages and schema changes are correlated, so independence is generous.

Preview model retirement, token-limit changes, an inaccessible R2 asset, malformed structured output, partial database writes, and retry duplication are where it will actually break. The runner needs checkpoint/resume, idempotency keys, immutable inputs, per-provider timeouts, one fallback path, and notification only after the stored artifact re-reads and validates. A model's “done” message is not a checkpoint.

Also, three models reading the same wrong source packet are not independent witnesses. Majority agreement can merely certify a shared premise error.

### 4. Four-track WIP consumes the month before throughput exists

At 4–6 sessions a week, a four-week month contains **16–24 sessions**. A minimal reliable vertical slice will consume about eight sessions before its first unattended result. That leaves **8–16 sessions** for running, repairing, reviewing, intake, and recognition work. Producing 20 reviewed casefiles would require almost every remaining session to yield more than one clean reviewed case, while also shipping the four-track substrate. The arithmetic does not close.

The likely break is context switching: one session adds an archive adapter, the next tunes retrieval, the next repairs mobile, and the runner remains “almost ready.” Enforce the WIP limit and forbid Track 2/3 expansion until two unattended cases survive human review.

### 5. Automation removes the pleasure and leaves only editorial obligation

Both drafts assume Nolan wants to wake up after the mystery has been solved and act as editor-in-chief. The evidence says he enjoyed *conducting* investigations. Those are not the same reward loop. A dossier can feel like a gift; a pile of model prose can feel like homework. Six mediocre dossiers out of 20 is enough to make the morning ritual aversive, even if the pipeline is technically successful.

Measure “worth opening” explicitly and test two outputs: a completed dossier versus an interactive 15-minute mystery that withholds the next inference until Nolan chooses a clue or candidate. If the interactive version wins, the correct autonomy boundary is evidence preparation, not conclusion generation.

## 4. Concrete first-two-weeks sequence

The order below is an eight-session minimum, with two stretch sessions if the week reaches five. At four sessions a week, do not compress it to preserve a Monday-night launch date. A broken first morning will cost more motivation than a one-week delay.

| Session | Track | Required output |
|---|---|---|
| **W1-S1** | 1 — Desk | Choose one existing high-value case with a confirmed anchor and a real unresolved question. Hand-build the ideal morning artifact and write a binary “worth opening” rubric. This defines the product before any orchestration code. |
| **W1-S2** | 1 — Desk | Define the minimal run/case contract: immutable input manifest, atomic claims, evidence IDs, alternatives, contradictions, requested decisions, model/version/tokens/cost, status transitions, and idempotency key. Add schema validation and the rule that no run writes confirmed data. |
| **W1-S3** | 2 — Evidence | Build a read-only evidence-packet assembler for the pilot using only already-held, rights-known material: original image/crops, provenance, known people, GEDCOM dates, co-occurrence, current retrieval candidates, and exact source excerpts. Store checksums and permission dimensions. Produce one known-good packet. |
| **W1-S4** | 3 — Recognition | Freeze the pilot candidate slate. Run the current exhaustive/local retrieval and temporal/family constraints; save ranks and distances as evidence. Add a few assertions that catch impossible-age, wrong-family, and missing-anchor failures. Do not start an embedding bake-off. |
| **W1-S5** | 1 — Desk | Run one investigator against the static packet. Reject any output whose claim cannot cite evidence IDs. Manually score every claim and record false-positive, unsupported, and omitted-evidence classes. Fix the packet/contract, not the prose. |
| **W2-S6** | 1 — Desk | Add a second investigator and conditional skeptical pass. Define disagreement triggers, strongest-alternative requirements, timeouts, and the $2 default cap. Prove that a provider failure still leaves a valid partial artifact. |
| **W2-S7** | 4 — Stage | Render the stored artifact in a minimal admin-only mobile review page: source beside claim, model disagreement visible, accept/reject/unsure, and no more than three requested decisions. Verify a real record on desktop and mobile. No biography compiler or redesign. |
| **W2-S8** | 1 — Desk | Add checkpoints, resume, dedupe, retry limit, kill switch, and artifact re-read validation. Run a full manual dress rehearsal from clean start, time it, and confirm that rerunning the same `run_id` creates no duplicate claims or charges after completed checkpoints. Then schedule exactly one preselected unattended case. |
| **W2-S9 (stretch)** | 1 + 4 | Review the unattended artifact in the morning. Record review minutes, accepted/unsupported claims, cost, failure recovery, and whether Nolan actually wanted to open it. Do not schedule recurrence unless the artifact validates and review stays under 15 minutes. |
| **W2-S10 (stretch)** | 2 — Evidence | Run one supply pilot only: either a 50-image HTR triage or one screenshot Research Drop into a private lead. Do not build a public-archive connector yet. Feed the result into the next named case to prove supply creates case value. |

Before the first unattended run, the non-negotiables are therefore: a real case and acceptance rubric; an immutable rights-aware packet; a validated claim schema; a frozen candidate slate; bounded model routing and cost; a minimal human review surface; and resumable/idempotent execution. A scheduler, research-value scorer, archive connectors, corpus sweep, model league, new embedding model, event engine, biography compiler, email digest, and public casefile are **not** prerequisites.

## 5. What both models missed

1. **The autonomy-boundary experiment.** Both models silently promote Nolan from investigator to reviewer. Test that premise before building a factory. The emotionally correct product may be “prepare the mystery overnight,” not “solve it overnight.”
2. **Permission is multidimensional.** A single `rights_state` is insufficient. Store separate permission for private retention, third-party model processing, face embedding/biometric comparison, quotation, derivative crop, and public republication, plus who granted it and when. A source can permit citation but prohibit every other operation.
3. **External evidence is hostile input.** Web pages, OCR, comments, and archive metadata can contain instructions that an autonomous agent follows as prompt injection. Source text must be data-delimited; tools must be read-only during research; model-authored URLs and archive IDs must be independently validated before storage.
4. **Abstention needs to count as value.** The proposed counters reward accepted claims. A careful “no defensible identification; here is the decisive missing evidence” can be the best historical result. Track unsupported-claim rate, calibrated abstention, overturned conclusions, and review minutes—not only discoveries.
5. **Citation durability is separate from citation presence.** A URL is not preservation. Store retrieval time, item identifier, exact supporting excerpt or region, checksum, and—only when rights allow—a private source snapshot. Otherwise tomorrow's elegant casefile can point to a changed paywall, deleted post, or re-cataloged item.
6. **The golden cases will be overfit immediately.** Fox/Heft and the 1946 anchor are useful smoke tests but will become prompt-development fixtures. Keep a sealed set of cases and family-held-out evaluation; otherwise the model league will measure familiarity with Rhodesli's favorite stories rather than investigative quality.

The program should proceed, but only after losing its assumption that more agents, more sources, more proposals, and more nightly volume are automatically more discovery. For this owner, scarcity is a feature: one strong case, three consequential decisions, and no obligation-shaped backlog.
