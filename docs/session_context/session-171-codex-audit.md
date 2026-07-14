# Session 171 — Independent Adversarial Audit

**Auditor:** Codex CLI v0.144.3 (gpt-5.6-sol, xhigh) — ran a full adversarial pass with live
testing but STALLED during final report composition (tee log frozen ~2775 lines, 4 procs alive,
no structured report emitted after ~7 min). Per `.claude/rules/ai-tool-audit.md`, fell back to a
**fresh-context Claude general-purpose subagent** which completed the structured report and
CONFIRMED codex's in-flight finding.
**Agent type:** Independent (fresh context, no prior session knowledge).
**Scope:** Session 171 code diff — R1 tree scoping (`0c372aab`) + Phase 2 run contract (`225b86da`).
**Date:** 2026-07-14.

## How the primary finding was caught
Codex, before stalling, live-constructed a test where a `rhodes-identity` node carried
`rels: {children: ['@FOXPRIVATE@']}` and observed `/api/tree/data` return it with status 200 — i.e.
the R1 filter drops Fox GEDCOM *nodes* but leaves Fox references inside kept nodes' `rels`. The
Claude fallback auditor traced and CONFIRMED this against the real `_make_tree_node`.

## Findings

### P1 — R1 GEDCOM leak survives via `rels` + `shared_photos` of kept nodes (CONFIRMED) — FIXED
`_scope_tree_nodes_to_community` filtered only the top-level `nodes` list; it did NOT scrub the kept
nodes' `rels` (father/mother/spouses/children) or `data.shared_photos`, which `_make_tree_node`
builds referencing ids that were `in included` at build time — including dropped Fox nodes. A rhodes
identity adjacent to a Fox person (cross-community edge / xref→uuid resolution) survives filtering but
still carries `rels: {"father":"@I...@","mother":"<fox-uuid>"}` + `shared_photos: {"<fox-uuid>": N}`,
leaking Fox UUIDs, raw `@...@` xrefs, shared-photo counts, and relationship structure (not names/dates
/avatars — those nodes are dropped). The regression tests missed it because the fixture stubs
`_make_tree_node` to return `"rels": {}`. **Fix applied:** scrub each kept node's `rels` +
`data.shared_photos` to the community id set; new regression test with real cross-community rels.

### P2 — Idempotent re-run returns an id-less row, breaking crash recovery — FIXED
`create_run` used `upsert(ignore_duplicates=True)` (= INSERT … ON CONFLICT DO NOTHING). On a genuine
duplicate (the retry case idempotency exists for), PostgREST returns empty data → the function
returned the locally-built row with no DB `id`/`created_at`; a caller then doing
`transition_status(run["id"], …)` KeyErrors or passes None to `get_run`. **Fix applied:** on an empty
upsert result, re-read the canonical row via `get_run(idempotency_key=…)` and return that.

### P2 — Tree API has no auth; `/c/fox-family/tree` is world-readable — DEFERRED (design decision)
The tree API takes no `sess`/auth; post-fix the full Fox GEDCOM is served to any anonymous request at
the `fox-family` URL. This is **pre-existing** (the tree API never had auth) and consistent with the
site being a **public heritage archive** (person/photo/GEDCOM pages render publicly by design). R1's
job was the cross-community leak (a Rhodes visitor seeing Fox data), which is fixed. Whether the Fox
tree should be *private* is a product decision for the owner, not an R1 bug. **Deferred → BACKLOG
(TREE-AUTH-171); flagged to Nolan.** Do not gate it silently — it could break the public archive.

### P3 — `transition_status` read-then-update is not compare-and-swap (TOCTOU) — FIXED
Two concurrent transitions could both validate from the same status and both write (double transition,
lost history entry). Low risk for a single-operator desk. **Fix applied:** added `.eq("status",
current)` optimistic-concurrency guard; empty result = lost race (returns None).

### P3 — Idempotency-key delimiter ambiguity (`:`) — NOTED (BACKLOG)
`case_ref || ':' || hash`: `("a:b","c")` and `("a","b:c")` both → `a:b:c`. Requires a `:` in the
inputs (hashes are hex; case_refs are UUIDs/slugs — none contain `:` today). Low real risk. **→
BACKLOG (RUN-KEY-171):** switch to a NUL delimiter or hash-the-pair if case_ref format ever changes.

## CLEAN (explicitly confirmed by the auditor)
create_run atomicity (single upsert; failed = zero rows — Lesson 199 ✓) · no writes to confirmed
identity data (only `investigation_runs` ✓) · illegal-transition guard ✓ · migration
additive/idempotent/backwards-compatible ✓ · RLS service_role-only ✓ · R1 owner-check no casing
bypass, all four data return paths + expand routed through scoping, fail-closed correct, focal
recompute correct, `photo_people` echoes only user input ✓ · fox-family legitimate tree not broken ✓.

## Disposition
P1 + both actionable P2/P3 (idempotency, TOCTOU) FIXED in this session (commit follows). The auth P2
and the delimiter P3 are DEFERRED to BACKLOG with rationale above. Re-audit not re-run (fixes are
surgical and covered by new targeted tests).
