# Session 154 — Harry Isaackovitz Repair + Loose-End Sweep

**Mode:** Implementation (with interactive identification mid-session)
**Predecessor:** Session 153 (commits 4430f1ad → 3cd841d1)

## Orientation

Read at session start (in order):
1. `docs/feedback/session-153-harry-isaackovitz-breakthrough.md` — the user-confirmed Harry Isaackovitz identification, repair plan
2. `docs/feedback/session-153-harry-verification.md` — original ML evidence
3. `docs/feedback/session-153-corrective-analysis.md` — 3007/3009 revised hypotheses
4. `docs/feedback/session-153-codex-audit.md` — 3 P0, 4 P1, 2 P2, 1 P3 still open
5. Any session-153 feedback docs created after commit 3cd841d1 (shadow-eval, baselines, event-clustering research, Gemini-Chrome validation — check for docs/feedback/session-153-*.md files not yet referenced)

Set session:
```bash
echo "154" > .claude/current_session.txt
echo "implementation" > .claude/session_mode.txt
source venv/bin/activate
make test-fast
bash scripts/harness-check.sh
```

---

## Phase 1: Execute the Harry Fox anchor repair (HIGHEST PRIORITY)

**User has authorized the Harry Isaackovitz identification via Ancestry**, but the anchor-detach mutation on CONFIRMED identity Harry Fox was NOT executed in Session 153. Execute with full data safety.

### Steps
1. Snapshot `identities` row for Harry Fox (`d74cb556-6d44-4288-ade3-1cc8fa2b45a6`) to `backups/session-154/harry-fox-before-split-<UTC-ts>.json`.
2. Snapshot any audit_log entries for Harry Fox in the same file.
3. Create new identity for Harry Isaackovitz:
   - `identity_id`: generate UUID
   - `state`: CONFIRMED (user has confirmed via Ancestry)
   - `name`: "Harry Isaackovich" (match GEDCOM canonical form from `@I132506612777@`)
   - `anchor_ids`: 2 faces (validate exact IDs vs `docs/feedback/session-153-harry-verification.md` — agent labeled them F and G; one is in 02068-Detroit-center, the other in 01659-conservatory-companion)
4. Detach those 2 anchors from Harry Fox.
5. Hold anchor "E" (1968-74 banquet photo) for user visual review — Harry verification agent flagged it as an outlier.
6. Create gedcom_match row linking new identity to `@I132506612777@`.
7. Write audit_log entries for both mutations with `metadata={"route": "session_154_harry_repair", "evidence_ancestry_id": "132506612777"}`.
8. Verify post-repair: Harry Fox now has 5 anchors (7 - 2), new Harry Isaackovitz identity has 2 anchors, no orphaned faces.
9. Browser-verify the Detroit photo on production — the center man's identity label should now read "Harry Isaackovich" (or whatever canonical form we chose).

**Data safety gate:** Before writing ANY mutation, run the existing structural test `tests/test_merge_pipeline.py` or equivalent to confirm no post-merge orphans would result. If any test fails: STOP.

---

## Phase 2: Confirm 3009 = Bessie Fox

With Harry Isaackovitz confirmed as the center man, Bessie Fox is the leading 3009 candidate (his wife).

1. Visual compare 3009 (`inbox_ed3f214545b9`) to Bessie's 2 known anchors (both old-age).
2. Compute embedding distance to Bessie + to Harry Isaackovitz's Ancestry-tree photo if available via the Ancestry API or user-provided JPG.
3. If confidence STRONG: propose to user to confirm 3009 = Bessie Fox.
4. If AMBIGUOUS: leave as INBOX with a note.

---

## Phase 3: Close remaining Codex P0/P1 from Session 153

Still open after Session 153:

### P0
- **Production `date_labels` still reads "New York, New York"** for Detroit photo. User said "feel free to ignore B" in Session 153 — so leave as-is. (Double-check with user at start of Session 154.)
- **Belle Isle as "ground truth" needs independent archival citation.** Look for Burton Historical Collection reference. Session 153 Gemini transcript has a lead — they mentioned a specific Burton archival photo.

### P1
- **Gemini prompt shadow-eval** — `scripts/session153_shadow_eval.py` was committed but may not have run to completion (rate-limit blocked Session 153). Verify whether it has, and if not run it. Should include 02068 + 91b6f6b296e93a60 + 01659 (the 3 Belle Isle photos) + ≥7 other known-location photos as controls.
- **Embedding baselines** — `scripts/compute_embedding_baselines.py` was committed; Session 153 tried to run it with a bad `timeout` command (macOS). Re-run without `timeout`. Output to `docs/feedback/session-153-embedding-baselines.md`.
- **Recalibrate tier thresholds** using the baselines output. Update `docs/feedback/session-153-corrective-analysis.md` and any ML docs with the honest threshold.

---

## Phase 4: Photo event-clustering feature (PRD)

Session 153 launched an agent to research this (agent `af0449b5cd9e68ea0` — photo event-clustering). Check `docs/feedback/session-153-event-clustering-research.md`. If the agent's output has a recommended tier:

1. Read the research findings.
2. Decide with user: proceed with Tier 1 (rule-based) or stop?
3. If proceeding: write PRD `docs/prds/061_event_clustering.md`.
4. Tie into existing PRD-059 (temporal co-occurrence) since they overlap.

---

## Phase 5: UX fix deploy verification

Session 153 commit `3ba5dbff` landed the accidental-skip undo path (server + client + render). Verify:

1. `git push origin main` (if not yet pushed) and wait for Railway deploy.
2. Browser-verify on production: skip a test face from a safe photo, confirm the amber toast appears with Undo button, click Undo, confirm restore works.
3. READ-ONLY on real identity data — use a throwaway INBOX identity for this test.
4. Full e2e smoke via `python scripts/production_smoke_test.py`.

---

## Still-open work items (background)

- Session 153 agents that may have completed after the session ended:
  - `ad830473561c8e8e1` — Gemini-via-Chrome Harry validation. Findings: `docs/feedback/session-153-gemini-harry-validation.md`
  - `af0449b5cd9e68ea0` — Event-clustering feature research. Findings: `docs/feedback/session-153-event-clustering-research.md`
  - Codex CLI audit of Harry thesis (Bash command `bwuwbjfsw`) — check completion
  - Embedding baselines script (Bash command `b0tjphf91`) — check completion

If any of these completed, incorporate findings into Session 154 phases.

---

## Harness gap to address in Session 154

New rule: `.claude/rules/proactive-context-management.md` (created Session 153). The assistant should proactively recommend session wrap at 60% context or 5+ commits. Session 153 failed at this — the user had to explicitly tell the assistant to wrap.

Consider: add a transcript-line hook that echoes a "session getting long, consider wrap" message to the USER (not just the assistant) at 300 lines.

---

## Key identity IDs (reference)

| Person | Identity ID | State |
|--------|-------------|-------|
| Albert Fox | `85546ebf-75b9-4971-a9d4-b2ce2271bc19` | CONFIRMED |
| Bessie Fox | `b4a43575-9312-40ec-a574-85bf4294d0af` | CONFIRMED |
| Harry Fox (currently contaminated) | `d74cb556-6d44-4288-ade3-1cc8fa2b45a6` | CONFIRMED — Phase 1 splits off 2 anchors |
| Irving Israel Fox | `7e6aae2b-2b70-4a8a-9ee5-46e2b2c16c41` | CONFIRMED |
| Person 2510 (restored) | `c39e8284-871d-4a1d-88ae-888793f4b151` | INBOX |
| Person 3007 (Detroit back-left) | `121c9aa7-ed47-4adc-97a0-46588d5c24de` | INBOX |
| Person 3009 (Detroit back-right) | `63a1c0c1-aed2-4429-9e54-9dfae1b099d4` | INBOX — Phase 2 may confirm as Bessie |
| Person 3010 (Detroit background) | `ee0f3026-1459-4cf1-b184-538acf11131d` | SKIPPED (Session 153) |

| GEDCOM Key | Ancestry ID |
|---|---|
| Harry Isaackovich @I132506612777@ | 132506612777 |
| Bessie Fox (Basya Minya Fuks) | (look up in gedcom_individuals by surname=Fuks or name=Bessie Fox) |
| Fox/Capeluto/Fogel/Waldorf tree | 162873127 |

## Data safety reminders
- Backups before ANY mutation to `identities` rows: `backups/session-154/*-before-<UTC-ts>.json`.
- Audit_log entries for all state changes.
- Browser is READ-ONLY on production (never click action buttons).
- Run `make test-fast` before every commit.
- `/clear` after every commit (Opus 4.7 recall cliff at 300 lines).
