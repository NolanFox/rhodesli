# Egress Budget Awareness

Triggers: When modifying cache TTLs, adding new Supabase table reads, changing
auth/permissions to add admin roles, or scaling concurrent users.

## Current budget
- Supabase free plan: 5GB egress/month
- Grace period until 2026-04-13
- Primary egress driver: TTL cache reloads (identities 380KB, photos 436KB, photo_faces 293KB)
- Current TTLs: registry 120s, community IDs 120s, GEDCOM/alignment 300s

## Monitoring thresholds (from OD-011)
Revisit egress strategy when ANY of these occur:

1. **Multi-admin** — More than 1 admin user → 120s staleness visible to both, need write-through invalidation
2. **Table > 1MB** — Any cached table exceeds 1MB per fetch (~9000 identity rows) → need incremental sync
3. **10+ concurrent users** — Sustained concurrent users → constant-traffic model applies, ~24 GB/month → Pro plan
4. **gemini_api_calls growth** — Currently 1.49MB, no cache → if /tools/estimate gets traffic, add caching
5. **Another Supabase quota warning** — Just upgrade to Pro ($25/mo)

## When adding new Supabase reads
- Every new `supabase.table("X").select("*")` adds to egress
- Always add a TTL cache (minimum 120s) for any table read in a request path
- Use `.select("col1,col2")` instead of `.select("*")` when possible
- Log the table size and fetch frequency in OD-011's egress table

## Breadcrumbs
- Decision: OD-011 in docs/ops/OPS_DECISIONS.md
- BACKLOG: EGRESS-001 (ETag), EGRESS-002 (incremental sync), EGRESS-003 (selective columns)
- Supabase usage dashboard: check monthly if approaching 80% of 5GB
