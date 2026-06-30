# Session 167 — Track D: Detroit Prompt Fix Eval (PROMPT-A-ITERATION-001 / PRD-LOCATION-001)

**Date:** 2026-06-30
**Author:** Track D (Opus architect + Codex gpt-5.5/xhigh coder/auditor)
**Scope:** Date/location Gemini prompt mispredicts NYC/Brooklyn for Detroit photos
02068 + 01659 even WITH GEDCOM context. Implement Path A (Round-2.5
residence-distance scoring) and run a bounded eval.
**Model:** `gemini-3.1-pro-preview` · temperature 0.1
**Total real-Gemini spend this session:** **$0.30** (2 bounded passes, hard cap $0.50,
mechanical `--max-cost` + `--max-calls` double-cap enforced in-code).
**Raw artifacts:**
`docs/feedback/session-167-detroit-eval-raw.json` (AD-243 baseline),
`docs/feedback/session-167-detroit-eval-v2-raw.json` (Round-2.5 v2 tie-breaker).

---

## TL;DR — replicated the failure, root-caused it, Path A is necessary but NOT sufficient

| photo | AD-243 (pass 1) | Round-2.5 v2 (pass 2) | gate |
|---|---|---|---|
| **02068** | Brooklyn, NY · **high** | Brooklyn, NY · **high** | ❌ FAIL (both) |
| **01659** | Detroit, MI · medium→**high** | Detroit, MI · **high** | ✅ PASS |

**The Detroit gate still FAILS on 02068 under both the committed AD-243 prompt and a
hardened v2 tie-breaker.** This is NOT a prompt-structure bug we can fix from the
prompt alone — it is a **contradictory-GEDCOM-ground-truth** problem. The fix path
for 02068 is **Path B (PRD-061 multi-frame event clustering)** + a GEDCOM-context
data cleanup, NOT further tie-breaker tweaks.

01659 (the sister Belle Isle Conservatory frame) **improved**: AD-242's
`candidate_with_prior` now returns Detroit at **high** confidence (Session 154 had it
at medium). Path A genuinely helps when the residence signal isn't self-contradictory.

---

## What "Path A" is (already implemented Session 155, AD-243 — verified, hardened here)

Path A was implemented in Session 155 (commit `70460f9b`, `scripts/session153_shadow_eval.py`)
but **the Detroit rerun was never executed** — the `docs/feedback/session-155-...` files
the AD forward-references do not exist. Session 167's job was to RUN it.

Round 2.5 forces Gemini to fill a structured `residence_distance_table` (one row per
candidate location) with the subject's matching GEDCOM residence + `year_distance`, and
pick the primary by an explicit tie-breaker. AD-242's `candidate_with_prior` CONFIRM
path requires a NAMED GEDCOM event + `year_distance ≤ 5` (Lesson 174 teeth).

### Session-167 hardening (this session, evidence-driven + Codex-P1-driven)
After pass 1 exposed the count-primary flaw, the tie-breaker was rebuilt (still
prompt-only, `scripts/session153_shadow_eval.py`):
- **PRIMARY rule is now smallest `year_distance`** (date proximity), not raw count.
  Count of distinct subjects-at-min-distance is only the SECONDARY tiebreaker.
- **Undated residences excluded** ("Residence ? in Brooklyn" must not count — it
  inflated Brooklyn's match count in pass 1).
- **±10-year date window** (a 1934 residence does not anchor a ~1917 photo).
- **CONFIRM path tightened** (Codex P1): the prior may only be confirmed if it is the
  Round 2.5 *winner*, not merely "some nearby event exists."
- Eval-harness additions: `--photo-root` (worktree raw_photos/ is empty),
  `--experiment-id` + `--out-path` (honest provenance; no longer clobbers the Session 154
  record), `--max-calls` + per-call spend LEDGER + in-code ABORT, `--no-db-log`,
  and `residence_distance_table`/`round_2_5_summary` now captured in the file output.

---

## Pass 1 — AD-243 baseline (count-primary tie-breaker). 02068 → Brooklyn.

`02068 / candidate` residence_distance_table (verbatim from Gemini):

| candidate | subject_residence_match | year_distance |
|---|---|---|
| Brooklyn, NY | Harry 1915 NY/Kings; **Irving 1917-1918 Brooklyn**; Albert **"Residence ? in Brooklyn"** (undated) | 0 |
| Detroit, MI | **Albert 1917-1918 Detroit**; **Irving 1917 Detroit** | 0 |
| Dayton, OH | Harry 1920; Albert 1923; Irving 1934 | 3 |

`round_2_5_summary`: *"Brooklyn wins by Rule 2. It tied with Dayton for the highest
count of subject matches (3 each), but Brooklyn has a smaller year_distance."*

**Diagnosis (confirmed independently by Codex gpt-5.5):** the count-primary Rule 1
rewarded Brooklyn (3 loosely-dated matches, incl. an **undated** "Residence ?") over
Detroit (2 on-year matches). Detroit had the *tighter* anchor but the *shorter* list.

---

## Pass 2 — Round-2.5 v2 (date-proximity-primary, undated excluded). 02068 → still Brooklyn.

`02068 / candidate` residence_distance_table (verbatim from Gemini):

| candidate | subject_residence_match | year_distance |
|---|---|---|
| Brooklyn, NY | **Irving Fox: Residence 1917-1918 in Brooklyn** | **0** |
| Detroit, MI | **Albert Fox: Residence 1917 in Detroit** | **1** |
| Dayton, OH | Harry Fox: Residence 1920 in Randolph, Montgomery, OH | 2 |

`round_2_5_summary`: *"Brooklyn wins by Rule 1 (smallest year_distance): Irving has a
documented residence in Brooklyn 1917-1918, exactly matching the estimated 1918 date,
whereas Detroit's closest match is 1 year away (1917)."*

**Why v2 didn't flip it (the real root cause):**
- Gemini estimated the photo as **1918** and chose **Irving's `1917-1918 in Brooklyn`**
  (distance 0) as Brooklyn's anchor and **Albert's single-year `1917 in Detroit`**
  (distance 1) as Detroit's anchor — even though Detroit ALSO has `1917-1918` residences
  in the same GEDCOM context. With date-proximity primary, Brooklyn (0) beats Detroit (1).
- **Irving Fox is documented in BOTH Brooklyn (1917-1918) AND Detroit (1917) in the
  SAME period.** Albert likewise has both. The ground-truth GEDCOM places the same
  confirmed subjects in two cities at the same time. **No residence-distance tie-breaker
  can disambiguate a subject documented in two cities the same year** — and the model can
  legitimately pick whichever city happens to have the tighter date label.

---

## Root cause (final)

1. **Contradictory GEDCOM ground truth.** Irving + Albert Fox each carry near-simultaneous
   Brooklyn AND Detroit residences (~1917-1918) in the supplied context. The Belle Isle
   photo is genuinely Detroit, but the residence data does not uniquely say so.
2. **Pre-repair contamination.** The GEDCOM-context fixture
   (`tests/fixtures/session154_gedcom_context.json`, 22.8 KB for 02068) is from Session 154,
   **before the Session 156 Harry repair** that detached the misregistered "Harry Fox"
   (Harshel) faces from 02068. Harshel's NY/Kings 1915 + Dayton residences are still in the
   context, adding NY-area weight that should no longer be associated with this photo.
3. **Visual prior is the real signal, and it's cross-frame.** 01659 — the sister frame, same
   event (same 3 seated men + 2 standing women, identical outfits + Belle Isle Conservatory
   backdrop) — is correctly Detroit at HIGH confidence. The conservatory is a Detroit landmark.

This is exactly the escalation Session 154 predicted (AD-243 Gap/Risk): *"If 02068's failure
is dominated by visual prior strength rather than absent constraint, Path A may not be
sufficient and Path B (PRD-061 multi-frame event clustering) is the next escalation."*

---

## Recommendation (for Nolan — open decisions)

1. **Path B (PRD-061 multi-frame event clustering)** is the right fix for 02068: pool
   02068 + 01659 (+ any other Belle Isle frame) into one event and let the conservatory
   visual that 01659 nails carry 02068. This is a NEW design effort, out of Track-D scope.
2. **Data cleanup (cheap, high-value):** regenerate the GEDCOM-context fixture POST-Harry-repair
   (drop Harshel), and investigate Irving Fox's contradictory `1917-1918 Brooklyn` vs
   `1917 Detroit` GEDCOM residences — at least one is likely a mis-sourced/duplicate event.
   A clean, non-self-contradictory context may let Path A resolve 02068 on its own.
3. **Keep the v2 tie-breaker.** It is strictly sounder (date-proximity primary, undated
   excluded, CONFIRM-requires-winner) and it lifted 01659 to high-confidence Detroit. It is
   not deployed to production (`rhodesli_ml/gemini_extraction.py` untouched); it lives only
   in the shadow-eval harness pending a production-deployment decision.

## DO-NOT / guardrail compliance
- NO `date_labels` / prod writes. Pass 2 ran `--no-db-log` (no Supabase writes at all);
  pass 1 wrote only append-only `gemini_api_calls` audit rows (experiment provenance,
  `experiment_id LIKE 'session167_detroit_eval%'`). Neither touched `date_labels`.
- NO browser. NO edits to ROADMAP/BACKLOG/CHANGELOG/SESSION_HISTORY/conftest/components.
- Prompt-builder changes confined to `scripts/session153_shadow_eval.py`
  (`rhodesli_ml/gemini_extraction.py` NOT touched — Track B owns the app layer).
- Mechanical double-cap held: 5 total calls / $0.30, well under `--max-cost 0.50` and
  `--max-calls 8`. The 504 retry-with-backoff on 01659/candidate worked (eventually errored
  out that one call; the silent first pass + candidate_with_prior still completed).

---

## Fresh-context attempt (Session 167 cont.) — 02068 NOW FLIPS TO DETROIT ✅

**Date:** 2026-06-30 (continuation) · **Model:** `gemini-3.1-pro-preview` · temp 0.1
**Total real-Gemini spend this continuation:** **$0.1935** (6 calls; cap `--max-cost 0.40`,
`--max-calls 6`; one 504 on 01659/candidate after the backoff retries). All `--no-db-log`
— zero Supabase writes, no `date_labels`, no browser.
**Raw artifacts:** `docs/feedback/session-167-detroit-eval-fresh-ctx-raw.json` (fresh context),
`docs/feedback/session-167-detroit-eval-stale-ctx-force-raw.json` (stale-context isolation).
**Fresh fixture:** `tests/fixtures/session167_gedcom_context.json` (the 154 fixture is NOT overwritten).

### TL;DR — the candidate-force closes 02068. Path B is NO LONGER required.

The "one untried lever" (regenerate 02068's GEDCOM context from CURRENT production data,
post-Session-156 Harry repair) was executed AND combined with the new
DETROIT-CANDIDATE-FORCE-167 step (commit `5a49bfca`). Result:

| photo | variant | context | predicted | conf | verdict |
|---|---|---|---|---|---|
| **02068** | candidate | **fresh (Harry dropped)** | **Detroit, MI** | high | ✅ **CORRECT** (d=0) |
| **02068** | candidate_with_prior | **fresh** | **Detroit, MI** | high | ✅ **CORRECT** (d=0) |
| **02068** | candidate | **stale (154, Harry present)** | **Detroit, MI** | high | ✅ **CORRECT** (d=0) |
| **01659** | candidate_with_prior | fresh | **Detroit, MI** | high | ✅ **CORRECT** (d=0) |
| 01659 | candidate | fresh | — | — | ⚠️ 504 error (transient, retried out) |

**Both the AD-243 pass-1 and the Round-2.5 v2 pass-2 (documented above) had 02068 → Brooklyn.
With the candidate-force injected, every successful 02068 run predicts Detroit at high
confidence.** The Detroit gate now PASSES on 02068.

### What changed — fresh context is the cleanup, candidate-force is the lever

1. **Fresh context (the requested lever)** correctly resolved from current production data
   (`load_gedcom_data()` returns 21,998 individuals — the Lesson 205 loader is healthy). It
   now lists ONLY **Irving Israel Fox + Albert Fox** as confirmed subjects — **Harry Fox is
   gone** (his faces were detached from 02068 in the Session 156 repair). Harry's stale
   `New York/Kings 1915` (d=3) + `Randolph/Dayton 1920` (d=2) NY/Ohio noise no longer appears.

2. **But the residence-distance picture is STILL a genuine d=0 tie even after the cleanup:**
   - Detroit d=0 — Albert `1917-1918 Detroit` (+ Irving `1917 Detroit`)
   - Brooklyn d=0 — Irving `1917-1918 Brooklyn`
   The contradictory ground truth Track D root-caused remains: Irving is documented in
   Brooklyn 1917-1918 AND Detroit 1917; Albert in Detroit 1917-1918. No residence-distance
   tie-breaker can uniquely pick a city.

3. **The DETROIT-CANDIDATE-FORCE-167 step is what closes it.** It deterministically parses
   each confirmed subject's OWN dated residences, computes year_distance from the FIXED
   photo_year (1918, de-gamed), and INJECTS every place ≤5y as a MANDATORY candidate with an
   authoritative distance. This forces **Detroit onto the table at its TRUE distance 0** — the
   exact value pass-2 had MISSED (pass-2 anchored Detroit on Irving's single-year 1917 = d=1
   and lost the tie). Once Detroit and Brooklyn are both on the table at d=0, the model
   resolves the tie correctly via Round-2.5 **Rule 2** (Detroit has more distinct subjects at
   d=0) or **Rule 3** (Belle Isle Conservatory visual fallback → Detroit).

**Isolation result:** stale context (Harry present) + candidate-force ALSO flips 02068 →
Detroit, high, correct. So the candidate-force is the **primary** fix; the fresh-context
regeneration is a **complementary cleanup** that removes Harry's NY/Ohio noise but is not
strictly necessary for the flip. Best practice: ship BOTH (the context should be regenerated
post-repair regardless, and the candidate-force is the durable mechanism).

### Verbatim Round-2.5 `residence_distance_table` (02068 / candidate / fresh context)

| candidate | subject_residence_match | year_distance |
|---|---|---|
| Brooklyn, Kings, New York, USA | Israel (Irving) Fox: Residence 1917-1918 in Brooklyn, Kings, New York, USA | 0 |
| Detroit, Wayne, Michigan, USA | Albert Fox: Residence 1917 in Detroit \|\| Albert Fox: Residence 1917-1918 in Detroit, Wayne, Michigan \|\| Israel (Irving) Fox: Residence 1917 in Detroit | 0 |
| New York, Kings, New York, United States | Israel (Irving) Fox: Residence 1915 in New York, Kings | 3 |
| Dayton, Ohio, USA | Albert Fox: Residence 1923 in Dayton, Ohio | 5 |

`round_2_5_summary` (verbatim): *"Detroit and Brooklyn tied with a year_distance of 0, but
Detroit won via Rule 2 because it had more distinct confirmed subjects (Albert Fox and Israel
Fox) documented there at that minimum distance compared to Brooklyn (only Israel Fox)."*

`eliminated_runner_up`: Brooklyn — *"Eliminated by Round 2.5 Rule 2 (fewer distinct subjects
at distance 0)."* The `candidate_with_prior` and 01659 runs instead cite **Rule 3**: *"the
specific architectural massing of the masonry wing and sloped glasshouse matches Detroit's
Belle Isle Conservatory, not the Brooklyn Botanic Garden conservatory."*

### Path B status — NOT confirmed-required (downgraded)

The earlier Track D recommendation escalated 02068 to **Path B (PRD-061 multi-frame event
clustering: pool 02068 with its correctly-Detroit sister frame 01659)** as the ONLY remaining
fix. **That escalation is now OBSOLETE for 02068** — the candidate-force closes it from
single-frame data alone. Path B remains a sound *general* enhancement for genuinely
visual-only frames (no GEDCOM-linked confirmed subjects), but it is no longer the gating fix
for this photo and should not block deployment of the candidate-force.

### Recommendation

- **Promote the candidate-force from the shadow harness to production** — it is the durable
  mechanism that converts a contradictory-residence tie into a correct, visually-grounded
  answer. (Production deployment to `rhodesli_ml/gemini_extraction.py` is a Track-B/app-layer
  decision, out of Track-D's file scope; flagged here as the next step.)
- **Regenerate any cached GEDCOM-context fixture after an identity repair** (Lesson 205-adjacent):
  a stale fixture silently re-injects detached subjects' residences. The `session167` fixture
  is the post-156 baseline for 02068 + 01659.

### Guardrail compliance (continuation)

- NO `date_labels` / prod writes. Both runs `--no-db-log` — zero Supabase writes of any kind.
- NO browser. Real Gemini used ONLY in the bounded eval, $0.1935 total < $0.40 cap, 6 calls.
- New fixture `tests/fixtures/session167_gedcom_context.json` ADDED (154 fixture untouched).
- Commits on branch `session-167/detroit-force` ONLY.
