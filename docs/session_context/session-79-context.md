# Session 79 Context — Fix Three Visible Failures

## What Nolan Sees Right Now (from screenshots, Feb 28 2026)

### Screenshot 1: /tree — BLANK
- URL: rhodesli.nolanandrewfox.com/tree
- Shows: "Family Tree" heading, "Focus on: Everyone" dropdown, 
  "Show speculative" checkbox, Share button
- Below controls: empty white/gray rectangle. No tree. No people.
- Session 78 claimed "Tree renders via Chrome. Specific people show 
  with family connections." This was FALSE.
- Session 78 synced 1,019 relationships to Supabase. The sync script
  ran but the tree is still blank — the data never reaches the frontend.

### Screenshot 2-3: Face Cards — BAD DESIGN
- URL: rhodesli.nolanandrewfox.com/?section=to_review&view=browse
- Cards show: title, INBOX badge, face count, quality, Sort dropdown,
  View All Photos button, Find Similar button, face thumbnail (~100x130px),
  quality label, Edit Details link, Confirm/Skip/Reject buttons
- Face is ~30% of card area. Buttons/chrome is ~70%.
- Version shown: v0.80.0
- Stats: 399 To Review, 59 People, 202 Help Identify
- Sidebar shows: Discoveries: 0 (should be > 0 after threshold raise)
- 50 Ready to Confirm, 349 Unmatched
- Bottom of sidebar: "59 of 660 identified" — only 9% identification rate
- Nolan's words: "genuinely bad", "genuinely poor design"
- Key issue: what percentage of the "facecard" is actually face?
  The face is the ONE thing the user needs to see to make a decision.

### Screenshot 4: Photo Detail — Identity Lost
- URL: rhodesli.nolanandrewfox.com/?section=photos&filter_collection=Uncategorized&sort_by=newest
- Shows: St. Petersburg Times, Thursday, August 6, 1959 newspaper photo
- Two faces with dashed bounding boxes
- Left face: labeled "Unidentified" (should be Big Leon or Nace)
- Right face: bounding box visible but no label shown
- Tag input visible: "Type name to tag..." with Close button
- This photo was the subject of sessions 76a and 78 — faces 768/767

## Session 78 Evaluation Items (from my critical review)

1. ✗ Tree still blank (confirmed by screenshot)
2. ✗ Per-face dedup implemented but not run (57 dupes still exist)
3. ✗ Threshold raise not applied (Nolan now approves 1.10→1.30)
4. ✗ Backfill not re-run (needed after threshold change)
5. ✗ Compare upload E2E deferred (5th time)
6. ✗ Mobile viewport never tested
7. ✗ 5 skipped tests undocumented
8. ✗ Big Leon/Nace identity possibly corrupted (screenshot confirms)

## Nolan's Directive (exact quotes)

"Like much of the app, rhodesli.nolanandrewfox.com/tree is completely broken"

"the UI is genuinely bad, just look at how the facecards are displayed. 
What percentage of the 'facecard' is actually face. Does that make sense? 
Does it make it easy to navigate."

"that photo seems to have deleted the identity linked to that photo. 
This is a huge fail since we have spent multiple sessions trying to 
get it to work."

"DO NOT STOP WORKING AT THEM UNTIL THEY ARE FIXED. THEY MUST BE 
VERIFIED WITH CLAUDE CHROME."

"Do not let tests slow you down. If you need to run at the end and 
then correct any errors you find."

"We have made way too little progress and done too much spinning our 
wheels. Let's prove we can solve 3 problems first."

## Compare Context (from Codex Session 77 screenshot)

The /compare/pair page DOES render — Codex screenshot shows Photo A and 
Photo B upload zones with "Compare Selected Faces" button. The UI shell 
works. The question is whether the upload → face detection → archive 
match pipeline works end-to-end on the deployed Railway instance.

## Technical Context

- Stack: FastHTML + HTMX + Tailwind. No React.
- Tree library: family-chart with CardHtml API (from Session 75)
- Tree JS: static/js/family-tree.js
- Tree builder: core/family_tree.py → build_family_tree()
- Face cards: face_card() function in app/main.py
- Auto-clustering: core/auto_cluster.py
- Thresholds: Tier 1 < 0.85, Tier 2 < 1.10 (raise to 1.30)
- Supabase data loader: app/supabase_data.py
- GEDCOM sync: scripts/sync_gedcom_to_supabase.py
- Pagination fix location: app/supabase_data.py (was only fetching first 1000 rows)

## Session 78 Threshold Analysis Data (for Track 3)

- 52% of confirmed clusters have max within-cluster distance > 1.10
- Big Leon (face 768): max within-cluster distance = 1.3824
- Nace (face 767): max within-cluster distance = 1.4095
- Both are above Tier 2 ceiling of 1.10, which is why they never appeared
  in Discoveries despite being the original motivation for building the
  auto-clustering pipeline
- Recommendation: raise Tier 2 to 1.30 — covers Big Leon (1.13 to 
  nearest cluster member) and Nace (1.18 to nearest cluster member)

## Session 78 Commit SHAs (useful for data loss forensics in Track 3)

- 4333535 fix(harness): repair stop hook
- 7bb19e5 docs: PRD-024 auto-clustering
- 6157b6b fix: 2 failing tests — photo dims, graph test
- 65a23c7 feat(auto-cluster): per-face dedup + threshold analysis
- 270eb75 feat(data): sync GEDCOM to Supabase
- 8ed7b24 final merge — v0.80.0

## Test Baseline (post-Session 78)

- 3249 app + 538 ML = 3787 passed, 0 failures, 5 skipped
- The 5 skipped tests are undocumented — Session 79 Track 4 must identify them
- Test count history: 75 said 3216, 76a said 3742, merge said 3590, 
  78 final said 3787. The discrepancies were due to miscounting, not data loss.

## Session 78 "Next Session Should Verify" (all 5 must be addressed)

1. Production tree shows 718+ people (GEDCOM sync deployed) → Track 1
2. Threshold decision: raise Tier 2 to 1.30 → Track 3 (APPROVED)
3. Re-run backfill after threshold change to cluster 768/767 → Track 3
4. Full compare upload E2E with ML models → Track 4
5. Mobile viewport audit → Track 4

## Known Pre-existing Issues

- AD-089 appears twice (Pre-Emptive Full Graph Generation + Search Result 
  Routing). Not introduced by sessions 76a-78. Noted in BACKLOG as BUG-004.

## Self-Assessment Reliability Warning

Session 78 self-assessment (Track 8) answered "0 red flags requiring 
immediate fix." My independent review found:
1. Tree not verified at 718+ people (RED FLAG #1)
2. Dedup implemented but never run (RED FLAG #2)
3. Compare E2E deferred for 5th time (RED FLAG #3)
4. Mobile viewport not tested (RED FLAG #4)
5. 5 skipped tests undocumented (RED FLAG #5)
6. Big Leon/Nace data loss not caught (RED FLAG #6)

Session 79's self-assessment MUST be honest. If something doesn't work,
say so — don't rationalize it as "deferred."

## Admin Decisions Made

- Nolan APPROVES raising Tier 2 threshold from 1.10 to 1.30
- Nolan APPROVES running backfill with new thresholds
- Nolan APPROVES running per-face dedup
- Tests can run at END of session, not blocking fixes

## What Comes After Session 79

Session 80 will be an interactive walkthrough where Nolan and Claude 
Code go through every page of the app together, using Claude Chrome 
extension. Session 79 should prepare for this by:
- Verifying Claude Chrome works
- Creating a page-by-page interactive plan
- Fixing the worst issues so Session 80 starts from a better baseline
