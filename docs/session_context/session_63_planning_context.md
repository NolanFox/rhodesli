# Session 63 Planning Context
# "Close the Gaps, Calibrate, Re-Run"

## Source: Claude planning conversation, Feb 22-23, 2026
## Breadcrumbs: 61C (GEDCOM + comparison) + 62 (face alignment) → 63
## Status: UPDATED with 61C/62 results and unresolved issues

---

## 1. SESSION 61C RESULTS + UNRESOLVED ISSUES

### What Shipped
- GEDCOM context builder with 5 enrichment variants (19 tests)
- Model comparison driver (scripts/compare_models.py)
- Extended GEDCOM parser (RESI, OCCU, IMMI, EMIG, BURI events)
- 11 comparison runs × 20 photos, $2.46 of $10 spent

### Winner
**gemini-3.1-pro-preview + curated GEDCOM variant**
- $0.02/photo, 0% error rate, 20s latency
- Location: vague → city-level in 4/5 cases
- Date estimates narrow by 3-7 years
- Confidence jumps from 60% → 80-100%

### Model Comparison
| Model | Cost/Photo | Errors | Notes |
|-------|-----------|--------|-------|
| gemini-2.0-flash | $0.0008 | 3% | GEDCOM "confusion bug" |
| gemini-3-flash-preview | $0.0083 | 13% | Unreliable availability |
| gemini-3.1-pro-preview | $0.0198 | 0% | Best quality, reliable |

### ⚠️ UNRESOLVED FROM 61C

**U1: Supabase GEDCOM tables not created.**
Import script exists (scripts/import_gedcom_supabase.py) but the
actual database tables (gedcom_individuals, gedcom_events,
gedcom_relationships, gedcom_face_links) were never created in
Supabase Dashboard. GEDCOM data is parsed but not persisted.
→ Session 63 MUST create these tables and run the import.

**U2: GEDCOM face linking never happened.**
The name-matching logic to link Rhodesli faces to GEDCOM individuals
was not implemented. Without this, GEDCOM enrichment only works for
manually linked photos. → Session 63 must implement fuzzy matching.

**U3: Variant D/E results unclear.**
First-order connections (D) and photo co-occurrence (E) were run but
the summary doesn't detail whether they improved over curated (C).
→ Session 63 Phase 0 must read the full comparison report to
determine if D/E add value or just noise.

**U4: Flash GEDCOM confusion bug unexplained.**
gemini-2.0-flash had a "GEDCOM confusion" issue at 3% error rate.
What specifically confused it? Does this affect bulk Flash usage?
→ Read the run results to understand the bug.

**U5: Context management protocol not followed.**
Session acknowledged not doing /clear between phases. Context
degraded. → Session 63 MUST follow /clear protocol.

---

## 2. SESSION 62 RESULTS + UNRESOLVED ISSUES

### What Shipped (v0.65.0)
- EXIF orientation handler (app/exif_handler.py, 10 tests)
- Coordinate bridging module (app/face_alignment.py, 30 tests)
- API endpoints POST/GET /api/face-alignment/{photo_id} (8 tests)
- Photo page UI: per-face description cards, mismatch warnings,
  admin trigger button (6 tests)
- 54 new tests, all passing
- AD-146 documentation

### ⚠️ UNRESOLVED FROM 62

**U6: NO real photo was ever sent to Gemini.**
FA-005 deferred — "needs deploy." Phase 5 was explicitly designed
to test on real photos because unit tests miss real-world bugs.
The face alignment module has NEVER aligned a real face.
→ Session 63 MUST test on real photos BEFORE batch re-run.
This is the #1 priority.

**U7: Vida Capeluto photo never tested.**
The motivating example for PRD-015 was never run through the
pipeline. → Session 63 must test this specific photo.

**U8: No production deploy.**
Code is on main but never pushed to Railway.
→ Session 63 must deploy and verify.

**U9: UI not verified in browser.**
Description cards, mismatch warnings, admin trigger — these exist
as code but were never seen rendering in a real browser.
→ Verify after deploy.

**U10: Test count anomaly.**
Both 61C and 62 claim 3373 tests. If 62 added 54 new tests,
the count should differ. Possible: 62 ran after 61C merged and
included 61C's tests in its count. Benign but verify.

---

## 3. PLATT SCALING — CONTINUOUS CALIBRATION DESIGN

### The Asymmetric Ground Truth Problem (from Nolan)

**Current state:**
- MANY confirmed match pairs (user merges → "same person")
- VERY FEW explicit non-match pairs (no UX for "not same")
- Available FREE source: implicit non-matches from different
  identified people (Big Leon ≠ Victoria → non-match pair)

**Future state (non-matches will spike):**
When "Not the same person" UX launches, users reviewing similar
faces will reject matches. This means:
1. Non-match pairs could increase 10-50x suddenly
2. These are HARD negatives (most informative data)
3. Calibration curve will shift significantly
4. System must handle this gracefully

### Design for Continuous Recalibration

Architecture: isotonic regression (not logistic/Platt) because
it's more flexible with weird score distributions.

Recalibration triggers:
- Every 20 new pairs
- Non-match ratio shifts > 50% since last fit
- Manual admin trigger
- Model age > 30 days

Safety rails for non-match spike:
- Rate-limit recalibration: max once per hour
- If threshold shifts > 0.1: save but flag for admin review
- Never retroactively change past merge decisions
- Weight recent explicit non-matches 1.5x (more informative)

Ground truth pair sources:
| Source | Match? | Available Now |
|--------|--------|--------------|
| admin_merge | ✓ | Yes — every face merge |
| implicit_different_id | ✗ | Yes — FREE from named people |
| community_confirm | ✓ | Yes — identity confirmations |
| admin_reject | ✗ | No UX yet |
| community_reject | ✗ | No UX yet — will spike later |

---

## 4. BATCH RE-RUN DESIGN

### Prerequisites (all must be true before batch)
- [ ] Face alignment tested on real photos (U6 resolved)
- [ ] GEDCOM tables in Supabase (U1 resolved)
- [ ] GEDCOM face linking done (U2 resolved)
- [ ] Calibration model fitted
- [ ] Nolan approves budget

### Cost Estimates (271 photos, Pro + curated GEDCOM)
- Interactive API: 271 × $0.02 = ~$5.42
- Gemini Batch API (50% off, 24hr SLA): ~$2.71
- Recommended: Batch API overnight

### Strategy
1. Run 5 photos through full pipeline first (alignment + GEDCOM)
2. If quality good: submit batch job for remaining 266
3. Store results versioned — don't overwrite
4. New results feed into calibration pairs

---

## 5. CONTEXT MANAGEMENT — LESSONS LEARNED

Both 61C and 62 failed to follow /clear protocol.
61C hit 0% context and degraded. 62 was fast enough to
finish before context pressure hit.

**Session 63 MUST**:
- /clear after EVERY phase (not optional, not conditional)
- Re-read next phase from prompt file after every /clear
- Phases designed to be small (< 15 min each)
- No phase should generate massive output that fills context
- API calls: process results immediately, don't accumulate

---

## 6. APP THESIS REMINDER

- **Identify**: Calibrated scores → "85% match" not "0.67 cosine"
- **Share**: Meaningful probabilities are shareable
- **Contribute**: Active learning surfaces most valuable pairs
- **Solve mysteries**: Full pipeline (alignment + GEDCOM) in one call
- **Systematize**: Continuous calibration improves with every interaction
