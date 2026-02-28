# Session 78 Context — Integration + Fix-Everything

## Session Lineage
- Session 74: Antigravity/Gemini — introduced 9K lines of key-reorder noise, 
  wiped 19 UUID relationships, broke date parser
- Session 75: Cleaned up 74's mess. Fixed date parser, tree frontend, xdist 
  race condition. But: stop hook broke, ML tests failing, no GEDCOM sync.
- Session 76a: Built auto-clustering pipeline + Discoveries UX + browse card 
  sizing. But: backfill found 0 actionable results, 57 dupes unresolved, 
  no visual verification, no deploy.
- Session 77 (Codex): Enriched compare pair endpoint + auto-queue uploads + 
  10 golden tests. But: AD-179 collision, couldn't run full suite, scope was 
  25% of prompt, no browser verification.

## Known ML Test Failures (3 total)

### test_mls_score_range_exceeds_threshold
- File: rhodesli_ml/tests/ (exact file TBD)
- First noted: Session 75 assessment
- Uses: embeddings.npy + core/pfe.py
- Neither file was modified in Session 75, so this may be a pre-existing 
  data drift issue or a test with a too-tight threshold

### test_only_matched_individuals  
- File: rhodesli_ml/tests/test_graphs.py
- First noted: Session 76a assessment
- Error: "20 relationships found where 0 expected"
- Likely cause: Session 75 merged 1,019 relationships (19 UUID + 1,000 GEDCOM).
  The test probably expected an empty or filtered set and now gets GEDCOM rels.

### test_compare_photos_tab_has_face_overlays
- File: tests/test_compare_faces.py
- First noted: Session 77
- This is a UI test checking for face overlay markup in compare tab
- May be outdated assertion after Session 77's compare changes

## Duplicate Face IDs (57 total)

Phase 0 of Session 76a found 57 faces that exist in BOTH:
- Confirmed identity clusters (as part of a named person)
- Inbox (as separate unidentified entries)

Current dedup_inbox() only catches cases where ALL faces of an inbox 
identity match a confirmed identity. Per-face dedup would catch the 
remaining 57 — these are individual faces that were added to a confirmed 
cluster but their inbox entry was never removed.

## Threshold Analysis Data

From Session 76a Phase 0:
- Within-cluster distances: mean=1.01, std=0.19, p5=0.70, p25=0.88
- Tier 1 threshold: < 0.85 (below p25)
- Tier 2 threshold: 0.85 - 1.10
- Big Leon closest non-duplicate inbox match: 1.13+ (above Tier 2)
- Nace closest non-duplicate inbox match: 1.18+ (above Tier 2)

Key question: Is 1.10 the right Tier 2 ceiling? If Big Leon's 
within-cluster max distance is > 1.10, then the ceiling is provably 
too low for his face variation. The analysis in Track 3 should compute 
per-identity max distances.

## GEDCOM Sync Gap

- Local data/relationships.json: ~1,019 relationships
- Local data/identities.json: 775 identities (60 confirmed, 472 inbox)
- Supabase relationships table: unknown count (likely just the 19 UUID ones)
- Production /tree page: shows 24 people (confirmed identities only)
- Expected after sync: ~718 people visible on tree

The startup code in supabase_data.py pulls from Supabase and overwrites 
local JSON. So even though the local files have GEDCOM data, production 
doesn't see it because Supabase doesn't have it.

## Compare Feature State

Session 77 (Codex) modified:
- /api/compare/pair/match — now includes archive context, cross-photo 
  face pairs, per-face archive best-hit summaries
- _queue_compare_upload_for_review() — auto-queues uploads to admin review
- _save_compare_upload() — wired queueing into persistence

What WASN'T done (from the original 8-phase prompt):
- Full UX redesign of compare flow
- Upload pipeline debugging (uploads have been broken for 5+ sessions)
- Test suite speedup
- Standalone compare product vision
- Competitive research implementation
- Mobile optimization

## Stop Hook Issue

Session 75 log shows: "Stop hook error: Failed with non-blocking status 
code: No stderr output"

The hook in .claude/settings.json (or hooks.json) should enforce that 
docs/assessments/session-NN-assessment.md exists before allowing session 
completion. It failed silently in Session 75, allowing the session to 
end without an assessment.

## Post-Merge State (ACTUAL — from merge session)

Tests: 3204 app + 386 ML = 3590 total (all passing)
- 76a claimed 3205 app + 537 ML = 3742. ML count dropped by 151.
- 75 claimed 3216 total.
- Track 1B must reconcile these three different numbers.

AD numbering (COMPLETED by merge session):
- AD-179: Two-tier auto-clustering thresholds (Session 76a)
- AD-180: (Session 76a)
- AD-181: Pair-compare archive-context (renumbered from 77's AD-179)
- AD-182: Compare pipeline decisions (renumbered from 77's AD-180)

Version: v0.79.1. Session 78 should bump to v0.80.0.

## Visual Testing Strategy

### Primary: Claude Chrome Extension
Claude Chrome reads the actual browser, clicks, takes screenshots, 
and reports back. It works with authenticated sessions (uses your 
actual logged-in Chrome). Use for all visual verification.

### Fallback: Playwright
```bash
pip install playwright --break-system-packages
playwright install chromium
```

Write headless scripts that navigate, screenshot, and assert.

### UX Evaluation Questions (from .claude/rules/ux-evaluation.md)
For every page:
1. Can a community member identify someone from this page?
2. Can they share what they found?
3. Can they contribute knowledge?
4. Is there a clear path to the next action?
5. Does the growth loop work?

## Harness Reminders

- Save this prompt to docs/prompts/session-78-prompt.md
- Every decision → AD entry with provenance
- /clear between tracks (not /compact)
- Commit after every track
- Tests after every merge
- Assessment file must exist before session ends
- ROADMAP < 150 lines, no doc > 300 lines
- Update SESSION_HISTORY.md
- Update CHANGELOG.md (v0.80.0 for this session)
