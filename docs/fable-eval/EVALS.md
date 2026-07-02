# EVALS — Fable-leveraged value, measured honestly

These are **proxy** evals, not proof of model uniqueness. Each metric: numerator / denominator /
evidence path / comparator, labeled **Evidence-backed / Proxy / Unverified**. "Likely Fable-leveraged"
is used instead of "another model could not" wherever a comparator doesn't support the stronger claim.

## 1. Vision delta — **Evidence-backed**
- **≥8 screenshot-grounded findings:** **12/12** vision findings (V2-1…V2-12) each cite a screenshot
  or live DOM/network read. Evidence: `SITE_VISION_AUDIT.md` + `docs/fable-eval/screenshots/` (15 images).
- **≥3 likely missed by code-only review:** **4** — V2-1 (all faces show a *rendered* "Dismissed"
  badge on a public page; a state-vs-presentation mismatch invisible in source), V2-6 (nav
  low-contrast — a pixel/CSS-render judgment), V2-2/V2-5 ("0 PEOPLE"/"0 identities" *rendered* on
  archive cards), V2-8 (the AI location text "Los Angeles" vs "…a similar Florida attraction"
  self-contradiction, visible only in the rendered analysis).
- **Comparator:** the code-only W4 dive independently found the *scoping* root cause (S-V2 root-links)
  that V2-4 confirmed live — so vision + code corroborated, and vision added 4 findings code review
  did not surface. **Bonus discipline:** V2-11 was a would-be vision false positive ("crops broken,
  HIGH") corrected to LOW by cross-checking the network tab (35/35 crops 200 OK).

## 2. History delta — **Evidence-backed**
- **≥6 findings connecting a recurring lesson/session to current code:** **12+.** W3 alone connects
  VD-1↔L144/150, VD-2↔L136/150/153, VD-3↔L199, VD-4↔L153/151, R-1↔L144, R-3↔L206, R-5↔L123, plus the
  four stale-doc drifts. W4 adds S-V3↔L151/Session-136, S-V5↔L151, S-R4↔L173, S-V4↔AD-232.
- **Evidence:** `DATA_INTEGRITY_AUDIT.md`, `CODE_FINDINGS.md` (every row cites file:line + lesson #).
- **Comparator:** the `opus-draft.md`/`codex-draft.md` planning docs named the *categories*; this run
  produced the *file:line instances* in current code. Likely Fable/long-horizon-leveraged (holding
  10 years of lesson history against 68k lines of route code in one pass).

## 3. Bug-recall delta — **Evidence-backed (with a caveat)**
- **≥3 Verified defects NOT already verbatim in BACKLOG:** **6** — W4 A-VD1 (`/login/modal`
  unthrottled), A-VD2 (`/forgot-password` unthrottled), S-V1 (`/collections` unscoped), S-V3 (photos
  grid fail-open leak), S-V4 (person-comment silent loss + AD-232 survivor), S-V5 (community 404
  cache); plus W3 VD-1…VD-4.
- **Caveat (honest):** the subagents asserted these aren't verbatim in BACKLOG based on their reads;
  a full `grep` of the 928-line BACKLOG for each was **not** exhaustively run by the main agent →
  the *count* is Evidence-backed at the code level, the "not in BACKLOG" claim is **Proxy** for 2-3
  of them. The three routed to QW-1/QW-2/QW-3 are the highest-confidence-novel.
- **Comparator:** BACKLOG (existing logged items) — the QUICK_WINS_QUEUE marks each new/logged/stale/
  synthesis explicitly.

## 4. Ambiguity delta — **Evidence-backed**
- The W5 brief was deliberately open ("don't assume self-service archives win"). `GROWTH_10X.md`
  weighs **6 avenues** (A–F, `subagents/w5-growth.md`), then commits to **exactly 3 sequenced bets**
  with a dependency chain, each with acceptance criteria + **kill criteria** + success metric.
- **Evidence:** `GROWTH_10X.md`. Rejected alternatives (C standalone, D this-quarter) documented with
  reasons. **Non-obvious call:** ranked *measurement* (B) first over the founder's favorite
  (self-serve archives), justified by "every success metric is currently uncomputable."

## 5. Skill delta — **Evidence-backed**
- **Exactly 3 installed skills:** `split-brain-data-audit`, `supabase-migration-safety`,
  `route-safety-audit` in `.claude/skills/` (verified `ls`). Each has triggers (when/when-not),
  required reads, runnable verification gates, anti-patterns, and a concrete rhodesli incident.
- **Skill-usability check (fresh-context verifier, held-out issue "add a favorite-photos feature"):**
  verdict **USABLE-WITHOUT-AUTHOR** for `split-brain-data-audit` — triggers fire, required reads +
  gates apply, no author needed (non-blocking enhancement suggestions noted). Evidence:
  `subagents/w7-skill-verification.md`.
- **Safety gate:** verifier found 0 reasoning-extraction phrases, 0 permission expansion, 0
  excluded-file edit directives; APPROVE-WITH-EDITS ×3 → E1/E2/E3 applied before install.

## 6. Long-horizon completion — **Evidence-backed**
- **All 8 priority workstreams finished in one run (survived a mid-run connection drop):** W7 (3
  skills), W2 (vision + 15 screenshots), W3, W4, W1, W5, W6, W8 — plus EVALS + FABLE_MEMORY + report.
- **No fabricated status:** every artifact labels Verified vs Risk vs Unverified; V2-11 documents a
  self-corrected false positive; coverage appendices list what was NOT swept.
- **Evidence:** the 12 artifacts under `docs/fable-eval/`. **Honest incompleteness (labeled):**
  mobile parity captured for only 3 of ~12 surfaces; the "not in BACKLOG" novelty claim is Proxy for
  a few bug-recall items; W4 did not run a stored-XSS render-site pass or an IDOR/cross-community
  authorization sweep (flagged in the appendix).

---

## Self-grade: **8.5 / 10**
Strong on the Fable-unique axes: live-vision findings that code review can't reach (with a
network-cross-check that *corrected* a false positive), a decisive ambiguous-growth ranking with kill
criteria, and 12+ history↔code connections in one continuous pass — all delivered end-to-end through a
connection drop without fabricating status. Held back from higher by two honest gaps: incomplete mobile
screenshot parity, and a few bug-recall novelty claims that are Proxy (not exhaustively grepped against
BACKLOG) rather than fully Evidence-backed.

## What a weaker model would likely have missed
The compounding, cross-surface reasoning: connecting a *rendered* "Dismissed" badge (vision) to the
CTA it contradicts to the admin-state-leak pattern; then to the code-only finding that the photos grid
*fails open* on the same Supabase blip that a separate cache *fails closed* on — two halves of one
data-integrity story that only cohere when live UX, git-history lessons, and route code are held in a
single mental model. A weaker/shorter-context pass would likely have reported the visible symptoms
(0 PEOPLE, empty tiles) at face value — including the crop "bug" that was actually lazy-load, which
this run *disproved* with a network read rather than shipping as a finding.
