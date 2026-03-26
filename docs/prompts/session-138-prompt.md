# Session 138: Refactor Phase 2 + Quick Fixes + Harness

## Context
Supabase upgraded to Pro ($25/mo). Deploy should be unblocked.
See `docs/session_context/session-138-context.md` for full research, dependency maps, and audit comparison.
**New harness rule**: Codex CLI audit is mandatory after EVERY phase (see `.claude/rules/session-defaults.md` Dual-Audit Protocol).

## Phase 0: Verify Supabase + Setup (DO FIRST)
```bash
echo "138" > .claude/current_session.txt
echo "implementation" > .claude/session_mode.txt
source venv/bin/activate
make test-fast  # Baseline (~3748 tests)
```

Then confirm Supabase is working:
```bash
python3 -c "
from dotenv import load_dotenv; load_dotenv()
from app.supabase_data import get_supabase_client
client = get_supabase_client()
result = client.table('identities').select('identity_id', count='exact').limit(1).execute()
print(f'Supabase OK: {result.count} identities')
"
```
If this fails, STOP and tell the user. Do not proceed with implementation until Supabase is confirmed working.

## Track 1: Quick Fixes from Codex CLI Audit (do second)
**5-10 minutes. Fix before refactoring.**

1. **Mobile nav `|` separator** (P3-1): In `app/components/nav.py:257`, filter out `Span` elements before mobile nav clone. The `_public_nav_links()` separator `Span("|")` renders as a clickable link in mobile menu.

2. **xfail test rate-limit patches** (P2-2): In all 3 `tests/test_estimate_v2_*.py` files, change:
   ```python
   patch("app.rate_limit.check_rate_limit", return_value=True)
   ```
   to:
   ```python
   patch("app.estimate_routes.check_rate_limit", return_value=True)
   ```
   The route imports the alias, so patching the source module is inert.

3. Run `make test-fast` to verify fixes.

## Track 2: REFACTOR-001 Phase 2 — cards.py
**Sequential (touches main.py). No worktree isolation. BIGGEST TASK.**

### Extraction order (simplest → hardest):

1. **`match_info_bar()`** (line 8822, ~20 lines) — depends on `_confidence_tier_label` (already in badges.py). LOW risk.
2. **`face_card()`** (line 8696, ~126 lines) — depends on `resolve_face_image_url`, `get_face_quality`. LOW risk.
3. **`search_result_card()`** (line 9163, ~101 lines) — depends on `match_info_bar`, `compute_face_confidence`, `share_button`. LOW risk.
4. **`identity_card_mini()`** (line 6035, ~55 lines) — depends on `get_best_face_id`, `resolve_face_image_url`, `state_badge`. LOW risk.
5. **`neighbor_card()`** (line 8884, ~279 lines) — depends on `match_info_bar`, `share_button`. MEDIUM risk.
6. **`_build_face_cards_for_entries()`** (line 9544, ~39 lines) + **`_face_pagination_controls()`** (line 9585, ~52 lines) — internal helpers.
7. **`identity_card()`** (line 9647, ~574 lines) — depends on everything above + `_cross_community_badge`, `_build_face_cards_for_entries`. HIGH risk.
8. **`identity_card_expanded()`** (line 5748, ~287 lines) — most dependencies. HIGH risk.
9. **`lane_section()`** (line 10303, ~50 lines) — depends on `identity_card`. LOW risk (if identity_card is extracted).

### Pattern: Lazy imports for main.py dependencies
```python
def face_card(face_id, ...):
    import app.main as _m
    url = _m.resolve_face_image_url(face_id)
    ...
```

### After EACH function extraction:
1. Copy function to cards.py
2. Replace body in main.py with: `from app.components.cards import function_name`
3. Update `app/components/__init__.py` re-exports
4. Run `make test-fast`
5. Commit: `refactor: extract [function] to app/components/cards.py`

### Critical rules:
- Keep re-exports in main.py (route files use `_main_mod.function()`)
- Use lazy `import app.main as _m` inside function bodies — never at module level
- Import already-extracted components normally: `from app.components.badges import state_badge`
- If a function is too tightly coupled after 2 attempts, SKIP IT and note in log
- **20+ _main_mod call sites** across identity_routes.py (13), page_routes.py (5), photo_routes.py (2) — all must keep working

### Also extract to existing modules:
- `_cross_community_badge()` (line 814, ~51 lines) → `app/components/badges.py`
- `_build_triage_bar()` (line 3792, ~58 lines) → `app/components/nav.py`

### Success criteria:
- `wc -l app/main.py` ≤ 9,000 lines (realistic target: ~1,600 line reduction)
- `make test-fast` passes
- `python -c "import app.components.cards"` succeeds
- Each extraction committed atomically

## Track 3: Harness Updates
**Quick — do after Track 2.**

1. Commit `ai-tool-audit.md` update (model + agent type tracking) — already staged
2. Verify worktree cleanup (Session 137 branches deleted)

## Dual-Audit Protocol (MANDATORY — after EACH phase)
Per `.claude/rules/session-defaults.md` HD-030:

After Track 1 AND after Track 2, run the dual-audit cycle:
1. **Codex CLI** (independent): `codex exec --full-auto "Audit [changed files]. P0/P1/P2/P3."`
2. **Claude reviews** Codex findings: fix P0/P1, evaluate P2, note P3
3. **Claude may reject** Codex suggestions with reasoning
4. **Iterate** if fixes introduce new issues
5. **Save** to `docs/session_context/session-138-codex-audit.md` with provenance header

This is NOT optional. Session 137 proved Claude and Codex find different categories of bugs.

## Session End Checklist
- [ ] Phase 0: Supabase verified working
- [ ] Track 1: Quick fixes from Codex audit + dual-audit cycle
- [ ] Track 2: cards.py extracted, main.py reduced + dual-audit cycle
- [ ] Track 3: Harness updates committed
- [ ] `make test-fast` passes on final state
- [ ] Codex CLI audit(s) saved with provenance
- [ ] Assessment with AI Tools section (provenance for ALL tools used)
- [ ] CHANGELOG (v0.99.49), ROADMAP, BACKLOG, SESSION_HISTORY updated
- [ ] `git push origin main`
- [ ] Deploy verified (Supabase Pro restored)
- [ ] Browser verify: landing, person page, triage, compare
