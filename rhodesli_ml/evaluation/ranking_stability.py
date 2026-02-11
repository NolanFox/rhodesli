"""Ranking stability: measures how much neighbor rankings change between model versions.

When a new model or threshold is proposed, this module compares:
- Top-k neighbors for each face (before vs after)
- Rank correlation (Kendall's tau) for confirmed identities
- New matches that appear / existing matches that disappear

High instability is a red flag for model changes.
"""

# Placeholder — will be implemented when model comparison is needed.
#
# Interface:
# - compare_rankings(old_embeddings, new_embeddings, identities) -> StabilityReport
# - StabilityReport: rank_correlation, new_matches, lost_matches, affected_identities
