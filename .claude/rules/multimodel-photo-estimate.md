# Multi-Model Photo Estimate Workflow

Triggers: When asked to run a date/location (or other forensic) estimate on a
specific photo and compare models, OR to "update the website" with the best
estimate for a photo. Also read before adding any new per-photo model output to
the database.

## The workflow (script: `scripts/multimodel_photo_estimate.py`)

1. **Build ONE fully-enriched prompt** (date + location "quick" preset +
   **GEDCOM context** for every CONFIRMED, GEDCOM-linked face in the photo).
   The same prompt + same image go to every model — fair comparison.
2. **Run each model** and capture the raw output:
   - **Gemini 3.1 Pro** — `run-gemini` phase, via the production
     `_call_gemini_date_estimate` (auto-logs to `gemini_api_calls`).
   - **Fable 5.0** — `Agent` tool subagent with `model: "fable"`, reads the
     image + `PROMPT.txt`, returns the JSON.
   - **Codex gpt-5.5 xhigh** — `codex exec "<prompt>" -i image.jpg </dev/null`
     (Codex CLI ≥0.139 supports `-i/--image`; pin in `~/.codex/config.toml`).
   - Run Fable + Codex in **parallel** (one background Bash + one Agent call).
3. **Compare + decide.** Score on (a) correct use of EVERY GEDCOM constraint,
   (b) visual-evidence specificity, (c) soundness of the probability
   distribution. Write `DECISION.md` with the table + the determination.
4. **Persist:** only the **chosen** estimate goes to the DB; ALL candidates +
   the decision stay in the repo artifact.

## Schema rule — why only the chosen estimate goes in the DB

`date_labels` is keyed by `photo_id` (one row, upsert = **last-write-wins**) and
the website renders that single row. Writing all candidates would silently leave
only the most recent → the comparison is destroyed. `gemini_api_calls` is
append-only but **Gemini-shaped** (Gemini pricing/lineage) — Fable (Anthropic)
and Codex (OpenAI) outputs do NOT belong there.

Therefore:
- **DB (`date_labels` + `photo_locations`)** holds ONLY the chosen estimate +
  `analysis_provenance` (the website's single source of truth).
- **Repo artifact** (`docs/experiments/photo-estimates/<photo_id>-<date>/`)
  holds `PROMPT.txt`, every `candidate-<model>.json`, and `DECISION.md`.
  Reproducible, version-controlled, nothing lost. Do NOT commit the image
  (retrievable via the `site_url`/`photo_id` in `meta.json`).
- Upgrade path if DB-queryable cross-provider experiments are wanted at scale:
  a dedicated `photo_estimate_experiments` table (append-only, one row per
  model). Not needed for occasional admin runs.

## Manual-vs-platform provenance (structural, queryable)

A human-directed one-off MUST be distinguishable from a platform run by data
structure alone:
- `gemini_api_calls`: manual ⇒ `experiment_id LIKE 'manual-%'` AND
  `gemini_config->>'operator' = 'claude-code-manual'`. Platform ⇒
  `experiment_id` NULL, `operator='platform'` (the `_call_gemini_date_estimate`
  default).
- `date_labels.data.analysis_provenance.operator = 'claude-code-manual'` +
  `chosen_model` + `decision_artifact`. Platform reanalysis has no
  `analysis_provenance` block.

## Updating the live site

The production app caches `date_labels`/`photo_locations` in a module global
with **no TTL** — a direct Supabase write is NOT reflected until the app
re-reads on startup. A normal **deploy (`git push origin main`)** restarts the
app and surfaces the new estimate. Do NOT use `/api/sync/resync-supabase` to
bust the cache — it re-upserts volume JSON to Supabase (destructive).
Do NOT hit the in-app reanalyze button — it re-runs Gemini and overwrites the
chosen estimate.

## GEDCOM enrichment is mandatory for linked photos

If the photo has CONFIRMED, GEDCOM-linked faces, the estimate MUST run with
GEDCOM context (`_build_gedcom_context_for_photo`). Verify the context is
non-empty before running — a silent `None` means the loader is broken again
(see Lesson 205/206). Rich GEDCOM context is the single biggest accuracy lever:
it gives birth/death years (age anchoring), residence history (location), and a
hard date ceiling (a spouse's death year).

See: AD-251, Lessons 205/206/207, `docs/experiments/photo-estimates/`.
