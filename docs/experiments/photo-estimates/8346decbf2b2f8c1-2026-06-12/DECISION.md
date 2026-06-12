# Multi-Model Photo Estimate — Decision Record

**Photo:** `8346decbf2b2f8c1` — `IMG_1260.JPG` ("Old Fox Photos from Extended Family")
**Live page:** https://rhodesli.nolanandrewfox.com/c/fox-family/photo/8346decbf2b2f8c1
**Subjects (both CONFIRMED + GEDCOM-linked):**
- **Meyer Fox (Fuks)** `@I132127405051@` — b. abt 1853 Russia, d. 24 Aug 1940 Brooklyn (Kings, NY)
- **Rebecca "Reva" Heft Fox** `@I132127405052@` — b. abt 1865 Russia, **d. 2 Aug 1926 Brooklyn** (Kings, NY)
- Married, family `@F5091@` (11 children). Residence: Minsk → Manhattan (1905, 1910 Ward 7) → Brooklyn (1915–1940).

**Run by:** Claude Code (manual admin workflow), 2026-06-12. `operator=claude-code-manual`.
**Prompt:** identical for all three models — `PROMPT.txt` (date+location "quick" preset, **fully GEDCOM-enriched**, ~11.9 KB). See `image.jpg` for the exact pixels analyzed.

---

## Candidate results

| Model | decade | best year | probable range | P(1910s) | location | confidence | cost / tokens |
|-------|:------:|:---------:|:--------------:|:--------:|----------|:----------:|---------------|
| **Gemini 3.1 Pro** (`gemini-3.1-pro-preview`) | 1910 | 1910 | 1905–1915 | 0.60 | New York, NY | medium | $0.0167 / 27.3 s |
| **Fable 5.0** (`fable-5.0`) | 1910 | **1912** | 1906–1920 | 0.60 | New York City | medium | (subagent) |
| **Codex gpt-5.5 xhigh** | 1910 | 1910 | 1906–1918 | 0.50 | Manhattan, NYC | medium | 18,971 tokens |

Raw outputs: `candidate-gemini.json`, `candidate-fable.json`, `candidate-codex.json`.

**Headline:** strong 3-way agreement — **decade 1910, New York City, medium confidence**, hard ceiling **1926** (Reva's death). The disagreement is only in reasoning depth and the weight placed on the lower (1900) tail.

---

## Assessment — which was better

**Winner: Fable 5.0** (Gemini 3.1 Pro a very close 2nd; Codex gpt-5.5 a strong 3rd).

Scored on: (a) correct use of *every* GEDCOM constraint, (b) visual-evidence specificity, (c) soundness of the probability distribution.

1. **Fable 5.0 — best reasoning.** It is the only model that (i) explicitly treated the sitters' **apparent ages vs GEDCOM birth years** as a *strong* signal and used it to **anchor the lower bound** ("not earlier, since the sitters' apparent ages anchor the lower bound"), (ii) named the **1926 death ceiling** explicitly, (iii) ran the **missing-child test** correctly (all 11 children born by 1901 → their absence from a couple portrait is expected, so it adds no constraint), and (iv) gave the most granular distribution (4 decade buckets incl. a 0.02 tail on 1890). Its candidates are the most specific (Manhattan **Ward 7 / Lower East Side** vs Brooklyn). best_year 1912 sits inside every other model's range.
2. **Gemini 3.1 Pro — best production fit, ~tie on the answer.** Concise, correct, well-grounded biographically. Slightly less explicit age math. It is the platform-native path (auto-logs cost/latency/lineage to `gemini_api_calls`). If reproducibility-with-cost-tracking mattered more than reasoning depth, this would be the pick.
3. **Codex gpt-5.5 xhigh — solid but over-weighted the early tail.** Careful and cheapest. But it placed **0.42 probability on the 1900s** vs 0.50 on the 1910s — nearly a coin-flip — because it leaned on the broad print-format range (1895–1920) instead of letting the apparent-age evidence pull the lower bound up. It also read Meyer as "full mustache and short beard" where the others (and the age read) support a fuller white beard. Defensible, but the least sharp distribution.

### Why this matters (the trap)
The print-format/enlargement evidence is genuinely broad (~1895–1920). A model that weights it heavily drifts toward 1900. The **decisive** evidence is the GEDCOM-anchored apparent-age read (Meyer ~60, Reva ~50 → early 1910s) plus the Edwardian bodice. **Fable handled this best; Codex handled it least well.** This is the core learning: *with rich GEDCOM context, the best estimate comes from models that privilege biographical-age anchoring over broad material-format ranges.*

---

## Decision

- **Website / `date_labels`:** write **Fable 5.0**'s estimate (decade **1910**, best year **1912**, range **1906–1920**, **New York City, NY**, medium).
- **Provenance** stored in `date_labels.data.analysis_provenance`: `operator=claude-code-manual`, `chosen_model=fable-5.0`, `decision_method`, `candidates_compared`, and a pointer to this artifact.
- The two non-chosen candidates remain here in the repo for later review. Nothing is lost; `date_labels` is last-write-wins per photo, so only the chosen one is in the DB by design (see methodology below).

---

## Methodology & schema rationale

`date_labels` is keyed by `photo_id` (one row, upsert = last-write-wins) and the website renders that single row — it **cannot** hold three competing estimates without the most recent silently overwriting the rest. `gemini_api_calls` is append-only but Gemini-shaped (Gemini pricing/lineage), so Fable (Anthropic) and Codex (OpenAI) outputs don't belong there.

Therefore: **the DB stores only the chosen estimate** (the website's single source of truth) + provenance; **all candidates + this decision live as a versioned repo artifact**. This needs no schema migration, keeps production clean, and keeps the cross-provider experiment fully reproducible in git. A dedicated `photo_estimate_experiments` table is the documented upgrade path if DB-queryable experiments are wanted at scale.

**Manual vs platform** is structurally distinguishable in the data:
- `gemini_api_calls`: `experiment_id LIKE 'manual-%'` AND `gemini_config->>'operator' = 'claude-code-manual'` (platform leaves `experiment_id` NULL, `operator='platform'`).
- `date_labels.data.analysis_provenance.operator = 'claude-code-manual'` (platform reanalysis has no `analysis_provenance` block).
