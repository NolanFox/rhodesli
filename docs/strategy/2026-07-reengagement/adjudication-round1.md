# Adjudication Round 1 — Fable × Sol convergence map

**Adjudicator:** Fable (with the caveat that I authored one of the drafts; Sol gets a rebuttal
pass on this memo — see `sol-critique.md`).

## Convergent core (both models, independently — treat as HIGH CONFIDENCE, adopt)

| Theme | Fable | Sol | Verdict |
|---|---|---|---|
| Nightly autonomous investigation engine, one case/night, morning review | A1 (10/10) | #1 (10/10) | **The flagship.** Sol's version is better-specified: use existing `identification_investigations` schema, immutable model artifacts, no auto-confirm. |
| Persistent case ledger / case files as first-class objects | A2 | Discovery Ledger + #20 | Adopt Sol's ledger metrics (6 counters: cases advanced, accepted claims, identities confirmed/corrected, photos linked, witness answers, $/accepted claim). |
| Kill FB DOM extraction as critical path; consent-first intake instead | B1 + premise pushback | #7/#8 + Boundary note | Adopt. Sol's TOS reading is stricter and better sourced (Meta automated-collection terms). |
| Multi-model bake-off as *standing infrastructure*, not one-off | C3/D1 | #17/#18 | Adopt Sol's "model league" framing + agent tools over bigger prompts. |
| Eval harness before any embedding change; champion/challenger | C1/C2 | #13 | Identical. Adopt with Sol's hard slices (decade-gap, family-held-out, children, occlusion). |
| Signal fusion (face + age + kinship + co-occurrence + testimony) | C4 | #15 | Identical intent. Sol's calibrated-posterior framing is the right spec. |
| Narrative/publishable output (biographies, casefiles, open mysteries) | D3 | #3/#20 | Adopt both: biography compiler (private-first) + published casefiles. |
| Kill list: multi-tenant, growth phases, funnel/SEO polish, pgvector, chatbots, framework rewrite | Kill list | §4 | Near-identical. Adopt Sol's "security = interrupt lane, not phase." |
| Reranker post-mortem: label gate was the wrong frame; architecture couldn't discover outside top-5 | premise pushback | #12 + Kill #4 | **Sol wins the argument.** Retrieval 2.0 replaces "collect labels, rerun PRD-038." |

## Sol-only ideas — adopt

- **#2 Event Reconstruction Engine** — events as the unit of reasoning. Strong; feeds cases.
- **#12 Retrieval 2.0** exhaustive age-conditioned search. The single best ML move proposed.
- **#4 Skeptical Historian** mandatory adversarial pass (Detroit lesson institutionalized).
- **#5 Research-Value Scheduler** (pick the case with max expected historical unlock).
- **#6 One-Question Witness Packets** (never auto-sent).
- **#8 Facebook author-export (DYI) importer** — offline, consent-explicit.
- **#11 Provenance/original-fidelity manifest** (content hash, source chain, "best known original").
- The operating rule: **no frontier pass without a named hypothesis + evidence packet + ledger destination.**

## Fable-only ideas — for Sol to critique

- **B2 Public-archive connectors** (Yad Vashem, USHMM, JDC, ANU, UW Stroum Sephardic Studies,
  JewishGen, Ellis Island manifests, FindAGrave, newspapers). Sol's supply plan is entirely
  contributor/FB-author-centric; institutional archives are TOS-clean, rich in Rhodes content
  (the archive is only 44% Rhodes today), and citable. I claim this is Sol's biggest gap.
- **B3 Standalone HTR/verso sweep over the existing 1,127 photos.** Sol's kill-rule #9 (no
  indiscriminate batch re-analysis) *seems* to forbid this. My position: OCR/HTR is *evidence
  extraction* (recovering text that exists on the artifact), not conclusion generation — it
  should be exempt from the hypothesis gate. Session 152 found 15+ names on one photo.
- **B1 Screenshot-native ingestion** (phone screenshot → VLM parse → inbox). Sol's #7 Research
  Drop covers contributor bundles; my claim is the *owner's own screenshots* of group posts are
  the practical day-over-day capture path and belong in scope as a Research Drop input type,
  with private-by-default + author-consent-before-publication baked in.
- **Mining existing session docs** (Fox/Heft corpus) for day-one publishable casefiles/bios.

## Divergences resolved by adjudicator (Sol may contest)

1. **UX scope.** Fable said rebuild core-three pages; Sol says Detective Desk + intake islands
   only, then journey-based repairs. **Ruling: Sol.** The mobile-unusable complaint gets fixed
   through Sol #21's journey contract (each session: one journey, two viewports, before/after
   screenshots), starting with the journeys the Desk lands on.
2. **Batch date/location enrichment.** Fable wanted completion across all photos; Sol's gate
   says no. **Ruling: Sol's gate, with the HTR exemption argued above** (pending Sol's rebuttal),
   and with "event-bundle" batch runs allowed when the Event Engine names the hypothesis.
3. **Model effort levels** (from `model-settings-research.md`): Sol at **medium** for bounded
   coding, **high** for case investigation, **xhigh** for adversarial audit/ideation only;
   consider Terra/Luna for bulk mechanical work. Fable at **high** for architecture/judgment,
   **max** only for final adjudications. Opus orchestrates. Token budgets per track, hard.

## Proposed final structure (for Sol's verdict)

**Program name: "The Rhodesli Research Desk"** — 4 tracks:
- **Track 1 — The Desk** (engine): case ledger + nightly investigation factory + morning review
  + skeptical historian + research-value scheduler. [Sol #1,#4,#5 + Fable A1-A3]
- **Track 2 — Evidence supply** (TOS-safe): Research Drop (screenshots, scans, author exports),
  public-archive connectors, HTR sweep, provenance manifest, witness packets, source-rescue
  cards. [Sol #6-#11 + Fable B1-B4]
- **Track 3 — Recognition science**: eval harness → Retrieval 2.0 → bake-off → fusion →
  active learning by historical unlock. [Sol #12-#16 + Fable C1-C4]
- **Track 4 — The stage**: Detective Desk UI, publishable casefiles, biography compiler,
  journey-based mobile repairs, model league plumbing. [Sol #17-#21 + Fable D2-D3]

30-day promise (Sol's final bet, adopted verbatim): *Nolan wakes up to one case worth opening.*
Success = 20 reviewed casefiles, 5 identity confirmations/corrections, 50 sourced claims,
3 reconstructed events, 5 witness responses.
