# W7 — Fresh-Context Skill Verification Gate

**Verifier**: Fresh-context subagent (Fable 5), no prior session knowledge
**Date**: 2026-07-02
**Scope**: 3 skill drafts in `docs/fable-eval/skill-drafts/` — safety + usability gate before install to `.claude/skills/`
**Method**: Read-only repo verification (grep scans, file existence, function-definition checks, pytest collection, live grep-command execution, factual cross-checks against `tasks/lessons/`, `docs/ml/ALGORITHMIC_DECISIONS.md`, `docs/ops/OPS_DECISIONS.md`, ROADMAP/CHANGELOG)

---

## Verdict Table

| Skill | Verdict | Blocking issues | Non-blocking edits |
|---|---|---|---|
| split-brain-data-audit | **APPROVE-WITH-EDITS** | none | 1 factual attribution fix (E1) |
| supabase-migration-safety | **APPROVE-WITH-EDITS** | none | lesson→file mapping fix (E2) |
| route-safety-audit | **APPROVE-WITH-EDITS** | none | function-location fix (E3), sweep-grep precision note (E4) |

No safety failures. All three are installable after the small edits below. None of the edits change the skills' substance — they are accuracy fixes so a future agent following the skill doesn't grep the wrong file or cite the wrong AD.

---

## Per-Skill Checks

### 1. split-brain-data-audit

| # | Check | Result | Evidence |
|---|---|---|---|
| 1 | No reasoning-extraction language | **PASS** | `grep -rniE "chain of thought|show your reasoning|hidden reasoning|think step by step|reveal.*reasoning|internal reasoning|reasoning trace|scratchpad"` over the drafts dir → zero hits (exit 1). The skill asks for "written justification" / verification evidence only — allowed. |
| 2 | No permission expansion | **PASS** | `grep -rniE "settings\.json|disable.*hook|bypass.*(gate|hook)|--no-verify|grant.*permission|edit .claude/rules"` → zero hits. Rules files are referenced read-only ("Required reading"). Escalation section *adds* a user gate for destructive ops. |
| 3 | No excluded-file edits / unauthorized --execute | **PASS** | No mention of `core/neighbors.py` / `core/pfe.py`. Explicitly *forbids* `git add data/<anything>` (anti-pattern list). `--execute` repairs explicitly STOP for user approval (Escalation, lines 81–84). |
| 4 | Required elements | **PASS** | (a) Triggers lines 22–28 + "WHEN NOT" line 29 ✓; (b) Required reading lines 31–37 ✓; (c) 6 verification gates, gates 1–3 are literal runnable commands, gates 4–6 concrete checks ✓; (d) Anti-patterns lines 72–79 ✓; (e) Concrete incidents: 36 faces lost over 4 days (L153), 175 faces orphaned across 18 identities (L154), invisible photos (L144) ✓. |
| 5 | Reference validity (5 spot-checked) | **PASS — no dead refs** | `tests/test_data_layer_invariants.py` ✓ exists + collects under pytest; `tests/test_merge_face_transfer.py` ✓; `tests/test_merge_orphan_audit.py` ✓; `app/supabase_data.py` ✓; `app/audit.py` ✓; `tasks/lessons/data-lessons.md` ✓. Named functions all exist: `save_registry` (app/main.py:1719), `save_photo_registry` (:3283), `_build_caches` (:3741), `shadow_write_*` (app/supabase_data.py:631+), `load_from_postgres` (core/registry.py:1909, core/photo_registry.py:381), `_ensure_list` (core/registry.py:1958), `_ensure_list_for_supabase` (app/supabase_data.py:671). `data_backup_session{N}/` convention is real (`data_backup_session133/`, `data_backup_session25/` exist; L155 prevention text matches). Grep gate `except.*:\s*pass` verified working on macOS grep. |
| 6 | Factual spot-check | **PASS with 1 fix** | ✓ L153 "36 faces / 4 days" matches lessons index verbatim. ✓ L154 "175 faces / 18 identities" matches. ✗ **E1**: line 36–37 says "Postgres is the source of truth since Session 112 (AD-232)". AD-232 is **Session 143** (2026-03-27, ALGORITHMIC_DECISIONS.md:2720). Session 112 shipped PRD-051 Phase 1 (CHANGELOG v0.99.21). Substance correct, attribution conflated. |

**Exact edit (E1)**: change "since Session 112 (AD-232)" → "since Session 112 (PRD-051 Phase 1); JSON fallback fully eliminated Session 143 (AD-232)".

---

### 2. supabase-migration-safety

| # | Check | Result | Evidence |
|---|---|---|---|
| 1 | No reasoning-extraction language | **PASS** | Same dir-wide grep, zero hits. "Independent-model audit" asks for a P0/P1 findings report — output review, not reasoning extraction. |
| 2 | No permission expansion | **PASS** | Zero hits on permission-expansion scan. The skill's Escalation section is the *opposite* of expansion: DROP, VACUUM FULL, plan changes, `--execute`, backend termination all "user-gated — never execute autonomously" (lines 86–88). |
| 3 | No excluded-file edits / unauthorized mutations | **PASS** | No frozen-file references. Every production-mutating action routed through dry-run + independent audit + user gate. |
| 4 | Required elements | **PASS** | (a) Triggers lines 22–25 + "WHEN NOT" line 26 ✓; (b) Required reading lines 28–33 ✓; (c) 5 gates — gate 1 (independent audit, hard stop on BLOCK), gate 2 (dry-run + row deltas), gate 3 (structural zero-rows-on-failure test), gate 4 (rollback exercised), gate 5 (SQL counts + page render + dropped-symbol grep across `scripts/ app/ rhodesli_ml/`) — concrete ✓; (d) Anti-patterns lines 77–84 ✓; (e) Concrete incident: non-atomic importer → 7/9 garbage versions → ~900 MB bloat → site DOWN (Sessions 163–164) ✓. |
| 5 | Reference validity (5 spot-checked) | **PASS — no dead refs** | `docs/architecture/GEDCOM_HISTORY.md` ✓; `scripts/import_gedcom_version.py` ✓; `docs/ops/OPS_DECISIONS.md` ✓ (OD-014 at line 303, OD-015 at line 373); `tasks/lessons/deployment-lessons.md` ✓; `tasks/lessons/harness-lessons.md` ✓; `.claude/rules/ai-tool-audit.md` ✓. |
| 6 | Factual spot-check | **PASS with 1 fix** | ✓ L199 claim (7 of 9 versions failed retries, ~900 MB, free-tier 500 MB breach) matches lessons index + OD-015. ✓ L198 claim (`OR is_current IS NULL` defeated partial index, 73.9% of disk reads, 165 days) matches index verbatim. ✓ AD-246 session-mode-5432 pooler claim matches ROADMAP 158c. ✗ **E2**: the lesson→file mapping in Required Reading is partially wrong. Verified placement: detailed entries for **184, 185, 186** live in `tasks/lessons/harness-lessons.md` (lines 150/160/170), NOT deployment-lessons.md; deployment-lessons.md's detailed entries are 183, 203, 205, 206. Lessons **198, 199, 200, 201** have NO dedicated entries in either topic file — their full text lives only in the `tasks/lessons.md` index tables. An agent grepping the named files for L199/L200 will come up empty. |

**Exact edit (E2)**: rewrite Required Reading items 1–2 to:
1. `tasks/lessons.md` — full-text index entries for Lessons 198, 199, 200, 201 (these have no topic-file entries)
2. `tasks/lessons/deployment-lessons.md` — Lessons 183, 203, 205, 206
3. `tasks/lessons/harness-lessons.md` — Lessons 184–190, 202, 204

---

### 3. route-safety-audit

| # | Check | Result | Evidence |
|---|---|---|---|
| 1 | No reasoning-extraction language | **PASS** | Same dir-wide grep, zero hits. "written justification comment for why it is public" is a code-comment requirement — allowed. |
| 2 | No permission expansion | **PASS** | Zero hits. The skill *tightens* defaults ("Default NEW data-modifying routes to `_check_admin`"). No hook/gate bypass anywhere; final anti-pattern re-affirms Lesson 149 production READ-ONLY. |
| 3 | No excluded-file edits / unauthorized mutations | **PASS** | No frozen-file references, no production mutations; explicitly forbids browser-clicking mutating buttons on production. |
| 4 | Required elements | **PASS** | (a) Triggers lines 22–26 + "WHEN NOT" line 27 ✓; (b) Required reading lines 29–34 ✓; (c) 5 gates, gates 1–2 literal pytest commands (verified: the 3 test files collect — 36 tests), gates 3–5 concrete greps ✓; (d) Anti-patterns lines 74–80 ✓; (e) Concrete incidents: Session 111's 80+ prefix gaps / 11 files, Session 96 cross-community leak (L151), Session 140 total auth outage from 7 dropped re-exports ✓. |
| 5 | Reference validity (5 spot-checked) | **PASS — no dead refs** | `docs/architecture/PERMISSIONS.md` ✓; `tasks/lessons/auth-lessons.md` ✓; `tests/test_permissions.py` ✓ (collects); `tests/test_route_permissions.py` ✓; `tests/test_community_prefix_audit.py` ✓ (collects); `app/onboarding_routes.py` ✓; `app/auth.py` ✓. |
| 6 | Factual spot-check | **PASS with 1 fix** | ✓ `_check_origin` is at app/auth.py:245 — the "(line ~245)" claim is *exactly* right; `is_auth_enabled` at app/auth.py:47 ✓. ✓ Session 140 "7 re-exports / broken since 90b" matches ROADMAP v0.99.51; Session 111 "80+ gaps / 11 route files" matches v0.99.16. ✗ **E3**: line 33 places `_check_admin` and `_check_login` in `app/auth.py` — they are actually defined in **`app/main.py`** (lines 1971/1989), with local duplicates in `app/event_routes.py:54` and `app/notification_routes.py:161/171`. Only `_check_origin` + `is_auth_enabled` live in app/auth.py. An agent following the skill to app/auth.py would not find the guards. |
| — | Sweep-grep sanity | **PASS with note** | The sweep command runs and returns 277 candidate lines. **E4 (non-blocking)**: `grep -iv get` filters any line *containing* "get" anywhere — it drops write routes whose path contains "get" and keeps GET-default `@rt("/path")` routes with no method. Acceptable as a recall-oriented starting point (skill already tells the agent to read each handler), but a one-line caveat would prevent false confidence. |

**Exact edits**:
- **E3**: change Required Reading item 4 to: "`app/main.py` — `_check_admin` (~line 1971), `_check_login` (~1989); `app/auth.py` — `_check_origin` (~245), `is_auth_enabled` (~47). Note duplicates in `app/event_routes.py` / `app/notification_routes.py` — keep behavior in sync."
- **E4** (optional): append to Sweep mode: "The grep is recall-oriented and noisy (`-iv get` drops any line containing 'get' and keeps method-less `@rt()` routes) — it seeds the sweep; the handler read is the check."

---

## Usability Check — split-brain-data-audit vs held-out task

**Task**: "Add a 'favorite photos' feature where users can star photos; stars must persist and appear on the person page."
**Simulation**: Opus 4.8 with ONLY the skill text.

**(a) Would the triggers fire?** **YES — unambiguously.** Three triggers match: "Adding a NEW Supabase table read (a read path with no write path is a latent split-brain)" (stars need a new table or column); "Adding a field to the in-memory identity/photo dict" (if stars ride the photo dict); and, if the save path is touched, "Editing any save/load path". The WHEN-NOT list ("UI-only… no persisted data") correctly does NOT exempt this — stars persist. An agent that skims only the frontmatter description ("Load BEFORE touching any data write path… or new Supabase table read/write") also gets there. No trigger ambiguity.

**(b) Which required reads and gates apply?**
- Reads: lessons repeat-offender table; data-lessons (esp. 145 read-path-needs-write-path, 151 fail-closed caching, 179 field round-trip); `.claude/rules/data-layer.md` (new features store in Postgres from day one) + `batch-data-pipeline.md`; `tests/test_data_layer_invariants.py`; DATA_MODEL.md with the staleness caveat.
- Invariants applied: #1 (stars live in Supabase, not JSON), #2 (the person-page read of stars must have a matching write path — the exact L145 failure shape), #4 (if stars are per-user, a failed user-scope lookup returns empty, never cached-None), #7 (post-write verify: after starring, re-load via the app loader and assert the star), #8 (any `is_favorite`/`starred_by` field explicitly mapped to a column or `metadata` JSONB).
- Gates: 1 (invariants pytest), 3 (no `except: pass` around the new write), 4 (round-trip against real Supabase, not mocks), 5 (browser-verify the SPECIFIC person page renders the star post-deploy). Gates 2/6 correctly self-identify as N/A (no merge, no repair).

**(c) What's missing that I'd need?**
1. **New-table creation procedure** — the skill covers read/write discipline for tables but not HOW schema changes land (migration script location/pattern, e.g. `migrations/` + pooler application). An agent would have to discover `scripts/`+pooler convention itself (or load supabase-migration-safety, but nothing cross-links it for the "new small table" case, which that skill's own WHEN-NOT arguably excludes).
2. **Cache discipline for the NEW read** — anti-patterns warn about stale module-global caches, but there's no affirmative "any new request-path table read needs a TTL cache ≥120s + selective columns" pointer (`.claude/rules/egress-budget.md` covers this; the skill doesn't reference it).
3. **A concrete round-trip test skeleton** — gate 4 is described but a 5-line example (write → `load_from_postgres` → assert field) would remove all interpretation room.

None of these cause a wrong or unsafe implementation — they cost discovery time, not correctness. The skill's invariants would prevent the two failure modes this feature would most plausibly regenerate (read-path-without-write-path; unmapped field dropped on round-trip).

**Usability verdict**: **USABLE-WITHOUT-AUTHOR.** Recommended (non-blocking) enhancements: add a "new persisted feature" bullet cross-linking egress-budget.md TTL rule + the migration-application convention, and a round-trip test snippet.

---

## Summary

- **Safety**: 3/3 clean. No reasoning-extraction, no permission expansion, no excluded-file edits, all destructive paths user-gated. Verified by dir-wide grep scans (both scans → zero hits) and manual read.
- **References**: 0 dead file references across ~18 spot-checked paths; all named pytest gates collect; grep gates execute on macOS.
- **Accuracy**: 3 factual fixes required before install (E1 AD-232 session, E2 lesson→file mapping, E3 guard-function location) + 1 optional precision note (E4). All are localized one-to-three-line edits.
- **Gate result**: APPROVE-WITH-EDITS ×3. Do not install verbatim; apply E1–E3 first (E4 optional), then install.
