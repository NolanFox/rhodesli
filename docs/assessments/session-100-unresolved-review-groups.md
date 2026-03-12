# Session 100 Unresolved Review Groups

## Purpose
Record the follow-up slice that exposes unresolved-but-similar identities in Upload Review without changing canonical clustering behavior.

## Trigger
- Fox Family dogfooding showed likely same-person identities that were not surfaced anywhere useful for review.
- The prior Upload Review page only exposed:
  - multi-face INBOX groups
  - unresolved -> confirmed proposal matches
- That left unresolved -> unresolved lookalikes effectively invisible unless the user manually stumbled into a similar-faces page.

## User Signal Captured
- Roland Fox and Albert Fox examples looked like they should have been clustered or at least reviewable together.
- The user explicitly called out confidence loss when similar identities appeared ungrouped.
- The user also called out dismissed faces remaining visible without enough state signal.

## What Changed
- Added a new `Potential Review Groups` section to `/admin/upload-review`.
- The section surfaces unresolved identities whose representative face embeddings are close enough to deserve manual review.
- Each surfaced group includes:
  - a primary identity preview
  - up to five nearby unresolved neighbors
  - direct actions to `Review Similar` and `Open Queue`
  - explicit state badges:
    - `Inbox`
    - `Proposed`
    - `Dismissed`

## Implementation
- File: [app/cluster_review_routes.py](/Users/nolanfox/rhodesli/app/cluster_review_routes.py)
- Tests: [tests/test_cluster_review.py](/Users/nolanfox/rhodesli/tests/test_cluster_review.py)

Key design choices:
- Use one representative preview face per unresolved identity.
- Compare preview embeddings with Euclidean distance.
- Respect explicit negative links.
- Exclude identities that already share photos, to avoid noisy self-same-photo groupings.
- Build reviewable star groups rather than transitive mega-clusters.
- Keep this review-only:
  - no automatic merge
  - no identity-state mutation
  - no write-path changes

Current thresholds:
- `UNRESOLVED_REVIEW_THRESHOLD = 0.85`
- `UNRESOLVED_REVIEW_GROUP_LIMIT = 18`
- `UNRESOLVED_REVIEW_MEMBER_LIMIT = 6`

## Why This Is Safe
- It improves discoverability without loosening auto-cluster rules.
- It does not rewrite identity data.
- It does not alter the frozen embedding or merge invariants.
- It keeps the actual merge decision in the existing similar/merge workflow.

## Verification
- `ruff check app/cluster_review_routes.py tests/test_cluster_review.py`
- `pytest tests/test_cluster_review.py -x -q`
  - `23 passed`

Live-data sanity checks against current local data:
- Fox Family unresolved review groups surfaced: `18`
- Known problematic Fox identities now appear in surfaced review groups instead of remaining hidden.

## Limitations Still Open
- Review groups can still overlap; dedupe is improved but not perfect.
- This does not solve true batch clustering or cluster confirmation.
- This does not solve false negatives in the underlying embeddings/model output.
- Other surfaces may still need dismissed-state affordances for confidence.

## Attribution
- User: live Fox/Rhodes dogfooding, screenshot evidence, cluster-confidence concerns
- Antigravity: earlier workflow critique emphasizing batch/cluster review importance
- Codex: design choice, implementation, and verification of the review-only surfacing layer
