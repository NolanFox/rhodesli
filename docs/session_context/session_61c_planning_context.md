# Session 61C Planning Context
# "GEDCOM-Enriched Analysis + Flash vs Pro"

## Source: Claude research conversation, Feb 22, 2026
## Breadcrumbs: 61 → 61B (verify/optimize) → 61C (this session)
## Parallel: Designed to run simultaneously with Session 62 via git worktree

---

## 1. PARALLELIZATION DESIGN — CAN RUN WITH SESSION 62

### Confirmed: Yes, 61C and 62 Can Run Simultaneously
Session 61C (ML analysis, scripts, GEDCOM, docs) and Session 62
(PRD-015 face alignment, app code) touch different files. Git
worktrees give each session its own working directory and branch.

### File Ownership
| File/Directory | 61C Owns | 62 Owns | Shared (merge carefully) |
|----------------|----------|---------|--------------------------|
| rhodesli_ml/gemini_extraction.py | ✓ | | |
| rhodesli_ml/gedcom_context.py | ✓ (new) | | |
| scripts/compare_models.py | ✓ | | |
| scripts/gedcom_enrichment.py | ✓ (new) | | |
| results/ | ✓ | | |
| app/main.py | | ✓ | |
| app/templates/ | | ✓ | |
| ROADMAP.md | | | ✓ |
| BACKLOG.md | | | ✓ |
| CHANGELOG.md | | | ✓ |
| docs/ALGORITHMIC_DECISIONS.md | ✓ (append) | ✓ (append) | ✓ |
| docs/session_context/ | ✓ (61c files) | ✓ (62 files) | |
| tests/ | ✓ (ML tests) | ✓ (app tests) | |

### Merge Strategy
- 61C merges FIRST (smaller scope, ML-only, lower conflict risk)
- 62 merges SECOND, resolving any shared doc conflicts
- Both sessions append-only to shared docs (no rewriting)
- If conflict in ADs: 62 takes higher AD number

---

## 2. GEDCOM-ENRICHED GEMINI ANALYSIS — RESEARCH + DESIGN

### The Hypothesis
Feeding GEDCOM-derived temporal-spatial data to Gemini alongside a
photo should improve date estimation, location identification, and
overall analysis quality. Five variants tested from zero to maximum
contextual enrichment.

### Evidence It Works (Nolan's Direct Experience)

**Albert Fox example:**
- Photo of great-grandfather with siblings, location unknown
- Fed all known residences: Minsk, New York, Detroit, Ohio + birthdate
- Gemini identified the SPECIFIC BUILDING and found corroborating
  old photographs of the same building
- This is the workflow we want to approximate at scale

**Big Leon + Victoria wedding photo:**
- Known: married in Atlanta, approximate date
- If Gemini had these facts + saw formal wedding attire →
  high-confidence inference that this is the Atlanta wedding photo
- This inference is impossible without GEDCOM context

### Five GEDCOM Enrichment Variants

| Variant | Context Included | Example |
|---------|-----------------|---------|
| A: None | Visual analysis only — no GEDCOM | Baseline control |
| B: Full Person | All GEDCOM events for identified people | Birth, death, all residences, marriages, immigration, occupation |
| C: Curated Person | Only location/time-relevant events (±15yr of estimated date) | Residences near estimated photo date, marriages, immigration |
| D: First-Order | Variant B + all events for immediate family (parents, siblings, spouse, children) | Big Leon in photo → include son Nace's Tampa marriage (could ID wedding photo location) |
| E: First-Order + Photo Co-occurrence | Variant D + all events for anyone sharing ANY photo with identified people | Treats sharing a photo as a connection — someone in 5 photos with Big Leon gets their GEDCOM included |

### Token + Cost + Time Tracking (CRITICAL for D and E)

| Variant | Est. Tokens/Photo | Est. Cost/Photo (Pro) | Latency Risk |
|---------|------------------|-----------------------|--------------|
| A: None | ~800 | $0.028 | Baseline |
| B: Full Person | ~1,500 | $0.030 | Low |
| C: Curated | ~1,200 | $0.029 | Low |
| D: First-Order | ~3,000-8,000 | $0.034-0.044 | Medium — large families |
| E: Co-occurrence | ~5,000-20,000 | $0.038-0.068 | HIGH — well-connected people |

**Variant E risk**: Big Leon appears in many photos. Everyone in those
photos gets their GEDCOM included. If 30 people share photos with him,
that's ~30 × ~500 = 15,000 extra tokens. Cost is still only ~$0.03
extra. The REAL risk is context noise drowning signal — extra data
may CONFUSE the model. Must track quality impact, not just cost.

**Must log per-call**: input_tokens, output_tokens, wall_clock_seconds,
cost, model, variant, photo_id. This data goes to both MLflow AND
Supabase for permanent record.

### 2×5 Comparison Matrix

| | None (A) | Full (B) | Curated (C) | 1st-Order (D) | Co-occur (E) |
|---|---|---|---|---|---|
| **Flash** | A1 | B1 | C1 | D1 | E1 |
| **Pro** | A2 | B2 | C2 | D2 | E2 |

10 runs × 20 photos = 200 API calls.
**Estimated total: ~$4.25** (well within $10 budget).

### Photo Selection for 20-Photo Subset
- 5 with confirmed IDs linked to GEDCOM (test enrichment)
- 5 with confirmed IDs but NO GEDCOM link (control)
- 5 with high-match unconfirmed IDs (test partial enrichment)
- 5 with NO identified faces (pure visual baseline)

Photos without GEDCOM links produce identical results across B-E
(no data to inject), confirming the baseline is stable.

---

## 3. GEDCOM DATA STORAGE — DATABASE DESIGN

### Problem
Re-parsing the full GEDCOM file for every API call is slow and wasteful.
Parse once, store in Supabase, query fast.

### Schema

```sql
-- Parsed GEDCOM individuals
CREATE TABLE gedcom_individuals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    gedcom_id TEXT NOT NULL,         -- "@I123@"
    name TEXT NOT NULL,
    birth_date TEXT,
    birth_place TEXT,
    death_date TEXT,
    death_place TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- GEDCOM events (residences, marriages, immigration, etc.)
CREATE TABLE gedcom_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    individual_id UUID REFERENCES gedcom_individuals(id),
    event_type TEXT NOT NULL,        -- RESI, MARR, IMMI, EMIG, OCCU
    date TEXT,
    place TEXT,
    description TEXT,
    source TEXT
);

-- Link Rhodesli faces → GEDCOM individuals
CREATE TABLE gedcom_face_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    face_id TEXT NOT NULL,
    gedcom_individual_id UUID REFERENCES gedcom_individuals(id),
    confidence FLOAT,
    linked_by TEXT,                   -- "admin" | "auto-match" | "community"
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Family relationships (for first-order connections)
CREATE TABLE gedcom_relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    individual_id UUID REFERENCES gedcom_individuals(id),
    related_individual_id UUID REFERENCES gedcom_individuals(id),
    relationship_type TEXT NOT NULL   -- parent, child, spouse, sibling
);
```

### Query Patterns
- **Variant B/C**: Events for identified person only
- **Variant D**: + events for all related individuals
- **Variant E**: + events for all people sharing any photo (join
  through face_links → photos → other faces → face_links → individuals)

### Import Flow
1. Parse GEDCOM once → populate all 4 tables
2. Fuzzy-match names to existing Rhodesli faces
3. Admin reviews/confirms links
4. Future: auto-link when new identifications are made
5. GEDCOM file location: ~/Downloads/*.ged

---

## 4. 61B ASSESSMENT — ITEMS FOR 61C TO ADDRESS

From `session_61b_assessment.md` "Next Session Should Verify":
1. ✅ ENOSPC fix persists → Phase 0 verify
2. ✅ Flash vs Pro comparison → Phases 3-5 (now with 5 GEDCOM variants)
3. ⏭️ Platt scaling (AD-145 Stage 1) → DEFERRED to Session 63
   Rationale: depends on Flash vs Pro results informing the pipeline.
   Must be tracked in BACKLOG with breadcrumb.
4. ⏭️ UX-130 visitor homepage → DEFERRED to Session 62 or 63
   Rationale: app-level UX change, not ML scope for 61C.
   Must remain in BACKLOG.

Other loose ends from 61B:
- Duplicate HD-015 numbering → fix in Phase 0
- Quick-identify CSS crash → explicit verify in Phase 0
- UX-130/131/132 in BACKLOG → verify present in Phase 0

---

## 5. ENGAGEMENT VIRTUOUS CYCLE (from GEDCOM enrichment)

```
More GEDCOM data → Better Gemini analysis → More interesting results
→ Users share results → More people contribute → More identifications
→ More GEDCOM links → Even better analysis → ...
```

### Feature Ideas (log to BACKLOG, don't implement in 61C)
- "This analysis improved because [User] confirmed [Person]" UX
- "High-match popup": upload → >70% match → "Is this [Person]?" →
  confirmed → load GEDCOM → enriched re-analysis
- Batch re-analysis when new identifications accumulate
- Currently uploads don't auto-add to clusters; popup is manual bridge

---

## 6. APP THESIS REMINDER

From Nolan's words:
- Help people **identify** photos / people
- **Share** photos to ask for help identifying
- Help people **find relatives** they didn't know existed
- **Solve mysteries** through photo context (Albert Fox = this)
- **Deepen understanding** through annotation + community knowledge
- **Systematize** what happens ad-hoc on Facebook groups

GEDCOM enrichment directly serves: mystery solving, deepening
understanding, and the engagement virtuous cycle.
