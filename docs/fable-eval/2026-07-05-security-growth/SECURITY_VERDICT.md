# Security Verdict — the 51 anonymous "Compare Upload" pending entries

**Date:** 2026-07-05 · **Investigators:** Opus (orchestrator, code trace + verification) +
independent Codex gpt-5.5/xhigh (`codex-security.md`). Both fresh-context, agree.

## Bottom line for the owner

**This is not a breach, and your API keys are not exposed.** The 51 anonymous uploads are your
own **public face-compare tool** (`/tools/compare`) working exactly as built. When someone who
isn't logged in uploads a photo to "compare my face to the archive," the code queues that photo
into your admin **Pending Uploads** list tagged `source: "Compare Upload"`, `uploader: "unknown"`.
So bots and curious visitors testing the public tool show up as anonymous pending items. 51 over
~11 days is light traffic, not a flood or an attack.

**None are likely legitimate heritage photos.** The pattern — random modern selfies, no uploader,
no source, no collection — is bot/curiosity probing of a public tool, not family contributions.
Safe to reject all 51.

## What's actually protecting you (verified in code)
- Rate-limited (20/hr per IP), file-type-validated (jpg/png only — no arbitrary files), 10 MB cap,
  filename path-traversal sanitized on the upload write.
- Anonymous uploads only **queue** — they never enter the archive without your approval.
- No live secret is reachable by a browser: Supabase service-role key, R2 keys, Gemini key,
  session secret, and the ML service token are all **server-side only**. The one key present in
  page JS is the **public PostHog analytics key** — that's meant to be public. Benign.

## Two real (but limited) findings worth acting on — NOT the spam, and NOT key exposure to the web
1. **A real secret is committed to the repo.** `ML_SERVICE_TOKEN=VaIE…[REDACTED]` sits in
   `docs/session_logs/session-116-log.md`. It's not browser-reachable and only guards your internal
   Railway ML service (reachable only by someone with repo read access), but it IS a genuine secret
   in git. **Recommend: rotate the token on Railway** (that instantly kills the committed value).
   Scrubbing git history is optional once it's rotated.
2. **Missing path-traversal guard** on `/photos/{filename:path}` and `/uploads/facecompare/`
   (`app/main.py:1439` builds `photos_path / filename` with no containment check). Whether it's
   live-exploitable depends on the proxy/server normalizing `..`, but the guard is missing. Worst
   case it could read on-disk **data files** (which are largely public data anyway) — **not** env
   vars or keys. Cheap defense-in-depth fix: require the resolved path to stay under the base dir.

## The product problem underneath the spam (this is the real lesson)
Your public compare tool **persists** anonymous uploads (to R2 + the review queue) and conflates a
throwaway "compare my face" query with a durable archive **contribution**. That's fine today, but
it's the exact front door you'd send other Rhodes families through — so it's a content-liability +
admin-burden + trust problem before any growth. The fix (separating ephemeral compare from explicit
contribution) is designed in `SPAM_BOUNDARY_DESIGN.md` and is item #1 of `GROWTH_ROADMAP.md`.

## What to do now (in order)
1. **Reject the 51** — but note there's **no batch-reject** today (only one-at-a-time
   `/admin/pending/{job_id}/reject`, or `batch-approve` which you do NOT want). Adding a
   batch-reject filtered by `source=Compare Upload` is a small, high-value quick win (roadmap #3).
2. **Rotate `ML_SERVICE_TOKEN`** on Railway.
3. Schedule the path-traversal guard + the compare/contribution split into the implementation sprint.
4. Do **not** invite other communities until the compare front door is defanged (roadmap items 1-3).

## Full evidence
- `codex-security.md` — independent security audit (findings table with file:line, root-cause trace,
  secret-exposure proof, abuse-vector analysis).
- Verified by orchestrator: `app/compare_routes.py:1571-1700` (root cause), `app/main.py:1432-1446`
  (traversal), `app/rate_limit.py` (limiter), `docs/session_logs/session-116-log.md:50` (token).
