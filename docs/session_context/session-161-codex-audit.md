# Session 161 — Pre-Execution Plan Audit

**Auditor**: Claude general-purpose subagent (Opus 4.7, fresh context)
**Agent type**: Independent (no prior session knowledge)
**Phase**: Pre-execution plan review (audit ran BEFORE Session 161 phases 0-9)
**Scope**: `docs/prompts/session-161-prompt.md` + `docs/session_context/session-161-context.md`
**Date**: 2026-05-13
**Note**: Codex CLI (v0.130, gpt-5.5, xhigh) was tried first; hung at 23.7s CPU after 25 min wall-clock — recurrence of the stdin-hang pattern from Sessions 152-155. Fell back to Claude subagent per `.claude/rules/ai-tool-audit.md` documented fallback. ~5 min wall-clock, 161,637 tokens.

## Verdict: **PROCEED-WITH-FIXES**

Architecture is sound; 6 ADs are reasonable. The 2 P0s are blockers but ~30-min fixes if addressed in Phase 0 before any code is written. The 3h estimate is optimistic by ~1h once P1 fixes are budgeted.

## Summary by axis

| Axis | Findings | Worst |
|---|---|---|
| 1. Architecture soundness | 1 P1 (schema drift), 1 P2 (no AD log), 1 P2 (dual SoT) | P1 |
| 2. Atomicity gaps | **1 P0** (rollback unsafe), 1 P2 (idempotency), 1 P2 (concurrent race) | **P0** |
| 3. Security | **1 P0** (path traversal), 1 P1 (CSRF missing), 1 P1 (prefill query param) | **P0** |
| 4. Cross-repo safety | 1 P2 (settings deny rule illusory at runtime) | P2 |
| 5. Production safety | 1 P1 (RAILWAY_ENVIRONMENT gate) | P1 |
| 6. Test coverage | 2 P2 (concurrent race, drift detection) | P2 |
| 7. Schema correctness | 1 P1 (schema drift with rhodes-wiki arch doc) | P1 |
| 8. Carryover scope creep | 1 P2 (FB-NESTED-001 may exceed 20-min slot) | P2 |
| 9. Time estimate | 1 P1 (sidebar wiring +10min), 1 P2 (Phase 8 +30min) | P1 |
| 10. Anti-goals missing | 3 P3 (proxy, dedup, hint persistence) | P3 |

---

## P0 findings — applied to plan before commit

### P0-1: Atomic rollback for `mark_approved` is unsafe

**Problem**: Plan specified filesystem-move-first, Supabase-write-second with a reverse-move on Supabase failure. Three issues: (1) crash between the two operations leaves half-state; (2) reverse-move on Supabase failure is itself not atomic; (3) `approved_pending_filesystem` recovery status violates the CHECK constraint.

**Applied fix**: Inverted order to **Supabase-first, filesystem-second**. Supabase upsert is idempotent (a retry no-ops). Filesystem move uses `os.replace()` (POSIX atomic rename), not `shutil.move()`. Status field drops the `approved_pending_filesystem` substate; reconciliation script `scripts/rhodes_inbox_reconcile.py` detects + reports drift instead.

### P0-2: Path traversal in slug param

**Problem**: `slug` arrives via URL path param then is used in filesystem ops. A malicious admin could submit `slug = "../../../etc/passwd_dir"`. Session 160 P1-1 caught this exact pattern in rhodes-wiki's `extract_fb_post.py` — it's about to be repeated on rhodesli.

**Applied fix**: Added `_SLUG_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}_[a-zA-Z0-9_-]+$")` and `_validate_slug()` helper that resolves the candidate path and verifies it stays under `inbox_root`. Called from every route handler AND `mark_approved` / `mark_rejected` / `load_entry`. Added test `test_mark_approved_rejects_path_traversal_slug`.

---

## P1 findings — applied to plan before commit

### P1-1: CSRF (`_check_origin`) missing from POST routes
**Applied**: Phase 3 spec now requires `_check_origin(request)` at top of every POST handler, before `_check_admin(sess)`.

### P1-2: AD-S161-1 production gate too soft
**Applied**: AD-S161-1 updated to require BOTH path existence AND `not os.environ.get("RAILWAY_ENVIRONMENT")`. Defense in depth — even if `RHODES_WIKI_ROOT` is misconfigured on Railway, the production marker blocks the gate.

### P1-3: Schema drift between context AD-S161-4 and rhodes-wiki ARCHITECTURE.md §3.3
**Applied**: Phase 7 now includes updating rhodes-wiki `docs/ARCHITECTURE.md §3.3` to match rhodesli's canonical schema (rhodesli's plan schema wins because `photos.photo_id` is TEXT — verified). Field name reconciliation: kept `rejection_reason` (rhodesli style) and added schema-doc-sync to Phase 7 deliverables.

### P1-4: Phase 8 Codex prompt references `migrations/` not `scripts/migrations/`
**Applied**: One-line fix in Phase 8 prompt invocation.

### P1-5: Admin sidebar wiring lacks file/line anchor
**Applied**: Pre-research result added inline to prompt: existing nav pattern is in `app/main.py` around line 4640-4700 (already cached in this audit's grep) and `app/components/nav.py`. Added +10 min to Phase 3 budget (30 → 40 min).

### P1-6: Phase 5 prefill GET reads wrong directory (race after approval move)
**Applied**: Phase 5 redirect now points to `/upload?prefill=<slug>` where the GET handler reads `inbox/approved/<slug>/post.json` (post-approval is the right time to prefill). `load_entry()` accepts a `state` parameter (pending|approved|rejected). Added `_validate_slug()` call at top of prefill GET.

### P1-7: `extract_kinship` import path / caching unspecified
**Applied**: Decision = **copy** `extract_kinship.py` from rhodes-wiki to rhodesli (`app/extract_kinship.py`) at Phase 0 to decouple. rhodesli depends on the JSON contract, not rhodes-wiki Python. Kinship triples computed once and persisted in `rhodes_inbox_entries.kinship_triples_json jsonb` column (added to schema). Detail view reads from the column, not at request time.

---

## P2 findings — applied where cheap, BACKLOGGED where heavy

### Applied inline:
- **P2-A** (concurrent approval race): mark_approved uses atomic CAS — `UPDATE ... WHERE status='pending' RETURNING *`; empty result = someone else won; raises `AlreadyApprovedError`. Test added.
- **P2-D** (audit_log writes): every approve/reject calls `_log_audit(action='rhodes_inbox.approve', ...)`.
- **P2-E** (Phase 8 budget): Phase 8 extended to 45 min (15 audit + 30 fixes). Total session 3h → **~4h**.
- **P2-H** (settings deny rule illusory at runtime): Phase 0 deny rules also block `Bash(python:* /Users/nolanfox/rhodes-wiki/*)` and similar.
- **P2-I** (AD log persistence): AD-S161-5 becomes HD-035 in HARNESS_DECISIONS.md; remaining ADs go to a new `docs/architecture/RHODES_INBOX.md` doc. +10 min to Phase 9.

### Backlogged (created BACKLOG entries):
- **P2-B** (Supabase upsert idempotency semantics): document the `INSERT ... ON CONFLICT DO NOTHING` pattern in module docstring; defer formal idempotency test.
- **P2-C** (rate limiting on admin routes): admin trust model; not added. Backlog as `RHODES-INBOX-RATELIMIT`.
- **P2-F** (FB-NESTED-001 may exceed 20min): downgraded to "synthetic-fixture-only test"; real-world validation deferred to a future capture session.
- **P2-G** (dual source of truth): AD-S161-6 reworded — **Supabase is authoritative for status; filesystem mirrors it for offline-readable provenance**. Reconciliation script `scripts/rhodes_inbox_reconcile.py --dry-run` added to Phase 2.

---

## P3 findings — accepted as backlog

- **P3-A** image preview removal degrades UX → manual FB-download means admin already saw image (per AD-S161-2 reasoning).
- **P3-B** `rejection_reason` length cap → add `CHECK (length(rejection_reason) <= 4096)` to schema.
- **P3-C** no deletion path → admin can DELETE via Supabase SQL editor; backlog item for future admin route.
- **P3-D** Phase 9 browser verification optional-skip language tightened: end-to-end is mandatory for the Session 160 inbox entry.
- **P3-E** Session 160 P2-E known-broken kinship triple noted in admin UI footer: "Triples are auto-extracted; manual review required."

## Anti-goals additions
Added to out-of-scope list:
- FB image proxying via rhodesli backend (out of scope — production deploy implications)
- Duplicate-detection beyond rhodesli's existing photo SHA256 dedup
- Identity-hint persistence into rhodesli's identity-merge workflow (RHODESLI-INBOX-005 — future)

---

## AI Tool Usage

- **Tool**: Claude general-purpose subagent (Opus 4.7, fresh context)
- **Wall-clock**: ~5 min
- **Tokens**: 161,637
- **Value rating**: **STRONG** — caught 2 P0s (atomicity ordering, path traversal) that Codex Session 160 had already caught on the rhodes-wiki side; this audit prevented the regression of the same bug class on the rhodesli side. The schema drift with rhodes-wiki ARCHITECTURE.md §3.3 (P1-3) was non-obvious from the rhodesli side alone and would have caused Session 162 confusion.
- **Comparison note**: Codex CLI hung 25 min before fallback. Claude subagent finished in 5 min. Per `.claude/rules/ai-tool-audit.md`, this confirms the documented fallback path works. The Codex hang is a known recurring failure mode (Lessons recorded Sessions 152-155); for plan reviews (vs code reviews) the Claude-subagent path may actually be the better default given the prompt's read-mostly nature.
