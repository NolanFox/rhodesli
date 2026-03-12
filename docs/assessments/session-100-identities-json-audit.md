# Session 100 Identities JSON Audit

**Date:** 2026-03-12  
**Author:** Codex

## Summary
The local [data/identities.json](/Users/nolanfox/rhodesli/data/identities.json) working-tree delta is a mixed artifact and should not be committed as-is.

It contains:
- `2` likely legitimate human rename edits
- `10` clear merge-chain regressions where `merged_into` rolled back to an older intermediate target
- the same `10` entries also rolled `version_id` backward

That combination is unsafe for blind commit and unsafe for blind revert.

## Repo-Backed Constraints
- Supabase/Postgres is the source of truth for structured data per [AGENT_HARNESS.md](/Users/nolanfox/rhodesli/docs/AGENT_HARNESS.md#L67).
- JSON writes are expected to flow through canonical save functions like `save_registry()` rather than ad hoc edits.
- Production refresh already has a supported path in [sync_from_production.sh](/Users/nolanfox/rhodesli/scripts/sync_from_production.sh).

## Likely Human Edits
- `531c8221-a115-4bdd-ac96-bd930a27135b`
  - `Unidentified Person 737` -> `Jenny israel`
- `44ee07e0-bc1c-4839-9ee3-149e9ef349db`
  - `Unidentified Person 738` -> `Emily israel`

## Clear Regression Pattern
Examples of rollback behavior in the local file:
- `e8e8bb8c-4bdd-4391-b898-d1d9151da913`
  - `merged_into`: `d1d18cb0-f6ab-46af-acb2-bfe2a6d9a4cb` -> `c33f3348-d3d3-40c8-96c2-727c80854a7e`
  - `version_id`: `2` -> `1`
- `a86a2ff6-77b7-4d7c-9eba-883f7342e515`
  - `merged_into`: `85546ebf-75b9-4971-a9d4-b2ce2271bc19` -> `babb2d1e-0b02-4d97-811a-c76d1a21243d`
  - `version_id`: `4` -> `3`
- `44af1e76-2309-47b6-8dc9-a11d5ea8b0b8`
  - `merged_into`: `65207728-9ee6-48c1-be68-a2da23354caf` -> `a3a01405-12aa-4219-9349-5a5e727196fc`
  - `version_id`: `2` -> `1`

## Recommended Handling
1. Do not commit the local `data/identities.json` delta.
2. Do not discard it blindly until the human rename edits are accounted for.
3. Preserve a local backup first.
4. Refresh local `data/identities.json` from production using the existing admin export/sync flow.
5. Re-check whether the two rename edits already exist in production.
6. If they do not, re-apply only those intentional edits through the canonical app/admin path.

## Decision
For Session 100 code work, treat `data/identities.json` as an out-of-scope local artifact and keep it out of commits.
