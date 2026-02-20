# Rhodesli Decision Log

Chronological record of major architectural, algorithmic, and product decisions.

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-02-05 | **Tech Stack**: FastHTML + InsightFace + JSON data model | Rapid prototyping for 124 photos; Python single file, minimal deployment overhead |
| 2026-02-05 | **Auth**: Supabase (Google OAuth + email/password) | Speed; outsource to managed provider; invite codes for access control |
| 2026-02-05 | **Hosting**: Railway + Cloudflare R2 | Persistent volume for JSON data; R2 for zero-egress photo storage |
| 2026-02-06 | **Mobile UX**: Bottom tab nav + hamburger sidebar | Mobile-first; 2-col grid mobile / 4-col desktop |
| 2026-02-06 | **JS patterns**: Global event delegation via `data-action` | HTMX-safe; unaffected by DOM swaps (Lesson #39) |
| 2026-02-07 | **Formalize decisions**: AD-xxx (algorithmic), OD-xxx (ops) logs | Prevent repeat debates; clarity for future contributors |
| 2026-02-08 | **Phase A**: Fix 4 P0 bugs + 103 regression tests | Lightbox arrows, face counts, merge direction, collection stats |
| 2026-02-09 | **ML calibration**: Golden set (90 mappings, 4005 pairs) | Swept thresholds 0.50–2.00; established AD-013 distance scale |
| 2026-02-09 | **Confidence tiers**: VERY HIGH / HIGH / MODERATE / LOW / VERY LOW | Replace raw distances; non-technical user comprehension |
| 2026-02-10 | **Contributor roles**: ROLE-002/003 (contributor, trusted contributor) | Enable family contributions; auto-promote after 5 approvals |
| 2026-02-10 | **Non-destructive merges**: Audit snapshots + undo | Reversible data transformations; preserve history |
| 2026-02-10 | **Annotation engine**: Submit → review → approve → reject | Community moderation workflow |
| 2026-02-10 | **Production sync**: Bearer token API (not cookies) | Reliable machine-to-machine sync; token never expires |
| 2026-02-11 | **Surname variants**: 13 Sephardic family name groups | Capeluto ↔ Capelouto ↔ Capuano search bidirectional |
| 2026-02-11 | **Merge-aware push**: Production state merge before git push | Preserve admin actions; prevent overwrite on re-push |
| 2026-02-11 | **Co-occurrence signals**: "N shared photos" badge on neighbors | Boost confidence when identities appear together |
| 2026-02-12 | **Global reclustering**: Include SKIPPED faces in ML grouping | Skip = deferral, not exclusion; continuous re-evaluation |
| 2026-02-12 | **Actionability sorting**: Sort inbox by confidence + proposal status | Confirmed leads first; admin time on high-value actions |
| 2026-02-20 | **Memory infra evaluation** (AD-115): Rejected NotebookLM MCP, Mem0, Notion MCP, LangChain for dev workflow | Current in-repo harness (AD docs, session_context, .claude/rules/) is sufficient. See session_54c_planning_context.md |
| 2026-02-20 | **MLflow integration** (AD-116): Accepted for targeted use starting with CORAL training | Portfolio talking point + Gemini prompt tracking. ~10 lines via autolog. Local only. |
| 2026-02-20 | **Face Compare product** (AD-117): Three-tier plan accepted, Tier 1 prioritized | Competitive analysis: all 7+ existing tools give single % with no kinship/cross-age context. Rhodesli already exceeds them. |
| 2026-02-20 | **NL Archive Query** (AD-118): Deferred LangChain-powered natural language interface | High portfolio value but prerequisites (similarity calibration, CORAL, stable matching) not ready |
| 2026-02-20 | **Historical Photo Date Estimator**: Identified as future standalone product | Novel — no existing tool. Depends on CORAL model training. See session_54c_planning_context.md Part 2D |
